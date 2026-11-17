"""Pattern : Adapter — `ManagedServer` adapte uvicorn.Server à une interface
simple start() / wait_ready() / stop(), exécutée dans un thread.

Pattern : Registry — `SERVICE_REGISTRY` décrit les 5 composants (nom, module,
port) en un seul endroit ; ajouter un service = ajouter une ligne.
"""
from __future__ import annotations

import importlib
import socket
import threading
import time
from dataclasses import dataclass

import uvicorn

HOTE = "127.0.0.1"   # boucle locale uniquement : pas d'exposition sur le réseau du bureau


@dataclass(frozen=True)
class ServiceSpec:
    nom: str
    module: str      # module Python qui expose `app` (FastAPI)
    port: int


SERVICE_REGISTRY: tuple[ServiceSpec, ...] = (
    ServiceSpec("Robot (extraction RSA)", "robot_service", 8001),
    ServiceSpec("Moteur BAEL / RPS", "engine_service", 8002),
    ServiceSpec("Générateur DXF", "dxf_service", 8003),
    ServiceSpec("Note de calcul", "report_service", 8004),
    ServiceSpec("Passerelle + tableau de bord", "app", 8090),
)


def port_libre(port: int, hote: str = HOTE) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((hote, port)) != 0


class ManagedServer:
    """Adaptateur autour de uvicorn.Server."""

    def __init__(self, spec: ServiceSpec):
        self.spec = spec
        app = importlib.import_module(spec.module).app
        config = uvicorn.Config(app, host=HOTE, port=spec.port, log_level="warning",
                                access_log=False, lifespan="on")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, name=spec.module, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def wait_ready(self, timeout_s: float = 30.0) -> bool:
        fin = time.monotonic() + timeout_s
        while time.monotonic() < fin:
            if self._server.started:
                return True
            if not self._thread.is_alive():
                return False
            time.sleep(0.05)
        return False

    @property
    def vivant(self) -> bool:
        return self._thread.is_alive()

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
