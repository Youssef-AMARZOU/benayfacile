"""Service DXF — génération du plan de fondation (ezdxf).

Calques : AXES (rouge), COFFRAGE (vert), ACIER_LONG (magenta), CADRES (cyan),
          COTATION (jaune), CARTOUCHE (blanc)
Port : 8003
"""
from __future__ import annotations
import datetime
import pathlib
import json
from typing import List, Optional

import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.units import MM

from plans_ferraillage import dessiner_plans

HERE = pathlib.Path(__file__).resolve().parent
# BNAY_DATA : dossier de données inscriptible (fixé par le lanceur .exe)
DATA = pathlib.Path(__import__("os").environ.get("BNAY_DATA", str(HERE.parent)))
REFS = DATA / "referentiels"
OUT = DATA / "output"
OUT.mkdir(exist_ok=True)

app = FastAPI(title="Bénayfacile — Service DXF", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
LAYERS = {
    "AXES": 1, "COFFRAGE": 3, "ACIER_LONG": 6, "CADRES": 4, "COTATION": 2, "CARTOUCHE": 7,
}


class Footing(BaseModel):
    nom: str = "S1"
    A_m: float = 2.27
    B_m: float = 2.27
    H_m: float = 0.49
    d_m: float = 0.43
    asx_cm2: float = 19.6
    asy_cm2: float = 19.6
    acier_x: str = "13 HA14"
    acier_y: str = "13 HA14"
    cote_x_m: float = 0.0
    cote_y_m: float = 0.0


class DxfInput(BaseModel):
    projet: str = "Projet"
    client: str = ""
    site: str = ""
    indice: str = "A"
    echelle: str = "1:100"
    format: str = "A3"
    trame_x_m: List[float] = [0, 6, 12]
    trame_y_m: List[float] = [0, 5, 10]
    footings: List[Footing] = []
    bureau: Optional[dict] = None
    sortie: str = "plan_fondation"


def lire_bureau(inp_bureau: Optional[dict]) -> dict:
    if inp_bureau:
        return inp_bureau
    try:
        return json.loads((REFS / "bureau.json").read_text(encoding="utf-8"))
    except Exception:
        return {"nom": "Bureau d'études", "rc": "", "ice": "", "patente": "", "adresse": "", "telephone": "", "ingenieur": ""}


def mm(m: float, echelle: float = 100.0) -> float:
    return m * 1000.0 / echelle


def dessiner(inp: DxfInput) -> pathlib.Path:
    ech = 100.0
    if inp.echelle and ":" in inp.echelle:
        try:
            ech = float(inp.echelle.split(":")[1])
        except ValueError:
            ech = 100.0
    doc = ezdxf.new("R2010", setup=True)
    doc.units = MM
    msp = doc.modelspace()
    for name, color in LAYERS.items():
        if name in doc.layers:
            doc.layers.get(name).color = color
        else:
            doc.layers.add(name, color=color)

    BUR = lire_bureau(inp.bureau)
    now = datetime.date.today().strftime("%d/%m/%Y")

    # ---------- cadre de la feuille ----------
    ox, oy = 0, 0
    W, H = (297, 210)   # A3 paysage en dm ? -> on dessine en mm réels feuille A3: 420x297
    W, H = 420, 297
    msp.add_lwpolyline([(ox, oy), (W, oy), (W, H), (ox, H), (ox, oy)], dxfattribs={"layer": "CARTOUCHE", "lineweight": 30})

    # ---------- cartouche (bas droite) ----------
    cx0, cy0, cx1, cy1 = 212, 10, 408, 64
    msp.add_lwpolyline([(cx0, cy0), (cx1, cy0), (cx1, cy1), (cx0, cy1), (cx0, cy0)],
                       dxfattribs={"layer": "CARTOUCHE", "lineweight": 40})
    # lignes internes (bandes : 10-24 | 26-40 | 42-52 | 52-64)
    msp.add_line((cx0, cy0 + 14), (cx1, cy0 + 14), dxfattribs={"layer": "CARTOUCHE"})
    msp.add_line((cx0, cy0 + 32), (cx1, cy0 + 32), dxfattribs={"layer": "CARTOUCHE"})
    msp.add_line((cx0, cy0 + 44), (cx1, cy0 + 44), dxfattribs={"layer": "CARTOUCHE"})
    msp.add_line((cx0 + 96, cy0), (cx0 + 96, cy0 + 14), dxfattribs={"layer": "CARTOUCHE"})
    # bande haute : identité du bureau
    msp.add_text(str(BUR.get("nom", "Bureau d'études")),
                 dxfattribs={"layer": "CARTOUCHE", "height": 3.6, "insert": (cx0 + 3, cy0 + 44.5)})
    msp.add_text(f"{BUR.get('adresse', '')} — Tél {BUR.get('telephone', '')}",
                 dxfattribs={"layer": "CARTOUCHE", "height": 2.0, "insert": (cx0 + 3, cy0 + 48.5)})
    msp.add_text(f"RC : {BUR.get('rc', '')}   ICE : {BUR.get('ice', '')}",
                 dxfattribs={"layer": "CARTOUCHE", "height": 1.8, "insert": (cx0 + 3, cy0 + 33.5)})
    msp.add_text(f"Patente : {BUR.get('patente', '')}",
                 dxfattribs={"layer": "CARTOUCHE", "height": 1.8, "insert": (cx0 + 3, cy0 + 37.5)})
    # bande médiane : projet
    msp.add_text(f"Projet : {inp.projet}", dxfattribs={"layer": "CARTOUCHE", "height": 3.0, "insert": (cx0 + 3, cy0 + 27.2)})
    msp.add_text(f"Client : {inp.client}", dxfattribs={"layer": "CARTOUCHE", "height": 2.3, "insert": (cx0 + 3, cy0 + 18.3)})
    msp.add_text(f"Site : {inp.site}", dxfattribs={"layer": "CARTOUCHE", "height": 2.3, "insert": (cx0 + 3, cy0 + 13.8)})
    # bande basse : cartouche technique
    msp.add_text(f"Dessiné par : {BUR.get('ingenieur', '')}", dxfattribs={"layer": "CARTOUCHE", "height": 2.3, "insert": (cx0 + 3, cy0 + 5.5)})
    msp.add_text(f"Indice : {inp.indice}   Date : {now}", dxfattribs={"layer": "CARTOUCHE", "height": 2.3, "insert": (cx0 + 100, cy0 + 5.5)})
    msp.add_text(f"Échelle : {inp.echelle}   Format : {inp.format}", dxfattribs={"layer": "CARTOUCHE", "height": 2.3, "insert": (cx0 + 3, cy0 + 1.2)})

    # ---------- titre ----------
    msp.add_text("BÉNAYFACILE — PLAN DE FONDATION (SEMELLES ISOLÉES)",
                 dxfattribs={"layer": "CARTOUCHE", "height": 7.0, "insert": (20, H - 18)})
    msp.add_text(f"Projet : {inp.projet}   —   BAEL 91 rév. 99 / RPS 2000 v2011   —   Pose : axes cotés en mètres",
                 dxfattribs={"layer": "CARTOUCHE", "height": 2.6, "insert": (20, H - 26)})

    # ---------- implantation (plan) ----------
    gx0, gy0 = 30, 78          # origine plan dans la feuille (mm)
    trames_x, trames_y = inp.trame_x_m, inp.trame_y_m
    lx = mm(trames_x[-1] if trames_x else 10, ech)
    ly = mm(trames_y[-1] if trames_y else 10, ech)
    # axes (rouge, tireté)
    for i, x in enumerate(trames_x):
        px = gx0 + mm(x, ech)
        msp.add_line((px, gy0 - 6), (px, gy0 + ly + 6),
                     dxfattribs={"layer": "AXES", "linetype": "DASHED"})
        msp.add_circle((px, gy0 + ly + 10), 3.2, dxfattribs={"layer": "AXES"})
        msp.add_text(str(i + 1), dxfattribs={"layer": "AXES", "height": 3.0,
                                             "insert": (px, gy0 + ly + 9), "halign": 1})
    for j, y in enumerate(trames_y):
        py = gy0 + mm(y, ech)
        msp.add_line((gx0 - 6, py), (gx0 + lx + 6, py),
                     dxfattribs={"layer": "AXES", "linetype": "DASHED"})
        msp.add_circle((gx0 - 10, py), 3.2, dxfattribs={"layer": "AXES"})
        msp.add_text(chr(65 + j), dxfattribs={"layer": "AXES", "height": 3.0,
                                              "insert": (gx0 - 10, py - 1.1), "halign": 1})

    # cotes globales (jaune)
    y_cot = gy0 - 12
    msp.add_line((gx0, y_cot), (gx0 + lx, y_cot), dxfattribs={"layer": "COTATION"})
    for x in (gx0, gx0 + lx):
        msp.add_line((x, y_cot - 1.5), (x, y_cot + 1.5), dxfattribs={"layer": "COTATION"})
    msp.add_text(f"{trames_x[-1]:.2f} m", dxfattribs={"layer": "COTATION", "height": 3.0,
                                                      "insert": (gx0 + lx / 2, y_cot + 1), "halign": 1})
    x_cot = gx0 + lx + 8
    msp.add_line((x_cot, gy0), (x_cot, gy0 + ly), dxfattribs={"layer": "COTATION"})
    for y in (gy0, gy0 + ly):
        msp.add_line((x_cot - 1.5, y), (x_cot + 1.5, y), dxfattribs={"layer": "COTATION"})
    msp.add_text(f"{trames_y[-1]:.2f} m", dxfattribs={"layer": "COTATION", "height": 3.0,
                                                      "insert": (x_cot + 2, gy0 + ly / 2)})

    # semelles (vert) aux intersections de trames + aciers (magenta)
    hauteur_pied_acier = 1.6
    nb_acier_aff = 4
    if not inp.footings:
        inp.footings = [Footing(nom=f"S{k+1}", cote_x_m=x, cote_y_m=y)
                        for k, (x, y) in enumerate(((x, y) for y in trames_y for x in trames_x))]
    for f in inp.footings:
        cx, cy = gx0 + mm(f.cote_x_m, ech), gy0 + mm(f.cote_y_m, ech)
        hw, hh = mm(f.A_m, ech) / 2, mm(f.B_m, ech) / 2
        msp.add_lwpolyline([(cx - hw, cy - hh), (cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy + hh)],
                           close=True, dxfattribs={"layer": "COFFRAGE", "lineweight": 25})
        # aciers inférieurs (petits segments magenta en quinconce)
        nbar = min(6, max(3, int(f.A_m * 4)))
        for k in range(nbar):
            off = -hw + (2 * hw) * (k + 0.75) / (nbar + 0.5)
            msp.add_line((cx + off, cy - hh + 1.2), (cx + off, cy + hh - 1.2),
                         dxfattribs={"layer": "ACIER_LONG"})
        for k in range(nbar):
            off = -hh + (2 * hh) * (k + 0.75) / (nbar + 0.5)
            msp.add_line((cx - hw + 1.2, cy + off), (cx + hw - 1.2, cy + off),
                         dxfattribs={"layer": "ACIER_LONG"})
        msp.add_text(f"{f.nom}  A={f.A_m:.2f} B={f.B_m:.2f} H={f.H_m:.2f}",
                     dxfattribs={"layer": "COFFRAGE", "height": 2.1,
                                 "insert": (cx, cy - hh - 1.5), "halign": 1})

    # ---------- détail poteau (cyan) ----------
    dx, dy = 380, 122   # détail à droite, sous le tableau
    half = 9            # demi-largeur du poteau 30 cm à l'échelle détail (mm feuille)
    msp.add_lwpolyline([(dx - half, dy - half), (dx + half, dy - half),
                         (dx + half, dy + half), (dx - half, dy + half)],
                       close=True, dxfattribs={"layer": "CADRES", "lineweight": 30})
    for (bx, by) in [(dx - half + 2.2, dy - half + 2.2), (dx + half - 2.2, dy - half + 2.2),
                      (dx + half - 2.2, dy + half - 2.2), (dx - half + 2.2, dy + half - 2.2)]:
        msp.add_circle((bx, by), 1.5, dxfattribs={"layer": "ACIER_LONG"})
    msp.add_text("DÉTAIL POTEAU 30×30 — CADRES HA8 e=15 cm",
                 dxfattribs={"layer": "CADRES", "height": 2.6, "insert": (dx, dy + half + 3), "halign": 1})

    # ---------- tableau des semelles ----------
    ty = 244
    msp.add_text("TABLEAU DES SEMELLES", dxfattribs={"layer": "CARTOUCHE", "height": 3.2, "insert": (250, ty)})
    colonnes = ["N°", "A(m)", "B(m)", "H(m)", "d(m)", "Asx(cm²)", "Asy(cm²)", "Acier X", "Acier Y"]
    xcur = 222
    largeurs = [9, 11, 11, 10, 10, 16, 16, 27, 27]
    yrow = ty - 7
    # entêtes
    for c, w in zip(colonnes, largeurs):
        msp.add_text(c, dxfattribs={"layer": "CARTOUCHE", "height": 2.1, "insert": (xcur + 1, yrow)})
        xcur += w
    msp.add_line((220, yrow - 2), (220 + sum(largeurs), yrow - 2), dxfattribs={"layer": "CARTOUCHE"})
    yrow -= 4.6
    for f in inp.footings[:14]:
        xcur = 222
        valeurs = [f.nom, f"{f.A_m:.2f}", f"{f.B_m:.2f}", f"{f.H_m:.2f}", f"{f.d_m:.2f}",
                   f"{f.asx_cm2:.1f}", f"{f.asy_cm2:.1f}", f.acier_x, f.acier_y]
        for v, w in zip(valeurs, largeurs):
            msp.add_text(str(v), dxfattribs={"layer": "CARTOUCHE", "height": 1.9, "insert": (xcur + 1, yrow)})
            xcur += w
        yrow -= 4.2

    # ezdxf : align_point requis pour les textes halign≠0 (rendu/audit des ENTITÉS)
    for e in msp.query("TEXT"):
        try:
            if e.dxf.halign in (1, 2, 3) and (e.dxf.align_point is None or (e.dxf.align_point.x == 0 and e.dxf.align_point.y == 0)):
                e.dxf.align_point = e.dxf.insert
        except Exception:
            pass

    fname = f"{inp.sortie}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.dxf"
    chemin = OUT / fname
    doc.saveas(chemin)
    return chemin


@app.get("/health")
def health():
    return {"service": "dxf", "status": "ok", "ezdxf": ezdxf.__version__}


@app.post("/generate")
def generate(inp: DxfInput):
    chemin = dessiner(inp)
    return {"fichier": chemin.name, "chemin": str(chemin), "octets": chemin.stat().st_size,
            "calques": list(LAYERS), "format": "A3", "unites": "mm"}


class PlansInput(BaseModel):
    projet: str = "Projet"
    client: str = ""
    site: str = ""
    indice: str = "A"
    lot: dict                          # réponse de POST /lot (moteur)
    trame_x_m: List[float] = []
    trame_y_m: List[float] = []
    bureau: Optional[dict] = None


def _slug(texte: str) -> str:
    t = re.sub(r"[^A-Za-z0-9]+", "_", texte.encode("ascii", "ignore").decode()).strip("_")
    return (t or "Projet")[:40]


@app.post("/plans")
def plans(inp: PlansInput):
    """Dossier de plans de ferraillage de tout le modèle (un DXF, plusieurs planches A1)."""
    projet = {"projet": inp.projet, "client": inp.client, "site": inp.site, "indice": inp.indice}
    doc, resume = dessiner_plans(inp.lot, projet, lire_bureau(inp.bureau), inp.trame_x_m, inp.trame_y_m)
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = OUT / f"Plans_Ferraillage_{_slug(inp.projet)}_{now}.dxf"
    doc.saveas(chemin)
    return {"fichier": chemin.name, "octets": chemin.stat().st_size, "dossier": str(OUT), **resume}


@app.get("/download/{nom}")
def download(nom: str):
    # un simple nom de fichier .dxf du dossier output : pas de chemin (« ..\ » sous Windows)
    if nom != pathlib.Path(nom).name or not nom.lower().endswith(".dxf"):
        raise HTTPException(400, "nom de fichier invalide")
    chemin = OUT / nom
    if not chemin.is_file():
        raise HTTPException(404, "fichier introuvable")
    return FileResponse(chemin, media_type="application/dxf", filename=nom)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8003)
