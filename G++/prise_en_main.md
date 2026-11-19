# Prise en main du projet (à lire par Claude en début de session)

Ce fichier transmet tout le contexte du projet. Lis-le en entier avant d'agir.
Mis à jour le 11/11/2026 (chaîne mail ajoutée, voir §10).

---

## 1. L'utilisateur et sa demande

- Thomas Gineste, à la SOGEN (coopérative d'insémination bovine).
- Il écrit en français. Il n'est pas développeur. Il veut **des explications simples et courtes** :
  il a déjà dit « je ne comprends rien tout est brouillon ». Fais des listes claires, pas de jargon,
  et explique ce qu'il a à faire.
- Son but : automatiser des tâches dans le logiciel **GENICIA++ v2026.10.14**, en lecture
  (récupérer des informations) comme en écriture.
- Sa manière de travailler : il décrit **un parcours précis** dans le logiciel (voir `g++.txt`).
  Claude explore ce parcours étape par étape, puis code l'action pour qu'elle soit rejouable à volonté.
- Il **refuse l'exploration automatique de tout le logiciel** (une « cartographie » a été proposée puis abandonnée) :
  « chaque écran est différent, les informations ne se récupèrent pas de la même manière ».
  On ne fait pas d'exploration à l'aveugle : uniquement les parcours qu'il demande.
- Pendant les explorations, il ferme GENICIA++ ou le laisse sur un écran, et ne touche plus au poste.

---

## 2. Règles à respecter (non négociables)

1. **Identifiants et mots de passe : jamais en clair.** Pas d'affichage, pas de copie, pas de stockage.
   Masque-les avec `XXX` quand tu montres une configuration.
   - Les identifiants GENICIA++ de l'utilisateur sont dans le Gestionnaire d'identifiants Windows
     (`keyring`, service `GENICIA++`). Ne les lis jamais pour les afficher.
   - `GPP\packages\gpp.prm` (XML) et le DSN ODBC `bddg++` contiennent le compte DBA de la base.
     **Erreur déjà commise deux fois :** un masquage par regex n'a pas couvert les balises XML de `gpp.prm`,
     puis un mot de passe web généré est apparu en clair dans une sortie (champ « Mot de passe » et corps
     du mail d'identifiants). Avant d'afficher le contenu d'un écran ou d'un fichier, masque **tout** texte
     qui contient un mot de passe : les champs `password text`, le champ à droite du libellé
     « Mot de passe », et toute chaîne qui contient « Mot de passe: ».
2. **Base de PRODUCTION.** Toute action qui modifie des données doit avoir été demandée explicitement.
   Avant un clic sur VALIDER / ENREGISTRER / CREER / MODIFIER / SUPPRIMER / OUI dans une confirmation,
   **lis la fenêtre et vérifie que c'est bien ce qui est prévu**. Si le parcours réel ne correspond pas à
   la description de l'utilisateur, **arrête-toi et demande** (exemple réel : il manquait
   « ENREGISTRER DROITS » dans sa description de l'action espace).
3. Les tests de modification se font sur **le cheptel de test 64284002** (GAEC LES VIGNES ROUSSES),
   que l'utilisateur a modifié exprès. Les PDF portent l'en-tête « TEST SOGEN ».
   L'adresse mail de sa fiche reçoit les mails de l'action espace.
4. Base de données : **uniquement des `SELECT`**. L'utilisateur autorise l'usage du compte du DSN pour lire.
5. Attentes explicites (attendre un écran, un élément, une boîte) plutôt que des `sleep`. Éléments trouvés
   par nom, type ou libellé. Les coordonnées ne servent qu'au clic souris, et viennent toujours de la position
   donnée par Java pour l'élément.
6. Avant de modifier un fichier de l'utilisateur, relis-le : il écrit parfois dedans (notes dans `main.py`, `g++.txt`).

---

## 3. Ce qu'est GENICIA++ (déjà analysé, ne pas refaire)

- **Application Java Swing** (Java 8u25 64 bits, `C:\Program Files\Java\jre1.8.0_25`).
  Les `.exe` sont de petits lanceurs (compilés avec MinGW) : le vrai code est dans `GPP\lib\gpp.jar`.
  Interface principale : `javaw ... psaihm.StructAccueilIHM`.
- Les `.bat` lancent des classes de `gpp.jar` (`psrvtransfert.CtrlTransfert`, `papplication.Publication`,
  `papplication.RejeuMic`...). Les `.kix` (KiXtart) enchaînent les traitements de nuit : sauvegarde de la base,
  rejeu, transferts (voir `rtcol.kix`).
- **Base** : Sybase SQL Anywhere 9, fichier local `GPP\bdd\bddg++.db`, moteur `dbeng9` démarré par
  l'application. DSN ODBC 64 bits `bddg++`. 305 tables + 4 vues, environ 32,5 millions de lignes, 5,3 Go.
  `rtcol.kix` arrête et sauvegarde la base la nuit.
- Échanges : fichiers XML dans `C:\Logicia\Genicia\transgpp`, Telelogos MediaTransfer (`transfert.ini`).
- Les backends `win32` et `uia` de pywinauto **ne voient rien** : une seule fenêtre `SunAwtFrame`, sans enfants.
  La solution retenue est **Java Access Bridge** (JAB), activé avec `jabswitch -enable`, utilisé via **pyjab**
  et des appels directs au bridge.
- Titre de la fenêtre principale : `GENICIA++ v2026.10.14 <date> N° Opérateur : 022 / ... - [<ÉCRAN>]`.
  L'écran courant est entre crochets ; sans crochets, c'est l'accueil (`titre_fenetre_principale()` renvoie « ACCUEIL »).
  Fenêtre de connexion : `Genicia++ V2026.10.14 Informations de session` (minuscules !).
- Sur un écran ouvert, les menus du haut sont **désactivés** : il faut revenir à l'accueil (QUITTER (ESC)) pour naviguer.
- Les menus déroulants restent souvent ouverts après un clic accessible. Le **clic souris suivant sert juste
  à les fermer** : il faut recliquer (c'est ce que ferait un humain).
- Organisation type d'un écran : boutons de fonction à gauche (`F5 ...`, `F6 ...`), en bas
  `PRECEDENT / VALIDER (F12) / QUITTER (ESC) / SUIVANT`, en haut un titre souligné.

---

## 4. Les pièges techniques (erreurs à ne pas refaire)

| Piège | Ce qu'il faut faire |
|---|---|
| `pyjab` ne trouve pas `WindowsAccessBridge-64.dll` | Passer `bridge_dll=DLL_BRIDGE` (constante de `genicia_auto.py`) |
| Les recherches de pyjab (`find_elements_by_*`, `visible=True` ou non) plantent avec `getVisibleChildren error` / `GetAccessibleContextInfo error` | Utiliser le parcours maison `elements_affiches()`, qui ignore les éléments en erreur et ne descend que dans les zones affichées (`showing`) |
| **Un clic accessible (`element.click()`) sur un bouton qui ouvre une fenêtre modale bloque tout Java Access Bridge** tant que la fenêtre reste ouverte : plus aucun appel ne répond, même `isJavaWindow` sur la fenêtre principale | Pour ces boutons, utiliser `cliquer_souris()` / `ouvrir_dialogue()` (vrai clic souris). Pour débloquer : mettre la boîte au premier plan avec pywinauto et envoyer `{ESC}` |
| `JABDriver(hwnd=<boîte>)` refuse les boîtes de dialogue (« is not Java Window ») | `attendre_dialogue(driver, titre)` : passe par `bridge.getAccessibleContextFromHWND` avec le bridge de la fenêtre principale |
| Le clic souris de pyjab (`click(simulate=True)`) tombe à côté | Clic pywinauto au centre de `bounds` (les coordonnées JAB = coordonnées écran) |
| Clic souris instantané ignoré par Java | Clic décomposé : déplacer, attendre 0,3 s, appuyer, attendre 0,15 s, relâcher (déjà dans `clic_souris_element`) |
| Clic ignoré juste après un changement d'écran, ou « mangé » par un menu resté ouvert | Recliquer jusqu'à ce que l'effet attendu se produise : `ouvrir_dialogue()`, `cliquer_souris_jusqua()` |
| VS Code passe devant GENICIA++ et reçoit les clics | `premier_plan(hwnd)` vérifie `GetForegroundWindow` avant chaque clic souris et refuse de cliquer sinon |
| La fenêtre GENICIA++ change de position (x négatif parfois) | Toujours relire `bounds` juste avant de cliquer, ne jamais garder de coordonnées |
| Les lignes de liste n'ont pas de nom | Une ligne est un panneau d'étiquettes `label`, une par colonne, dans l'ordre des en-têtes (colonnes cachées comprises, souvent avec une étiquette vide en premier) : `lire_lignes()` |
| Sélectionner une ligne de liste | `selectionner_ligne(liste, index)` (`clear/addAccessibleSelectionFromContext`). Ça active bien les boutons qui dépendent de la sélection |
| Listes déroulantes (combo box) : valeur `None` en lecture | Options = étiquettes enfants, l'option choisie a l'état `selected`. `choisir(combo, option)` fait la sélection et la vérifie |
| Libellé trouvé par « contient » (« A » trouvait n'importe quel libellé) | `libelle()` cherche d'abord une égalité exacte (sans HTML ni « : »), puis « commence par » |
| Boutons au nom précédé d'une espace (`' FACTURES SANS PJ'`) | Copier le nom exact relevé à l'écran |
| PowerShell : un `python -c "..."` qui contient une apostrophe (`D'UNE FACTURE`) provoque une erreur d'analyse | Écrire le code dans un fichier `.py` du scratchpad et l'exécuter |
| Masquage des secrets incomplet (voir règle 1) | Masquer par rôle (`password text`), par libellé voisin et par motif dans les textes longs |

---

## 5. Architecture du code

```
main.py                     point d'entrée : sous-commandes « facture » et « espace »
action_facture.py           telecharger_facture(d, cheptel, date_facture, debut, dossier)
                            telecharger_factures(d, cheptel, periode_du, periode_au, dossier) -> [{chemin, numero, date}]
                              (17/11/2026 : toutes les factures d'une période, 30 max (MAX_FACTURES d'ordres_genicia),
                              facture = Type « F » + Transaction en chiffres ; n° contrôlé sur « DETAIL D'UNE FACTURE »
                              (libellé « Facture n°… ») avant chaque PDF ; QUITTER (ESC) une fois pour revenir à
                              l'analyse ; la date de Fin n'est pas toujours appliquée par GENICIA++ → filtre en Python)
action_espace_adherent.py   generer_espace_adherent(d, cheptel, profil) -> {eleveur, profil, destinataire, abonnements}
action_mail_eleveur.py      lire_mail_eleveur(d, cheptel) -> adresse « e-mail » de la fiche éleveur (lecture seule)
genicia_auto.py             boîte à outils (voir ci-dessous)
file_attente_genicia.py     (18/11/2026) `with tour_genicia(desc):` autour de TOUT pilotage de GENICIA++ (main.py,
                              executer_ordres.py). Verrou %LOCALAPPDATA%\GENICIA\execution.lock + tickets FIFO
                              file_attente\<time_ns>_<pid>.ticket (ticket verrouillé = programme vivant). Attente max
                              1 h (GeniciaOccupe). Marqueurs ⏳/▶️ lus par le veilleur : le délai max repart au tour.
                              Tout nouveau script qui pilote GENICIA++ DOIT passer par tour_genicia.
--- chaîne mail (ajoutée le 11/11/2026, voir §10) ---
ordres_genicia.py           CATALOGUE des actions par mail (référence unique), lire_reponse, valider, valider_ordre
executer_ordres.py          exécute un JSON contrôlé dans GENICIA++ (ACTIONS : nom JSON -> fonction), résultats par ordre
veilleur/veilleur_genicia.py surveille OneDrive G++\pending, contrôle, exécute (sous-processus + délai max), range, result/
veilleur/compte_rendu.py    rediger(code, controle, resultats) -> {objet, corps HTML}
lancer_veilleur.ps1/.bat    -Identifiants / -Installer / -Desinstaller / -Etat / -Arreter ; BOM UTF-8 obligatoire sur le .ps1
generer_doc_copilot.py      génère copilot/genicia-modeles-json/SKILL.md (ne pas éditer le SKILL.md à la main)
comparer_reponse_copilot.py compare une réponse de l'agent à copilot/tests/attendus/test_XX.json
copilot/                    instructions.md (à coller dans l'agent), exemples.md, SKILL.md généré, tests/
config_genicia.py           DRIVE (OneDrive G++ trouvé automatiquement) et FLUX (%LOCALAPPDATA%\GENICIA, propre au PC)
veilleur/poste_actif.py     un seul PC à la fois (G++\_poste_actif.json) ; COPIE IDENTIQUE de EGESYS\workflow\poste_actif.py
%LOCALAPPDATA%\GENICIA\     produit à l'exécution : veilleur.log, veilleur.lock, rapports/, travail/ (ancien GENICIA_flux/)
enregistrer_identifiants.py met les identifiants dans keyring
inspecter_ecran.py          relève les éléments des fenêtres Java dans arbre_interface.txt
                            (il passe par JABDriver par fenêtre et peut donc échouer sur les boîtes de dialogue)
lecture_bdd.py              lecture ODBC, SELECT uniquement (tables / colonnes / apercu / sql, --csv, --compte-dsn)
apercu_base.py              résumé de toute la base -> apercu_base.txt
g++.txt                     notes de l'utilisateur : les parcours des actions
factures/                   PDF produits
```

Fonctions principales de `genicia_auto.py` :
- **Fenêtres** : `lancer_et_connecter()`, `attendre_fenetre(titre_partiel)`, `attendre_dialogue(d, titre_exact)`,
  `dialogues_ouverts()`, `dialogue_ouvert(titre)`, `titre_fenetre_principale()`, `attendre_ecran(titre)`, `premier_plan(hwnd)`.
- **Éléments** : `elements_affiches(cible)`, `visibles(cible, role)`, `attendre_element(cible, nom, role)`,
  `trouver(cible, nom, role)` (cherche aussi les éléments cachés, par exemple l'entrée d'un menu replié), `enfants(e)`.
  `cible` = un `JABDriver` (fenêtre principale) ou la racine `JABElement` d'une boîte de dialogue.
- **Actions** : `cliquer()` (accessible), `cliquer_souris()`, `clic_souris_element(e)`, `ouvrir_dialogue(...)`,
  `cliquer_souris_jusqua(cible, nom, condition)`, `ecrire(element, texte)`, `champ_par_libelle()`,
  `liste_deroulante_par_libelle()`, `choisir()`, `valeur_liste_deroulante()`.
- **Listes** : `liste_affichee()`, `lire_lignes()`, `attendre_lignes()`, `selectionner_ligne()`.
- **Application** : `lancer_et_connecter()`, `quitter_application(d)` (ferme GENICIA++ depuis l'accueil).
- **Navigation** : `aller_a(d, "Menu > Entrée > Bouton")` (clics accessibles),
  `quitter_ecran(d)` (QUITTER (ESC) jusqu'à l'accueil ; s'arrête si une boîte est ouverte),
  `rechercher_eleveur(d, cheptel, ecran_suivant_pret)` (écran de recherche d'éleveur commun à plusieurs menus :
  avec un seul résultat, GENICIA++ passe seul à l'écran suivant).

Règle pratique : **clic accessible** pour la navigation simple (menus, boutons qui changent d'écran) ;
**clic souris** pour tout bouton qui ouvre une boîte (Impression, Aperçu, Confirmation, Enregistrer...) ou qui peut
être « mangé » (bouton clé, VALIDER sur un écran de mail...).

---

## 6. Ce qui est fait et testé

| Élément | État |
|---|---|
| Lancement + connexion par keyring | Testé plusieurs fois (le lancement depuis GENICIA++ fermé a été testé avant les dernières modifications, et ce code n'a pas changé) |
| Action facture (`python main.py facture`) | Testée 3 fois de bout en bout. PDF vérifié avec pypdf (DUPLICATA, bon n°) |
| Action espace (`python main.py espace 64284002`) | Testée de bout en bout. **L'étape FACTURES SANS PJ n'a été faite qu'à la main** : au test final, l'abonnement existait déjà et l'étape a été sautée. À valider sur un éleveur sans abonnement |
| Lecture de la base | `lecture_bdd.py` et `apercu_base.py` fonctionnent (309 tables lues sans erreur) |
| Recherche de taureaux (Bovin > Taureau > F6 CONSULTER > Nom Mâle) | Fonctionnait, **supprimée à la demande** de l'utilisateur. Les colonnes de cette liste étaient : `_`, N° Travail, Nom, N° National, oidSexage, Pays, OID |

Détails des écrans relevés :
- **Bilan éleveur** : écrans « Recherche éleveur » → « BILAN ELEVEUR » → « ANALYSE D'UN BILAN ELEVEUR »
  (colonnes : `_`, Sequence, Date (jj/mm/aa), Op., Transaction (n° facture suivi de `*`), Débit, Crédit,
  Montant dû, Type (F facture, R règlement, E solde, N non facturé), codeCouleurLigne, oid) →
  « DETAIL D'UNE FACTURE ». Boîtes : « Impression » (imprimante, Aperçu/OK/Annuler) → « Aperçu avant impression »
  (menu Fichier > Enregistrer en PDF... / Fermer) → « Enregistrement du rapport en PDF ... » (Nom du fichier = chemin complet, Confirmer).
- **Communication éleveur** : « GESTION DES ELEVEURS » → F14 COMMUNIC. → « COMMUNICATION AVEC L'ELEVEUR »
  (Droits Oui/Non ; Profil : ELWEB1 STANDARD, PRWEB2 STANDART+, PRWEB3 TECHNIQUE, PRWEB4 TECHNIQUE+, PRWEBA BASE,
  FOAD/FOAR/FOIN, PAR, TK ; clé sans nom à droite du mot de passe ; ENREGISTRER DROITS → boîte « Confirmation »
  « Souhaitez-vous envoyer un mail récapitulatif avec les identifiants WEB ? » OUI/NON →
  « ENVOI IDENTIFIANTS WEB DE L'ELEVEUR » (A, CC, Objet, Message ; VALIDER = envoi) ; liste des abonnements
  (colonnes : `_`, Nom du document, Média, Fréquence Envoi, oidCheptel, oidAbonnement)).
- Menus relevés (76 entrées actives pour l'opérateur 022) : Organisation, Bovin, Administratif, Paramétrage,
  Système, Génicia. Plusieurs entrées de Système sont grisées pour ce profil.

---

## 7. Méthode pour ajouter une nouvelle action

1. Lire la description de l'utilisateur (souvent dans `g++.txt`). Demander les données de test (cheptel, dates...).
2. Créer dans le **scratchpad** de petits outils jetables :
   - `ecran.py` : affiche les éléments affichés de la fenêtre principale **et des boîtes ouvertes**
     (rôle | nom | position | états | valeur), **avec masquage des mots de passe** ;
   - un script par étape. Ne pas utiliser `python -c` sous PowerShell dès qu'il y a des apostrophes.
3. Avancer **une étape à la fois** : action → `ecran.py` → décider de la suite. Prendre une capture d'écran
   (.NET `CopyFromScreen`, PIL n'est pas installé) quand le résultat est inattendu.
4. Pour chaque clic, se demander : est-ce qu'il ouvre une boîte ? Si oui, clic souris.
   Est-ce qu'il modifie des données ? Si oui, lire la confirmation et vérifier que c'est prévu.
5. Écrire `action_<nom>.py`, avec en tête la **liste numérotée des étapes réelles** (noms exacts des écrans,
   boutons et boîtes), une fonction principale et un `try/finally` qui referme les boîtes et revient à l'accueil.
6. Ajouter une sous-commande dans `main.py` et une section dans `README.md`.
7. Tester de bout en bout au moins deux fois, puis **retester les autres actions** si `genicia_auto.py` a changé.

---

## 8. Idées pas encore réalisées

- **Trouver quelles tables bougent lors d'une action** : compter les lignes (ou faire des `SELECT` ciblés)
  avant et après une action faite dans l'interface sur le client de test. Ça répond à la question de départ de
  l'utilisateur : « quelles tables et quelles valeurs sont modifiées, ajoutées, supprimées ».
- Plus tard : la **lecture par la base** pour les consultations en masse, et l'**interface** pour les modifications
  (pour respecter les règles métier du logiciel).
- Lancer une action sur **plusieurs éleveurs** à partir d'une liste ou d'un CSV.
- Exporter des résultats en CSV/Excel (la sortie `--csv` existe déjà pour la base).
- Option « ne pas envoyer le mail » pour l'action espace (bouton NON de la confirmation) : **écran suivant inconnu, pas exploré**.
- `inspecter_ecran.py` : le faire passer par `attendre_dialogue` pour qu'il lise aussi les boîtes de dialogue,
  et lui ajouter le masquage des mots de passe.
- Points à faire valider par l'utilisateur et son IT : autorisation de l'automatisation, compte de base
  en lecture seule, environnement de test séparé. Le compte DBA par défaut stocké en clair dans `gpp.prm`
  et dans le DSN est un risque de sécurité à signaler.

---

## 9. Environnement

- Windows 10 Enterprise LTSC, écran 1920×1080. Shells : PowerShell 5.1 (principal) et Git Bash.
- Python 3.12 64 bits (`C:\Program Files\Python312`). Paquets installés : pywinauto 0.6.9, pyjab 1.12.0,
  keyring, pyodbc 5.5.0, pypdf 7.0.0. **PIL n'est pas installé.**
- VS Code tourne en administrateur. GENICIA++ est souvent ouvert sur le même écran, et VS Code peut passer devant lui.
- Java Access Bridge est activé dans `%USERPROFILE%\.accessibility.properties`.

---

## 10. Chaîne mail → GENICIA++ (sur le modèle d'EGESYS)

Objectif fixé le 11/11/2026 : faire comme le projet voisin `EGESYS` (abouti, en service).
Mail → Power Automate n°1 → agent Copilot GENICIA++ (JSON) → `OneDrive - Sogen\G++\pending\` → veilleur →
GENICIA++ → `completed\`/`error\` → `result\<nom>.json` → Power Automate n°2 répond au mail.

**Deux sessions Claude** peuvent travailler dans le projet `SOGEN` : une pour EGESYS, une pour G++. Ne modifier EGESYS
que si l'utilisateur le demande (il l'a fait le 17/11/2026 pour le fonctionnement sur deux PC). Collisions à éviter :
- dossiers OneDrive : EGESYS utilise `OneDrive - Sogen\EGESYS\…` ; G++ utilise `OneDrive - Sogen\G++\…` ;
- nom du programme : `lancer_workflow.ps1 -Arreter` d'EGESYS tue tout python dont la ligne de commande contient
  `workflow.py` → le nôtre s'appelle `veilleur_genicia.py` ; verrou propre `%LOCALAPPDATA%\GENICIA\veilleur.lock`.

**Deux PC (depuis le 16/11/2026)** : l'utilisateur alterne entre deux PC Windows. Le projet `SOGEN` est lui-même dans
OneDrive (`<OneDrive Sogen>\SOGEN`) : le code est synchronisé automatiquement. Règles :
- **aucun chemin propre à un PC dans le code** : le OneDrive est donné par Windows (`OneDriveCommercial`), les fichiers
  d'exécution vont dans `%LOCALAPPDATA%` (jamais dans le projet, qui est synchronisé) ;
- ce qui ne se synchronise pas (Python, bibliothèques, identifiants, Java Access Bridge, Git, démarrage auto) est vérifié
  par `SOGEN\installer_poste.bat` (`-Verifier` : sans rien modifier) ;
- un seul PC traite les mails : `poste_actif.py` (fichier `_poste_actif.json` dans le OneDrive, signe de vie toutes les
  60 s, périmé après 5 min) ;
- historique sur GitHub : `SOGEN\sauvegarder.bat` (commit + push) ; `.gitignore` exclut les données clients
  (`G++/apercu_base.txt`, `EGESYS/cartes/`, PDF, CSV, xlsx) et les fichiers d'exécution.

Aiguillage des mails : **filtre d'objet** dans Power Automate, « EGESYS » pour l'un, « G++ » pour l'autre. L'objet de nos réponses (« GENICIA++ : … ») ne doit JAMAIS contenir « G++ » (risque de boucle : une réponse revenant dans la boîte surveillée relancerait le flux n°1) ; l'agent ignore aussi les comptes rendus automatiques (test 10).

Décisions de l'utilisateur (11/11/2026) :
- **toutes les actions sont exécutées automatiquement** par mail, y compris « espace » (pas de liste d'expéditeurs
  autorisés pour l'instant ; à revoir plus tard si besoin) ;
- (13/11/2026) **le PDF est joint à la réponse** : champ `pdf` du JSON de `result/` = liste des NOMS des PDF déposés dans
  `G++\result\pdf\` (`<nom>_<cheptel>_<n° facture>_<date>.pdf`) ; les PDF y sont copiés avant l'écriture du JSON (l'original reste dans `completed\`).
  Le flux n°2 les ajoute en pièces jointes puis les supprime de `result\pdf\` (nettoyage côté flux) ;
- format de la réponse identique à EGESYS (`{id_message, expediteur, objet, corps}` + `pdf`) pour pouvoir dupliquer ses flux
  Power Automate ; le rapport détaillé est `<nom>_rapport.txt`.

JSON de l'agent : `{resume, id_message, expediteur, ordres, incertitudes}` ; ordres à plat :
`{action, justification, cheptel, nom_eleveur, date_facture}` (facture) ou `{…, profil}` (espace, "" → ELWEB1 STANDARD).
Le cheptel est obligatoire (pas de recherche par nom). Période du bilan pour la facture : 01/01 de l'année de la facture.

Mail au client (17/11/2026) : l'utilisateur transfère simplement le mail du client. Après chaque facture récupérée,
`executer_ordres.py` lit l'adresse de l'éleveur (`action_mail_eleveur.lire_mail_eleveur` : Bilan Eleveur → F5 FICHE ELV.
(clic souris ; pendant le chargement le titre n'a plus de crochets, ne pas recliquer) → « CONSULTATION D'UN ELEVEUR »
1/8 → SUIVANT → champ « e-mail » (pas « e-mail Facture ») → QUITTER sans confirmation), une fois par cheptel ; un échec
ne fait pas échouer l'ordre. Le résultat de l'ordre porte `mail_client`, `numero_facture`, `date_facture` ;
`compte_rendu.mail_client()` produit `"client": {mail, objet, corps}` dans `result/<nom>.json` (vide si pas de facture,
pas d'adresse, ou plusieurs éleveurs). Objet « SOGEN : … » (ni « G++ » ni « GENICIA++ : », pour qu'une réponse du
client transférée soit traitée). Testé 2 fois sur 64284002.

Fin d'exécution (16/11/2026) : `executer_ordres.py` ferme GENICIA++ par `quitter_application()` (Génicia > Quitter →
boîte « Confirmation » « Confirmez-vous la sortie de l'application ? » → OUI, clics souris), seulement si l'accueil est
affiché sans boîte ouverte. dbeng9 s'arrête ~5 s après ; javaw reste sans fenêtre tant que le Python qui tient le bridge
tourne, puis disparaît. Testé 2 fois de bout en bout (facture 64284002).

Garde-fous : incertitude / ordre invalide → rien n'est exécuté ; exécution dans un sous-processus avec délai max
(10 min + 5 min par ordre) ; après une erreur, on continue seulement si GENICIA++ est revenu à l'accueil sans boîte
ouverte ; fichier trouvé dans `processing/` au démarrage → `error/` (INTERROMPU), jamais relancé.

| État au 11/11/2026 | |
|---|---|
| Contrôle, rangement, réponses (7 cas : réussite, partiel, incertitude, invalide, JSON cassé, mail vide, interrompu) | Testé hors ligne avec une exécution simulée |
| `executer_ordres.py` dans le vrai GENICIA++ | **Pas encore testé** (à faire sur 64284002, avec l'accord de l'utilisateur) |
| Veilleur lancé en arrière-plan (fenêtre cachée) : mise au premier plan de GENICIA++ et clics souris | **Pas encore testé** : Windows peut refuser le premier plan à un processus d'arrière-plan |
| Agent Copilot G++ et 2 flux Power Automate | À créer par l'utilisateur (instructions + SKILL.md prêts) |

Pistes : retrouver le cheptel par le nom via la base (`lecture_bdd.py`, SELECT) ; facture sans date = la plus
récente ; joindre le PDF à la réponse ; liste d'expéditeurs autorisés pour « espace » ; journal Excel comme EGESYS.
