r"""Mails de test : génère un JSON par mail de copilot/tests/mails_de_test.md, puis les dépose dans le dossier OneDrive
TESTS_MAILS, où un flux Power Automate les envoie par mail (et le mail suit ensuite le circuit normal de l'agent).

Usage (PowerShell, dans H:\SOGEN\EGESYS) :
    python envoyer_mails_test.py --liste              liste les mails de test disponibles
    python envoyer_mails_test.py 1 5 12               envoie les tests 01, 05 et 12
    python envoyer_mails_test.py 19-22                envoie les tests 19 à 22
    python envoyer_mails_test.py --tous               envoie tous les tests, dans l'ordre
    python envoyer_mails_test.py --generer            régénère seulement les JSON (après modification du .md)
Options : --pause 20 (secondes entre deux envois, défaut 15), --destinataire autre@adresse.fr

Format d'un fichier (attendu par le flux) : {"destinataire": ..., "objet": "[EGSYS] [TEST 05] ...", "corps": HTML}.
« [EGSYS] » en tête de l'objet est le filtre qui déclenche le flux ; « [TEST 05] » permet de retrouver le test.

⚠️ Les mails envoyés passent dans le vrai circuit : ceux qui sont valides MODIFIENT les clients de test dans EGESYS
(guitton, brana). Certains tests dépendent d'un autre (09 après 08) ou d'une pièce jointe (08), voir --liste.
"""
import argparse
import html
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_egesys import DRIVE  # noqa: E402

FICHIER_MD = Path(__file__).resolve().parent / "copilot" / "tests" / "mails_de_test.md"
DOSSIER_JSON = FICHIER_MD.parent / "mails_json"
TESTS_MAILS = DRIVE.parent / "TESTS_MAILS"       # OneDrive - Sogen\TESTS_MAILS (surveillé par le flux)
DESTINATAIRE = "thomas.gineste@sogen.coop"       # Boîte surveillée par le flux qui transmet les mails à l'agent
PREFIXE_OBJET = "[EGSYS]"                         # Filtre du flux : toujours en tête de l'objet
CODE_GUITTON = "64464002"                         # Remplace CODE_DE_GUITTON (test 18)


# ---------------------------------------------------------------------------------------------------------------
# Lecture de mails_de_test.md
# ---------------------------------------------------------------------------------------------------------------

def lire_tests():
    """[{numero, titre, expediteur, objet, piece_jointe, corps (texte)}] dans l'ordre du fichier."""
    texte = FICHIER_MD.read_text(encoding="utf-8").replace("CODE_DE_GUITTON", CODE_GUITTON)
    tests = []
    for bloc in re.split(r"\n(?=## Test \d+)", texte)[1:]:
        entete = re.match(r"## Test (\d+) — (.+)", bloc)
        de_objet = re.search(r"\*\*De :\*\* (.+?) — \*\*Objet :\*\* (.+)", bloc)
        piece = re.search(r"\*\*Pièce jointe :\*\* `([^`]+)`", bloc)
        lignes = [re.sub(r"^> ?", "", ligne) for ligne in bloc.splitlines() if ligne.startswith(">")]
        if not (entete and de_objet and lignes):
            sys.exit(f"🛑 Bloc de test mal formé dans {FICHIER_MD.name} : {bloc[:80]!r}")
        tests.append({"numero": int(entete.group(1)), "titre": entete.group(2).strip(),
                      "expediteur": de_objet.group(1).strip(), "objet": de_objet.group(2).strip(),
                      "piece_jointe": piece.group(1) if piece else "", "corps": "\n".join(lignes).strip()})
    return tests


def corps_html(texte):
    """Texte du mail → HTML (le flux envoie un mail HTML : sans <br>, les retours à la ligne disparaîtraient)."""
    paragraphes = [p for p in texte.split("\n\n") if p.strip()]
    return "".join(f"<p>{'<br>'.join(html.escape(ligne, quote=False) for ligne in p.splitlines())}</p>" for p in paragraphes)


def contenu_json(test, destinataire):
    return {"destinataire": destinataire,
            "objet": f"{PREFIXE_OBJET} [TEST {test['numero']:02d}] {test['objet']}",
            "corps": corps_html(test["corps"])}


def generer(destinataire):
    """Écrit copilot/tests/mails_json/test_XX.json pour chaque test. Retourne la liste des tests."""
    tests = lire_tests()
    DOSSIER_JSON.mkdir(parents=True, exist_ok=True)
    for test in tests:
        chemin = DOSSIER_JSON / f"test_{test['numero']:02d}.json"
        chemin.write_text(json.dumps(contenu_json(test, destinataire), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📝 {len(tests)} fichiers JSON générés dans {DOSSIER_JSON}")
    return tests


# ---------------------------------------------------------------------------------------------------------------
# Envoi (dépôt dans TESTS_MAILS)
# ---------------------------------------------------------------------------------------------------------------

def numeros_demandes(arguments, disponibles):
    numeros = []
    for argument in arguments:
        plage = re.fullmatch(r"(\d+)-(\d+)", argument)
        if plage:
            numeros += range(int(plage.group(1)), int(plage.group(2)) + 1)
        elif argument.isdigit():
            numeros.append(int(argument))
        else:
            sys.exit(f"🛑 « {argument} » n'est pas un numéro de test (ex : 5, 19-22).")
    inconnus = sorted(set(numeros) - set(disponibles))
    if inconnus:
        sys.exit(f"🛑 Test(s) inexistant(s) : {inconnus}. Disponibles : {min(disponibles)} à {max(disponibles)}.")
    return list(dict.fromkeys(numeros))


def deposer(test, destinataire):
    """Dépose le JSON dans TESTS_MAILS d'un coup (écriture à côté puis renommage) : le flux ne voit jamais un fichier
    à moitié écrit. Nom unique (heure) : renvoyer un même test redéclenche le flux."""
    nom = f"test_{test['numero']:02d}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    temporaire = TESTS_MAILS.parent / f".{nom}.tmp"   # Hors du dossier surveillé, même disque
    temporaire.write_text(json.dumps(contenu_json(test, destinataire), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaire, TESTS_MAILS / nom)
    return nom


def main():
    parametres = argparse.ArgumentParser(description="Génère et envoie (via le OneDrive) les mails de test EGESYS.")
    parametres.add_argument("tests", nargs="*", help="numéros des tests à envoyer (ex : 1 5 12 ou 19-22)")
    parametres.add_argument("--tous", action="store_true", help="envoyer tous les tests")
    parametres.add_argument("--liste", action="store_true", help="lister les tests disponibles")
    parametres.add_argument("--generer", action="store_true", help="régénérer seulement les JSON")
    parametres.add_argument("--pause", type=int, default=15, help="secondes entre deux envois (défaut 15)")
    parametres.add_argument("--destinataire", default=DESTINATAIRE, help=f"adresse destinataire (défaut {DESTINATAIRE})")
    options = parametres.parse_args()

    tests = generer(options.destinataire)  # Toujours à jour avec le .md
    par_numero = {test["numero"]: test for test in tests}

    if options.liste or not (options.tous or options.tests or options.generer):
        for test in tests:
            remarque = f"  📎 pièce jointe à ajouter à la main : {test['piece_jointe']}" if test["piece_jointe"] else ""
            print(f"  {test['numero']:02d}  {test['titre']:<45} objet : {test['objet']}{remarque}")
        if not (options.liste or options.generer):
            print("\nPréciser les tests à envoyer (ex : python envoyer_mails_test.py 1 5 12, 19-22 ou --tous).")
        return
    if options.generer:
        return

    if not TESTS_MAILS.is_dir():
        sys.exit(f"🛑 Dossier introuvable : {TESTS_MAILS} (OneDrive est-il synchronisé ?)")
    numeros = sorted(par_numero) if options.tous else numeros_demandes(options.tests, par_numero)
    print(f"📤 Envoi de {len(numeros)} mail(s) de test à {options.destinataire} via {TESTS_MAILS}")
    for position, numero in enumerate(numeros, start=1):
        test = par_numero[numero]
        nom = deposer(test, options.destinataire)
        avertissement = f"  ⚠️ sans la pièce jointe {test['piece_jointe']}" if test["piece_jointe"] else ""
        print(f"  ✅ {numero:02d} {test['titre']} → {nom}{avertissement}")
        if position < len(numeros) and options.pause > 0:
            time.sleep(options.pause)
    print("Les réponses arriveront par mail ; le détail est dans le OneDrive EGESYS (completed/, error/, result/).")


if __name__ == "__main__":
    # line_buffering : chaque ligne s'affiche aussitôt (pas de « programme muet » pendant les pauses)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    main()
