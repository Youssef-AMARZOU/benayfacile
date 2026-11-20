"""Service Robot — extraction du modèle Robot Structural Analysis via COM (Interop.RobotOM).

Mode réel  : Robot doit être installé et ouvert (ou installé et pilotable) ; utilise
             win32com + Robot.Application. Sinon, mode SIMULATION (données R+4).

Port : 8001
"""
from __future__ import annotations
import json
import pathlib
from typing import Optional

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from robot_ossature import extraire_ossature_com, ossature_simulation
from import_excel import creer_modele, lire_classeur

HERE = pathlib.Path(__file__).resolve().parent
# BNAY_DATA : dossier de données inscriptible (fixé par le lanceur .exe)
DATA = pathlib.Path(__import__("os").environ.get("BNAY_DATA", str(HERE.parent)))
REFS = DATA / "referentiels"

app = FastAPI(title="Bénayfacile — Service Robot", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def connecter_robot(lancer: bool = False):
    """Instance de Robot déjà ouverte par l'utilisateur.

    GetActiveObject ne lance jamais Robot. Dispatch, lui, démarrerait un Robot
    invisible s'il n'est pas ouvert : on ne l'utilise qu'en secours (lancer=True),
    pour les installations où Robot ne s'inscrit pas dans la table des objets actifs.
    """
    import win32com.client  # type: ignore
    try:   # les requêtes FastAPI tournent dans des fils de travail : COM doit y être initialisé
        import pythoncom  # type: ignore
        pythoncom.CoInitialize()
    except Exception:
        pass
    try:
        return win32com.client.GetActiveObject("Robot.Application")
    except Exception:
        if not lancer:
            raise
    try:   # bibliothèque de types : donne accès aux constantes RobotOM
        return win32com.client.gencache.EnsureDispatch("Robot.Application")
    except Exception:
        return win32com.client.Dispatch("Robot.Application")


# Codes d'erreur COM (HRESULT) les plus fréquents, traduits pour l'utilisateur
ROBOT_ABSENT = (-2147221005, -2147221164)          # CO_E_CLASSSTRING, REGDB_E_CLASSNOTREG
ROBOT_OCCUPE = (-2147418111, -2147417846)          # RPC_E_CALL_REJECTED, RPC_E_SERVERCALL_RETRYLATER
ROBOT_FERME = (-2147023174, -2147417848, -2147023170)   # RPC_S_SERVER_UNAVAILABLE, RPC_E_DISCONNECTED, RPC_S_CALL_FAILED
CONSEIL_EXCEL = "Sans Robot sur ce poste, téléchargez le modèle Excel, remplissez-le, puis importez-le."


def code_com(e: Exception) -> Optional[int]:
    """HRESULT d'une erreur pywin32 (com_error), sinon None."""
    for v in (getattr(e, "hresult", None), (getattr(e, "args", None) or [None])[0]):
        if isinstance(v, int):
            return v
    return None


def expliquer_erreur_robot(e: Exception) -> str:
    """Message lisible, avec la marche à suivre, pour une erreur de dialogue avec Robot."""
    code = code_com(e)
    if code in ROBOT_ABSENT:
        return ("Robot Structural Analysis n'est pas installé sur ce poste, ou son interface de programmation "
                "n'est pas enregistrée. Si Robot est installé, ouvrez-le une fois, puis réessayez ; sinon, réparez "
                "son installation (Paramètres Windows › Applications › Autodesk Robot Structural Analysis › Modifier › Réparer). "
                + CONSEIL_EXCEL)
    if code in ROBOT_OCCUPE:
        return ("Robot est occupé : une fenêtre ou un message y attend une réponse. Fermez-la dans Robot, "
                "puis réessayez.")
    if code in ROBOT_FERME:
        return "Robot a été fermé ou ne répond plus pendant la lecture. Rouvrez Robot, puis réessayez."
    if isinstance(e, ImportError):
        return "Le dialogue avec Robot (pywin32) n'est pas disponible sur ce poste. " + CONSEIL_EXCEL
    texte = str(e).strip() or e.__class__.__name__
    return texte[:1].upper() + texte[1:]


def processus_robot_ouvert() -> bool:
    """Un robot.exe tourne-t-il sur ce poste ? (Windows uniquement)"""
    import subprocess
    try:
        sortie = subprocess.run(["tasklist", "/FI", "IMAGENAME eq robot.exe", "/NH"], capture_output=True,
                                text=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return "robot.exe" in sortie.lower()
    except Exception:
        return False


def robot_disponible() -> tuple[bool, Optional[str]]:
    """True si un Robot est ouvert, sans jamais en démarrer un : connexion directe, ou
    processus robot.exe présent (Robot non inscrit dans la table des objets actifs)."""
    try:
        robot = connecter_robot(lancer=False)
        _ = robot.Name
        return True, None
    except Exception as e:
        if processus_robot_ouvert():
            return True, None          # la lecture passera par Dispatch, qui se rattachera à ce Robot
        return False, expliquer_erreur_robot(e)


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
        "nom": "Exemple de démonstration — immeuble R+4",
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
    robot = connecter_robot(lancer=True)
    projet = robot.Project                       # RobotOM : le projet ouvert dans Robot
    if projet is None or not getattr(projet, "IsActive", True):
        raise RuntimeError("aucun projet n'est ouvert dans Robot")
    nom = getattr(projet, "Name", "") or "Projet Robot"
    periods: list = []
    notes = ["Extraction COM réussie."]
    try:
        ossature = extraire_ossature_com(projet, cas_elu, cas_els)
        notes += ossature.get("remarques", [])
    except Exception as e:
        ossature = None
        notes.append(f"Ossature (poteaux, poutres, semelles, voiles) non lue : {expliquer_erreur_robot(e)}")
    return {
        "nom": nom,
        "nb_niveaux": len(ossature["niveaux"]) if ossature else None,
        "elements": ossature["resume"] if ossature else {},
        "cas_de_charge": (ossature or {}).get("cas", []),
        "combinaisons": [c["nom"] for c in (ossature or {}).get("cas", [])],
        "modal": {"T1_s": periods[0] if periods else None},
        "ossature": ossature,
        "notes": notes,
    }


@app.get("/health")
def health():
    ok, err = robot_disponible()
    return {"service": "robot", "status": "ok", "robot_com_disponible": ok,
            "detail": err if err else "Robot pilotable via COM", "mode_defaut": "simulation si COM indisponible"}


class OuvrirInput(BaseModel):
    chemin: str                     # fichier .rtd choisi par l'utilisateur
    calculer: bool = True           # lancer l'analyse si les résultats manquent
    cas_elu: Optional[int] = None
    cas_els: Optional[int] = None


def ouvrir_projet(chemin: str, calculer: bool = True) -> dict:
    """Ouvre un .rtd dans Robot (démarré au besoin, visible), puis lance l'analyse si
    les résultats ne sont pas disponibles. Le format .rtd est propriétaire : seul
    Robot sait le lire, d'où le passage par son API."""
    import os
    f = pathlib.Path(chemin)
    if f.suffix.lower() != ".rtd":
        raise ValueError("choisissez un fichier de projet Robot (.rtd)")
    if not f.is_file():
        raise ValueError(f"fichier introuvable : {chemin}")
    robot = connecter_robot(lancer=True)
    for attr in ("Visible", "Interactive"):   # Robot visible : licence, messages et calcul restent sous les yeux
        try:
            setattr(robot, attr, 1)
        except Exception:
            pass
    projet = robot.Project
    projet.Open(os.fspath(f.resolve()))
    etapes = [f"Projet ouvert dans Robot : {f.name}."]
    if calculer:
        try:
            disponibles = bool(projet.Structure.Results.Available)
        except Exception:
            disponibles = False
        if not disponibles:
            projet.CalcEngine.Calculate()
            etapes.append("Analyse lancée dans Robot (résultats absents du fichier).")
    return {"etapes": etapes}


class ExtractInput(BaseModel):
    chemin_fichier: Optional[str] = None
    forcer_simulation: bool = False
    cas_elu: Optional[int] = None    # numéro de la combinaison ELU dans Robot (sinon : nom contenant « ELU »)
    cas_els: Optional[int] = None


@app.get("/model")
def model(demo: bool = False):
    """Modèle du projet ouvert dans Robot. Le bâtiment de démonstration n'est renvoyé
    que sur demande explicite (?demo=true) : un projet réel ne doit jamais être
    remplacé en silence par des données d'exemple."""
    if demo:
        m = modele_simulation()
        m["mode"] = "simulation"
        m["robot_com"] = {"disponible": None, "demande": "démonstration"}
        return m
    ok, err = robot_disponible()
    if not ok:
        return {"mode": "indisponible", "robot_com": {"disponible": False, "erreur": err},
                "notes": ["Robot Structural Analysis n'est pas détecté. Ouvrez votre projet dans Robot, "
                          "lancez l'analyse, puis réessayez."]}
    try:
        m = extraire_com()
        m["mode"] = "robot"
        m["robot_com"] = {"disponible": True}
        return m
    except Exception as e:
        return {"mode": "indisponible", "robot_com": {"disponible": True, "erreur_extraction": str(e)},
                "notes": [f"Robot est ouvert mais le modèle n'a pas pu être lu. {expliquer_erreur_robot(e)} "
                          "Vérifiez qu'un projet est ouvert et que l'analyse a été lancée."]}


@app.post("/ouvrir")
def ouvrir(inp: OuvrirInput):
    """Ouvre le .rtd choisi dans Bénayfacile, calcule si nécessaire, puis lit le modèle."""
    try:
        etapes = ouvrir_projet(inp.chemin, inp.calculer)["etapes"]
    except ValueError as e:
        return {"mode": "indisponible", "notes": [f"Ouverture impossible : {e}."]}
    except Exception as e:
        if code_com(e) in ROBOT_ABSENT or isinstance(e, ImportError):
            note = expliquer_erreur_robot(e)
        else:
            note = (f"Robot n'a pas pu ouvrir ce projet. {expliquer_erreur_robot(e)} Vérifiez aussi que la "
                    "licence de Robot est active et que le fichier s'ouvre normalement dans Robot.")
        return {"mode": "indisponible", "robot_com": {"erreur": str(e)}, "notes": [note]}
    try:
        m = extraire_com(inp.cas_elu, inp.cas_els)
        m["mode"] = "robot"
        m["robot_com"] = {"disponible": True}
        m["notes"] = etapes + m.get("notes", [])
        return m
    except Exception as e:
        return {"mode": "indisponible", "robot_com": {"erreur_extraction": str(e)},
                "notes": etapes + [f"Le projet est ouvert mais n'a pas pu être lu. {expliquer_erreur_robot(e)}"]}


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TAILLE_MAX = 10 * 1024 * 1024


@app.get("/modele-excel")
def modele_excel():
    """Classeur vide à remplir (poteaux, poutres, semelles, voiles, trame)."""
    return Response(creer_modele(), media_type=XLSX,
                    headers={"Content-Disposition": 'attachment; filename="Modele_Benayfacile.xlsx"'})


@app.post("/import-excel")
async def import_excel(fichier: UploadFile = File(...)):
    """Modèle importé d'un classeur Excel : même format que la lecture Robot."""
    nom = pathlib.Path(fichier.filename or "classeur.xlsx").name
    octets = await fichier.read(TAILLE_MAX + 1)
    if len(octets) > TAILLE_MAX:
        return {"mode": "indisponible", "notes": ["Import impossible : fichier trop volumineux (10 Mo au plus)."]}
    if not nom.lower().endswith((".xlsx", ".xlsm")):
        return {"mode": "indisponible", "notes": ["Import impossible : choisissez un classeur Excel (.xlsx)."]}
    try:
        oss = lire_classeur(octets)
    except ValueError as e:
        return {"mode": "indisponible", "notes": [f"Import impossible : {e}."]}
    return {"mode": "excel", "nom": pathlib.Path(nom).stem, "ossature": oss,
            "nb_niveaux": len(oss["niveaux"]), "elements": oss["resume"],
            "notes": [f"Classeur importé : {nom}."] + oss["remarques"]}


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
