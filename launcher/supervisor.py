"""Pattern : Facade — `BenayfacileApp` cache la préparation des données, la
vérification des ports et le cycle de vie des 5 serveurs derrière
demarrer() / attendre() / arreter().

Pattern : Observer (léger) — les événements de cycle de vie passent par un
callback `notifier`, ce qui sépare la logique (ici) de l'affichage (console).
"""
from __future__ import annotations

import os
import sys
import time
import webbrowser
from typing import Callable, List

from .bootstrap import DataBootstrapper
from .paths import AppPaths
from .server import HOTE, SERVICE_REGISTRY, ManagedServer, port_libre

Notifier = Callable[[str], None]


class DemarrageImpossible(RuntimeError):
    pass


class BenayfacileApp:
    def __init__(self, paths: AppPaths, notifier: Notifier = print):
        self.paths = paths
        self.notifier = notifier
        self.serveurs: List[ManagedServer] = []

    @property
    def url(self) -> str:
        port = SERVICE_REGISTRY[-1].port
        return f"http://{HOTE}:{port}"

    def demarrer(self, ouvrir_navigateur: bool = True) -> None:
        # 1. Données : les services lisent BNAY_DATA à l'import, donc AVANT l'import.
        os.environ["BNAY_DATA"] = str(self.paths.data)
        for ligne in DataBootstrapper.par_defaut(self.paths).preparer():
            self.notifier(f"  référentiels — {ligne}")
        for sous in ("services", "gateway"):
            p = str(self.paths.bundle / sous)
            if p not in sys.path:
                sys.path.insert(0, p)

        # 2. Garde : tous les ports libres, sinon on s'arrête avant de lancer quoi que ce soit.
        occupes = [s for s in SERVICE_REGISTRY if not port_libre(s.port)]
        if occupes:
            liste = ", ".join(f"{s.port} ({s.nom})" for s in occupes)
            raise DemarrageImpossible(
                f"Port(s) déjà utilisé(s) : {liste}. Bénayfacile est peut-être déjà lancé "
                f"(ou run_services.bat tourne). Fermez-le puis relancez.")

        # 3. Démarrage dans l'ordre du registre ; la passerelle en dernier.
        for spec in SERVICE_REGISTRY:
            srv = ManagedServer(spec)
            srv.start()
            if not srv.wait_ready():
                self.arreter()
                raise DemarrageImpossible(f"Échec du démarrage : {spec.nom} (port {spec.port}).")
            self.serveurs.append(srv)
            self.notifier(f"  OK  {spec.nom:<32} {HOTE}:{spec.port}")

        self.notifier(f"\nTableau de bord : {self.url}")
        self.notifier(f"Données et sorties : {self.paths.data}")
        if ouvrir_navigateur:
            webbrowser.open(self.url)

    def attendre(self) -> None:
        """Bloque jusqu'à Ctrl+C, fermeture de la fenêtre ou arrêt d'un serveur."""
        try:
            while all(s.vivant for s in self.serveurs):
                time.sleep(0.5)
            self.notifier("Un service s'est arrêté de façon inattendue.")
        except KeyboardInterrupt:
            pass

    def arreter(self) -> None:
        for srv in reversed(self.serveurs):
            srv.stop()
        self.serveurs.clear()
        self.notifier("Bénayfacile arrêté.")
