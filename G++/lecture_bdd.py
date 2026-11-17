"""Lecture (seule) de la base GENICIA++ : Sybase SQL Anywhere 9 via le DSN ODBC « bddg++ ».

Identifiants : jamais dans le code.
  - par défaut : variables d'environnement GENICIA_DB_UID / GENICIA_DB_PWD
    (le compte lecture seule fourni par l'IT) ;
  - option --compte-dsn : utilise le compte enregistré dans le DSN (compte applicatif,
    tous droits) -> à réserver aux essais autorisés.

Sécurité : seules les requêtes SELECT/WITH sont acceptées, en transaction
non validée (rollback systématique à la fermeture).

Exemples :
  python lecture_bdd.py tables
  python lecture_bdd.py colonnes NOM_TABLE
  python lecture_bdd.py apercu NOM_TABLE --lignes 20
  python lecture_bdd.py sql "SELECT TOP 10 * FROM ma_table" --csv sortie.csv
"""
import argparse
import csv
import os
import re
import sys

import pyodbc

DSN = "bddg++"
ENCODAGE = "cp1252"  # encodage habituel des bases ASA 9 sous Windows FR

sys.stdout.reconfigure(encoding="utf-8")


def connexion(compte_dsn: bool = False) -> pyodbc.Connection:
    chaine = f"DSN={DSN};"
    if not compte_dsn:
        uid, pwd = os.environ.get("GENICIA_DB_UID"), os.environ.get("GENICIA_DB_PWD")
        if not uid or not pwd:
            sys.exit("Définir GENICIA_DB_UID et GENICIA_DB_PWD (ou utiliser --compte-dsn).")
        chaine += f"UID={uid};PWD={pwd};"
    cnx = pyodbc.connect(chaine, autocommit=False, timeout=10)
    cnx.setdecoding(pyodbc.SQL_CHAR, encoding=ENCODAGE)
    cnx.setencoding(encoding=ENCODAGE)
    return cnx


_LECTURE = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


def lire(cnx: pyodbc.Connection, sql: str, params=()):
    """Exécute une requête de lecture et renvoie (colonnes, lignes)."""
    if not _LECTURE.match(sql) or ";" in sql.rstrip().rstrip(";"):
        raise ValueError("Seules les requêtes SELECT/WITH uniques sont autorisées.")
    cur = cnx.cursor()
    cur.execute(sql, params)
    colonnes = [d[0] for d in cur.description]
    return colonnes, cur.fetchall()


def tables(cnx):
    return lire(cnx, """
        SELECT u.user_name AS proprietaire, t.table_name, t.table_type, t.count AS nb_lignes_approx
        FROM SYS.SYSTABLE t JOIN SYS.SYSUSERPERM u ON u.user_id = t.creator
        WHERE u.user_name NOT IN ('SYS', 'dbo', 'rs_systabgroup')
        ORDER BY t.table_type, t.table_name""")


def colonnes(cnx, table: str):
    return lire(cnx, """
        SELECT cname AS colonne, coltype AS type, length AS taille, nulls, in_primary_key AS pk
        FROM SYS.SYSCOLUMNS WHERE tname = ? ORDER BY colno""", (table,))


def apercu(cnx, table: str, lignes: int):
    if not re.fullmatch(r"[A-Za-z0-9_]+", table):
        raise ValueError("Nom de table invalide.")
    return lire(cnx, f'SELECT TOP {int(lignes)} * FROM "{table}"')


def afficher(colonnes_, lignes, largeur_max=40):
    def txt(v):
        s = "" if v is None else str(v)
        return s if len(s) <= largeur_max else s[: largeur_max - 1] + "…"
    rows = [[txt(v) for v in r] for r in lignes]
    larg = [max([len(c)] + [len(r[i]) for r in rows]) for i, c in enumerate(colonnes_)]
    print("  ".join(c.ljust(l) for c, l in zip(colonnes_, larg)))
    print("  ".join("-" * l for l in larg))
    for r in rows:
        print("  ".join(v.ljust(l) for v, l in zip(r, larg)))
    print(f"\n{len(rows)} ligne(s)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("commande", choices=["tables", "colonnes", "apercu", "sql"])
    ap.add_argument("argument", nargs="?", help="nom de table ou requête SQL")
    ap.add_argument("--lignes", type=int, default=10)
    ap.add_argument("--csv", help="exporter le résultat dans ce fichier CSV")
    ap.add_argument("--compte-dsn", action="store_true", help="utiliser le compte enregistré dans le DSN")
    a = ap.parse_args()

    cnx = connexion(a.compte_dsn)
    try:
        if a.commande == "tables":
            res = tables(cnx)
        elif a.commande == "colonnes":
            res = colonnes(cnx, a.argument)
        elif a.commande == "apercu":
            res = apercu(cnx, a.argument, a.lignes)
        else:
            res = lire(cnx, a.argument)
        if a.csv:
            with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(res[0])
                w.writerows(res[1])
            print(f"{len(res[1])} ligne(s) exportée(s) dans {a.csv}")
        else:
            afficher(*res)
    finally:
        cnx.rollback()
        cnx.close()


if __name__ == "__main__":
    main()
