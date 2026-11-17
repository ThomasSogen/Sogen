# Automatisation GENICIA++

Des scripts Python qui utilisent le logiciel **GENICIA++** à la place d'un utilisateur.
Ils lancent le logiciel, se connectent, cliquent, remplissent les champs et récupèrent
les informations, sans intervention humaine.

Deux actions sont disponibles :

| Action | Ce qu'elle fait | Commande | Nom dans le JSON |
|---|---|---|---|
| **facture** | Enregistre en PDF le duplicata d'une facture d'un éleveur | `python main.py facture` | `telecharger_facture` |
| **espace** | Crée l'espace adhérent web d'un éleveur et lui envoie ses identifiants par mail | `python main.py espace 64284002` | `generer_espace_adherent` |

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
python main.py facture                                     (exemple : cheptel 64284002, facture du 28/02/2026)
python main.py facture 64284002 28/02/2026
python main.py facture 64284002 31/03/2026 --debut 01/01/2026
```
- `64284002` : n° de cheptel de l'éleveur
- `28/02/2026` : date de la facture
- `--debut` : début de la période du bilan dans laquelle chercher la facture (par défaut 01/01/2026)

Le PDF est enregistré dans le dossier **`factures`**, sous la forme
`<cheptel>_<n° facture>_<date>.pdf`, par exemple `64284002_4500000088031_2026-02-28.pdf`.
Si le fichier existe déjà, il est remplacé.

Parcours suivi dans le logiciel : Administratif → Bilan Eleveur → N° Cheptel → Rechercher →
Début → VALIDER → ++ → sélection de la facture → F5 DETAILLER → F5 DUPLICATA → Aperçu →
Fichier → Enregistrer en PDF. À la fin, le script annule l'impression : rien n'est imprimé.

### Action « espace » : générer l'espace adhérent web
```
python main.py espace 64284002
python main.py espace 64284002 --profil "ELWEB1 STANDARD"
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
   `pdf` = liste des **noms** des factures à joindre, déposées dans `result\pdf\` (ex : `<nom>_64284002_4500000088031_2026-02-28.pdf`),
   liste vide s'il n'y en a pas. Les PDF sont copiés dans `result\pdf\` **avant** l'écriture du JSON ; l'original reste
   dans `completed\` ou `error\`. Le flux n°2 lit chaque fichier `/G++/result/pdf/<nom du PDF>` (« Obtenir le contenu du fichier à l'aide du chemin »)
   et l'ajoute en pièce jointe, puis le supprime de `result\pdf\` (nettoyage fait par le flux).

| Résultat | Code | Dossier | Objet de la réponse |
|---|---|---|---|
| Tout a réussi | `EXECUTE` | `completed/` | GENICIA++ : Demande traitée |
| Une partie ou tout a échoué | `ERREUR_EXECUTION` | `error/` | … partiellement traitée / Erreur lors du traitement |
| Incertitude ou information manquante | `REFUSE_VALIDATION` | `error/` | … Précisions nécessaires / Demande non traitée |
| PC ou veilleur arrêté pendant l'exécution | `INTERROMPU` | `error/` | … Traitement interrompu, à vérifier dans GENICIA++ (jamais relancé) |

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
- **Tests** : [copilot/tests/mails_de_test.md](copilot/tests/mails_de_test.md) (10 mails) et
  `python comparer_reponse_copilot.py copilot/tests/attendus/test_01.json copilot/tests/reponses/test_01.txt`.
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
| `genicia_auto.py` | La boîte à outils : lancer, se connecter, cliquer, écrire, lire les listes, gérer les fenêtres |
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
| Réponse « Délai d'exécution dépassé » | GENICIA++ ne répondait plus : le programme a été arrêté. Vérifiez l'écran de GENICIA++, fermez les boîtes ouvertes et revenez à l'accueil. |
| Un fichier reste dans `processing/` | Le veilleur est en train de l'exécuter. S'il est arrêté, il le passera dans `error/` (code `INTERROMPU`) au prochain démarrage, sans le relancer. |

---

## 7. Règles d'usage

- Faites les **premiers essais d'une nouvelle action sur un client de test** (par exemple le cheptel 64284002, prévu pour ça).
- La base est celle de **production** : les actions qui modifient des données doivent être voulues.
- Vérifiez auprès de l'IT que l'automatisation du logiciel est autorisée.
