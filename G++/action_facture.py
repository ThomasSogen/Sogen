"""Action : télécharger le duplicata PDF d'une facture d'un éleveur.

Étapes relevées dans GENICIA++ (10/11/2026) :
  1. Menu Administratif > Bilan Eleveur                      -> écran « Recherche éleveur »
  2. N° Cheptel : <cheptel>, bouton « Rechercher (F3) »
     - un seul éleveur trouvé : GENICIA++ passe seul à l'écran « BILAN ELEVEUR »
     - sinon : sélectionner la ligne du cheptel puis « VALIDER (F12) »
  3. Écran « BILAN ELEVEUR » : Début : <date début>, « VALIDER (F12) »
                                                             -> « ANALYSE D'UN BILAN ELEVEUR »
  4. Début : <date début>, bouton « ++ » (recharge la liste des opérations)
  5. Sélectionner la ligne Date = <date facture> et Type = F (facture)
  6. « F5 DETAILLER »                                        -> « DETAIL D'UNE FACTURE »
  7. « F5 DUPLICATA » (clic souris)                          -> boîte « Impression »
  8. « Aperçu » (clic souris)                                -> boîte « Aperçu avant impression »
  9. Menu Fichier > Enregistrer en PDF... (clics souris)     -> boîte « Enregistrement du rapport en PDF ... »
 10. Nom du fichier : <chemin complet du PDF>, « Confirmer » (clic souris)
 11. Fermeture : Aperçu > Fichier > Fermer, Impression > Annuler (rien n'est imprimé),
     puis QUITTER (ESC) jusqu'à l'accueil.

Les étapes 7 à 10 utilisent de vrais clics souris : ne pas toucher la souris pendant ce temps.
"""
import os
import time
from datetime import datetime

import genicia_auto as g

# Colonnes des listes (étiquettes de chaque ligne, dans l'ordre)
COL_BILAN = {"date": 2, "transaction": 4, "debit": 5, "type": 8}


def _date_courte(date: str) -> str:
    """'28/02/2026' -> '28/02/26' (format affiché dans la liste du bilan)."""
    return datetime.strptime(date, "%d/%m/%Y").strftime("%d/%m/%y")


def _ouvrir_bilan(d, cheptel: str, debut: str):
    g.aller_a(d, "Administratif > Bilan Eleveur")
    g.attendre_ecran("Recherche éleveur")
    g.rechercher_eleveur(d, cheptel, lambda: g.titre_fenetre_principale() == "BILAN ELEVEUR")

    g.ecrire(g.champ_par_libelle(d, "Début"), debut)
    g.cliquer(d, "VALIDER (F12)")
    g.attendre_ecran("ANALYSE D'UN BILAN ELEVEUR")


def _selectionner_facture(d, debut: str, date_facture: str) -> str:
    g.ecrire(g.champ_par_libelle(d, "Début"), debut)
    g.cliquer(d, "++")
    time.sleep(1)
    lignes = g.attendre_lignes(d)
    cible = _date_courte(date_facture)
    factures = [i for i, l in enumerate(lignes)
                if l[COL_BILAN["date"]] == cible and l[COL_BILAN["type"]] == "F"]
    if not factures:
        dispo = [f"{l[COL_BILAN['date']]} (n° {l[COL_BILAN['transaction']].rstrip('*')}, {l[COL_BILAN['debit']]} €)"
                 for l in lignes if len(l) > COL_BILAN["type"] and l[COL_BILAN["type"]] == "F"]
        liste = ("Factures de la période : " + " ; ".join(dispo[-10:])) if dispo \
            else f"Aucune facture depuis le {debut}"
        raise LookupError(f"Aucune facture au {date_facture} dans le bilan. {liste}")
    if len(factures) > 1:
        print(f"   Attention : {len(factures)} factures le {date_facture}, la première est prise.")
    i = factures[0]
    g.selectionner_ligne(g.liste_affichee(d), i)
    numero = lignes[i][COL_BILAN["transaction"]].rstrip("*")
    print(f"   Facture n° {numero} du {date_facture} ({lignes[i][COL_BILAN['debit']]} €)")
    return numero


def _enregistrer_pdf(d, chemin_pdf: str):
    g.cliquer(d, "F5 DETAILLER")
    g.attendre_ecran("DETAIL D'UNE FACTURE")

    impression = g.ouvrir_dialogue(d, d, "F5 DUPLICATA", "Impression", "push button")
    apercu = g.ouvrir_dialogue(d, impression, "Aperçu", "Aperçu avant impression", "push button",
                               attente=20, timeout=120)
    dlg = g.ouvrir_dialogue(d, apercu, "Enregistrer en PDF...", "Enregistrement du rapport en PDF ...",
                            "menu item", avant=lambda: g.cliquer_souris(apercu, "Fichier", "menu"))
    if os.path.exists(chemin_pdf):
        os.remove(chemin_pdf)              # même facture : on remplace l'ancien fichier
    g.ecrire(g.champ_par_libelle(dlg, "Nom du fichier"), chemin_pdf)
    g.cliquer_souris(dlg, "Confirmer", "push button")

    fin = time.time() + 60                 # attend que le fichier soit écrit
    while time.time() < fin:
        if os.path.exists(chemin_pdf) and not g.dialogue_ouvert("Enregistrement du rapport en PDF ..."):
            return
        time.sleep(0.5)
    raise TimeoutError(f"Le PDF n'a pas été créé : {chemin_pdf}")


def _fermer_boites(d):
    """Referme les boîtes ouvertes par l'action, sans rien imprimer ni valider."""
    if g.dialogue_ouvert("Enregistrement du rapport en PDF ..."):
        g.trouver(g.attendre_dialogue(d, "Enregistrement du rapport en PDF ..."), "Annuler", "push button").click()
        time.sleep(1)
    if g.dialogue_ouvert("Aperçu avant impression"):
        g.trouver(g.attendre_dialogue(d, "Aperçu avant impression"), "Fermer", "menu item").click()
        time.sleep(1)
    if g.dialogue_ouvert("Impression"):
        g.trouver(g.attendre_dialogue(d, "Impression"), "Annuler", "push button").click()
        time.sleep(1)


def telecharger_facture(d, cheptel: str, date_facture: str, debut: str, dossier: str) -> str:
    """Enregistre le duplicata PDF de la facture du `date_facture` (jj/mm/aaaa) du cheptel.

    Renvoie le chemin du PDF créé.
    """
    os.makedirs(dossier, exist_ok=True)
    try:
        _ouvrir_bilan(d, cheptel, debut)
        numero = _selectionner_facture(d, debut, date_facture)
        date_iso = datetime.strptime(date_facture, "%d/%m/%Y").strftime("%Y-%m-%d")
        chemin = os.path.join(dossier, f"{cheptel}_{numero}_{date_iso}.pdf")
        _enregistrer_pdf(d, chemin)
        return chemin
    finally:
        _fermer_boites(d)
        g.quitter_ecran(d)
