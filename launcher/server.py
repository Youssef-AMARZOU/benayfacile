"""Pattern : Adapter — `ManagedServer` adapte uvicorn.Server à une interface
simple start() / wait_ready() / stop(), exécutée dans un thread.

Pattern : Registry — `SERVICE_REGISTRY` décrit les 5 composants (nom, module,
variable d'environnement) en un seul endroit ; ajouter un service = une ligne.

Ports : chaque serveur reçoit un socket déjà lié à un port libre choisi par le
système (port 0). Aucun conflit possible avec un autre logiciel du poste, et
aucune fenêtre entre « je vérifie que le port est libre » et « je l'utilise ».
"""
from __future__ import annotations

import importlib
import os
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional

import uvicorn

HOTE = "127.0.0.1"   # boucle locale uniquement : pas d'exposition sur le réseau du bureau


@dataclass(frozen=True)
class ServiceSpec:
    nom: str
    module: str               # module Python qui expose `app` (FastAPI)
    cle_env: Optional[str]    # BNAY_URL_<…> transmis à la passerelle ; None = la passerelle


SERVICE_REGISTRY: tuple[ServiceSpec, ...] = (
    ServiceSpec("Robot (extraction RSA)", "robot_service", "BNAY_URL_ROBOT"),
    ServiceSpec("Moteur BAEL / RPS", "engine_service", "BNAY_URL_ENGINE"),
    ServiceSpec("Générateur DXF", "dxf_service", "BNAY_URL_DXF"),
    ServiceSpec("Note de calcul", "report_service", "BNAY_URL_REPORT"),
    ServiceSpec("Passerelle + tableau de bord", "app", None),   # en dernier : lit les BNAY_URL_*
)


def socket_libre(hote: str = HOTE) -> socket.socket:
    """Socket TCP lié à un port libre attribué par le système."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((hote, 0))
    s.listen(128)
    s.set_inheritable(True)
    return s


class ManagedServer:
    """Adaptateur autour de uvicorn.Server."""

    def __init__(self, spec: ServiceSpec):
        self.spec = spec
        self._sock = socket_libre()
        self.port: int = self._sock.getsockname()[1]
        self.url = f"http://{HOTE}:{self.port}"
        if spec.cle_env:
            # Publié AVANT l'import de la passerelle, qui lit ces variables à l'import.
            os.environ[spec.cle_env] = self.url
        app = importlib.import_module(spec.module).app
        config = uvicorn.Config(app, log_level="warning", access_log=False,
                                lifespan="on", log_config=None)   # log_config=None : pas de console requise
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, kwargs={"sockets": [self._sock]},
                                        name=spec.module, daemon=True)

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
        try:
            self._sock.close()
        except OSError:
            pass
