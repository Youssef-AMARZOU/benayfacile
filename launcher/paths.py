"""Pattern : Value Object — chemins immuables résolus une seule fois.

`AppPaths` répond à une seule question : « où sont les fichiers ? », que l'on
tourne depuis les sources (python bnayfacile_app.py) ou depuis l'application
installée (sys.frozen). Le reste du code ne teste plus jamais sys.frozen.

Application installée : le programme est dans Program Files (lecture seule pour
un utilisateur standard), donc les données vont dans le profil Windows :
    %LOCALAPPDATA%\\Benayfacile\\referentiels   (bael, rps, bureau.json)
    %LOCALAPPDATA%\\Benayfacile\\output         (notes, DXF)
    %LOCALAPPDATA%\\Benayfacile\\logs           (journal)
"""
from __future__ import annotations

import os
import pathlib
import sys
from dataclasses import dataclass

NOM_DOSSIER = "Benayfacile"


@dataclass(frozen=True)
class AppPaths:
    bundle: pathlib.Path   # ressources en lecture seule (sources, ou dossier _internal de PyInstaller)
    data: pathlib.Path     # dossier inscriptible : referentiels/ + output/ + logs/

    @property
    def referentiels(self) -> pathlib.Path:
        return self.data / "referentiels"

    @property
    def output(self) -> pathlib.Path:
        return self.data / "output"

    @property
    def logs(self) -> pathlib.Path:
        return self.data / "logs"

    @classmethod
    def detect(cls) -> "AppPaths":
        """Factory Method : choisit la résolution selon le mode d'exécution."""
        if getattr(sys, "frozen", False):
            bundle = pathlib.Path(getattr(sys, "_MEIPASS"))
            base = os.environ.get("LOCALAPPDATA") or str(pathlib.Path.home() / ".local" / "share")
            data = pathlib.Path(base) / NOM_DOSSIER
        else:
            root = pathlib.Path(__file__).resolve().parent.parent
            bundle = root
            data = pathlib.Path(os.environ["BNAY_DATA"]) if os.environ.get("BNAY_DATA") else root
        return cls(bundle=bundle, data=data)
