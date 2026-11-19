r"""File d'attente GENICIA++ : un seul programme pilote GENICIA++ à la fois sur ce PC, les autres attendent leur tour
dans l'ordre d'arrivée.

Pourquoi : GENICIA++ est piloté par de vrais clics souris sur UNE fenêtre. Deux programmes en même temps (veilleur +
lancement à la main de main.py ou executer_ordres.py, par exemple) cliqueraient l'un sur l'autre.

Utilisation :
    with tour_genicia("Facture 64284002"):
        ... tout le pilotage de GENICIA++ (connexion → fermeture) ...

Fonctionnement (tout est dans %LOCALAPPDATA%\GENICIA, propre au PC : chaque PC a son propre GENICIA++) :
  - execution.lock : verrouillé par le programme qui pilote GENICIA++. Windows libère le verrou tout seul si le
    programme s'arrête, même brutalement (plantage, PC éteint, programme tué par le veilleur).
  - file_attente\<heure d'arrivée>_<pid>.ticket : un ticket par programme en attente, verrouillé par lui tant qu'il
    vit. Le plus ancien ticket encore vivant passe en premier. Un ticket non verrouillé = programme disparu → supprimé.
Pendant l'attente, une ligne « ⏳ » est affichée chaque minute (signe de vie pour le veilleur).
"""
import msvcrt
import os
import time
from contextlib import contextmanager
from datetime import datetime

from config_genicia import FLUX

VERROU_EXECUTION = FLUX / "execution.lock"
FILE_ATTENTE = FLUX / "file_attente"
ATTENTE_MAX = 3600          # secondes : au-delà, on abandonne (GENICIA++ occupé anormalement longtemps)
INTERVALLE = 2              # secondes entre deux vérifications
INTERVALLE_MESSAGE = 60     # une ligne « en attente » par minute
MARQUEUR_ATTENTE = "⏳ GENICIA++ occupé"      # lus par le veilleur (veilleur_genicia.py) : ne pas modifier
MARQUEUR_TOUR = "▶️ Tour GENICIA++ obtenu"


class GeniciaOccupe(Exception):
    """Attente trop longue : GENICIA++ est resté occupé plus de ATTENTE_MAX secondes."""


def _verrouiller(fichier):
    """Verrou non bloquant sur le 1er octet. True si obtenu."""
    try:
        fichier.seek(0)
        msvcrt.locking(fichier.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _deverrouiller(fichier):
    try:
        fichier.seek(0)
        msvcrt.locking(fichier.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def _ticket_vivant(chemin):
    """Le programme qui a déposé ce ticket attend-il toujours ? (il garde son ticket verrouillé)"""
    try:
        with open(chemin, "a+") as f:
            if not _verrouiller(f):
                return True                 # verrouillé par son programme : vivant
            _deverrouiller(f)
    except PermissionError:
        return True                         # ouvert ailleurs : vivant
    except OSError:
        return False                        # déjà supprimé
    try:
        chemin.unlink()                     # programme disparu : ticket abandonné, on le retire de la file
    except OSError:
        pass
    return False


def _premier_de_la_file(mon_ticket):
    """Mon ticket est-il le plus ancien encore vivant ?"""
    for chemin in sorted(FILE_ATTENTE.glob("*.ticket")):
        if chemin.name == mon_ticket.name:
            return True
        if _ticket_vivant(chemin):
            return False
    return True


def _position(mon_ticket):
    tickets = sorted(c.name for c in FILE_ATTENTE.glob("*.ticket"))
    return tickets.index(mon_ticket.name) + 1 if mon_ticket.name in tickets else 1


@contextmanager
def tour_genicia(description="", attente_max=ATTENTE_MAX):
    """Attend son tour (ordre d'arrivée), puis garde GENICIA++ pour soi jusqu'à la fin du bloc `with`."""
    FILE_ATTENTE.mkdir(parents=True, exist_ok=True)
    verrou = open(VERROU_EXECUTION, "a+")
    ticket_chemin = FILE_ATTENTE / f"{time.time_ns():020d}_{os.getpid()}.ticket"
    ticket = open(ticket_chemin, "a+")
    ticket.write(f"{datetime.now():%d/%m/%Y %H:%M:%S} {description}\n")
    ticket.flush()
    _verrouiller(ticket)
    debut, dernier_message, obtenu = time.time(), 0.0, False
    try:
        while True:
            if _premier_de_la_file(ticket_chemin) and _verrouiller(verrou):
                obtenu = True
                break
            attente = time.time() - debut
            if attente > attente_max:
                raise GeniciaOccupe(f"GENICIA++ est resté occupé par un autre traitement pendant plus de "
                                    f"{attente_max // 60} min : rien n'a été fait, à relancer.")
            if time.time() - dernier_message >= INTERVALLE_MESSAGE:
                print(f"{MARQUEUR_ATTENTE} par un autre traitement : en attente "
                      f"(position {_position(ticket_chemin)} dans la file, {int(attente // 60)} min)...", flush=True)
                dernier_message = time.time()
            time.sleep(INTERVALLE)
    finally:
        _deverrouiller(ticket)
        ticket.close()
        try:
            ticket_chemin.unlink()
        except OSError:
            pass
        if not obtenu:
            verrou.close()
    if dernier_message:                     # n'affiche le marqueur que si on a vraiment attendu
        print(f"{MARQUEUR_TOUR} après {int((time.time() - debut) // 60)} min d'attente.", flush=True)
    try:
        yield
    finally:
        _deverrouiller(verrou)
        verrou.close()
