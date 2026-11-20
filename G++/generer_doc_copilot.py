"""Génère la compétence de l'agent Copilot : copilot/genicia-modeles-json/SKILL.md

Source : CATALOGUE de ordres_genicia.py + copilot/exemples.md. À relancer après toute évolution des actions,
puis recharger le SKILL.md dans l'agent. Ne pas modifier SKILL.md à la main.

Usage : python generer_doc_copilot.py
"""
import json
import sys
from pathlib import Path

from ordres_genicia import CATALOGUE, PROFIL_PAR_DEFAUT

DOSSIER = Path(__file__).parent / "copilot"
SORTIE = DOSSIER / "genicia-modeles-json" / "SKILL.md"


def generer():
    lignes = ["---", "name: genicia-modeles-json",
              'description: "Modèles JSON, listes de valeurs et exemples des actions GENICIA++."', "---", "",
              "## Listes de valeurs autorisées", "",
              "Pour ces champs, recopier EXACTEMENT une valeur de la liste (majuscules, espaces et signes compris).",
              "Si le mail n'en parle pas : \"\". Si rien ne correspond à ce que dit le mail : \"\" et l'expliquer "
              "dans `incertitudes`.", ""]
    listes = {}
    for definition in CATALOGUE.values():
        listes.update(definition["listes"])
    for champ, valeurs in listes.items():
        lignes += [f"### `{champ}`", ""] + [f"- `{v}`" for v in valeurs] + [""]
    lignes += [f"Profil vide (\"\") : le profil `{PROFIL_PAR_DEFAUT}` est utilisé.", "",
               "## Actions GENICIA++ disponibles", ""]
    for action, definition in CATALOGUE.items():
        lignes += [f"### `{action}`", "", definition["description"], "",
                   "Champs obligatoires : " + ", ".join(" ou ".join(f"`{x}`" for x in (c if isinstance(c, tuple) else (c,)))
                                              for c in definition["obligatoires"]), "",
                   "Champs :", ""]
        lignes += ["- `justification` : extrait exact du mail qui justifie l'ordre"]
        lignes += [f"- `{champ}` : {texte}" for champ, texte in definition["champs"].items()]
        lignes += ["", "Modèle JSON (recopier toutes les clés, dans cet ordre) :", "", "```json",
                   json.dumps(definition["modele"], ensure_ascii=False, indent=2), "```", ""]
    lignes.append((DOSSIER / "exemples.md").read_text(encoding="utf-8").replace("# Exemples", "## Exemples", 1)
                  .replace("\n## Exemple ", "\n### Exemple "))
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text("\n".join(lignes), encoding="utf-8")
    return SORTIE


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    chemin = generer()
    print(f"Compétence générée : {chemin} ({len(chemin.read_text(encoding='utf-8'))} caractères)")
