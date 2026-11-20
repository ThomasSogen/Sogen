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
MAX_PERIODES = 24     # dates / périodes au plus dans une demande « telecharger_factures »
DEBUT_HISTORIQUE = date(2000, 1, 1)   # « Ses N dernières factures » sans date : bilan lu depuis cette date
MOTIF_DATE = re.compile(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})")

# Chaque action : description pour l'agent, modèle JSON exact, champs obligatoires, listes fermées.
# Tous les champs sont des textes ; "" = non précisé dans le mail.
CATALOGUE = {
    "telecharger_facture": {
        "libelle": "Duplicata de facture",
        "description": ("Récupère le duplicata PDF d'une facture d'un éleveur (Bilan éleveur > F5 DETAILLER > "
                        "F5 DUPLICATA). Lecture seule : rien n'est modifié dans GENICIA++."),
        "modele": {"action": "telecharger_facture", "justification": "", "cheptel": "", "nom_eleveur": "",
                   "date_facture": ""},
        "obligatoires": [("cheptel", "nom_eleveur"), "date_facture"],
        "listes": {},
        "champs": {
            "cheptel": ("N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). "
                    "« Code client » et « numéro d'élevage » désignent aussi le n° de cheptel"),
            "nom_eleveur": ("Nom de l'éleveur tel qu'écrit dans le mail, sinon \"\". Sans n° de cheptel, le programme "
                            "retrouve l'éleveur par ce nom dans GENICIA++ (un seul éleveur possible, sinon rien n'est fait)"),
            "date_facture": "Date de la facture, JJ/MM/AAAA",
        },
    },
    "telecharger_factures": {
        "libelle": "Duplicatas de factures",
        "description": ("Récupère le duplicata PDF de PLUSIEURS factures d'un éleveur : toutes celles de une ou "
                        "plusieurs dates précises et/ou périodes (ex : un mois, un trimestre, une année ; "
                        f"{MAX_FACTURES} factures maximum), ou les N dernières factures (« ses 3 dernières "
                        "factures »). Une date ou une période sans facture n'arrête pas la "
                        "demande : les factures trouvées sont envoyées et les manques expliqués. Lecture seule : rien "
                        "n'est modifié dans GENICIA++."),
        "modele": {"action": "telecharger_factures", "justification": "", "cheptel": "", "nom_eleveur": "",
                   "periodes": "", "nombre_dernieres": ""},
        "obligatoires": [("cheptel", "nom_eleveur"), ("periodes", "nombre_dernieres")],   # tuple : l'un OU l'autre
        "listes": {},
        "champs": {
            "cheptel": ("N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). "
                    "« Code client » et « numéro d'élevage » désignent aussi le n° de cheptel"),
            "nom_eleveur": ("Nom de l'éleveur tel qu'écrit dans le mail, sinon \"\". Sans n° de cheptel, le programme "
                            "retrouve l'éleveur par ce nom dans GENICIA++ (un seul éleveur possible, sinon rien n'est fait)"),
            "periodes": ("Dates et/ou périodes des factures demandées, séparées par « ; ». Une date précise : "
                         "JJ/MM/AAAA ; une période : JJ/MM/AAAA au JJ/MM/AAAA (premier et dernier jour inclus). "
                         "Ex : « la facture du 31 janvier et celles de mars 2026 » → "
                         "\"31/01/2026 ; 01/03/2026 au 31/03/2026\""),
            "nombre_dernieres": ("Nombre des dernières factures demandées, en chiffres (« ses 3 dernières factures » "
                                 "→ \"3\"), sinon \"\". Seules les plus récentes sont prises (parmi les dates de "
                                 "\"periodes\" si elles sont données, sinon parmi toutes les factures de l'éleveur)"),
        },
    },
    "generer_espace_adherent": {
        "libelle": "Création de l'espace adhérent web",
        "description": ("Ouvre les droits web de l'éleveur (profil choisi), génère un nouveau mot de passe, envoie "
                        "par mail à l'éleveur ses identifiants (adresse de sa fiche) et l'abonne aux factures par "
                        "mail sans pièce jointe. Modifie la fiche de l'éleveur."),
        "modele": {"action": "generer_espace_adherent", "justification": "", "cheptel": "", "nom_eleveur": "",
                   "profil": ""},
        "obligatoires": [("cheptel", "nom_eleveur")],
        "listes": {"profil": PROFILS_WEB},
        "champs": {
            "cheptel": ("N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). "
                    "« Code client » et « numéro d'élevage » désignent aussi le n° de cheptel"),
            "nom_eleveur": ("Nom de l'éleveur tel qu'écrit dans le mail, sinon \"\". Sans n° de cheptel, le programme "
                            "retrouve l'éleveur par ce nom dans GENICIA++ (un seul éleveur possible, sinon rien n'est fait)"),
            "profil": f"Profil web demandé (liste fermée) ; \"\" si le mail n'en parle pas → {PROFIL_PAR_DEFAUT}",
        },
    },
}


def factures_max_estimees(ordre):
    """Nombre de factures au plus attendu pour un ordre (sert au délai maximal d'exécution du veilleur) :
    1 pour une facture ; pour plusieurs : 2 par date précise et 2 par mois de chaque période (plafonné)."""
    if not isinstance(ordre, dict) or ordre.get("action") != "telecharger_factures":
        return 1 if isinstance(ordre, dict) and ordre.get("action") == "telecharger_facture" else 0
    nombre = str(ordre.get("nombre_dernieres", "")).strip()
    if nombre.isdigit() and int(nombre) > 0:
        return min(MAX_FACTURES, int(nombre))
    try:
        periodes = lire_periodes(ordre.get("periodes", ""))
    except ValueError:
        return MAX_FACTURES
    total = sum(2 * ((au.year - du.year) * 12 + au.month - du.month + 1) for du, au in periodes)
    return max(1, min(MAX_FACTURES, total))


# ---------------------------------------------------------------------------------------------------------------
# Dates et périodes de factures (« 31/01/2026 ; 01/03/2026 au 31/03/2026 »)
# ---------------------------------------------------------------------------------------------------------------

def lire_periodes(texte):
    """« 31/01/2026 ; 01/03/2026 au 31/03/2026 » → [(début, fin)] (dates, bornes incluses), dans l'ordre du texte.
    Une date seule = ce jour-là (début = fin) ; deux dates = une période. Séparateurs : « ; », « , » ou retour à
    la ligne. ValueError (message clair) si un morceau n'est ni une date ni une période valide."""
    morceaux = [m.strip() for m in re.split(r"[;,\n]", str(texte)) if m.strip()]
    if not morceaux:
        raise ValueError("aucune date ni période")
    periodes = []
    for morceau in morceaux:
        dates = []
        for jour, mois, annee in MOTIF_DATE.findall(morceau):
            try:
                dates.append(date(int(annee), int(mois), int(jour)))
            except ValueError:
                raise ValueError(f"« {morceau} » contient une date qui n'existe pas") from None
        if len(dates) not in (1, 2):
            raise ValueError(f"« {morceau} » n'est ni une date (JJ/MM/AAAA) ni une période (JJ/MM/AAAA au JJ/MM/AAAA)")
        if dates[0] > dates[-1]:
            raise ValueError(f"la période « {morceau} » commence après sa fin")
        if (dates[0], dates[-1]) not in periodes:
            periodes.append((dates[0], dates[-1]))
    if len(periodes) > MAX_PERIODES:
        raise ValueError(f"{len(periodes)} dates ou périodes (maximum {MAX_PERIODES})")
    return periodes


def texte_periodes(periodes):
    """Forme normalisée du champ « periodes » : « 31/01/2026 ; 01/03/2026 au 31/03/2026 »."""
    return " ; ".join(du.strftime("%d/%m/%Y") if du == au else f"{du:%d/%m/%Y} au {au:%d/%m/%Y}" for du, au in periodes)


def libelle_periode(du, au):
    """« le 31/01/2026 » ou « du 01/03/2026 au 31/03/2026 » (phrases du compte rendu)."""
    return f"le {du:%d/%m/%Y}" if du == au else f"du {du:%d/%m/%Y} au {au:%d/%m/%Y}"


def libelle_dernieres(nombre):
    """« la dernière facture » / « les 3 dernières factures »."""
    return "la dernière facture" if int(nombre) == 1 else f"les {int(nombre)} dernières factures"


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
    if ordre.get("action") == "telecharger_factures" and "periodes" not in ordre \
            and {"periode_du", "periode_au"} <= set(ordre):      # ancien format (une seule période) : converti
        ordre = dict(ordre)
        du, au = str(ordre.pop("periode_du")).strip(), str(ordre.pop("periode_au")).strip()
        ordre["periodes"] = f"{du} au {au}" if du and au else ""
    if ordre.get("action") == "telecharger_factures" and "nombre_dernieres" not in ordre:
        ordre = dict(ordre, nombre_dernieres="")       # agent d'avant cette option : aucune limite

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
        choix = champ if isinstance(champ, tuple) else (champ,)     # tuple : au moins un des champs rempli
        if not any(propre[c] for c in choix):
            erreurs.append(f"le champ obligatoire '{' ou '.join(choix)}' n'est pas précisé dans le mail")
    if propre.get("nombre_dernieres"):
        nombre = propre["nombre_dernieres"]
        if not nombre.isdigit() or not 1 <= int(nombre) <= MAX_FACTURES:
            erreurs.append(f"nombre de dernières factures invalide : '{nombre}' (entier de 1 à {MAX_FACTURES})")
        else:
            propre["nombre_dernieres"] = str(int(nombre))
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
    if propre.get("periodes"):
        try:
            periodes = lire_periodes(propre["periodes"])
            futures = [libelle_periode(du, au) for du, au in periodes if du > date.today()]
            if futures:
                erreurs.append(f"dates de factures invalides : dates dans le futur ({' ; '.join(futures)})")
            else:
                propre["periodes"] = texte_periodes(periodes)
        except ValueError as erreur:
            erreurs.append(f"dates de factures invalides : {erreur}")
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
