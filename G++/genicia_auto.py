"""Outils pour piloter GENICIA++ via Java Access Bridge (pyjab).

Les éléments sont toujours trouvés par leur nom, leur type ou leur libellé.

Deux façons de cliquer :
  - cliquer()       : clic « accessible » (Java Access Bridge), ne bouge pas la souris.
  - cliquer_souris(): vrai clic souris au centre de l'élément. OBLIGATOIRE pour les boutons
                      qui ouvrent une fenêtre bloquante (Impression, Aperçu, Enregistrer...) :
                      un clic accessible sur ces boutons bloque Java Access Bridge tant que
                      la fenêtre reste ouverte. La fenêtre est mise au premier plan avant le clic.
"""
import re
import subprocess
import time
from ctypes import byref, c_long, windll
from typing import Union

import keyring
import pythoncom
from pyjab.common.exceptions import JABException
from pyjab.common.types import JOBJECT64
from pyjab.jabdriver import JABDriver
from pyjab.jabelement import JABElement
from pywinauto import Desktop, mouse

DLL_BRIDGE = r"C:\Program Files\Java\jre1.8.0_25\bin\WindowsAccessBridge-64.dll"
EXE = r"C:\Logicia\Genicia\GPP\packages\genicia.exe"
DOSSIER = r"C:\Logicia\Genicia\GPP\packages"

Cible = Union[JABDriver, JABElement]   # une fenêtre (driver) ou la racine d'une boîte de dialogue


# ---------------------------------------------------------------- messages Windows (anti-blocage)
# Java Access Bridge envoie ses notifications à ce programme par des messages Windows. S'ils ne sont pas traités,
# ils s'accumulent et GENICIA++ finit par se figer en attendant notre réponse (éléments « introuvables », écran
# bloqué, programme long à se terminer). D'où : TOUTE attente passe par pause(), qui traite les messages en continu.

def traiter_messages():
    """Traite les messages Windows/COM en attente (non bloquant, très rapide si la file est vide)."""
    try:
        pythoncom.PumpWaitingMessages()
    except pythoncom.com_error:
        pass


def pause(secondes: float):
    """Comme time.sleep, mais en traitant les messages Windows toutes les 50 ms."""
    fin = time.time() + secondes
    while True:
        traiter_messages()
        reste = fin - time.time()
        if reste <= 0:
            return
        time.sleep(min(0.05, reste))


# ---------------------------------------------------------------- fenêtres

def fenetres_java():
    return [w for w in Desktop(backend="win32").windows(visible_only=True)
            if w.class_name() in ("SunAwtFrame", "SunAwtDialog")]


def attendre_fenetre(morceau_titre: str, timeout: float = 60, classe: str = None) -> JABDriver:
    """Attend qu'une fenêtre Java dont le titre contient `morceau_titre` apparaisse.
    `classe` : « SunAwtFrame » (fenêtre principale) ou « SunAwtDialog » (boîte), pour ne pas les confondre."""
    fin = time.time() + timeout
    while time.time() < fin:
        for w in fenetres_java():
            if morceau_titre.lower() in w.window_text().lower() and (classe is None or w.class_name() == classe):
                return JABDriver(hwnd=w.handle, bridge_dll=DLL_BRIDGE)
        pause(0.5)
    titres = [w.window_text() for w in fenetres_java()]
    raise TimeoutError(f"Fenêtre « {morceau_titre} » introuvable. Fenêtres ouvertes : {titres}")


def attendre_dialogue(driver: JABDriver, titre: str, timeout: float = 60) -> JABElement:
    """Attend une boîte de dialogue Java (titre exact) et renvoie sa racine.

    pyjab refuse parfois les boîtes de dialogue ; on passe donc directement par le bridge
    déjà ouvert sur la fenêtre principale.
    """
    fin = time.time() + timeout
    while time.time() < fin:
        for w in fenetres_java():
            if w.window_text() == titre:
                vmid, ctx = c_long(), JOBJECT64()
                if driver.bridge.getAccessibleContextFromHWND(w.handle, byref(vmid), byref(ctx)):
                    return JABElement(driver.bridge, w.handle, vmid, ctx)
        pause(0.5)
    raise TimeoutError(f"Boîte « {titre} » introuvable. Fenêtres : {dialogues_ouverts()}")


def dialogue_ouvert(titre: str) -> bool:
    return titre in dialogues_ouverts()


def dialogues_ouverts():
    return [w.window_text() for w in fenetres_java() if w.class_name() == "SunAwtDialog"]


def premier_plan(hwnd) -> bool:
    """Met la fenêtre au premier plan et vérifie qu'elle y est."""
    for _ in range(10):
        if windll.user32.GetForegroundWindow() == hwnd:
            return True
        try:
            Desktop(backend="win32").window(handle=hwnd).set_focus()
        except Exception:
            pass
        pause(0.3)
    return windll.user32.GetForegroundWindow() == hwnd


# ---------------------------------------------------------------- éléments

def _racine(cible: Cible) -> JABElement:
    return cible.root_element if isinstance(cible, JABDriver) else cible


def enfants(e: JABElement):
    """Enfants d'un élément ; ceux que Java refuse de décrire sont ignorés."""
    try:
        n = e.children_count
    except JABException:
        return
    for i in range(n):
        try:
            ctx = e.bridge.getAccessibleChildFromContext(e.vmid, e.accessible_context, i)
            if ctx:
                yield JABElement(e.bridge, e.hwnd, e.vmid, ctx)
        except JABException:
            continue


def elements_affiches(cible: Cible):
    """Parcourt les éléments affichés, sans descendre dans les zones cachées.

    Plus robuste que les recherches de pyjab, qui s'arrêtent à la première erreur
    de Java Access Bridge (éléments cachés ou périmés).
    """
    traiter_messages()
    pile = [_racine(cible)]
    while pile:
        e = pile.pop()
        try:
            etats = e.states_en_us or []
        except JABException:
            continue
        if "showing" not in etats:
            continue
        yield e
        pile.extend(reversed(list(enfants(e))))


def _role(e):
    try:
        return e.role_en_us
    except JABException:
        return None


def _nom(e):
    try:
        return e.name or ""
    except JABException:
        return ""


def visibles(cible: Cible, role: str):
    """Éléments affichés d'un type donné, triés de haut en bas puis de gauche à droite."""
    places = []
    for e in elements_affiches(cible):
        if _role(e) != role:
            continue
        try:
            b = e.bounds
        except JABException:          # élément disparu entre-temps (écran ou liste en cours de rechargement)
            continue
        places.append(((b["y"], b["x"]), e))
    return [e for _, e in sorted(places, key=lambda p: p[0])]


def attendre_element(cible: Cible, nom: str, role: str = None, timeout: float = 30):
    """Attend qu'un élément affiché porte exactement ce nom (et ce type), et le renvoie."""
    fin = time.time() + timeout
    while True:
        for e in elements_affiches(cible):
            if _nom(e) == nom and (role is None or _role(e) == role):
                return e
        if time.time() > fin:
            raise TimeoutError(f"Élément « {nom} » introuvable à l'écran")
        pause(0.5)


def trouver(cible: Cible, nom: str, role: str = None):
    """Premier élément portant ce nom, même caché (ex. entrée d'un menu replié)."""
    pile = [_racine(cible)]
    while pile:
        e = pile.pop()
        if _nom(e) == nom and (role is None or _role(e) == role):
            return e
        pile.extend(enfants(e))
    raise LookupError(f"Élément « {nom} » introuvable")


def cliquer(cible: Cible, nom: str, role: str = None, timeout: float = 30):
    """Clic accessible. NE PAS utiliser pour un bouton qui ouvre une fenêtre bloquante."""
    attendre_element(cible, nom, role, timeout).click()


def cliquer_souris(cible: Cible, nom: str, role: str = None, timeout: float = 30):
    """Vrai clic souris au centre de l'élément, après mise au premier plan de sa fenêtre."""
    clic_souris_element(attendre_element(cible, nom, role, timeout))


def clic_souris_element(e: JABElement):
    """Vrai clic souris au centre d'un élément déjà trouvé (ex. bouton sans nom)."""
    if not premier_plan(e.hwnd):
        raise RuntimeError(f"Impossible de mettre la fenêtre au premier plan pour cliquer sur « {_nom(e)} »")
    b = e.bounds
    x, y = b["x"] + b["width"] // 2, b["y"] + b["height"] // 2
    # clic décomposé : un clic instantané est parfois ignoré par Java
    mouse.move(coords=(x, y)); pause(0.3)
    mouse.press(coords=(x, y)); pause(0.15)
    mouse.release(coords=(x, y))


def ouvrir_dialogue(driver: JABDriver, cible: Cible, nom: str, titre: str, role: str = None,
                    avant=None, essais: int = 3, attente: float = 8, timeout: float = 60) -> JABElement:
    """Clic souris sur `nom` jusqu'à ce que la boîte `titre` s'ouvre, et renvoie sa racine.

    Un clic juste après un changement d'écran est parfois ignoré par GENICIA++ : on réessaie.
    `avant` : fonction appelée avant chaque clic (ex. ouvrir un menu).
    """
    for essai in range(essais):
        pause(0.5 + essai)
        if not dialogue_ouvert(titre):
            try:
                if avant:
                    avant()
                # le menu ouvert par `avant` peut ne pas s'être déroulé (clic ignoré) : délai court, puis nouvel essai
                cliquer_souris(cible, nom, role, timeout=10 if avant else 30)
            except TimeoutError:
                if essai == essais - 1:
                    raise
                print(f"   « {nom.strip()} » pas encore affiché : nouvel essai")
                continue
        fin = time.time() + attente
        while time.time() < fin:
            if dialogue_ouvert(titre):
                return attendre_dialogue(driver, titre, timeout)
            pause(0.3)
    # dernière chance : la boîte peut être lente à apparaître (génération d'un aperçu...)
    return attendre_dialogue(driver, titre, timeout)


def cliquer_souris_jusqua(cible: Cible, nom: str, condition, role: str = None,
                          essais: int = 3, attente: float = 10, description: str = ""):
    """Clic souris sur `nom`, répété tant que `condition()` n'est pas vraie.

    Le premier clic est parfois « mangé » par un menu déroulant resté ouvert : on reclique,
    comme le ferait un utilisateur.
    """
    for essai in range(essais):
        if essai:
            pause(1)
        cliquer_souris(cible, nom, role)
        fin = time.time() + attente
        while time.time() < fin:
            if condition():
                return
            pause(0.3)
    raise TimeoutError(f"Le clic sur « {nom.strip()} » n'a pas eu d'effet ({description})")


def options_liste_deroulante(combo: JABElement) -> list[str]:
    """Choix proposés par une liste déroulante (combo box), dans l'ordre."""
    pile, options = [combo], []
    while pile:
        e = pile.pop()
        if _role(e) in ("label", "list item"):
            options.append(_nom(e))
        pile.extend(reversed(list(enfants(e))))
    return options


def choisir(combo: JABElement, option: str):
    """Sélectionne `option` dans une liste déroulante et vérifie que c'est pris en compte."""
    options = options_liste_deroulante(combo)
    if option not in options:
        raise LookupError(f"« {option} » absent de la liste : {options}")
    combo.bridge.clearAccessibleSelectionFromContext(combo.vmid, combo.accessible_context)
    combo.bridge.addAccessibleSelectionFromContext(combo.vmid, combo.accessible_context, options.index(option))
    pause(0.5)
    if valeur_liste_deroulante(combo) != option:
        raise RuntimeError(f"La sélection de « {option} » n'a pas été prise en compte")


def valeur_liste_deroulante(combo: JABElement) -> str:
    pile = [combo]
    while pile:
        e = pile.pop()
        if _role(e) in ("label", "list item") and "selected" in (e.states_en_us or []):
            return _nom(e)
        pile.extend(enfants(e))
    return ""


def liste_deroulante_par_libelle(cible: Cible, texte: str) -> JABElement:
    """Liste déroulante affichée sur la même ligne, à droite du libellé `texte`."""
    lb = libelle(cible, texte).bounds
    candidats = [c for c in visibles(cible, "combo box")
                 if abs(c.bounds["y"] - lb["y"]) < 20 and c.bounds["x"] > lb["x"]]
    if not candidats:
        raise LookupError(f"Aucune liste déroulante à droite de « {texte} »")
    return min(candidats, key=lambda c: c.bounds["x"])


def ecrire(element, texte: str):
    element.send_text(texte)


def _texte_libelle(nom: str) -> str:
    """'<html><u>N° Cheptel :</u></html>' -> 'n° cheptel'"""
    t = re.sub(r"<[^>]+>", "", nom or "")
    return re.sub(r"\s+", " ", t).strip().rstrip(":").strip().lower()


def libelle(cible: Cible, texte: str) -> JABElement:
    """Libellé affiché correspondant à `texte` : exact d'abord, sinon « commence par »."""
    labels = visibles(cible, "label")
    cherche = _texte_libelle(texte)
    for test in (lambda t: t == cherche, lambda t: t.startswith(cherche)):
        trouves = [l for l in labels if test(_texte_libelle(_nom(l)))]
        if trouves:
            return trouves[0]
    raise LookupError(f"Libellé « {texte} » introuvable")


def champ_par_libelle(cible: Cible, texte: str):
    """Champ de saisie affiché sur la même ligne, à droite du libellé `texte`."""
    lb = libelle(cible, texte).bounds
    candidats = [t for t in visibles(cible, "text")
                 if abs(t.bounds["y"] - lb["y"]) < 20 and t.bounds["x"] > lb["x"]]
    if not candidats:
        raise LookupError(f"Aucun champ à droite de « {texte} »")
    return min(candidats, key=lambda t: t.bounds["x"])


# ---------------------------------------------------------------- listes

def liste_affichee(cible: Cible, index: int = 0) -> JABElement:
    return visibles(cible, "list")[index]


def lire_lignes(liste: JABElement) -> list[list[str]]:
    """Valeurs de chaque ligne d'une liste GENICIA++ (étiquettes dans l'ordre des colonnes),
    y compris les lignes hors écran."""
    return [[_nom(c) for c in enfants(l) if _role(c) == "label"] for l in enfants(liste)]


def attendre_lignes(cible: Cible, timeout: float = 30) -> list[list[str]]:
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            lignes = lire_lignes(liste_affichee(cible))
            if lignes:
                return lignes
        except (IndexError, JABException):    # liste pas encore affichée, ou en cours de rechargement
            pass
        pause(0.5)
    return []


def selectionner_ligne(liste: JABElement, index: int):
    liste.bridge.clearAccessibleSelectionFromContext(liste.vmid, liste.accessible_context)
    liste.bridge.addAccessibleSelectionFromContext(liste.vmid, liste.accessible_context, index)


# ---------------------------------------------------------------- navigation

def titre_fenetre_principale() -> str:
    for w in fenetres_java():
        if "genicia++ v" in w.window_text().lower() and w.class_name() == "SunAwtFrame":
            t = w.window_text()
            return t[t.rfind("[") + 1:t.rfind("]")] if "[" in t else "ACCUEIL"
    return ""


def attendre_ecran(titre: str, timeout: float = 30):
    """Attend que la fenêtre principale affiche l'écran `titre` (ex. « BILAN ELEVEUR »)."""
    fin = time.time() + timeout
    while time.time() < fin:
        if titre_fenetre_principale().lower() == titre.lower():
            return
        pause(0.5)
    raise TimeoutError(f"Écran « {titre} » non atteint (écran actuel : {titre_fenetre_principale()})")


def rechercher_eleveur(d: JABDriver, cheptel: str, ecran_suivant_pret, timeout: float = 30):
    """Écran de recherche d'éleveur (commun à plusieurs menus) : N° Cheptel -> Rechercher (F3).

    - un seul éleveur trouvé : GENICIA++ passe seul à l'écran suivant ;
    - plusieurs : sélection de la ligne du cheptel puis VALIDER (F12).
    `ecran_suivant_pret()` doit renvoyer True quand l'écran suivant est affiché.
    """
    attendre_element(d, "Rechercher (F3)")
    ecrire(champ_par_libelle(d, "N° Cheptel"), cheptel)
    cliquer(d, "Rechercher (F3)")
    fin = time.time() + timeout
    while time.time() < fin:
        if ecran_suivant_pret():
            return
        listes = visibles(d, "list")
        lignes = lire_lignes(listes[0]) if listes else []
        if lignes:
            index = next((i for i, l in enumerate(lignes) if cheptel in l), None)
            if index is None:
                raise LookupError(f"Cheptel {cheptel} absent des résultats de recherche")
            selectionner_ligne(listes[0], index)
            cliquer(d, "VALIDER (F12)")
            break
        pause(0.5)
    while time.time() < fin:
        if ecran_suivant_pret():
            return
        pause(0.5)
    raise TimeoutError(f"Éleveur {cheptel} : l'écran suivant ne s'est pas affiché")


def aller_a(driver: JABDriver, chemin: str, sep: str = " > ", essais: int = 2):
    """Suit un chemin de menus/boutons, ex. « Bovin > Taureau > F6 CONSULTER ».

    Si un menu reste introuvable (GENICIA++ encore occupé à fermer l'écran précédent), retour à l'accueil et nouvel
    essai : ce ne sont que des clics de navigation, rien n'est validé.
    """
    for essai in range(essais):
        try:
            for etape in chemin.split(sep):
                cliquer(driver, etape.strip())
                pause(0.5)
                if dialogues_ouverts():
                    raise RuntimeError(f"Une boîte de dialogue s'est ouverte : {dialogues_ouverts()}")
            return
        except TimeoutError:
            if essai == essais - 1:
                raise
            print(f"   Menu « {chemin} » pas encore accessible : nouvel essai")
            quitter_ecran(driver)
            pause(3)


def quitter_ecran(driver: JABDriver, max_niveaux: int = 6):
    """Revient à l'accueil avec QUITTER (ESC), sans jamais valider.

    S'arrête (sans rien cliquer) si une boîte de dialogue apparaît.
    """
    for _ in range(max_niveaux):
        if dialogues_ouverts():
            raise RuntimeError(f"Boîte de dialogue ouverte, arrêt par sécurité : {dialogues_ouverts()}")
        if titre_fenetre_principale() == "ACCUEIL":
            return
        try:
            cliquer(driver, "QUITTER (ESC)", timeout=3)
        except (TimeoutError, JABException):   # écran en cours de chargement : on réessaie au tour suivant
            pass
        pause(1)


# ---------------------------------------------------------------- application

def identifiants():
    ident = keyring.get_password("GENICIA++", "identifiant")
    mdp = keyring.get_password("GENICIA++", ident) if ident else None
    if not ident or not mdp:
        raise SystemExit("Identifiants absents : lancer python enregistrer_identifiants.py")
    return ident, mdp


def application_ouverte() -> bool:
    return any("genicia++ v" in w.window_text().lower() and w.class_name() == "SunAwtFrame"
               for w in fenetres_java())


def _pids_genicia() -> list[int]:
    """Processus Java de GENICIA++ en cours (javaw … psaihm.StructAccueilIHM), avec ou sans fenêtre."""
    commande = ("Get-CimInstance Win32_Process -Filter \"name='javaw.exe'\" | "
                "Where-Object { $_.CommandLine -match 'StructAccueilIHM' } | ForEach-Object { $_.ProcessId }")
    try:
        sortie = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, text=True,
                                timeout=60, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [int(x) for x in sortie.split() if x.isdigit()]


def _pids_sans_fenetre() -> list[int]:
    avec_fenetre = {w.process_id() for w in fenetres_java()}
    return [pid for pid in _pids_genicia() if pid not in avec_fenetre]


def _arreter_instances_bloquees():
    """Arrête les GENICIA++ sans aucune fenêtre (bloqués au démarrage ou à la fermeture). Jamais une instance avec
    fenêtre : elle peut être utilisée par quelqu'un."""
    for pid in _pids_sans_fenetre():
        print(f"   GENICIA++ bloqué sans fenêtre (processus {pid}) : arrêt forcé")
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)


def _attendre_fin_instance_precedente(timeout: float = 60):
    """Après « Quitter », GENICIA++ met un moment à s'arrêter complètement (Java + base de données). Le relancer
    pendant ce temps le bloque au démarrage, sans aucune fenêtre. On attend donc la fin de l'instance précédente,
    puis on arrête ce qui reste (sans fenêtre)."""
    fin = time.time() + timeout
    while _pids_sans_fenetre():
        if time.time() > fin:
            _arreter_instances_bloquees()
            pause(5)
            return
        pause(2)


def lancer_et_connecter(timeout: float = 180, attente_demarrage: float = 90) -> JABDriver:
    """Lance GENICIA++ si besoin, se connecte, et renvoie la fenêtre principale.

    Jamais d'attente sans fin : si la fenêtre de connexion n'apparaît pas en `attente_demarrage` secondes, l'instance
    bloquée (sans fenêtre) est arrêtée et GENICIA++ relancé une fois ; au 2e échec, erreur.
    """
    if not application_ouverte():
        if any("informations de session" in w.window_text().lower() for w in fenetres_java()):
            login = attendre_fenetre("Informations de session", timeout)
        else:
            _attendre_fin_instance_precedente()
            for essai in range(2):
                subprocess.Popen([EXE], cwd=DOSSIER)
                try:
                    login = attendre_fenetre("Informations de session", attente_demarrage)
                    break
                except TimeoutError:
                    if essai:
                        raise TimeoutError(f"GENICIA++ ne s'ouvre pas : aucune fenêtre de connexion après "
                                           f"{attente_demarrage:.0f} s (2 essais)") from None
                    print(f"   GENICIA++ ne s'affiche pas après {attente_demarrage:.0f} s : arrêt et relance")
                    _arreter_instances_bloquees()
                    pause(5)
        _se_connecter(login)
    return attendre_fenetre("GENICIA++ v", timeout, classe="SunAwtFrame")


def _se_connecter(login: JABDriver, essais: int = 2, attente: float = 120):
    """Saisit l'identifiant et le mot de passe (jamais affiché), clique OK, puis vérifie que la connexion aboutit
    (la fenêtre principale s'ouvre). Saisie refaite une fois si l'identifiant ne s'est pas écrit (fenêtre pas encore
    prête). Jamais de nouvelle saisie après OK : pendant une connexion en cours, GENICIA++ la refuserait."""
    ident, mdp = identifiants()
    for essai in range(essais):
        fin = time.time() + 30                    # champs prêts ?
        while not (visibles(login, "text") and visibles(login, "password text")):
            if time.time() > fin:
                raise TimeoutError("Fenêtre de connexion GENICIA++ : champs de saisie introuvables")
            pause(0.5)
        pause(1)
        champ = visibles(login, "text")[0]
        ecrire(champ, ident)
        ecrire(visibles(login, "password text")[0], mdp)
        if (champ.text or "").strip() != ident:
            print("   Saisie de l'identifiant non prise en compte : nouvelle saisie")
            continue
        cliquer(login, "OK")
        fin = time.time() + attente
        while time.time() < fin:
            if application_ouverte():
                return
            pause(0.5)
        raise TimeoutError(f"Connexion à GENICIA++ sans réponse : fenêtre principale absente {attente:.0f} s après OK")
    raise RuntimeError("Fenêtre de connexion GENICIA++ : l'identifiant ne s'écrit pas dans le champ")


def quitter_application(driver: JABDriver, timeout: float = 60):
    """Ferme GENICIA++ proprement depuis l'accueil : Génicia > Quitter -> boîte « Confirmation »
    (« Confirmez-vous la sortie de l'application ? ») -> OUI. La base (dbeng9) s'arrête avec l'application.

    Refuse de quitter si GENICIA++ n'est pas à l'accueil ou si une boîte est ouverte (rien n'est cliqué).
    Clics souris : la boîte de confirmation est modale (un clic accessible bloquerait le bridge).
    Le processus javaw ne disparaît qu'à la fin du programme Python (il garde la connexion au bridge).
    """
    if dialogues_ouverts():
        raise RuntimeError(f"Boîte de dialogue ouverte, GENICIA++ laissé ouvert : {dialogues_ouverts()}")
    if titre_fenetre_principale() != "ACCUEIL":
        raise RuntimeError(f"GENICIA++ n'est pas à l'accueil ({titre_fenetre_principale()}), laissé ouvert")

    def ouvrir_menu():      # le clic sur le menu est parfois ignoré juste après un retour à l'accueil : on reclique
        for _ in range(3):
            cliquer_souris(driver, "Génicia", "menu")
            try:
                attendre_element(driver, "Quitter", "menu item", timeout=5)
                return
            except TimeoutError:
                pause(1)
        raise TimeoutError("Le menu « Génicia » ne s'ouvre pas (entrée « Quitter » introuvable)")

    pause(1)           # laisse l'accueil finir de s'afficher

    boite = ouvrir_dialogue(driver, driver, "Quitter", "Confirmation", role="menu item", avant=ouvrir_menu)
    message = " ".join(_nom(e) or "" for e in elements_affiches(boite) if _role(e) == "label")
    if "sortie de l'application" not in message:
        raise RuntimeError(f"Boîte « Confirmation » inattendue, rien n'est cliqué : {message}")
    cliquer_souris(boite, "OUI", "push button")
    fin = time.time() + timeout
    while time.time() < fin:
        if not application_ouverte():
            return
        pause(0.5)
    raise TimeoutError("GENICIA++ ne s'est pas fermé après OUI")
