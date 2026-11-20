r"""Mails de test G++ : génère un JSON par mail de copilot/tests/mails_de_test.md, puis les dépose dans le dossier
OneDrive TESTS_MAILS, où un flux Power Automate les envoie par mail (le mail suit ensuite le circuit normal de l'agent
GENICIA++). Même fonctionnement que EGESYS\envoyer_mails_test.py.

Usage (PowerShell, dans le dossier G++) :
    python envoyer_mails_test.py --liste              liste les mails de test disponibles
    python envoyer_mails_test.py 1 6 34               envoie les tests 01, 06 et 34
    python envoyer_mails_test.py 34-39                envoie les tests 34 à 39
    python envoyer_mails_test.py --tous               envoie tous les tests, dans l'ordre
    python envoyer_mails_test.py --generer            régénère seulement les JSON (après modification du .md)
Options : --pause 20 (secondes entre deux envois, défaut 15), --destinataire autre@adresse.fr

Format d'un fichier (attendu par le flux) : {"destinataire": ..., "objet": "[G++] [TEST 05] ...", "corps": HTML}.
« G++ » dans l'objet est le filtre qui déclenche le flux de l'agent GENICIA++ ; « [TEST 05] » permet de retrouver
le test.

⚠️ Les mails envoyés passent dans le vrai circuit : ceux qui sont valides sont EXÉCUTÉS dans GENICIA++ (cheptel de
test 64233008 uniquement) : duplicatas de factures, création de l'espace adhérent (nouveau mot de passe envoyé à
l'adresse de la fiche). Les tests de factures sur de longues périodes prennent plusieurs minutes chacun.
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
from config_genicia import DRIVE  # noqa: E402

FICHIER_MD = Path(__file__).resolve().parent / "copilot" / "tests" / "mails_de_test.md"
DOSSIER_JSON = FICHIER_MD.parent / "mails_json"
TESTS_MAILS = DRIVE.parent / "TESTS_MAILS"       # OneDrive - Sogen\TESTS_MAILS (surveillé par le flux)
DESTINATAIRE = "thomas.gineste@sogen.coop"       # Boîte surveillée par le flux qui transmet les mails à l'agent
PREFIXE_OBJET = "[G++]"                           # Filtre du flux G++ : l'objet doit contenir « G++ »


# ---------------------------------------------------------------------------------------------------------------
# Lecture de mails_de_test.md
# ---------------------------------------------------------------------------------------------------------------

def lire_tests():
    """[{numero, titre, objet, corps (texte)}] dans l'ordre du fichier.
    Format G++ : « ## Test 05 » puis le mail cité (« > Objet : … », « > », « > texte… ») ; le titre vient du tableau
    « | 05 | Thème | Vérifie | » en tête du fichier."""
    texte = FICHIER_MD.read_text(encoding="utf-8")
    titres = {int(n): t.strip() for n, t in re.findall(r"^\| (\d+) \| ([^|]+) \|", texte, re.M)}
    tests = []
    for bloc in re.split(r"\n(?=## Test \d+)", texte)[1:]:
        entete = re.match(r"## Test (\d+)", bloc)
        lignes = [re.sub(r"^> ?", "", ligne) for ligne in bloc.splitlines() if ligne.startswith(">")]
        objet = re.match(r"Objet ?: ?(.+)", lignes[0]) if lignes else None
        if not (entete and objet):
            sys.exit(f"🛑 Bloc de test mal formé dans {FICHIER_MD.name} : {bloc[:80]!r}")
        numero = int(entete.group(1))
        tests.append({"numero": numero, "titre": titres.get(numero, ""), "objet": objet.group(1).strip(),
                      "corps": "\n".join(lignes[1:]).strip()})
    return tests


def corps_html(texte):
    """Texte du mail → HTML (le flux envoie un mail HTML : sans <br>, les retours à la ligne disparaîtraient)."""
    paragraphes = [p for p in texte.split("\n\n") if p.strip()]
    return "".join(f"<p>{'<br>'.join(html.escape(ligne, quote=False) for ligne in p.splitlines())}</p>"
                   for p in paragraphes)


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
            sys.exit(f"🛑 « {argument} » n'est pas un numéro de test (ex : 5, 34-39).")
    inconnus = sorted(set(numeros) - set(disponibles))
    if inconnus:
        sys.exit(f"🛑 Test(s) inexistant(s) : {inconnus}. Disponibles : {min(disponibles)} à {max(disponibles)}.")
    return list(dict.fromkeys(numeros))


def deposer(test, destinataire):
    """Dépose le JSON dans TESTS_MAILS d'un coup (écriture à côté puis renommage) : le flux ne voit jamais un fichier
    à moitié écrit. Nom unique (test_XX_gpp_ + heure) : renvoyer un même test redéclenche le flux, et les fichiers
    ne se confondent pas avec ceux d'EGESYS."""
    nom = f"test_{test['numero']:02d}_gpp_{time.strftime('%Y%m%d_%H%M%S')}.json"
    temporaire = TESTS_MAILS.parent / f".{nom}.tmp"   # Hors du dossier surveillé, même disque
    temporaire.write_text(json.dumps(contenu_json(test, destinataire), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporaire, TESTS_MAILS / nom)
    return nom


def main():
    parametres = argparse.ArgumentParser(description="Génère et envoie (via le OneDrive) les mails de test G++.")
    parametres.add_argument("tests", nargs="*", help="numéros des tests à envoyer (ex : 1 6 34 ou 34-39)")
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
            print(f"  {test['numero']:02d}  {test['titre']:<45} objet : {test['objet']}")
        if not (options.liste or options.generer):
            print("\nPréciser les tests à envoyer (ex : python envoyer_mails_test.py 1 6 34, 34-39 ou --tous).")
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
        print(f"  ✅ {numero:02d} {test['titre']} → {nom}")
        if position < len(numeros) and options.pause > 0:
            time.sleep(options.pause)
    print("Les réponses arriveront par mail ; le détail est dans le OneDrive G++ (completed/, error/, result/).")


if __name__ == "__main__":
    # line_buffering : chaque ligne s'affiche aussitôt (pas de « programme muet » pendant les pauses)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    main()
