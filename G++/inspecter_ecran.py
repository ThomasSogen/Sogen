"""Étape 2 : afficher tous les éléments des fenêtres GENICIA++ ouvertes
(boutons, champs, menus, tableaux...).

Utilise Java Access Bridge. Lecture seule : ne clique sur rien, ne tape rien.
Résultat dans le fichier arbre_interface.txt.

Lancement :  python etape2_interface.py
"""
from pathlib import Path

from pywinauto import Desktop
from pyjab.jabdriver import JABDriver

FICHIER = Path(__file__).with_name("arbre_interface.txt")
DLL_BRIDGE = r"C:\Program Files\Java\jre1.8.0_25\bin\WindowsAccessBridge-64.dll"


def fenetres_genicia():
    """Toutes les fenêtres Java visibles du processus GENICIA++ (accueil + fiches + dialogues)."""
    fenetres = [w for w in Desktop(backend="win32").windows(visible_only=True)
                if w.class_name() in ("SunAwtFrame", "SunAwtDialog")]
    accueil = [w for w in fenetres if "genicia" in w.window_text().lower()]
    if not accueil:
        raise SystemExit("Fenêtre GENICIA++ introuvable : le logiciel est-il ouvert ?")
    pid = accueil[0].process_id()
    return [w for w in fenetres if w.process_id() == pid]


def main():
    total = 0
    with open(FICHIER, "w", encoding="utf-8") as f:
        f.write("Éléments des fenêtres GENICIA++\n")
        f.write("Format : type | nom | description | états | position\n")
        for w in fenetres_genicia():
            f.write(f"\n\n######## FENÊTRE : {w.window_text()!r} ({w.class_name()})\n\n")
            driver = JABDriver(hwnd=w.handle, bridge_dll=DLL_BRIDGE)
            arbre = driver.root_element.walk(limit=5000)
            for profondeur, e in arbre:
                b = e["bounds"]
                pos = f"x={b.get('x')} y={b.get('y')}" if b else ""
                f.write(f"{'    ' * profondeur}{e['role']} | {e['name']!r} | "
                        f"{e['description']!r} | {e['states']} | {pos}\n")
            if arbre.truncated:
                f.write("\n(liste coupée à 5000 éléments)\n")
            total += len(arbre)
            print(f"{w.window_text()[:60]!r} : {len(arbre)} éléments")

    print(f"Total {total} éléments -> {FICHIER}")


if __name__ == "__main__":
    main()
