"""Affiche toute la base GENICIA++ en résumé, dans le fichier apercu_base.txt.

Pour chaque table : nombre de lignes, liste des colonnes, et quelques lignes d'exemple.
Lecture seule (uniquement des SELECT, via lecture_bdd.py).

Lancement :  python apercu_base.py            (5 lignes d'exemple par table)
             python apercu_base.py --lignes 10
"""
import argparse
import contextlib
import sys
from pathlib import Path

from lecture_bdd import afficher, apercu, colonnes, connexion, tables

FICHIER = Path(__file__).with_name("apercu_base.txt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lignes", type=int, default=5, help="lignes d'exemple par table")
    a = ap.parse_args()

    cnx = connexion(compte_dsn=True)
    try:
        _, liste = tables(cnx)
        with open(FICHIER, "w", encoding="utf-8") as f, contextlib.redirect_stdout(f):
            print(f"BASE GENICIA++ : {len(liste)} tables/vues\n")
            print("=== SOMMAIRE ===")
            for proprio, nom, type_, nb in liste:
                print(f"  {nom:<45} {type_:<5} {nb or 0:>12,} lignes".replace(",", " "))

            for i, (proprio, nom, type_, nb) in enumerate(liste, 1):
                nb_txt = f"{nb or 0:,}".replace(",", " ")
                print(f"\n\n{'=' * 100}\n{nom}  ({type_}, {nb_txt} lignes)\n{'=' * 100}")
                print("\n--- Colonnes ---")
                afficher(*colonnes(cnx, nom))
                print(f"\n--- {a.lignes} premières lignes ---")
                try:
                    afficher(*apercu(cnx, nom, a.lignes))
                except Exception as e:  # une table illisible ne bloque pas les autres
                    print(f"(lecture impossible : {e})")
                print(f"[{i}/{len(liste)}] {nom}", file=sys.stderr)
    finally:
        cnx.rollback()
        cnx.close()
    print(f"Terminé : {FICHIER}")


if __name__ == "__main__":
    main()
