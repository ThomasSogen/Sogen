r"""Nettoyage du OneDrive G++ : supprime les fichiers accumulés dans completed/, error/, result/ et result/pdf/.

Usage (PowerShell, dans le dossier G++ du projet) :
    python nettoyer_onedrive.py                 supprime TOUT de suite, sans question (puis affiche le bilan)
    python nettoyer_onedrive.py --simulation    liste seulement ce qui serait supprimé, sans rien supprimer
    python nettoyer_onedrive.py --jours 30      ne supprime que les fichiers de plus de 30 jours

Par défaut, tout est supprimé, y compris les fichiers qui viennent d'être créés : à lancer quand Power Automate a fini
d'envoyer les réponses (un result/<nom>.json ou un PDF de result/pdf/ supprimé avant l'envoi = pas de réponse au mail
ou réponse sans sa facture).

Ce qui n'est JAMAIS touché :
- pending/ (mails pas encore traités) et processing/ (exécution en cours) ;
- les sous-dossiers eux-mêmes (seuls les fichiers sont supprimés) et tout ce qui est hors du dossier G++ (ex : EGESYS).

Les fichiers supprimés partent dans la corbeille de OneDrive (en ligne), récupérables quelques semaines.
La copie locale des rapports (%LOCALAPPDATA%\GENICIA\rapports) n'est pas touchée.
"""
import argparse
import os
import sys
import time
from pathlib import Path

from config_genicia import DRIVE   # même dossier que veilleur/veilleur_genicia.py (trouvé automatiquement)

DOSSIERS_A_NETTOYER = ("completed", "error", "result", "result/pdf")
FICHIERS_SYSTEME = {"desktop.ini"}


def fichiers_a_supprimer(jours):
    """{dossier: [(chemin, taille)]} des fichiers à supprimer (sans descendre dans les sous-dossiers).
    jours = 0 : tous les fichiers, même ceux créés à l'instant."""
    maintenant = time.time()
    age_mini = jours * 86400
    selection, recents = {}, 0
    for nom in DOSSIERS_A_NETTOYER:
        dossier = DRIVE / nom
        selection[nom] = []
        if not dossier.is_dir():
            continue
        for fichier in sorted(dossier.iterdir()):
            if not fichier.is_file() or fichier.name.lower() in FICHIERS_SYSTEME:
                continue
            if maintenant - fichier.stat().st_mtime < age_mini:
                recents += 1
                continue
            selection[nom].append((fichier, fichier.stat().st_size))
    return selection, recents


def taille_lisible(octets):
    for unite in ("o", "Ko", "Mo", "Go"):
        if octets < 1024 or unite == "Go":
            return f"{octets:.0f} {unite}" if unite == "o" else f"{octets:.1f} {unite}"
        octets /= 1024


def main():
    parametres = argparse.ArgumentParser(description="Supprime les fichiers accumulés dans le OneDrive G++.")
    parametres.add_argument("--jours", type=int, default=0,
                            help="ne supprimer que les fichiers de plus de N jours (défaut : tous)")
    parametres.add_argument("--simulation", action="store_true", help="lister seulement, sans rien supprimer")
    parametres.add_argument("--oui", action="store_true", help=argparse.SUPPRESS)  # Ancienne option, sans effet
    options = parametres.parse_args()

    # Sécurité : on ne travaille que dans un dossier qui ressemble bien au OneDrive G++
    if not (DRIVE / "pending").is_dir() or not (DRIVE / "result").is_dir():
        sys.exit(f"🛑 {DRIVE} ne contient pas les dossiers pending/ et result/ : ce n'est pas le OneDrive G++, "
                 "rien n'est supprimé.")
    if any((DRIVE / "processing").glob("*.json")):
        print("⚠️  Un mail est en cours d'exécution (processing/ n'est pas vide) : il n'est pas touché.")

    selection, recents = fichiers_a_supprimer(options.jours)
    total = sum(len(fichiers) for fichiers in selection.values())
    poids = sum(taille for fichiers in selection.values() for _, taille in fichiers)
    print(f"📁 OneDrive G++ : {DRIVE}")
    for nom, fichiers in selection.items():
        print(f"   {nom + '/':<12} {len(fichiers):>5} fichier(s)  {taille_lisible(sum(t for _, t in fichiers)):>9}")
    if recents:
        print(f"   ({recents} fichier(s) de moins de {options.jours} jours conservé(s))")
    if not total:
        print("✅ Rien à supprimer.")
        return

    if options.simulation:
        print(f"\nSimulation : {total} fichier(s) ({taille_lisible(poids)}) seraient supprimés. Rien n'a été supprimé.")
        return

    # Pas de question : certains terminaux (ex : VS Code) n'affichent rien pendant qu'un programme attend une saisie
    supprimes, erreurs = 0, []
    for fichiers in selection.values():
        for fichier, _ in fichiers:
            try:
                fichier.unlink()
                supprimes += 1
            except OSError as erreur:  # Fichier ouvert ou en cours de synchronisation : il sera pris la prochaine fois
                erreurs.append(f"{fichier.name} ({erreur.strerror or erreur})")
    print(f"🗑️  {supprimes} fichier(s) supprimé(s) ({taille_lisible(poids)}).")
    for erreur in erreurs:
        print(f"⚠️  Non supprimé : {erreur}")


if __name__ == "__main__":
    # Windows : console pas en UTF-8 par défaut, les emojis feraient planter le script
    # line_buffering : chaque ligne s'affiche aussitôt, même si la sortie n'est pas une console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nAnnulé : rien n'a été supprimé.")
