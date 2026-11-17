"""Pattern : Value Object — chemins immuables résolus une seule fois.

`AppPaths` répond à une seule question : « où sont les fichiers ? », que l'on
tourne depuis les sources (python benayfacile_app.py) ou depuis l'exécutable
PyInstaller (sys.frozen). Le reste du code ne teste plus jamais sys.frozen.
"""
from __future__ import annotations

import pathlib
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class AppPaths:
    bundle: pathlib.Path   # ressources en lecture seule (sources, ou _MEIPASS de PyInstaller)
    data: pathlib.Path     # dossier inscriptible : referentiels/ + output/ (à côté du .exe)

    @property
    def referentiels(self) -> pathlib.Path:
        return self.data / "referentiels"

    @property
    def output(self) -> pathlib.Path:
        return self.data / "output"

    @classmethod
    def detect(cls) -> "AppPaths":
        """Factory Method : choisit la résolution selon le mode d'exécution."""
        if getattr(sys, "frozen", False):
            bundle = pathlib.Path(getattr(sys, "_MEIPASS"))
            data = pathlib.Path(sys.executable).resolve().parent / "Benayfacile_donnees"
        else:
            root = pathlib.Path(__file__).resolve().parent.parent
            bundle = root
            data = root
        return cls(bundle=bundle, data=data)
