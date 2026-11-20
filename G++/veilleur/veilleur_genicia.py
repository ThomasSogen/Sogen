r"""Veilleur OneDrive ↔ GENICIA++ : exécute les demandes déposées par Power Automate dans le OneDrive.

Usage : python veilleur\veilleur_genicia.py            (tourne en continu, vérifie toutes les 5 s)
        python veilleur\veilleur_genicia.py --une-fois (un seul passage)
Lancement en arrière-plan : lancer_veilleur.bat (journal : %LOCALAPPDATA%\GENICIA\veilleur.log, propre à chaque PC)

Dossiers (<OneDrive Sogen>\G++, trouvé automatiquement sur chaque PC : voir config_genicia.py) :
  pending/     Power Automate y dépose le JSON de l'agent Copilot
  processing/  JSON valide, pendant son exécution dans GENICIA++
  completed/   Toutes les demandes ont réussi
  error/       JSON refusé (incertitude, information manquante) ou erreur pendant l'exécution
  result/      <nom>.json = la réponse au mail d'origine, ÉCRITE EN TOUT DERNIER :
               {"id_message", "expediteur", "objet", "corps" (HTML), "pdf": [noms des PDF déposés dans result/pdf/],
                "client": {"mail", "objet", "corps"}}
               → le 2e flux Power Automate répond au mail, avec les PDF en pièces jointes, et, si client.mail n'est
                 pas vide, envoie aussi les factures (mêmes PDF) à l'éleveur, à l'adresse de sa fiche GENICIA++

Pour pending/<nom>.json, on trouve à la fin dans completed/ ou error/ :
  <nom>.json, <nom>_valide.json, <nom>_rapport.txt (rapport détaillé), <nom>_resultat.json, <nom>_<fichier>.pdf

Sécurité :
  - rien n'est exécuté si l'agent a une incertitude ou si un ordre est incomplet / invalide ;
  - un seul mail traité à la fois, une seule instance du veilleur ;
  - un seul PC à la fois : <OneDrive>\G++\_poste_actif.json dit quel PC fait tourner le veilleur (poste_actif.py) ;
    le veilleur refuse de démarrer si un autre PC est actif, et s'arrête si un autre PC a pris le relais ;
  - un fichier trouvé dans processing/ au démarrage (exécution interrompue) n'est JAMAIS relancé : il part dans
    error/ pour vérification dans GENICIA++.
⚠ GENICIA++ est piloté par de vrais clics souris : la session Windows doit être ouverte et déverrouillée,
  et personne ne doit utiliser le poste pendant un traitement.
"""
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

DOSSIER_PROJET = Path(__file__).resolve().parent.parent      # ...\SOGEN\G++
sys.path.insert(0, str(DOSSIER_PROJET))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ordres_genicia import (JsonIllisible, factures_max_estimees, lire_champ_brut, lire_reponse,  # noqa: E402
                            texte_validation, valider)
from compte_rendu import mail_client, rediger                                                    # noqa: E402
from config_genicia import DRIVE, FLUX                                                           # noqa: E402
from file_attente_genicia import MARQUEUR_ATTENTE, MARQUEUR_TOUR                                 # noqa: E402
from poste_actif import POSTE, PosteActif                                                        # noqa: E402

PENDING, PROCESSING, COMPLETED, ERROR, RESULT = (DRIVE / n for n in
                                                 ("pending", "processing", "completed", "error", "result"))
RESULT_PDF = RESULT / "pdf"     # PDF à joindre à la réponse, récupérés par le flux Power Automate n°2
POSTE_ACTIF = PosteActif(DRIVE / "_poste_actif.json", "Le veilleur GENICIA++")   # un seul PC à la fois
TRAVAIL = FLUX / "travail"                 # dossier de travail local (%LOCALAPPDATA%\GENICIA, hors OneDrive)
RAPPORTS_LOCAUX = FLUX / "rapports"
VERROU = FLUX / "veilleur.lock"

INTERVALLE = 5                 # secondes entre deux passages
DELAI_SYNCHRO = 3              # fichier modifié il y a moins de 3 s : peut-être encore en cours de synchro
DELAI_JSON_ILLISIBLE = 60      # un JSON illisible est retenté pendant 60 s avant d'être refusé
DUREE_MAX_BASE, DUREE_MAX_PAR_ORDRE = 600, 300   # délai maximal d'exécution d'un mail (secondes)
DUREE_MAX_PAR_FACTURE = 120                       # + par facture attendue (duplicatas sur une période)
INACTIVITE_MAX = 60            # exécution arrêtée si elle n'affiche plus rien pendant 1 min (GENICIA++ figé) ;
                               # le journal détaillé (genicia_auto.journal) écrit un signe de vie toutes les 20 s

WINDOWS = sys.platform == "win32"
SANS_FENETRE = subprocess.CREATE_NO_WINDOW if WINDOWS else 0


def horodatage():
    return f"{datetime.now():%d/%m/%Y %H:%M:%S}"


def deplacer(source, destination):
    """Déplacement robuste (fichier brièvement verrouillé par la synchronisation OneDrive)."""
    for essai in range(5):
        try:
            shutil.move(str(source), str(destination))
            return
        except PermissionError:
            if essai == 4:
                raise
            time.sleep(2)


def ecrire_atomique(texte, cible, travail):
    """Écrit en local puis met le fichier en place d'un coup : Power Automate ne voit jamais un fichier partiel."""
    temporaire = travail / f"_tmp_{cible.name}"
    temporaire.write_text(texte, encoding="utf-8")
    try:
        os.replace(temporaire, cible)
    except OSError:
        deplacer(temporaire, cible)


def nom_libre(nom):
    """Nom qui n'existe encore dans aucun dossier de statut (n'écrase jamais un ancien résultat)."""
    candidat = nom
    while any((d / f"{candidat}.json").exists() for d in (PROCESSING, COMPLETED, ERROR, RESULT)):
        candidat += "_bis"
    return candidat


# Notification Windows native (aucun module à installer) ; texte passé par variables d'environnement.
SCRIPT_NOTIFICATION = r"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual></toast>')
$textes = $xml.GetElementsByTagName('text')
$textes.Item(0).AppendChild($xml.CreateTextNode($env:GENICIA_NOTIF_TITRE)) > $null
$textes.Item(1).AppendChild($xml.CreateTextNode($env:GENICIA_NOTIF_MESSAGE)) > $null
$appli = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appli).Show(
    (New-Object Windows.UI.Notifications.ToastNotification $xml))
"""


def notifier(titre, message):
    """Notification sur le bureau ; jamais bloquante."""
    if not WINDOWS:
        return
    try:
        script = base64.b64encode(SCRIPT_NOTIFICATION.encode("utf-16-le")).decode("ascii")
        subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", script],
                         env={**os.environ, "GENICIA_NOTIF_TITRE": titre, "GENICIA_NOTIF_MESSAGE": message},
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=SANS_FENETRE)
    except OSError as erreur:
        print(f"⚠️  Notification impossible ({erreur}).")


def prendre_verrou():
    """Une seule instance du veilleur à la fois."""
    VERROU.parent.mkdir(parents=True, exist_ok=True)
    fichier = open(VERROU, "a+")
    try:
        import msvcrt
        fichier.seek(0)
        msvcrt.locking(fichier.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        sys.exit("🛑 Le veilleur GENICIA++ tourne déjà (une seule instance à la fois).")
    return fichier


# ---------------------------------------------------------------------------------------------------------------
# Exécution et publication
# ---------------------------------------------------------------------------------------------------------------

def executer(valide, travail, ordres):
    """Lance executer_ordres.py dans un processus séparé ; renvoie (code retour, sortie, résultats par ordre).
    Délai maximal : une base, plus un temps par ordre et par facture attendue (plusieurs factures = plus long)."""
    duree_max = (DUREE_MAX_BASE + DUREE_MAX_PAR_ORDRE * len(ordres)
                 + DUREE_MAX_PAR_FACTURE * sum(factures_max_estimees(o) for o in ordres))
    resultats_json = travail / "resultats_execution.json"
    commande = [sys.executable, str(DOSSIER_PROJET / "executer_ordres.py"), str(valide),
                "--fichiers", str(travail / "fichiers"), "--resultats", str(resultats_json)]
    environnement = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    p = subprocess.Popen(commande, cwd=DOSSIER_PROJET, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace", env=environnement, creationflags=SANS_FENETRE)
    lignes, derniere_activite, debut = [], [time.time()], [time.time()]

    def lire_sortie():           # chaque ligne affichée par executer_ordres.py = signe de vie
        for ligne in p.stdout:
            lignes.append(ligne)
            derniere_activite[0] = time.time()
            # File d'attente GENICIA++ (file_attente_genicia.py) : le délai maximal ne compte qu'à partir du tour
            if MARQUEUR_ATTENTE in ligne or MARQUEUR_TOUR in ligne:
                if MARQUEUR_ATTENTE in ligne and not any(MARQUEUR_ATTENTE in l for l in lignes[:-1]):
                    notifier("GENICIA++ : demande en attente",
                             "GENICIA++ est occupé par un autre traitement ; ce mail passera ensuite.")
                debut[0] = time.time()

    lecteur = threading.Thread(target=lire_sortie, daemon=True)
    lecteur.start()
    arret = ""
    while p.poll() is None:
        if time.time() - derniere_activite[0] > INACTIVITE_MAX:
            derniere = next((l.strip() for l in reversed(lignes) if l.strip()), "aucune")
            arret = (f"🛑 Aucune activité depuis {INACTIVITE_MAX} s : GENICIA++ semble figé, programme arrêté. "
                     f"Dernière action écrite : {derniere}")
        elif time.time() - debut[0] > duree_max:
            arret = "🛑 Délai d'exécution dépassé : programme arrêté."
        if arret:
            p.kill()
            break
        time.sleep(1)
    try:
        p.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass
    lecteur.join(timeout=5)
    sortie = "".join(lignes) + (f"\n{arret}" if arret else "")
    retour = -1 if arret else p.returncode
    try:
        resultats = json.loads(resultats_json.read_text(encoding="utf-8"))["ordres"]
    except (OSError, ValueError, KeyError):
        resultats = None
    if retour == -1 and resultats:
        for r in resultats:
            if r["resultat"] == "Non exécuté" and not r["detail"]:
                r["detail"] = ("Délai d'exécution dépassé : GENICIA++ ne répondait plus (aucune activité), arrêt par "
                               "sécurité.")
    return retour, sortie, resultats


def publier(nom, destination, code, message, controle, resultats, journal, travail, json_source):
    """Range tout dans completed/ ou error/, puis écrit result/<nom>.json EN DERNIER."""
    destination.mkdir(parents=True, exist_ok=True)
    produits = []
    if json_source and Path(json_source).exists():
        deplacer(json_source, destination / f"{nom}.json")
        produits.append(f"{nom}.json")
    if controle.get("ok"):
        (destination / f"{nom}_valide.json").write_text(
            json.dumps(controle["ordres"], ensure_ascii=False, indent=2), encoding="utf-8")
        produits.append(f"{nom}_valide.json")
    pdf = []   # noms des PDF à joindre à la réponse (copiés dans result/pdf/)
    if (travail / "fichiers").is_dir():
        for fichier in sorted((travail / "fichiers").iterdir()):
            if not fichier.is_file():
                continue
            nom_final = f"{nom}_{fichier.name}"
            if fichier.suffix.lower() == ".pdf":
                RESULT_PDF.mkdir(parents=True, exist_ok=True)
                temporaire = travail / f"_tmp_{nom_final}"      # copie complète avant mise en place d'un coup
                shutil.copy2(fichier, temporaire)
                try:
                    os.replace(temporaire, RESULT_PDF / nom_final)
                except OSError:
                    deplacer(temporaire, RESULT_PDF / nom_final)
                pdf.append(nom_final)
            deplacer(fichier, destination / nom_final)
            produits.append(nom_final)

    rapport = "\n".join([f"{code} : {message}", ""] + journal)
    (destination / f"{nom}_rapport.txt").write_text(rapport, encoding="utf-8")
    produits.append(f"{nom}_rapport.txt")
    RAPPORTS_LOCAUX.mkdir(parents=True, exist_ok=True)
    (RAPPORTS_LOCAUX / f"{nom} - {code}.txt").write_text(rapport, encoding="utf-8")

    resultat = {"fichier": f"{nom}.json", "statut": destination.name.upper(), "code": code, "message": message,
                "date": datetime.now().isoformat(timespec="seconds"), "resume": controle.get("resume", ""),
                "incertitudes": controle.get("incertitudes", []), "ordres": resultats or [],
                "fichiers": produits, "rapport": f"{nom}_rapport.txt"}
    ecrire_atomique(json.dumps(resultat, ensure_ascii=False, indent=2), destination / f"{nom}_resultat.json", travail)

    # Réponse au mail d'origine, en tout dernier
    source = travail / "reponse_agent.json"
    id_message, expediteur = lire_champ_brut(source, "id_message"), lire_champ_brut(source, "expediteur")
    if not id_message:
        print(f"⚠️  {nom} : pas d'id_message dans le JSON de l'agent, la réponse au mail ne pourra pas être envoyée.")
    mail = rediger(code, controle, resultats)
    # Mail au client avec ses factures (pièces jointes = liste « pdf ») ; mail vide = rien à envoyer au client
    client = mail_client(resultats, pdf)
    if client["mail"]:
        print(f"✉️  {nom} : factures à envoyer au client ({client['mail']})")
    RESULT.mkdir(parents=True, exist_ok=True)
    ecrire_atomique(json.dumps({"id_message": id_message, "expediteur": expediteur, **mail, "pdf": pdf,
                                "client": client}, ensure_ascii=False, indent=2), RESULT / f"{nom}.json", travail)

    shutil.rmtree(travail, ignore_errors=True)
    print(f"{'✅' if destination == COMPLETED else '⚠️ '} {horodatage()} {nom} → {destination.name}/ ({code})")
    notifier(f"GENICIA++ : {code}", f"{nom}\n{message}")


def traiter(fichier):
    nom = nom_libre(fichier.stem)
    travail = TRAVAIL / nom
    shutil.rmtree(travail, ignore_errors=True)
    (travail / "fichiers").mkdir(parents=True)
    shutil.copy2(fichier, travail / "reponse_agent.json")
    journal = [f"Fichier : {fichier.name}", f"Reçu le : {horodatage()}", ""]
    print(f"📥 {horodatage()} {fichier.name} reçu")

    # 1. Validation (sans GENICIA++)
    controle = valider(travail / "reponse_agent.json")
    journal += ["--- Contrôle de la demande ---", texte_validation(controle), ""]
    if not controle["ok"]:
        message = "Demande incomplète, ambiguë ou illisible : rien n'a été fait dans GENICIA++."
        publier(nom, ERROR, "REFUSE_VALIDATION", message, controle, None, journal, travail, fichier)
        return

    # 2. Exécution : le JSON passe dans processing/ le temps de l'exécution
    PROCESSING.mkdir(parents=True, exist_ok=True)
    en_cours = PROCESSING / f"{nom}.json"
    deplacer(fichier, en_cours)
    valide = travail / "ordres_valide.json"
    valide.write_text(json.dumps(controle["ordres"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"⚙️  {nom} → processing/ ({len(controle['ordres'])} ordre(s)) : ne touchez pas au poste")
    notifier("GENICIA++ : traitement en cours", f"{nom} — ne touchez ni au clavier ni à la souris")
    retour, sortie, resultats = executer(valide, travail, controle["ordres"])
    journal += ["--- Exécution dans GENICIA++ ---", sortie]

    if resultats is None:
        resultats = [{"numero": i, "action": o["action"], "cheptel": o["cheptel"], "resultat": "Erreur",
                      "detail": "Pas de résultat d'exécution (voir le rapport)", "fichiers": []}
                     for i, o in enumerate(controle["ordres"], start=1)]
    if retour == 0:
        publier(nom, COMPLETED, "EXECUTE", f"{len(resultats)} demande(s) traitée(s) dans GENICIA++.",
                controle, resultats, journal, travail, en_cours)
    else:
        reussis = sum(r["resultat"] == "Réussite" for r in resultats)
        message = f"{reussis}/{len(resultats)} demande(s) traitée(s) ; voir le détail des erreurs."
        publier(nom, ERROR, "ERREUR_EXECUTION", message, controle, resultats, journal, travail, en_cours)


def recuperer_interrompus():
    """Fichiers restés dans processing/ : on ne sait pas ce qui a été fait, on ne relance JAMAIS."""
    if not PROCESSING.is_dir():
        return
    for fichier in sorted(PROCESSING.glob("*.json")):
        nom = fichier.stem
        travail = TRAVAIL / nom
        travail.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fichier, travail / "reponse_agent.json")
        controle = valider(travail / "reponse_agent.json")
        message = "Exécution interrompue (PC ou veilleur arrêté pendant le traitement) : vérifier dans GENICIA++."
        journal = [f"Fichier : {fichier.name}", f"Repris le : {horodatage()}", "",
                   "Le fichier était dans processing/ au démarrage du veilleur."]
        publier(nom, ERROR, "INTERROMPU", message, controle, None, journal, travail, fichier)


def pret(fichier):
    """Le fichier est-il complètement synchronisé ?"""
    age = time.time() - fichier.stat().st_mtime
    if age < DELAI_SYNCHRO:
        return False
    try:
        lire_reponse(fichier)
    except JsonIllisible:
        return age >= DELAI_JSON_ILLISIBLE     # peut-être encore en cours d'écriture
    except OSError:
        return False
    return True


def passage():
    if not PENDING.is_dir():
        print(f"⚠️  Dossier introuvable : {PENDING} (OneDrive est-il lancé ?)")
        return
    POSTE_ACTIF.entretenir()          # s'arrête si un autre PC a pris le relais
    for fichier in sorted(PENDING.glob("*.json"), key=lambda f: f.stat().st_mtime):
        if pret(fichier):
            POSTE_ACTIF.entretenir()  # vérifié juste avant chaque mail
            traiter(fichier)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    verrou = prendre_verrou()
    if not DRIVE.is_dir():
        sys.exit(f"🛑 Dossier OneDrive introuvable : {DRIVE} (OneDrive est-il installé et synchronisé sur ce PC ?)")
    POSTE_ACTIF.prendre()   # refuse de démarrer si le veilleur tourne sur un autre PC
    try:
        for dossier in (PENDING, PROCESSING, COMPLETED, ERROR, RESULT):
            dossier.mkdir(parents=True, exist_ok=True)
        print(f"👀 {horodatage()} Veilleur GENICIA++ (PC {POSTE}) : surveille {PENDING}")
        recuperer_interrompus()
        if "--une-fois" in sys.argv:
            passage()
        else:
            while True:
                try:
                    passage()
                except Exception:
                    print(f"⚠️  Incident pendant le passage ({horodatage()}), nouvel essai :\n{traceback.format_exc()}")
                    try:
                        recuperer_interrompus()
                    except Exception:
                        print(traceback.format_exc())
                    time.sleep(30)
                time.sleep(INTERVALLE)
    finally:
        POSTE_ACTIF.liberer()   # arrêt normal : l'autre PC peut démarrer tout de suite
