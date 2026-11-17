"""Ordres GENICIA++ : catalogue des actions, lecture et validation du JSON de l'agent Copilot (sans GENICIA++).

Le JSON de l'agent :
  {"resume": "...", "id_message": "...", "expediteur": "...",
   "ordres": [{"action": "telecharger_facture", "cheptel": "...", ...}, ...],
   "incertitudes": [...]}

Usage : python ordres_genicia.py reponse.json
  -> affiche le contrôle ; si tout est correct, écrit reponse_valide.json (ordres prêts pour executer_ordres.py)

Ce fichier est la RÉFÉRENCE des actions : la validation, l'exécution, la réponse au mail et la compétence
de l'agent (generer_doc_copilot.py) se basent toutes sur CATALOGUE.
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

PROFILS_WEB = ["ELWEB1 STANDARD", "PRWEB2 STANDART+", "PRWEB3 TECHNIQUE", "PRWEB4 TECHNIQUE+", "PRWEBA BASE"]
PROFIL_PAR_DEFAUT = "ELWEB1 STANDARD"
MAX_FACTURES = 30     # factures au plus par demande « telecharger_factures » (même limite que dans action_facture.py)

# Chaque action : description pour l'agent, modèle JSON exact, champs obligatoires, listes fermées.
# Tous les champs sont des textes ; "" = non précisé dans le mail.
CATALOGUE = {
    "telecharger_facture": {
        "libelle": "Duplicata de facture",
        "description": ("Récupère le duplicata PDF d'une facture d'un éleveur (Bilan éleveur > F5 DETAILLER > "
                        "F5 DUPLICATA). Lecture seule : rien n'est modifié dans GENICIA++."),
        "modele": {"action": "telecharger_facture", "justification": "", "cheptel": "", "nom_eleveur": "",
                   "date_facture": ""},
        "obligatoires": ["cheptel", "date_facture"],
        "listes": {},
        "champs": {
            "cheptel": ("N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). "
                    "« Code client » et « numéro d'élevage » désignent aussi le n° de cheptel"),
            "nom_eleveur": "Nom de l'éleveur tel qu'écrit dans le mail (information seulement), sinon \"\"",
            "date_facture": "Date de la facture, JJ/MM/AAAA",
        },
    },
    "telecharger_factures": {
        "libelle": "Duplicatas de factures",
        "description": ("Récupère le duplicata PDF de TOUTES les factures d'un éleveur sur une période (ex : un mois, "
                        f"un trimestre, une année ; {MAX_FACTURES} factures maximum). Lecture seule : rien n'est "
                        "modifié dans GENICIA++."),
        "modele": {"action": "telecharger_factures", "justification": "", "cheptel": "", "nom_eleveur": "",
                   "periode_du": "", "periode_au": ""},
        "obligatoires": ["cheptel", "periode_du", "periode_au"],
        "listes": {},
        "champs": {
            "cheptel": ("N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). "
                    "« Code client » et « numéro d'élevage » désignent aussi le n° de cheptel"),
            "nom_eleveur": "Nom de l'éleveur tel qu'écrit dans le mail (information seulement), sinon \"\"",
            "periode_du": "Premier jour de la période des factures demandées, JJ/MM/AAAA (ex : mars 2026 → 01/03/2026)",
            "periode_au": "Dernier jour de la période des factures demandées, JJ/MM/AAAA (ex : mars 2026 → 31/03/2026)",
        },
    },
    "generer_espace_adherent": {
        "libelle": "Création de l'espace adhérent web",
        "description": ("Ouvre les droits web de l'éleveur (profil choisi), génère un nouveau mot de passe, envoie "
                        "par mail à l'éleveur ses identifiants (adresse de sa fiche) et l'abonne aux factures par "
                        "mail sans pièce jointe. Modifie la fiche de l'éleveur."),
        "modele": {"action": "generer_espace_adherent", "justification": "", "cheptel": "", "nom_eleveur": "",
                   "profil": ""},
        "obligatoires": ["cheptel"],
        "listes": {"profil": PROFILS_WEB},
        "champs": {
            "cheptel": ("N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). "
                    "« Code client » et « numéro d'élevage » désignent aussi le n° de cheptel"),
            "nom_eleveur": "Nom de l'éleveur tel qu'écrit dans le mail (information seulement), sinon \"\"",
            "profil": f"Profil web demandé (liste fermée) ; \"\" si le mail n'en parle pas → {PROFIL_PAR_DEFAUT}",
        },
    },
}


def factures_max_estimees(ordre):
    """Nombre de factures au plus attendu pour un ordre (sert au délai maximal d'exécution du veilleur) :
    1 pour une facture, 2 par mois de la période (plafonné à MAX_FACTURES) pour plusieurs factures."""
    if not isinstance(ordre, dict) or ordre.get("action") != "telecharger_factures":
        return 1 if isinstance(ordre, dict) and ordre.get("action") == "telecharger_facture" else 0
    du, au = lire_date(ordre.get("periode_du", "")), lire_date(ordre.get("periode_au", ""))
    if not du or not au:
        return MAX_FACTURES
    mois = (au.year - du.year) * 12 + au.month - du.month + 1
    return max(1, min(MAX_FACTURES, 2 * mois))


def libelle_action(action):
    return CATALOGUE.get(action, {}).get("libelle") or str(action).replace("_", " ").capitalize()


# ---------------------------------------------------------------------------------------------------------------
# Lecture du JSON de l'agent
# ---------------------------------------------------------------------------------------------------------------

class JsonIllisible(ValueError):
    pass


def lire_reponse(chemin):
    """(ordres, incertitudes, resume). Accepte la réponse collée telle quelle (bloc ```json ... ```)."""
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    bloc = re.search(r"```(?:json)?\s*(.*?)```", texte, re.S)
    try:
        donnees = json.loads(bloc.group(1) if bloc else texte)
    except json.JSONDecodeError as erreur:
        raise JsonIllisible(f"JSON illisible ({erreur})") from None
    if not isinstance(donnees, dict) or "ordres" not in donnees:
        raise JsonIllisible("le JSON ne contient pas de clé \"ordres\"")
    ordres = donnees["ordres"] if isinstance(donnees["ordres"], list) else [donnees["ordres"]]
    incertitudes = donnees.get("incertitudes") or []
    if not isinstance(incertitudes, list):
        incertitudes = [incertitudes]
    return ordres, [str(i) for i in incertitudes if str(i).strip()], str(donnees.get("resume", ""))


def lire_champ_brut(chemin, cle):
    """Valeur texte de `cle`, lue même si le JSON est cassé (recherche dans le texte). "" si absente."""
    try:
        texte = Path(chemin).read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    trouve = re.search(r'"' + re.escape(cle) + r'"\s*:\s*"((?:[^"\\]|\\.)*)"', texte)
    if not trouve:
        return ""
    try:
        return json.loads(f'"{trouve.group(1)}"').strip()
    except json.JSONDecodeError:
        return trouve.group(1).strip()


# ---------------------------------------------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------------------------------------------

def normaliser_cheptel(valeur):
    """'FR 64 284 002' -> '64284002'. Renvoie "" si ce n'est pas un n° de cheptel."""
    texte = re.sub(r"[\s.\-]", "", str(valeur)).upper()
    texte = re.sub(r"^FR", "", texte)
    return texte if re.fullmatch(r"(\d{2}|2A|2B)\d{6}", texte) else ""


def lire_date(valeur):
    """'28/02/2026' (ou 28-02-2026, 28.02.2026) -> date ; None si invalide."""
    texte = re.sub(r"[-.]", "/", str(valeur).strip())
    try:
        return datetime.strptime(texte, "%d/%m/%Y").date()
    except ValueError:
        return None


def valider_ordre(ordre):
    """Contrôle un ordre ; renvoie (ordre normalisé, liste d'erreurs)."""
    if not isinstance(ordre, dict):
        return ordre, ["l'ordre n'est pas un objet JSON"]
    definition = CATALOGUE.get(ordre.get("action"))
    if not definition:
        return ordre, [f"action inconnue : '{ordre.get('action')}'"]

    erreurs = []
    attendues = set(definition["modele"])
    if set(ordre) != attendues:
        manquantes, en_trop = sorted(attendues - set(ordre)), sorted(set(ordre) - attendues)
        if manquantes:
            erreurs.append(f"clés manquantes : {manquantes}")
        if en_trop:
            erreurs.append(f"clés en trop : {en_trop}")
    for cle, valeur in ordre.items():
        if not isinstance(valeur, str):
            erreurs.append(f"'{cle}' doit être un texte")
    if erreurs:
        return ordre, erreurs

    propre = {cle: ordre[cle].strip() for cle in definition["modele"]}
    for champ in definition["obligatoires"]:
        if not propre[champ]:
            erreurs.append(f"le champ obligatoire '{champ}' n'est pas précisé dans le mail")
    for champ, valeurs in definition["listes"].items():
        if propre[champ] and propre[champ] not in valeurs:
            erreurs.append(f"'{champ}' = '{propre[champ]}' n'est pas une valeur autorisée ({', '.join(valeurs)})")

    if propre["cheptel"]:
        cheptel = normaliser_cheptel(propre["cheptel"])
        if cheptel:
            propre["cheptel"] = cheptel
        else:
            erreurs.append(f"n° de cheptel invalide : '{propre['cheptel']}' (8 caractères attendus)")
    if propre.get("date_facture"):
        jour = lire_date(propre["date_facture"])
        if jour is None:
            erreurs.append(f"date de facture invalide : '{propre['date_facture']}' (JJ/MM/AAAA attendu)")
        elif jour > date.today():
            erreurs.append(f"date de facture dans le futur : '{propre['date_facture']}'")
        else:
            propre["date_facture"] = jour.strftime("%d/%m/%Y")
    if propre.get("periode_du") and propre.get("periode_au"):
        bornes = {champ: lire_date(propre[champ]) for champ in ("periode_du", "periode_au")}
        for champ, jour in bornes.items():
            if jour is None:
                erreurs.append(f"date de période invalide : '{propre[champ]}' (JJ/MM/AAAA attendu)")
            else:
                propre[champ] = jour.strftime("%d/%m/%Y")
        if None not in bornes.values():
            if bornes["periode_du"] > bornes["periode_au"]:
                erreurs.append(f"période inversée : du '{propre['periode_du']}' au '{propre['periode_au']}'")
            elif bornes["periode_du"] > date.today():
                erreurs.append(f"période dans le futur : du '{propre['periode_du']}' au '{propre['periode_au']}'")
    if "profil" in propre and not propre["profil"]:
        propre["profil"] = PROFIL_PAR_DEFAUT
    return propre, erreurs


def valider(chemin):
    """Contrôle complet d'une réponse de l'agent.

    Renvoie un dict : ok, resume, incertitudes, ordres (normalisés), controles (une entrée par ordre :
    numero, action, cheptel, erreurs), erreur_generale.
    """
    resultat = {"ok": False, "resume": "", "incertitudes": [], "ordres": [], "controles": [], "erreur_generale": ""}
    try:
        ordres, incertitudes, resume = lire_reponse(chemin)
    except (JsonIllisible, OSError) as erreur:
        resultat["erreur_generale"] = str(erreur)
        return resultat
    resultat.update(resume=resume, incertitudes=incertitudes)
    for numero, ordre in enumerate(ordres, start=1):
        propre, erreurs = valider_ordre(ordre)
        resultat["ordres"].append(propre)
        resultat["controles"].append({"numero": numero,
                                      "action": propre.get("action", "") if isinstance(propre, dict) else "",
                                      "cheptel": propre.get("cheptel", "") if isinstance(propre, dict) else "",
                                      "erreurs": erreurs})
    if not ordres and not incertitudes:
        resultat["erreur_generale"] = "aucune demande GENICIA++ trouvée dans le mail"
    resultat["ok"] = bool(ordres) and not incertitudes and not any(c["erreurs"] for c in resultat["controles"])
    return resultat


def texte_validation(resultat):
    """Résumé lisible du contrôle (rapport technique)."""
    lignes = [f"Demande : {resultat['resume']}"] if resultat["resume"] else []
    if resultat["erreur_generale"]:
        lignes.append(f"🛑 {resultat['erreur_generale']}")
    for controle, ordre in zip(resultat["controles"], resultat["ordres"]):
        lignes.append(f"  {controle['numero']}. {controle['action']} — cheptel {controle['cheptel'] or '?'}")
        if isinstance(ordre, dict) and ordre.get("justification"):
            lignes.append(f"     « {ordre['justification']} »")
        lignes += [f"     🛑 {erreur}" for erreur in controle["erreurs"]]
    lignes += [f"⚠️  Incertitude : {i}" for i in resultat["incertitudes"]]
    lignes.append("✅ Ordres valides." if resultat["ok"] else "🛑 Ordres NON validés : rien ne sera exécuté.")
    return "\n".join(lignes)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    controle = valider(sys.argv[1])
    print(texte_validation(controle))
    if not controle["ok"]:
        sys.exit(1)
    sortie = Path(sys.argv[1]).with_name(Path(sys.argv[1]).stem + "_valide.json")
    sortie.write_text(json.dumps(controle["ordres"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {sortie}")
