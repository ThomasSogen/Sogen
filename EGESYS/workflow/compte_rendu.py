"""Réponse en français clair (objet + corps HTML mis en forme pour Outlook), envoyée par mail à l'utilisateur à la fin de chaque traitement
(fichier JSON du dossier result/).

Ne contient aucun nom de fichier JSON ni jargon technique : pour chaque demande du mail, ce qui a été fait dans EGESYS,
ou pourquoi ce n'a pas été fait, et ce qu'il reste à faire.
"""
import re
from datetime import datetime
from html import escape

from script_egesys import lignes_modification, LIBELLES_NOTE

LIBELLES_ACTIONS = {
    "modifier_civilite_client": "Modification de la civilité",
    "modifier_nom_client": "Modification du nom",
    "modifier_prenom_client": "Modification du prénom",
    "modifier_responsable_client": "Modification du responsable",
    "modifier_adresse_client": "Modification de l'adresse",
    "modifier_mail_client": "Modification de l'adresse mail",
    "modifier_mail_comptable_client": "Modification de l'adresse mail comptable",
    "modifier_telephone_fixe_client": "Modification du téléphone fixe",
    "modifier_telephone_portable_client": "Modification du téléphone portable",
    "modifier_activite_client": "Modification de l'activité",
    "ajouter_modèle_de_reglement_client": "Nouveau modèle de règlement",
    "modifier_modèle_de_reglement_client": "Correction d'un modèle de règlement",
    "ajouter_document_client": "Ajout d'un document",
    "modifier_document_client": "Modification d'un document",
    "supprimer_document_client": "Suppression d'un document",
    "ajouter_note_client": "Ajout d'une note",
    "modifier_note_client": "Modification d'une note",
    "supprimer_note_client": "Suppression d'une note",
    "telecharger_facture_client": "Duplicata de facture",
    "telecharger_factures_client": "Duplicatas de factures",
}
LIBELLES_FACTURE = {"numero_facture": "Numéro de facture", "date_realisation": "Date de la facture",
                    "date_etat": "Date de validation", "montant": "Montant TTC"}

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
RAISON_BANQUE = ("Coordonnées bancaires reçues par mail : par sécurité (risque de fraude au RIB), elles ne sont jamais "
                 "saisies automatiquement. Elles doivent être confirmées auprès du client par un autre moyen "
                 "(téléphone, courrier signé...).")
RAISON_BANQUE_AUTRES = ("Non exécutée car ce mail contient aussi des coordonnées bancaires à confirmer : les demandes "
                        "d'un même mail sont traitées ensemble.")
RAISON_INTERROMPU = ("Le traitement a été interrompu (ordinateur ou programme arrêté pendant l'exécution). Impossible "
                     "de savoir si cette demande a été enregistrée : vérifiez la fiche du client dans EGESYS.")


# ---------------------------------------------------------------------------------------------------------------
# Traduction des messages techniques
# ---------------------------------------------------------------------------------------------------------------

def nettoyer(texte):
    """Retire les emojis et préfixes techniques (« 🛑 ERREUR : »...)."""
    texte = re.sub(r'[🛑⚠️✅❌📁🖱️📤👉⏳🎉]|️', '', str(texte))
    texte = re.sub(r'^\s*(ERREUR( DE NAVIGATION)?|ÉCHEC D\'ÉCRITURE|ATTENTION)\s*:\s*', '', texte.strip())
    return re.sub(r'\s+', ' ', texte).strip()


def libelle_champ(champ):
    return LIBELLES_NOTE.get(champ, LIBELLES_FACTURE.get(champ, champ.replace("_", " ")))


def libelle_action(action):
    return LIBELLES_ACTIONS.get(action, str(action).replace("_", " ").capitalize())


def traduire_incertitude(texte):
    texte = nettoyer(texte)
    obligatoire = re.match(r"(\S+) : le champ obligatoire '(.+?)' n'est pas précisé dans le mail\.?", texte)
    if obligatoire:
        return (f"{libelle_action(obligatoire.group(1))} : information manquante dans le mail "
                f"({libelle_champ(obligatoire.group(2))}).")
    client = re.match(r"(\S+) : client non identifié", texte)
    if client:
        return f"{libelle_action(client.group(1))} : le mail ne permet pas de savoir de quel client il s'agit."
    piece = re.match(r"Pièce jointe '(.+?)' introuvable dans le mail", texte)
    if piece:
        return f"La pièce jointe « {piece.group(1)} » n'a pas été reçue avec le mail."
    return texte


def traduire_erreur_validation(texte):
    texte = nettoyer(texte)
    if texte.startswith("action inconnue ou désactivée"):
        return "Cette demande ne fait pas partie des opérations que l'automate sait réaliser dans EGESYS."
    valeur = re.match(r"'(.+?)' = '(.*?)' n'est pas une valeur autorisée", texte)
    if valeur:
        return f"La valeur « {valeur.group(2)} » n'existe pas dans EGESYS pour « {libelle_champ(valeur.group(1))} »."
    if "clés attendues" in texte or "doit contenir exactement" in texte or "chaîne de caractères" in texte:
        return "La demande préparée par l'assistant est mal formée (erreur technique) : le mail doit être retraité."
    return texte[0].upper() + texte[1:] if texte else "Demande refusée par le contrôle avant exécution."


def traduire_erreur_execution(detail):
    """Erreur pendant l'exécution EGESYS → (phrase compréhensible, détail technique court)."""
    brut = " | ".join(nettoyer(morceau) for morceau in str(detail).split(" | ") if nettoyer(morceau))
    if "ÉCHEC D'ÉCRITURE" in detail:
        explication = ("Après l'enregistrement, EGESYS n'affichait pas la valeur attendue : l'exécution a été arrêtée "
                       "par sécurité.")
    elif "NAVIGATION" in detail:
        explication = ("EGESYS n'a pas affiché la page attendue (client introuvable ou fiche différente ?) : "
                       "l'exécution a été arrêtée par sécurité.")
    elif "introuvable sur le disque" in detail:
        explication = "La pièce jointe à enregistrer n'a pas été trouvée."
    elif re.search(r"session|expir|connexion|identifiant", detail, re.I):
        explication = "La connexion à EGESYS a échoué ou a été perdue."
    else:
        explication = "Arrêt de sécurité pendant l'exécution dans EGESYS."
    return explication, brut


def erreurs_par_ordre(sortie_validation):
    """Lit la sortie du validateur : erreurs propres à chaque ordre (n° → [messages]) et incertitudes générales."""
    par_ordre, incertitudes, numero = {}, [], None
    for ligne in sortie_validation.splitlines():
        entete = re.match(r'\s{2}(\d+)\. ', ligne)
        if entete:
            numero = int(entete.group(1))
        elif ligne.startswith('     ') and '🛑' in ligne and numero:
            par_ordre.setdefault(numero, []).append(ligne)
        elif ligne.startswith('⚠️'):
            incertitudes.append(ligne)
    return par_ordre, incertitudes


# ---------------------------------------------------------------------------------------------------------------
# Construction du compte rendu
# ---------------------------------------------------------------------------------------------------------------

def client_lisible(ordre):
    nom, code = ordre.get("nom_client", ""), ordre.get("code_client", "")
    if nom and code:
        return f"client {nom.upper()} (code {code})"
    if nom or code:
        return f"client {(nom or code).upper()}"
    numero = (ordre.get("facture") or {}).get("numero_facture", "")
    return f"facture n° {numero}" if numero else "client non précisé"


def valeurs_demandees(ordre):
    if ordre.get("action") == "telecharger_facture_client":
        criteres = [f"{libelle_champ(champ)} : « {valeur} »" for champ, valeur in (ordre.get("facture") or {}).items()
                    if str(valeur).strip()]
        return criteres or ["Aucun critère précis : la facture validée la plus récente."]
    if ordre.get("action") == "telecharger_factures_client":
        periode = ordre.get("factures") or {}
        return [f"Toutes les factures validées du « {periode.get('periode_du', '?')} » au « {periode.get('periode_au', '?')} »"]
    try:
        return lignes_modification(ordre, {})
    except (AttributeError, TypeError):
        return []


def contient_banque(ordre):
    return any((ordre.get("modèle_de_reglement") or {}).get(champ) for champ in ("iban", "bic"))


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
    """« Prénom : « Thomas » » → libellé normal, valeur en gras."""
    libelle, separateur, valeur = str(texte).partition(" : ")
    if not separateur:
        return e(texte)
    return f"{e(libelle)} : <b>{e(valeur)}</b>"


def raison(texte, technique="", candidates=()):
    return {"texte": texte, "technique": technique, "candidates": list(candidates)}


def bloc_demande(index, action, client, libelle, valeurs, motif, ton):
    couleur = COULEURS[ton][0]
    morceaux = [paragraphe(f'<span style="color:{couleur};font-weight:bold;">{index}.</span> '
                           f'<b>{e(action)}</b> &mdash; {e(client)}', "margin-top:12px;")]
    if valeurs:
        morceaux.append(paragraphe(f"<u>{e(libelle)}</u> :", "margin-left:18px;"))
        morceaux.append(liste([valeur_en_gras(v) for v in valeurs], marge=36))
    if motif and ton == "succes":
        morceaux.append(paragraphe(f"<i>{e(motif['texte'])}</i>", "margin-left:18px;color:#555555;"))
    elif motif:
        morceaux.append(paragraphe(f'<b style="color:{couleur};">Raison :</b> {e(motif["texte"])}',
                                   "margin-left:18px;"))
        if motif["candidates"]:
            morceaux.append(paragraphe("<u>Factures possibles</u> :", "margin-left:36px;"))
            morceaux.append(liste([e(c) for c in motif["candidates"]], marge=54))
        if motif["technique"]:
            morceaux.append(paragraphe(f"<i>Détail technique : {e(motif['technique'])}</i>",
                                       "margin-left:18px;font-size:12px;color:#777777;"))
    return "".join(morceaux)


def rediger(code, ordres, incertitudes_agent, sortie_validation="", resultats_execution=None, fichiers=(),
            resume=""):
    """Réponse au mail : {"objet": ..., "corps": HTML}. ordres : ordres tels qu'envoyés par l'agent ;
    resultats_execution : résultats ordre par ordre de script_egesys.py (s'il y a eu exécution) ;
    fichiers : PDF récupérés."""
    ordres = [ordre for ordre in ordres if isinstance(ordre, dict)]
    resultats = {r.get("numero"): r for r in (resultats_execution or [])}
    erreurs_validation, incertitudes_validateur = erreurs_par_ordre(sortie_validation)
    incertitudes = [traduire_incertitude(texte) for texte in (incertitudes_validateur or incertitudes_agent)]

    executees, non_executees, a_verifier = [], [], []
    for numero, ordre in enumerate(ordres, start=1):
        entete = (libelle_action(ordre.get('action')), client_lisible(ordre))
        demande = valeurs_demandees(ordre)
        resultat = resultats.get(numero, {})

        if code == "INTERROMPU":
            a_verifier.append((*entete, demande, raison(RAISON_INTERROMPU)))
        elif resultat.get("resultat") == "Réussite":
            faits = resultat.get("modification", "").splitlines() or demande
            if ordre.get("action") == "telecharger_facture_client" and fichiers and not resultat.get("modification"):
                faits = [f"Duplicata PDF récupéré : {nom}" for nom in fichiers]
            detail = nettoyer(resultat.get("detail", ""))
            executees.append((*entete, faits, raison(detail) if detail else None))
        elif resultat.get("resultat") == "Erreur" and resultat.get("detail", "").startswith("Modification faite"):
            faits = resultat.get("modification", "").splitlines() or demande
            executees.append((*entete, faits,
                              raison("Attention : la note de suivi n'a pas pu être ajoutée sur la fiche.")))
        elif resultat:  # Exécution tentée ou arrêtée avant cet ordre
            detail = resultat.get("detail", "")
            if "Arrêt sur un ordre précédent" in detail:
                motif = raison("Pas tentée : l'exécution s'est arrêtée sur une demande précédente.")
            elif "Par sécurité, aucune" in detail or "correspondent aux critères" in detail or "AUCUNE" in detail:
                # Chaque candidate : « - N° … | Date … | TTC … », candidates séparées elles aussi par « | »
                candidates = [nettoyer(c) for c in re.findall(r'- (N°.*?)(?= \| - N°|$)', detail)]
                if ordre.get("action") != "telecharger_factures_client":
                    texte = ("Aucune facture ou plusieurs factures correspondent aux critères du mail : rien n'a "
                             "été récupéré pour éviter une erreur.")
                elif "clients différents" in detail:
                    texte = ("Les factures trouvées appartiennent à plusieurs clients : rien n'a été récupéré pour "
                             "éviter une erreur. Précisez le code client.")
                elif "maximum" in detail:
                    texte = ("Trop de factures sur cette période (30 au maximum par demande) : rien n'a été "
                             "récupéré. Réduisez la période.")
                else:
                    texte = "Aucune facture validée n'a été trouvée pour ce client sur cette période."
                motif = raison(texte, candidates=candidates)
            else:
                motif = raison(*traduire_erreur_execution(detail))
            non_executees.append((*entete, demande, motif))
        else:  # Pas d'exécution : bloqué avant (validation, coordonnées bancaires)
            if erreurs_validation.get(numero):
                texte = " ".join(traduire_erreur_validation(erreur) for erreur in erreurs_validation[numero])
            elif code == "A_VERIFIER_BANQUE":
                texte = RAISON_BANQUE if contient_banque(ordre) else RAISON_BANQUE_AUTRES
            elif incertitudes:
                texte = RAISON_INCERTITUDE
            else:
                texte = ("Non exécutée car une autre demande du même mail a été refusée : les demandes d'un même "
                         "mail sont traitées ensemble.")
            non_executees.append((*entete, demande, raison(texte)))

    # --- Bilan ---
    total = len(ordres)
    if a_verifier:
        bilan = "le traitement a été interrompu : vérifiez dans EGESYS ce qui a réellement été enregistré."
        ton = "erreur"
    elif not ordres:
        bilan = "aucune modification n'a été faite dans EGESYS : aucune demande exploitable n'a été trouvée dans le mail."
        ton = "attention"
    elif len(executees) == total:
        bilan = f"tout a été fait ({total} demande{'s' if total > 1 else ''} exécutée{'s' if total > 1 else ''})."
        ton = "succes"
    elif not executees:
        bilan = "aucune modification n'a été faite dans EGESYS."
        ton = "erreur" if code == "ERREUR_EXECUTION" else "attention"
    else:
        bilan, ton = f"{len(executees)} demande(s) exécutée(s) sur {total}.", "attention"
    icone = {"succes": "&#10004;", "attention": "&#9888;", "erreur": "&#10006;"}[ton]

    # --- En-tête ---
    html = [f'<div style="{POLICE}max-width:760px;">',
            paragraphe("Résultat du traitement de votre demande EGESYS",
                       f"font-size:20px;font-weight:bold;color:{COULEURS['info'][0]};margin:0;"),
            paragraphe(f"<i>Traité le {datetime.now():%d/%m/%Y à %H:%M}</i>", "font-size:12px;color:#777777;")]
    if resume and resume.strip() != "*":
        html.append(paragraphe(f"<b>Demande reçue :</b> <i>{e(resume.strip())}</i>", "margin-top:10px;"))
    html.append(encadre(f'<span style="font-size:16px;color:{COULEURS[ton][0]};">{icone} '
                        f'<b>En résumé :</b> {e(bilan)}</span>', ton))

    # --- Demandes ---
    for titre, elements, libelle, ton_section in (
            ("Demandes exécutées", executees, "Ce qui a été fait", "succes"),
            ("Demandes non exécutées", non_executees, "Ce qui était demandé", "erreur"),
            ("Demandes à vérifier dans EGESYS", a_verifier, "Ce qui était demandé", "attention")):
        if elements:
            html.append(titre_section(titre, ton_section, len(elements)))
            html += [bloc_demande(index, action, client, libelle, valeurs, motif, ton_section)
                     for index, (action, client, valeurs, motif) in enumerate(elements, start=1)]

    if incertitudes:
        html.append(titre_section("Points à clarifier", "attention"))
        html.append(encadre(liste([e(texte) for texte in incertitudes], marge=0), "attention"))
    elif not ordres and sortie_validation and "JSON illisible" in sortie_validation:
        html.append(encadre("La réponse de l'assistant n'a pas pu être lue (erreur technique) : "
                            "le mail doit être retraité.", "erreur"))

    # --- Que faire ? ---
    motifs = [motif for *_, motif in non_executees]
    conseils = []
    if incertitudes:
        conseils.append("<b>Répondez à ce mail</b> en précisant les points à clarifier ci-dessus pour que la demande "
                        "soit relancée, ou faites la modification directement dans EGESYS.")
    if code == "A_VERIFIER_BANQUE":
        conseils.append("<b>Confirmez les coordonnées bancaires auprès du client</b>, puis saisissez-les dans EGESYS "
                        "(ou demandez leur exécution manuelle).")
    if any("factures correspondent" in motif["texte"] for motif in motifs):
        conseils.append("<b>Renvoyez la demande</b> en précisant le numéro de la facture, sa date ou son montant.")
    if any("période" in motif["texte"] or "plusieurs clients" in motif["texte"] for motif in motifs):
        conseils.append("<b>Renvoyez la demande</b> en vérifiant le client (code client) et la période des factures.")
    if any(motif["technique"] or "Pas tentée" in motif["texte"] for motif in motifs) or a_verifier:
        conseils.append("<b>Vérifiez la fiche du client dans EGESYS</b> : les demandes non exécutées peuvent être "
                        "refaites à la main ou renvoyées.")
    if non_executees and not conseils:
        conseils.append("<b>Corrigez la demande et renvoyez-la</b>, ou faites la modification directement dans EGESYS.")
    if conseils:
        html.append(titre_section("Que faire ?", "info"))
        html.append(liste(conseils, numerotee=True))
    elif any(not faits[0].startswith("Duplicata") for _, _, faits, _ in executees if faits):
        html.append(paragraphe("<i>Chaque modification a été contrôlée dans EGESYS après son enregistrement.</i>",
                               "margin-top:14px;color:#555555;"))

    html.append(paragraphe("<i>Message généré automatiquement par l'automate EGESYS de SOGEN.</i>",
                           "margin-top:24px;padding-top:6px;border-top:1px solid #dddddd;font-size:11px;"
                           "color:#999999;"))
    html.append("</div>")
    corps = "\n".join(html)

    # --- Objet du mail de réponse, selon le résultat ---
    if a_verifier:
        objet = "Traitement interrompu, à vérifier dans EGESYS"
    elif ordres and len(executees) == total:
        objet = "Demande traitée"
    elif executees:
        objet = "Demande partiellement traitée"
    elif code == "A_VERIFIER_BANQUE":
        objet = "Coordonnées bancaires à confirmer"
    elif code == "A_PRECISER":
        objet = "Facture à préciser"
    elif incertitudes:
        objet = "Précisions nécessaires"
    elif code == "ERREUR_EXECUTION":
        objet = "Erreur lors du traitement"
    else:
        objet = "Demande non traitée"
    return {"objet": f"EGESYS : {objet}", "corps": corps}
