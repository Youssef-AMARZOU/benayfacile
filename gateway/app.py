"""Bénayfacile — Gateway (port 8090).

- Sert le tableau de bord (static/)
- Proxy /api/<service>/* vers les microservices FastAPI :
    /api/robot/*    -> 8001
    /api/engine/*   -> 8002
    /api/dxf/*      -> 8003
    /api/report/*   -> 8004
- /api/bureau (GET/PUT) : données du bureau (référentiels/bureau.json)
- /api/demo : scénario de démonstration pré-rempli
"""
from __future__ import annotations
import json
import os
import pathlib

import requests
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
# BNAY_DATA : dossier de données inscriptible (fixé par le lanceur .exe)
REFS = pathlib.Path(os.environ.get("BNAY_DATA", str(ROOT))) / "referentiels"
STATIC = HERE / "static"

# Adresses des microservices. Le lanceur de l'application de bureau choisit des
# ports libres au démarrage et les transmet par BNAY_URL_<SERVICE> ; les valeurs
# par défaut correspondent à run_services.bat.
SERVICES = {
    "robot": os.environ.get("BNAY_URL_ROBOT", "http://127.0.0.1:8001"),
    "engine": os.environ.get("BNAY_URL_ENGINE", "http://127.0.0.1:8002"),
    "dxf": os.environ.get("BNAY_URL_DXF", "http://127.0.0.1:8003"),
    "report": os.environ.get("BNAY_URL_REPORT", "http://127.0.0.1:8004"),
}

# Appels internes en boucle locale : ignorer les proxys système (HTTP_PROXY,
# proxy Windows), qui casseraient les appels vers 127.0.0.1 sur certains postes.
_HTTP = requests.Session()
_HTTP.trust_env = False

app = FastAPI(title="Bénayfacile — Gateway", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    status = {}
    for name, base in SERVICES.items():
        try:
            r = _HTTP.get(base + "/health", timeout=2.5)
            status[name] = "ok" if r.ok else f"erreur {r.status_code}"
        except Exception as e:
            status[name] = f"injoignable ({e})"
    return {"service": "gateway", "status": "ok", "services": status}


@app.get("/api/dxf/download/{nom}")
def dxf_download(nom: str):
    url = SERVICES["dxf"] + f"/download/{nom}"
    r = _HTTP.get(url, timeout=60)
    if r.status_code != 200:
        raise HTTPException(r.status_code, "fichier introuvable")
    return Response(content=r.content, media_type="application/dxf",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@app.get("/api/report/excel/{nom}")
def excel_download(nom: str):
    # route dédiée (le proxy générique ne transmet pas Content-Disposition)
    r = _HTTP.get(SERVICES["report"] + f"/excel/{nom}", timeout=60)
    if r.status_code != 200:
        raise HTTPException(r.status_code, "fichier introuvable")
    return Response(content=r.content,
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"'})


@app.get("/api/bureau")
def bureau_get():
    try:
        return json.loads((REFS / "bureau.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


@app.put("/api/bureau")
async def bureau_put(request: Request):
    data = await request.json()
    allowed = {"nom", "adresse", "telephone", "email", "ingenieur", "rc", "if_", "ice", "patente", "logo_base64", "cachet_base64", "_note"}
    data = {k: v for k, v in data.items() if k in allowed}
    (REFS / "bureau.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"saved": True, "chemin": str(REFS / "bureau.json")}


@app.get("/api/demo")
def demo():
    """Scénario de démonstration R+4 (identique à la simulation Robot)."""
    return {
        "projet": "Exemple — immeuble R+4",
        "client": "Démonstration",
        "site": "Casablanca, Maroc",
        "robot": {"simuler": True},
        "sismique": {"hauteur_m": 15.0, "longueur_contreventement_m": 12.0,
                     "g_kn": 3800, "q_kn": 1200, "usage": "habitation_admin",
                     "zone_vitesse": 3, "rapport_za_zv": "za_eq_zv", "site": "S2",
                     "classe": "classe_II", "systeme": "portiques_ba", "ductilite": "ND1",
                     "periode_methode": "portique", "amortissement_pct": 5.0,
                     "niveaux": [
                         {"nom": "RDC", "w_kn": 950, "h_m": 0.0},
                         {"nom": "R+1", "w_kn": 820, "h_m": 3.0},
                         {"nom": "R+2", "w_kn": 820, "h_m": 6.0},
                         {"nom": "R+3", "w_kn": 820, "h_m": 9.0},
                         {"nom": "R+4", "w_kn": 700, "h_m": 12.0},
                         {"nom": "Acrotère", "w_kn": 180, "h_m": 15.0},
                     ]},
        "poteaux": [{"a_cm": 30, "b_cm": 30, "lf_m": 3.0, "fc28_mpa": 25, "fe_mpa": 500,
                     "nu_kn": 950, "mx_knm": 25, "my_knm": 10}],
        "poutres": [{"b_cm": 25, "h_cm": 50, "enrobage_mm": 40, "fc28_mpa": 25, "fe_mpa": 500,
                     "mu_knm": 120, "vu_kn": 90, "fissuration": "prejudiciable"}],
        "semelles_isolees": [{"ns_kn": 950, "a_poteau_cm": 30, "b_poteau_cm": 30,
                              "sigma_sol_bar": 2.0, "fc28_mpa": 25, "fe_mpa": 500}],
        "voiles": [{"longueur_m": 4.0, "ep_cm": 18, "fc28_mpa": 25, "fe_mpa": 500,
                    "n_kn": 1200, "m_knm": 260, "v_kn": 180}],
    }


# Proxy générique : déclaré APRÈS les routes /api/... dédiées, que FastAPI doit trouver d'abord.
@app.api_route("/api/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(service: str, path: str, request: Request):
    base = SERVICES.get(service)
    if not base:
        raise HTTPException(404, f"service inconnu : {service}")
    url = f"{base}/{path}"
    params = dict(request.query_params)
    try:
        if request.method == "GET":
            r = _HTTP.get(url, params=params, timeout=60)
        else:
            body = await request.body()
            headers = {"Content-Type": request.headers.get("content-type", "application/json")}
            r = _HTTP.request(request.method, url, data=body, params=params, headers=headers, timeout=120)
    except requests.RequestException as e:
        raise HTTPException(502, f"service {service} injoignable : {e}")
    content_type = r.headers.get("content-type", "application/octet-stream")
    return Response(content=r.content, status_code=r.status_code,
                    media_type=content_type.split(";")[0],
                    headers={"x-upstream-status": str(r.status_code)})


app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8090)
