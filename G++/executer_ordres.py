"""Exécute dans GENICIA++ les ordres validés par ordres_genicia.py (lancé par le veilleur, ou à la main).

Usage : python executer_ordres.py ordres_valide.json [--fichiers DOSSIER] [--resultats FICHIER.json]
  --fichiers   dossier où ranger les PDF produits (défaut : factures/)
  --resultats  fichier JSON du résultat de chaque ordre (réécrit après chaque ordre)

Déroulement : connexion à GENICIA++ (lancement si besoin), puis chaque ordre l'un après l'autre en partant de
l'accueil. Après une erreur, on ne continue que si GENICIA++ est revenu proprement à l'accueil (sans boîte de
dialogue ouverte) ; sinon les ordres suivants ne sont pas exécutés.
À la fin, GENICIA++ est fermé (Génicia > Quitter > OUI) s'il est revenu à l'accueil sans boîte ouverte ;
sinon il reste ouvert, pour pouvoir constater le problème.

Code de sortie : 0 = tous les ordres réussis ; 1 = au moins un ordre en erreur ou non exécuté.
⚠ Pendant l'exécution, ne touchez ni au clavier ni à la souris.
"""
import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import genicia_auto as g
from action_espace_adherent import generer_espace_adherent, verifier_espace_adherent
from action_facture import telecharger_facture, telecharger_factures
from action_mail_eleveur import MAILS_BILAN, lire_mail_eleveur
from file_attente_genicia import GeniciaOccupe, tour_genicia
from ordres_genicia import libelle_dernieres, libelle_periode, lire_date, lire_periodes

DOSSIER_FACTURES = Path(__file__).with_name("factures")
MAILS_LUS = {}   # cheptel -> adresse mail de la fiche (lue une seule fois par exécution)


def mail_eleveur(d, cheptel):
    """Adresse mail de l'éleveur, pour lui envoyer ses factures. Ne fait jamais échouer l'ordre : '' en cas de souci."""
    if cheptel not in MAILS_LUS and cheptel in MAILS_BILAN:     # lue sur BILAN ELEVEUR (« Coordonnées »)
        MAILS_LUS[cheptel] = MAILS_BILAN[cheptel]
        print(f"   Adresse mail de l'éleveur (Coordonnées) : {MAILS_LUS[cheptel] or 'aucune'}")
    if cheptel not in MAILS_LUS:             # secours : zone « Coordonnées » illisible -> fiche de l'éleveur
        try:
            MAILS_LUS[cheptel] = lire_mail_eleveur(d, cheptel)
            print(f"   Adresse mail de l'éleveur : {MAILS_LUS[cheptel] or 'aucune sur la fiche'}")
        except Exception as erreur:
            print(f"   ⚠️ Adresse mail de l'éleveur non lue ({erreur}) : pas de mail au client.")
            MAILS_LUS[cheptel] = ""
    return MAILS_LUS[cheptel]


ESPACES_VERIFIES = set()   # cheptels dont l'espace adhérent a déjà été vérifié pendant cette exécution
ESPACES_DEMANDES = set()   # cheptels ayant leur propre ordre « generer_espace_adherent » dans le même mail


def espace_eleveur(d, cheptel):
    """Après une récupération de facture(s) : espace adhérent web de l'éleveur vérifié (Droits) et créé s'il ne l'est
    pas. Une seule fois par éleveur et par exécution. Ne fait jamais échouer l'ordre de facture.
    Renvoie ({statut: existant | cree | erreur, ...} ou None si rien à signaler, lignes du compte rendu)."""
    if cheptel in ESPACES_DEMANDES or cheptel in ESPACES_VERIFIES:
        return None, []
    ESPACES_VERIFIES.add(cheptel)
    try:
        espace = verifier_espace_adherent(d, cheptel)
    except Exception as erreur:
        print(f"   ⚠️ Espace adhérent web non vérifié ({erreur})")
        return ({"statut": "erreur", "detail": str(erreur)},
                [f"Espace adhérent web : vérification impossible ({erreur}), à contrôler dans GENICIA++"])
    if espace["statut"] == "existant":
        return espace, ["Espace adhérent web : déjà ouvert (rien n'a été modifié)"]
    print(f"   ✅ Espace adhérent web créé, identifiants envoyés à {espace.get('destinataire')}")
    return espace, ["Espace adhérent web : CRÉÉ automatiquement (Droits était à « Non »), "
                    f"profil {espace.get('profil')}",
                    f"Identifiants web envoyés par mail à : {espace.get('destinataire') or 'l’adresse de la fiche'}"]


def executer_facture(d, ordre, dossier):
    date_facture = ordre["date_facture"]
    debut = f"01/01/{lire_date(date_facture).year}"        # période du bilan : depuis le 1er janvier
    chemin = Path(telecharger_facture(d, ordre["cheptel"], date_facture, debut, str(dossier)))
    numero = chemin.stem.split("_")[1] if chemin.stem.count("_") >= 2 else ""
    detail = f"Duplicata de la facture n° {numero} du {date_facture} récupéré."
    modification = [f"N° de facture : {numero}", f"Date de la facture : {date_facture}",
                    f"Duplicata PDF joint à ce mail : {chemin.name}"]
    infos = {"mail_client": mail_eleveur(d, ordre["cheptel"]), "numero_facture": numero, "date_facture": date_facture,
             "factures": [{"numero_facture": numero, "date_facture": date_facture}]}
    infos["espace_adherent"], lignes = espace_eleveur(d, ordre["cheptel"])
    return detail, [chemin.name], modification + lignes, infos


def executer_factures(d, ordre, dossier):
    periodes = lire_periodes(ordre["periodes"]) if ordre.get("periodes") else []
    dernieres = int(ordre.get("nombre_dernieres") or 0)
    resultat = telecharger_factures(d, ordre["cheptel"], periodes, str(dossier), dernieres)
    factures, manquantes = resultat["factures"], resultat["manquantes"]
    n, s = len(factures), "s" if len(factures) > 1 else ""
    detail = f"{n} duplicata{s} de facture récupéré{s}" + (
        f" ; {len(manquantes)} date(s) ou période(s) sans facture." if manquantes else ".")
    demandees = " ; ".join(libelle_periode(du, au) for du, au in periodes)
    if dernieres:
        demandees = libelle_dernieres(dernieres) + (f" ({demandees})" if demandees else "")
    modification = ([f"Factures demandées : {demandees}"]
                    + [f"Facture n° {f['numero']} du {f['date']}" for f in factures]
                    + [f"{n} duplicata{s} PDF joint{s} à ce mail"]
                    + [f"Non trouvée : {m['periode']} : {m['raison']}" for m in manquantes])
    infos = {"mail_client": mail_eleveur(d, ordre["cheptel"]), "periodes": ordre["periodes"],
             "nombre_dernieres": ordre.get("nombre_dernieres", ""),
             "manquantes": manquantes,
             "factures": [{"numero_facture": f["numero"], "date_facture": f["date"]} for f in factures]}
    infos["espace_adherent"], lignes = espace_eleveur(d, ordre["cheptel"])
    return detail, [Path(f["chemin"]).name for f in factures], modification + lignes, infos


def executer_espace(d, ordre, _dossier):
    info = generer_espace_adherent(d, ordre["cheptel"], ordre["profil"]) or {}
    eleveur, profil = info.get("eleveur") or "l’éleveur", info.get("profil", ordre["profil"])
    destinataire = info.get("destinataire") or "l’adresse de la fiche"
    abonnement = {"créés": "créé", "déjà présents": "déjà présent"}.get(info.get("abonnements"), "?")
    detail = (f"Espace web de {eleveur} créé (profil {profil}). Identifiants envoyés par mail à {destinataire}. "
              f"Abonnement factures par mail sans pièce jointe : {info.get('abonnements', '?')}.")
    modification = [f"Éleveur : {eleveur}", "Droits web : Oui", f"Profil web : {profil}",
                    "Mot de passe : nouveau mot de passe généré (jamais affiché)",
                    f"Identifiants envoyés par mail à : {destinataire}",
                    f"Abonnement factures par mail sans pièce jointe : {abonnement}"]
    return detail, [], modification, {}


ACTIONS = {"telecharger_facture": executer_facture, "telecharger_factures": executer_factures,
           "generer_espace_adherent": executer_espace}


def etat_propre():
    """GENICIA++ est-il revenu à l'accueil, sans boîte de dialogue ouverte ?"""
    try:
        return g.titre_fenetre_principale() == "ACCUEIL" and not g.dialogues_ouverts()
    except Exception:
        return False


def ecrire_resultats(chemin, resultats):
    if chemin:
        Path(chemin).write_text(json.dumps({"ordres": resultats}, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ordres")
    ap.add_argument("--fichiers", default=str(DOSSIER_FACTURES))
    ap.add_argument("--resultats", default="")
    a = ap.parse_args()

    ordres = json.loads(Path(a.ordres).read_text(encoding="utf-8"))
    ESPACES_DEMANDES.update(o["cheptel"] for o in ordres if o.get("action") == "generer_espace_adherent")
    dossier = Path(a.fichiers)
    dossier.mkdir(parents=True, exist_ok=True)
    resultats = [{"numero": i, "action": o["action"], "cheptel": o["cheptel"], "nom_eleveur": o.get("nom_eleveur", ""),
                  "resultat": "Non exécuté", "detail": "", "fichiers": [], "modification": ""}
                 for i, o in enumerate(ordres, start=1)]
    ecrire_resultats(a.resultats, resultats)

    # Un seul programme pilote GENICIA++ à la fois : sinon on attend son tour, dans l'ordre d'arrivée
    try:
        with tour_genicia(f"executer_ordres {Path(a.ordres).name}"):
            piloter(ordres, resultats, dossier, a.resultats)
    except GeniciaOccupe as erreur:
        print(f"🛑 {erreur}")
        for r in resultats:
            r["detail"] = str(erreur)
        ecrire_resultats(a.resultats, resultats)
        sys.exit(1)
    sys.exit(0 if all(r["resultat"] == "Réussite" for r in resultats) else 1)


def piloter(ordres, resultats, dossier, fichier_resultats):
    """Connexion, exécution de chaque ordre, fermeture de GENICIA++ (appelé quand c'est notre tour)."""
    print(f"{datetime.now():%d/%m/%Y %H:%M:%S} Connexion à GENICIA++...")
    try:
        g.demarrer_debloqueur()      # clic dans une zone vide si GENICIA++ reste bloqué (voir genicia_auto)
        d = g.lancer_et_connecter()
        g.quitter_ecran(d)
    except BaseException as erreur:                       # SystemExit compris (identifiants absents)
        print(f"🛑 Connexion à GENICIA++ impossible : {erreur}")
        for r in resultats:
            r["detail"] = f"Connexion à GENICIA++ impossible : {erreur}"
        ecrire_resultats(fichier_resultats, resultats)
        sys.exit(1)

    arret = ""
    for ordre, r in zip(ordres, resultats):
        if arret:
            r["detail"] = arret
            continue
        qui = f"cheptel {ordre['cheptel']}" if ordre["cheptel"] else f"éleveur « {ordre.get('nom_eleveur', '')} »"
        print(f"\n{datetime.now():%H:%M:%S} Ordre {r['numero']} : {ordre['action']} — {qui}")
        try:
            if not ordre["cheptel"]:   # éleveur désigné par son nom : n° de cheptel retrouvé dans GENICIA++
                ordre["cheptel"] = r["cheptel"] = g.identifier_cheptel(d, ordre.get("nom_eleveur", ""))
                print(f"   Éleveur « {ordre.get('nom_eleveur', '')} » : cheptel {ordre['cheptel']}")
                if ordre["action"] == "generer_espace_adherent":
                    ESPACES_DEMANDES.add(ordre["cheptel"])
            r["detail"], r["fichiers"], lignes, infos = ACTIONS[ordre["action"]](d, ordre, dossier)
            r["modification"] = "\n".join(lignes)
            r.update(infos)          # factures : mail_client, factures [{numero_facture, date_facture}]... (mail client)
            r["resultat"] = "Réussite"
            print(f"   ✅ {r['detail']}")
            if not etat_propre():    # ex. lecture du mail interrompue : on ne continue pas à l'aveugle
                arret = ("Non exécuté : GENICIA++ n'est pas revenu à l'accueil après l'ordre "
                         f"{r['numero']}, arrêt par sécurité.")
                print(f"   🛑 {arret}")
        except Exception as erreur:
            r["resultat"] = "Erreur"
            r["detail"] = str(erreur) or type(erreur).__name__
            print(f"   🛑 {r['detail']}")
            print(traceback.format_exc())
            if not etat_propre():
                arret = ("Non exécuté : GENICIA++ n'est pas revenu à l'accueil après l'erreur de l'ordre "
                         f"{r['numero']}, arrêt par sécurité.")
                print(f"   🛑 {arret}")
        ecrire_resultats(fichier_resultats, resultats)

    # Fermeture de GENICIA++ (Génicia > Quitter > OUI), seulement s'il est revenu proprement à l'accueil.
    # Sinon il reste ouvert pour qu'on puisse voir ce qui s'est passé. N'influence pas le résultat des ordres.
    print(f"\n{datetime.now():%H:%M:%S} Fermeture de GENICIA++...")
    try:
        g.quitter_application(d)
        print("   ✅ GENICIA++ fermé.")
    except Exception as erreur:
        print(f"   ⚠️ GENICIA++ laissé ouvert : {erreur}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    main()
