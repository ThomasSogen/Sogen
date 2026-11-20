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
from datetime import date, datetime, timedelta

import genicia_auto as g
from action_mail_eleveur import MAILS_BILAN, mail_des_coordonnees
from ordres_genicia import DEBUT_HISTORIQUE, MAX_FACTURES, libelle_dernieres, libelle_periode   # au-delà de MAX_FACTURES : refus (comme sur EGESYS)

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
    # Adresse mail de l'éleveur, affichée ici (« Coordonnées : … Email : … ») : plus besoin d'ouvrir sa fiche
    if cheptel not in MAILS_BILAN:
        try:
            adresse = mail_des_coordonnees(d)
            if adresse is not None:
                MAILS_BILAN[cheptel] = adresse
        except Exception as erreur:          # ne fait jamais échouer la récupération des factures
            g.journal(f"adresse mail non lue dans « Coordonnées » ({erreur})")

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
            g.journal(f"n° de facture affiché vérifié : {numero}")
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

    g.journal(f"attente de l'écriture du PDF : {os.path.basename(chemin_pdf)}")
    g._attente(f"écriture du PDF {os.path.basename(chemin_pdf)}")
    fin = time.time() + 60                 # attend que le fichier soit écrit
    while time.time() < fin:
        if os.path.exists(chemin_pdf) and not g.dialogue_ouvert("Enregistrement du rapport en PDF ..."):
            g.journal(f"PDF écrit ({os.path.getsize(chemin_pdf)} octets)")
            return
        g.pause(0.5)
    raise TimeoutError(f"Le PDF n'a pas été créé : {chemin_pdf}")


def _fermer_boites(d):
    """Referme les boîtes ouvertes par l'action, sans rien imprimer ni valider."""
    g.journal(f"fermeture des boîtes ouvertes : {g.dialogues_ouverts() or 'aucune'}")
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


def _plus_proches(toutes, du: date, au: date, nombre: int = 2) -> str:
    """« n° 4500… du 31/01/2026, n° 4500… du 28/02/2026 » : factures du bilan les plus proches d'une date ou période
    sans facture (aide pour l'utilisateur), ou "" s'il n'y en a aucune dans la liste lue."""
    def ecart(facture):
        jour = datetime.strptime(facture[1], "%d/%m/%Y").date()
        return (du - jour).days if jour < du else (jour - au).days
    proches = sorted(sorted(toutes, key=ecart)[:nombre], key=lambda f: datetime.strptime(f[1], "%d/%m/%Y"))
    return ", ".join(f"n° {numero} du {jour}" for numero, jour in proches)


def telecharger_factures(d, cheptel: str, periodes: list[tuple[date, date]], dossier: str,
                         dernieres: int = 0) -> dict:
    """Enregistre le duplicata PDF de chaque facture du cheptel datée dans l'une des `periodes` ([(début, fin)],
    bornes incluses ; début = fin pour une date précise).

    Une date ou période sans facture N'ARRÊTE PAS la demande : elle est notée (avec les factures les plus proches)
    et les autres sont récupérées. Renvoie {"factures": [{"chemin", "numero", "date"}] (ordre chronologique),
    "manquantes": [{"periode": « le 31/01/2026 » / « du … au … », "raison": …}]}.

    LookupError (rien n'est enregistré) si aucune facture sur l'ensemble des dates, ou plus de MAX_FACTURES.
    En cas d'erreur technique en cours de route, les PDF déjà enregistrés par cet appel sont supprimés (tout ou rien).

    dernieres = N : seules les N factures les plus récentes sont gardées (« ses 3 dernières factures ») ; sans
    `periodes`, tout le bilan de l'éleveur est lu (depuis DEBUT_HISTORIQUE). Moins de N factures : entrée
    « manquantes » avec "nombre_demande".
    """
    toutes_dates = not periodes
    if toutes_dates:
        if not dernieres:
            raise ValueError("Ni dates ni nombre de dernières factures")
        periodes = [(DEBUT_HISTORIQUE, date.today())]
    debut, fin = min(du for du, _ in periodes), max(au for _, au in periodes)
    # liste lue un mois avant la 1re date : permet de proposer la facture la plus proche d'une date sans facture
    debut_liste, fin_liste = (debut - timedelta(days=31)).strftime("%d/%m/%Y"), fin.strftime("%d/%m/%Y")
    os.makedirs(dossier, exist_ok=True)
    enregistrees = []
    try:
        _ouvrir_bilan(d, cheptel, debut_liste)
        lignes = _afficher_periode(d, debut_liste, fin_liste)
        toutes = factures_de_la_periode(lignes, date.min, date.max)
        retenues, manquantes = {}, []
        for du, au in periodes:
            trouvees = factures_de_la_periode(lignes, du, au)
            libelle = libelle_periode(du, au)
            if trouvees:
                print(f"   {libelle} : {len(trouvees)} facture(s) : " + ", ".join(n for n, _ in trouvees))
                retenues.update(dict(trouvees))
                continue
            if toutes_dates:
                break
            proches = _plus_proches(toutes, du, au)
            raison = ("aucune facture à cette date" if du == au else "aucune facture sur cette période") \
                + " dans le bilan de l'éleveur"
            if proches:
                raison += f" (factures les plus proches : {proches})"
            manquantes.append({"periode": libelle, "raison": raison})
            print(f"   {libelle} : {raison}")
        factures = sorted(retenues.items(), key=lambda f: datetime.strptime(f[1], "%d/%m/%Y"))
        if dernieres and factures:
            factures = factures[-dernieres:]          # les N plus récentes (toujours dans l'ordre chronologique)
            print(f"   {libelle_dernieres(dernieres).capitalize()} : "
                  + ", ".join(f"n° {n} du {j}" for n, j in reversed(factures)))
            if len(factures) < dernieres:
                manque = {"periode": libelle_dernieres(dernieres), "nombre_demande": dernieres,
                          "raison": f"seulement {len(factures)} facture(s) trouvée(s)"
                                    + (" pour cet éleveur" if toutes_dates else " sur les dates demandées")}
                manquantes.append(manque)
                print(f"   {manque['periode']} : {manque['raison']}")
        if not factures and toutes_dates:
            raise LookupError("Aucune facture pour les dates demandées : aucune facture dans le bilan de l'éleveur")
        if not factures:
            raise LookupError("Aucune facture pour les dates demandées : "
                              + " ; ".join(f"{m['periode']} : {m['raison']}" for m in manquantes))
        if len(factures) > MAX_FACTURES:
            raise LookupError(f"Trop de factures pour les dates demandées : {len(factures)} "
                              f"(maximum {MAX_FACTURES}). Période à réduire.")

        for rang, (numero, date_facture) in enumerate(factures, start=1):
            if rang > 1:      # la liste est relue à chaque tour : on retrouve la facture par son n°
                lignes = _afficher_periode(d, debut_liste, fin_liste)
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
        return {"factures": enregistrees, "manquantes": manquantes}
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
