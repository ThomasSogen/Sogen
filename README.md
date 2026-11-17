# Projet SOGEN : EGESYS + G++

Deux automatisations par mail, chacune dans son dossier :

- [EGESYS/](EGESYS/README.md) : met à jour la base clients EGESYS ;
- [G++/](G++/README.md) : pilote le logiciel GENICIA++.

## Travailler sur deux PC

**Le code est synchronisé par OneDrive.** Ce dossier `SOGEN` est dans OneDrive : une modification faite sur un PC
arrive sur l'autre en quelques secondes. Il n'y a rien à copier, ni à « commit / push » pour passer d'un PC à l'autre.

Le code ne contient aucun réglage propre à un PC. Chaque PC trouve tout seul son dossier OneDrive et range ses journaux
dans `%LOCALAPPDATA%` (hors du projet).

### Sur un nouveau PC, une seule fois

Double-cliquez sur **`installer_poste.bat`**. Le script vérifie ce qui ne se synchronise pas, et propose de corriger
chaque point :

- Python et ses bibliothèques ;
- identifiants EGESYS et GENICIA++ ;
- Java Access Bridge ;
- Git ;
- démarrage automatique.

En cas de doute plus tard : `installer_poste.bat -Verifier` (vérifie sans rien modifier).

### Un seul PC traite les mails à la fois

Le workflow EGESYS et le veilleur G++ s'inscrivent dans OneDrive (`_poste_actif.json`). Si l'un tourne déjà sur l'autre
PC, il refuse de démarrer, avec un message qui dit quel PC est actif.

Pour basculer :

1. sur l'ancien PC : `lancer_workflow.bat -Arreter` (EGESYS) et `lancer_veilleur.bat -Arreter` (G++) ;
2. sur le nouveau PC : `lancer_workflow.bat` et `lancer_veilleur.bat` (ou double-clic).

Si l'ancien PC est éteint ou en veille, le nouveau peut démarrer 5 minutes après son dernier signe de vie. Quand
l'ancien PC se réveille, il voit que l'autre a pris le relais et s'arrête tout seul.

Pour savoir quel PC est actif : `-Etat` sur l'un des deux lanceurs.

### Historique sur GitHub

Double-cliquez sur **`sauvegarder.bat`** après une modification qui fonctionne. Le script enregistre et envoie tout sur
GitHub, en une fois.

Ça sert à revenir en arrière en cas de problème, pas à passer d'un PC à l'autre. Au premier lancement, il demande
l'adresse du dépôt GitHub.

Ne partent **jamais** sur GitHub (voir [.gitignore](.gitignore)) :

- les fichiers contenant de vraies données clients (`G++/apercu_base.txt`, `EGESYS/cartes/`, PDF, CSV, Excel) ;
- les journaux.

Les identifiants ne sont dans aucun fichier du projet.
