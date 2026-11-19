"""Point d'entrée de l'application de bureau Bénayfacile.

    Bénayfacile (menu Démarrer)        # application installée : une fenêtre, rien d'autre
    python bnayfacile_app.py           # depuis les sources
    python bnayfacile_app.py --headless   # serveurs seuls, sans fenêtre (tests, CI)
    python bnayfacile_app.py --browser    # forcer l'affichage dans le navigateur
"""
from __future__ import annotations

import sys

from launcher.desktop import InstanceUnique, configurer_journal, message
from launcher.paths import AppPaths
from launcher.supervisor import BenayfacileApp, DemarrageImpossible
from launcher.window import STRATEGIES, Navigateur, executer_avec_repli

VERSION = "0.3.0"


def main(argv: list[str]) -> int:
    paths = AppPaths.detect()
    journal = configurer_journal(paths.logs)
    import logging
    log = logging.getLogger("benayfacile")
    log.info("Bénayfacile %s — démarrage (données : %s)", VERSION, paths.data)

    instance = InstanceUnique()
    if instance.deja_ouverte:
        message("Bénayfacile est déjà ouvert.\n\nUtilisez la fenêtre existante (barre des tâches).")
        return 0

    app = BenayfacileApp(paths)
    try:
        if "--headless" in argv:
            app.demarrer()
            print(app.url, flush=True) if sys.stdout else None
            app.attendre()
        else:
            depuis = STRATEGIES.index(Navigateur) if "--browser" in argv else 0
            executer_avec_repli(app, depuis)
    except DemarrageImpossible as e:
        message(f"Bénayfacile n'a pas pu démarrer.\n\n{e}\n\nJournal : {journal}", erreur=True)
        return 1
    except Exception as e:
        log.exception("Erreur inattendue")
        message(f"Erreur inattendue : {e}\n\nJournal : {journal}", erreur=True)
        return 1
    finally:
        app.arreter()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
