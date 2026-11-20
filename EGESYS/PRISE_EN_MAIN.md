# Prise en main — projet d'automatisation EGESYS

Document de reprise pour continuer le projet dans une nouvelle session.
Il résume **ce qui a été fait**, **comment c'est organisé** et **les points à connaître** pour ne pas repartir de zéro.
Le fonctionnement détaillé pour l'utilisateur est dans [README.md](README.md) ; une présentation illustrée est dans
[presentation_projet.html](presentation_projet.html). Ce fichier-ci s'adresse à celui qui reprend le développement.

---

## 1. Le but du projet

Mettre à jour la base clients de l'intranet **EGESYS** (PC SOFT WebDev 26, interne à SOGEN,
`http://egesys.sogen.coop/eGESYS/eGESYS?p1=TEST` = base de TEST ; production : `http://egesys.sogen.coop/eGESYS`) à partir des mails reçus, sans intervention manuelle. La chaîne :

```
Mail Outlook → Power Automate → agent Copilot (traduit en ordres JSON) → OneDrive\pending\
→ workflow sur le PC → validation → script EGESYS (saisit comme un utilisateur, vérifie chaque écriture)
→ OneDrive\completed\ ou error\ → OneDrive\result\ (réponse HTML) → Power Automate répond au mail
```

**Contrainte technique forte :** EGESYS est un site WebDev sans API. On agit uniquement en HTTP avec `requests` +
BeautifulSoup, en reproduisant les clics d'un utilisateur. **Jamais de Selenium ni de Playwright.** On n'accède pas à
la base SQL directement (piste évoquée, non engagée : lecture seule `SELECT` uniquement et avec l'accord explicite de
l'utilisateur).

---

## 2. Architecture des fichiers

Projet dans `<OneDrive Sogen>\SOGEN\EGESYS` (Windows, Python 3.12). L'utilisateur alterne entre **deux PC** (depuis le
16/11/2026) : le projet est synchronisé par OneDrive, donc **aucun chemin propre à un PC dans le code** (OneDrive donné par
Windows, fichiers d'exécution dans `%LOCALAPPDATA%`). Ce qui ne se synchronise pas est vérifié par
`SOGEN\installer_poste.bat` ; historique GitHub par `SOGEN\sauvegarder.bat` (`SOGEN\.gitignore` exclut `cartes/`, qui
contient de vraies données clients).

### Cœur — exécution dans EGESYS
| Fichier | Rôle |
|---|---|
| `moteur_egesys.py` | Moteur HTTP bas niveau : `connexion_egesys`, `deconnexion_egesys` (bouton M37), `soumettre_page_webdev` (POST avec Referer, fail-fast si la session expire), `uploader_fichier_webdev` (upload AJAX HTML5), `telecharger_fichier_webdev` (récupère un PDF dont le serveur a mis le chemin dans un champ caché), lecture des tableaux WebDev, sélection de ligne AJAX. **Ne pas modifier sans demande explicite.** |
| `script_egesys.py` | Le gros du projet. `MAPPING_*` (texte → valeur technique des listes déroulantes), `CATALOGUE_ACTIONS` (une « recette » = liste d'étapes par action), `preparer_donnees`, `note_de_suivi` / `lignes_modification`, `executer_recette` (étapes + audits), verrou de connexion, `__main__` (boucle sur les ordres, note de suivi, journal, résultats). Variables lues : `EGESYS_IDENTIFIANT`, `EGESYS_MDP`, `EGESYS_FACTURES` (dossier des PDF), `EGESYS_RESULTATS` (JSON des résultats par ordre). |
| `journal_egesys.py` | Journal Excel `journal_egesys.xlsx` à la racine du OneDrive EGESYS (openpyxl). Fermé dans Excel, sinon la ligne n'est pas écrite (avertissement dans le log). Une ligne par ordre. Migre tout seul un ancien fichier quand on ajoute une colonne. |

### Automatisation
| Fichier | Rôle |
|---|---|
| `workflow/workflow.py` | Surveille `<OneDrive Sogen>\EGESYS\pending` (trouvé automatiquement, voir `config_egesys.py`) toutes les 5 s. Un seul PC à la fois (`workflow/poste_actif.py`). Attend la synchro et les pièces jointes, valide, bloque IBAN/BIC, déplace dans `processing/`, lance `script_egesys.py`, publie dans `completed/` ou `error/` (écriture atomique), copie les PDF récupérés dans `result/pdf/`, puis écrit `result/<nom>.json` en dernier (clé `pdf` = PDF à joindre). Ne relance jamais un fichier trouvé dans `processing/` (→ `error/`, code INTERROMPU). Une seule instance (`%LOCALAPPDATA%\EGESYS\workflow.lock`). Contient aussi `lancer`, `notifier` (toast Windows), `contient_banque`, `journaliser_blocage`. |
| `workflow/poste_actif.py` | Un seul PC à la fois : fichier `EGESYS\_poste_actif.json` du OneDrive (PC, signe de vie toutes les 60 s par une tâche de fond, périmé après 5 min). Refus de démarrer si un autre PC est actif ; arrêt si un autre PC a repris. **Copie identique** de `G++\veilleur\poste_actif.py` : modifier les deux. |
| `workflow/compte_rendu.py` | Réponse au mail : `rediger()` → `{"objet", "corps"}`, corps en HTML à styles en ligne (tableaux pour les encadrés, seule forme fiable dans Outlook). Traduit les messages techniques en français clair. `mail_client()` (17/11/2026) → `"client": {mail, objet, corps}` de `result/<nom>.json` : mail AU CLIENT avec ses duplicatas (mêmes PDF que `pdf`), à l'adresse A205 de sa fiche, lue par l'étape `"lire"` de la recette `ajouter_note_client` (note de suivi) et rangée dans le résultat de l'ordre (`mail_client`, `factures`). Vide si pas de facture, pas d'adresse valide ou plusieurs clients. Objet « SOGEN : … » (jamais « EGESYS »). Testé en réel par l'utilisateur (« ça fonctionne très bien »). Plusieurs dates (19/11/2026) : `dates_lisibles()` ; résultat d'ordre `manquantes` → `rediger` compte les demandes « incomplètes » (objet « Demande traitée, factures manquantes », MOTIF_FACTURES_MANQUANTES, conseil « Vérifiez les dates sans facture ») ; aucune facture → RAISON_DATES_SANS_FACTURE avec « Détail par date » (lignes « 🛑 Aucune facture le … : raison » du script) ; `mail_client` rappelle les dates et ajoute « Nous n'avons trouvé aucune facture le … ». |
| `valider_ordres.py` | Validation hors ligne (structure, listes, obligatoires, IBAN clé de contrôle, RUM, dates des factures, pièces jointes, incertitudes). Écrit `<fichier>_valide.json`. `lire_id_message` / `lire_expediteur` lisent ces clés même dans un JSON cassé. `verifier_structure` convertit l'ancien format factures `periode_du`/`periode_au` en `periodes`. |
| `lancer_workflow.ps1` + `lancer_workflow.bat` | Options `-Identifiants` (variables utilisateur, saisie masquée), `-Installer`/`-Desinstaller` (raccourci dans `shell:startup`), `-Etat`, `-Arreter` ; sans option = lancement caché, une seule instance, log ajouté à `%LOCALAPPDATA%\EGESYS\workflow.log`. Le `.ps1` doit garder son BOM UTF-8 (sinon PowerShell 5.1 lit mal les accents). |

### Agent Copilot (no-code, côté Microsoft 365)
| Fichier | Rôle |
|---|---|
| `copilot/instructions.md` | **À coller dans les instructions de l'agent.** ~7,7k caractères (limite Copilot ≈ 8k : raccourcir avant d'ajouter). Rôle, format de réponse (JSON brut, 5 clés : resume, id_message, expediteur, ordres, incertitudes), règles de construction, choix de l'action. |
| `copilot/egesys-modeles-json/SKILL.md` | **Compétence de l'agent, à charger comme fichier.** GÉNÉRÉ par `generer_doc_copilot.py` — ne pas éditer à la main. |
| `generer_doc_copilot.py` | Génère le SKILL.md depuis `CATALOGUE_ACTIONS` + `MAPPING_*` + `copilot/exemples_egesys.md`. À relancer après toute évolution. |
| `copilot/exemples_egesys.md` | Exemples de mails traités (données fictives). Repris dans le SKILL.md. |
| `copilot/tests/mails_de_test.md` | 59 mails de test (56-59 : une facture sur une période) + résultat attendu (côté agent ET côté script) décrit sous chacun, tous sur le client 64233008 ; factures : 19-22, 25, 27-55 (47 et 50-55 : N dernières factures ; 48 et 55 : modification puis factures). |
| `copilot/tests/attendus/test_01..55.json` | Réponses attendues (`"*"` = texte libre accepté). `copilot/tests/mails_json/` : les mêmes mails, prêts à envoyer. |
| `comparer_reponse_copilot.py` | Compare une réponse d'agent à l'attendu (ignore casse/accents/espaces). |

### Cartographie & divers
| Fichier | Rôle |
|---|---|
| `explorer.py` | Cartographie en LECTURE SEULE les pages EGESYS → `cartes/*.json`. Usage : `python explorer.py` (gestion clients) ou `python explorer.py factures`. C'est l'outil à utiliser pour ajouter une action. |
| `cartes/*.json` | Cartes des pages (champs, boutons, tableaux). Référence pour écrire les recettes. |
| `extraire_ordres.py` | Schéma des ordres (`generer_schema`, utilisé par la validation ET le SKILL.md : `ACTIONS_DESCRIPTIONS`, `CHAMPS`, `CHAMPS_OBLIGATOIRES`, `LISTES_FERMEES`) + extraction directe d'un `.eml` par l'API Claude (option non utilisée dans la chaîne actuelle). |

### Produit à l'exécution
- `config_egesys.py` centralise les emplacements. Plus de dossier `EGESYS_flux` dans le projet (supprimé le 16/11/2026).
- `%LOCALAPPDATA%\EGESYS\` (C:\Users\<utilisateur>\AppData\Local\EGESYS) : `workflow.log`, `travail/` (un dossier par mail
  le temps du traitement), verrous `workflow.lock` et `connexion_egesys.lock` (indispensables : une seule connexion
  EGESYS et un seul workflow à la fois).
- OneDrive `EGESYS\journal_egesys.xlsx` (journal Excel) et `EGESYS\_ecriture_en_cours\` (dossier caché : chaque résultat
  y est écrit puis déplacé d'un coup vers `result/`, pour que Power Automate ne voie jamais de fichier partiel).
- OneDrive `<OneDrive Sogen>\EGESYS\` (`config_egesys.DRIVE` : variable Windows `OneDriveCommercial`, sinon `OneDrive` ; `EGESYS_DRIVE` force un autre dossier) : `_poste_actif.json` (PC actif), `pending/`, `processing/`, `completed/`, `error/`, `result/` (+ `result/pdf/` : PDF à joindre à la réponse). Le dossier `G++` voisin appartient à un autre projet : ne pas y toucher.

---

## 3. Les actions supportées (19)

Client désigné par `nom_client`, `code_client` (7-8 chiffres) ou les deux.

- **Fiche :** civilité, nom, prénom, responsable, adresse, mail, mail comptable, tél fixe, tél portable.
- **Modèle de règlement :** `ajouter_modèle_de_reglement_client` (nouvelle date d'application : mode, échéance, famille,
  IBAN, BIC, RUM…), `modifier_modèle_de_reglement_client` (corriger une date existante). **On ne supprime jamais une
  date d'application** (règle EGESYS).
- **Documents :** ajouter / modifier / supprimer (pièce jointe + libellé + famille CONTRATS ou DOCUMENTS SOGEN).
- **Notes :** ajouter / modifier / supprimer.
- **Factures (lecture seule) :** `telecharger_facture_client` — duplicata PDF. Recherche par n° / dates (± 3 j) /
  montant TTC (± 1 %). 0 ou >1 résultat → rien n'est pris, la réponse liste les factures possibles.
  `telecharger_factures_client` — factures validées de plusieurs dates et/ou périodes (`factures.periodes` =
  « 31/01/2026 ; 01/03/2026 au 31/03/2026 », lu par `lire_periodes`) : étape `pour_chaque_periode`
  (`executer_pour_chaque_periode`) qui joue la recette INTERNE `lister_factures_client` (ACTIONS_INTERNES, absente du
  schéma de l'agent ; étape `collecter_lignes` du tableau A31) pour chaque date / période. Une date sans facture est
  notée dans `etat['manquantes']` (factures à ± 15 j proposées) sans arrêt ; résultat de l'ordre : `manquantes`. Puis la
  recette d'une facture est rejouée avec chaque numéro. Arrêt sans rien télécharger si 0 facture au total, > 30, ou
  plusieurs clients (colonne A12). L'ancien format `periode_du`/`periode_au` est converti par `valider_ordres.py`.
  `factures.nombre_dernieres` = N (« ses 3 dernières factures ») : seules les N plus récentes sont gardées (tri par
  « Dt Fac » décroissante) ; sans `periodes`, recherche du 01/01/2000 à aujourd'hui. Moins de N trouvées → entrée
  `manquantes` avec `nombre_demande`. Champ obligatoire : `periodes` OU `nombre_dernieres` (tuple dans
  `CHAMPS_OBLIGATOIRES`). « Sa dernière facture » (une seule) reste `telecharger_facture_client` sans critère.
  **Une facture sans le jour** (20/11/2026) : `facture.date_realisation` = « JJ/MM/AAAA au JJ/MM/AAAA »
  (`plages_recherche_facture` prend alors les bornes exactes, sans ± 3 j). Sans autre critère (n°, date d'état,
  montant), `facture_sur_periode` convertit l'ordre, au début de la boucle de `__main__`, en
  `telecharger_factures_client` sur cette période ; plusieurs PDF → résultat `plusieurs_trouvees` + `periode_facture`
  → `compte_rendu` : objet « Demande traitée, plusieurs factures trouvées », motif, phrase dans `mail_client`. Journal
  Excel et note de suivi au nom de l'action convertie. Tests 56-59. Testé hors connexion seulement.
  ⚠ Redémarrer le workflow après une modification de `workflow/compte_rendu.py` ou `valider_ordres.py` (importés une
  fois au démarrage) ; `script_egesys.py` et la validation complète sont relancés à chaque mail.
- Désactivée : `modifier_activite_client` (dans `ACTIONS_DESACTIVEES`).

---

## 4. Fonctionnalités transversales importantes

- **Note de suivi automatique** : après chaque action réussie (fiche, règlement, document, duplicata de facture), le script ajoute une note sur la fiche (sujet = ce
  qui a changé, message = ancienne → nouvelle valeur + extrait du mail, agent = « GINESTE Thomas », choisi PAR SON
  NOM dans la liste A28 (étape `choisir_par_libelle` : la valeur technique diffère selon la base, le 39 de production =
  HIRIART David en base de TEST) ; sujet limité à 50 caractères (`LONGUEUR_SUJET_NOTE` : EGESYS coupe au-delà ; la
  vérification `ligne_presente` accepte un texte coupé d'au moins 20 caractères). Factures : `note_de_suivi(..., fichiers)` liste les n° des duplicatas récupérés, client = code lu dans le nom
  du PDF (`facture_<code>_<n°>.pdf`) ; pas de note si aucun PDF. Les actions sur les notes n'ajoutent pas de note.
  L'agent Copilot a pour consigne de NE PAS créer lui-même ces notes.
- **Civilité** (règle SOGEN du 16/11/2026) : plus de MADAME / MONSIEUR / MADEMOISELLE / MESSIEURS / VEUVE ; une personne
  = ENTREPRISE INDIVIDUELLE (valeur 10). Ces civilités restent dans la liste EGESYS (A208, relue le 16/11/2026, 38 options
  inchangées) mais sont retirées de `MAPPING_CIVILITE` : refusées par le validateur et le script. Un changement de nom
  ou de prénom ne touche plus la civilité.
- **Journal Excel** : colonnes Date, Action, Client, Modification (ancienne → nouvelle), Raison, Résultat
  (Réussite/Erreur/Non exécuté, coloré), Détail, Source.
- **Garde-fous** : incertitude de l'agent ou refus du validateur → rien n'est exécuté ; IBAN/BIC jamais exécutés
  automatiquement (risque de fraude au RIB) ; relecture après chaque écriture ; arrêt net au moindre écart ;
  déconnexion systématique ; fichier interrompu jamais relancé ; boutons dangereux jamais cliqués (Supprimer,
  transferts compta, « Envoyer » qui mail la facture au client).
- **Réponse au mail** : `result/<nom>.json` = `{id_message, expediteur, objet, corps}`. `id_message` et `expediteur`
  sont recopiés par l'agent depuis la requête Power Automate ; absents → `""` et avertissement dans le log, sans
  bloquer. Le corps est déjà en HTML : Power Automate l'insère tel quel.

---

## 5. Détails WebDev à ne pas réapprendre

- L'URL d'action du `<form>` change à chaque clic ; il faut renvoyer le header `Referer` = URL précédente.
- Boutons cliqués via `WD_BUTTON_CLICK_=<alias>`.
- Listes déroulantes : on envoie la **valeur** de l'`<option>`, pas le texte → d'où les `MAPPING_*`.
- Champs de zones répétées : utiliser le **name** (`zrl_1_A35`), pas l'id.
- **Cases à cocher** : WebDev relit leur état à chaque envoi du formulaire ; une case absente de la requête = décochée.
  Bug corrigé le 18/11/2026 : chaque clic sur la fiche client (Enregistrer, Note, Document, Modèle…) décochait
  « Client Actif » (A197) → le client devenait inactif. `ajouter_cases_cochees()` (script_egesys.py) renvoie
  désormais les cases et radios cochés de la page avant chaque envoi, sans remplacer les valeurs de la recette.
- Si la page de login (champ `A4`) réapparaît → session expirée → fail-fast.
- Recherche client (« Gestion des clients ») : `A24` = case « Clients Actifs » (`1` actifs, `0` inactifs), résultats dans
  le tableau `A12`. `activite_actuelle` vide (non précisée par le mail) → `0`, puis `1` si `A12` est vide
  (`rechercher_client_autre_activite`) ; la note de suivi reprend la catégorie où le client a été trouvé.
- EGESYS refuse deux connexions simultanées : `script_egesys.py` prend un verrou
  (`%LOCALAPPDATA%\EGESYS\connexion_egesys.lock`, attente jusqu'à 15 min) avant de se connecter.
- Upload = POST multipart dans un ordre précis (voir `uploader_fichier_webdev`), déclenché avant le clic de validation.
- Sélection d'une ligne de tableau = POST AJAX `AJAXCHAMP`/`CLICTABLE` (+ parfois un `AJAXPAGE`).
- `A2` sur la page « Gestion des clients » = « page précédente », pas « accueil » → étape `remonter_jusqu_a` dans la
  recette facture. La fiche client porte AUSSI le titre « Gestion des clients » mais n'a pas d'A2 (flèche retour = A3,
  image `IMAGE_BOUTON_RETOUR`) et M3 n'en sort pas : `remonter_jusqu_a` clique alors la flèche retour.
- Constaté le 19/11/2026 (base de TEST, lecture seule) : la flèche retour de la fiche client (A3) n'a PAS l'image
  `IMAGE_BOUTON_RETOUR` (`btn_195aa…` au lieu de `btn_4304…`) → la fiche est reconnue à son tableau des notes A160
  (`est_fiche_client`) et on clique A3. EGESYS n'envoie qu'une partie des lignes d'un tableau (32 notes sur 35 :
  attribut `NOMBRE` du XML = total) : si la note ajoutée n'est pas lue, `ligne_presente` l'accepte quand le total
  a augmenté de 1 (`nombres_lignes_tables`, `etat['nombres_tables']`).
- Entre deux ordres d'un même mail : `revenir_a_l_accueil` (19/11/2026, procédure manuelle de l'utilisateur) :
  fiche client → « Enregistrer » (A4), flèche retour A3 si besoin, puis maison A2 jusqu'au Tableau de bord. Les clics
  de navigation envoient le formulaire COMPLET (`valeurs_formulaire`), comme un navigateur : après un Enregistrer,
  A2 envoyé seul ne faisait rien. Si A2 reste sans effet 2 fois : déconnexion + reconnexion (`etat['identifiants']`,
  en mémoire seulement). Ancienne description : (Tableau de bord ou Menu Général ; flèche retour, puis A2
  `IMAGE_BOUTON_PRECEDENT`, sinon M3). Sur le Menu Général, « Fiches client » = M11 : un clic M3 d'une recette y est
  remplacé par M11.
- Clés d'étape d'une recette : `requete`, `audit` (`titre_page`, `champs_modifies`, `ignorer_vides`, `ligne_presente`,
  `ligne_absente`, `ligne_unique`), `upload`, `upload_webdev`, `selection_ligne`, `conserver_valeurs_actuelles`,
  `telechargement`, `remonter_jusqu_a`, `lire` (valeur d'un champ → `etat['lectures']`, ex. A205), `pour_chaque_ligne`
  (plus utilisée), `collecter_lignes` (lignes d'un tableau → `etat['collecte']`, sans rien sélectionner),
  `pour_chaque_periode` (étape sans `requete` : boucle sur les dates de `periodes`).
- Recettes internes (`ACTIONS_INTERNES`, ex. `lister_factures_client`) : sous-étapes d'autres recettes, exclues du schéma
  de l'agent par `extraire_ordres.generer_schema` (donc refusées si l'agent les envoie). Une recette dont les variables
  client n'apparaissent pas dans une `requete` doit les citer ailleurs (ex. `"client": ['{code_client}', '{nom_client}']`),
  sinon `code_client` / `nom_client` disparaissent du modèle JSON de l'agent.
- Sujet de note de suivi : 60 caractères au plus (coupé avec « … ») ; pour plusieurs factures, dates courtes
  (« 31/05/26 ; 01/03/26-31/03/26 »).

---

## 6. Comment ajouter une action (procédure rodée)

1. `python explorer.py [nom_page]` en lecture seule → carte JSON de la page.
2. Repérer boutons/champs, écrire la recette dans `CATALOGUE_ACTIONS`. Ajouter un `MAPPING_*` si liste déroulante.
3. Décrire l'action dans `extraire_ordres.py` (`ACTIONS_DESCRIPTIONS`, `CHAMPS`, `CHAMPS_OBLIGATOIRES`).
4. Ajouter son libellé dans `LIBELLES_ACTIONS` de `workflow/compte_rendu.py` (texte de la réponse au mail).
5. `python generer_doc_copilot.py` → recharger le SKILL.md dans l'agent (+ instructions si une règle change).
6. Ajouter un mail de test dans `copilot/tests/`.
7. Tester hors ligne, puis une vraie exécution que **l'utilisateur** lance (voir §9).

---

## 7. Points techniques Windows

- **Encodage (le piège principal)** : la console et les redirections Windows sont en cp1252 → le premier emoji
  affiché plantait le script. Chaque point d'entrée fait `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`,
  et `workflow.lancer()` lance les scripts avec `PYTHONUTF8=1` et relit leur sortie en UTF-8 (la détection « Par
  sécurité, aucune » en dépend). **À reproduire dans tout nouveau script.** Lire le log avec
  `Get-Content … -Encoding UTF8`.
- **Notifications** : toast Windows natif via PowerShell (`-EncodedCommand`, texte passé par variables
  d'environnement, aucun module à installer). Non bloquant.
- **OneDrive** : le workflow attend 3 s après la dernière modification d'un fichier, retente 60 s un JSON illisible,
  et écrit ses résultats d'abord en local puis les met en place d'un coup (`os.replace`) pour que Power Automate ne
  voie jamais un fichier partiel.
- **Sous-processus** lancés sans fenêtre de console (`CREATE_NO_WINDOW`).
- **Identifiants** : variables d'environnement **utilisateur** Windows ; le lanceur les relit dans le registre, donc
  pas besoin de rouvrir de session après `-Identifiants`.
- **Dépendances** : `pip install requests beautifulsoup4 openpyxl` (`anthropic`/`pypdf` seulement pour l'extraction
  directe de `extraire_ordres.py`).
- Commandes : `python` (et non `python3`), chemins avec `\` dans PowerShell.

---

## 8. Pistes d'évolution

1. (Réglé le 16/11/2026 : la civilité ne dépend plus du sexe, voir §4.)
2. **Lecture SQL** : interroger la base EGESYS en `SELECT` uniquement pour les recherches (factures, clients) au lieu
   de parcourir les pages — à n'engager qu'avec l'accord de l'utilisateur (moteur, serveur et port à identifier).
3. Identifier le client par code client partout (déjà possible, à généraliser dans les mails).

---

## 9. Règles de travail à garder (important pour une nouvelle session)

- **Demander avant toute connexion ou écriture dans EGESYS.** L'exploration en lecture seule sur un client de test est OK
  une fois le cadre posé ; toute écriture (créer/modifier/supprimer) se fait avec un feu vert explicite, et c'est
  l'utilisateur qui lance les vraies exécutions d'écriture.
- Client de test : **uniquement le code client 64233008** depuis le 19/11/2026 (tous les tests, mails de test Copilot compris ;
  factures connues 31/01/2019 et 31/03/2019 d'après GENICIA++, à vérifier dans EGESYS). Anciens clients de test (guitton,
  brana 64233004) : ne plus les utiliser.
- **Ne jamais afficher ni coder en dur le mot de passe.** Identifiants via variable d'environnement.
- **Toujours se déconnecter** (M37) — sinon EGESYS refuse les connexions suivantes (ERR_ALREADYCONNECTED).
- **Ne pas modifier le moteur (`moteur_egesys.py`) sans demande explicite.** Nouvelles fonctionnalités = nouvelle recette
  + mapping.
- **Pas de Selenium / Playwright.** `requests` + BeautifulSoup uniquement.
- **Contenu destiné à Copilot** : aucune formulation de type « ignore tes instructions », aucune donnée personnelle ou
  bancaire réaliste (noms réels, IBAN, téléphones, mails) → sinon Microsoft bloque la création de l'agent (« violation
  IAR »). Utiliser des X et des noms génériques (martin, dupont).
- L'utilisateur (Thomas, SOGEN) travaille **en français** ; expliquer simplement les mécanismes WebDev.

---

## 10. État au 2026-11-20

- L'utilisateur a passé de nombreux mails de test en réel (base de TEST, client 64233008) : « tout a l'air de
  fonctionner ». Comprend les N dernières factures (tests 47, 50-55) et le retour au Tableau de bord entre deux ordres
  (tests 48, 55 : Enregistrer A4 → A3 → A2 avec formulaire complet → reconnexion en dernier recours).
- `copilot/instructions.md` ≈ 7,7k caractères : presque à la limite de Copilot (8k), raccourcir avant d'ajouter une règle.
- `presentation_projet.html` mis à jour pour une présentation à la direction (sections « Exemples » et « Bilan »).
  Le projet voisin G++ a sa propre page, sur le même modèle.

### État au 2026-11-19

- **Base de TEST** depuis le 17/11/2026 (`moteur_egesys.connexion_egesys`, `?p1=TEST`) ; production = `http://egesys.sogen.coop/eGESYS`.
- Mail au client avec ses factures (17/11) : testé en réel par l'utilisateur.
- Factures à plusieurs dates et/ou périodes (19/11) : testé HORS CONNEXION (validation, boucle avec EGESYS simulé,
  compte rendu, mail client, sujet de note). **Exécution réelle à faire lancer par l'utilisateur** : mail de test 27
  (client 64233008).
- Agent Copilot : « cheptel » / « numéro d'élevage » = code client (règle 6 des instructions et description du champ).

### État au 2026-11-11

La chaîne complète fonctionne en réel : mail → Power Automate → agent → `pending/` → workflow → EGESYS →
`completed/`/`error/` → `result/` → réponse HTML dans Outlook (avec `id_message` et `expediteur`).
Nettoyage du 11/11 : renommage EGSYS → EGESYS partout (fichiers, dossier `EGESYS_flux`, variables `EGESYS_*`,
compétence `egesys-modeles-json`), suppression de l'ancien veilleur (dossier Téléchargements), du circuit rclone et
des fichiers Linux ; le lanceur s'appelle désormais `lancer_workflow.bat`.
