"""Service Robot — extraction du modèle Robot Structural Analysis via COM (Interop.RobotOM).

Mode réel  : Robot doit être installé et ouvert (ou installé et pilotable) ; utilise
             win32com + Robot.Application. Sinon, mode SIMULATION (données R+4).

Port : 8001
"""
from __future__ import annotations
import json
import pathlib
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from robot_ossature import extraire_ossature_com, ossature_simulation

HERE = pathlib.Path(__file__).resolve().parent
# BNAY_DATA : dossier de données inscriptible (fixé par le lanceur .exe)
DATA = pathlib.Path(__import__("os").environ.get("BNAY_DATA", str(HERE.parent)))
REFS = DATA / "referentiels"

app = FastAPI(title="Bénayfacile — Service Robot", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def robot_disponible() -> tuple[bool, Optional[str]]:
    """True si Robot est accessible via COM (message d'erreur sinon)."""
    try:
        import win32com.client  # type: ignore
        robot = win32com.client.Dispatch("Robot.Application")
        _ = robot.Name
        return True, None
    except Exception as e:  # Robot non installé / non lancé / version incompatibilisée
        return False, str(e)


def modele_simulation() -> dict:
    """Modèle R+4 fictif (zone 3, site S2, classe II) — identique au spec Bénayfacile."""
    niveaux = [
        {"nom": "RDC", "altitude_m": 0.0, "w_kn": 950},
        {"nom": "R+1", "altitude_m": 3.0, "w_kn": 820},
        {"nom": "R+2", "altitude_m": 6.0, "w_kn": 820},
        {"nom": "R+3", "altitude_m": 9.0, "w_kn": 820},
        {"nom": "R+4", "altitude_m": 12.0, "w_kn": 700},
        {"nom": "Acrotère", "altitude_m": 15.0, "w_kn": 180},
    ]
    return {
        "nom": "Immeuble R+4 — Casablanca (modèles de démonstration Bénayfacile)",
        "nb_niveaux": 6,
        "plan": {"trame_x_m": [0, 6, 12], "trame_y_m": [0, 5, 10], "nb_poteaux": 9},
        "elements": {"poteaux": 9, "poutres": 12, "dalles": 10, "voiles": 2},
        "section_poteaux_cm": [30, 30],
        "section_poutres_cm": [25, 50],
        "epaisseur_dalle_cm": 16,
        "materiaux": {"beton_fc28_mpa": 25, "acier": "HA fe500"},
        "masses": {"G_kn": 3800, "Q_kn": 1200, "W_kn": round(3800 + 0.2 * 1200, 1)},
        "niveaux": niveaux,
        "combinaisons": ["Poids propre", "Charges permanentes", "Charges d'exploitation",
                         "Séisme ELU (1.35 G + 1.5 Q + E)", "Séisme ELS"],
        "modal": {"T1_s": 0.62, "T2_s": 0.55, "T3_s": 0.41, "masse_participante_pct": 92.4},
        "rps": {"zone": 3, "site": "S2", "classe": "II", "K": 2.0, "I": 1.2, "S": 1.2},
        "ossature": ossature_simulation(),
        "notes": ["Modèle SIMULÉ (Robot non piloté). Pour un modèle réel : lancer Robot, ouvrir le projet, puis POST /extract."],
    }


def extraire_com(cas_elu: Optional[int] = None, cas_els: Optional[int] = None) -> dict:
    import win32com.client  # type: ignore
    try:   # bibliothèque de types : donne accès aux constantes RobotOM
        robot = win32com.client.gencache.EnsureDispatch("Robot.Application")
    except Exception:
        robot = win32com.client.Dispatch("Robot.Application")
    projet = robot.GetCurrentProject()
    if projet is None:
        # tenter de prendre le projet actif
        projet = robot.Project
    if projet is None:
        raise RuntimeError("Aucun projet Robot ouvert.")
    om = projet  # Project OM
    nom = getattr(projet, "Name", "Projet Robot")
    # Structure
    n_elements = {}
    try:
        struct = om.Structure
        n_elements["nodes"] = struct.Nodes.Count
        n_elements["bars"] = struct.Bars.Count
        n_elements["panels"] = struct.Panels.Count
    except Exception as e:
        n_elements["erreur_structure"] = str(e)
    # Cas de charge
    cas = []
    try:
        for i in range(om.Cases.Count):
            c = om.Cases[i + 1]
            cas.append({"nom": getattr(c, "Name", f"cas{i+1}"), "type": str(getattr(c, "Type", ""))})
    except Exception as e:
        cas.append({"erreur": str(e)})
    # Combinaisons
    combs = []
    try:
        for i in range(om.Combinations.Count):
            cb = om.Combinations[i + 1]
            combs.append(getattr(cb, "Name", f"comb{i+1}"))
    except Exception:
        pass
    # Modal analysis : périodes
    periods = []
    try:
        for i in range(om.Analyses.Count):
            pass
    except Exception:
        periods = []
    notes = ["Extraction COM réussie."]
    try:
        ossature = extraire_ossature_com(projet, cas_elu, cas_els)
        notes += ossature.get("remarques", [])
    except Exception as e:
        ossature = None
        notes.append(f"Ossature (poteaux, poutres, semelles, voiles) non lue : {e}")
    return {
        "nom": nom,
        "nb_niveaux": len(ossature["niveaux"]) if ossature else None,
        "elements": ossature["resume"] if ossature else n_elements,
        "cas_de_charge": cas,
        "combinaisons": combs,
        "modal": {"T1_s": periods[0] if periods else None},
        "ossature": ossature,
        "notes": notes,
    }


@app.get("/health")
def health():
    ok, err = robot_disponible()
    return {"service": "robot", "status": "ok", "robot_com_disponible": ok,
            "detail": err if err else "Robot pilotable via COM", "mode_defaut": "simulation si COM indisponible"}


class ExtractInput(BaseModel):
    chemin_fichier: Optional[str] = None
    forcer_simulation: bool = False
    cas_elu: Optional[int] = None    # numéro de la combinaison ELU dans Robot (sinon : nom contenant « ELU »)
    cas_els: Optional[int] = None


@app.get("/model")
def model():
    ok, err = robot_disponible()
    if not ok:
        m = modele_simulation()
        m["mode"] = "simulation"
        m["robot_com"] = {"disponible": False, "erreur": err}
        return m
    try:
        m = extraire_com()
        m["mode"] = "robot"
        m["robot_com"] = {"disponible": True}
        return m
    except Exception as e:
        m = modele_simulation()
        m["mode"] = "simulation"
        m["robot_com"] = {"disponible": True, "erreur_extraction": str(e)}
        return m


@app.post("/extract")
def extract(inp: ExtractInput):
    ok, err = robot_disponible()
    if inp.forcer_simulation or not ok:
        m = modele_simulation()
        m["mode"] = "simulation"
        m["robot_com"] = {"disponible": ok, "erreur": err}
        return m
    try:
        m = extraire_com(inp.cas_elu, inp.cas_els)
        m["mode"] = "robot"
        m["robot_com"] = {"disponible": True}
        return m
    except Exception as e:
        m = modele_simulation()
        m["mode"] = "simulation"
        m["robot_com"] = {"disponible": True, "erreur_extraction": str(e)}
        return m

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8001)
