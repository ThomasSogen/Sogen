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

Plusieurs factures sur une période (telecharger_factures, relevé le 17/11/2026) :
  - étapes 1 à 3 avec Début = début de la période ;
  - écran « ANALYSE D'UN BILAN ELEVEUR » : Début et Fin de la période, « ++ ». La liste mélange factures et autres
    opérations (SOLDE, prélèvements, chèques, NON FACTURE) : une facture = colonne Type « F » ET Transaction composée
    de chiffres (ex. « 4500000088031* »). GENICIA++ n'applique pas toujours la date de Fin : le programme filtre
    lui-même les dates de la liste ;
  - pour chaque facture, l'une après l'autre : sélection de sa ligne (retrouvée par son n°), étapes 6 à 11 sans
    revenir à l'accueil, puis QUITTER (ESC) une fois depuis « DETAIL D'UNE FACTURE » pour revenir à l'analyse.
"""
import os
import time
from datetime import date, datetime

import genicia_auto as g
from ordres_genicia import MAX_FACTURES   # au-delà, la demande est refusée (période à réduire), comme sur EGESYS

# Colonnes des listes (étiquettes de chaque ligne, dans l'ordre)
COL_BILAN = {"date": 2, "transaction": 4, "debit": 5, "type": 8}
ECRAN_ANALYSE = "ANALYSE D'UN BILAN ELEVEUR"
ECRAN_DETAIL = "DETAIL D'UNE FACTURE"


def _date_courte(date: str) -> str:
    """'28/02/2026' -> '28/02/26' (format affiché dans la liste du bilan)."""
    return datetime.strptime(date, "%d/%m/%Y").strftime("%d/%m/%y")


def _champ(d, libelle: str, timeout: float = 15):
    """Champ à droite du libellé, en attendant qu'il soit affiché (l'écran peut finir de se dessiner)."""
    fin = time.time() + timeout
    while True:
        try:
            return g.champ_par_libelle(d, libelle)
        except LookupError:
            if time.time() > fin:
                raise
            g.pause(0.5)


def _ouvrir_bilan(d, cheptel: str, debut: str):
    g.aller_a(d, "Administratif > Bilan Eleveur")
    g.attendre_ecran("Recherche éleveur")
    g.rechercher_eleveur(d, cheptel, lambda: g.titre_fenetre_principale() == "BILAN ELEVEUR")

    g.ecrire(_champ(d, "Début"), debut)
    g.cliquer(d, "VALIDER (F12)")
    g.attendre_ecran(ECRAN_ANALYSE)


def _selectionner_facture(d, debut: str, date_facture: str) -> str:
    g.ecrire(_champ(d, "Début"), debut)
    g.cliquer(d, "++")
    g.pause(1)
    lignes = g.attendre_lignes(d)
    cible = _date_courte(date_facture)
    factures = [i for i, l in enumerate(lignes)          # lignes incomplètes (liste en cours de chargement) ignorées
                if len(l) > COL_BILAN["type"] and l[COL_BILAN["date"]] == cible and l[COL_BILAN["type"]] == "F"]
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


def _verifier_numero(d, numero: str, timeout: float = 15):
    """Contrôle que l'écran de détail affiche bien la facture attendue (libellé « Facture n°<numéro> »)."""
    fin = time.time() + timeout
    while True:
        affiches = [g._texte_libelle(g._nom(l)).replace(" ", "") for l in g.visibles(d, "label")]
        if f"facturen°{numero}" in affiches:
            return
        if time.time() > fin:
            vus = [a for a in affiches if a.startswith("facturen°")]
            raise RuntimeError(f"Mauvaise facture ouverte (attendu n° {numero}, affiché : {vus or 'aucun n°'}), "
                               "arrêt par sécurité")
        g.pause(0.5)


def _enregistrer_pdf(d, chemin_pdf: str, numero: str = ""):
    g.cliquer(d, "F5 DETAILLER")
    g.attendre_ecran(ECRAN_DETAIL)
    if numero:
        _verifier_numero(d, numero)

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
        g.pause(0.5)
    raise TimeoutError(f"Le PDF n'a pas été créé : {chemin_pdf}")


def _fermer_boites(d):
    """Referme les boîtes ouvertes par l'action, sans rien imprimer ni valider."""
    if g.dialogue_ouvert("Enregistrement du rapport en PDF ..."):
        g.trouver(g.attendre_dialogue(d, "Enregistrement du rapport en PDF ..."), "Annuler", "push button").click()
        g.pause(1)
    if g.dialogue_ouvert("Aperçu avant impression"):
        g.trouver(g.attendre_dialogue(d, "Aperçu avant impression"), "Fermer", "menu item").click()
        g.pause(1)
    if g.dialogue_ouvert("Impression"):
        g.trouver(g.attendre_dialogue(d, "Impression"), "Annuler", "push button").click()
        g.pause(1)


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
        _enregistrer_pdf(d, chemin, numero)
        return chemin
    finally:
        _fermer_boites(d)
        g.quitter_ecran(d)


# ---------------------------------------------------------------- plusieurs factures sur une période

def _lignes_completes(d) -> list[list[str]]:
    """Lignes de la liste du bilan, une fois son chargement terminé (même nombre de lignes deux fois de suite)."""
    lignes, fin = g.attendre_lignes(d), time.time() + 20
    while time.time() < fin:
        g.pause(1)
        relues = g.attendre_lignes(d)
        if len(relues) == len(lignes) and all(len(l) > COL_BILAN["type"] for l in relues):
            return relues
        lignes = relues
    return lignes


def _afficher_periode(d, du: str, au: str) -> list[list[str]]:
    """Écran d'analyse : Début / Fin de la période, « ++ », puis lignes de la liste."""
    g.ecrire(_champ(d, "Début"), du)
    g.ecrire(_champ(d, "Fin"), au)
    g.cliquer(d, "++")
    g.pause(1)
    return _lignes_completes(d)


def _numero_facture(ligne) -> str:
    """N° de la facture de la ligne, ou "" si la ligne n'est pas une facture (SOLDE, chèque, prélèvement...)."""
    if len(ligne) <= COL_BILAN["type"] or ligne[COL_BILAN["type"]] != "F":
        return ""
    numero = ligne[COL_BILAN["transaction"]].rstrip("*").strip()
    return numero if numero.isdigit() else ""


def factures_de_la_periode(lignes, du: date, au: date) -> list[tuple[str, str]]:
    """[(n° de facture, date JJ/MM/AAAA)] des factures datées entre du et au (inclus), dans l'ordre de la liste."""
    factures = []
    for ligne in lignes:
        numero = _numero_facture(ligne)
        try:
            jour = datetime.strptime(ligne[COL_BILAN["date"]], "%d/%m/%y").date()
        except (ValueError, IndexError):
            continue
        if numero and du <= jour <= au and numero not in (n for n, _ in factures):
            factures.append((numero, jour.strftime("%d/%m/%Y")))
    return factures


def _revenir_a_l_analyse(d):
    """Depuis « DETAIL D'UNE FACTURE » : QUITTER (ESC) une fois, sans rien valider."""
    if g.dialogues_ouverts():
        raise RuntimeError(f"Boîte de dialogue ouverte, arrêt par sécurité : {g.dialogues_ouverts()}")
    if g.titre_fenetre_principale() == ECRAN_DETAIL:
        g.cliquer(d, "QUITTER (ESC)")
    g.attendre_ecran(ECRAN_ANALYSE)


def telecharger_factures(d, cheptel: str, periode_du: str, periode_au: str, dossier: str) -> list[dict]:
    """Enregistre le duplicata PDF de chaque facture du cheptel datée du `periode_du` au `periode_au` (JJ/MM/AAAA,
    inclus). Renvoie [{"chemin", "numero", "date"}] dans l'ordre chronologique.

    LookupError si aucune facture sur la période ou s'il y en a plus de MAX_FACTURES (rien n'est enregistré).
    En cas d'erreur en cours de route, les PDF déjà enregistrés par cet appel sont supprimés (tout ou rien).
    """
    du = datetime.strptime(periode_du, "%d/%m/%Y").date()
    au = datetime.strptime(periode_au, "%d/%m/%Y").date()
    os.makedirs(dossier, exist_ok=True)
    enregistrees = []
    try:
        _ouvrir_bilan(d, cheptel, periode_du)
        factures = factures_de_la_periode(_afficher_periode(d, periode_du, periode_au), du, au)
        if not factures:
            raise LookupError(f"Aucune facture du {periode_du} au {periode_au} dans le bilan de l'éleveur.")
        if len(factures) > MAX_FACTURES:
            raise LookupError(f"Trop de factures du {periode_du} au {periode_au} : {len(factures)} "
                              f"(maximum {MAX_FACTURES}). Période à réduire.")
        print(f"   {len(factures)} facture(s) du {periode_du} au {periode_au} : "
              + ", ".join(n for n, _ in factures))

        for rang, (numero, date_facture) in enumerate(factures, start=1):
            if rang > 1:      # la liste est relue à chaque tour : on retrouve la facture par son n°
                lignes = _afficher_periode(d, periode_du, periode_au)
            else:
                lignes = _lignes_completes(d)
            index = next((i for i, l in enumerate(lignes) if _numero_facture(l) == numero), None)
            if index is None:
                raise LookupError(f"Facture n° {numero} disparue de la liste du bilan")
            g.selectionner_ligne(g.liste_affichee(d), index)
            print(f"   [{rang}/{len(factures)}] Facture n° {numero} du {date_facture} "
                  f"({lignes[index][COL_BILAN['debit']]} €)")
            date_iso = datetime.strptime(date_facture, "%d/%m/%Y").strftime("%Y-%m-%d")
            chemin = os.path.join(dossier, f"{cheptel}_{numero}_{date_iso}.pdf")
            _enregistrer_pdf(d, chemin, numero)
            enregistrees.append({"chemin": chemin, "numero": numero, "date": date_facture})
            _fermer_boites(d)
            _revenir_a_l_analyse(d)
        return enregistrees
    except BaseException:
        for facture in enregistrees:          # tout ou rien : pas de PDF isolé joint à un ordre en erreur
            try:
                os.remove(facture["chemin"])
            except OSError:
                pass
        raise
    finally:
        _fermer_boites(d)
        g.quitter_ecran(d)
