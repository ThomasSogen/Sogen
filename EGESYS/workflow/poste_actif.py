r"""Un seul PC à la fois : verrou partagé par OneDrive entre les PC qui peuvent faire tourner le programme.

Le fichier <dossier OneDrive>\_poste_actif.json dit quel PC fait tourner le programme :
  {"poste": nom du PC, "programme": ..., "depuis": date de démarrage, "battement": heure du dernier signe de vie}

- au démarrage : si un AUTRE PC a donné signe de vie depuis moins de PERIME secondes, on refuse de démarrer ;
- en marche : le battement est rafraîchi toutes les BATTEMENT secondes par une tâche de fond (même pendant un
  traitement long) ; si un autre PC a pris la place (parce que
  ce PC semblait arrêté : veille, coupure réseau…), ce programme s'arrête aussitôt, sans traiter de mail ;
- à l'arrêt normal (Ctrl+C, fin) : le fichier est supprimé. Après un arrêt brutal (PC éteint, processus tué), l'autre
  PC peut démarrer PERIME secondes après le dernier signe de vie.

Limite : OneDrive met quelques secondes à synchroniser ; démarrer les deux PC exactement en même temps n'est pas
détecté. Le battement utilise l'horloge des PC (synchronisée par le domaine).

Fichier identique dans EGESYS\workflow\ et G++\veilleur\ : modifier les deux.
"""
import json
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path

BATTEMENT = 60    # secondes entre deux signes de vie
PERIME = 300      # sans signe de vie depuis 5 min, l'autre PC est considéré comme arrêté
POSTE = os.environ.get("COMPUTERNAME") or socket.gethostname()


def _heure(secondes):
    return datetime.fromtimestamp(secondes).strftime("%d/%m/%Y %H:%M:%S")


class PosteActif:
    def __init__(self, fichier: Path, programme: str):
        self.fichier = Path(fichier)
        self.programme = programme
        self.depuis = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.dernier_battement = 0.0
        self._verrou = threading.Lock()
        self._arret = threading.Event()

    def lire(self):
        try:
            return json.loads(self.fichier.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def autre_poste(self):
        """Contenu du fichier si un AUTRE PC est actif (signe de vie récent), sinon None."""
        contenu = self.lire()
        if not isinstance(contenu, dict) or contenu.get("poste") == POSTE:
            return None
        try:
            age = time.time() - float(contenu.get("battement", 0))
        except (TypeError, ValueError):
            return None
        return contenu if age < PERIME else None

    def _ecrire(self):
        with self._verrou:
            contenu = {"poste": POSTE, "programme": self.programme, "depuis": self.depuis, "battement": time.time(),
                       "battement_lisible": datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
            self.fichier.parent.mkdir(parents=True, exist_ok=True)
            temporaire = self.fichier.with_name(self.fichier.name + ".tmp")
            temporaire.write_text(json.dumps(contenu, ensure_ascii=False, indent=2), encoding="utf-8")
            for essai in range(5):
                try:
                    os.replace(temporaire, self.fichier)
                    break
                except PermissionError:      # fichier brièvement verrouillé par la synchronisation OneDrive
                    if essai == 4:
                        raise
                    time.sleep(2)
            self.dernier_battement = time.time()

    def _battre(self):
        """Tâche de fond : signe de vie toutes les BATTEMENT secondes, tant qu'aucun autre PC n'a pris la place."""
        while not self._arret.wait(BATTEMENT):
            try:
                if self.autre_poste():
                    return               # le programme principal s'arrêtera à son prochain entretenir()
                self._ecrire()
            except Exception as erreur:  # OneDrive momentanément indisponible : on réessaiera
                print(f"⚠️  Signe de vie impossible ({erreur}).")

    def _message_autre(self, autre):
        return (f"🛑 {self.programme} tourne déjà sur le PC {autre.get('poste')} (depuis le {autre.get('depuis')}, "
                f"dernier signe de vie le {_heure(float(autre.get('battement', 0)))}). Un seul PC à la fois : "
                f"arrêtez-le sur l'autre PC, ou attendez {PERIME // 60} min s'il est éteint, puis relancez.")

    def prendre(self):
        """Au démarrage : refuse (SystemExit) si un autre PC est actif, sinon s'inscrit comme PC actif."""
        autre = self.autre_poste()
        if autre:
            raise SystemExit(self._message_autre(autre))
        self._ecrire()
        threading.Thread(target=self._battre, name="poste_actif", daemon=True).start()

    def entretenir(self):
        """À appeler avant chaque passage et avant chaque mail : s'arrête (SystemExit) si un autre PC a pris la
        place ; rafraîchit le signe de vie s'il est en retard (la tâche de fond le fait normalement)."""
        autre = self.autre_poste()
        if autre:
            raise SystemExit(f"🛑 {self.programme} a été repris par le PC {autre.get('poste')} (depuis le "
                             f"{autre.get('depuis')}) : il s'arrête sur ce PC ({POSTE}). Un seul PC à la fois.")
        if time.time() - self.dernier_battement >= BATTEMENT:
            self._ecrire()

    def liberer(self):
        """À l'arrêt : supprime le fichier s'il est bien à ce PC."""
        self._arret.set()
        with self._verrou:               # attend la fin d'une écriture de la tâche de fond
            contenu = self.lire()
            if isinstance(contenu, dict) and contenu.get("poste") == POSTE:
                try:
                    self.fichier.unlink()
                except OSError:
                    pass
