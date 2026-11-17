"""Point d'entrée de l'exécutable Benayfacile.exe (un seul processus, 5 serveurs).

    python bnayfacile_app.py            # depuis les sources
    Benayfacile.exe                      # après build_exe.bat
    Benayfacile.exe --no-browser         # sans ouvrir le navigateur
"""
from __future__ import annotations

import sys

from launcher.paths import AppPaths
from launcher.supervisor import BenayfacileApp, DemarrageImpossible

VERSION = "0.1.0"


def main(argv: list[str]) -> int:
    print(f"Bénayfacile {VERSION} — BAEL 91 rév. 99 / RPS 2000 v2011")
    print("Démarrage des services…")
    app = BenayfacileApp(AppPaths.detect())
    try:
        app.demarrer(ouvrir_navigateur="--no-browser" not in argv)
    except DemarrageImpossible as e:
        print(f"\nERREUR : {e}")
        if getattr(sys, "frozen", False):
            input("Appuyez sur Entrée pour fermer…")
        return 1
    print("Fermez cette fenêtre (ou Ctrl+C) pour arrêter Bénayfacile.\n")
    app.attendre()
    app.arreter()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
