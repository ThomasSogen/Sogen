"""Lecture (sans rien modifier) de l'adresse mail d'un éleveur, pour lui envoyer ses factures.

Étapes relevées dans GENICIA++ (17/11/2026) :
  1. Menu Administratif > Bilan Eleveur                      -> écran « Recherche éleveur »
  2. N° Cheptel : <cheptel>, bouton « Rechercher (F3) »      -> écran « BILAN ELEVEUR »
  3. « F5 FICHE ELV. » (clic souris ; le 1er clic est parfois mangé par le menu resté ouvert)
                                                             -> écran « CONSULTATION D'UN ELEVEUR », page 1/8
  4. « SUIVANT »                                             -> page 2/8 (adresse, téléphones, e-mail)
  5. Lecture du champ « e-mail » (le champ « e-mail Facture » voisin n'est pas utilisé)
  6. QUITTER (ESC) jusqu'à l'accueil (aucune boîte de confirmation : écran de consultation)
"""
import re
import time

import genicia_auto as g

ECRAN_FICHE = "CONSULTATION D'UN ELEVEUR"
MOTIF_MAIL = re.compile(r"[^@\s;,<>]+@[^@\s;,<>]+\.[A-Za-z]{2,}")


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
        texte = (champ.text or "").strip()
        trouve = MOTIF_MAIL.fullmatch(texte)
        return trouve.group(0) if trouve else ""
    finally:
        g.quitter_ecran(d)
