"""Script principal GENICIA++ : lance le logiciel (si besoin), se connecte, puis exécute une action.

Actions disponibles :

  facture   Télécharger le duplicata PDF d'une facture (étapes : action_facture.py)
              python main.py facture
              python main.py facture 64284002 28/02/2026 --debut 01/01/2026
            -> PDF enregistré dans le dossier « factures »

  espace    Générer l'espace adhérent web d'un éleveur (étapes : action_espace_adherent.py)
            ⚠ modifie la fiche et ENVOIE UN MAIL avec les identifiants à l'éleveur
              python main.py espace 64284002
              python main.py espace 64284002 --profil "ELWEB1 STANDARD"

Pendant une action, ne pas toucher au clavier ni à la souris (certains clics sont de vrais clics souris).
"""
import argparse
import sys
from pathlib import Path

import genicia_auto as g
from action_espace_adherent import generer_espace_adherent
from action_facture import telecharger_facture

sys.stdout.reconfigure(encoding="utf-8")
DOSSIER_FACTURES = Path(__file__).with_name("factures")


def main():
    ap = argparse.ArgumentParser(description="Automatisation GENICIA++",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    actions = ap.add_subparsers(dest="action", required=True)

    f = actions.add_parser("facture", help="télécharger le duplicata PDF d'une facture")
    f.add_argument("cheptel", nargs="?", default="64284002", help="N° de cheptel")
    f.add_argument("date_facture", nargs="?", default="28/02/2026", help="date de la facture jj/mm/aaaa")
    f.add_argument("--debut", default="01/01/2026", help="début de la période du bilan jj/mm/aaaa")

    e = actions.add_parser("espace", help="générer l'espace adhérent web (envoie un mail)")
    e.add_argument("cheptel", help="N° de cheptel")
    e.add_argument("--profil", default="ELWEB1 STANDARD", help="profil web")

    a = ap.parse_args()

    print("Lancement et connexion à GENICIA++...")
    d = g.lancer_et_connecter()
    g.quitter_ecran(d)                                   # part toujours de l'accueil

    if a.action == "facture":
        print(f"Facture du {a.date_facture} pour le cheptel {a.cheptel}...")
        chemin = telecharger_facture(d, a.cheptel, a.date_facture, a.debut, str(DOSSIER_FACTURES))
        print(f"PDF enregistré : {chemin}")
    elif a.action == "espace":
        print(f"Espace adhérent du cheptel {a.cheptel} (profil {a.profil})...")
        generer_espace_adherent(d, a.cheptel, a.profil)
        print("Espace adhérent généré.")


if __name__ == "__main__":
    main()
