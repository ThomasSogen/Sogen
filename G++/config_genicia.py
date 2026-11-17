r"""Emplacements utilisés par la chaîne mail G++ (un seul endroit à modifier). Identiques sur tous les PC.

- DRIVE : dossier OneDrive G++, lu et écrit par Power Automate (pending, processing, completed, error, result).
  Trouvé automatiquement : <OneDrive Sogen>\G++, où <OneDrive Sogen> est donné par Windows (variable
  OneDriveCommercial, sinon OneDrive). La variable GENICIA_DRIVE, si elle existe, reste prioritaire (à éviter :
  elle est propre à un PC).
- FLUX : dossier technique LOCAL, propre à chaque PC, hors projet et hors OneDrive (%LOCALAPPDATA%\GENICIA) :
  journal du veilleur (veilleur.log), verrou, dossier de travail, copie des rapports. Il ne doit pas être dans
  OneDrive, sinon les deux PC mélangeraient leurs journaux et leurs fichiers de travail.
"""
import os
from pathlib import Path


def dossier_onedrive() -> Path:
    """Dossier OneDrive de l'entreprise sur ce PC, tel que Windows le donne."""
    for variable in ("OneDriveCommercial", "OneDrive"):
        valeur = os.environ.get(variable)
        if valeur and Path(valeur).is_dir():
            return Path(valeur)
    return Path.home() / "OneDrive - Sogen"


DRIVE = Path(os.environ.get("GENICIA_DRIVE") or dossier_onedrive() / "G++")
FLUX = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "GENICIA"
