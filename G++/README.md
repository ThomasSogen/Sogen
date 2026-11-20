# Automatisation GENICIA++

Des scripts Python qui utilisent le logiciel **GENICIA++** à la place d'un utilisateur.
Ils lancent le logiciel, se connectent, cliquent, remplissent les champs et récupèrent
les informations, sans intervention humaine.

Trois actions sont disponibles :

| Action | Ce qu'elle fait | Commande | Nom dans le JSON |
|---|---|---|---|
| **facture** | Enregistre en PDF le duplicata d'une facture d'un éleveur | `python main.py facture` | `telecharger_facture` |
| **factures** (par mail uniquement) | Enregistre en PDF le duplicata de **plusieurs** factures d'un éleveur : toutes celles de **plusieurs dates précises et/ou périodes** (« la facture du 31/01 et toutes celles de mars », « du 1er trimestre »… ; 30 au maximum), ou ses **N dernières factures** (« sa dernière facture », « ses 3 dernières factures » : les plus récentes du bilan, sur tout l'historique si aucune date n'est donnée ; s'il y en a moins, la réponse le dit). Dans « ANALYSE D'UN BILAN ELEVEUR », seules les lignes de type F dont la Transaction est un n° sont des factures (SOLDE, chèques, prélèvements sont ignorés) ; chaque facture est ouverte, son n° contrôlé, enregistrée, puis retour à l'analyse pour la suivante. **Une date sans facture n'arrête rien** : les autres factures sont envoyées et la réponse (comme le mail au client) indique les dates « Non trouvée », avec les factures les plus proches. Erreur technique en cours de route : aucun PDF n'est envoyé | — | `telecharger_factures` (`periodes` = « 31/01/2026 ; 01/03/2026 au 31/03/2026 » et/ou `nombre_dernieres` = « 3 ») |
| **espace** | Crée l'espace adhérent web d'un éleveur et lui envoie ses identifiants par mail | `python main.py espace 64233008` | `generer_espace_adherent` |

**Espace adhérent vérifié à chaque facture (par mail)** : après chaque récupération de facture(s), le programme ouvre
la fiche « COMMUNICATION AVEC L'ELEVEUR » de l'éleveur. « Droits : Oui » → rien n'est modifié. « Droits : Non » → l'espace
est créé comme l'action **espace** (profil ELWEB1 STANDARD, identifiants envoyés par GENICIA++ à l'adresse de la fiche) ;
l'utilisateur en est averti dans le compte rendu (encadré bleu) et le client dans le mail de ses factures. Une seule
vérification par éleveur et par mail ; pas de vérification si le mail contient déjà une demande d'espace pour cet éleveur.
Un échec de cette vérification ne fait pas échouer la facture (encadré orange « à vérifier »).

Elles se lancent **à la main** (section 2) ou **par mail**, sans intervention (section 3) :

```
Mail reçu dans Outlook
   │  Flux Power Automate n°1 : envoie le mail (+ « ID du message » et « Expéditeur ») à l'agent Copilot GENICIA++
   ▼
Agent Copilot : traduit le mail en JSON {resume, id_message, expediteur, ordres, incertitudes}
   │  Power Automate dépose le JSON dans OneDrive\G++\pending\
   ▼
Veilleur (sur ce PC) : contrôle le JSON → exécute dans GENICIA++ → range dans completed\ ou error\
   │
   ▼
OneDrive\G++\result\<nom>.json : {id_message, expediteur, objet, corps HTML, pdf}  (+ PDF dans result\pdf\)
   │  Flux Power Automate n°2 : répond au mail d'origine
   ▼
Réponse dans Outlook : ce qui a été fait, ce qui ne l'a pas été et pourquoi, que faire
```

---

## 1. Installation (une seule fois)

### Ce qu'il faut sur le poste
- Windows, avec GENICIA++ installé dans `C:\Logicia\Genicia\GPP`
- Python 3.12 **64 bits**
- Les bibliothèques Python :
  ```
  python -m pip install pywinauto pyjab keyring pyodbc pypdf
  ```

### Activer Java Access Bridge
GENICIA++ est une application Java. Pour que Python puisse « voir » ses boutons et ses champs,
il faut activer Java Access Bridge :
```
"C:\Program Files\Java\jre1.8.0_25\bin\jabswitch.exe" -enable
```
Ensuite, **fermez et rouvrez GENICIA++**.

### Enregistrer vos identifiants GENICIA++
```
python enregistrer_identifiants.py
```
Le script demande votre n° d'opérateur, puis votre mot de passe (il ne s'affiche pas pendant
la saisie, c'est normal). Les identifiants sont rangés dans le **Gestionnaire d'identifiants
Windows**. Ils ne sont écrits dans aucun fichier.
Relancez ce script si votre mot de passe change.

---

## 2. Utilisation

Ouvrez un terminal dans `C:\Logicia\Genicia`, puis lancez une action.
Il n'est pas nécessaire d'ouvrir GENICIA++ avant : le script le lance et se connecte tout seul.
S'il est déjà ouvert, le script repart de l'écran d'accueil.

> ⚠ **Pendant une action, ne touchez ni au clavier ni à la souris.**
> Certaines étapes demandent de vrais clics de souris sur la fenêtre de GENICIA++.

### Action « facture » : télécharger le duplicata d'une facture
```
python main.py facture                                     (exemple : cheptel 64233008, facture du 31/03/2019)
python main.py facture 64233008 31/03/2019
python main.py facture 64233008 31/01/2019 --debut 01/01/2019
```
- `64233008` : n° de cheptel de l'éleveur
- `28/02/2026` : date de la facture
- `--debut` : début de la période du bilan dans laquelle chercher la facture (par défaut 01/01/2026)

Le PDF est enregistré dans le dossier **`factures`**, sous la forme
`<cheptel>_<n° facture>_<date>.pdf`, par exemple `64233008_0020000066643_2019-03-31.pdf`.
Si le fichier existe déjà, il est remplacé.

Parcours suivi dans le logiciel : Administratif → Bilan Eleveur → N° Cheptel → Rechercher →
Début → VALIDER → ++ → sélection de la facture → F5 DETAILLER → F5 DUPLICATA → Aperçu →
Fichier → Enregistrer en PDF. À la fin, le script annule l'impression : rien n'est imprimé.

### Action « espace » : générer l'espace adhérent web
```
python main.py espace 64233008
python main.py espace 64233008 --profil "ELWEB1 STANDARD"
```

> ⚠ Cette action **modifie la fiche de l'éleveur** (droits web, nouveau mot de passe, abonnements)
> et **envoie un mail** avec ses identifiants à l'adresse de sa fiche.
> Ne la lancez que sur un éleveur pour lequel c'est voulu.

Parcours suivi : Administratif → Eleveur → F14 COMMUNIC. → N° Cheptel → Rechercher →
Droits = Oui → Profil → clé (nouveau mot de passe) → ENREGISTRER DROITS → « envoyer un mail ? » OUI →
VALIDER (envoi du mail) → FACTURES SANS PJ (abonnements mail).
Si l'éleveur a déjà l'abonnement « factures sans pièce jointe », la dernière étape est sautée.
Le nouveau mot de passe n'est jamais affiché par le script.

---

## 3. Automatisation par mail

### Ce que fait le veilleur

`lancer_veilleur.bat` lance en arrière-plan [veilleur/veilleur_genicia.py](veilleur/veilleur_genicia.py). Toutes les
5 secondes, il regarde le dossier OneDrive `<OneDrive Sogen>\G++`, trouvé automatiquement sur chaque PC
([config_genicia.py](config_genicia.py)). **Un seul PC à la fois** : le fichier `G++\_poste_actif.json` du OneDrive indique
quel PC fait tourner le veilleur ; un autre PC refuse de démarrer tant que le premier donne signe de vie (5 min) :

| Dossier | Contenu |
|---|---|
| `pending/` | Power Automate y dépose le JSON de l'agent |
| `processing/` | Le JSON pendant son exécution dans GENICIA++ |
| `completed/` | Toutes les demandes ont réussi |
| `error/` | Demande refusée (incertitude, information manquante) ou erreur pendant l'exécution |
| `result/` | `<nom>.json` : **la réponse au mail d'origine**, écrite en tout dernier |

Pour chaque `pending/<nom>.json` :
1. **contrôle** sans GENICIA++ ([ordres_genicia.py](ordres_genicia.py)) : clés exactes, n° de cheptel (8 caractères),
   date valide et pas dans le futur, profil autorisé, incertitudes de l'agent. Au moindre problème, **rien n'est exécuté** ;
2. **exécution** ([executer_ordres.py](executer_ordres.py)) : lancement et connexion à GENICIA++ si besoin, puis chaque
   demande l'une après l'autre. Après une erreur, on ne continue que si GENICIA++ est revenu proprement à l'accueil.
   À la fin, **GENICIA++ est fermé** (Génicia > Quitter > OUI ; la base s'arrête avec lui). S'il n'est pas revenu
   à l'accueil ou si une boîte est ouverte, il reste ouvert pour qu'on puisse voir le problème ;
3. **rangement** dans `completed/` ou `error/` : `<nom>.json`, `<nom>_valide.json`, `<nom>_rapport.txt` (rapport détaillé),
   `<nom>_resultat.json`, et le PDF des factures (`<nom>_<cheptel>_<n° facture>_<date>.pdf`) ;
4. **réponse** dans `result/<nom>.json` ([veilleur/compte_rendu.py](veilleur/compte_rendu.py)) :
   `{"id_message", "expediteur", "objet", "corps", "pdf"}`. Le corps est en HTML, prêt à être inséré dans la réponse Outlook.
   `pdf` = liste des **noms** des factures à joindre, déposées dans `result\pdf\` (ex : `<nom>_64233008_0020000066643_2019-03-31.pdf`),
   liste vide s'il n'y en a pas. Les PDF sont copiés dans `result\pdf\` **avant** l'écriture du JSON ; l'original reste
   dans `completed\` ou `error\`. Le flux n°2 lit chaque fichier `/G++/result/pdf/<nom du PDF>` (« Obtenir le contenu du fichier à l'aide du chemin »)
   et l'ajoute en pièce jointe, puis le supprime de `result\pdf\` (nettoyage fait par le flux).
5. **mail au client** : quand des factures ont été récupérées, le JSON contient aussi
   `"client": {"mail", "objet", "corps"}`. Le flux n°2 envoie alors un second mail **à l'éleveur**, avec les mêmes PDF
   (liste `pdf`) en pièces jointes. L'adresse est lue sur la fiche de l'éleveur dans GENICIA++, jamais dans le mail :
   Bilan Eleveur → F5 FICHE ELV. → SUIVANT → « e-mail » ([action_mail_eleveur.py](action_mail_eleveur.py)).
   `client.mail` est **vide** (rien à envoyer au client) si aucune facture n'a été récupérée, si la fiche n'a pas
   d'adresse, ou si le mail concerne plusieurs éleveurs. L'objet commence par « SOGEN : » et le message est signé
   « Le service administratif de SOGEN » (modifiable dans `veilleur/compte_rendu.py`, `mail_client`).
   Pour une demande à plusieurs dates, le message rappelle les dates demandées et indique celles sans facture
   (« Nous n'avons trouvé aucune facture le 15/08/2026. ») ; si l'espace adhérent vient d'être créé, il l'annonce
   (identifiants envoyés dans un mail séparé).

   Dans le flux n°2, après la réponse à l'utilisateur et **avant** de supprimer les PDF de `result\pdf\` :
   condition « `client.mail` n'est pas vide » → « Envoyer un e-mail (V2) » : À = `client.mail`,
   Objet = `client.objet`, Corps = `client.corps`, pièces jointes = les mêmes PDF que la réponse.

| Résultat | Code | Dossier | Objet de la réponse |
|---|---|---|---|
| Tout a réussi | `EXECUTE` | `completed/` | GENICIA++ : Demande traitée |
| Factures envoyées, mais certaines dates demandées sans facture | `EXECUTE` | `completed/` | … Demande traitée, factures manquantes (lignes « Non trouvée » avec la raison et les factures les plus proches) |
| Aucune facture à aucune des dates demandées | `ERREUR_EXECUTION` | `error/` | … Facture à préciser (détail date par date) |
| Une partie ou tout a échoué | `ERREUR_EXECUTION` | `error/` | … partiellement traitée / Erreur lors du traitement |
| Incertitude ou information manquante | `REFUSE_VALIDATION` | `error/` | … Précisions nécessaires / Demande non traitée |
| PC ou veilleur arrêté pendant l'exécution | `INTERROMPU` | `error/` | … Traitement interrompu, à vérifier dans GENICIA++ (jamais relancé) |

**File d'attente GENICIA++** ([file_attente_genicia.py](file_attente_genicia.py)) : un seul programme pilote GENICIA++
à la fois sur un PC (veilleur, `main.py`, `executer_ordres.py`). Si GENICIA++ est déjà utilisé par un autre programme,
le nouveau **attend son tour**, dans l'ordre d'arrivée (ligne « ⏳ GENICIA++ occupé… » chaque minute, notification
« demande en attente » pour un mail). Le temps d'attente ne compte pas dans le délai maximal du veilleur. Au-delà
d'une heure d'attente, la demande est abandonnée sans rien faire (réponse en erreur, à relancer). Un programme arrêté
ou planté libère sa place tout seul.

**Jamais d'attente sans fin** (blocages corrigés les 17 et 19/11/2026) :
- le programme traite en continu les messages que Java lui envoie (sinon GENICIA++ se figeait : menu ou champ
  « introuvable ») et ne parcourt plus les menus déroulants restés ouverts quand il cherche un champ ou un bouton ;
- au lancement, il attend que le GENICIA++ précédent soit vraiment fermé ; si aucune fenêtre de connexion n'apparaît en
  90 s, l'instance bloquée (sans fenêtre) est arrêtée et GENICIA++ relancé une fois ; la connexion est vérifiée
  (identifiant bien saisi, fenêtre principale ouverte dans les 2 min) ;
- un clic ignoré sur un menu (« Génicia », « Fichier » de l'aperçu…) est refait ; une navigation dans les menus est
  retentée une fois depuis l'accueil ;
- le veilleur arrête une exécution qui n'affiche plus rien pendant **1 min** (GENICIA++ figé) et répond en erreur.
  Le rapport (`<nom>_rapport.txt`) contient le **journal détaillé** : chaque élément recherché, clic, saisie (mot de
  passe masqué), valeur lue, écran attendu, avec l'heure ; la dernière ligne montre où GENICIA++ s'est bloqué.
  Les clics se font au rythme d'un utilisateur : au moins 1 s entre deux clics, attente de la fin du chargement
  d'un nouvel écran ; les menus sont cliqués à la souris ; un clic non pris en compte (étape suivante absente après
  4 s) est refait sur le même bouton.
- **Blocage de GENICIA++** (il attend, et un clic n'importe où le débloque) : après 15 s sans aucune action, un
  surveillant clique dans la barre de titre de la fenêtre (zone sans bouton), jusqu'à 3 fois, puis le programme
  reprend son chemin (« clic de déblocage » dans le rapport).
- **Adresse mail de l'éleveur** : lue sur l'écran « BILAN ELEVEUR » (« Coordonnées : … Email : … »), déjà ouvert
  pour les factures ; la fiche de l'éleveur n'est plus ouverte que si cette zone est illisible.
- **Éleveur désigné par son nom** (sans n° de cheptel) : le programme cherche le nom sur « Recherche éleveur »
  (sans « EARL », « GAEC », « M. »…). Un seul éleveur → son cheptel est utilisé pour toute la suite ; plusieurs ou
  aucun → rien n'est fait et la réponse le dit (avec les éleveurs possibles).

> ⚠ **Le PC doit être allumé, la session Windows ouverte et déverrouillée**, OneDrive synchronisé et le veilleur lancé.
> GENICIA++ est piloté par de vrais clics de souris : pendant un traitement (notification « traitement en cours »),
> ne touchez ni au clavier ni à la souris. Un seul mail est traité à la fois.

### Commandes (PowerShell, dans le dossier `G++` du projet)

| Pour… | Commande |
|---|---|
| Enregistrer les identifiants GENICIA++ (une fois) | `.\lancer_veilleur.bat -Identifiants` |
| Lancer en arrière-plan | `.\lancer_veilleur.bat` ou double-clic |
| Lancer à chaque ouverture de session | `.\lancer_veilleur.bat -Installer` (retirer : `-Desinstaller`) |
| Savoir s'il tourne, et sur quel PC (+ fin du journal) | `.\lancer_veilleur.bat -Etat` |
| Suivre le journal en direct (journal propre à chaque PC) | `Get-Content $env:LOCALAPPDATA\GENICIA\veilleur.log -Wait -Tail 20 -Encoding UTF8` |
| Arrêter (refusé si un traitement est en cours) | `.\lancer_veilleur.bat -Arreter` |
| Lancer au premier plan pour voir ce qu'il fait | `python veilleur\veilleur_genicia.py` (Ctrl+C pour arrêter) |
| Contrôler un JSON à la main | `python ordres_genicia.py fichier.json` |
| Exécuter à la main un JSON contrôlé | `python executer_ordres.py fichier_valide.json` |
| Vider le OneDrive G++ (`completed`, `error`, `result`, `result\pdf`) | `python nettoyer_onedrive.py` (supprime tout, sans question ; à lancer quand les réponses sont parties) |
| … seulement les fichiers de plus de 30 jours | `python nettoyer_onedrive.py --jours 30` (`--simulation` : liste sans supprimer) |

Ce veilleur est indépendant de celui d'EGESYS (autres dossiers OneDrive, autre nom de programme, autre verrou).

### Les flux Power Automate

- **Flux n°1** (mail → agent → `G++\pending`) : déclenché uniquement par les mails dont l'**objet contient « G++ »**
  (filtre d'objet). Le flux EGESYS filtre sur « EGESYS » : un même mail ne doit pas contenir les deux.
- **Flux n°2** (`G++\result` → réponse) : mettre `objet` dans le champ **Objet** de la réponse et `corps` dans le corps.
  L'objet de nos réponses commence par « GENICIA++ : » et **ne contient pas « G++ »** : si la réponse revient dans la
  boîte surveillée, elle ne relance pas le flux n°1 (sinon une demande « espace » pourrait être rejouée en boucle).
  En dernier recours, l'agent ignore aussi tout compte rendu automatique (mail de test n°10).

### L'agent Copilot

- **Instructions** : [copilot/instructions.md](copilot/instructions.md), à coller dans l'agent (≈ 6 100 caractères, limite ≈ 8 000).
- **Compétence** : [copilot/genicia-modeles-json/SKILL.md](copilot/genicia-modeles-json/SKILL.md), à charger comme fichier.
  Elle est **générée** par `python generer_doc_copilot.py` à partir de `ordres_genicia.py` et de
  [copilot/exemples.md](copilot/exemples.md) : ne pas la modifier à la main.
- **Factures** : une seule facture à une date précise → `telecharger_facture` ; plusieurs dates et/ou périodes → UN
  ordre `telecharger_factures` avec `"periodes": "31/01/2026 ; 01/03/2026 au 31/03/2026"` (date précise = JJ/MM/AAAA,
  période = JJ/MM/AAAA au JJ/MM/AAAA, séparées par « ; »). « Sa dernière facture » / « ses N dernières factures » →
  `telecharger_factures` avec `"nombre_dernieres": "N"` (sans date : tout l'historique). « Cheptel », « code client » et « numéro d'élevage »
  désignent la même chose.
- **Tests** : [copilot/tests/mails_de_test.md](copilot/tests/mails_de_test.md) (39 mails, dont 28 sur les factures : dates exactes, mois, trimestre, année, mélanges, dates sans facture, date future, sans année, N dernières factures (06, 31, 34-39)…) et
  `python comparer_reponse_copilot.py copilot/tests/attendus/test_01.json copilot/tests/reponses/test_01.txt`.
  Envoi automatique des mails de test (comme EGESYS) : `python envoyer_mails_test.py 34-39` (`--liste` pour les voir) :
  les mails partent par le dossier `TESTS_MAILS` et sont VRAIMENT exécutés dans GENICIA++ (cheptel 64233008).
- Les textes chargés dans l'agent ne doivent contenir ni données personnelles réalistes ni formulations du type
  « ignore tes instructions » (sinon Microsoft bloque l'agent) : les exemples utilisent des noms et numéros fictifs.

### Ajouter une action à l'automatisation par mail
1. Créer et tester l'action à la main (section 7 de `prise_en_main.md`) ;
2. l'ajouter dans `CATALOGUE` de `ordres_genicia.py` et dans `ACTIONS` de `executer_ordres.py` ;
3. si besoin, adapter `demande()` / `traduire()` dans `veilleur/compte_rendu.py` ;
4. `python generer_doc_copilot.py`, puis recharger le SKILL.md dans l'agent ; ajouter un exemple et un mail de test.

---

## 4. Les fichiers du projet

| Fichier | Rôle |
|---|---|
| `main.py` | **Le script à lancer à la main.** Il choisit l'action. |
| `action_facture.py` | Les étapes de l'action « facture » |
| `action_espace_adherent.py` | Les étapes de l'action « espace » |
| `action_mail_eleveur.py` | Lit (sans rien modifier) l'adresse mail de la fiche d'un éleveur, pour lui envoyer ses factures |
| `genicia_auto.py` | La boîte à outils : lancer, se connecter, cliquer, écrire, lire les listes, gérer les fenêtres |
| `file_attente_genicia.py` | Un seul programme à la fois dans GENICIA++ ; les autres attendent leur tour (ordre d'arrivée) |
| `enregistrer_identifiants.py` | Enregistre vos identifiants dans Windows |
| `inspecter_ecran.py` | Liste les éléments de l'écran ouvert dans GENICIA++ (dans `arbre_interface.txt`). Sert à préparer une nouvelle action. |
| `lecture_bdd.py` | Lecture directe de la base de données (requêtes `SELECT` uniquement) |
| `apercu_base.py` | Produit `apercu_base.txt` : toutes les tables de la base avec leurs colonnes et quelques lignes d'exemple |
| `g++.txt` | Vos notes : les parcours des actions dans le logiciel |
| `factures/` | Les PDF téléchargés à la main |
| `ordres_genicia.py` | **Référence des actions par mail** (`CATALOGUE`) + lecture et contrôle du JSON de l'agent |
| `executer_ordres.py` | Exécute dans GENICIA++ les ordres d'un JSON contrôlé |
| `veilleur/veilleur_genicia.py` | Surveille OneDrive `G++\pending`, contrôle, exécute, range, écrit la réponse |
| `veilleur/compte_rendu.py` | Rédige la réponse au mail (objet + corps HTML) |
| `lancer_veilleur.bat`, `lancer_veilleur.ps1` | Identifiants, lancement en arrière-plan, démarrage automatique, état, arrêt |
| `generer_doc_copilot.py` | Génère la compétence de l'agent (`copilot/genicia-modeles-json/SKILL.md`) |
| `comparer_reponse_copilot.py` | Compare une réponse de l'agent à la réponse attendue d'un mail de test |
| `envoyer_mails_test.py` | Mails de test : génère `copilot/tests/mails_json/test_XX.json` depuis `mails_de_test.md` et les dépose dans `OneDrive - Sogen\TESTS_MAILS`, d'où le flux Power Automate les envoie (objet `[G++] [TEST XX] …`). `--liste`, `34-39`, `--tous`, `--generer` |
| `nettoyer_onedrive.py` | Supprime les fichiers accumulés dans le OneDrive G++ (jamais `pending/`, `processing/` ; tout le reste est supprimé, même les fichiers récents) |
| `copilot/` | Instructions, compétence, exemples et mails de test de l'agent |
| `config_genicia.py` | Emplacements : dossier OneDrive G++ (trouvé automatiquement), dossier local `%LOCALAPPDATA%\GENICIA` |
| `veilleur/poste_actif.py` | Un seul PC à la fois (fichier `_poste_actif.json` dans le OneDrive G++). Identique à celui d'EGESYS |
| `%LOCALAPPDATA%\GENICIA\` | Hors projet, propre à chaque PC, créé à l'exécution : `veilleur.log`, `veilleur.lock`, `rapports/`, `travail/`. L'ancien dossier `GENICIA_flux/` du projet ne sert plus (peut être supprimé) |

---

## 5. Lecture directe de la base (optionnel)

GENICIA++ s'appuie sur une base **Sybase SQL Anywhere 9** locale
(`C:\Logicia\Genicia\GPP\bdd\bddg++.db`), accessible par la source ODBC `bddg++`.
```
python lecture_bdd.py tables --compte-dsn                         liste des tables
python lecture_bdd.py colonnes FEMELLE --compte-dsn               colonnes d'une table
python lecture_bdd.py apercu FEMELLE --lignes 20 --compte-dsn     premières lignes
python lecture_bdd.py sql "SELECT TOP 10 * FROM FEMELLE" --compte-dsn --csv sortie.csv
```
Le script refuse toute requête autre qu'un `SELECT` : rien n'est jamais modifié.
`--compte-dsn` utilise le compte enregistré dans la source ODBC. Sans cette option, le script lit
`GENICIA_DB_UID` / `GENICIA_DB_PWD` (à utiliser avec un compte en lecture seule fourni par l'IT).

---

## 6. En cas de problème

| Symptôme | Cause probable / solution |
|---|---|
| `Identifiants absents` | Lancer `python enregistrer_identifiants.py` |
| `... is not Java Window` | Java Access Bridge n'est pas actif : lancer `jabswitch -enable`, puis redémarrer GENICIA++ |
| Le script s'arrête avec « Boîte de dialogue ouverte, arrêt par sécurité » | Une fenêtre inattendue est apparue. Le script s'arrête au lieu de cliquer au hasard. Fermez-la à la main, puis relancez. |
| `Impossible de mettre la fenêtre au premier plan` | Une autre fenêtre a pris le dessus (souris ou clavier touchés pendant l'action ?). Relancez. |
| `Aucune facture au ...` | Aucune facture à cette date dans la période. Vérifiez la date ou élargissez `--debut`. |
| Le script reste bloqué | Fermez les fenêtres ouvertes dans GENICIA++, revenez à l'accueil, puis relancez. |
| Les mails ne sont plus traités | `.\lancer_veilleur.bat -Etat` : le veilleur tourne-t-il, et sur quel PC ? OneDrive est-il synchronisé ? La session est-elle verrouillée ? |
| « Le veilleur GENICIA++ tourne déjà sur le PC … » | Il tourne sur l'autre PC : l'arrêter là-bas (`-Arreter`), ou attendre 5 min si l'autre PC est éteint, puis relancer |
| Réponse « Délai d'exécution dépassé » ou « Aucune activité depuis 60 s » | GENICIA++ ne répondait plus : le programme a été arrêté. Vérifiez l'écran de GENICIA++, fermez les boîtes ouvertes et revenez à l'accueil. |
| « GENICIA++ ne s'ouvre pas : aucune fenêtre de connexion » | Un GENICIA++ reste bloqué sans fenêtre : Gestionnaire des tâches (Ctrl+Maj+Échap) → Détails → `javaw.exe` → Fin de tâche, puis renvoyer le mail. |
| Réponse « Demande traitée, factures manquantes » | Normal : certaines dates demandées n'ont pas de facture (voir « Non trouvée » et les factures les plus proches). Renvoyer la demande avec les bonnes dates si besoin. |
| Un fichier reste dans `processing/` | Le veilleur est en train de l'exécuter. S'il est arrêté, il le passera dans `error/` (code `INTERROMPU`) au prochain démarrage, sans le relancer. |

---

## 7. Règles d'usage

- Faites les **premiers essais d'une nouvelle action sur un client de test** (**uniquement le cheptel 64233008** pour tous les tests, depuis le 19/11/2026 ; l'adresse mail de sa fiche est celle de l'utilisateur).
- La base est celle de **production** : les actions qui modifient des données doivent être voulues.
- Vérifiez auprès de l'IT que l'automatisation du logiciel est autorisée.
