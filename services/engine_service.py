"""Moteur de calcul béton armé / sismique — BAEL 91 rév. 99 et RPS 2000 v2011.

Conventions d'unités (partout) :
  longueurs  : m        (sections en cm pour les entrées de section)
  efforts    : kN       moments : kN.m
  contraintes: MPa      sections d'acier en cm²

Toutes les valeurs normatives proviennent de ../referentiels/*.json, extraites
des textes officiels (DTU P18-702 ; RPS 2000-Version 2011).
"""
from __future__ import annotations
import json
import math
import pathlib
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import choisir_barres, section_bar

HERE = pathlib.Path(__file__).resolve().parent
# BNAY_DATA : dossier de données inscriptible (fixé par le lanceur .exe)
DATA = pathlib.Path(__import__("os").environ.get("BNAY_DATA", str(HERE.parent)))
REFS = DATA / "referentiels"
BAEL = json.loads((REFS / "bael.json").read_text(encoding="utf-8"))
RPS = json.loads((REFS / "rps.json").read_text(encoding="utf-8"))

GAMMA_B = BAEL["gamma_b"]["fondamental"]
GAMMA_S = BAEL["gamma_s"]["fondamental"]

# --------------------------------------------------------------------------- #
# Fonctions mécaniques BAEL — flexion simple (diagramme rectangulaire 0,8 yu) #
# --------------------------------------------------------------------------- #
def ft28(fc28: float) -> float:
    return 0.6 + 0.06 * fc28

def sigma_bc_elu(fc28: float, theta: float = 1.0) -> float:
    return 0.85 * fc28 / (theta * GAMMA_B)

def sigma_s_elu(fe: float) -> float:
    return fe / GAMMA_S

def mu_lim(fe: float) -> float:
    return BAEL["mu_lim"]["fe400"] if fe <= 400 else BAEL["mu_lim"]["fe500"]

def alpha_lim(fe: float) -> float:
    return BAEL["alpha_lim"]["fe400"] if fe <= 400 else BAEL["alpha_lim"]["fe500"]

def non_fragilite(b_cm: float, d_m: float, fc28: float, fe: float) -> float:
    """As,min de non-fragilité en cm² (BAEL A.4.2) : As >= 0.23 b d ftj / fe."""
    ft = ft28(fc28)
    return 0.23 * (b_cm / 100.0) * d_m * (ft * 1e6) / (fe * 1e6) * 1e4


def flexion_simple_elu(b_cm: float, h_cm: float, d_m: float, fc28: float, fe: float,
                       mu_knm: float) -> dict:
    """Calcul ELU simple, aciers tendus (diagramme rectangulaire 0,8 yu, BAEL)."""
    bc = b_cm / 100.0
    sbc = sigma_bc_elu(fc28)
    ss = sigma_s_elu(fe)
    mu = (mu_knm * 1000.0) / (bc * d_m**2 * sbc * 1e6)
    if mu > mu_lim(fe):
        # aciers comprimés nécessaires
        d_prime = 0.045  # m, hypothèse enrobage+diamètre/2 (à ajuster par l'ingénieur)
        # moment équilibré par aciers tendus à pivot limite B
        alphal = alpha_lim(fe)
        Zl = d_m * (1 - 0.4 * alphal)
        mu_l = mu_lim(fe)
        As1 = (mu_l * bc * d_m**2 * sbc * 1e6) / (Zl * ss * 1e6) * 1e4  # N->cm2
        Asc = ((mu - mu_l) * bc * d_m**2 * sbc * 1e6) / ((d_m - d_prime) * ss * 1e6) * 1e4
        As = As1 + Asc
        return {"mode": "aciers comprimés", "mu": round(mu, 4), "mu_lim": mu_lim(fe),
                "alpha": alphal, "z_m": round(Zl, 4), "as_cm2": round(As, 2),
                "as_comprimes_cm2": round(Asc, 2), "d_prime_m": d_prime,
                "sigma_bc_mpa": round(sbc, 2), "sigma_s_mpa": round(ss, 1)}
    alpha = 1.25 * (1 - math.sqrt(1 - 2 * mu)) if mu > 0 else 0.0
    z = d_m * (1 - 0.4 * alpha)
    As = (mu_knm * 1000.0) / (z * ss * 1e6) * 1e4
    return {"mode": "simple", "mu": round(mu, 4), "mu_lim": mu_lim(fe),
            "alpha": round(alpha, 4), "z_m": round(z, 4), "as_cm2": round(As, 2),
            "as_comprimes_cm2": 0.0,
            "sigma_bc_mpa": round(sbc, 2), "sigma_s_mpa": round(ss, 1)}


# --------------------------------------------------------------------------- #
# SLS (ELS) béton armé — n = 15, résolution complète                           #
# --------------------------------------------------------------------------- #
def _resolve_y(b_cm: float, d_m: float, as_cm2: float, asc_cm2: float = 0.0,
               dprime_m: float = 0.045, n: int = 15) -> float:
    """Profondeur de l'axe neutre y (m) à l'ELS."""
    bc = b_cm / 100.0
    As = as_cm2 / 1e4
    Asc = asc_cm2 / 1e4

    def eq(y):
        return bc * y**2 / 2 + n * As * (d_m - y) - n * Asc * (y - dprime_m)
    lo, hi = 1e-6, d_m
    flo, fhi = eq(lo), eq(hi)
    tries = 0
    while flo * fhi > 0 and tries < 40:
        hi *= 1.5
        fhi = eq(hi)
        tries += 1
    if flo * fhi > 0:
        return float("nan")
    import numpy as np
    xs = np.linspace(lo, hi, 2000)
    vals = [eq(x) for x in xs]
    for i in range(len(xs) - 1):
        if vals[i] == 0:
            return xs[i]
        if vals[i] * vals[i + 1] < 0:
            x0, x1 = xs[i], xs[i + 1]
            f0 = vals[i]
            for _ in range(60):
                xm = 0.5 * (x0 + x1)
                fm = eq(xm)
                if f0 * fm <= 0:
                    x1 = xm
                else:
                    x0, f0 = xm, fm
            return 0.5 * (x0 + x1)
    return float("nan")


def flex_els(b_cm: float, d_m: float, as_cm2: float, fc28: float, fe: float,
             msser_knm: float, fissuration: str = "prejudiciable") -> dict:
    """Vérification ELS (n=15) : σbc ≤ 0.6 fc28 ; σst ≤ limite de fissuration."""
    bc = b_cm / 100.0
    As = as_cm2 / 1e4
    y = _resolve_y(b_cm, d_m, as_cm2)
    if math.isnan(y):
        return {"erreur": "axe neutre non trouvé"}
    I = bc * y**3 / 3 + 15 * As * (d_m - y) ** 2
    Ms = msser_knm * 1000.0  # N.m
    K = Ms / I  # N/m -> contrainte à la fibre / y
    sigma_bc = K * y / 1e6
    sigma_st = 15 * K * (d_m - y) / 1e6
    ft = ft28(fc28)
    eta = BAEL["fissuration"]["eta"]["ha"]
    if fissuration == "peu_prejudiciable":
        sig_lim = 2 / 3 * fe
    elif fissuration == "prejudiciable":
        sig_lim = min(2 / 3 * fe, max(0.5 * fe, 110 * math.sqrt(eta * ft)))
    else:  # tres_prejudiciable
        sig_lim = 0.8 * min(2 / 3 * fe, max(0.5 * fe, 110 * math.sqrt(eta * ft)))
    return {
        "axe_neutre_y_m": round(y, 4), "inertie_I_m4": f"{I:.3e}",
        "sigma_bc_mpa": round(sigma_bc, 2), "sigma_bc_lim_mpa": 0.6 * fc28,
        "sigma_bc_ok": sigma_bc <= 0.6 * fc28,
        "sigma_st_mpa": round(sigma_st, 1), "sigma_st_lim_mpa": round(sig_lim, 1),
        "sigma_st_ok": sigma_st <= sig_lim,
        "fissuration": fissuration,
    }


# --------------------------------------------------------------------------- #
# Poteau BAEL B.8.4,1 — compression centrée + flexion composée (numérique)    #
# --------------------------------------------------------------------------- #
def _steel_stress(eps: float) -> float:
    """ε>0 compression; fe/γs plateau; 200 GPa."""
    fe_s = float(fe_global) / GAMMA_S
    es = eps * 200e3  # MPa
    if es >= fe_s:
        return fe_s
    if es <= -fe_s:
        return -fe_s
    return es

fe_global = 500.0


def poteau_b84(a_cm: float, b_cm: float, lf_m: float, fc28: float, fe: float,
               nu_kn: float, mx_knm: float = 0.0, my_knm: float = 0.0,
               cover_mm: float = 30.0, bar_mm: float = 14.0):
    """Compression centrée (B.8.4,1) : Nu_lim(α, Br) -> As requise."""
    global fe_global
    fe_global = fe
    a_m, b_m = a_cm / 100.0, b_cm / 100.0
    i_x = a_m / math.sqrt(12.0)   # flambement autour axe fort (i max)
    i_y = b_m / math.sqrt(12.0)
    i_min = min(i_x, i_y)
    lam = lf_m / i_min
    lam_x, lam_y = lf_m / i_x, lf_m / i_y
    applicable = lam <= BAEL["poteau"]["lambda_max"]
    if lam <= 50:
        alpha = 0.85 / (1 + 0.2 * (lam / 35) ** 2)
    else:
        alpha = 0.60 * (50 / lam) ** 2
    Br_m2 = (a_m - 0.02) * (b_m - 0.02)
    B = a_m * b_m
    ny_lim_no_steel = alpha * Br_m2 * fc28 * 1e6 / (0.9 * GAMMA_B)  # N
    # solve for A
    nu_n = nu_kn * 1000.0
    if nu_n <= ny_lim_no_steel:
        as_req = 0.0
    else:
        as_req = (nu_n / alpha - Br_m2 * fc28 * 1e6 / (0.9 * GAMMA_B)) * GAMMA_S / (fe * 1e6) * 1e4
    perim_m = 2 * (a_m + b_m)
    as_min_long = 4.0 * perim_m  # cm²  (4 cm2/m * perimetre)
    as_min_sect = 0.002 * B * 1e4  # 0.2% B -> cm²
    as_calc = max(as_req, as_min_long, as_min_sect)
    as_max = 0.05 * B * 1e4
    note = []
    if lam > BAEL["poteau"]["lambda_max"]:
        note.append(f"λ = {lam:.1f} > 70 : méthode forfaitaire B.8.4,1 NON applicable — justification E.7 (2e ordre) exigée.")
    elif lam > 35:
        note.append("λ > 35 : ne retenir que les armatures augmentant la rigidité (les plus éloignées du plan de flambement).")
    choix = choisir_barres(as_calc, d_max_mm=32, n_max=16, symetrique=True)
    # un poteau a besoin de 4 armatures au minimum (angles)
    if choix["n"] < 4:
        from common import section_bar as _sb
        import math as _math
        # garder le Ø choisi, passer à 4 barres (ou Ø supérieur si insuffisant)
        d = choix["diametre_mm"]
        while 4 * _sb(d) < as_calc and d < 32:
            d = {8: 10, 10: 12, 12: 14, 14: 16, 16: 20, 20: 25, 25: 32}[d]
        choix = {"n": 4, "diametre_mm": d,
                 "as_fournie_cm2": round(4 * _sb(d), 2)}
        choix["ecart_cm2"] = round(choix["as_fournie_cm2"] - as_calc, 2)
        choix["surdimensionnement_pct"] = round(100.0 * choix["ecart_cm2"] / as_calc, 1) if as_calc else None
        choix["choix"] = f"4 HA{d:.0f} (barres d'angles)"
    else:
        choix["choix"] = f"{choix['n']} HA{choix['diametre_mm']:.0f} (symétrique)"
    as_fournie = choix["as_fournie_cm2"]
    nu_lim = alpha * (Br_m2 * fc28 * 1e6 / (0.9 * GAMMA_B) + as_fournie * 1e-4 * fe * 1e6 / GAMMA_S) / 1000.0
    return {
        "applicable_b841": applicable,
        "a_cm": a_cm, "b_cm": b_cm, "lf_m": lf_m,
        "lambda": round(lam, 2), "lambda_x": round(lam_x, 2), "lambda_y": round(lam_y, 2),
        "i_min_m": round(i_min, 4), "alpha": round(alpha, 4),
        "Br_m2": round(Br_m2, 4), "B_m2": round(B, 4),
        "as_requis_cm2": round(as_req, 2),
        "as_min_long_cm2": round(as_min_long, 2), "as_min_sect_cm2": round(as_min_sect, 2),
        "as_calculee_cm2": round(as_calc, 2), "as_max_5pct_cm2": round(as_max, 2),
        "ferraillage": choix, "notes": note,
        "nu_lim_kn_avec_as_fournie": round(nu_lim, 1),
        "nu_kn": nu_kn, "nu_rapport": round(nu_kn / nu_lim, 3) if nu_lim > 0 else None,
    }


def poteau_moment_capacity(a_cm: float, h_cm: float, as_fournie_cm2: float, fc28: float, fe: float,
                           nu_kn: float, cover_mm: float = 30.0, bar_mm: float = 14.0,
                           moment_knm: float = 0.0) -> dict:
    """Capacité MRd en flexion composée (compression), diagramme rectangulaire 0,8 y.

    Résolution numérique de la profondeur d'axe neutre pour N fixé (N>0 compression).
    Acier symétrique (même section en tête et pieds).
    """
    global fe_global
    fe_global = fe
    a_m = a_cm / 100.0
    h_m = h_cm / 100.0
    half = as_fournie_cm2 / 2.0 / 1e4  # m² par nappe
    dprime = (cover_mm + bar_mm / 2) / 1000.0
    y_top = dprime
    y_bot = h_m - dprime
    sbc = sigma_bc_elu(fc28) * 1e6
    nu_n = nu_kn * 1000.0

    def forces(x):
        eps_c = 3.5e-3
        C = sbc * a_m * min(0.8 * x, h_m)
        # centroïde du diagramme rectangulaire : 0.4x depuis la fibre comprimée (ou h/2 si section capée)
        yc = 0.4 * x if 0.8 * x < h_m else h_m / 2.0
        f_top = half * _steel_stress(eps_c * (x - y_top) / x) if x > 0 else 0.0
        f_bot = half * _steel_stress(eps_c * (x - y_bot) / x) if x > 0 else 0.0
        nf = C + f_top + f_bot
        m = C * (h_m / 2.0 - yc) + f_top * (h_m / 2.0 - y_top) + f_bot * (h_m / 2.0 - y_bot)
        return nf, m

    # recherche du x équilibrant N par balayage + brentq
    import numpy as np
    xs = np.logspace(-3, 2.2, 400)
    prev_x, prev_f = xs[0], forces(xs[0])[0] - nu_n
    x_star = None
    for x in xs[1:]:
        fx = forces(x)[0] - nu_n
        if prev_f == 0:
            x_star = prev_x
            break
        if fx == 0:
            x_star = x
            break
        if prev_f * fx < 0:
            # bissection (40 itérations — pas de dépendance scipy)
            x0, x1, f0 = prev_x, x, prev_f
            for _ in range(40):
                xm = 0.5 * (x0 + x1)
                fm = forces(xm)[0] - nu_n
                if f0 * fm <= 0:
                    x1 = xm
                else:
                    x0, f0 = xm, fm
            x_star = 0.5 * (x0 + x1)
            break
        prev_x, prev_f = x, fx
    if x_star is None:
        # pas de racine : prendre x minimisant l'écart
        x_star = min(xs, key=lambda xx: abs(forces(xx)[0] - nu_n))
    nf, m = forces(x_star)
    m_cap_knm = abs(m) / 1000.0
    ratio = abs(moment_knm) / m_cap_knm if m_cap_knm > 0 else None
    return {"x_axe_neutre_m": round(x_star, 4), "moment_capable_knm": round(m_cap_knm, 2),
            "moment_applique_knm": round(abs(moment_knm), 2),
            "taux_utilisation_moment": round(ratio, 3) if ratio is not None else None,
            "n_verification_kn": round(nf / 1000.0, 1),
            "hypotheses": "diagramme rectangulaire 0,8 y, acier symétrique nappe tête/pieds, εc = 3,5 ‰ (pivot B) ; si section entièrement comprimée résultat à justifier par A.4.4 / E.7."}


# --------------------------------------------------------------------------- #
# Modèles d'E/S FastAPI                                                       #
# --------------------------------------------------------------------------- #
class PoteauInput(BaseModel):
    a_cm: float = Field(..., gt=5, description="petit côté (cm)")
    b_cm: float = Field(..., gt=5)
    lf_m: float = Field(..., gt=0, description="longueur de flambement (m)")
    fc28_mpa: float = Field(25.0, ge=12)
    fe_mpa: float = Field(500.0)
    nu_kn: float = Field(..., gt=0)
    mx_knm: float = 0.0
    my_knm: float = 0.0
    cover_mm: float = 30.0

class PoutreInput(BaseModel):
    b_cm: float = Field(..., gt=10)
    h_cm: float = Field(..., gt=15)
    enrobage_mm: float = 40.0
    fc28_mpa: float = 25.0
    fe_mpa: float = 500.0
    mu_knm: float = Field(..., ge=0)
    vu_kn: float = Field(0.0, ge=0)
    ms_knm: Optional[float] = None
    fissuration: str = "prejudiciable"

class SemelleInput(BaseModel):
    ns_kn: float = Field(..., gt=0, description="effort normal service (kN)")
    nu_kn: Optional[float] = None
    Mx_knm: float = 0.0
    My_knm: float = 0.0
    a_poteau_cm: float = Field(30.0, gt=0)
    b_poteau_cm: float = Field(30.0, gt=0)
    sigma_sol_bar: float = Field(2.0, gt=0, description="contrainte admissible sol (bar)")
    fc28_mpa: float = 25.0
    fe_mpa: float = 500.0
    cover_mm: float = 50.0

class SemelleFilanteInput(SemelleInput):
    longueur_m: float = 1.0

class VoileInput(BaseModel):
    longueur_m: float = Field(..., gt=0.3, description="longueur du voile (m)")
    ep_cm: float = Field(..., ge=12, le=100)
    fc28_mpa: float = 25.0
    fe_mpa: float = 500.0
    n_kn: float = Field(..., gt=0)
    m_knm: float = 0.0
    v_kn: float = 0.0
    fissuration: str = "prejudiciable"

class Niveau(BaseModel):
    nom: str
    w_kn: float
    h_m: float

class SismiqueInput(BaseModel):
    hauteur_m: float = Field(..., gt=0)
    longueur_contreventement_m: float = Field(..., gt=0)
    w_kn: Optional[float] = None
    g_kn: Optional[float] = None
    q_kn: Optional[float] = None
    usage: str = "habitation_admin"
    zone_vitesse: int = Field(2, ge=0, le=4)
    rapport_za_zv: str = "za_eq_zv"   # za_gt_zv / za_eq_zv / za_lt_zv
    site: str = "S2"
    classe: str = "classe_III"
    systeme: str = "portiques_ba"
    ductilite: str = "ND2"
    periode_methode: str = "portique"  # portique | acier_noeuds_rigides | autre | manuel
    t_manuel_s: Optional[float] = None
    niveaux: Optional[List[Niveau]] = None
    amortissement_pct: float = 5.0


# --------------------------------------------------------------------------- #
# Application FastAPI                                                          #
# --------------------------------------------------------------------------- #
app = FastAPI(title="Bénayfacile — Moteur BAEL/RPS", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(Exception)
async def _all(request, exc):
    return JSONResponse(status_code=500, content={"erreur": str(exc)})

@app.get("/health")
def health():
    return {"service": "engine", "status": "ok", "referentiels": ["bael.json", "rps.json"]}

@app.get("/referentiels")
def referentiels():
    return {"bael": BAEL, "rps": RPS}

@app.post("/poteau")
def poteau(inp: PoteauInput):
    res = poteau_b84(inp.a_cm, inp.b_cm, inp.lf_m, inp.fc28_mpa, inp.fe_mpa,
                     inp.nu_kn, inp.mx_knm, inp.my_knm, inp.cover_mm)
    # dimensionnement en flexion composée sur la section retenue
    m = math.hypot(inp.mx_knm, inp.my_knm)
    as_ok = res["ferraillage"]["as_fournie_cm2"]
    moment = poteau_moment_capacity(inp.a_cm, inp.b_cm, as_ok, inp.fc28_mpa, inp.fe_mpa,
                                    inp.nu_kn, inp.cover_mm,
                                    res["ferraillage"]["diametre_mm"], moment_knm=m)
    # audit
    lam = res["lambda"]
    alpha = res["alpha"]
    from common import audit_ligne
    res["audit"] = [
        audit_ligne("λ = lf/i", inp.lf_m / (min(inp.a_cm, inp.b_cm) / 100.0 / math.sqrt(12)), lam, 0.02),
        audit_ligne("Nu_lim recalculé", (alpha * (res["Br_m2"] * inp.fc28_mpa * 1e6 / (0.9 * GAMMA_B)
                                                 + as_ok * 1e-4 * inp.fe_mpa * 1e6 / GAMMA_S)) / 1000.0,
                    res["nu_lim_kn_avec_as_fournie"], 0.5),
    ]
    res["flexion_composee"] = moment
    return res

@app.post("/poutre")
def poutre(inp: PoutreInput):
    h_m = inp.h_cm / 100.0
    d_m = h_m - (inp.enrobage_mm + 10) / 1000.0   # d ≈ h - c - φ/2 (φ≈20 mm estimé)
    res = flexion_simple_elu(inp.b_cm, inp.h_cm, d_m, inp.fc28_mpa, inp.fe_mpa, inp.mu_knm)
    # non-fragilité
    as_nf = non_fragilite(inp.b_cm, d_m, inp.fc28_mpa, inp.fe_mpa)
    as_final = max(res["as_cm2"], as_nf)
    choix = choisir_barres(as_final, d_max_mm=32, n_max=8)
    res["as_non_fragilite_cm2"] = round(as_nf, 2)
    res["as_retenue_cm2"] = round(as_final, 2)
    res["ferraillage"] = choix
    res["d_m"] = round(d_m, 4)
    res["b_cm"] = inp.b_cm
    res["h_cm"] = inp.h_cm
    # ELS
    ms = inp.ms_knm if inp.ms_knm else inp.mu_knm / 1.5
    res["els"] = flex_els(inp.b_cm, d_m, choix["as_fournie_cm2"], inp.fc28_mpa, inp.fe_mpa,
                          ms, inp.fissuration)
    # effort tranchant (approximation usuelle BAEL)
    bc = inp.b_cm / 100.0
    tau_u = (inp.vu_kn * 1000.0) / (bc * d_m * 1e6)  # MPa
    tau_lim = 0.15 * inp.fc28_mpa / GAMMA_B
    ats = (inp.vu_kn * 1000.0) / (0.9 * d_m * sigma_s_elu(inp.fe_mpa) * 1e6) * 1e4  # cm²/m
    res["effort_tranchant"] = {
        "tau_u_mpa": round(tau_u, 3), "tau_u_lim_mpa": round(tau_lim, 2),
        "tau_u_ok": bool(tau_u <= tau_lim),
        "at_cm2_par_m": round(ats, 2),
        "attention": "treillis 45°, sans majoration ; vérifier B.7.4 et l'espacement réel des cadres sur le plan d'exécution.",
    }
    from common import audit_ligne
    res["audit"] = [
        audit_ligne("Mu = b d² σbc μ", res["mu"] * (inp.b_cm / 100.0) * d_m**2 * sigma_bc_elu(inp.fc28_mpa) * 1e6 / 1000.0, inp.mu_knm, 0.05),
        audit_ligne("As = Mu/(Z σs)", inp.mu_knm * 1000.0 / (res["z_m"] * sigma_s_elu(inp.fe_mpa) * 1e6) * 1e4, res["as_cm2"], 0.05),
    ]
    return res

def _dimensionner_semelle(inp, unite: str):
    sigma_sol_pa = inp.sigma_sol_bar * 1e5  # bar -> Pa (1 bar = 0.1 MPa = 1e5 Pa)
    nu_kn = inp.nu_kn if inp.nu_kn else 1.5 * inp.ns_kn
    ns_n = inp.ns_kn * 1000.0
    nu_n = nu_kn * 1000.0
    a_m, b_m = inp.a_poteau_cm / 100.0, inp.b_poteau_cm / 100.0
    # aire semelle: d'abord centrée
    # si moments: dimensionner sur σmax côté sollicité (itération)
    B = max(a_m, b_m) + 0.6
    A = max(a_m, b_m) + 0.6
    for _ in range(200):
        area = A * B
        sig_max = ns_n / area
        sig_min = ns_n / area
        if inp.Mx_knm or inp.My_knm:
            sig_max = ns_n / area + 6 * inp.Mx_knm * 1000 / (A * B**2) + 6 * inp.My_knm * 1000 / (B * A**2)
            sig_min = ns_n / area - 6 * inp.Mx_knm * 1000 / (A * B**2) - 6 * inp.My_knm * 1000 / (B * A**2)
        if sig_max <= sigma_sol_pa and sig_min >= 0:
            break
        # augmenter
        grow = 1.05
        if sig_max > sigma_sol_pa:
            A *= grow
            B *= grow
        if sig_min < 0:
            A *= grow
            B *= grow
    h_min = max(0.30, (max(A, B) - max(a_m, b_m)) / 4.0)
    h_m = h_min
    # poinçonnement : augmenter H par pas de 5 cm si non vérifié (pratique BET usuelle)
    nu_poinc = 0.0
    ok_poinc = False
    while h_m <= 1.5:
        uc_try = 2 * (a_m + b_m + 2 * h_m)
        nu_poinc = 0.045 * uc_try * h_m * inp.fc28_mpa * 1e6 / GAMMA_B / 1000.0
        ok_poinc = nu_n <= nu_poinc * 1000.0
        if ok_poinc:
            break
        h_m += 0.05
    d_m = h_m - (inp.cover_mm + 10) / 1000.0
    h_augmentee = h_m > h_min
    # armatures (bielles)
    as_x = nu_n * (A - a_m) / (8 * d_m * sigma_s_elu(inp.fe_mpa) * 1e6) * 1e4
    as_y = nu_n * (B - b_m) / (8 * d_m * sigma_s_elu(inp.fe_mpa) * 1e6) * 1e4
    as_nf_x = non_fragilite(B * 100, d_m, inp.fc28_mpa, inp.fe_mpa)
    as_nf_y = non_fragilite(A * 100, d_m, inp.fc28_mpa, inp.fe_mpa)
    as_x = max(as_x, as_nf_x)
    as_y = max(as_y, as_nf_y)
    choix_x = choisir_barres(as_x, d_max_mm=25, n_max=20)
    choix_y = choisir_barres(as_y, d_max_mm=25, n_max=20)
    # poinçonnement
    uc = 2 * (a_m + b_m + 2 * h_m)
    nu_poinc = 0.045 * uc * h_m * inp.fc28_mpa * 1e6 / GAMMA_B / 1000.0
    sig_max_pa = ns_n / (A * B) + 6 * inp.Mx_knm * 1000 / (A * B**2) + 6 * inp.My_knm * 1000 / (B * A**2) if (inp.Mx_knm or inp.My_knm) else ns_n / (A * B)
    sig_min_pa = ns_n / (A * B) - 6 * inp.Mx_knm * 1000 / (A * B**2) - 6 * inp.My_knm * 1000 / (B * A**2) if (inp.Mx_knm or inp.My_knm) else ns_n / (A * B)
    from common import audit_ligne
    res = {
        "type": unite,
        "A_m": round(A, 2), "B_m": round(B, 2), "H_m": round(h_m, 3), "d_m": round(d_m, 3),
        "poids_T": round(A * B * h_m * 2.5, 2),
        "sigma_sol_bar": inp.sigma_sol_bar,
        "sigma_max_bar": round(sig_max_pa / 1e5, 3), "sigma_min_bar": round(sig_min_pa / 1e5, 3),
        "asx_cm2": round(as_x, 2), "asy_cm2": round(as_y, 2),
        "acier_x": choix_x["choix"], "acier_y": choix_y["choix"],
        "choix_x": choix_x, "choix_y": choix_y,
        "nu_kn_utilise": round(nu_kn, 1),
        "poinconnement": {"uc_m": round(uc, 3), "nu_poinc_kn": round(nu_poinc, 1),
                          "ok": bool(nu_n <= nu_poinc * 1000.0),
                          "nu_utilise_kn": round(nu_kn, 1)},
        "semelle_rigide": h_m >= (max(A, B) - max(a_m, b_m)) / 4.0,
        "h_augmentee_pour_poinconnement": bool(h_augmentee),
        "non_fragilite_x_cm2": round(as_nf_x, 2), "non_fragilite_y_cm2": round(as_nf_y, 2),
        "avertissements": [],
    }
    if h_augmentee:
        res["avertissements"].append(f"H augmentée de {h_min:.2f} m à {h_m:.2f} m pour satisfaire le poinçonnement.")
    if sig_min_pa < 0:
        res["avertissements"].append("Contrainte de service en traction sous la semelle : risque de soulèvement — justification spéciale requise.")
    if not res["poinconnement"]["ok"]:
        res["avertissements"].append("Poinçonnement non vérifié : augmenter H ou fc28.")
    res["audit"] = [
        audit_ligne("σ = N/(A B)", ns_n / (A * B) / 1e5, res["sigma_max_bar"] if not (inp.Mx_knm or inp.My_knm) else res["sigma_max_bar"], 0.05),
        audit_ligne("As = Nu (A-a)/(8 d σs)", nu_n * (A - a_m) / (8 * d_m * sigma_s_elu(inp.fe_mpa) * 1e6) * 1e4, as_x, 0.05),
        audit_ligne("Q × P = T (poids semelle)", A * B * h_m * 2.5, res["poids_T"], 0.05),
    ]
    return res

@app.post("/semelle")
def semelle(inp: SemelleInput):
    return _dimensionner_semelle(inp, "semelle isolée")

@app.post("/semelle_filante")
def semelle_filante(inp: SemelleFilanteInput):
    res = _dimensionner_semelle(inp, "semelle filante")
    # restitution par mètre linéaire
    d_m = res["d_m"]
    a_m = inp.a_poteau_cm / 100.0
    nu_n = (inp.nu_kn if inp.nu_kn else 1.5 * inp.ns_kn) * 1000.0
    A = res["A_m"]
    as_par_m = nu_n * (A - a_m) / (8 * d_m * sigma_s_elu(inp.fe_mpa) * 1e6) * 1e4
    res["as_cm2_par_ml"] = round(as_par_m, 2)
    res["as_min_cm2_par_ml"] = round(max(3.3 * d_m, 1.6), 2)
    res["remarque"] = "Semelle filante : armatures inférieures par mètre linéaire, nappe continue ; chaînage longitudinal sur toute la longueur. (As,min ≥ 3,3 cm²/m usuel BET — à confirmer.)"
    return res

@app.post("/voile")
def voile(inp: VoileInput):
    ep_m = inp.ep_cm / 100.0
    L = inp.longueur_m
    area = ep_m * L
    n_n = inp.n_kn * 1000.0
    m_nm = inp.m_knm * 1000.0
    sigma_c = n_n / area / 1e6
    sigma_b = 6 * m_nm / (ep_m * L**2) / 1e6 if L else 0.0
    sig_max, sig_min = sigma_c + sigma_b, sigma_c - sigma_b
    sbc = sigma_bc_elu(inp.fc28_mpa)
    # vérifier compression extrême
    pleine_compression = sig_min >= 0
    if pleine_compression:
        # armatures minimales (pratique BET courante pour voiles — à confirmer)
        as_vert_min = max(0.002 * area * 1e4, 4.0 * L)
        as_horiz_min = max(0.002 * area * 1e4, 4.0 * L)
        as_boundary = 0.0
        mode = "section entièrement comprimée"
    else:
        # zone tendue : armature de rive (semelle de rive)
        L_t = L * (-sig_min) / (sig_max - sig_min) if (sig_max - sig_min) != 0 else 0.0
        Ft = 0.5 * abs(sig_min) * 1e6 * L_t * ep_m  # N
        as_boundary = Ft / (sigma_s_elu(inp.fe_mpa) * 1e6) * 1e4
        as_vert_min = max(0.002 * area * 1e4, 4.0 * L)
        as_horiz_min = max(0.002 * area * 1e4, 4.0 * L)
        mode = "section partiellement comprimée — aciers de rive dimensionnés"
    taux_c = sig_max / (0.6 * inp.fc28_mpa)
    tau_u = (inp.v_kn * 1000.0) / area / 1e6 if area else 0.0
    tau_lim = 0.15 * inp.fc28_mpa / GAMMA_B
    att = []
    if not pleine_compression and taux_c >= 1:
        att.append("Contrainte de compression extrême ≥ 0,6 fc28 : augmenter l'épaisseur ou fc28.")
    if tau_u > tau_lim:
        att.append(f"τu = {tau_u:.2f} MPa > {tau_lim:.2f} MPa : armatures transversales d'âme renforcées requises.")
    att.append("Voile : vérifier aussi effort tranchant RPS (art. 7.2.2.2 — ω) et dispositions ND2/ND3 (zones critiques, art. 7.3.1).")
    from common import audit_ligne, choisir_barres
    choix_rive = choisir_barres(max(as_boundary, as_vert_min / max(L, 1) * 1.0), d_max_mm=32)
    choix_hmin = choisir_barres(as_horiz_min / L, d_max_mm=16)
    res = {
        "mode": mode,
        "longueur_m": L, "ep_cm": inp.ep_cm, "n_kn": inp.n_kn, "m_knm": inp.m_knm, "v_kn": inp.v_kn,
        "sigma_max_mpa": round(sig_max, 2), "sigma_min_mpa": round(sig_min, 2),
        "sigma_sol_admissible_mpa": 0.6 * inp.fc28_mpa,
        "compression_ok": bool(sig_max <= 0.6 * inp.fc28_mpa),
        "tau_u_mpa": round(tau_u, 3), "tau_u_lim_mpa": round(tau_lim, 2), "tau_ok": bool(tau_u <= tau_lim),
        "as_rive_cm2": round(as_boundary, 2),
        "as_vert_min_total_cm2": round(as_vert_min, 2), "as_horiz_min_total_cm2": round(as_horiz_min, 2),
        "as_vert_par_m_cm2": round(as_vert_min / L, 2), "as_horiz_par_m_cm2": round(as_horiz_min / L, 2),
        "rive": choix_rive, "horiz": choix_hmin,
        "attention": att,
        "audit": [audit_ligne("σ = N/(e.L)", n_n / area / 1e6, sigma_c, 0.01),
                  audit_ligne("σ_extr = N/(e.L)+6M/(e.L²)", sig_max, sig_max, 0.01)],
    }
    return res

@app.post("/sismique")
def sismique(inp: SismiqueInput):
    nu_vitesse = RPS["vitesse_zones"][str(inp.zone_vitesse)]
    S = RPS["site_coefficients"].get(inp.site)
    if S is None:
        S = 1.8
    I = RPS["importance_I"][inp.classe]
    K = RPS["K"][inp.systeme][inp.ductilite]
    psi = RPS["psi"][inp.usage]
    W = inp.w_kn if inp.w_kn else (inp.g_kn or 0) + psi * (inp.q_kn or 0)
    if not W or W <= 0:
        raise HTTPException(400, "W (ou G et Q) requis")
    # période
    if inp.periode_methode == "portique":
        T = 0.075 * inp.hauteur_m ** 0.75
    elif inp.periode_methode == "acier_noeuds_rigides":
        T = 0.085 * inp.hauteur_m ** 0.75
    elif inp.periode_methode == "autre":
        T = 0.09 * inp.hauteur_m / math.sqrt(inp.longueur_contreventement_m)
    else:
        T = inp.t_manuel_s or 0.09 * inp.hauteur_m / math.sqrt(inp.longueur_contreventement_m)
    if inp.amortissement_pct != 5.0:
        m = (5.0 / inp.amortissement_pct) ** 0.4
    else:
        m = 1.0
    # D selon rapport Za/Zv
    if T <= 0.25:
        D = {"za_gt_zv": 3.5, "za_eq_zv": 2.5, "za_lt_zv": 1.9}[inp.rapport_za_zv]
    elif T < 0.50:
        if inp.rapport_za_zv == "za_gt_zv":
            D = -6.4 * T + 5.1
        elif inp.rapport_za_zv == "za_eq_zv":
            D = -2.4 * T + 3.1
        else:
            D = 1.9
    else:
        D = 1.20 / (T ** (2.0 / 3.0))
    D *= m
    F = nu_vitesse * S * D * I * W / K
    Ft = 0.0 if T <= 0.7 else 0.07 * T * F
    Fn = []
    if inp.niveaux:
        denom = sum(n.w_kn * n.h_m for n in inp.niveaux)
        for n in inp.niveaux:
            Fn.append({"niveau": n.nom, "Fn_kn": round((F - Ft) * n.w_kn * n.h_m / denom, 1),
                       "Wn_kn": n.w_kn, "hn_m": n.h_m})
    omega = None
    if inp.periode_methode == "portique":
        omega = min(1.8, max(1.3, 0.6 * T + 0.85))
    regles_ok = inp.hauteur_m <= 60 and T <= 2.0
    return {
        "methode": "statique équivalente (RPS 2000 v2011, art. 6.2.1)",
        "nu_m_s": nu_vitesse, "S": S, "I": I, "K": K, "psi": psi, "W_kn": round(W, 1),
        "T_s": round(T, 3), "D": round(D, 3), "m_amortissement": m,
        "F_base_kn": round(F, 1), "Ft_kn": round(Ft, 1), "Fn": Fn,
        "omega_modes_superieurs": round(omega, 3) if omega else None,
        "acceleration_zone_note": "Za (Figure 5.3, % g — carte) : renseignez « rapport Za/Zv » en comparant la zone d'accélération et de vitesse du site du projet.",
        "hypotheses": [
            f"T ≤ 2 s et H ≤ 60 m : {'OK' if regles_ok else 'NON RESPECTÉ — justifier par approche dynamique'}",
            "Approche statique équivalente applicable si bâtiment régulier (art. 3.2/4.3).",
            "Si analyse modale faite : V_modal ≥ 0,90 × V_SE (art. 6.4.1).",
        ],
        "sources": [
            "RPS 2000 v2011 — eq. 6.1 (F = υ·S·D·I·W/K), eq. 6.2 (W = G + ψQ)",
            "Tableau 5.1 (υ), Tableau 5.2 (S), Tableau 5.3/Fig.5.4 (D), Tableau 3.1 (I), Tableau 3.3 (K), Tableau 6.1 (ψ)",
        ],
    }

@app.get("/bars")
def bars():
    return {"diametres_mm": [8, 10, 12, 14, 16, 20, 25, 32], "sections_cm2": {d: round(section_bar(d), 2) for d in [8, 10, 12, 14, 16, 20, 25, 32]}}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8002)
