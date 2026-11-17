r"""Workflow OneDrive ↔ EGESYS : exécute les ordres déposés par Power Automate dans le Drive.

Usage : python workflow\\workflow.py            (tourne en continu, vérifie toutes les 5 s)
        python workflow\\workflow.py --une-fois (un seul passage)

Dossiers (synchronisés par OneDrive pour ordinateur, lus/écrits par Power Automate) :
  pending/     Power Automate y dépose le JSON de l'agent (+ les pièces jointes citées par les ordres)
  processing/  JSON valide en cours d'exécution dans EGESYS
  completed/   Exécution réussie
  error/       JSON refusé, exécution bloquée (IBAN, facture introuvable…) ou erreur pendant l'exécution

Pour un fichier pending/<nom>.json, on trouve à la fin dans completed/ ou error/ :
  <nom>.json            la réponse de l'agent, telle que reçue
  <nom>_valide.json     les ordres validés (si la validation est passée)
  <nom>_rapport.txt     le rapport détaillé (validation + exécution)
  <nom>_<fichier>.pdf   les fichiers produits (duplicata de facture…) et les pièces jointes utilisées
  <nom>_resultat.json   le résultat détaillé, lisible par Power Automate

Et dans result/ : <nom>.json, la réponse au mail d'origine, ÉCRITE EN TOUT DERNIER (déclencher le flux Power
Automate de réponse sur ce dossier) :
  {"id_message": identifiant du mail (recopié par l'agent depuis la requête),
   "expediteur": expéditeur du mail (recopié par l'agent depuis la requête),
   "objet": objet de la réponse selon le résultat (« EGESYS : Demande traitée », « EGESYS : Précisions nécessaires »…),
   "corps": compte rendu en HTML mis en forme pour Outlook (demandes exécutées, non exécutées avec leur raison, que faire),
   "pdf": noms des PDF à joindre, présents dans result/pdf/ (ex : ["<nom>_facture_….pdf"], [] si aucun),
   "client": {"mail", "objet", "corps"} : mail à envoyer AU CLIENT avec les mêmes PDF (duplicatas de facture), à
             l'adresse de sa fiche EGESYS (A205) ; "mail" vide = rien à envoyer au client}
Les PDF récupérés (duplicatas de facture…) sont copiés dans result/pdf/<nom>_<fichier>.pdf AVANT result/<nom>.json.

Lancement en arrière-plan : lancer_workflow.bat (voir lancer_workflow.ps1), journal %LOCALAPPDATA%\EGESYS\workflow.log.

Sécurité : rien n'est exécuté si le validateur refuse ou si l'agent a une incertitude ;
un ordre avec IBAN ou BIC n'est jamais exécuté automatiquement ; un fichier trouvé dans processing/ au démarrage
(exécution interrompue) n'est JAMAIS relancé : il part dans error/ pour vérification dans EGESYS.

Variables d'environnement : EGESYS_IDENTIFIANT / EGESYS_MDP (obligatoires). Le dossier OneDrive est trouvé
automatiquement (<OneDrive Sogen>\EGESYS, voir config_egesys.py ; EGESYS_DRIVE pour le forcer).

Un seul PC à la fois : le fichier <OneDrive>\EGESYS\_poste_actif.json indique quel PC fait tourner le workflow
(voir poste_actif.py). Le workflow refuse de démarrer si un autre PC est actif, et s'arrête si un autre PC a pris
le relais.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

DOSSIER_SCRIPTS = Path(__file__).resolve().parent.parent  # Dossier du projet (...\SOGEN\EGESYS)
sys.path.insert(0, str(DOSSIER_SCRIPTS))

from valider_ordres import lire_reponse, lire_id_message, lire_expediteur   # noqa: E402
from journal_egesys import ajouter_au_journal                                # noqa: E402
from script_egesys import lignes_modification                               # noqa: E402
from compte_rendu import rediger as rediger_compte_rendu, mail_client       # noqa: E402
import config_egesys                                                        # noqa: E402
from poste_actif import POSTE, PosteActif                                   # noqa: E402

DRIVE = config_egesys.DRIVE  # OneDrive EGESYS (voir config_egesys.py)
POSTE_ACTIF = PosteActif(DRIVE / "_poste_actif.json", "Le workflow EGESYS")  # Un seul PC à la fois
PENDING = DRIVE / "pending"
PROCESSING = DRIVE / "processing"
COMPLETED = DRIVE / "completed"
ERROR = DRIVE / "error"
RESULT = DRIVE / "result"   # Compte rendu en clair, envoyé par mail à l'utilisateur
RESULT_PDF = RESULT / "pdf"  # PDF récupérés (duplicatas de facture…), joints à la réponse par Power Automate

# Dossier technique Windows (%LOCALAPPDATA%\EGESYS), hors projet et hors OneDrive
TRAVAIL = config_egesys.DOSSIER_LOCAL / "travail"      # Un sous-dossier par mail, le temps du traitement
VERROU = config_egesys.DOSSIER_LOCAL / "workflow.lock"  # Une seule instance du workflow à la fois
NOM_REPONSE = "reponse_copilot.txt"  # Nom attendu par script_egesys.py pour retrouver le nom du mail (journal)
SORTIE_VALIDATION = "sortie_validation.txt"  # Sortie du validateur, relue pour le compte rendu
FICHIERS_INTERNES = ("reponse_copilot_valide", "resultats_execution", "sortie_validation", "_tmp_")

INTERVALLE = 5                # secondes entre deux passages
DELAI_SYNCHRO = 3             # un fichier modifié il y a moins de 3 s est peut-être encore en cours de synchro
DELAI_JSON_ILLISIBLE = 60     # un JSON illisible est retenté pendant 60 s (fichier incomplet) avant le refus
DELAI_PIECES_JOINTES = 600    # on attend jusqu'à 10 min que les pièces jointes citées arrivent dans pending/


# ---------------------------------------------------------------------------------------------------------------
# Outils
# ---------------------------------------------------------------------------------------------------------------

def horodatage():
    return f"{datetime.now():%d/%m/%Y %H:%M:%S}"


def deplacer(source, destination):
    """Déplacement robuste (Drive ↔ disque local, fichier brièvement verrouillé par la synchronisation)."""
    for essai in range(5):
        try:
            shutil.move(str(source), str(destination))
            return
        except PermissionError:
            if essai == 4:
                raise
            time.sleep(2)


def nom_libre(nom):
    """Nom de base qui n'existe encore dans aucun dossier de statut (évite d'écraser un ancien résultat)."""
    candidat = nom
    while any((dossier / f"{candidat}.json").exists() for dossier in (PROCESSING, COMPLETED, ERROR)):
        candidat += "_bis"
    return candidat


def lignes_arret(sortie):
    """Messages d'erreur (🛑) et avertissements (⚠️) d'une sortie de script, pour le résultat."""
    return [ligne.strip() for ligne in sortie.splitlines() if '🛑' in ligne or '⚠️' in ligne]


WINDOWS = sys.platform == 'win32'
SANS_FENETRE = subprocess.CREATE_NO_WINDOW if WINDOWS else 0  # Sous-processus sans fenêtre de console


def lancer(commande):
    """Lance un script Python du projet ; retourne (succès, sortie complète)."""
    # PYTHONUTF8 : le script enfant écrit en UTF-8 (emojis compris) même sous Windows, et on relit en UTF-8
    environnement = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    resultat = subprocess.run([sys.executable, *commande], cwd=DOSSIER_SCRIPTS, capture_output=True, text=True,
                              encoding='utf-8', errors='replace', env=environnement, creationflags=SANS_FENETRE)
    return resultat.returncode == 0, resultat.stdout + resultat.stderr


# Notification Windows 10/11 native (sans module à installer). Le titre et le message passent par des variables
# d'environnement : aucun risque qu'un caractère du texte soit interprété par PowerShell.
SCRIPT_NOTIFICATION_WINDOWS = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual></toast>')
$textes = $xml.GetElementsByTagName('text')
$textes.Item(0).AppendChild($xml.CreateTextNode($env:EGESYS_NOTIF_TITRE)) > $null
$textes.Item(1).AppendChild($xml.CreateTextNode($env:EGESYS_NOTIF_MESSAGE)) > $null
$appli = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appli).Show(
    (New-Object Windows.UI.Notifications.ToastNotification $xml))
"""


def notifier(titre, message):
    """Notification Windows sur le bureau. Jamais bloquante : si elle échoue, le journal workflow.log suffit."""
    if not WINDOWS:
        return
    try:
        script = base64.b64encode(SCRIPT_NOTIFICATION_WINDOWS.encode('utf-16-le')).decode('ascii')
        subprocess.Popen(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', script],
                         env={**os.environ, 'EGESYS_NOTIF_TITRE': titre, 'EGESYS_NOTIF_MESSAGE': message},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=SANS_FENETRE)
    except OSError as erreur:
        print(f"⚠️  Notification impossible ({erreur}).")


def pieces_jointes_citees(chemin_fichier):
    """Noms des pièces jointes utilisées par les ordres (note ou document)."""
    try:
        ordres, _, _ = lire_reponse(chemin_fichier)
    except SystemExit:
        return set()  # JSON illisible : le validateur le signalera
    return {os.path.basename(ordre.get(dossier_ordre, {}).get(champ, ''))
            for ordre in ordres if isinstance(ordre, dict)
            for dossier_ordre, champ in (("note", "piece_jointe"), ("document", "chemin"))} - {''}


def contient_banque(chemin_valide):
    """Un des ordres validés contient-il un IBAN ou un BIC ?"""
    with open(chemin_valide, encoding='utf-8') as fichier:
        ordres = json.load(fichier)
    return any((ordre.get("modèle_de_reglement") or {}).get(champ) for ordre in ordres for champ in ("iban", "bic"))


def journaliser_blocage(nom, reponse, statut):
    """Inscrit dans le journal Excel les ordres bloqués avant exécution (validation, incertitudes, IBAN)."""
    try:
        ordres, incertitudes, _ = lire_reponse(reponse)
    except SystemExit:
        ordres, incertitudes = [], ["JSON illisible"]
    detail = " | ".join([statut] + [str(i) for i in incertitudes])
    for ordre in (ordres if ordres else [{"action": "—", "justification": "Aucun ordre dans la réponse de l'agent"}]):
        ordre = ordre if isinstance(ordre, dict) else {}
        try:
            modification = "\n".join(lignes_modification(ordre, {}))  # Valeurs demandées (non appliquées)
        except (AttributeError, TypeError):
            modification = ""  # Ordre mal formé : le détail du validateur suffit
        ajouter_au_journal(ordre, "Non exécuté", detail, nom, modification)


def prendre_verrou_workflow():
    """Une seule instance du workflow à la fois (sinon un fichier pourrait être traité deux fois)."""
    VERROU.parent.mkdir(parents=True, exist_ok=True)
    fichier = open(VERROU, 'a+')
    try:
        if sys.platform == 'win32':
            import msvcrt
            fichier.seek(0)
            msvcrt.locking(fichier.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fichier, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit("🛑 Le workflow tourne déjà (une seule instance à la fois).")
    return fichier


# ---------------------------------------------------------------------------------------------------------------
# Écriture des résultats dans le dossier de statut
# ---------------------------------------------------------------------------------------------------------------

def mettre_en_place(cible, texte=None, source=None):
    """Écrit le texte (ou copie le fichier source) dans le dossier caché du OneDrive _ecriture_en_cours, puis le
    déplace d'un coup vers la cible (même disque = instantané) : Power Automate ne voit jamais un fichier à moitié
    écrit, ni de fichier temporaire dans les dossiers qu'il surveille (pending, result)."""
    dossier = config_egesys.ECRITURE_EN_COURS
    if not dossier.is_dir():
        dossier.mkdir(parents=True, exist_ok=True)
        if WINDOWS:
            import ctypes
            ctypes.windll.kernel32.SetFileAttributesW(str(dossier), 0x2)  # Dossier caché
    temporaire = dossier / cible.name
    if texte is not None:
        temporaire.write_text(texte, encoding='utf-8')
    else:
        shutil.copy2(source, temporaire)
    try:
        os.replace(temporaire, cible)
    except OSError:
        deplacer(temporaire, cible)  # Fichier cible brièvement verrouillé par la synchronisation : nouvel essai


def publier(nom, destination, statut, code, message, journal, travail, details_ordres=None, json_source=None):
    """Range tout ce qui concerne <nom> dans destination (COMPLETED ou ERROR), puis écrit le compte rendu en clair
    dans result/ EN TOUT DERNIER : quand Power Automate le voit, tous les autres fichiers sont déjà là."""
    destination.mkdir(parents=True, exist_ok=True)
    produits = []
    pdf_recuperes = sorted(f.name for f in (travail / "fichiers").glob("*") if f.is_file()) \
        if (travail / "fichiers").is_dir() else []

    if json_source and Path(json_source).exists():
        deplacer(json_source, destination / f"{nom}.json")
    produits.append(f"{nom}.json")

    valide = travail / "reponse_copilot_valide.json"
    if valide.exists():
        shutil.copy2(valide, destination / f"{nom}_valide.json")
        produits.append(f"{nom}_valide.json")

    # PDF produits par l'exécution (duplicatas de facture…) : copie dans result/pdf/ pour être joints à la réponse.
    # Mise en place d'un coup : Power Automate ne voit jamais un PDF à moitié copié.
    pdf_reponse = []
    for nom_pdf in pdf_recuperes:
        if not nom_pdf.lower().endswith(".pdf"):
            continue
        RESULT_PDF.mkdir(parents=True, exist_ok=True)
        cible = RESULT_PDF / f"{nom}_{nom_pdf}"
        mettre_en_place(cible, source=travail / "fichiers" / nom_pdf)
        pdf_reponse.append(cible.name)

    # Fichiers produits par l'exécution (duplicatas de facture…), puis pièces jointes reçues
    for dossier_fichiers in (travail / "fichiers", travail / "pieces_jointes"):
        if dossier_fichiers.is_dir():
            for fichier in sorted(dossier_fichiers.iterdir()):
                if fichier.is_file():
                    deplacer(fichier, destination / f"{nom}_{fichier.name}")
                    produits.append(f"{nom}_{fichier.name}")

    rapport = "\n".join([f"{code} : {message}", ""] + journal)
    (destination / f"{nom}_rapport.txt").write_text(rapport, encoding='utf-8')
    produits.append(f"{nom}_rapport.txt")

    try:
        ordres_recus, incertitudes, resume = lire_reponse(str(travail / NOM_REPONSE))
    except (SystemExit, OSError):
        ordres_recus, incertitudes, resume = [], [], ""

    resultat = {
        "fichier": f"{nom}.json",
        "statut": statut,                 # COMPLETED / ERROR
        "code": code,                     # EXECUTE, REFUSE_VALIDATION, A_VERIFIER_BANQUE, A_PRECISER, ERREUR_EXECUTION…
        "message": message,               # Phrase prête à renvoyer à l'utilisateur
        "date": datetime.now().isoformat(timespec='seconds'),
        "resume": resume,
        "incertitudes": incertitudes,
        "ordres": details_ordres or [],
        "fichiers": produits,             # Tous les fichiers de ce traitement présents dans le dossier
        "rapport": f"{nom}_rapport.txt",
    }
    mettre_en_place(destination / f"{nom}_resultat.json", texte=json.dumps(resultat, ensure_ascii=False, indent=2))

    # Compte rendu pour l'utilisateur (dossier result/), en dernier
    try:
        sortie_validation = (travail / SORTIE_VALIDATION).read_text(encoding='utf-8')
    except OSError:
        sortie_validation = ""
    execute = code in ("EXECUTE", "A_PRECISER", "ERREUR_EXECUTION")  # script_egesys.py a été lancé
    reponse_mail = rediger_compte_rendu(code, ordres_recus, incertitudes, sortie_validation,
                                        details_ordres if execute else None, pdf_recuperes, resume)
    id_message = lire_id_message(str(travail / NOM_REPONSE))
    if not id_message:
        print(f"⚠️  {nom} : pas d'id_message dans le JSON de l'agent, la réponse au mail ne pourra pas être envoyée.")
    expediteur = lire_expediteur(str(travail / NOM_REPONSE))
    if not expediteur:
        print(f"⚠️  {nom} : pas d'expediteur dans le JSON de l'agent.")
    # Mail au client avec ses factures (mêmes PDF que la liste « pdf ») ; mail vide = rien à envoyer au client
    client = mail_client(details_ordres if execute else None, pdf_reponse, ordres_recus)
    if client["mail"]:
        print(f"✉️  {nom} : factures à envoyer au client ({client['mail']})")
    contenu = {"id_message": id_message, "expediteur": expediteur,
               "objet": reponse_mail["objet"], "corps": reponse_mail["corps"],
               "pdf": pdf_reponse,  # Noms des PDF de result/pdf/ à joindre à la réponse ([] si aucun)
               "client": client}    # {mail, objet, corps} du mail au client (adresse de sa fiche EGESYS)
    RESULT.mkdir(parents=True, exist_ok=True)
    mettre_en_place(RESULT / f"{nom}.json", texte=json.dumps(contenu, ensure_ascii=False, indent=2))

    shutil.rmtree(travail, ignore_errors=True)
    print(f"{'✅' if statut == 'COMPLETED' else '⚠️ '} {nom} → {destination.name}/ ({code})")
    notifier(f"EGESYS : {code}", f"{nom}\n{message}")


def ordres_demandes(chemin_reponse, resultat, detail):
    """Liste des ordres de la réponse, tous avec le même résultat (utilisé quand rien n'a été exécuté)."""
    try:
        ordres, _, _ = lire_reponse(str(chemin_reponse))
    except SystemExit:
        return []
    return [{"numero": numero, "action": ordre.get("action", "") if isinstance(ordre, dict) else "",
             "client": " / ".join(v for v in (ordre.get("nom_client", ""), ordre.get("code_client", "")) if v)
             if isinstance(ordre, dict) else "",
             "resultat": resultat, "detail": detail, "modification": ""}
            for numero, ordre in enumerate(ordres, start=1)]


# ---------------------------------------------------------------------------------------------------------------
# Traitement d'un fichier
# ---------------------------------------------------------------------------------------------------------------

def pret(fichier):
    """Le fichier est-il complètement synchronisé et ses pièces jointes arrivées ? Retourne les pièces jointes
    (nom → chemin dans pending, ou None si absente) ou None s'il faut encore attendre."""
    age = time.time() - fichier.stat().st_mtime
    if age < DELAI_SYNCHRO:
        return None
    try:
        lire_reponse(str(fichier))
    except SystemExit:
        if age < DELAI_JSON_ILLISIBLE:
            return None  # Peut-être encore en cours d'écriture : on retentera
        return {}        # Toujours illisible : le validateur le refusera
    pieces = {piece: (PENDING / piece if (PENDING / piece).is_file() else None)
              for piece in pieces_jointes_citees(str(fichier))}
    if any(chemin is None for chemin in pieces.values()) and age < DELAI_PIECES_JOINTES:
        return None  # On laisse le temps à Power Automate de déposer les pièces jointes
    return pieces


def traiter(fichier, pieces):
    nom = nom_libre(fichier.stem)
    travail = TRAVAIL / nom
    shutil.rmtree(travail, ignore_errors=True)
    (travail / "pieces_jointes").mkdir(parents=True)
    (travail / "fichiers").mkdir()
    journal = [f"Fichier : {fichier.name}", f"Reçu le : {horodatage()}", ""]
    print(f"📥 {fichier.name} reçu" + (f" avec {sorted(pieces)}" if pieces else ""))
    notifier("EGESYS : traitement en cours", fichier.name)

    # Copie locale : le validateur cherche les pièces jointes dans le dossier du JSON
    reponse = travail / NOM_REPONSE
    shutil.copy2(fichier, reponse)
    manquantes = [piece for piece, chemin in pieces.items() if chemin is None]
    for piece, chemin in pieces.items():
        if chemin is not None:
            deplacer(chemin, travail / piece)
    if manquantes:
        journal.append(f"⚠️  Pièces jointes absentes de pending/ : {manquantes}\n")

    # 1. Validation (sans connexion)
    succes, sortie = lancer(['valider_ordres.py', str(reponse)])
    journal += ["--- Validation ---", sortie]
    (travail / SORTIE_VALIDATION).write_text(sortie, encoding='utf-8')
    if not succes:
        message = "Ordres refusés par le validateur ou incertitudes de l'agent : rien n'a été modifié dans EGESYS."
        erreurs = lignes_arret(sortie)
        journaliser_blocage(nom, str(reponse), message)
        ranger_pieces(travail)
        publier(nom, ERROR, "ERROR", "REFUSE_VALIDATION", message, journal, travail,
                ordres_demandes(reponse, "Non exécuté", " | ".join(erreurs)), json_source=fichier)
        return

    valide = travail / "reponse_copilot_valide.json"
    if contient_banque(str(valide)):
        message = ("Coordonnées bancaires reçues par mail : à confirmer auprès du client (risque de fraude au RIB). "
                   "Rien n'a été modifié dans EGESYS.")
        journaliser_blocage(nom, str(reponse), message)
        ranger_pieces(travail)
        publier(nom, ERROR, "ERROR", "A_VERIFIER_BANQUE", message, journal, travail,
                ordres_demandes(reponse, "Non exécuté", message), json_source=fichier)
        return

    # 2. JSON valide → processing/ pendant l'exécution
    PROCESSING.mkdir(parents=True, exist_ok=True)
    en_cours = PROCESSING / f"{nom}.json"
    deplacer(fichier, en_cours)
    print(f"⚙️  {nom} → processing/")

    # 3. Exécution dans EGESYS : factures et résultats écrits dans le dossier de travail
    os.environ['EGESYS_FACTURES'] = str(travail / "fichiers")
    os.environ['EGESYS_RESULTATS'] = str(travail / "resultats_execution.json")
    try:
        succes, sortie = lancer(['script_egesys.py', str(valide)])
    finally:
        os.environ.pop('EGESYS_FACTURES', None)
        os.environ.pop('EGESYS_RESULTATS', None)
    journal += ["--- Exécution EGESYS ---", sortie]

    try:
        execution = json.loads((travail / "resultats_execution.json").read_text(encoding='utf-8'))
        details = execution.get("ordres", [])
    except (OSError, json.JSONDecodeError):
        details = ordres_demandes(reponse, "Erreur", " | ".join(lignes_arret(sortie)) or "Pas de résultat d'exécution")
    ranger_pieces(travail)

    if succes:
        nb = len(details)
        message = f"{nb} ordre(s) exécuté(s) avec succès dans EGESYS."
        publier(nom, COMPLETED, "COMPLETED", "EXECUTE", message, journal, travail, details, json_source=en_cours)
    elif "Par sécurité, aucune" in sortie:
        message = "Aucune ou plusieurs factures correspondent : critères à préciser (voir les candidates dans le rapport)."
        publier(nom, ERROR, "ERROR", "A_PRECISER", message, journal, travail, details, json_source=en_cours)
    else:
        arrets = lignes_arret(sortie)
        message = ("Erreur pendant l'exécution dans EGESYS : " + (arrets[-1] if arrets else "voir le rapport")
                   + ". Les ordres précédents ont pu être exécutés (voir le détail).")
        publier(nom, ERROR, "ERROR", "ERREUR_EXECUTION", message, journal, travail, details, json_source=en_cours)


def ranger_pieces(travail):
    """Pièces jointes reçues : déplacées dans pieces_jointes/ pour être publiées avec le résultat."""
    for fichier in travail.iterdir():
        if fichier.is_file() and fichier.name != NOM_REPONSE and not fichier.name.startswith(FICHIERS_INTERNES):
            deplacer(fichier, travail / "pieces_jointes" / fichier.name)


def recuperer_interrompus():
    """Fichiers restés dans processing/ (PC éteint ou script arrêté pendant l'exécution). On ne sait pas ce qui a été
    fait dans EGESYS : on ne relance JAMAIS automatiquement (risque de double saisie), on signale."""
    if not PROCESSING.is_dir():
        return
    for fichier in sorted(PROCESSING.glob("*.json")):
        nom = fichier.stem
        travail = TRAVAIL / nom
        travail.mkdir(parents=True, exist_ok=True)
        if not (travail / NOM_REPONSE).exists():
            shutil.copy2(fichier, travail / NOM_REPONSE)
        message = ("Exécution interrompue (PC ou workflow arrêté pendant le traitement) : vérifier dans EGESYS ce qui a "
                   "été fait avant de relancer.")
        journal = [f"Fichier : {fichier.name}", f"Repris le : {horodatage()}", "",
                   "Le fichier était dans processing/ au démarrage du workflow."]
        ranger_pieces(travail)
        publier(nom, ERROR, "ERROR", "INTERROMPU", message, journal, travail,
                ordres_demandes(travail / NOM_REPONSE, "Inconnu", message), json_source=fichier)


def passage():
    if not PENDING.is_dir():
        print(f"⚠️  Dossier introuvable : {PENDING} (OneDrive est-il lancé ?)")
        return
    POSTE_ACTIF.entretenir()  # S'arrête si un autre PC a pris le relais
    for fichier in sorted(PENDING.glob("*.json")):
        pieces = pret(fichier)
        if pieces is not None:
            POSTE_ACTIF.entretenir()  # Vérifié juste avant chaque mail
            traiter(fichier, pieces)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr.reconfigure(encoding='utf-8', errors='replace', line_buffering=True)
    if not os.environ.get('EGESYS_IDENTIFIANT') or not os.environ.get('EGESYS_MDP'):
        sys.exit("🛑 ERREUR : Variables d'environnement EGESYS_IDENTIFIANT et EGESYS_MDP non définies.")
    verrou = prendre_verrou_workflow()
    if not DRIVE.is_dir():
        sys.exit(f"🛑 Dossier OneDrive introuvable : {DRIVE} (OneDrive est-il installé et synchronisé sur ce PC ?)")
    POSTE_ACTIF.prendre()  # Refuse de démarrer si le workflow tourne sur un autre PC
    try:
        for dossier in (PENDING, PROCESSING, COMPLETED, ERROR, RESULT):
            dossier.mkdir(parents=True, exist_ok=True)
        print(f"👀 {horodatage()} Workflow EGESYS (PC {POSTE}) : surveille {PENDING}")
        recuperer_interrompus()
        if '--une-fois' in sys.argv:
            passage()
        else:
            while True:
                try:
                    passage()
                except Exception:
                    print(f"⚠️  Incident pendant le passage ({horodatage()}), nouvel essai :\n{traceback.format_exc()}")
                    try:
                        recuperer_interrompus()  # Un fichier resté dans processing/ ne doit pas y rester bloqué
                    except Exception:
                        print(traceback.format_exc())
                    time.sleep(30)
                time.sleep(INTERVALLE)
    finally:
        POSTE_ACTIF.liberer()  # Arrêt normal : l'autre PC peut démarrer tout de suite
