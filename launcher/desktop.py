"""Intégration Windows : dialogues, instance unique, journal.

Rien ici n'est indispensable au calcul : chaque fonction se dégrade proprement
hors Windows (tests Linux, mode --headless).
"""
from __future__ import annotations

import logging
import logging.handlers
import pathlib
import sys

TITRE = "Bénayfacile"
EST_WINDOWS = sys.platform == "win32"
log = logging.getLogger("benayfacile")


def configurer_journal(dossier: pathlib.Path) -> pathlib.Path:
    dossier.mkdir(parents=True, exist_ok=True)
    fichier = dossier / "benayfacile.log"
    racine = logging.getLogger()
    racine.setLevel(logging.INFO)
    h = logging.handlers.RotatingFileHandler(fichier, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    racine.addHandler(h)
    if sys.stderr is not None:          # en mode fenêtre (sans console), stderr vaut None
        racine.addHandler(logging.StreamHandler(sys.stderr))
    return fichier


def message(texte: str, erreur: bool = False) -> None:
    """Boîte de dialogue Windows (ou console hors Windows)."""
    log.error(texte) if erreur else log.info(texte)
    if EST_WINDOWS:
        import ctypes
        MB_ICONERROR, MB_ICONINFORMATION, MB_SETFOREGROUND = 0x10, 0x40, 0x10000
        ctypes.windll.user32.MessageBoxW(
            None, texte, TITRE, (MB_ICONERROR if erreur else MB_ICONINFORMATION) | MB_SETFOREGROUND)
    elif sys.stderr is not None:
        print(f"[{TITRE}] {texte}", file=sys.stderr)


class InstanceUnique:
    """Mutex nommé Windows : une seule fenêtre Bénayfacile à la fois par session."""

    NOM = "Local\\Benayfacile.InstanceUnique"

    def __init__(self) -> None:
        self._handle = None
        self.deja_ouverte = False
        if EST_WINDOWS:
            import ctypes
            ERROR_ALREADY_EXISTS = 183
            k32 = ctypes.windll.kernel32
            self._handle = k32.CreateMutexW(None, False, self.NOM)
            self.deja_ouverte = k32.GetLastError() == ERROR_ALREADY_EXISTS
