"""Pattern : Strategy — la « coquille » qui affiche l'application.

Trois stratégies, essayées dans l'ordre jusqu'à la première disponible :

1. `FenetreNative`  : fenêtre Windows unique (pywebview + Edge WebView2,
                      présent par défaut sur Windows 10/11). C'est le mode
                      normal : l'utilisateur voit un logiciel, pas un navigateur.
2. `FenetreEdgeApp` : Microsoft Edge en mode application (--app), sans barre
                      d'adresse ni onglets. Repli si WebView2 est absent.
3. `Navigateur`     : navigateur par défaut. Dernier recours.

Chaque coquille possède la boucle principale et rend la main quand
l'utilisateur ferme la fenêtre ; l'arrêt des serveurs suit.
"""
from __future__ import annotations

import logging
import os
import pathlib
import shutil
import subprocess
import webbrowser
from typing import List, Optional

from .supervisor import BenayfacileApp

log = logging.getLogger("benayfacile")
TITRE = "Bénayfacile — Calcul BA (BAEL 91 / RPS 2011)"

ECRAN_DEMARRAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<style>html,body{height:100%;margin:0;font-family:'Segoe UI',sans-serif;background:#f6f7f9;color:#1e293b}
.c{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px}
h1{font-weight:600;font-size:26px;margin:0}p{margin:0;color:#64748b}
.b{width:220px;height:4px;background:#e2e8f0;border-radius:2px;overflow:hidden}
.b i{display:block;width:40%;height:100%;background:#1d4ed8;animation:a 1.1s ease-in-out infinite}
@keyframes a{0%{margin-left:-40%}100%{margin-left:100%}}</style></head>
<body><div class="c"><h1>Bénayfacile</h1><p>Démarrage du moteur de calcul…</p><div class="b"><i></i></div></div></body></html>"""


class Coquille:
    nom = "?"

    def disponible(self) -> bool:
        raise NotImplementedError

    def executer(self, app: BenayfacileApp) -> None:
        raise NotImplementedError


class PontFenetre:
    """Fonctions natives offertes à la page (window.pywebview.api.*), dans la fenêtre native.

    Sert aux boîtes de dialogue Windows, que la page web ne peut pas ouvrir elle-même
    avec un vrai chemin de fichier (nécessaire pour faire ouvrir le .rtd par Robot)."""

    def __init__(self) -> None:
        self._fenetre = None    # « _ » : pywebview n'expose pas (et ne parcourt pas) les attributs privés

    def choisir_projet_robot(self) -> Optional[str]:
        import webview
        if self._fenetre is None:
            return None
        ouvrir = webview.FileDialog.OPEN if hasattr(webview, "FileDialog") else webview.OPEN_DIALOG
        choix = self._fenetre.create_file_dialog(
            ouvrir, allow_multiple=False,
            file_types=("Projets Robot (*.rtd)", "Tous les fichiers (*.*)"))
        if not choix:
            return None
        return str(choix[0] if isinstance(choix, (list, tuple)) else choix)


class FenetreNative(Coquille):
    nom = "fenêtre native (WebView2)"

    def disponible(self) -> bool:
        try:
            import webview  # noqa: F401
            return True
        except Exception as e:
            log.info("pywebview indisponible : %s", e)
            return False

    def executer(self, app: BenayfacileApp) -> None:
        import webview
        webview.settings["ALLOW_DOWNLOADS"] = True            # DXF / notes : boîte « Enregistrer sous »
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        erreur: List[BaseException] = []
        api = PontFenetre()

        fenetre = webview.create_window(TITRE, html=ECRAN_DEMARRAGE, width=1380, height=880,
                                        min_size=(1024, 680), text_select=True, js_api=api)
        api._fenetre = fenetre

        def apres_affichage(win):
            try:
                app.demarrer()
                win.load_url(app.url)
            except BaseException as e:   # remonté après fermeture de la fenêtre
                erreur.append(e)
                win.destroy()

        stockage = app.paths.data / "webview"
        stockage.mkdir(parents=True, exist_ok=True)
        webview.start(apres_affichage, (fenetre,), gui="edgechromium",
                      private_mode=False, storage_path=str(stockage))
        if erreur:
            raise erreur[0]


def _chemin_edge() -> Optional[str]:
    candidats = [shutil.which("msedge")]
    for var in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if base:
            candidats.append(str(pathlib.Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"))
    return next((c for c in candidats if c and pathlib.Path(c).is_file()), None)


class FenetreEdgeApp(Coquille):
    nom = "Microsoft Edge en mode application"

    def disponible(self) -> bool:
        return _chemin_edge() is not None

    def executer(self, app: BenayfacileApp) -> None:
        app.demarrer()
        profil = app.paths.data / "edge-profil"   # profil dédié : Edge reste un processus à part,
        profil.mkdir(parents=True, exist_ok=True)  # donc `wait()` rend la main à la fermeture
        proc = subprocess.Popen([_chemin_edge(), f"--app={app.url}", f"--user-data-dir={profil}",
                                 "--no-first-run", "--no-default-browser-check", "--window-size=1380,880"])
        proc.wait()


class Navigateur(Coquille):
    nom = "navigateur par défaut"

    def disponible(self) -> bool:
        return True

    def executer(self, app: BenayfacileApp) -> None:
        app.demarrer()
        webbrowser.open(app.url)
        app.attendre()


STRATEGIES = (FenetreNative, FenetreEdgeApp, Navigateur)


def executer_avec_repli(app: BenayfacileApp, depuis: int = 0) -> str:
    """Essaie les coquilles dans l'ordre ; renvoie le nom de celle qui a servi."""
    from .supervisor import DemarrageImpossible
    for cls in STRATEGIES[depuis:]:
        coquille = cls()
        if not coquille.disponible():
            continue
        try:
            log.info("Affichage : %s", coquille.nom)
            coquille.executer(app)
            return coquille.nom
        except DemarrageImpossible:
            raise                         # erreur de l'application elle-même : pas de repli
        except Exception as e:
            log.exception("Coquille « %s » en échec, repli : %s", coquille.nom, e)
    raise RuntimeError("Aucun moyen d'afficher l'application.")
