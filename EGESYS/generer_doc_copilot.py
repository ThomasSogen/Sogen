"""Génère la compétence de l'agent Copilot (copilot/egesys-modeles-json/SKILL.md) depuis le catalogue et les mappings.

Usage : python generer_doc_copilot.py
À relancer après chaque modification de CATALOGUE_ACTIONS, des MAPPING_* ou de copilot/exemples_egesys.md,
puis recharger le SKILL.md dans Copilot.
Copilot refuse (« violation IAR ») un nom, une description ou une introduction trop « métier » (testé le 02/11/2026) :
l'en-tête reste volontairement neutre et minimal.
"""
import json
import os
import sys
import re
from extraire_ordres import (generer_schema, LISTES_FERMEES, CHAMPS_OBLIGATOIRES, VALEURS_AUTOMATIQUES)

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'copilot')
NOM_COMPETENCE = "egesys-modeles-json"
DESCRIPTION_COMPETENCE = "Modèles JSON, listes de valeurs et exemples EGESYS."


def _modele_vide(definition):
    """Ordre type de l'action, tous les champs à "" (seule l'action est remplie)."""
    ordre = {}
    for nom, propriete in definition["properties"].items():
        if propriete.get("type") == "object":
            ordre[nom] = {champ: "" for champ in propriete["properties"]}
        else:
            ordre[nom] = propriete.get("const", "")
    return ordre


def _champs(definition):
    """(champ, emplacement, détail) de chaque champ de l'action, hors "action"."""
    for nom, propriete in definition["properties"].items():
        if nom == "action":
            continue
        if propriete.get("type") == "object":
            for champ, detail in propriete["properties"].items():
                yield champ, nom, detail
        else:
            yield nom, "racine", propriete


def generer_glossaire(schema):
    """Un seul tableau pour tous les champs (un tableau par action rendait le fichier deux fois plus long)."""
    lignes = {}
    for definition in schema["$defs"].values():
        for champ, emplacement, detail in _champs(definition):
            description = re.sub(r"\s*\(une étiquette.*?\)", "", detail.get('description', ''))  # Propre à l'API
            valeurs = "voir « Listes de valeurs autorisées »" if "enum" in detail else "texte libre"
            lignes.setdefault(champ, f"| `{champ}` | {emplacement} | {description} | {valeurs} |")
    return "\n".join(["## Description des champs", "",
                      "| Champ | Emplacement | Description | Valeurs |", "|---|---|---|---|",
                      *lignes.values(), ""])


def generer_actions(schema):
    parties = [
        "## Actions EGESYS disponibles",
        "",
        "Chaque ordre du JSON correspond à UNE action ci-dessous. Recopier le modèle de l'action, puis remplir",
        "uniquement les champs que le mail précise. Un champ non précisé reste \"\" (pour une modification : \"\" = inchangé).",
        "Ne jamais ajouter, renommer ou retirer une clé.",
        "",
    ]
    for definition in schema["$defs"].values():
        action = definition["properties"]["action"]["const"]
        description = definition["properties"]["action"]["description"]
        obligatoires = CHAMPS_OBLIGATOIRES.get(action, [])
        parties += [
            f"### `{action}`",
            "",
            f"{description} Champs obligatoires : "
            f"{', '.join(' ou '.join(f'`{x}`' for x in (c if isinstance(c, tuple) else (c,))) for c in obligatoires) if obligatoires else 'client uniquement (`nom_client` ou `code_client`)'}.",
            "",
            "```json",
            json.dumps(_modele_vide(definition), ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    return "\n".join(parties)


def generer_listes():
    parties = [
        "## Listes de valeurs autorisées",
        "",
        "Pour ces champs, recopier EXACTEMENT une valeur de la liste (majuscules, espaces et accents compris).",
        "Si aucune valeur ne correspond à ce que dit le mail : laisser \"\" et l'expliquer dans `incertitudes`.",
        "",
    ]
    for champ, mapping in LISTES_FERMEES.items():
        parties += [f"### `{champ}`", ""] + [f"- `{valeur}`" for valeur in mapping if valeur] + [""]
    automatiques = ", ".join(f"`{c}`" for c in VALEURS_AUTOMATIQUES)
    parties += [
        "### Champs à ne jamais remplir",
        "",
        f"{automatiques} : ajouté(s) automatiquement par le validateur, ne pas l'écrire dans le JSON.",
        "",
    ]
    return "\n".join(parties)


def ecrire_competence(dossier, corps, nom=NOM_COMPETENCE, description=DESCRIPTION_COMPETENCE):
    contenu = "\n".join([
        "---",
        f"name: {nom}",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "---",
        "",
        *corps,
    ])
    os.makedirs(dossier, exist_ok=True)
    with open(os.path.join(dossier, 'SKILL.md'), 'w', encoding='utf-8') as fichier:
        fichier.write(contenu)
    print(f"📝 {os.path.relpath(dossier, os.path.dirname(DOSSIER))}/SKILL.md généré ({len(contenu)} caractères).")


def main():
    schema = generer_schema()
    with open(os.path.join(DOSSIER, 'exemples_egesys.md'), encoding='utf-8') as fichier:
        exemples = fichier.read().lstrip('\ufeff')
    corps = [generer_listes(), generer_actions(schema), generer_glossaire(schema)]
    ecrire_competence(os.path.join(DOSSIER, NOM_COMPETENCE), corps + [exemples])


if __name__ == '__main__':
    # Windows : console / redirection pas en UTF-8 par défaut, les emojis feraient planter le script
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    main()
