"""Dalles pleines et balcons : cas calculés à la main (BAEL 91 rév. 99)."""
import json
import math
import pathlib
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "services"))

import engine_service as e  # noqa: E402
import dalles as D  # noqa: E402


# ---------- balcon : l = 1,50 m, h = 18 cm, revêtement 1,5, q = 3,5, garde-corps 1,0 kN/m ----------
@pytest.fixture(scope="module")
def balcon():
    return D.balcon(D.BalconInput(longueur_m=1.5, h_cm=18, g_sup_kn_m2=1.5, q_kn_m2=3.5, garde_corps_kn_m=1.0))


def test_balcon_moment_et_effort_a_l_encastrement(balcon):
    # g = 25 × 0,18 + 1,5 = 6,0 kN/m² ; l²/2 = 1,125
    # Mu = 1,35 (6,0 × 1,125 + 1,0 × 1,5) + 1,5 (3,5 × 1,125) = 11,1375 + 5,90625 = 17,04375
    assert balcon["charges"]["g_kn_m2"] == 6.0
    assert balcon["mu_knm"] == pytest.approx(17.04, abs=0.01)
    assert balcon["ms_knm"] == pytest.approx(12.19, abs=0.01)          # 8,25 + 3,9375
    assert balcon["vu_kn"] == pytest.approx(21.38, abs=0.01)           # 1,35 × 10 + 1,5 × 5,25


def test_balcon_aciers_superieurs(balcon):
    # d = 0,18 − 0,030 − 0,005 = 0,145 ; μ = 17,044e3 / (0,145² × 14,17e6) = 0,0572
    # α = 0,0737 ; z = 0,1407 ; As = 17,044e3 / (0,1407 × 434,8e6) = 2,79 cm²/m
    sup = balcon["nappe_superieure"]
    assert balcon["d_m"] == 0.145
    assert sup["as_elu_cm2_m"] == pytest.approx(2.79, abs=0.01)
    # extérieur : fissuration préjudiciable, σst,lim = min(333, max(250, 201,6)) = 250 MPa → l'ELS gouverne
    assert sup["gouverne"] == "ELS (σst)" and sup["els"]["sigma_st_lim_mpa"] == 250.0
    assert sup["els"]["sigma_st_ok"] and sup["ferraillage"]["as_fournie_cm2_m"] >= sup["as_retenue_cm2_m"]
    assert sup["ferraillage"]["espacement_cm"] <= 25                     # A.8.2,42 préjudiciable : min(2h, 25)


def test_balcon_ancrage_et_dispositions(balcon):
    # ls = Ø fe / (4 × 0,6 × 1,5² × 2,1) = 10 × 500 / 11,34 = 441 mm (HA10)
    assert balcon["ls_m"] == pytest.approx(0.44, abs=0.01)
    assert balcon["prolongement_chapeaux_m"] == 1.5                      # max(l, ls)
    assert "SUPÉRIEURE" in balcon["dispositions"][0]
    assert balcon["cisaillement"]["ok"] and balcon["verifie"]


def test_balcon_elance_signale():
    r = D.balcon(D.BalconInput(longueur_m=2.0, h_cm=15, g_sup_kn_m2=1.5, q_kn_m2=3.5))
    assert any("l/10" in x for x in r["remarques"])


def test_poussee_sur_garde_corps_augmente_le_moment():
    base = dict(longueur_m=1.2, h_cm=16, g_sup_kn_m2=1.5, q_kn_m2=3.5)
    m0 = D.balcon(D.BalconInput(**base))["mu_knm"]
    m1 = D.balcon(D.BalconInput(**base, poussee_kn_m=1.0, hauteur_main_courante_m=1.0))["mu_knm"]
    assert m1 - m0 == pytest.approx(1.5, abs=0.01)                       # 1,5 × H × hg


# ---------- dalle portant dans les deux sens : 4 × 5 m, h = 16 cm, panneau de rive ----------
@pytest.fixture(scope="module")
def dalle():
    return D.dalle(D.DalleInput(lx_m=4, ly_m=5, h_cm=16, g_sup_kn_m2=1.5, q_kn_m2=1.5, continuite="rive"))


def test_dalle_coefficients_annexe_e3(dalle):
    # ρ = 0,8 ; μx = 1 / (8 (1 + 2,4 × 0,512)) = 0,05608 ; μy = 0,512 × (1,9 − 0,72) = 0,6042
    assert dalle["rho"] == 0.8 and not dalle["un_sens"]
    assert dalle["mu_x"] == pytest.approx(0.0561, abs=1e-4)
    assert dalle["mu_y"] == pytest.approx(0.6042, abs=1e-4)
    # pu = 1,35 × (4,0 + 1,5) + 1,5 × 1,5 = 9,675 ; M0x = 0,05608 × 9,675 × 16 = 8,68
    assert dalle["charges"]["pu_kn_m2"] == pytest.approx(9.675)
    assert dalle["m0x_knm"] == pytest.approx(8.68, abs=0.01)
    assert dalle["m0y_knm"] == pytest.approx(5.25, abs=0.01)


def test_dalle_moments_de_continuite_et_aciers(dalle):
    r = dalle["resultats"]
    assert r["x_travee"]["m_elu_knm"] == pytest.approx(7.38, abs=0.01)   # 0,85 M0x
    assert r["appuis"]["m_elu_knm"] == pytest.approx(4.34, abs=0.01)     # 0,5 M0x
    assert r["y_travee"]["m_elu_knm"] == pytest.approx(4.46, abs=0.01)   # 0,85 M0y
    # d = 0,13 ; μ = 0,0308 ; z = 0,1280 ; As = 7,38e3 / (0,128 × 434,8e6) = 1,33 cm²/m
    assert r["x_travee"]["as_elu_cm2_m"] == pytest.approx(1.33, abs=0.01)
    # minimum : max(ρ0 (3 − ρ)/2 × 100 h = 1,06 ; 0,23 × 0,13 × 2,1 / 500 = 1,26) → l'appui est au minimum
    assert r["appuis"]["as_min_cm2_m"] == pytest.approx(1.26, abs=0.01) and r["appuis"]["gouverne"] == "minimum"
    for k in ("x_travee", "appuis"):
        assert r[k]["ferraillage"]["espacement_cm"] <= 33                # min(3h, 33)
    assert r["y_travee"]["ferraillage"]["espacement_cm"] <= 45           # min(4h, 45)


def test_dalle_effort_tranchant(dalle):
    # Vx = p lx ly / (2 ly + lx) = 9,675 × 20 / 14 = 13,82 ; Vy = p lx / 3 = 12,90
    c = dalle["cisaillement"]
    assert (c["vx_kn_m"], c["vy_kn_m"]) == (13.82, 12.9)
    assert c["tau_lim_mpa"] == 1.25 and c["ok"]


def test_dalle_portant_dans_un_seul_sens():
    # 3 × 8 m : ρ = 0,375 < 0,4 ; pu = 1,35 × 5,0 + 1,5 × 1,5 = 9,0 ; M0 = 9 × 3² / 8 = 10,125
    r = D.dalle(D.DalleInput(lx_m=3, ly_m=8, h_cm=14, g_sup_kn_m2=1.5, q_kn_m2=1.5, continuite="isostatique"))
    assert r["un_sens"] and r["m0x_knm"] == pytest.approx(10.12, abs=0.01)
    rep = r["resultats"]["y_travee"]
    assert rep["repartition"] and rep["as_retenue_cm2_m"] >= r["resultats"]["x_travee"]["ferraillage"]["as_fournie_cm2_m"] / 4


def test_portees_inversees_et_entrees_invalides():
    a = D.dalle(D.DalleInput(lx_m=5, ly_m=4, h_cm=16, g_sup_kn_m2=1.5, q_kn_m2=1.5))
    assert (a["lx_m"], a["ly_m"]) == (4, 5)
    with pytest.raises(ValueError):
        D.dalle(D.DalleInput(lx_m=4, ly_m=5, h_cm=16, g_sup_kn_m2=1.5, q_kn_m2=1.5, continuite="encastree"))


def test_treillis_diametre_et_espacement():
    t = D.choisir_treillis(3.0, h_cm=12, st_max_cm=25)
    assert t["diametre_mm"] <= 12 and t["espacement_cm"] <= 25 and t["as_fournie_cm2_m"] >= 3.0
    assert t["as_fournie_cm2_m"] == pytest.approx(D.section_bar(t["diametre_mm"]) * 100 / t["espacement_cm"], abs=0.01)
    assert D.choisir_treillis(40.0, h_cm=10, st_max_cm=20).get("inconstructible")


def test_constantes_dans_le_referentiel():
    bael = json.loads((RACINE / "referentiels" / "bael.json").read_text(encoding="utf-8"))
    for cle in ("dalles", "balcons", "ancrage", "charges"):
        assert "_source" in json.dumps(bael[cle])
    assert bael["charges"]["poids_volumique_ba_kn_m3"]["valeur"] == 25.0


def test_routes_du_moteur():
    assert e.balcon(D.BalconInput(longueur_m=1.5, h_cm=18, g_sup_kn_m2=1.5, q_kn_m2=3.5))["type"] == "balcon"
    with pytest.raises(Exception) as err:
        e.dalle(D.DalleInput(lx_m=4, ly_m=5, h_cm=16, g_sup_kn_m2=1, q_kn_m2=1, fissuration="inconnue"))
    assert "fissuration" in str(err.value.detail)


# ---------- note de calcul ----------
def test_note_section_dalles_et_balcons():
    import re
    import xml.dom.minidom
    import note_calcul as nc
    d = D.dalle(D.DalleInput(lx_m=4, ly_m=5, h_cm=16, g_sup_kn_m2=1.5, q_kn_m2=1.5))
    b = D.balcon(D.BalconInput(longueur_m=1.5, h_cm=18, g_sup_kn_m2=1.5, q_kn_m2=3.5, garde_corps_kn_m=1.0))
    mince = D.balcon(D.BalconInput(longueur_m=2.5, h_cm=12, g_sup_kn_m2=1.5, q_kn_m2=3.5, garde_corps_kn_m=3.0))
    html = nc.construire({"projet": "Test", "dalles": [{**d, "nom": "D1", "niveau": "R+1"}],
                          "balcons": [{**b, "nom": "B1"}, {**mince, "nom": "B2"}]}, {})
    assert "6.5 Dalles et balcons" in html and "Dalles pleines</caption>" in html and "Balcons en porte-à-faux</caption>" in html
    assert "nappe supérieure" in html and "HA" in html
    for f in re.findall(r"<math .*?</math>", html, flags=re.S):
        xml.dom.minidom.parseString(f)
    assert not mince["verifie"] and "Balcon B2" in html.split("Réserves.")[1]


def test_note_sans_dalle_ni_balcon():
    import note_calcul as nc
    assert "Aucune dalle ni aucun balcon calculé." in nc.construire({"projet": "Vide"}, {})
