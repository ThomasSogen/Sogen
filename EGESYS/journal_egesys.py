r"""Journal Excel des ordres EGESYS : une ligne par ordre exécuté (ou bloqué), ajoutée à chaque fin d'exécution.

Fichier : OneDrive EGESYS\journal_egesys.xlsx, voir config_egesys.py (colonnes Date, Action, Client, Modification, Raison, Résultat, Détail, Source).
Utilisé par script_egesys.py (ordres exécutés) et workflow/workflow.py (ordres bloqués avant exécution).
"""
import os
from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
import config_egesys

FICHIER_JOURNAL = str(config_egesys.FICHIER_JOURNAL)  # OneDrive EGESYS\journal_egesys.xlsx
COLONNES = [("Date", 17), ("Action", 34), ("Client", 18), ("Modification", 55), ("Raison", 60), ("Résultat", 14),
            ("Détail", 70), ("Source", 32)]
TITRES = [titre for titre, _ in COLONNES]
COULEURS_RESULTAT = {"Réussite": "D9EFDF", "Erreur": "F6D5D0", "Non exécuté": "FBEFCF"}


def _mettre_en_forme_entete(feuille):
    for numero, (titre, largeur) in enumerate(COLONNES, start=1):
        cellule = feuille.cell(row=1, column=numero, value=titre)
        cellule.font = Font(bold=True)
        feuille.column_dimensions[cellule.column_letter].width = largeur
    feuille.freeze_panes = "A2"

def _ouvrir():
    if os.path.isfile(FICHIER_JOURNAL):
        classeur = load_workbook(FICHIER_JOURNAL)
        feuille = classeur["Journal"]
        # Journal créé avant l'ajout d'une colonne : on insère les colonnes manquantes, les anciennes lignes restent vides
        for numero, titre in enumerate(TITRES, start=1):
            if feuille.cell(row=1, column=numero).value != titre:
                feuille.insert_cols(numero)
        _mettre_en_forme_entete(feuille)
        return classeur
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Journal"
    _mettre_en_forme_entete(feuille)
    return classeur


def client_de(ordre):
    return " / ".join(v for v in (ordre.get("nom_client", ""), ordre.get("code_client", "")) if v) or \
        (ordre.get("facture") or {}).get("numero_facture", "")


def ajouter_au_journal(ordre, resultat, detail="", source="", modification=""):
    """Ajoute une ligne au journal. Ne bloque jamais l'exécution : en cas de problème, affiche un avertissement.
    modification : valeurs modifiées, une par ligne (« ancienne » → « nouvelle »)."""
    try:
        os.makedirs(os.path.dirname(FICHIER_JOURNAL), exist_ok=True)
        classeur = _ouvrir()
        feuille = classeur["Journal"]
        valeurs = {"Date": datetime.now(), "Action": ordre.get("action", "—"), "Client": client_de(ordre),
                   "Modification": modification, "Raison": ordre.get("justification", ""), "Résultat": resultat,
                   "Détail": detail, "Source": source}
        feuille.append([valeurs[titre] for titre in TITRES])
        ligne = feuille.max_row
        colonne = {titre: numero for numero, titre in enumerate(TITRES, start=1)}
        feuille.cell(row=ligne, column=colonne["Date"]).number_format = "DD/MM/YYYY HH:MM"
        feuille.cell(row=ligne, column=colonne["Résultat"]).fill = PatternFill("solid", fgColor=COULEURS_RESULTAT.get(resultat, "FFFFFF"))
        for titre in ("Modification", "Raison", "Détail"):
            feuille.cell(row=ligne, column=colonne[titre]).alignment = Alignment(wrap_text=True, vertical="top")
        feuille.auto_filter.ref = f"A1:{feuille.cell(row=1, column=len(COLONNES)).column_letter}{ligne}"
        classeur.save(FICHIER_JOURNAL)
    except Exception as erreur:  # Fichier ouvert ailleurs, disque plein... : le journal ne doit pas arrêter EGESYS
        conseil = " : fermez le journal dans Excel" if isinstance(erreur, PermissionError) else ""
        print(f"⚠️  Journal Excel non mis à jour ({erreur}){conseil}.")
