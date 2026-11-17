"""Action : générer l'espace adhérent (accès web) d'un éleveur.

⚠ Cette action MODIFIE des données et ENVOIE UN MAIL à l'éleveur (adresse de sa fiche).

Étapes relevées dans GENICIA++ (10/11/2026) :
  1. Menu Administratif > Eleveur                     -> écran « GESTION DES ELEVEURS »
  2. « F14 COMMUNIC. »                                -> écran « COMMUNICATION AVEC L'ELEVEUR » (recherche)
  3. N° Cheptel : <cheptel>, « Rechercher (F3) »
     (un seul éleveur : la fiche communication s'affiche seule ; sinon ligne + VALIDER (F12))
  4. Droits : Oui ; Profil : <profil> (par défaut ELWEB1 STANDARD)
  5. Bouton clé (sans nom, à droite du champ Mot de passe) : génère un nouveau mot de passe
  6. « ENREGISTRER DROITS »                           -> boîte « Confirmation » :
     « Souhaitez-vous envoyer un mail récapitulatif avec les identifiants WEB ? »
  7. « OUI »                                          -> écran « ENVOI IDENTIFIANTS WEB DE L'ELEVEUR »
                                                         (mail pré-rempli : identifiant + mot de passe)
  8. « VALIDER (F12) » : envoie le mail               -> retour « COMMUNICATION AVEC L'ELEVEUR »
  9. « FACTURES SANS PJ » : crée les abonnements mail (Bulletins de prestations,
     Mail facture sans pièce jointe, Prévision de vêlage, Suivi des inséminations).
     Ignoré si l'abonnement « Mail facture sans pièce jointe » existe déjà.
 10. QUITTER (ESC) jusqu'à l'accueil.

Les clics des étapes 5 à 9 sont de vrais clics souris : ne pas toucher la souris pendant ce temps.
Le mot de passe généré n'est jamais affiché ni enregistré par ce script.

verifier_espace_adherent (17/11/2026), appelé à chaque récupération de facture(s) : étapes 1 à 3, lecture de « Droits »
(« Oui » / « Non »). « Oui » : rien n'est modifié. « Non » : étapes 4 à 10 avec le profil par défaut.
"""
import time

import genicia_auto as g
from ordres_genicia import PROFIL_PAR_DEFAUT

ECRAN_COMMUNICATION = "COMMUNICATION AVEC L'ELEVEUR"
ECRAN_MAIL = "ENVOI IDENTIFIANTS WEB DE L'ELEVEUR"
ABONNEMENT_FACTURES = "Mail facture sans pièce jointe"


def _bouton_cle(d):
    """Bouton sans nom situé juste à droite du champ Mot de passe."""
    champ = g.champ_par_libelle(d, "Mot de passe")
    cb = champ.bounds
    for b in g.visibles(d, "push button"):
        bb = b.bounds
        if not g._nom(b) and abs(bb["y"] - cb["y"]) < 20 and bb["x"] >= cb["x"] + cb["width"] - 5:
            return champ, b
    raise LookupError("Bouton clé introuvable à droite du mot de passe")


def _cliquer_cle(d):
    """Clique sur la clé jusqu'à ce que le mot de passe change (1er clic parfois ignoré)."""
    champ, cle = _bouton_cle(d)
    avant = champ.text
    for _ in range(3):
        g.clic_souris_element(cle)
        fin = time.time() + 5
        while time.time() < fin:
            if champ.text != avant:
                return
            g.pause(0.3)
    raise TimeoutError("Le bouton clé n'a pas généré de nouveau mot de passe")


def _abonnements(d) -> list[str]:
    return [l[1] for l in g.lire_lignes(g.liste_affichee(d)) if len(l) > 1]


def _ouvrir_communication(d, cheptel: str) -> str:
    """Étapes 1 à 3 : fiche « COMMUNICATION AVEC L'ELEVEUR » du cheptel. Renvoie le nom de l'éleveur."""
    g.aller_a(d, "Administratif > Eleveur")
    g.attendre_ecran("GESTION DES ELEVEURS")
    g.cliquer(d, "F14 COMMUNIC.")
    g.attendre_ecran(ECRAN_COMMUNICATION)
    g.rechercher_eleveur(d, cheptel, lambda: any(g._nom(b) == "ENREGISTRER DROITS"
                                                 for b in g.visibles(d, "push button")))
    eleveur = g.champ_par_libelle(d, "Eleveur").text
    print(f"   Éleveur : {eleveur}")
    return eleveur


def _droits_web(d) -> str:
    """Valeur affichée de la liste « Droits » ('Oui' ou 'Non') de la fiche communication."""
    valeur = g.valeur_liste_deroulante(g.liste_deroulante_par_libelle(d, "Droits"))
    if valeur not in ("Oui", "Non"):
        raise RuntimeError(f"Valeur de « Droits » illisible ({valeur!r}) : rien n'est modifié")
    return valeur


def verifier_espace_adherent(d, cheptel: str, profil: str = PROFIL_PAR_DEFAUT) -> dict:
    """Appelé à chaque récupération de facture(s) : regarde « Droits » sur la fiche communication de l'éleveur.
    - « Oui » : l'espace adhérent existe déjà, rien n'est modifié -> {"statut": "existant"} ;
    - « Non » : l'espace est généré comme l'action generer_espace_adherent (droits, profil par défaut, nouveau mot de
      passe, mail des identifiants à l'éleveur, abonnement factures sans PJ) -> {"statut": "cree", eleveur, profil,
      destinataire, abonnements}.
    """
    try:
        eleveur = _ouvrir_communication(d, cheptel)
        droits = _droits_web(d)
        print(f"   Espace adhérent web (Droits) : {droits}")
        if droits == "Oui":
            return {"statut": "existant", "eleveur": eleveur}
        return {"statut": "cree", **_generer_sur_la_fiche(d, eleveur, profil)}
    finally:
        g.quitter_ecran(d)


def generer_espace_adherent(d, cheptel: str, profil: str = PROFIL_PAR_DEFAUT) -> dict:
    """Renvoie un résumé : éleveur, profil, destinataire du mail, abonnements (jamais le mot de passe)."""
    try:
        eleveur = _ouvrir_communication(d, cheptel)
        return _generer_sur_la_fiche(d, eleveur, profil)
    finally:
        g.quitter_ecran(d)


def _generer_sur_la_fiche(d, eleveur: str, profil: str) -> dict:
    """Étapes 4 à 9, depuis la fiche communication déjà ouverte."""
    # 4 : droits et profil
    g.choisir(g.liste_deroulante_par_libelle(d, "Droits"), "Oui")
    g.choisir(g.liste_deroulante_par_libelle(d, "Profil"), profil)

    # 5 : nouveau mot de passe
    _cliquer_cle(d)
    print("   Nouveau mot de passe généré")

    # 6-7 : enregistrement des droits + mail récapitulatif
    confirmation = g.ouvrir_dialogue(d, d, "ENREGISTRER DROITS", "Confirmation", "push button")
    g.cliquer_souris_jusqua(confirmation, "OUI",
                            lambda: g.titre_fenetre_principale() == ECRAN_MAIL,
                            role="push button", description="ouverture du mail")
    destinataire = g.champ_par_libelle(d, "A").text
    print(f"   Droits enregistrés, envoi du mail à {destinataire}")

    # 8 : envoi du mail
    g.cliquer_souris_jusqua(d, "VALIDER (F12)",
                            lambda: g.titre_fenetre_principale() == ECRAN_COMMUNICATION,
                            role="push button", description="envoi du mail")
    print("   Mail envoyé")

    # 9 : abonnements « factures sans PJ »
    if ABONNEMENT_FACTURES in _abonnements(d):
        abonnements = "déjà présents"
        print("   Abonnement « factures sans PJ » déjà présent : rien à faire")
    else:
        avant = len(_abonnements(d))
        g.cliquer_souris_jusqua(d, " FACTURES SANS PJ",
                                lambda: len(_abonnements(d)) > avant,
                                role="push button", description="création des abonnements")
        abonnements = "créés"
        print(f"   Abonnements : {', '.join(_abonnements(d))}")
    return {"eleveur": eleveur, "profil": profil, "destinataire": destinataire,
            "abonnements": abonnements}
