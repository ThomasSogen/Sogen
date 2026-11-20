"""Lecture (sans rien modifier) de l'adresse mail d'un éleveur, pour lui envoyer ses factures.

Étapes relevées dans GENICIA++ (17/11/2026) :
  1. Menu Administratif > Bilan Eleveur                      -> écran « Recherche éleveur »
  2. N° Cheptel : <cheptel>, bouton « Rechercher (F3) »      -> écran « BILAN ELEVEUR »
  3. « F5 FICHE ELV. » (clic souris ; le 1er clic est parfois mangé par le menu resté ouvert)
                                                             -> écran « CONSULTATION D'UN ELEVEUR », page 1/8
  4. « SUIVANT »                                             -> page 2/8 (adresse, téléphones, e-mail)
  5. Lecture du champ « e-mail » (le champ « e-mail Facture » voisin n'est pas utilisé)
  6. QUITTER (ESC) jusqu'à l'accueil (aucune boîte de confirmation : écran de consultation)

Depuis le 19/11/2026 (indication de l'utilisateur), l'adresse est lue DIRECTEMENT sur l'écran « BILAN ELEVEUR »,
déjà ouvert pour récupérer les factures : valeur de « Coordonnées : », qui contient « Email : <adresse> »
(mail_des_coordonnees, appelée par action_facture._ouvrir_bilan). Le chemin ci-dessus ne sert plus que de secours,
si la zone « Coordonnées » n'a pas pu être lue.
"""
import re
import time

import genicia_auto as g

ECRAN_FICHE = "CONSULTATION D'UN ELEVEUR"
MOTIF_MAIL = re.compile(r"[^@\s;,<>]+@[^@\s;,<>]+\.[A-Za-z]{2,}")
MAILS_BILAN = {}     # cheptel -> adresse lue dans « Coordonnées » de BILAN ELEVEUR ("" = aucune adresse)


def mail_des_coordonnees(d):
    """Adresse mail de la zone « Coordonnées : » de l'écran BILAN ELEVEUR (« … Email : x@y.fr … »).
    Renvoie "" si la zone ne contient pas d'adresse, None si la zone est introuvable (lecture impossible)."""
    textes = []
    try:
        textes.append(g.lire(g.champ_par_libelle(d, "Coordonnées"), "« Coordonnées »"))
    except LookupError:
        # zone de plusieurs lignes ou simple texte : tout élément affiché qui parle d'e-mail
        for e in g.visibles(d, "text") + g.visibles(d, "label"):
            texte = (e.text or "") if g._role(e) == "text" else g._nom(e)
            if "mail" in texte.lower():
                textes.append(texte)
        g.journal(f"zone « Coordonnées » lue autrement : {textes or 'rien trouvé'}")
    tout = " ".join(textes)
    if "mail" not in tout.lower():     # zone vide ou autre champ : on ne conclut pas (chemin de secours)
        g.journal("aucune mention « Email » dans « Coordonnées » : lecture par la fiche de l'éleveur")
        return None
    trouve = re.search(r"e-?mail\s*:?\s*([^\s;,<>]+@[^\s;,<>]+)", tout, re.I) or MOTIF_MAIL.search(tout)
    adresse = (trouve.group(1) if trouve and trouve.groups() else trouve.group(0) if trouve else "").strip(".")
    adresse = adresse if MOTIF_MAIL.fullmatch(adresse) else ""
    g.journal(f"adresse mail de l'éleveur (Coordonnées) : {adresse or 'aucune'}")
    return adresse


def lire_mail_eleveur(d, cheptel: str, timeout: float = 30) -> str:
    """Adresse mail de la fiche de l'éleveur ('' si vide ou invalide). Revient toujours à l'accueil."""
    g.quitter_ecran(d)
    try:
        g.aller_a(d, "Administratif > Bilan Eleveur")
        g.attendre_ecran("Recherche éleveur")
        g.rechercher_eleveur(d, cheptel, lambda: g.titre_fenetre_principale() == "BILAN ELEVEUR")
        # Pendant le chargement de la fiche, le titre n'indique plus d'écran (comme l'accueil) : on reclique seulement
        # si l'écran BILAN ELEVEUR est toujours affiché, puis on attend la fiche.
        g.cliquer_souris_jusqua(d, "F5 FICHE ELV.", lambda: g.titre_fenetre_principale() != "BILAN ELEVEUR",
                                role="push button", description="ouverture de la fiche éleveur")
        g.attendre_ecran(ECRAN_FICHE, timeout=60)
        g.attendre_element(d, "SUIVANT", "push button")
        g.cliquer(d, "SUIVANT", "push button")
        fin = time.time() + timeout
        while True:                                   # la page 2 est affichée quand le libellé « e-mail » apparaît
            try:
                champ = g.champ_par_libelle(d, "e-mail")
                break
            except LookupError:
                if time.time() > fin:
                    raise TimeoutError("Fiche éleveur : champ « e-mail » introuvable (page 2)")
                g.pause(0.5)
        texte = g.lire(champ, "« e-mail » de la fiche").strip()
        trouve = MOTIF_MAIL.fullmatch(texte)
        return trouve.group(0) if trouve else ""
    finally:
        g.quitter_ecran(d)
