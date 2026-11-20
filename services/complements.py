"""Compléments : logiciels externes dont Bénayfacile se sert, et leur présence sur ce poste.

Bénayfacile n'installe rien et ne redistribue aucun logiciel tiers : il détecte ce qui
est présent (base de registre Windows, en lecture seule) et donne le lien officiel de
l'éditeur pour obtenir ce qui manque.
"""
from __future__ import annotations

import sys
from typing import Callable, Dict, List, Optional, Tuple

# (ruche, clé) ; ruche « HKCR », « HKLM » ou « HKCU »
Cle = Tuple[str, str]


def _cle_existe(ruche: str, chemin: str) -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    racine = {"HKCR": winreg.HKEY_CLASSES_ROOT, "HKLM": winreg.HKEY_LOCAL_MACHINE,
              "HKCU": winreg.HKEY_CURRENT_USER}[ruche]
    for vue in (0, winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            winreg.CloseKey(winreg.OpenKey(racine, chemin, 0, winreg.KEY_READ | vue))
            return True
        except OSError:
            continue
    return False


def _app_path(exe: str) -> Cle:
    return ("HKLM", rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe}")


# Chaque besoin : programmes qui y répondent (nom affiché, clés qui prouvent sa présence)
BESOINS: List[dict] = [
    {
        "id": "robot",
        "titre": "Autodesk Robot Structural Analysis",
        "role": "Ouvrir un projet Robot (.rtd) et en lire l'ossature, les sections et les efforts.",
        "requis": "Pour « Ouvrir un fichier Robot » et « Lire le projet déjà ouvert dans Robot ».",
        "programmes": [("Robot Structural Analysis", [("HKCR", r"Robot.Application\CLSID")])],
        "manque": "Robot est un logiciel Autodesk distinct d'AutoCAD, avec sa propre licence (incluse dans "
                  "l'abonnement AEC Collection). Sans Robot, utilisez l'import Excel.",
        "liens": [("Robot Structural Analysis (Autodesk)", "https://www.autodesk.com/products/robot-structural-analysis/overview"),
                  ("Licence éducation gratuite (étudiants, enseignants)", "https://www.autodesk.com/education/edu-software/overview")],
    },
    {
        "id": "tableur",
        "titre": "Tableur : Microsoft Excel ou LibreOffice Calc",
        "role": "Remplir le modèle Excel de Bénayfacile (sans Robot) et ouvrir l'export des résultats.",
        "requis": "Pour « Importer un classeur Excel » et l'export Excel du calcul.",
        "programmes": [("Microsoft Excel", [("HKCR", r"Excel.Application\CLSID"), _app_path("excel.exe")]),
                       ("LibreOffice Calc", [("HKLM", r"SOFTWARE\LibreOffice"), _app_path("soffice.exe")])],
        "manque": "LibreOffice est gratuit et ouvre les classeurs .xlsx.",
        "liens": [("LibreOffice (gratuit)", "https://www.libreoffice.org/download/download-libreoffice/"),
                  ("Microsoft Excel", "https://www.microsoft.com/microsoft-365/excel")],
    },
    {
        "id": "dxf",
        "titre": "Lecteur de plans DXF",
        "role": "Ouvrir, imprimer et compléter les plans de ferraillage produits par Bénayfacile.",
        "requis": "Pour les plans DXF de la synthèse.",
        "programmes": [("AutoCAD", [("HKCR", r"AutoCAD.Application\CLSID"), _app_path("acad.exe")]),
                       ("DWG TrueView", [_app_path("dwgviewr.exe")]),
                       ("LibreCAD", [_app_path("librecad.exe"), ("HKLM", r"SOFTWARE\LibreCAD")]),
                       ("Programme associé aux fichiers .dxf", [("HKCR", r".dxf\OpenWithProgids"), ("HKCU", r"Software\Classes\.dxf")])],
        "manque": "DWG TrueView (Autodesk) et LibreCAD sont gratuits.",
        "liens": [("DWG TrueView — gratuit (Autodesk)", "https://www.autodesk.com/viewers"),
                  ("LibreCAD — gratuit", "https://librecad.org/")],
    },
]


def detecter(besoins: List[dict] = BESOINS, existe: Callable[[str, str], bool] = _cle_existe) -> List[Dict]:
    """État de chaque complément : programmes trouvés sur ce poste et liens officiels."""
    out = []
    for b in besoins:
        trouves = [nom for nom, cles in b["programmes"] if any(existe(r, c) for r, c in cles)]
        out.append({
            "id": b["id"], "titre": b["titre"], "role": b["role"], "requis": b["requis"],
            "installe": bool(trouves), "trouves": trouves,
            "conseil": None if trouves else b["manque"],
            "liens": [{"libelle": l, "url": u} for l, u in b["liens"] if u.startswith("https://")],
        })
    return out
