"""Pattern : Facade — `BenayfacileApp` cache la préparation des données et le
cycle de vie des 5 serveurs derrière demarrer() / attendre() / arreter().

Pattern : Observer (léger) — les événements de cycle de vie passent par un
callback `notifier` (journal par défaut), ce qui sépare la logique (ici) de
l'affichage (fenêtre, dialogues, console).
"""
from __future__ import annotations

import logging
import os
import sys
import time
from typing import Callable, List

from .bootstrap import DataBootstrapper
from .paths import AppPaths
from .server import SERVICE_REGISTRY, ManagedServer

Notifier = Callable[[str], None]
log = logging.getLogger("benayfacile")


class DemarrageImpossible(RuntimeError):
    pass


class BenayfacileApp:
    def __init__(self, paths: AppPaths, notifier: Notifier = log.info):
        self.paths = paths
        self.notifier = notifier
        self.serveurs: List[ManagedServer] = []

    @property
    def url(self) -> str:
        if not self.serveurs:
            raise DemarrageImpossible("Bénayfacile n'est pas démarré.")
        return self.serveurs[-1].url   # la passerelle est le dernier du registre

    @property
    def demarre(self) -> bool:
        return len(self.serveurs) == len(SERVICE_REGISTRY)

    def demarrer(self) -> None:
        if self.demarre:            # idempotent : une coquille de repli peut rappeler demarrer()
            return
        # 1. Données : les services lisent BNAY_DATA à l'import, donc AVANT l'import.
        os.environ["BNAY_DATA"] = str(self.paths.data)
        for ligne in DataBootstrapper.par_defaut(self.paths).preparer():
            self.notifier(f"référentiels — {ligne}")
        for sous in ("services", "gateway"):
            p = str(self.paths.bundle / sous)
            if p not in sys.path:
                sys.path.insert(0, p)

        # 2. Démarrage dans l'ordre du registre ; la passerelle en dernier.
        for spec in SERVICE_REGISTRY:
            try:
                srv = ManagedServer(spec)
            except Exception as e:
                self.arreter()
                raise DemarrageImpossible(f"Impossible de charger « {spec.nom} » : {e}") from e
            srv.start()
            if not srv.wait_ready():
                self.arreter()
                raise DemarrageImpossible(f"Échec du démarrage : {spec.nom}.")
            self.serveurs.append(srv)
            self.notifier(f"OK  {spec.nom:<32} {srv.url}")
        self.notifier(f"Tableau de bord : {self.url} — données : {self.paths.data}")

    @property
    def tous_vivants(self) -> bool:
        return all(s.vivant for s in self.serveurs)

    def attendre(self) -> None:
        """Bloque jusqu'à Ctrl+C ou l'arrêt inattendu d'un serveur (modes sans fenêtre)."""
        try:
            while self.tous_vivants:
                time.sleep(0.5)
            self.notifier("Un service s'est arrêté de façon inattendue.")
        except KeyboardInterrupt:
            pass

    def arreter(self) -> None:
        for srv in reversed(self.serveurs):
            srv.stop()
        self.serveurs.clear()
        self.notifier("Bénayfacile arrêté.")
