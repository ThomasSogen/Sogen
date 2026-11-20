"""Réponse en français clair (objet + corps HTML mis en forme pour Outlook), envoyée par mail à l'utilisateur à la fin de
chaque traitement (fichier JSON du dossier result/).

Même présentation que le compte rendu du projet EGESYS, adaptée à GENICIA++.
Ne contient aucun nom de fichier JSON, aucun mot de passe ni jargon technique : pour chaque demande du mail, ce qui a été
fait dans GENICIA++, ou pourquoi ce n'a pas été fait, et ce qu'il reste à faire.

⚠ L'objet commence par « GENICIA++ : » et ne doit JAMAIS contenir « G++ » : c'est le filtre du flux Power Automate n°1
  (une réponse revenue dans la boîte surveillée relancerait le traitement).
"""
import re
from datetime import datetime
from html import escape

from ordres_genicia import libelle_action, libelle_dernieres, libelle_periode, lire_periodes

PREFIXE_OBJET = "GENICIA++ : "
PIED_DE_PAGE = "Message généré automatiquement par l'automate GENICIA++ de SOGEN."   # repéré par l'agent (boucle)

LIBELLES_CHAMPS = {"cheptel": "N° de cheptel", "nom_eleveur": "Éleveur", "date_facture": "Date de la facture",
                   "periodes": "Dates des factures", "nombre_dernieres": "Nombre de dernières factures",
                   "profil": "Profil web"}
ACTIONS_FACTURES = ("telecharger_facture", "telecharger_factures")

# Mise en forme HTML du mail (styles en ligne et tableaux : seule forme bien rendue par Outlook)
POLICE = "font-family:'Segoe UI',Arial,sans-serif;font-size:14px;line-height:1.5;color:#222222;"
COULEURS = {  # ton : (couleur du texte et des bordures, couleur de fond)
    "succes": ("#1e7e34", "#e8f5e9"),
    "attention": ("#9a5b00", "#fff6e0"),
    "erreur": ("#b3261e", "#fdecea"),
    "info": ("#0b5394", "#e8f0fe"),
}

RAISON_INCERTITUDE = ("Le mail comporte un point à clarifier (voir « Points à clarifier » ci-dessous). Par sécurité, "
                      "aucune demande de ce mail n'est exécutée tant que ce point n'est pas levé.")
RAISON_AUTRE_ORDRE = ("Non exécutée car une autre demande du même mail a été refusée : les demandes d'un même "
                      "mail sont traitées ensemble.")
RAISON_INTERROMPU = ("Le traitement a été interrompu (ordinateur ou programme arrêté pendant l'exécution). Impossible "
                     "de savoir si cette demande a été faite : vérifiez dans GENICIA++.")
RAISON_FACTURE_INTROUVABLE = ("Aucune facture n'existe à cette date pour cet éleveur : rien n'a été récupéré pour "
                              "éviter une erreur.")
RAISON_PERIODE_SANS_FACTURE = ("Aucune facture n'existe aux dates demandées pour cet éleveur : rien n'a été "
                               "récupéré.")
MOTIF_FACTURES_MANQUANTES = ("Les duplicatas trouvés sont joints à ce mail. Pour les dates marquées « Non trouvée », "
                             "aucune facture n'existe dans GENICIA++ : la raison est indiquée.")


# ---------------------------------------------------------------------------------------------------------------
# Traduction des messages techniques
# ---------------------------------------------------------------------------------------------------------------

def nettoyer(texte):
    """Retire les emojis et préfixes techniques (« 🛑 ERREUR : »...)."""
    texte = re.sub(r'[🛑⚠️✅❌📁🖱️📤👉⏳🎉]|️', '', str(texte))
    texte = re.sub(r'^\s*(ERREUR|ATTENTION)\s*:\s*', '', texte.strip())
    return re.sub(r'\s+', ' ', texte).strip()


def libelle_champ(champ):
    if " ou " in champ:          # champ obligatoire au choix : « cheptel ou nom_eleveur »
        return " ou ".join(libelle_champ(c) for c in champ.split(" ou "))
    return LIBELLES_CHAMPS.get(champ, champ.replace("_", " "))


def traduire_incertitude(texte):
    return nettoyer(texte)


def traduire_erreur_validation(texte):
    texte = nettoyer(texte)
    if texte.startswith("action inconnue"):
        return "Cette demande ne fait pas partie des opérations que l'automate sait réaliser dans GENICIA++."
    obligatoire = re.match(r"le champ obligatoire '(.+?)' n'est pas précisé", texte)
    if obligatoire:
        return f"Information manquante dans le mail ({libelle_champ(obligatoire.group(1)).lower()})."
    cheptel = re.match(r"n° de cheptel invalide : '(.*?)'", texte)
    if cheptel:
        return f"Le n° de cheptel « {cheptel.group(1)} » n'est pas valide (8 caractères attendus, ex : 64284002)."
    date = re.match(r"date de facture invalide : '(.*?)'", texte)
    if date:
        return f"La date de facture « {date.group(1)} » n'est pas une date valide (attendu : JJ/MM/AAAA)."
    futur = re.match(r"date de facture dans le futur : '(.*?)'", texte)
    if futur:
        return f"La date de facture « {futur.group(1)} » est dans le futur."
    dates = re.match(r"dates de factures invalides : (.*)$", texte)
    if dates:
        aide = (" (attendu : JJ/MM/AAAA pour une date, JJ/MM/AAAA au JJ/MM/AAAA pour une période)"
                if "n'est ni une date" in texte or "n'existe pas" in texte else "")
        return f"Les dates de factures demandées sont incorrectes : {dates.group(1)}{aide}."
    valeur = re.match(r"'(.+?)' = '(.*?)' n'est pas une valeur autorisée", texte)
    if valeur:
        return f"La valeur « {valeur.group(2)} » n'existe pas dans GENICIA++ pour « {libelle_champ(valeur.group(1))} »."
    if texte.startswith(("clés", "'")) or "doit être un texte" in texte or "n'est pas un objet" in texte:
        return "La demande préparée par l'assistant est mal formée (erreur technique) : le mail doit être retraité."
    return texte[0].upper() + texte[1:] if texte else "Demande refusée par le contrôle avant exécution."


def traduire_erreur_execution(detail):
    """Erreur pendant l'exécution GENICIA++ → (phrase compréhensible, détail technique court)."""
    brut = nettoyer(detail)
    if re.search(r"Connexion à GENICIA\+\+ impossible|Identifiants absents", detail):
        explication = "Le programme n'a pas pu ouvrir GENICIA++ ou s'y connecter : rien n'a été fait."
    elif "Délai d'exécution dépassé" in detail:
        explication = "GENICIA++ ne répondait plus : l'exécution a été arrêtée par sécurité."
    elif re.search(r"Plusieurs éleveurs|Aucun éleveur trouvé|Champ du nom introuvable|N° de cheptel illisible",
                   detail):
        explication = ("L'éleveur n'a pas pu être identifié par son nom dans GENICIA++ (aucun ou plusieurs éleveurs "
                       "possibles) : rien n'a été fait. Indiquez son n° de cheptel.")
    elif re.search(r"Cheptel \S+ absent des résultats|Éleveur \S+ : l'écran suivant", detail):
        explication = "L'éleveur n'a pas été trouvé dans GENICIA++ avec ce n° de cheptel."
    elif "Boîte de dialogue ouverte" in detail or "boîte de dialogue s'est ouverte" in detail:
        explication = ("Une fenêtre inattendue s'est ouverte dans GENICIA++ : l'exécution a été arrêtée par sécurité, "
                       "sans rien valider.")
    elif "Mauvaise facture ouverte" in detail:
        explication = ("GENICIA++ a ouvert une autre facture que celle attendue : rien n'a été envoyé, arrêt par "
                       "sécurité.")
    elif "Trop de factures" in detail:
        explication = ("Il y a trop de factures sur cette période pour une seule demande : rien n'a été récupéré. "
                       "Renvoyez la demande avec une période plus courte.")
    elif "n'est pas pris en compte" in detail:
        explication = ("GENICIA++ n'a pas réagi à un clic malgré plusieurs essais : l'exécution a été arrêtée par "
                       "sécurité, sans rien valider.")
    elif "premier plan" in detail:
        explication = ("GENICIA++ n'a pas pu être mis au premier plan (poste utilisé ou session verrouillée ?) : "
                       "l'exécution a été arrêtée par sécurité.")
    else:
        explication = "Arrêt de sécurité pendant l'exécution dans GENICIA++."
    return explication, brut


def factures_possibles(detail):
    """« … Factures de la période : 31/01/26 (n° 450001, 120,00 €) ; … » → candidates lisibles."""
    liste_brute = re.search(r"Factures de la période : (.*)$", str(detail))
    if not liste_brute:
        return []
    candidates = []
    for morceau in liste_brute.group(1).split(" ; "):
        facture = re.match(r"\s*(\S+) \(n° (\S+), (.+?)\)\s*\.?$", morceau)
        candidates.append(f"N° {facture.group(2)} | Date {facture.group(1)} | TTC {facture.group(3)}"
                          if facture else nettoyer(morceau))
    return candidates


# ---------------------------------------------------------------------------------------------------------------
# Construction du compte rendu
# ---------------------------------------------------------------------------------------------------------------

def eleveur_lisible(ordre):
    cheptel, nom = ordre.get("cheptel", ""), ordre.get("nom_eleveur", "")
    if cheptel and nom:
        return f"cheptel {cheptel} ({nom.upper()})"
    if cheptel:
        return f"cheptel {cheptel}"
    return f"éleveur {nom.upper()} (cheptel non précisé)" if nom else "éleveur non précisé"


def dates_lisibles(periodes, nombre_dernieres=""):
    """« 31/01/2026 ; 01/03/2026 au 31/03/2026 » → « le 31/01/2026 ; du 01/03/2026 au 31/03/2026 » (texte brut si
    illisible). Avec un nombre de dernières factures : « les 3 dernières factures (…) »."""
    try:
        dates = " ; ".join(libelle_periode(du, au) for du, au in lire_periodes(periodes)) if str(periodes or "").strip() else ""
    except ValueError:
        dates = str(periodes or "").strip()
    nombre = str(nombre_dernieres or "").strip()
    if nombre.isdigit() and int(nombre) > 0:
        return libelle_dernieres(nombre) + (f" ({dates})" if dates else "")
    return dates


def valeurs_demandees(ordre):
    if ordre.get("action") == "telecharger_facture":
        return [f"Date de la facture : « {ordre.get('date_facture') or 'non précisée'} »"]
    if ordre.get("action") == "telecharger_factures":
        return [f"Factures demandées : « {dates_lisibles(ordre.get('periodes', ''), ordre.get('nombre_dernieres', '')) or 'non précisées'} »"]
    if ordre.get("action") == "generer_espace_adherent":
        return [f"Profil web : « {ordre.get('profil') or 'ELWEB1 STANDARD'} »",
                "Identifiants envoyés par mail à l'éleveur (adresse de sa fiche)",
                "Abonnement factures par mail sans pièce jointe"]
    return []


# ---------------------------------------------------------------------------------------------------------------
# Mise en forme HTML
# ---------------------------------------------------------------------------------------------------------------

def e(texte):
    """Texte échappé pour le HTML."""
    return escape(str(texte), quote=False)


def paragraphe(contenu, style=""):
    return f'<p style="{POLICE}margin:4px 0;{style}">{contenu}</p>'


def liste(elements, marge=18, numerotee=False):
    balise = "ol" if numerotee else "ul"
    items = "".join(f'<li style="{POLICE}margin:2px 0;">{element}</li>' for element in elements)
    return f'<{balise} style="margin:2px 0 6px {marge}px;padding-left:18px;">{items}</{balise}>'


def encadre(contenu, ton):
    couleur, fond = COULEURS[ton]
    return ('<table role="presentation" width="100%" cellpadding="12" cellspacing="0" border="0" '
            'style="border-collapse:collapse;margin:12px 0;">'
            f'<tr><td style="{POLICE}background-color:{fond};border-left:5px solid {couleur};">{contenu}</td></tr>'
            '</table>')


def titre_section(texte, ton, nombre=None):
    couleur = COULEURS[ton][0]
    suffixe = f" ({nombre})" if nombre else ""
    return (f'<p style="{POLICE}font-size:16px;font-weight:bold;color:{couleur};border-bottom:2px solid {couleur};'
            f'padding-bottom:3px;margin:22px 0 8px 0;">{e(texte.upper())}{suffixe}</p>')


def valeur_en_gras(texte):
    """« Profil web : « ELWEB1 STANDARD » » → libellé normal, valeur en gras."""
    libelle, separateur, valeur = str(texte).partition(" : ")
    if not separateur:
        return e(texte)
    return f"{e(libelle)} : <b>{e(valeur)}</b>"


def raison(texte, technique="", candidates=()):
    return {"texte": texte, "technique": technique, "candidates": list(candidates)}


def bloc_demande(index, action, eleveur, libelle, valeurs, motif, ton):
    couleur = COULEURS[ton][0]
    morceaux = [paragraphe(f'<span style="color:{couleur};font-weight:bold;">{index}.</span> '
                           f'<b>{e(action)}</b> &mdash; {e(eleveur)}', "margin-top:12px;")]
    if valeurs:
        morceaux.append(paragraphe(f"<u>{e(libelle)}</u> :", "margin-left:18px;"))
        morceaux.append(liste([valeur_en_gras(v) for v in valeurs], marge=36))
    if motif and ton == "succes":
        morceaux.append(paragraphe(f"<i>{e(motif['texte'])}</i>", "margin-left:18px;color:#555555;"))
    elif motif:
        morceaux.append(paragraphe(f'<b style="color:{couleur};">Raison :</b> {e(motif["texte"])}',
                                   "margin-left:18px;"))
        if motif["candidates"]:
            titre = "Détail par date" if motif["texte"] == RAISON_PERIODE_SANS_FACTURE else "Factures possibles"
            morceaux.append(paragraphe(f"<u>{titre}</u> :", "margin-left:36px;"))
            morceaux.append(liste([e(c) for c in motif["candidates"]], marge=54))
        if motif["technique"]:
            morceaux.append(paragraphe(f"<i>Détail technique : {e(motif['technique'])}</i>",
                                       "margin-left:18px;font-size:12px;color:#777777;"))
    return "".join(morceaux)


def avis_espaces_adherents(resultats):
    """Encadrés signalant à l'utilisateur les espaces adhérents web vérifiés lors d'une récupération de facture(s) :
    créé automatiquement (Droits était à « Non »), ou vérification impossible. Rien si l'espace existait déjà."""
    avis = []
    for r in resultats:
        espace = r.get("espace_adherent") or {}
        cheptel = f"cheptel {r.get('cheptel', '')}"
        if espace.get("statut") == "cree":
            avis.append(encadre(
                f"&#9432; <b>Espace adhérent web créé</b> pour le {e(cheptel)} ({e(espace.get('eleveur', ''))}) : "
                f"ses droits web étaient à « Non ». Profil <b>{e(espace.get('profil', ''))}</b>, identifiants envoyés "
                f"par mail à <b>{e(espace.get('destinataire') or 'l’adresse de la fiche')}</b>. L'éleveur en est "
                "aussi informé dans le mail qui lui envoie ses factures.", "info"))
        elif espace.get("statut") == "erreur":
            avis.append(encadre(
                f"&#9888; <b>Espace adhérent web non vérifié</b> pour le {e(cheptel)} : vérifiez dans GENICIA++ "
                "(Administratif &gt; Eleveur &gt; F14 COMMUNIC.) si ses droits web sont ouverts. "
                f"<i>Détail technique : {e(nettoyer(espace.get('detail', '')))}</i>", "attention"))
    return avis


def rediger(code, controle, resultats_execution=None):
    """Réponse au mail : {"objet": ..., "corps": HTML}.
    code : EXECUTE, ERREUR_EXECUTION, REFUSE_VALIDATION, INTERROMPU ;
    controle : résultat de ordres_genicia.valider() (ordres, controles, incertitudes, resume, erreur_generale) ;
    resultats_execution : résultats ordre par ordre d'executer_ordres.py (s'il y a eu exécution)."""
    ordres = [ordre for ordre in controle.get("ordres", []) if isinstance(ordre, dict)]
    erreurs_validation = {c["numero"]: c["erreurs"] for c in controle.get("controles", []) if c.get("erreurs")}
    resultats = {r.get("numero"): r for r in (resultats_execution or [])}
    incertitudes = [traduire_incertitude(texte) for texte in controle.get("incertitudes", [])]
    resume = controle.get("resume", "")

    executees, non_executees, a_verifier = [], [], []
    incompletes = 0       # demandes de factures exécutées, mais avec des dates sans facture
    for numero, ordre in enumerate(ordres, start=1):
        entete = (libelle_action(ordre.get('action')), eleveur_lisible(ordre))
        demande = valeurs_demandees(ordre)
        resultat = resultats.get(numero, {})

        if code == "INTERROMPU":
            a_verifier.append((*entete, demande, raison(RAISON_INTERROMPU)))
        elif resultat.get("resultat") == "Réussite":
            faits = resultat.get("modification", "").splitlines() or demande
            if resultat.get("manquantes"):
                motif = raison(MOTIF_FACTURES_MANQUANTES)
                incompletes += 1
            elif ordre.get("action") in ACTIONS_FACTURES and resultat.get("fichiers"):
                motif = raison("Les duplicatas PDF sont joints à ce mail." if len(resultat["fichiers"]) > 1
                               else "Le duplicata PDF est joint à ce mail.")
            elif not resultat.get("modification") and resultat.get("detail"):
                motif = raison(nettoyer(resultat["detail"]))     # pas de liste détaillée : la phrase la remplace
            else:
                motif = None
            executees.append((*entete, faits, motif))
        elif resultat:  # Exécution tentée, ou arrêtée avant cet ordre
            detail = resultat.get("detail", "")
            if detail.startswith("Non exécuté") or not detail:
                motif = raison("Pas tentée : l'exécution s'est arrêtée sur une demande précédente.")
            elif detail.startswith("Aucune facture au"):
                motif = raison(RAISON_FACTURE_INTROUVABLE, candidates=factures_possibles(detail))
            elif detail.startswith(("Aucune facture du", "Aucune facture pour les dates")):
                # « Aucune facture pour les dates demandées : le X : raison ; du … au … : raison »
                details = detail.split(" : ", 1)[1].split(" ; ") if "dates demandées : " in detail else []
                motif = raison(RAISON_PERIODE_SANS_FACTURE, candidates=details)
            else:
                motif = raison(*traduire_erreur_execution(detail))
            non_executees.append((*entete, demande, motif))
        else:  # Pas d'exécution : bloqué avant (contrôle de la demande)
            if erreurs_validation.get(numero):
                texte = " ".join(traduire_erreur_validation(erreur) for erreur in erreurs_validation[numero])
            elif incertitudes:
                texte = RAISON_INCERTITUDE
            else:
                texte = RAISON_AUTRE_ORDRE
            non_executees.append((*entete, demande, raison(texte)))

    # --- Bilan ---
    total = len(ordres)
    if a_verifier:
        bilan = "le traitement a été interrompu : vérifiez dans GENICIA++ ce qui a réellement été fait."
        ton = "erreur"
    elif not ordres:
        bilan = "rien n'a été fait dans GENICIA++ : aucune demande exploitable n'a été trouvée dans le mail."
        ton = "attention"
    elif len(executees) == total and incompletes:
        bilan = ("les factures trouvées sont jointes, mais certaines dates demandées n'ont pas de facture "
                 "(voir « Non trouvée » ci-dessous).")
        ton = "attention"
    elif len(executees) == total:
        bilan = f"tout a été fait ({total} demande{'s' if total > 1 else ''} exécutée{'s' if total > 1 else ''})."
        ton = "succes"
    elif not executees:
        bilan = "rien n'a été fait dans GENICIA++."
        ton = "erreur" if code == "ERREUR_EXECUTION" else "attention"
    else:
        bilan, ton = f"{len(executees)} demande(s) exécutée(s) sur {total}.", "attention"
    icone = {"succes": "&#10004;", "attention": "&#9888;", "erreur": "&#10006;"}[ton]

    # --- En-tête ---
    html = [f'<div style="{POLICE}max-width:760px;">',
            paragraphe("Résultat du traitement de votre demande GENICIA++",
                       f"font-size:20px;font-weight:bold;color:{COULEURS['info'][0]};margin:0;"),
            paragraphe(f"<i>Traité le {datetime.now():%d/%m/%Y à %H:%M}</i>", "font-size:12px;color:#777777;")]
    if resume and resume.strip() != "*":
        html.append(paragraphe(f"<b>Demande reçue :</b> <i>{e(resume.strip())}</i>", "margin-top:10px;"))
    html.append(encadre(f'<span style="font-size:16px;color:{COULEURS[ton][0]};">{icone} '
                        f'<b>En résumé :</b> {e(bilan)}</span>', ton))
    html += avis_espaces_adherents(resultats.values())

    # --- Demandes ---
    for titre, elements, libelle, ton_section in (
            ("Demandes exécutées", executees, "Ce qui a été fait", "succes"),
            ("Demandes non exécutées", non_executees, "Ce qui était demandé", "erreur"),
            ("Demandes à vérifier dans GENICIA++", a_verifier, "Ce qui était demandé", "attention")):
        if elements:
            html.append(titre_section(titre, ton_section, len(elements)))
            html += [bloc_demande(index, action, eleveur, libelle, valeurs, motif, ton_section)
                     for index, (action, eleveur, valeurs, motif) in enumerate(elements, start=1)]

    erreur_lecture = controle.get("erreur_generale", "")
    if incertitudes:
        html.append(titre_section("Points à clarifier", "attention"))
        html.append(encadre(liste([e(texte) for texte in incertitudes], marge=0), "attention"))
    elif not ordres and erreur_lecture and "aucune demande" not in erreur_lecture:
        html.append(encadre("La réponse de l'assistant n'a pas pu être lue (erreur technique) : "
                            "le mail doit être retraité.", "erreur"))

    # --- Que faire ? ---
    motifs = [motif for *_, motif in non_executees]
    conseils = []
    if incertitudes:
        conseils.append("<b>Répondez à ce mail</b> en précisant les points à clarifier ci-dessus pour que la demande "
                        "soit relancée, ou faites l'opération directement dans GENICIA++.")
    if any(motif["texte"] == RAISON_FACTURE_INTROUVABLE
           or (motif["candidates"] and motif["texte"] != RAISON_PERIODE_SANS_FACTURE) for motif in motifs):
        conseils.append("<b>Renvoyez la demande</b> avec la date exacte de la facture (voir les factures possibles).")
    if any(motif["texte"] == RAISON_PERIODE_SANS_FACTURE for motif in motifs) or incompletes:
        conseils.append("<b>Vérifiez les dates sans facture</b> dans le bilan de l'éleveur (GENICIA++) puis, si "
                        "besoin, renvoyez la demande avec les bonnes dates.")
    if any(motif["technique"] or "Pas tentée" in motif["texte"] for motif in motifs) or a_verifier:
        conseils.append("<b>Vérifiez dans GENICIA++</b> : les demandes non exécutées peuvent être refaites à la main "
                        "ou renvoyées.")
    if non_executees and not conseils:
        conseils.append("<b>Corrigez la demande et renvoyez-la</b>, ou faites l'opération directement dans GENICIA++.")
    if conseils:
        html.append(titre_section("Que faire ?", "info"))
        html.append(liste(conseils, numerotee=True))

    html.append(paragraphe(f"<i>{e(PIED_DE_PAGE)}</i>",
                           "margin-top:24px;padding-top:6px;border-top:1px solid #dddddd;font-size:11px;"
                           "color:#999999;"))
    html.append("</div>")
    corps = "\n".join(html)

    # --- Objet du mail de réponse, selon le résultat ---
    if a_verifier:
        objet = "Traitement interrompu, à vérifier dans GENICIA++"
    elif ordres and len(executees) == total and incompletes:
        objet = "Demande traitée, factures manquantes"
    elif ordres and len(executees) == total:
        objet = "Demande traitée"
    elif executees:
        objet = "Demande partiellement traitée"
    elif motifs and all(motif["texte"] in (RAISON_FACTURE_INTROUVABLE, RAISON_PERIODE_SANS_FACTURE)
                        for motif in motifs):
        objet = "Facture à préciser"
    elif incertitudes:
        objet = "Précisions nécessaires"
    elif code == "ERREUR_EXECUTION" or (not ordres and erreur_lecture and "aucune demande" not in erreur_lecture):
        objet = "Erreur lors du traitement"
    elif code == "REFUSE_VALIDATION" and ordres:
        objet = "Précisions nécessaires"
    else:
        objet = "Demande non traitée"
    return {"objet": PREFIXE_OBJET + objet, "corps": corps}


# ---------------------------------------------------------------------------------------------------------------
# Mail au client (l'éleveur) avec ses factures en pièces jointes
# ---------------------------------------------------------------------------------------------------------------
# L'utilisateur se contente de transférer le mail du client : le flux Power Automate n°2 envoie en plus ce mail à
# l'adresse lue sur la fiche de l'éleveur (jamais à une adresse tirée du mail : pas de facture envoyée à un inconnu),
# avec en pièces jointes les PDF de la liste « pdf ».
# ⚠ L'objet ne doit contenir ni « G++ » (filtre du flux n°1) ni commencer par « GENICIA++ : » (l'agent ignore ces
#   mails) : si le client répond et que l'utilisateur transfère sa réponse, elle doit être traitée normalement.

OBJET_CLIENT = "SOGEN : "
SIGNATURE_CLIENT = "Le service administratif de SOGEN"
MAIL_CLIENT_VIDE = {"mail": "", "objet": "", "corps": ""}
PHRASE_ESPACE_CREE = ("Par ailleurs, nous avons ouvert votre espace adhérent sur notre site internet. Vos "
                      "identifiants de connexion vous sont envoyés dans un mail séparé.")


def mail_client(resultats, pdf):
    """{mail, objet, corps} du mail à envoyer à l'éleveur avec ses factures, ou des valeurs vides (rien à envoyer) :
    aucune facture récupérée, adresse mail absente de la fiche, ou factures de plusieurs éleveurs dans le même mail."""
    ordres = [r for r in (resultats or []) if r.get("action") in ACTIONS_FACTURES
              and r.get("resultat") == "Réussite" and r.get("fichiers")]
    if not ordres or not pdf or len({r.get("cheptel") for r in ordres}) != 1:
        return dict(MAIL_CLIENT_VIDE)
    adresse = next((r["mail_client"] for r in ordres if r.get("mail_client")), "")
    if not adresse:
        return dict(MAIL_CLIENT_VIDE)

    factures = []     # [(n°, date)] de toutes les factures récupérées, sans doublon
    for r in ordres:
        for f in r.get("factures") or [{"numero_facture": r.get("numero_facture"), "date_facture": r.get("date_facture")}]:
            facture = (f.get("numero_facture") or "?", f.get("date_facture") or "?")
            if facture not in factures:
                factures.append(facture)

    cheptel = ordres[0].get("cheptel", "")
    periode = ordres[0] if len(ordres) == 1 and ordres[0].get("action") == "telecharger_factures" else None
    manquantes = [m for r in ordres for m in (r.get("manquantes") or []) if not m.get("nombre_demande")]
    # « Ses 20 dernières factures » alors que l'éleveur n'en a que 13 : on le dit simplement
    incomplets = [m for r in ordres for m in (r.get("manquantes") or []) if m.get("nombre_demande")]
    if periode:      # une demande « toutes les factures de ces dates / périodes »
        quand = dates_lisibles(periode.get("periodes", ""), periode.get("nombre_dernieres", "")).replace(" ; ", ", ")
        if len(factures) == 1:
            objet = f"{OBJET_CLIENT}duplicata de votre facture du {factures[0][1]}"
            suite = "Vous trouverez la facture correspondante en pièce jointe de ce mail :"
        else:
            objet = f"{OBJET_CLIENT}duplicatas de vos factures"
            suite = f"Vous trouverez les {len(factures)} factures correspondantes en pièces jointes de ce mail :"
        demande = (f"Vous nous avez demandé les duplicatas de vos factures ({e(quand)}, cheptel n° {e(cheptel)}). "
                   + suite)
    elif len(factures) == 1:
        objet = f"{OBJET_CLIENT}duplicata de votre facture du {factures[0][1]}"
        demande = (f"Vous nous avez demandé le duplicata de votre facture du {e(factures[0][1])} "
                   f"(cheptel n° {e(cheptel)}). Vous le trouverez en pièce jointe de ce mail :")
    else:
        objet = f"{OBJET_CLIENT}duplicatas de vos factures"
        demande = (f"Vous nous avez demandé les duplicatas de {len(factures)} factures (cheptel n° {e(cheptel)}). "
                   "Vous les trouverez en pièces jointes de ce mail :")
    corps = (f'<div style="{POLICE}">'
             + paragraphe("Bonjour,", "margin-bottom:10px;")
             + paragraphe(demande)
             + liste([e(f"Facture n° {numero} du {date}") for numero, date in factures])
             + (paragraphe("Nous n'avons trouvé aucune facture "
                           + e(", ".join(m["periode"] for m in manquantes)) + ".", "margin-top:10px;")
                if manquantes else "")
             + "".join(paragraphe(f"Vous nous aviez demandé {e(m['periode'])} : nous n'en avons trouvé que "
                                  f"{len(factures)}.", "margin-top:10px;") for m in incomplets[:1])
             + (paragraphe(PHRASE_ESPACE_CREE, "margin-top:10px;")
                if any((r.get("espace_adherent") or {}).get("statut") == "cree" for r in ordres) else "")
             + paragraphe(f"Cordialement,<br>{e(SIGNATURE_CLIENT)}", "margin-top:10px;")
             + "</div>")
    return {"mail": adresse, "objet": objet, "corps": corps}
