"""Dalles pleines sur appuis continus et balcons en porte-à-faux — BAEL 91 rév. 99.

Unités : longueurs en m (épaisseurs en cm), charges surfaciques en kN/m², charges
linéiques en kN/m, moments en kN·m/m, sections d'acier en cm²/m (bande de 1 m).

Dalle (A.8.2, Annexe E3) :
  ρ = lx / ly (lx ≤ ly) ; ρ < 0,4 : portée dans le seul sens lx, M0 = p lx² / 8 ;
  sinon M0x = μx p lx², M0y = μy M0x, avec My ≥ Mx / 4 ;
  travée / appuis selon la continuité du panneau (A.8.2,32).
Balcon (console encastrée, bande de 1 m) :
  Mu = 1,35 (g l²/2 + P l) + 1,5 (q l²/2 + H hg) ; aciers principaux en nappe SUPÉRIEURE.

Toutes les constantes viennent de referentiels/bael.json (clés « dalles », « balcons »,
« ancrage », « charges ») ; aucune charge n'est inventée : g et q sont des entrées.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

FISSURATIONS = ("peu_prejudiciable", "prejudiciable", "tres_prejudiciable")
CONTINUITES = ("isostatique", "rive", "intermediaire")


def _e():
    import engine_service as e      # import tardif : engine_service importe ce module à la fin
    return e


def _ref(cle: str) -> dict:
    return _e().BAEL[cle]


def section_bar(d_mm: float) -> float:
    return math.pi * (d_mm / 10.0) ** 2 / 4.0


# ───────────────────────── règles de ferraillage des dalles ─────────────────────────

def espacements_max_cm(h_cm: float, fissuration: str) -> Dict[str, float]:
    """A.8.2,42 : espacements maximaux (sens porteur principal / sens de répartition).
    Fissuration préjudiciable : min(2h ; 25 cm), très préjudiciable : min(1,5h ; 20 cm), dans les deux directions."""
    if fissuration == "prejudiciable":
        return {"principal": min(2 * h_cm, 25.0), "repartition": min(2 * h_cm, 25.0)}
    if fissuration == "tres_prejudiciable":
        return {"principal": min(1.5 * h_cm, 20.0), "repartition": min(1.5 * h_cm, 20.0)}
    return {"principal": min(3 * h_cm, 33.0), "repartition": min(4 * h_cm, 45.0)}


def choisir_treillis(as_requis_cm2_m: float, h_cm: float, st_max_cm: float) -> dict:
    """Barres HA à espacement constant (« HA10 e=15 ») : Ø ≤ h/10 (A.8.2,42), e ≤ st_max.

    On retient la plus petite section fournie ≥ As requise ; à égalité, l'espacement le
    plus grand (pose plus simple), puis le plus petit diamètre.
    """
    as_req = max(as_requis_cm2_m, 0.0)
    d_max = h_cm  # Ø (mm) ≤ h/10 avec h en mm, soit Ø (mm) ≤ h (cm)
    st_max = int(math.floor(st_max_cm))
    espacements = sorted({e for e in range(10, st_max + 1, 5)} | {st_max} if st_max >= 10 else {st_max})
    meilleur = None
    for d in (8, 10, 12, 14, 16, 20):
        if d > d_max:
            continue
        for e in espacements:
            fournie = section_bar(d) * 100.0 / e
            if fournie + 1e-9 < as_req:
                continue
            cle = (round(fournie, 3), -e, d)
            if meilleur is None or cle < meilleur[0]:
                meilleur = (cle, {"diametre_mm": d, "espacement_cm": e, "as_fournie_cm2_m": round(fournie, 2)})
    if meilleur is None:
        return {"diametre_mm": None, "espacement_cm": None, "as_fournie_cm2_m": None, "choix": "à revoir",
                "inconstructible": True}
    c = meilleur[1]
    c["choix"] = f"HA{c['diametre_mm']} e={c['espacement_cm']}"
    return c


def _armer(m_elu: float, m_els: float, h_cm: float, d_m: float, fc28: float, fe: float,
           fissuration: str, as_min: float, st_max: float) -> dict:
    """Section d'acier d'une bande de 1 m : ELU, minimum, puis ELS (σst) si nécessaire."""
    e = _e()
    elu = e.flexion_simple_elu(100.0, h_cm, d_m, fc28, fe, m_elu)
    as_elu = elu["as_cm2"]
    as_req = max(as_elu, as_min)
    choix = choisir_treillis(as_req, h_cm, st_max)
    els = e.flex_els(100.0, d_m, choix["as_fournie_cm2_m"] or as_req, fc28, fe, m_els, fissuration) if m_els > 0 else {}
    pas = 0
    while m_els > 0 and not els.get("sigma_st_ok", True) and not choix.get("inconstructible") and pas < 80:
        as_req = choix["as_fournie_cm2_m"] + 0.1
        choix = choisir_treillis(as_req, h_cm, st_max)
        if choix.get("inconstructible"):
            break
        els = e.flex_els(100.0, d_m, choix["as_fournie_cm2_m"], fc28, fe, m_els, fissuration)
        pas += 1
    return {"m_elu_knm": round(m_elu, 2), "m_els_knm": round(m_els, 2), "d_m": round(d_m, 3),
            "mu": elu["mu"], "z_m": elu["z_m"], "mode": elu["mode"],
            "as_elu_cm2_m": round(as_elu, 2), "as_min_cm2_m": round(as_min, 2),
            "as_retenue_cm2_m": round(as_req, 2), "gouverne": "ELS (σst)" if pas else ("minimum" if as_min > as_elu else "ELU"),
            "ferraillage": choix, "els": els}


def _rho0(fe: float) -> float:
    r = _ref("dalles")["rho0_armatures_min"]
    return r["fe400"] if fe <= 400 else r["fe500"]


def _poids_propre(h_cm: float) -> float:
    return _ref("charges")["poids_volumique_ba_kn_m3"]["valeur"] * h_cm / 100.0


def longueur_scellement_m(d_mm: float, fe: float, fc28: float) -> float:
    """A.6.1,23 : ls = Ø fe / (4 τs), τs = 0,6 ψs² ftj (barres HA, ψs = 1,5)."""
    psi = _ref("ancrage")["psi_s"]["ha"]
    tau_s = 0.6 * psi ** 2 * _e().ft28(fc28)
    return d_mm / 1000.0 * fe / (4.0 * tau_s)


# ───────────────────────── flèche : conditions de dispense ─────────────────────────

def fleche_dispense(cas: str, h_cm: float, l_m: float, mt: float, m0: float, as_cm2_m: float, d_m: float,
                    fe_mpa: float) -> dict:
    """Conditions du BAEL dispensant du calcul de la flèche.
    cas = "dalle" (B.7.5, dalle portant dans les deux sens) ou "poutre" (B.6.5,1 : poutre, console, bande de dalle)."""
    ref = _ref("fleche_dispense")
    h_l = h_cm / 100.0 / l_m
    taux = as_cm2_m / (100.0 * d_m * 100.0)            # A / (b d), b = 100 cm, d en cm
    if cas == "dalle":
        c = ref["dalle_deux_sens"]
        conditions = [
            {"nom": "h/lx ≥ Mtx/(20 M0x)", "valeur": round(h_l, 4), "limite": round(mt / (20.0 * m0), 4),
             "ok": bool(h_l >= mt / (20.0 * m0))},
            {"nom": "Ax/(b d) ≤ 2/fe", "valeur": round(taux, 5), "limite": round(c["a_sur_bd_max_x_fe"] / fe_mpa, 5),
             "ok": bool(taux <= c["a_sur_bd_max_x_fe"] / fe_mpa)},
        ]
        article = "B.7.5"
    else:
        c = ref["poutre_et_console"]
        conditions = [
            {"nom": "h/l ≥ 1/16", "valeur": round(h_l, 4), "limite": c["h_sur_l_min"], "ok": bool(h_l >= c["h_sur_l_min"])},
            {"nom": "h/l ≥ Mt/(10 M0)", "valeur": round(h_l, 4), "limite": round(mt / (10.0 * m0), 4),
             "ok": bool(h_l >= mt / (10.0 * m0))},
            {"nom": "A/(b d) ≤ 4,2/fe", "valeur": round(taux, 5), "limite": round(c["a_sur_bd_max_x_fe"] / fe_mpa, 5),
             "ok": bool(taux <= c["a_sur_bd_max_x_fe"] / fe_mpa)},
        ]
        article = "B.6.5,1"
    return {"article": article, "conditions": conditions, "dispense": all(x["ok"] for x in conditions)}


# ───────────────────────── dalle pleine ─────────────────────────

class DalleInput(BaseModel):
    lx_m: float = Field(..., gt=0.5, le=12, description="petite portée entre nus d'appuis (m)")
    ly_m: float = Field(..., gt=0.5, le=30, description="grande portée (m)")
    h_cm: float = Field(..., ge=8, le=40, description="épaisseur de la dalle (cm)")
    g_sup_kn_m2: float = Field(..., ge=0, description="charges permanentes hors poids propre : revêtement, enduit, cloisons (kN/m²)")
    q_kn_m2: float = Field(..., ge=0, description="charge d'exploitation (kN/m²)")
    continuite: str = Field("rive", description="isostatique | rive | intermediaire")
    fc28_mpa: float = Field(25.0, ge=12, le=60)
    fe_mpa: float = Field(500.0, ge=215, le=600)
    enrobage_mm: float = Field(25.0, ge=10, le=60)
    fissuration: str = "peu_prejudiciable"


def dalle(inp: DalleInput) -> dict:
    if inp.continuite not in CONTINUITES:
        raise ValueError(f"continuité inconnue : {inp.continuite} ({', '.join(CONTINUITES)})")
    if inp.fissuration not in FISSURATIONS:
        raise ValueError(f"fissuration inconnue : {inp.fissuration}")
    e = _e()
    ref = _ref("dalles")
    lx, ly = sorted((inp.lx_m, inp.ly_m))
    rho = lx / ly
    gpp = _poids_propre(inp.h_cm)
    g = gpp + inp.g_sup_kn_m2
    pu = 1.35 * g + 1.5 * inp.q_kn_m2
    ps = g + inp.q_kn_m2
    un_sens = rho < ref["rho_un_sens"]["valeur"]
    if un_sens:
        mu_x, mu_y = 1.0 / 8.0, 0.0
        m0x = pu * lx ** 2 / 8.0
        m0y = 0.0
    else:
        mu_x = 1.0 / (8.0 * (1.0 + 2.4 * rho ** 3))
        mu_y = max(rho ** 3 * (1.9 - 0.9 * rho), ref["my_min_sur_mx"]["valeur"])
        m0x = mu_x * pu * lx ** 2
        m0y = mu_y * m0x
    k = ref["continuite"][inp.continuite]
    r_els = ps / pu                                     # moments ELS proportionnels (ν = 0 retenu)
    h = inp.h_cm
    phi = 10.0                                          # Ø estimé pour d (mm)
    dx = h / 100.0 - (inp.enrobage_mm + phi / 2) / 1000.0
    dy = dx - phi / 1000.0                              # nappe y posée sur la nappe x
    st = espacements_max_cm(h, inp.fissuration)
    rho0 = _rho0(inp.fe_mpa)
    ay_min = rho0 * 100.0 * h
    ax_min = ay_min * (3.0 - rho) / 2.0 if not un_sens else ay_min * 1.5
    nf = lambda d: e.non_fragilite(100.0, d, inp.fc28_mpa, inp.fe_mpa)

    def arm(m, d, as_min, st_max):
        return _armer(m, m * r_els, h, d, inp.fc28_mpa, inp.fe_mpa, inp.fissuration, as_min, st_max)

    resultats = {
        "x_travee": arm(k["travee"] * m0x, dx, max(ax_min, nf(dx)), st["principal"]),
        "appuis": arm(k["appui"] * m0x, dx, max(ax_min, nf(dx)), st["principal"]),
    }
    if un_sens:   # armatures de répartition ≥ As/4 (A.8.2,41)
        a_rep = max(resultats["x_travee"]["ferraillage"]["as_fournie_cm2_m"] / 4.0, ay_min)
        resultats["y_travee"] = {"repartition": True, "as_retenue_cm2_m": round(a_rep, 2),
                                 "ferraillage": choisir_treillis(a_rep, h, st["repartition"])}
    else:
        resultats["y_travee"] = arm(k["travee"] * m0y, dy, max(ay_min, nf(dy)), st["repartition"])

    # effort tranchant : dalle sans armatures transversales si τu ≤ 0,05 fc28 (A.5.2,2)
    if un_sens:
        vx, vy = pu * lx / 2.0, 0.0
    else:
        vx, vy = pu * lx * ly / (2.0 * ly + lx), pu * lx / 3.0
    tau = max(vx, vy) * 1e3 / (1.0 * dx * 1e6)
    tau_lim = 0.05 * inp.fc28_mpa
    cisaillement = {"vx_kn_m": round(vx, 2), "vy_kn_m": round(vy, 2), "tau_u_mpa": round(tau, 3),
                    "tau_lim_mpa": round(tau_lim, 2), "ok": bool(tau <= tau_lim)}

    remarques: List[str] = []
    for nom, r in resultats.items():
        f = r["ferraillage"]
        if f.get("inconstructible"):
            remarques.append(f"{nom} : aucune nappe HA à Ø ≤ h/10 et e ≤ espacement maximal ne suffit ; augmentez l'épaisseur.")
        if r.get("els") and not r["els"].get("sigma_bc_ok", True):
            remarques.append(f"{nom} : σbc > 0,6 fc28 à l'ELS ; augmentez l'épaisseur.")
        if r.get("mode") == "aciers comprimés":
            remarques.append(f"{nom} : μ > μlim, aciers comprimés nécessaires ; augmentez l'épaisseur.")
    if not cisaillement["ok"]:
        remarques.append("τu > 0,05 fc28 : armatures d'effort tranchant nécessaires ou épaisseur à augmenter (A.5.2,2).")
    xt = resultats["x_travee"]
    fleche = fleche_dispense("poutre" if un_sens else "dalle", h, lx, k["travee"] * m0x, m0x,
                             xt["ferraillage"]["as_fournie_cm2_m"] or xt["as_retenue_cm2_m"], dx, inp.fe_mpa)
    if not fleche["dispense"]:
        manquees = ", ".join(c["nom"] for c in fleche["conditions"] if not c["ok"])
        remarques.append(f"Flèche : condition de dispense non satisfaite ({fleche['article']} : {manquees}) ; "
                         "calculez la flèche (B.6.5,2) ou augmentez l'épaisseur.")
    from common import audit_ligne
    fsu = e.sigma_s_elu(inp.fe_mpa)
    xt = resultats["x_travee"]
    audit = [
        audit_ligne("pu = 1,35 g + 1,5 q", 1.35 * g + 1.5 * inp.q_kn_m2, round(pu, 3), 0.001),
        audit_ligne("M0x = μx pu lx²" if not un_sens else "M0x = pu lx² / 8",
                    round(mu_x, 4) * pu * lx ** 2 if not un_sens else pu * lx ** 2 / 8, round(m0x, 2), 0.02),
        audit_ligne("Mtx = kt M0x", k["travee"] * round(m0x, 2), xt["m_elu_knm"], 0.02),
        audit_ligne("As = Mtx / (Z fsu)", xt["m_elu_knm"] * 1e3 / (xt["z_m"] * fsu * 1e6) * 1e4, xt["as_elu_cm2_m"], 0.02),
    ]
    return {
        "type": "dalle", "un_sens": un_sens, "rho": round(rho, 3), "lx_m": lx, "ly_m": ly, "h_cm": h,
        "charges": {"g_poids_propre_kn_m2": round(gpp, 2), "g_kn_m2": round(g, 2), "q_kn_m2": inp.q_kn_m2,
                    "pu_kn_m2": round(pu, 3), "ps_kn_m2": round(ps, 3)},
        "mu_x": round(mu_x, 4), "mu_y": round(mu_y, 4), "m0x_knm": round(m0x, 2), "m0y_knm": round(m0y, 2),
        "continuite": inp.continuite, "coefficients": {"travee": k["travee"], "appui": k["appui"]},
        "espacements_max_cm": st, "resultats": resultats, "cisaillement": cisaillement, "fleche": fleche,
        "verifie": not remarques, "audit": audit,
        "remarques": remarques,
        "hypotheses": ["Moments ELS pris proportionnels aux moments ELU (coefficients μ à ν = 0) : approché, à vérifier.",
                       "Panneau rectangulaire uniformément chargé, sans ouverture ni charge concentrée."],
    }


# ───────────────────────── balcon en porte-à-faux ─────────────────────────

class BalconInput(BaseModel):
    longueur_m: float = Field(..., gt=0.2, le=3.0, description="porte-à-faux, du nu de l'appui au bord libre (m)")
    h_cm: float = Field(..., ge=10, le=40, description="épaisseur à l'encastrement (cm)")
    g_sup_kn_m2: float = Field(..., ge=0, description="revêtement, forme de pente, étanchéité (kN/m²)")
    q_kn_m2: float = Field(..., ge=0, description="charge d'exploitation du balcon (kN/m²)")
    garde_corps_kn_m: float = Field(0.0, ge=0, description="poids du garde-corps ou de l'acrotère en bout (kN/m)")
    poussee_kn_m: float = Field(0.0, ge=0, description="poussée horizontale sur la main courante (kN/m)")
    hauteur_main_courante_m: float = Field(1.0, ge=0, le=1.5)
    fc28_mpa: float = Field(25.0, ge=12, le=60)
    fe_mpa: float = Field(500.0, ge=215, le=600)
    enrobage_mm: float = Field(30.0, ge=10, le=60, description="ouvrage extérieur : 3 cm au moins (A.7.1)")
    fissuration: str = "prejudiciable"


def balcon(inp: BalconInput) -> dict:
    if inp.fissuration not in FISSURATIONS:
        raise ValueError(f"fissuration inconnue : {inp.fissuration}")
    e = _e()
    l, h = inp.longueur_m, inp.h_cm
    gpp = _poids_propre(h)
    g = gpp + inp.g_sup_kn_m2
    q, P, H, hg = inp.q_kn_m2, inp.garde_corps_kn_m, inp.poussee_kn_m, inp.hauteur_main_courante_m
    mg = g * l ** 2 / 2.0 + P * l
    mq = q * l ** 2 / 2.0 + H * hg
    mu = 1.35 * mg + 1.5 * mq
    ms = mg + mq
    vu = 1.35 * (g * l + P) + 1.5 * q * l
    phi = 10.0
    d = h / 100.0 - (inp.enrobage_mm + phi / 2) / 1000.0
    st = espacements_max_cm(h, inp.fissuration)
    as_min = max(e.non_fragilite(100.0, d, inp.fc28_mpa, inp.fe_mpa), _rho0(inp.fe_mpa) * 100.0 * h * 1.5)
    sup = _armer(mu, ms, h, d, inp.fc28_mpa, inp.fe_mpa, inp.fissuration, as_min, st["principal"])
    a_rep = max(sup["ferraillage"]["as_fournie_cm2_m"] / 4.0 if sup["ferraillage"]["as_fournie_cm2_m"] else 0.0,
                _rho0(inp.fe_mpa) * 100.0 * h)
    repartition = {"as_retenue_cm2_m": round(a_rep, 2), "ferraillage": choisir_treillis(a_rep, h, st["repartition"])}
    inferieur = {"as_retenue_cm2_m": round(_rho0(inp.fe_mpa) * 100.0 * h, 2),
                 "ferraillage": choisir_treillis(_rho0(inp.fe_mpa) * 100.0 * h, h, st["repartition"])}
    tau = vu * 1e3 / (1.0 * d * 1e6)
    tau_lim = 0.05 * inp.fc28_mpa
    phi_sup = sup["ferraillage"]["diametre_mm"] or 10
    ls = longueur_scellement_m(phi_sup, inp.fe_mpa, inp.fc28_mpa)
    prolongement = max(l, ls)
    remarques: List[str] = []
    if sup["ferraillage"].get("inconstructible"):
        remarques.append("Aucune nappe supérieure HA à Ø ≤ h/10 et e ≤ espacement maximal ne suffit : augmentez l'épaisseur.")
    if sup["mode"] == "aciers comprimés":
        remarques.append("μ > μlim : augmentez l'épaisseur du balcon.")
    if sup["els"] and not sup["els"].get("sigma_bc_ok", True):
        remarques.append("σbc > 0,6 fc28 à l'ELS : augmentez l'épaisseur.")
    if tau > tau_lim:
        remarques.append("τu > 0,05 fc28 : armatures d'effort tranchant nécessaires ou épaisseur à augmenter (A.5.2,2).")
    # console : Mt = M0, d'où h/l ≥ 1/10 (B.6.5,1)
    fleche = fleche_dispense("poutre", h, l, mu, mu, sup["ferraillage"]["as_fournie_cm2_m"] or sup["as_retenue_cm2_m"],
                             d, inp.fe_mpa)
    if not fleche["dispense"]:
        manquees = ", ".join(c["nom"] for c in fleche["conditions"] if not c["ok"])
        remarques.append(f"Flèche : h = {h:g} cm, l/10 = {l * 10:g} cm ; condition de dispense non satisfaite "
                         f"(B.6.5,1 : {manquees}) ; calculez la flèche en bout de console ou augmentez l'épaisseur.")
    dispositions = [
        "Aciers principaux en nappe SUPÉRIEURE (zone tendue de la console) ; prévoir des distanciers pour les maintenir en place.",
        f"Prolonger les chapeaux dans la dalle intérieure d'au moins {prolongement:.2f} m (max(l, ls), ls = {ls:.2f} m) ; "
        "la dalle intérieure doit équilibrer le moment (cas Q sur le balcon seul).",
        "Sans dalle intérieure au même niveau (décaissé, trémie, escalier) : ancrer dans une poutre calculée en torsion.",
        "Bord libre : U de rive ; goutte d'eau ; pente ≥ 1 % vers l'extérieur et étanchéité relevée.",
    ]
    from common import audit_ligne
    fsu = e.sigma_s_elu(inp.fe_mpa)
    audit = [
        audit_ligne("Mu = 1,35 (g l²/2 + P l) + 1,5 (q l²/2 + H hg)",
                    1.35 * (g * l ** 2 / 2 + P * l) + 1.5 * (q * l ** 2 / 2 + H * hg), round(mu, 2), 0.01),
        audit_ligne("Vu = 1,35 (g l + P) + 1,5 q l", 1.35 * (g * l + P) + 1.5 * q * l, round(vu, 2), 0.01),
        audit_ligne("As = Mu / (Z fsu)", round(mu, 2) * 1e3 / (sup["z_m"] * fsu * 1e6) * 1e4, sup["as_elu_cm2_m"], 0.02),
    ]
    return {
        "type": "balcon", "longueur_m": l, "h_cm": h, "d_m": round(d, 3),
        "charges": {"g_poids_propre_kn_m2": round(gpp, 2), "g_kn_m2": round(g, 2), "q_kn_m2": q,
                    "garde_corps_kn_m": P, "poussee_kn_m": H, "hauteur_main_courante_m": hg},
        "mu_knm": round(mu, 2), "ms_knm": round(ms, 2), "vu_kn": round(vu, 2),
        "nappe_superieure": sup, "repartition": repartition, "nappe_inferieure": inferieur,
        "cisaillement": {"tau_u_mpa": round(tau, 3), "tau_lim_mpa": round(tau_lim, 2), "ok": bool(tau <= tau_lim)},
        "ls_m": round(ls, 2), "prolongement_chapeaux_m": round(prolongement, 2),
        "espacements_max_cm": st, "dispositions": dispositions, "fleche": fleche,
        "verifie": not remarques, "audit": audit,
        "remarques": remarques,
        "hypotheses": ["Console encastrée sur toute sa largeur, bande de 1 m ; charges uniformes.",
                       "Flèche : conditions de dispense B.6.5,1 vérifiées ; si elles ne le sont pas, la flèche est à calculer."],
    }
