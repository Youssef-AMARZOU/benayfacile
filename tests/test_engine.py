"""Tests unitaires du moteur BAEL/RPS — valeurs vérifiées manuellement."""
import math
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import engine_service as e  # noqa: E402
from common import choisir_barres, section_bar  # noqa: E402


# ---------- BAEL : flexion simple ----------
def test_sigma_bc_elu_fc25():
    # σbc = 0.85 * 25 / (1 * 1.5) = 14.1667 MPa
    assert e.sigma_bc_elu(25) == pytest.approx(0.85 * 25 / 1.5, abs=1e-6)


def test_flexion_simple_poutre_250x500():
    # Mu = 150 kN.m, b=25 cm, d=0.54 m
    r = e.flexion_simple_elu(25, 60, 0.54, 25, 500, 150)
    assert r["mode"] == "simple"
    assert 0 < r["mu"] < 0.372           # sous μlim FeE500
    assert r["as_cm2"] > 0
    # recalcul arithmétique
    bc = 0.25
    sbc = e.sigma_bc_elu(25)
    mu = 150 * 1000 / (bc * 0.54**2 * sbc * 1e6)
    assert r["mu"] == pytest.approx(mu, abs=1e-3)
    alpha = 1.25 * (1 - math.sqrt(1 - 2 * mu))
    z = 0.54 * (1 - 0.4 * alpha)
    as_expect = 150 * 1000 / (z * (500 / 1.15) * 1e6) * 1e4
    assert r["as_cm2"] == pytest.approx(as_expect, rel=1e-2)


def test_flexion_simple_mu_lim_fe500():
    # μlim FeE500 = 0.372 ; μ au-delà -> aciers comprimés
    r_limit = e.flexion_simple_elu(25, 60, 0.54, 25, 500, 10_000.0)  # Mu énorme
    assert r_limit["mu"] > 0.372
    assert r_limit["mode"] == "aciers comprimés"
    assert r_limit["as_comprimes_cm2"] > 0


def test_non_fragilite_poutre():
    # As,min = 0.23 * b * d * ft28 / fe ; ft28 = 0.6+0.06*25 = 2.1 MPa
    as_nf = e.non_fragilite(25, 0.54, 25, 500)
    expect = 0.23 * 0.25 * 0.54 * (2.1e6) / 500e6 * 1e4
    assert as_nf == pytest.approx(expect, rel=1e-6)


# ---------- BAEL : poteau ----------
def test_poteau_compression_centree():
    # 30x30, lf=3 m, Nu=800 kN, fc28=25, fe=500
    r = e.poteau_b84(30, 30, 3.0, 25, 500, 800)
    assert r["applicable_b841"] is True
    assert r["lambda"] == pytest.approx(3.0 / (0.3 / math.sqrt(12)), abs=0.01)
    assert r["alpha"] == pytest.approx(0.85 / (1 + 0.2 * (r["lambda"] / 35) ** 2), abs=1e-4)
    # Nu,lim avec As retenu >= Nu requis
    assert r["nu_lim_kn_avec_as_fournie"] >= 800
    # Armatures minimales A.8.1,21 (4 cm²/m)
    assert r["as_min_long_cm2"] == pytest.approx(4.8, rel=1e-6)


def test_poteau_nu_eleve_requiert_acier():
    # charge très élevée → As requise > As min constructive
    r = e.poteau_b84(20, 20, 3.0, 25, 500, 1500)
    assert r["as_requis_cm2"] > 0
    assert r["as_calculee_cm2"] == pytest.approx(max(r["as_requis_cm2"], r["as_min_long_cm2"], r["as_min_sect_cm2"]))


def test_poteau_lambda_hors_domaine():
    r = e.poteau_b84(30, 30, 9.0, 25, 500, 100)  # λ > 70
    assert r["lambda"] > 70
    assert r["applicable_b841"] is False


def test_poteau_flexion_composee_capacite():
    r = e.poteau_b84(30, 30, 3.0, 25, 500, 800)
    as_f = r["ferraillage"]["as_fournie_cm2"]
    m = e.poteau_moment_capacity(30, 30, as_f, 25, 500, 800, moment_knm=25)
    assert m["n_verification_kn"] == pytest.approx(800, abs=1.0)
    assert m["moment_capable_knm"] > 0


# ---------- Semelles ----------
def test_semelle_isolee_equilibrium():
    from engine_service import SemelleInput, _dimensionner_semelle
    inp = SemelleInput(ns_kn=1000, nu_kn=1500, a_poteau_cm=30, b_poteau_cm=30, sigma_sol_bar=2.0)
    r = _dimensionner_semelle(inp, "semelle isolée")
    # σ ≤ σsol (bar)
    assert r["sigma_max_bar"] <= 2.0 + 1e-6
    assert r["sigma_min_bar"] >= 0.0
    # semelle rigide h ≥ (A-a)/4
    a_m = 0.30
    assert r["H_m"] >= (max(r["A_m"], r["B_m"]) - a_m) / 4.0 - 1e-9
    # poids (tolérance liée aux arrondis d'affichage des champs A/B/H)
    assert r["poids_T"] == pytest.approx(r["A_m"] * r["B_m"] * r["H_m"] * 2.5, abs=0.06)
    # bielles : As = Nu(A-a)/(8 d σs)
    nu_n = 1500 * 1000
    expect = nu_n * (r["A_m"] - a_m) / (8 * r["d_m"] * (500 / 1.15) * 1e6) * 1e4
    assert r["asx_cm2"] >= expect - 0.01  # non-fragilité peut majorer


# ---------- Voile ----------
def test_voile_pleine_compression():
    from engine_service import VoileInput, app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    r = c.post("/voile", json={"longueur_m": 4.0, "ep_cm": 20, "fc28_mpa": 25, "fe_mpa": 500,
                               "n_kn": 1500, "m_knm": 0, "v_kn": 0}).json()
    assert r["sigma_min_mpa"] >= 0
    assert "entièrement comprimée" in r["mode"]
    assert r["as_rive_cm2"] == pytest.approx(0.0)


def test_voile_partiellement_comprime():
    from engine_service import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    r = c.post("/voile", json={"longueur_m": 2.0, "ep_cm": 15, "fc28_mpa": 25, "fe_mpa": 500,
                               "n_kn": 300, "m_knm": 300, "v_kn": 50}).json()
    assert r["sigma_min_mpa"] < 0
    assert r["as_rive_cm2"] > 0


# ---------- RPS 2000 v2011 ----------
def test_rps_force_base():
    from engine_service import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    r = c.post("/sismique", json={
        "hauteur_m": 15.0, "longueur_contreventement_m": 12.0,
        "g_kn": 3800, "q_kn": 1200, "usage": "habitation_admin",
        "zone_vitesse": 2, "rapport_za_zv": "za_eq_zv", "site": "S2",
        "classe": "classe_II", "systeme": "portiques_ba", "ductilite": "ND2",
        "periode_methode": "portique", "amortissement_pct": 5.0}).json()
    W = 3800 + 0.2 * 1200
    T = 0.075 * 15 ** 0.75
    D = 1.20 / T ** (2 / 3)
    expect = 0.10 * 1.2 * D * 1.2 * W / 3.5
    assert r["T_s"] == pytest.approx(T, abs=1e-3)
    assert r["D"] == pytest.approx(D, abs=1e-3)
    assert r["W_kn"] == pytest.approx(W, abs=1e-3)
    assert r["F_base_kn"] == pytest.approx(expect, rel=1e-3)


def test_rps_ft_seulement_si_t_superieur_07():
    from engine_service import app
    from fastapi.testclient import TestClient
    c = TestClient(app)
    # H petit -> T < 0.7 -> Ft = 0
    r = c.post("/sismique", json={
        "hauteur_m": 6.0, "longueur_contreventement_m": 12.0,
        "g_kn": 1000, "q_kn": 100, "usage": "habitation_admin",
        "zone_vitesse": 1, "rapport_za_zv": "za_lt_zv", "site": "S1",
        "classe": "classe_III", "systeme": "portiques_ba", "ductilite": "ND1",
        "periode_methode": "portique", "amortissement_pct": 5.0}).json()
    assert r["T_s"] < 0.7
    assert r["Ft_kn"] == 0.0


# ---------- Sélection de barres ----------
def test_choisir_barres_couvre_section():
    for as_req in (2.0, 5.0, 9.5, 19.6, 45.0):
        r = choisir_barres(as_req)
        assert r["as_fournie_cm2"] >= as_req


def test_section_bar_ha12():
    assert section_bar(12) == pytest.approx(1.130973, abs=1e-4)
