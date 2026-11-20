"""Planchers à corps creux (hourdis + poutrelles + dalle de compression) — BAEL 91 rév. 99.

La poutrelle est une poutre continue en T : nervure b0, table de compression h0 (dalle de
compression), largeur de table b limitée par A.4.1,3. Elle porte une bande de largeur égale à
l'entraxe des poutrelles.

Moments :
  - méthode forfaitaire (B.6.2,21) si ses conditions sont remplies ;
  - sinon méthode de Caquot (B.6.2,22), minorée (G' = 2G/3 aux appuis) si Q ≤ max(2G ; 5 kN/m²).
Section en travée : en T (table comprimée) ; sur appui : rectangle b0 × h (table tendue).
Dalle de compression : treillis soudé, B.6.8,423. Flèche : conditions de B.6.8,424.

Unités : portées en m, épaisseurs et largeurs en cm, charges surfaciques en kN/m², linéiques en
kN/m, moments en kN·m, efforts en kN, aciers en cm² (par poutrelle) ou cm²/m (treillis).
Aucune charge n'est inventée : le poids propre du plancher (hourdis + poutrelles + dalle de
compression) est une entrée, à prendre dans la documentation du fabricant.
"""
from __future__ import annotations

import math
from typing import List, Optional

from pydantic import BaseModel, Field

GAMMA_B, GAMMA_S = 1.5, 1.15
N_EQ = 15          # coefficient d'équivalence acier / béton (A.4.5,1)


def _e():
    import engine_service as e      # import tardif : engine_service importe ce module à la fin
    return e


def _ref() -> dict:
    return _e().BAEL["planchers_corps_creux"]


def section_bar(d_mm: float) -> float:
    return math.pi * (d_mm / 10.0) ** 2 / 4.0


class PlancherInput(BaseModel):
    travees_m: List[float] = Field(..., min_length=1, max_length=12,
                                   description="portées des poutrelles entre nus d'appuis, de gauche à droite (m)")
    hourdis_cm: float = Field(..., ge=8, le=35, description="hauteur du corps creux (cm), ex. 16 pour un plancher 16+4")
    dalle_compression_cm: float = Field(..., ge=3, le=10, description="épaisseur de la dalle de compression h0 (cm)")
    b0_cm: float = Field(..., ge=6, le=30, description="largeur de la nervure de la poutrelle (cm)")
    entraxe_cm: float = Field(..., ge=30, le=120, description="entraxe des poutrelles (cm)")
    g_plancher_kn_m2: float = Field(..., gt=0, description="poids propre du plancher : hourdis + poutrelles + dalle de compression (kN/m²)")
    g_sup_kn_m2: float = Field(..., ge=0, description="revêtement, enduit, cloisons (kN/m²)")
    q_kn_m2: float = Field(..., ge=0, description="charge d'exploitation (kN/m²)")
    fc28_mpa: float = Field(25.0, ge=12, le=60)
    fe_mpa: float = Field(500.0, ge=215, le=600, description="aciers longitudinaux des poutrelles")
    fe_etriers_mpa: float = Field(235.0, ge=215, le=600, description="étriers (rond lisse FeE235 ou HA)")
    fe_treillis_mpa: float = Field(500.0, ge=215, le=600, description="treillis soudé de la dalle de compression")
    etrier_mm: float = Field(6.0, ge=5, le=10)
    enrobage_mm: float = Field(20.0, ge=10, le=50)
    poutrelle: str = Field("coulee_en_place", description="coulee_en_place | prefabriquee (reprise de bétonnage : k = 0)")
    fissuration: str = "peu_prejudiciable"


# ───────────────────────── moments et efforts tranchants ─────────────────────────

def conditions_forfaitaire(travees: List[float], g: float, q: float, fissuration: str) -> List[dict]:
    """B.6.2,210 : domaine de validité de la méthode forfaitaire."""
    rapports = [travees[i] / travees[i + 1] for i in range(len(travees) - 1)]
    ok_portees = all(0.8 <= r <= 1.25 for r in rapports)
    return [
        {"nom": "Q ≤ max(2 G ; 5 kN/m²)", "ok": bool(q <= max(2 * g, 5.0)),
         "detail": f"Q = {q:g} ; max(2G ; 5) = {max(2 * g, 5.0):g}"},
        {"nom": "même inertie dans toutes les travées", "ok": True, "detail": "section de poutrelle constante"},
        {"nom": "0,8 ≤ li / li+1 ≤ 1,25", "ok": bool(ok_portees),
         "detail": ", ".join(f"{r:.2f}" for r in rapports) if rapports else "une seule travée"},
        {"nom": "fissuration peu préjudiciable", "ok": fissuration == "peu_prejudiciable", "detail": fissuration},
    ]


def moments_forfaitaire(travees: List[float], pu: float, alpha: float) -> dict:
    """B.6.2,21 : moments sur appuis (valeurs absolues) et en travée, efforts tranchants."""
    n = len(travees)
    m0 = [pu * l ** 2 / 8.0 for l in travees]
    coef = [0.0] * (n + 1)                       # appuis de rive : 0 pour le calcul des travées
    if n == 2:
        coef[1] = 0.6
    elif n > 2:
        for i in range(1, n):
            coef[i] = 0.5 if i in (1, n - 1) else 0.4
    ma = [coef[i] * max(m0[i - 1] if i >= 1 else 0, m0[i] if i < n else 0) for i in range(n + 1)]
    mt = []
    for i in range(n):
        rive = n == 1 or i in (0, n - 1)
        mw, me = ma[i], ma[i + 1]
        a = max(1.0 + 0.3 * alpha, 1.05) * m0[i] - (mw + me) / 2.0
        b = ((1.2 if rive else 1.0) + 0.3 * alpha) * m0[i] / 2.0
        mt.append(m0[i] if n == 1 else max(a, b))
    v = []
    for i, l in enumerate(travees):
        v0 = pu * l / 2.0
        kw = ke = 1.0
        if n == 2:
            kw, ke = (1.0, 1.15) if i == 0 else (1.15, 1.0)
        elif n > 2:
            if i == 0:
                ke = 1.10
            if i == n - 1:
                kw = 1.10
            if i == 1:
                kw = 1.10
            if i == n - 2:
                ke = 1.10
        v.append((kw * v0, ke * v0))
    return {"m0": m0, "appuis": ma, "coef_appuis": coef, "travees": mt, "v": v}


def moments_caquot(travees: List[float], g_l: float, q_l: float, minoree: bool) -> dict:
    """B.6.2,22 : méthode de Caquot (charges réparties). Portées fictives l' = l (rive), 0,8 l (intermédiaire).
    Ma = (pw l'w³ + pe l'e³) / (8,5 (l'w + l'e)). Minorée : G' = 2G/3 pour les moments sur appuis."""
    n = len(travees)
    lp = [l if (i in (0, n - 1)) else 0.8 * l for i, l in enumerate(travees)]
    gp = (2.0 / 3.0) * g_l if minoree else g_l
    charge = 1.35 * gp + 1.5 * q_l
    decharge = 1.35 * gp
    pu_plein = 1.35 * g_l + 1.5 * q_l

    def m_appui(i: int, pw: float, pe: float) -> float:
        if i == 0 or i == n:
            return 0.0
        return (pw * lp[i - 1] ** 3 + pe * lp[i] ** 3) / (8.5 * (lp[i - 1] + lp[i]))

    ma = [m_appui(i, charge, charge) for i in range(n + 1)]          # toutes travées chargées
    mt, v = [], []
    for i, l in enumerate(travees):
        # travée i chargée, voisines déchargées : moment maximal en travée
        mw = m_appui(i, decharge, charge)
        me = m_appui(i + 1, charge, decharge)
        x0 = min(max(l / 2.0 + (mw - me) / (pu_plein * l), 0.0), l)
        mt.append(pu_plein * x0 * (l - x0) / 2.0 - mw * (1 - x0 / l) - me * x0 / l)
        # efforts tranchants : toutes travées chargées
        v.append((pu_plein * l / 2.0 + (ma[i] - ma[i + 1]) / l, pu_plein * l / 2.0 + (ma[i + 1] - ma[i]) / l))
    return {"m0": [pu_plein * l ** 2 / 8.0 for l in travees], "appuis": ma, "travees": mt, "v": v}


# ───────────────────────── sections ─────────────────────────

def largeur_table_cm(b0_cm: float, entraxe_cm: float, portee_m: float) -> float:
    """A.4.1,3 : débord de table b1 ≤ min(l0 / 2 ; l / 10), l0 = distance entre nus des nervures."""
    b1 = min((entraxe_cm - b0_cm) / 2.0, portee_m * 100.0 / 10.0)
    return b0_cm + 2.0 * b1


def caracteristiques_T(b: float, b0: float, h: float, h0: float) -> dict:
    """Section brute en T (cm) : aire, position du centre de gravité depuis la fibre supérieure (v), inertie."""
    a1, a2 = b * h0, b0 * (h - h0)
    v = (a1 * h0 / 2.0 + a2 * (h0 + (h - h0) / 2.0)) / (a1 + a2)
    i = b * h0 ** 3 / 12.0 + a1 * (v - h0 / 2.0) ** 2 + b0 * (h - h0) ** 3 / 12.0 + a2 * (h0 + (h - h0) / 2.0 - v) ** 2
    return {"aire_cm2": a1 + a2, "v_cm": v, "v_prime_cm": h - v, "inertie_cm4": i}


def non_fragilite_T(car: dict, h_cm: float, fc28: float, fe: float, tendue_en_bas: bool) -> float:
    """A.4.2,1 (section en T) : A ≥ I ft28 / (0,81 h v fe), v = distance du centre de gravité à la fibre tendue."""
    v = car["v_prime_cm"] if tendue_en_bas else car["v_cm"]
    return car["inertie_cm4"] * _e().ft28(fc28) / (0.81 * h_cm * v * fe)


def flexion_T_elu(mu_knm: float, b: float, b0: float, h0: float, d_m: float, fc28: float, fe: float) -> dict:
    """Section en T à l'ELU : la table seule équilibre-t-elle Mu ? sinon nervure + débords."""
    e = _e()
    fbu = e.sigma_bc_elu(fc28)
    fsu = e.sigma_s_elu(fe)
    h0m = h0 / 100.0
    mtu = b / 100.0 * h0m * fbu * 1e3 * (d_m - h0m / 2.0)          # kN·m
    if mu_knm <= mtu:
        r = e.flexion_simple_elu(b, 0, d_m, fc28, fe, mu_knm)
        return {"cas": "table seule comprimée (section rectangulaire b × h)", "mtu_knm": round(mtu, 2), **r}
    m_deb = (b - b0) / 100.0 * h0m * fbu * 1e3 * (d_m - h0m / 2.0)
    a_deb = m_deb / ((d_m - h0m / 2.0) * fsu * 1e3) * 1e4
    r = e.flexion_simple_elu(b0, 0, d_m, fc28, fe, mu_knm - m_deb)
    r["as_cm2"] = round(r["as_cm2"] + a_deb, 2)
    return {"cas": "axe neutre dans la nervure (section en T)", "mtu_knm": round(mtu, 2), **r}


def els_T(ms_knm: float, b: float, b0: float, h0: float, d_m: float, as_cm2: float, fc28: float, fe: float,
          fissuration: str) -> dict:
    """ELS d'une section en T (n = 15) : axe neutre, inertie fissurée, σbc et σst."""
    bb, bb0, hh0, d, a = b / 100.0, b0 / 100.0, h0 / 100.0, d_m, as_cm2 / 1e4
    # axe neutre dans la table ?
    if bb * hh0 ** 2 / 2.0 - N_EQ * a * (d - hh0) >= 0:
        y = (-N_EQ * a + math.sqrt((N_EQ * a) ** 2 + 2 * bb * N_EQ * a * d)) / bb
        inertie = bb * y ** 3 / 3.0 + N_EQ * a * (d - y) ** 2
    else:   # b0 y²/2 + (b − b0) h0 (y − h0/2) − n A (d − y) = 0
        aa = bb0 / 2.0
        bq = (bb - bb0) * hh0 + N_EQ * a
        cq = -(bb - bb0) * hh0 ** 2 / 2.0 - N_EQ * a * d
        y = (-bq + math.sqrt(bq ** 2 - 4 * aa * cq)) / (2 * aa)
        inertie = bb * y ** 3 / 3.0 - (bb - bb0) * (y - hh0) ** 3 / 3.0 + N_EQ * a * (d - y) ** 2
    k = ms_knm * 1e3 / inertie
    sbc = k * y / 1e6
    sst = N_EQ * k * (d - y) / 1e6
    lim_st = _e().flex_els(100.0, d, 1.0, fc28, fe, 0.0, fissuration)["sigma_st_lim_mpa"]
    return {"axe_neutre_y_m": round(y, 4), "sigma_bc_mpa": round(sbc, 2), "sigma_bc_lim_mpa": round(0.6 * fc28, 2),
            "sigma_bc_ok": bool(sbc <= 0.6 * fc28), "sigma_st_mpa": round(sst, 1), "sigma_st_lim_mpa": lim_st,
            "sigma_st_ok": bool(fissuration == "peu_prejudiciable" or sst <= lim_st)}


def choisir_barres(as_req: float, b0_cm: float, enrobage_mm: float, etrier_mm: float, n_min: int = 1) -> dict:
    """Barres d'une poutrelle : n_min à 3 HA de Ø 8 à 16 sur un lit, espacement libre ≥ max(Ø ; 25 mm) (A.7.2).
    En travée, n_min = 2 : les étriers s'accrochent à deux barres d'angle."""
    largeur = b0_cm * 10.0 - 2.0 * (enrobage_mm + etrier_mm)
    meilleur = None
    for d in (8, 10, 12, 14, 16):
        for n in range(n_min, 4):
            if n * d + (n - 1) * max(d, 25) > largeur:
                continue
            fournie = n * section_bar(d)
            if fournie + 1e-9 < as_req:
                continue
            cle = (round(fournie, 3), n, d)
            if meilleur is None or cle < meilleur[0]:
                meilleur = (cle, {"n": n, "diametre_mm": d, "as_fournie_cm2": round(fournie, 2)})
    if meilleur is None:
        return {"n": None, "diametre_mm": None, "as_fournie_cm2": None, "choix": "à revoir", "inconstructible": True}
    c = meilleur[1]
    c["choix"] = f"{c['n']} HA{c['diametre_mm']}"
    return c


def fleche_calculee(l_m: float, m_j: float, m_g: float, m_p: float, b: float, b0: float, h: float, h0: float,
                    d_m: float, as_cm2: float, fc28: float) -> dict:
    """B.6.5,2 : flèche totale Δft = fgv − fji + fpi − fgi, comparée à l/500 (l ≤ 5 m) ou 0,5 cm + l/1000.
    Moments de service en kN·m : j (poids propre du plancher seul, à la pose des cloisons), g (G total), p (G + Q).
    Inerties fissurées Ifi = 1,1 I0 / (1 + λi μ), Ifv = 1,1 I0 / (1 + λv μ) ; Ei = 11 000 fc28^(1/3), Ev = Ei / 3."""
    e = _e()
    ft = e.ft28(fc28)
    bb, bb0, hh, hh0, a = b / 100.0, b0 / 100.0, h / 100.0, h0 / 100.0, as_cm2 / 1e4
    # inertie de la section totale homogénéisée (béton non fissuré + n A)
    s_t, s_n, s_a = bb * hh0, bb0 * (hh - hh0), N_EQ * a
    v = (s_t * hh0 / 2 + s_n * (hh0 + (hh - hh0) / 2) + s_a * d_m) / (s_t + s_n + s_a)
    i0 = (bb * hh0 ** 3 / 12 + s_t * (v - hh0 / 2) ** 2 + bb0 * (hh - hh0) ** 3 / 12
          + s_n * (hh0 + (hh - hh0) / 2 - v) ** 2 + s_a * (d_m - v) ** 2)
    rho = a / (bb0 * d_m)
    lam_i = 0.05 * ft / (rho * (2 + 3 * bb0 / bb))
    lam_v = 0.4 * lam_i
    ei = 11000.0 * fc28 ** (1 / 3) * 1e6
    ev = ei / 3.0

    def etat(m):
        sst = els_T(m, b, b0, h0, d_m, as_cm2, fc28, 500.0, "peu_prejudiciable")["sigma_st_mpa"]
        mu = max(0.0, 1.0 - 1.75 * ft / (4 * rho * sst + ft)) if sst > 0 else 0.0
        return sst, mu

    def f(m, module, inertie):
        return m * 1e3 * l_m ** 2 / (10.0 * module * inertie)

    sj, mj = etat(m_j)
    sg, mg = etat(m_g)
    sp, mp = etat(m_p)
    fji = f(m_j, ei, 1.1 * i0 / (1 + lam_i * mj))
    fgi = f(m_g, ei, 1.1 * i0 / (1 + lam_i * mg))
    fgv = f(m_g, ev, 1.1 * i0 / (1 + lam_v * mg))
    fpi = f(m_p, ei, 1.1 * i0 / (1 + lam_i * mp))
    dft = fgv - fji + fpi - fgi
    fadm = l_m / 500.0 if l_m <= 5.0 else 0.005 + l_m / 1000.0
    mm = lambda x: round(x * 1000.0, 2)
    return {"i0_cm4": round(i0 * 1e8, 0), "rho": round(rho, 5), "lambda_i": round(lam_i, 3), "lambda_v": round(lam_v, 3),
            "sigma_s_mpa": {"j": round(sj, 1), "g": round(sg, 1), "p": round(sp, 1)},
            "mu": {"j": round(mj, 3), "g": round(mg, 3), "p": round(mp, 3)},
            "fji_mm": mm(fji), "fgi_mm": mm(fgi), "fgv_mm": mm(fgv), "fpi_mm": mm(fpi),
            "delta_ft_mm": mm(dft), "f_adm_mm": mm(fadm), "ok": bool(dft <= fadm)}


def treillis_dalle_compression(entraxe_cm: float, fe_ts: float) -> dict:
    """B.6.8,423 : A⊥ ≥ 4 L / fe si 50 ≤ L ≤ 80 cm, A⊥ ≥ 200 / fe si L ≤ 50 cm (cm²/m) ; A// ≥ A⊥ / 2 ;
    mailles ≤ 20 cm (⊥ aux nervures) et ≤ 33 cm (// aux nervures)."""
    ref = _ref()["dalle_compression"]
    if entraxe_cm <= 50:
        a_perp = 200.0 / fe_ts
    else:
        a_perp = 4.0 * entraxe_cm / fe_ts
    a_par = a_perp / 2.0
    choix = None
    for d in (5, 6, 7, 8):          # diamètres courants de treillis : à adapter au catalogue du fournisseur
        for e in (20, 15, 10):
            if e > ref["maille_perp_max_cm"]:
                continue
            a = section_bar(d) * 100.0 / e
            if a + 1e-9 >= a_perp:
                choix = {"diametre_mm": d, "maille_cm": e, "as_fournie_cm2_m": round(a, 2)}
                break
        if choix:
            break
    out = {"a_perp_cm2_m": round(a_perp, 2), "a_par_cm2_m": round(a_par, 2), "hors_domaine": entraxe_cm > 80}
    if choix:
        out.update(choix)
        out["choix"] = f"TS Ø{choix['diametre_mm']} maille {choix['maille_cm']} × {choix['maille_cm']} cm"
    else:
        out["choix"] = "à revoir"
    return out


# ───────────────────────── calcul complet ─────────────────────────

def plancher(inp: PlancherInput) -> dict:
    from dalles import FISSURATIONS
    if inp.fissuration not in FISSURATIONS:
        raise ValueError(f"fissuration inconnue : {inp.fissuration}")
    if inp.poutrelle not in ("coulee_en_place", "prefabriquee"):
        raise ValueError(f"poutrelle inconnue : {inp.poutrelle} (coulee_en_place | prefabriquee)")
    if any(not (0.5 <= l <= 9.0) for l in inp.travees_m):
        raise ValueError("chaque portée doit être comprise entre 0,5 et 9 m")
    if inp.b0_cm >= inp.entraxe_cm:
        raise ValueError("la nervure b0 doit être plus étroite que l'entraxe des poutrelles")
    e = _e()
    ref = _ref()
    trav = list(inp.travees_m)
    n = len(trav)
    h0, b0, ent = inp.dalle_compression_cm, inp.b0_cm, inp.entraxe_cm
    h = inp.hourdis_cm + h0
    g = inp.g_plancher_kn_m2 + inp.g_sup_kn_m2
    q = inp.q_kn_m2
    g_l, q_l = g * ent / 100.0, q * ent / 100.0
    pu, ps = 1.35 * g_l + 1.5 * q_l, g_l + q_l
    r_els = ps / pu                                                   # moments ELS proportionnels
    alpha = q / (g + q) if g + q > 0 else 0.0

    conds = conditions_forfaitaire(trav, g, q, inp.fissuration)
    if n == 1:
        methode = "isostatique"
        mom = {"m0": [pu * trav[0] ** 2 / 8.0], "appuis": [0.0, 0.0], "travees": [pu * trav[0] ** 2 / 8.0],
               "v": [(pu * trav[0] / 2.0,) * 2]}
    elif all(c["ok"] for c in conds):
        methode = "forfaitaire"
        mom = moments_forfaitaire(trav, pu, alpha)
    else:
        minoree = conds[0]["ok"]
        methode = "Caquot minorée" if minoree else "Caquot"
        mom = moments_caquot(trav, g_l, q_l, minoree)

    phi_l = 12.0                                                      # Ø longitudinal estimé pour d
    d = h / 100.0 - (inp.enrobage_mm + inp.etrier_mm + phi_l / 2.0) / 1000.0
    k_reprise = 0.0 if inp.poutrelle == "prefabriquee" else 1.0
    ft = e.ft28(inp.fc28_mpa)
    fe = inp.fe_mpa
    if inp.fissuration == "peu_prejudiciable":
        tau_lim = min(0.2 * inp.fc28_mpa / GAMMA_B, 5.0)
    else:
        tau_lim = min(0.15 * inp.fc28_mpa / GAMMA_B, 4.0)
    remarques: List[str] = []
    observations: List[str] = []

    travees = []
    for i, l in enumerate(trav):
        b = largeur_table_cm(b0, ent, l)
        car = caracteristiques_T(b, b0, h, h0)
        mu_t = mom["travees"][i]
        elu = flexion_T_elu(mu_t, b, b0, h0, d, inp.fc28_mpa, fe)
        a_min = non_fragilite_T(car, h, inp.fc28_mpa, fe, tendue_en_bas=True)
        a_req = max(elu["as_cm2"], a_min)
        barres = choisir_barres(a_req, b0, inp.enrobage_mm, inp.etrier_mm, n_min=2)
        els = els_T(mu_t * r_els, b, b0, h0, d, barres["as_fournie_cm2"] or a_req, inp.fc28_mpa, fe, inp.fissuration)
        # effort tranchant et étriers (A.5.1)
        vu = max(mom["v"][i])
        tau = vu * 1e3 / (b0 / 100.0 * d * 1e6)
        at = 2.0 * section_bar(inp.etrier_mm)                          # un étrier = 2 brins
        fet = inp.fe_etriers_mpa
        st_max = min(0.9 * d * 100.0, 40.0)
        st_min_pct = at * fet / (0.4 * b0)                            # At fet / (b0 st) ≥ 0,4 MPa
        excedent = tau - 0.3 * ft * k_reprise
        st_calc = at * 0.9 * fet / GAMMA_S / (b0 * excedent) if excedent > 0 else float("inf")
        st = math.floor(min(st_max, st_min_pct, st_calc))
        # flèche : conditions de dispense des planchers à corps creux (B.6.8,424)
        cf = ref["fleche"]
        taux = (barres["as_fournie_cm2"] or a_req) / (b0 * d * 100.0)
        fleche = [
            {"nom": "h/l ≥ 1/22,5", "valeur": round(h / 100.0 / l, 4), "limite": round(1 / cf["h_sur_l_min_inverse"], 4)},
            {"nom": "h/l ≥ Mt/(15 M0)", "valeur": round(h / 100.0 / l, 4), "limite": round(mu_t / (15.0 * mom["m0"][i]), 4)},
            {"nom": "A/(b0 d) ≤ 3,6/fe", "valeur": round(taux, 5), "limite": round(cf["a_sur_b0d_max_x_fe"] / fe, 5)},
        ]
        for c in fleche[:2]:
            c["ok"] = bool(c["valeur"] >= c["limite"])
        fleche[2]["ok"] = bool(fleche[2]["valeur"] <= fleche[2]["limite"])
        nom = f"Travée {i + 1}"
        if barres.get("inconstructible"):
            remarques.append(f"{nom} : aucun lit de 1 à 3 HA ≤ 16 ne loge dans la nervure ; augmentez b0 ou la hauteur.")
        if elu["mode"] == "aciers comprimés":
            remarques.append(f"{nom} : μ > μlim ; augmentez la hauteur du plancher.")
        if not els["sigma_bc_ok"]:
            remarques.append(f"{nom} : σbc > 0,6 fc28 à l'ELS ; augmentez la hauteur.")
        if not els["sigma_st_ok"]:
            remarques.append(f"{nom} : σst > σst,lim à l'ELS ; augmentez la section d'acier.")
        if tau > tau_lim:
            remarques.append(f"{nom} : τu = {tau:.2f} MPa > {tau_lim:.2f} MPa ; augmentez b0 ou la hauteur.")
        dispense = all(c["ok"] for c in fleche)
        calcul_fleche = None
        if not dispense:    # pas de dispense : la flèche est calculée (B.6.5,2)
            k_m = mu_t / pu                                            # moment en travée par kN/m de charge
            calcul_fleche = fleche_calculee(l, k_m * inp.g_plancher_kn_m2 * ent / 100.0, k_m * g_l, k_m * (g_l + q_l),
                                            b, b0, h, h0, d, barres["as_fournie_cm2"] or a_req, inp.fc28_mpa)
            if not calcul_fleche["ok"]:
                remarques.append(f"{nom} : flèche Δft = {calcul_fleche['delta_ft_mm']:.1f} mm > f admissible "
                                 f"{calcul_fleche['f_adm_mm']:.1f} mm (B.6.5,2) ; augmentez la hauteur du plancher.")
        travees.append({
            "portee_m": l, "b_cm": round(b, 1), "m0_knm": round(mom["m0"][i], 2), "mt_knm": round(mu_t, 2),
            "ms_knm": round(mu_t * r_els, 2), "vu_kn": round(vu, 2),
            "elu": {"cas": elu["cas"], "mtu_knm": elu["mtu_knm"], "mu": elu["mu"], "mode": elu["mode"],
                    "as_elu_cm2": round(elu["as_cm2"], 2)},
            "as_min_cm2": round(a_min, 2), "as_retenue_cm2": round(a_req, 2),
            "gouverne": "minimum" if a_min > elu["as_cm2"] else "ELU", "ferraillage": barres, "els": els,
            "cisaillement": {"tau_u_mpa": round(tau, 3), "tau_lim_mpa": round(tau_lim, 2), "ok": bool(tau <= tau_lim)},
            "etriers": {"diametre_mm": inp.etrier_mm, "at_cm2": round(at, 2), "st_cm": st,
                        "st_max_cm": round(st_max, 1), "choix": f"étriers Ø{inp.etrier_mm:g} e={st}"},
            "fleche": {"article": "B.6.8,424", "conditions": fleche, "dispense": dispense, "calcul": calcul_fleche,
                       "ok": bool(dispense or calcul_fleche["ok"])},
        })

    # appuis : chapeaux dans la dalle de compression (table tendue, section b0 × h)
    appuis = []
    for i in range(n + 1):
        rive = i in (0, n)
        m_adj = max(mom["m0"][i - 1] if i >= 1 else 0.0, mom["m0"][i] if i < n else 0.0)
        if rive:      # appui de rive : moment forfaitaire de non-fragilité des chapeaux
            ma = ref["chapeau_rive_sur_m0"] * m_adj
        else:
            ma = mom["appuis"][i]
        car = caracteristiques_T(largeur_table_cm(b0, ent, min(trav[max(i - 1, 0)], trav[min(i, n - 1)])), b0, h, h0)
        r = e.flexion_simple_elu(b0, 0, d, inp.fc28_mpa, fe, ma)
        a_min = non_fragilite_T(car, h, inp.fc28_mpa, fe, tendue_en_bas=False)
        a_req = max(r["as_cm2"], a_min)
        barres = choisir_barres(a_req, ent, inp.enrobage_mm, 0.0)      # chapeaux logés dans la dalle de compression
        els = e.flex_els(b0, d, barres["as_fournie_cm2"] or a_req, inp.fc28_mpa, fe, ma * r_els, inp.fissuration)
        l_adj = max(trav[i - 1] if i >= 1 else 0.0, trav[i] if i < n else 0.0)
        voisin_rive = n >= 2 and i in (1, n - 1)
        frac = ref["longueur_chapeaux"]["voisin_rive" if (voisin_rive or rive) else "intermediaire"]
        nom = "Appui de rive" if rive else f"Appui {i}"
        if r["mode"] == "aciers comprimés":
            remarques.append(f"{nom} : μ > μlim sur appui ; augmentez la hauteur ou élargissez la nervure.")
        if els.get("sigma_bc_ok") is False:
            remarques.append(f"{nom} : σbc > 0,6 fc28 sur appui ; augmentez la hauteur.")
        if barres.get("inconstructible"):
            remarques.append(f"{nom} : chapeaux à revoir.")
        appuis.append({
            "appui": i, "rive": rive, "ma_knm": round(ma, 2), "mu": r["mu"], "mode": r["mode"],
            "as_elu_cm2": round(r["as_cm2"], 2), "as_min_cm2": round(a_min, 2), "as_retenue_cm2": round(a_req, 2),
            "ferraillage": barres, "els": els, "longueur_chapeau_m": round(frac * l_adj, 2),
        })

    ts = treillis_dalle_compression(ent, inp.fe_treillis_mpa)
    if ts["hors_domaine"]:
        remarques.append("Entraxe > 80 cm : hors du domaine de B.6.8,423 ; la dalle de compression doit être calculée.")
    phi_t_max = min(h * 10.0 / 35.0, b0 * 10.0 / 10.0)
    if inp.etrier_mm > phi_t_max + 1e-9:
        observations.append(f"Ø étriers {inp.etrier_mm:g} mm > min(h/35 ; b0/10) = {phi_t_max:.1f} mm (A.7.2,2).")
    if h0 < ref["h0_min_cm"]:
        remarques.append(f"Dalle de compression h0 = {h0:g} cm < {ref['h0_min_cm']:g} cm.")
    designation = f"{inp.hourdis_cm:g}+{h0:g}"
    return {
        "type": "plancher", "designation": designation, "h_cm": h, "h0_cm": h0, "b0_cm": b0, "entraxe_cm": ent,
        "travees_m": trav, "d_m": round(d, 3),
        "charges": {"g_plancher_kn_m2": inp.g_plancher_kn_m2, "g_kn_m2": round(g, 3), "q_kn_m2": q,
                    "g_kn_m": round(g_l, 3), "q_kn_m": round(q_l, 3), "pu_kn_m": round(pu, 3), "ps_kn_m": round(ps, 3)},
        "methode": methode, "conditions_forfaitaire": conds, "alpha": round(alpha, 3),
        "travees": travees, "appuis": appuis, "dalle_compression": ts,
        "predimensionnement": {"h_min_cm": round(max(trav) * 100.0 / ref["fleche"]["h_sur_l_min_inverse"], 1),
                               "ok": bool(h >= max(trav) * 100.0 / ref["fleche"]["h_sur_l_min_inverse"])},
        "verifie": not remarques, "remarques": remarques, "observations": observations,
        "hypotheses": [
            f"Poutrelle en T : nervure b0 = {b0:g} cm, table h0 = {h0:g} cm, entraxe {ent:g} cm (valeurs saisies).",
            "Poids propre du plancher saisi d'après la documentation du fabricant des hourdis.",
            "Moments ELS pris proportionnels aux moments ELU (ps / pu).",
            f"d estimé avec Ø longitudinal {phi_l:g} mm et étriers Ø{inp.etrier_mm:g}.",
            "Poutrelle " + ("préfabriquée : reprise de bétonnage, k = 0 dans le calcul des étriers."
                            if k_reprise == 0 else "coulée en place : k = 1 dans le calcul des étriers."),
        ],
    }
