"""Service Rapport — génération de la NOTE DE CALCUL (HTML imprimable A4).

Entrée : état de session complet (Robot + modules moteur + bureau).
Port : 8004
"""
from __future__ import annotations
import datetime
import html
import io
import json
import pathlib
from typing import Any, Optional

import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from excel_report import classeur_octets, classeur_resultats  # noqa: F401
from note_calcul import construire
from note_docx import docx_depuis_html

HERE = pathlib.Path(__file__).resolve().parent
# BNAY_DATA : dossier de données inscriptible (fixé par le lanceur .exe)
DATA = pathlib.Path(__import__("os").environ.get("BNAY_DATA", str(HERE.parent)))
REFS = DATA / "referentiels"
OUT = DATA / "output"
OUT.mkdir(exist_ok=True)

app = FastAPI(title="Bénayfacile — Service Rapport", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class NoteInput(BaseModel):
    projet: str = "Projet"
    client: str = ""
    site: str = ""
    indice: str = "A"
    objet: str = ""
    architecte: str = ""
    controle: str = ""          # bureau de contrôle
    laboratoire: str = ""       # étude géotechnique
    phase: str = "Exécution"
    lot: Optional[dict] = None  # calcul en lot (quantités de béton et d'acier)
    robot: Optional[dict] = None
    sismique: Optional[dict] = None
    poteaux: Optional[list] = None
    poutres: Optional[list] = None
    semelles_isolees: Optional[list] = None
    semelles_filantes: Optional[list] = None
    voiles: Optional[list] = None
    dalles: Optional[list] = None
    balcons: Optional[list] = None
    planchers: Optional[list] = None
    bureau: Optional[dict] = None


def build_note(inp: NoteInput) -> str:
    """Note de calcul au format d'un bureau d'études (voir note_calcul.py)."""
    try:
        bur = inp.bureau or json.loads((REFS / "bureau.json").read_text(encoding="utf-8"))
    except Exception:
        bur = {}
    return construire(inp.model_dump(), bur or {})


@app.get("/health")
def health():
    return {"service": "report", "status": "ok"}

@app.post("/note", response_class=HTMLResponse)
def note(inp: NoteInput):
    return HTMLResponse(content=build_note(inp))

@app.post("/note/save")
def note_save(inp: NoteInput):
    h = build_note(inp)
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = OUT / f"Note_de_Calcul_{_slug(inp.projet)}_{now}.html"
    chemin.write_text(h, encoding="utf-8")
    return {"fichier": chemin.name, "octets": chemin.stat().st_size}

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@app.post("/note/docx")
def note_docx(inp: NoteInput):
    """Note de calcul au format Word : même contenu que la note HTML du projet (titres, tableaux,
    équations Word natives si Office est installé). Téléchargement : GET /note/docx/{nom}."""
    octets, stats = docx_depuis_html(build_note(inp), titre=f"Note de calcul — {inp.projet}")
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = OUT / f"Note_de_Calcul_{_slug(inp.projet)}_{now}.docx"
    chemin.write_bytes(octets)
    return {"fichier": chemin.name, "octets": len(octets), "dossier": str(OUT), **stats}


@app.get("/note/docx/{nom}")
def note_docx_telecharger(nom: str):
    return _fichier_output(nom, ".docx", DOCX)


def _fichier_output(nom: str, ext: str, media: str):
    # un simple nom de fichier du dossier output : pas de chemin
    if nom != pathlib.Path(nom).name or not nom.endswith(ext):
        raise HTTPException(400, "nom de fichier invalide")
    chemin = OUT / nom
    if not chemin.is_file():
        raise HTTPException(404, "fichier introuvable")
    return FileResponse(chemin, media_type=media, filename=nom)


# ───────────── classeur Excel des résultats du calcul en lot ─────────────
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExcelInput(BaseModel):
    projet: str = "Projet"
    client: str = ""
    site: str = ""
    indice: str = "A"
    lot: dict                      # réponse de POST /lot (moteur)
    bureau: Optional[dict] = None


def _slug(texte: str) -> str:
    t = re.sub(r"[^A-Za-z0-9]+", "_", texte.encode("ascii", "ignore").decode()).strip("_")
    return (t or "Projet")[:40]


@app.post("/excel")
def excel(inp: ExcelInput):
    """Écrit le classeur dans output/ et renvoie son nom (téléchargement : GET /excel/{nom})."""
    try:
        bur = inp.bureau or json.loads((REFS / "bureau.json").read_text(encoding="utf-8"))
    except Exception:
        bur = {}
    projet = {"projet": inp.projet, "client": inp.client, "site": inp.site, "indice": inp.indice}
    wb = classeur_resultats(inp.lot, projet, bur)
    flux = io.BytesIO()
    wb.save(flux)
    octets = flux.getvalue()
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = OUT / f"Note_de_Calcul_{_slug(inp.projet)}_{now}.xlsx"
    chemin.write_bytes(octets)
    return {"fichier": chemin.name, "octets": len(octets), "dossier": str(OUT), "metre": wb.metre}


@app.get("/excel/{nom}")
def excel_telecharger(nom: str):
    return _fichier_output(nom, ".xlsx", XLSX)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8004)
