"""Planchers à corps creux 16+4 : cas calculés à la main (BAEL 91 rév. 99, B.6.2 et B.6.8,42)."""
import json
import pathlib
import sys

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "services"))

import engine_service as e  # noqa: E402
import planchers as P  # noqa: E402

BASE = dict(hourdis_cm=16, dalle_compression_cm=4, b0_cm=12, entraxe_cm=60,
            g_plancher_kn_m2=2.8, g_sup_kn_m2=2.2, q_kn_m2=1.5)


@pytest.fixture(scope="module")
def deux():
    return P.plancher(P.PlancherInput(travees_m=[4.0, 4.0], **BASE))


def test_charges_par_poutrelle(deux):
    # G = 2,8 + 2,2 = 5,0 ; par poutrelle (0,60 m) : g = 3,0, q = 0,9 ; pu = 1,35 × 3,0 + 1,5 × 0,9 = 5,40
    c = deux["charges"]
    assert (c["g_kn_m"], c["q_kn_m"], c["pu_kn_m"], c["ps_kn_m"]) == (3.0, 0.9, 5.4, 3.9)
    assert deux["designation"] == "16+4" and deux["h_cm"] == 20


def test_methode_forfaitaire_deux_travees(deux):
    # M0 = 5,4 × 4² / 8 = 10,80 ; appui central 0,6 M0 = 6,48
    # α = 1,5 / 6,5 = 0,2308 ; Mt ≥ 1,0692 × 10,8 − 6,48 / 2 = 8,31 ; Mt ≥ (1,2 + 0,0692) / 2 × 10,8 = 6,85
    assert deux["methode"] == "forfaitaire"
    t = deux["travees"][0]
    assert t["m0_knm"] == 10.8 and deux["appuis"][1]["ma_knm"] == 6.48
    assert t["mt_knm"] == pytest.approx(8.31, abs=0.01)
    assert t["vu_kn"] == pytest.approx(12.42, abs=0.01)                  # 1,15 × 5,4 × 4 / 2


def test_section_en_T_en_travee(deux):
    # b1 = min((60 − 12)/2 ; 400/10) = 24 → b = 60 cm ; d = 0,20 − 0,032 = 0,168 m
    # Mtu = 0,60 × 0,04 × 14,17 × (0,168 − 0,02) = 50,32 kN·m > Mt : table seule comprimée
    # μ = 8,308e-3 / (0,6 × 0,168² × 14,17) = 0,0346 ; z = 0,1650 ; As = 1,16 cm² → 2 HA10
    t = deux["travees"][0]
    assert t["b_cm"] == 60 and deux["d_m"] == 0.168
    assert t["elu"]["mtu_knm"] == pytest.approx(50.32, abs=0.01) and "table seule" in t["elu"]["cas"]
    assert t["elu"]["mu"] == pytest.approx(0.0346, abs=1e-4)
    assert t["as_retenue_cm2"] == pytest.approx(1.16, abs=0.01)
    assert t["ferraillage"]["choix"] == "2 HA10"


def test_chapeaux_sur_appui(deux):
    # rectangle b0 × h : μ = 6,48e-3 / (0,12 × 0,168² × 14,17) = 0,1351 ; z = 0,1558 ; As = 0,96 cm²
    a = deux["appuis"][1]
    assert a["mu"] == pytest.approx(0.1351, abs=1e-4)
    assert a["as_elu_cm2"] == pytest.approx(0.96, abs=0.01)
    assert a["longueur_chapeau_m"] == 1.0                                # l/4, appui voisin de rive


def test_etriers_et_cisaillement(deux):
    # τu = 12,42e-3 / (0,12 × 0,168) = 0,616 MPa ≤ min(0,2 × 25 / 1,5 ; 5) = 3,33
    # τu < 0,3 ft28 = 0,63 : st = min(0,9 d = 15,1 ; 40 ; At fet / (0,4 b0) = 27,7) → 15 cm
    t = deux["travees"][0]
    assert t["cisaillement"]["tau_u_mpa"] == pytest.approx(0.616, abs=0.001) and t["cisaillement"]["tau_lim_mpa"] == 3.33
    assert t["etriers"]["st_cm"] == 15


def test_dalle_de_compression(deux):
    # L = 60 cm : A⊥ = 4 × 60 / 500 = 0,48 cm²/m ; A// = 0,24 cm²/m ; TS Ø5 maille 20 = 0,98 cm²/m
    ts = deux["dalle_compression"]
    assert (ts["a_perp_cm2_m"], ts["a_par_cm2_m"]) == (0.48, 0.24)
    assert ts["choix"] == "TS Ø5 maille 20 × 20 cm"


def test_fleche_calculee_quand_pas_de_dispense(deux):
    # h/l = 0,05 < Mt/(15 M0) = 8,31/162 = 0,0513 : pas de dispense, la flèche est calculée (B.6.5,2)
    f = deux["travees"][0]["fleche"]
    assert not f["dispense"] and f["conditions"][1]["limite"] == pytest.approx(0.0513, abs=1e-4)
    c = f["calcul"]
    assert c["f_adm_mm"] == 8.0                                          # l/500, l = 4 m
    assert c["delta_ft_mm"] == pytest.approx(c["fgv_mm"] - c["fji_mm"] + c["fpi_mm"] - c["fgi_mm"], abs=0.02)
    assert c["ok"] and f["ok"] and deux["verifie"]


def test_caquot_minoree_si_portees_trop_differentes():
    # 3,0 / 4,5 = 0,67 < 0,8 → Caquot minorée (Q ≤ 2G) ; G' = 2/3 × 3,0 = 2,0 kN/m
    # appui : p = 1,35 × 2,0 + 1,5 × 0,9 = 4,05 ; Ma = 4,05 (3³ + 4,5³) / (8,5 × 7,5) = 7,51 kN·m
    r = P.plancher(P.PlancherInput(travees_m=[3.0, 4.5], **BASE))
    assert r["methode"] == "Caquot minorée"
    assert r["appuis"][1]["ma_knm"] == pytest.approx(7.51, abs=0.01)


def test_travee_isostatique():
    r = P.plancher(P.PlancherInput(travees_m=[3.5], **BASE))
    assert r["methode"] == "isostatique"
    assert r["travees"][0]["mt_knm"] == pytest.approx(5.4 * 3.5 ** 2 / 8, abs=0.01)


def test_plancher_trop_mince_signale():
    r = P.plancher(P.PlancherInput(travees_m=[5.5, 5.5], **BASE))
    assert not r["verifie"] and any("flèche" in x for x in r["remarques"])


def test_entrees_invalides_et_route():
    with pytest.raises(ValueError):
        P.plancher(P.PlancherInput(travees_m=[4.0], **{**BASE, "b0_cm": 60}))
    with pytest.raises(Exception) as err:
        e.plancher(P.PlancherInput(travees_m=[4.0], **BASE, poutrelle="inconnue"))
    assert "poutrelle" in str(err.value.detail)


def test_constantes_dans_le_referentiel():
    bael = json.loads((RACINE / "referentiels" / "bael.json").read_text(encoding="utf-8"))
    pcc = bael["planchers_corps_creux"]
    for cle in ("forfaitaire", "caquot", "dalle_compression", "fleche", "fleche_calcul", "etriers"):
        assert "_source" in pcc[cle]


def test_note_section_planchers():
    import re
    import xml.dom.minidom
    import note_calcul as nc
    r = P.plancher(P.PlancherInput(travees_m=[4.0, 4.0], **BASE))
    mince = P.plancher(P.PlancherInput(travees_m=[5.5, 5.5], **BASE))
    html = nc.construire({"projet": "Test", "planchers": [{**r, "nom": "PL1", "niveau": "R+1"}, {**mince, "nom": "PL2"}]}, {})
    assert "6.6 Planchers à corps creux" in html and "Planchers à corps creux</caption>" in html
    assert "TS Ø5 maille 20" in html and "2 HA10" in html
    for f in re.findall(r"<math .*?</math>", html, flags=re.S):
        xml.dom.minidom.parseString(f)
    assert "Plancher PL2" in html.split("Réserves.")[1]
    assert "Aucun plancher à corps creux calculé." in nc.construire({"projet": "Vide"}, {})
