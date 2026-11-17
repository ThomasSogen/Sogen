r"""Emplacements utilisés par le projet (un seul endroit à modifier).

- DRIVE : dossier OneDrive EGESYS, lu et écrit par Power Automate (pending, processing, completed, error, result)
  et qui contient aussi le journal Excel. Trouvé automatiquement sur chaque PC : <OneDrive Sogen>\EGESYS, où
  <OneDrive Sogen> est donné par Windows (variable OneDriveCommercial, sinon OneDrive). La variable EGESYS_DRIVE,
  si elle existe, reste prioritaire (à éviter : elle est propre à un PC).
- DOSSIER_LOCAL : dossier technique de Windows, hors projet et hors OneDrive (%LOCALAPPDATA%\EGESYS) :
  verrous (une seule connexion EGESYS, un seul workflow), journal du workflow (workflow.log), dossier de travail.
- ECRITURE_EN_COURS : dossier caché du OneDrive où les résultats sont d'abord écrits, puis déplacés d'un coup dans
  result/ (même disque = déplacement instantané) : Power Automate ne voit jamais un fichier à moitié écrit.
"""
import os
from pathlib import Path

def dossier_onedrive() -> Path:
    """Dossier OneDrive de l'entreprise sur ce PC, tel que Windows le donne (identique d'un PC à l'autre côté code)."""
    for variable in ('OneDriveCommercial', 'OneDrive'):
        valeur = os.environ.get(variable)
        if valeur and Path(valeur).is_dir():
            return Path(valeur)
    return Path.home() / "OneDrive - Sogen"


DRIVE = Path(os.environ.get('EGESYS_DRIVE') or dossier_onedrive() / "EGESYS")
FICHIER_JOURNAL = Path(os.environ.get('EGESYS_JOURNAL') or DRIVE / "journal_egesys.xlsx")
DOSSIER_LOCAL = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / "EGESYS"
ECRITURE_EN_COURS = DRIVE / "_ecriture_en_cours"
