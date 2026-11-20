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
import threading
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

# ---------------------------------------------------------------- journal détaillé (rapport.txt)
# Chaque bouton cherché / cliqué, champ rempli, valeur lue, écran attendu est écrit (heure à la seconde) : le rapport
# montre la DERNIÈRE action tentée avant un blocage. Le veilleur arrête l'exécution après 1 min sans aucune ligne ;
# pendant une attente normale (démarrage, aperçu…), pause() écrit donc un signe de vie toutes les 20 s.
# Une action bloquée DANS Java (appel qui ne rend pas la main) n'écrit plus rien : sa ligne est la dernière du rapport.

_dernier_signe = [time.time()]
_derniere_action = [time.time()]  # dernière VRAIE action (les signes de vie « … » ne comptent pas)
_attente_en_cours = [""]          # ce que le programme attend (repris dans les signes de vie)
SIGNE_DE_VIE = 20                 # secondes


def journal(message: str, signe_de_vie: bool = False):
    """Ligne du journal détaillé (rapport.txt), avec l'heure."""
    print(f"   · {time.strftime('%H:%M:%S')} {message}", flush=True)
    _dernier_signe[0] = time.time()
    if not signe_de_vie:
        _derniere_action[0] = time.time()


# ---------------------------------------------------------------- débloqueur (clic dans une zone vide)
# Constaté par l'utilisateur (19/11/2026) : GENICIA++ reste parfois bloqué indéfiniment, comme s'il attendait
# quelque chose ; un simple clic n'importe où sur la fenêtre le débloque. Le programme principal, coincé dans un appel
# à Java, ne peut pas cliquer lui-même : un fil d'exécution séparé surveille donc l'avancement et, après
# DEBLOCAGE_APRES secondes sans aucune action, clique dans la BARRE DE TITRE de la fenêtre GENICIA++ (partie gauche :
# aucun bouton, rien n'est validé), puis le programme reprend normalement son chemin.
DEBLOCAGE_APRES = 15              # secondes sans action avant un clic de déblocage
DEBLOCAGES_MAX = 3                # clics au plus pour un même blocage
_verrou_souris = threading.Lock() # le débloqueur ne clique jamais pendant un clic du programme
_debloqueur_actif = [False]


def _fenetre_au_premier_plan_genicia():
    """Fenêtre GENICIA++ à cliquer : la boîte de dialogue ouverte s'il y en a une, sinon la fenêtre principale."""
    fenetres = fenetres_java()
    boites = [w for w in fenetres if w.class_name() == "SunAwtDialog"]
    principales = [w for w in fenetres if "genicia" in w.window_text().lower() and w.class_name() == "SunAwtFrame"]
    return (boites or principales or [None])[0]


def clic_zone_vide():
    """Clic dans la barre de titre (zone sans bouton) de la fenêtre GENICIA++ au premier plan."""
    fenetre = _fenetre_au_premier_plan_genicia()
    if fenetre is None:
        return False
    r = fenetre.rectangle()
    x, y = r.left + max(60, (r.right - r.left) // 4), r.top + 10
    with _verrou_souris:
        mouse.click(coords=(x, y))
    journal(f"clic de déblocage dans une zone vide (barre de titre de « {fenetre.window_text()[:40]} », "
            f"x={x}, y={y}) ; le programme reprend son chemin", signe_de_vie=True)
    return True


def _surveiller_blocages():
    deblocages, reference = 0, _derniere_action[0]
    while _debloqueur_actif[0]:
        time.sleep(1)
        if _derniere_action[0] != reference:            # le programme a avancé : compteur remis à zéro
            deblocages, reference = 0, _derniere_action[0]
        inactif = time.time() - reference
        if deblocages < DEBLOCAGES_MAX and inactif >= DEBLOCAGE_APRES * (deblocages + 1):
            if _verrou_souris.locked():                 # un clic du programme est en cours
                continue
            journal(f"aucune action depuis {inactif:.0f} s : GENICIA++ semble attendre (blocage)", signe_de_vie=True)
            deblocages += 1
            try:
                clic_zone_vide()
            except Exception as erreur:                  # le débloqueur ne doit jamais faire échouer l'ordre
                journal(f"clic de déblocage impossible ({erreur})", signe_de_vie=True)


def demarrer_debloqueur():
    """Lance la surveillance des blocages (une seule fois ; s'arrête avec le programme)."""
    if not _debloqueur_actif[0]:
        _debloqueur_actif[0] = True
        threading.Thread(target=_surveiller_blocages, daemon=True, name="debloqueur").start()
        journal(f"surveillance des blocages active (clic dans une zone vide après {DEBLOCAGE_APRES} s sans action)")


def _attente(description: str):
    """Mémorise ce qui est attendu, pour les signes de vie écrits par pause()."""
    _attente_en_cours[0] = description


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
        if time.time() - _dernier_signe[0] >= SIGNE_DE_VIE:
            journal(f"… toujours en attente : {_attente_en_cours[0] or 'traitement en cours'}", signe_de_vie=True)
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
    journal(f"attente de la fenêtre « {morceau_titre} » (max {timeout:.0f} s)")
    _attente(f"fenêtre « {morceau_titre} »")
    fin = time.time() + timeout
    while time.time() < fin:
        for w in fenetres_java():
            if morceau_titre.lower() in w.window_text().lower() and (classe is None or w.class_name() == classe):
                journal(f"fenêtre trouvée : « {w.window_text()} » ; connexion à Java Access Bridge…")
                driver = JABDriver(hwnd=w.handle, bridge_dll=DLL_BRIDGE)
                journal("Java Access Bridge connecté")
                return driver
        pause(0.5)
    titres = [w.window_text() for w in fenetres_java()]
    journal(f"fenêtre « {morceau_titre} » introuvable (fenêtres : {titres})")
    raise TimeoutError(f"Fenêtre « {morceau_titre} » introuvable. Fenêtres ouvertes : {titres}")


def attendre_dialogue(driver: JABDriver, titre: str, timeout: float = 60) -> JABElement:
    """Attend une boîte de dialogue Java (titre exact) et renvoie sa racine.

    pyjab refuse parfois les boîtes de dialogue ; on passe donc directement par le bridge
    déjà ouvert sur la fenêtre principale.
    """
    journal(f"attente de la boîte « {titre} » (max {timeout:.0f} s)")
    _attente(f"boîte « {titre} »")
    fin = time.time() + timeout
    while time.time() < fin:
        for w in fenetres_java():
            if w.window_text() == titre:
                vmid, ctx = c_long(), JOBJECT64()
                if driver.bridge.getAccessibleContextFromHWND(w.handle, byref(vmid), byref(ctx)):
                    journal(f"boîte « {titre} » ouverte")
                    return JABElement(driver.bridge, w.handle, vmid, ctx)
        pause(0.5)
    journal(f"boîte « {titre} » introuvable (boîtes ouvertes : {dialogues_ouverts()})")
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


ROLES_MENUS = ("menu bar", "popup menu")
ROLES_LISTES = ("list", "table", "tree")


def elements_affiches(cible: Cible, menus: bool = True, listes: bool = False):
    """Parcourt les éléments affichés, sans descendre dans les zones cachées.

    Plus robuste que les recherches de pyjab, qui s'arrêtent à la première erreur
    de Java Access Bridge (éléments cachés ou périmés).
    menus=False : ne descend pas dans les menus. Un menu déroulant reste ouvert quelques secondes après une
    navigation ; le parcourir pendant qu'il se referme bloque Java Access Bridge (jusqu'à ~30 s par recherche).
    listes=False (par défaut) : ne descend pas dans le CONTENU des listes (la liste elle-même est rendue). Les lignes
    se lisent avec lire_lignes(). Sur « ANALYSE D'UN BILAN ELEVEUR » avec tout l'historique, la liste a des milliers
    de cellules : les parcourir pour chercher un libellé (« Fin ») dépassait la minute (test 6, 19/11/2026).
    Pendant un long parcours, un signe de vie est écrit toutes les SIGNE_DE_VIE secondes.
    """
    traiter_messages()
    pile, vus = [_racine(cible)], 0
    while pile:
        e = pile.pop()
        vus += 1
        if time.time() - _dernier_signe[0] >= SIGNE_DE_VIE:
            journal(f"… lecture de l'écran en cours ({vus} éléments parcourus)", signe_de_vie=True)
        try:
            etats = e.states_en_us or []
        except JABException:
            continue
        if "showing" not in etats:
            continue
        yield e
        role = _role(e)
        if (not menus and role in ROLES_MENUS) or (not listes and role in ROLES_LISTES):
            continue
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
    for e in elements_affiches(cible, menus=role in ("menu", "menu item")):
        if _role(e) != role:
            continue
        try:
            b = e.bounds
        except JABException:          # élément disparu entre-temps (écran ou liste en cours de rechargement)
            continue
        places.append(((b["y"], b["x"]), e))
    return [e for _, e in sorted(places, key=lambda p: p[0])]


def attendre_element(cible: Cible, nom: str, role: str = None, timeout: float = 30):
    """Attend qu'un élément affiché porte exactement ce nom (et ce type), et le renvoie.
    Les menus ne sont parcourus que pour un menu / une entrée de menu, ou si le type n'est pas précisé et que
    l'élément n'a pas été trouvé hors des menus (ex. étapes de aller_a)."""
    debut = time.time()
    fin = debut + timeout
    quoi = f"« {nom.strip()} »" + (f" ({role})" if role else "")
    journal(f"recherche de {quoi}…")
    _attente(f"élément {quoi}")
    if role in ("menu", "menu item"):
        passages = (True,)
    elif role:
        passages = (False,)
    else:
        passages = (False, True)
    while True:
        for menus in passages:
            for e in elements_affiches(cible, menus=menus):
                if _nom(e) == nom and (role is None or _role(e) == role):
                    journal(f"trouvé {quoi} en {time.time() - debut:.1f} s")
                    return e
        if time.time() > fin:
            journal(f"{quoi} introuvable après {timeout:.0f} s")
            raise TimeoutError(f"Élément « {nom} » introuvable à l'écran")
        pause(0.5)


def trouver(cible: Cible, nom: str, role: str = None):
    """Premier élément portant ce nom, même caché (ex. entrée d'un menu replié)."""
    journal(f"recherche (même caché) de « {nom} »" + (f" ({role})" if role else ""))
    pile = [_racine(cible)]
    while pile:
        e = pile.pop()
        if _nom(e) == nom and (role is None or _role(e) == role):
            journal(f"trouvé « {nom} »")
            return e
        pile.extend(enfants(e))
    journal(f"« {nom} » introuvable")
    raise LookupError(f"Élément « {nom} » introuvable")


# ---------------------------------------------------------------- rythme des clics (comme à la main)
# Cliquer trop vite (plusieurs clics dans la même seconde) laissait des menus ouverts et figeait GENICIA++ (test 6,
# 19/11/2026). Règles : au moins PAUSE_ENTRE_CLICS secondes entre deux clics ; si un clic change d'écran, on attend
# que le nouvel écran soit stable (même titre pendant ECRAN_STABLE s) avant toute autre action.
PAUSE_ENTRE_CLICS = 1.0
ECRAN_STABLE = 1.0
CHARGEMENT_MAX = 20
_dernier_clic = [0.0]


def _avant_clic():
    reste = PAUSE_ENTRE_CLICS - (time.time() - _dernier_clic[0])
    if reste > 0:
        pause(reste)
    return titre_fenetre_principale(), tuple(dialogues_ouverts())


def _apres_clic(etat_avant):
    """Attend la fin du chargement si le clic a changé d'écran ou ouvert/fermé une boîte."""
    pause(0.3)
    etat = (titre_fenetre_principale(), tuple(dialogues_ouverts()))
    if etat != etat_avant:
        journal(f"changement d'écran : « {etat[0]} »" + (f", boîtes {list(etat[1])}" if etat[1] else "")
                + " ; attente de la fin du chargement")
        _attente("fin du chargement de l'écran")
        stable_depuis, fin = time.time(), time.time() + CHARGEMENT_MAX
        while time.time() < fin and time.time() - stable_depuis < ECRAN_STABLE:
            pause(0.25)
            nouvel = (titre_fenetre_principale(), tuple(dialogues_ouverts()))
            if nouvel != etat:
                etat, stable_depuis = nouvel, time.time()
        journal(f"écran chargé : « {etat[0]} »")
    _dernier_clic[0] = time.time()


def cliquer(cible: Cible, nom: str, role: str = None, timeout: float = 30):
    """Clic accessible. NE PAS utiliser pour un bouton qui ouvre une fenêtre bloquante."""
    e = attendre_element(cible, nom, role, timeout)
    avant = _avant_clic()
    journal(f"clic sur « {nom.strip()} »")
    e.click()
    journal(f"clic sur « {nom.strip()} » effectué")
    _apres_clic(avant)


def cliquer_souris(cible: Cible, nom: str, role: str = None, timeout: float = 30):
    """Vrai clic souris au centre de l'élément, après mise au premier plan de sa fenêtre."""
    clic_souris_element(attendre_element(cible, nom, role, timeout))


def clic_souris_element(e: JABElement):
    """Vrai clic souris au centre d'un élément déjà trouvé (ex. bouton sans nom)."""
    nom = _nom(e).strip()
    avant = _avant_clic()
    if not premier_plan(e.hwnd):
        journal(f"fenêtre impossible à mettre au premier plan pour « {nom} »")
        raise RuntimeError(f"Impossible de mettre la fenêtre au premier plan pour cliquer sur « {_nom(e)} »")
    b = e.bounds
    x, y = b["x"] + b["width"] // 2, b["y"] + b["height"] // 2
    journal(f"clic souris sur « {nom} » (x={x}, y={y})")
    # clic décomposé : un clic instantané est parfois ignoré par Java ; verrou : pas de clic de déblocage en même temps
    with _verrou_souris:
        mouse.move(coords=(x, y)); pause(0.3)
        mouse.press(coords=(x, y)); pause(0.15)
        mouse.release(coords=(x, y))
    journal(f"clic souris sur « {nom} » effectué")
    _apres_clic(avant)


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
    journal(f"choix de « {option} » dans la liste {getattr(combo, 'libelle_genicia', '')}".rstrip())
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
            journal(f"valeur lue dans la liste {getattr(combo, 'libelle_genicia', '')} : « {_nom(e)} »")
            return _nom(e)
        pile.extend(enfants(e))
    journal(f"valeur lue dans la liste {getattr(combo, 'libelle_genicia', '')} : (vide)")
    return ""


def liste_deroulante_par_libelle(cible: Cible, texte: str) -> JABElement:
    """Liste déroulante affichée sur la même ligne, à droite du libellé `texte`."""
    lb = libelle(cible, texte).bounds
    candidats = [c for c in visibles(cible, "combo box")
                 if abs(c.bounds["y"] - lb["y"]) < 20 and c.bounds["x"] > lb["x"]]
    if not candidats:
        journal(f"aucune liste déroulante à droite de « {texte} »")
        raise LookupError(f"Aucune liste déroulante à droite de « {texte} »")
    combo = min(candidats, key=lambda c: c.bounds["x"])
    combo.libelle_genicia = f"« {texte} »"      # repris par le journal (choix / valeur lue)
    journal(f"liste déroulante « {texte} » trouvée")
    return combo


def ecrire(element, texte: str, masquer: bool = False):
    """Remplit un champ. masquer=True : la valeur n'apparaît jamais dans le journal (mot de passe…)."""
    champ = getattr(element, "libelle_genicia", "") or "(champ)"
    journal(f"saisie dans {champ} : " + ("•••••• (masqué)" if masquer else f"« {texte} »"))
    element.send_text(texte)
    journal(f"saisie dans {champ} effectuée")


def vider_champ(cible: Cible, texte_libelle: str, obligatoire: bool = True):
    """Efface le champ à droite du libellé (ex. « N° Cheptel » prérempli avec le dernier cheptel recherché) et vérifie
    qu'il est vide. obligatoire=False : champ absent de l'écran = rien à faire."""
    try:
        champ = champ_par_libelle(cible, texte_libelle)
    except LookupError:
        if obligatoire:
            raise
        return
    if not (lire(champ) or "").strip():
        return
    ecrire(champ, "")
    if (lire(champ) or "").strip():
        raise RuntimeError(f"Le champ « {texte_libelle} » n'a pas pu être vidé avant la recherche")


def lire(element, quoi: str = "") -> str:
    """Texte d'un champ affiché, écrit dans le journal (valeur récupérée)."""
    texte = element.text or ""
    journal(f"valeur lue {quoi or getattr(element, 'libelle_genicia', '') or '(champ)'} : « {texte.strip()} »")
    return texte


def _texte_libelle(nom: str) -> str:
    """'<html><u>N° Cheptel :</u></html>' -> 'n° cheptel'"""
    t = re.sub(r"<[^>]+>", "", nom or "")
    return re.sub(r"\s+", " ", t).strip().rstrip(":").strip().lower()


def libelle(cible: Cible, texte: str) -> JABElement:
    """Libellé affiché correspondant à `texte` : exact d'abord, sinon « commence par »."""
    journal(f"recherche du libellé « {texte} »…")
    labels = visibles(cible, "label")
    cherche = _texte_libelle(texte)
    for test in (lambda t: t == cherche, lambda t: t.startswith(cherche)):
        trouves = [l for l in labels if test(_texte_libelle(_nom(l)))]
        if trouves:
            return trouves[0]
    journal(f"libellé « {texte} » introuvable ({len(labels)} libellés à l'écran)")
    raise LookupError(f"Libellé « {texte} » introuvable")


def champ_par_libelle(cible: Cible, texte: str):
    """Champ de saisie affiché sur la même ligne, à droite du libellé `texte`."""
    lb = libelle(cible, texte).bounds
    candidats = [t for t in visibles(cible, "text")
                 if abs(t.bounds["y"] - lb["y"]) < 20 and t.bounds["x"] > lb["x"]]
    if not candidats:
        journal(f"aucun champ à droite de « {texte} »")
        raise LookupError(f"Aucun champ à droite de « {texte} »")
    champ = min(candidats, key=lambda t: t.bounds["x"])
    champ.libelle_genicia = f"« {texte} »"      # repris par le journal (saisie / valeur lue)
    journal(f"champ « {texte} » trouvé")
    return champ


# ---------------------------------------------------------------- listes

def liste_affichee(cible: Cible, index: int = 0) -> JABElement:
    return visibles(cible, "list")[index]


def lire_lignes(liste: JABElement) -> list[list[str]]:
    """Valeurs de chaque ligne d'une liste GENICIA++ (étiquettes dans l'ordre des colonnes),
    y compris les lignes hors écran."""
    return [[_nom(c) for c in enfants(l) if _role(c) == "label"] for l in enfants(liste)]


def attendre_lignes(cible: Cible, timeout: float = 30) -> list[list[str]]:
    journal("lecture de la liste affichée…")
    _attente("lignes de la liste")
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            lignes = lire_lignes(liste_affichee(cible))
            if lignes:
                journal(f"liste lue : {len(lignes)} ligne(s)")
                return lignes
        except (IndexError, JABException):    # liste pas encore affichée, ou en cours de rechargement
            pass
        pause(0.5)
    journal(f"liste vide après {timeout:.0f} s")
    return []


def selectionner_ligne(liste: JABElement, index: int):
    journal(f"sélection de la ligne {index + 1} de la liste")
    liste.bridge.clearAccessibleSelectionFromContext(liste.vmid, liste.accessible_context)
    liste.bridge.addAccessibleSelectionFromContext(liste.vmid, liste.accessible_context, index)
    journal(f"ligne {index + 1} sélectionnée")


# ---------------------------------------------------------------- navigation

def titre_fenetre_principale() -> str:
    for w in fenetres_java():
        if "genicia++ v" in w.window_text().lower() and w.class_name() == "SunAwtFrame":
            t = w.window_text()
            return t[t.rfind("[") + 1:t.rfind("]")] if "[" in t else "ACCUEIL"
    return ""


def attendre_ecran(titre: str, timeout: float = 30):
    """Attend que la fenêtre principale affiche l'écran `titre` (ex. « BILAN ELEVEUR »)."""
    journal(f"attente de l'écran « {titre} » (écran actuel : « {titre_fenetre_principale()} »)")
    _attente(f"écran « {titre} »")
    fin = time.time() + timeout
    while time.time() < fin:
        if titre_fenetre_principale().lower() == titre.lower():
            journal(f"écran « {titre} » affiché")
            return
        pause(0.5)
    journal(f"écran « {titre} » non atteint après {timeout:.0f} s (écran actuel : « {titre_fenetre_principale()} »)")
    raise TimeoutError(f"Écran « {titre} » non atteint (écran actuel : {titre_fenetre_principale()})")


def rechercher_eleveur(d: JABDriver, cheptel: str, ecran_suivant_pret, timeout: float = 30):
    """Écran de recherche d'éleveur (commun à plusieurs menus) : N° Cheptel -> Rechercher (F3).

    - un seul éleveur trouvé : GENICIA++ passe seul à l'écran suivant ;
    - plusieurs : sélection de la ligne du cheptel puis VALIDER (F12).
    `ecran_suivant_pret()` doit renvoyer True quand l'écran suivant est affiché.
    """
    attendre_element(d, "Rechercher (F3)")
    vider_champ(d, "Nom", obligatoire=False)     # un nom resté écrit fausserait la recherche par cheptel
    champ = champ_par_libelle(d, "N° Cheptel")   # prérempli avec le dernier cheptel : la saisie le remplace
    ecrire(champ, cheptel)
    if re.sub(r"\D", "", lire(champ) or "") != re.sub(r"\D", "", cheptel):
        raise RuntimeError(f"Le n° de cheptel {cheptel} ne s'est pas écrit correctement dans « N° Cheptel »")
    cliquer(d, "Rechercher (F3)")
    journal(f"attente du résultat de la recherche du cheptel {cheptel}")
    _attente(f"résultat de la recherche du cheptel {cheptel}")
    fin = time.time() + timeout
    while time.time() < fin:
        if ecran_suivant_pret():
            journal(f"un seul éleveur trouvé : écran suivant « {titre_fenetre_principale()} »")
            return
        listes = visibles(d, "list")
        lignes = lire_lignes(listes[0]) if listes else []
        if lignes:
            journal(f"{len(lignes)} éleveur(s) dans les résultats de recherche")
            index = next((i for i, l in enumerate(lignes) if cheptel in l), None)
            if index is None:
                journal(f"cheptel {cheptel} absent des résultats")
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


# ---------------------------------------------------------------- recherche d'un éleveur par son nom

FORMES_JURIDIQUES = {"EARL", "GAEC", "SCEA", "SARL", "SAS", "SA", "SCI", "EI", "M", "MR", "MME", "MLLE",
                     "MONSIEUR", "MADAME", "MADEMOISELLE"}
LIBELLES_NOM = ("Nom",)   # champ « Nom : » de l'écran « Recherche éleveur » (confirmé par l'utilisateur le 19/11/2026)
MOTIF_CHEPTEL = re.compile(r"^(?:FR)?\s*(\d{2})\s*(\d{3})\s*(\d{3})$", re.I)


def nom_de_recherche(nom: str) -> str:
    """« EARL Durand » -> « DURAND » : majuscules sans accents, sans forme juridique ni civilité."""
    import unicodedata
    texte = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode().upper()
    mots = [m for m in re.split(r"[\s.,]+", texte) if m and m.replace(".", "") not in FORMES_JURIDIQUES]
    return " ".join(mots)


def _cheptel_de(texte: str) -> str:
    trouve = MOTIF_CHEPTEL.match((texte or "").strip())
    return "".join(trouve.groups()) if trouve else ""


def _cheptel_affiche(d: JABDriver) -> str:
    """N° de cheptel affiché sur l'écran de l'éleveur (champ à droite de « N° Cheptel », sinon seul n° à 8 chiffres
    de l'écran)."""
    try:
        cheptel = _cheptel_de(lire(champ_par_libelle(d, "N° Cheptel")))
        if cheptel:
            return cheptel
    except LookupError:
        pass
    trouves = {_cheptel_de(_nom(e)) for e in visibles(d, "label")} | {_cheptel_de(e.text or "")
                                                                       for e in visibles(d, "text")}
    trouves.discard("")
    journal(f"n° de cheptel lus à l'écran : {sorted(trouves) or 'aucun'}")
    if len(trouves) != 1:
        raise LookupError(f"N° de cheptel illisible sur l'écran « {titre_fenetre_principale()} »")
    return trouves.pop()


def identifier_cheptel(d: JABDriver, nom_eleveur: str, timeout: float = 30) -> str:
    """N° de cheptel d'un éleveur désigné seulement par son nom : écran « Recherche éleveur » (Administratif > Bilan
    Eleveur), champ du nom, Rechercher (F3). Lecture seule, retour à l'accueil ensuite.
    - un seul éleveur : GENICIA++ ouvre sa fiche « BILAN ELEVEUR », le n° de cheptel y est lu ;
    - plusieurs lignes : on garde celles qui contiennent le nom cherché ; une seule -> son cheptel ; sinon
      LookupError avec la liste des éleveurs possibles (jamais de choix au hasard)."""
    recherche = nom_de_recherche(nom_eleveur)
    if not recherche:
        raise LookupError("Ni n° de cheptel ni nom d'éleveur : éleveur impossible à identifier")
    journal(f"recherche de l'éleveur par son nom : « {recherche} » (mail : « {nom_eleveur} »)")
    try:
        aller_a(d, "Administratif > Bilan Eleveur")
        attendre_ecran("Recherche éleveur")
        attendre_element(d, "Rechercher (F3)")
        champ = None
        for texte in LIBELLES_NOM:
            try:
                champ = champ_par_libelle(d, texte)
                break
            except LookupError:
                continue
        if champ is None:
            libelles = [_texte_libelle(_nom(l)) for l in visibles(d, "label")]
            raise LookupError(f"Champ du nom introuvable sur « Recherche éleveur » (libellés affichés : {libelles})")
        vider_champ(d, "N° Cheptel")             # prérempli avec le dernier cheptel recherché : à effacer
        ecrire(champ, recherche)
        cliquer(d, "Rechercher (F3)")
        _attente(f"résultat de la recherche de « {recherche} »")
        fin = time.time() + timeout
        while time.time() < fin:
            if titre_fenetre_principale() == "BILAN ELEVEUR":
                cheptel = _cheptel_affiche(d)
                journal(f"un seul éleveur « {recherche} » : cheptel {cheptel}")
                return cheptel
            listes = visibles(d, "list")
            lignes = lire_lignes(listes[0]) if listes else []
            if lignes:
                journal(f"{len(lignes)} éleveur(s) trouvé(s) pour « {recherche} »")
                mots = recherche.split()
                retenues = [l for l in lignes
                            if all(re.search(rf"\b{re.escape(m)}\b", " ".join(l).upper()) for m in mots)]
                cheptels = {c for l in retenues for c in map(_cheptel_de, l) if c}
                if len(retenues) == 1 and len(cheptels) == 1:
                    cheptel = cheptels.pop()
                    journal(f"éleveur retenu : {' | '.join(retenues[0])} -> cheptel {cheptel}")
                    return cheptel
                possibles = " ; ".join(" | ".join(c for c in l if c) for l in (retenues or lignes)[:10])
                raise LookupError(f"Plusieurs éleveurs (ou aucun exactement) pour « {recherche} » : rien n'est fait. "
                                  f"Indiquer le n° de cheptel. Éleveurs possibles : {possibles}")
            pause(0.5)
        raise LookupError(f"Aucun éleveur trouvé pour « {recherche} » : indiquer le n° de cheptel")
    finally:
        quitter_ecran(d)


def aller_a(driver: JABDriver, chemin: str, sep: str = " > ", essais: int = 2):
    """Suit un chemin de menus/boutons, ex. « Administratif > Bilan Eleveur », comme à la main :
    - VRAI clic souris sur chaque étape (un clic « accessible » sur une entrée de menu ouvrait l'écran mais laissait
      le menu déroulé, ce qui figeait ensuite GENICIA++ : test 6 du 19/11/2026) ;
    - au moins 1 s entre deux clics, et attente de la fin du chargement d'un nouvel écran (voir _apres_clic) ;
    - si l'étape suivante n'apparaît pas après quelques secondes, le clic n'a pas été pris en compte : nouveau clic
      sur la même étape (3 fois au plus).
    Si un menu reste introuvable (GENICIA++ encore occupé à fermer l'écran précédent), retour à l'accueil et nouvel
    essai : ce ne sont que des clics de navigation, rien n'est validé.
    """
    etapes = [e.strip() for e in chemin.split(sep)]
    for essai in range(essais):
        try:
            journal(f"navigation : {chemin}")
            titre_depart = titre_fenetre_principale()
            for i, etape in enumerate(etapes):
                suivante = etapes[i + 1] if i + 1 < len(etapes) else None
                _cliquer_etape(driver, etape, suivante, titre_depart)
            return
        except TimeoutError:
            if essai == essais - 1:
                raise
            print(f"   Menu « {chemin} » pas encore accessible : nouvel essai")
            quitter_ecran(driver)
            pause(3)


ATTENTE_ETAPE_SUIVANTE = 4      # secondes : au-delà, le clic n'a pas été pris en compte


def _cliquer_etape(driver: JABDriver, etape: str, suivante, titre_depart: str, essais: int = 3):
    """Clic souris sur `etape`, puis vérifie qu'il a été pris en compte : l'étape `suivante` est disponible (menu
    déroulé), ou, pour la dernière étape, l'écran a changé. Sinon, nouveau clic sur la même étape."""
    for n in range(essais):
        if n and suivante is None:
            # dernière étape : si elle n'est plus affichée (menu refermé), le clic a été pris en compte et l'écran
            # est en train de s'ouvrir ; l'appelant attend l'écran voulu
            try:
                e = attendre_element(driver, etape, timeout=1)
            except TimeoutError:
                journal(f"« {etape} » n'est plus affiché : le clic a été pris en compte, l'écran s'ouvre")
                return
        else:
            e = attendre_element(driver, etape, timeout=30 if n == 0 else 5)
        clic_souris_element(e)
        if dialogues_ouverts():
            raise RuntimeError(f"Une boîte de dialogue s'est ouverte : {dialogues_ouverts()}")
        if suivante:
            try:
                attendre_element(driver, suivante, timeout=ATTENTE_ETAPE_SUIVANTE)
                return
            except TimeoutError:
                journal(f"« {suivante} » pas disponible : le clic sur « {etape} » n'a pas été pris en compte, "
                        "nouveau clic")
        else:
            fin = time.time() + ATTENTE_ETAPE_SUIVANTE
            while time.time() < fin:
                if titre_fenetre_principale() != titre_depart:
                    return
                pause(0.3)
            journal(f"l'écran n'a pas changé après le clic sur « {etape} » : nouveau clic")
    raise TimeoutError(f"Le clic sur « {etape} » n'est pas pris en compte ({essais} essais)")


def quitter_ecran(driver: JABDriver, max_niveaux: int = 6):
    """Revient à l'accueil avec QUITTER (ESC), sans jamais valider.

    S'arrête (sans rien cliquer) si une boîte de dialogue apparaît.
    """
    journal(f"retour à l'accueil (écran actuel : « {titre_fenetre_principale()} »)")
    for _ in range(max_niveaux):
        if dialogues_ouverts():
            journal(f"boîte ouverte, arrêt du retour à l'accueil : {dialogues_ouverts()}")
            raise RuntimeError(f"Boîte de dialogue ouverte, arrêt par sécurité : {dialogues_ouverts()}")
        if titre_fenetre_principale() == "ACCUEIL":
            journal("accueil atteint")
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
    journal("recherche des processus GENICIA++ (javaw) en cours…")
    try:          # 30 s max : pendant cet appel, aucun signe de vie ne peut être écrit (veilleur : 1 min)
        sortie = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, text=True,
                                timeout=30, creationflags=subprocess.CREATE_NO_WINDOW).stdout
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
    journal("GENICIA++ déjà ouvert" if application_ouverte() else "GENICIA++ fermé : lancement")
    if not application_ouverte():
        if any("informations de session" in w.window_text().lower() for w in fenetres_java()):
            login = attendre_fenetre("Informations de session", timeout)
        else:
            _attendre_fin_instance_precedente()
            for essai in range(2):
                journal(f"lancement de {EXE}")
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
        champ.libelle_genicia = "« Identifiant »"
        ecrire(champ, ident, masquer=True)
        mot_de_passe = visibles(login, "password text")[0]
        mot_de_passe.libelle_genicia = "« Mot de passe »"
        ecrire(mot_de_passe, mdp, masquer=True)        # jamais écrit dans le journal
        if (champ.text or "").strip() != ident:
            print("   Saisie de l'identifiant non prise en compte : nouvelle saisie")
            continue
        cliquer(login, "OK")
        journal(f"attente de la fenêtre principale après connexion (max {attente:.0f} s)")
        _attente("ouverture de GENICIA++ après connexion")
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

    journal("fermeture de GENICIA++ (Génicia > Quitter)")
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
