"""Valide un JSON d'ordres produit par l'agent Copilot avant de le donner à script_egesys.py (aucune connexion).

Usage : python valider_ordres.py reponse_copilot.json
- Accepte le JSON seul ou la réponse complète de Copilot collée telle quelle (bloc ```json ... ```).
- Les pièces jointes citées doivent être enregistrées dans le même dossier que le fichier.
- Si tout est correct, écrit <fichier>_valide.json, prêt pour : python script_egesys.py <fichier>_valide.json
"""
import json
import os
import re
import sys
from extraire_ordres import generer_schema, finaliser_ordre, valider_ordre, CHAMPS_FACULTATIFS


def lire_reponse(chemin):
    with open(chemin, encoding='utf-8') as fichier:
        texte = fichier.read()
    bloc = re.search(r'```(?:json)?\s*(.*?)```', texte, re.S)
    try:
        donnees = json.loads(bloc.group(1) if bloc else texte)
    except json.JSONDecodeError as erreur:
        sys.exit(f"🛑 ERREUR : JSON illisible ({erreur}).")
    if isinstance(donnees, dict) and "ordres" in donnees:
        return donnees["ordres"], donnees.get("incertitudes", []), donnees.get("resume", "")
    return (donnees if isinstance(donnees, list) else [donnees]), [], ""

def lire_champ_brut(chemin, cle):
    """Valeur texte de la clé `cle` du JSON de l'agent, lue même si le JSON est cassé
    (recherche dans le texte brut). "" si absente."""
    try:
        with open(chemin, encoding='utf-8') as fichier:
            texte = fichier.read()
    except OSError:
        return ""
    trouve = re.search(r'"' + re.escape(cle) + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', texte)
    if not trouve:
        return ""
    try:
        return json.loads(f'"{trouve.group(1)}"').strip()
    except json.JSONDecodeError:
        return trouve.group(1).strip()


def lire_id_message(chemin):
    """Identifiant du mail d'origine ("id_message", placé par l'agent juste après "resume"), pour y répondre."""
    return lire_champ_brut(chemin, "id_message")


def lire_expediteur(chemin):
    """Expéditeur du mail d'origine ("expediteur", placé par l'agent juste après "id_message")."""
    return lire_champ_brut(chemin, "expediteur")


def verifier_structure(ordre, definitions):
    """Compare l'ordre au modèle de son action : clés exactes et valeurs des listes fermées."""
    definition = definitions.get(ordre.get("action"))
    if not definition:
        return [f"action inconnue ou désactivée : '{ordre.get('action')}'"]
    erreurs = []
    proprietes = definition["properties"]
    for champ, defaut in CHAMPS_FACULTATIFS.items():  # Ex : activite_actuelle absente = "" (non précisée)
        if champ in proprietes:
            ordre.setdefault(champ, defaut)
        elif ordre.get(champ, defaut) == defaut:
            ordre.pop(champ, None)  # Ajouté vide à une action qui ne cherche pas de client (factures) : sans effet
    if set(ordre) != set(proprietes):
        erreurs.append(f"clés attendues {sorted(proprietes)}, reçues {sorted(ordre)}")
    for nom, propriete in proprietes.items():
        valeur = ordre.get(nom)
        if propriete.get("type") == "object":
            if not isinstance(valeur, dict) or set(valeur) != set(propriete["properties"]):
                erreurs.append(f"'{nom}' doit contenir exactement {sorted(propriete['properties'])}")
                continue
            for champ, detail in propriete["properties"].items():
                if "enum" in detail and valeur[champ] not in detail["enum"]:
                    erreurs.append(f"'{champ}' = '{valeur[champ]}' n'est pas une valeur autorisée")
                elif not isinstance(valeur[champ], str):
                    erreurs.append(f"'{champ}' doit être une chaîne de caractères")
        elif not isinstance(valeur, str):
            erreurs.append(f"'{nom}' doit être une chaîne de caractères")
    return erreurs


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    chemin = sys.argv[1]
    dossier = os.path.dirname(os.path.abspath(chemin))
    ordres, incertitudes, resume = lire_reponse(chemin)

    definitions = {d["properties"]["action"]["const"]: d for d in generer_schema()["$defs"].values()}
    pieces_jointes = {nom: os.path.join(dossier, nom) for nom in os.listdir(dossier)
                      if os.path.isfile(os.path.join(dossier, nom))}

    if resume:
        print(f"📨 {resume}")
    erreurs_totales = 0
    for numero, ordre in enumerate(ordres, start=1):
        erreurs = verifier_structure(ordre, definitions)
        if not erreurs:
            finaliser_ordre(ordre, pieces_jointes, incertitudes)
            erreur = valider_ordre(ordre)
            if erreur:
                erreurs.append(erreur)
        print(f"\n  {numero}. {ordre.get('action')} — client '{ordre.get('nom_client', '')}' {ordre.get('code_client', '')}")
        print(f"     « {ordre.get('justification', '')} »")
        for erreur in erreurs:
            print(f"     🛑 {erreur}")
        if any((ordre.get("modèle_de_reglement") or {}).get(champ) for champ in ("iban", "bic")):
            print("     ⚠️  Coordonnées bancaires reçues par mail : à confirmer auprès du client avant exécution.")
        erreurs_totales += len(erreurs)
    for incertitude in incertitudes:
        print(f"\n⚠️  {incertitude}")

    if erreurs_totales or incertitudes or not ordres:
        sys.exit("\n🛑 Ordres NON validés : corrigez le JSON (ou traitez le mail à la main).")
    sortie = os.path.splitext(chemin)[0] + "_valide.json"
    with open(sortie, 'w', encoding='utf-8') as fichier:
        json.dump(ordres, fichier, ensure_ascii=False, indent=2)
    print(f"\n✅ {len(ordres)} ordre(s) valide(s). Après relecture : python script_egesys.py {sortie}")


if __name__ == '__main__':
    # Windows : console / redirection pas en UTF-8 par défaut, les emojis feraient planter le script
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    main()
