"""Classeur Excel des résultats du calcul en lot."""
import io
import os
import pathlib
import sys

import pytest
from openpyxl import load_workbook

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import engine_service as e  # noqa: E402
import excel_report as x  # noqa: E402
import robot_ossature as ro  # noqa: E402

PROJET = {"projet": "Immeuble R+4 — Casablanca", "client": "SARL Exemple", "site": "Casablanca", "indice": "B"}


@pytest.fixture(scope="module")
def lot():
    o = ro.ossature_simulation()
    return e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))


def classeur(lot):
    return load_workbook(io.BytesIO(x.classeur_octets(lot, PROJET, {"nom": "BET Exemple"})))


def lignes(ws, tete=5):
    entetes = [c.value for c in ws[tete]]
    return entetes, [dict(zip(entetes, [c.value for c in r])) for r in ws.iter_rows(min_row=tete + 1) if r[0].value]


def test_feuilles_et_comptes(lot):
    wb = classeur(lot)
    assert wb.sheetnames == ["Synthèse", "Poteaux", "Poutres", "Semelles", "Voiles", "Métré poteaux", "Métré poutres", "Métré semelles", "Métré voiles", "Récapitulatif métré"]
    assert [len(lignes(wb[n])[1]) for n in ("Poteaux", "Poutres", "Semelles", "Voiles")] == [45, 60, 9, 10]
    assert wb["Poteaux"]["A1"].value == PROJET["projet"]
    assert wb["Poteaux"].freeze_panes == "B6"
    assert wb["Poteaux"].auto_filter.ref.startswith("A5:")


def test_semelles_colonnes_de_la_note_bureau(lot):
    entetes, rows = lignes(classeur(lot)["Semelles"])
    assert entetes[:11] == ["N° Semelle", "Poteau\n(cm)", "Pu total\n(MN)", "Ns total\n(MN)", "A\n(m)", "B\n(m)",
                            "H\n(m)", "Asx\n(cm²)", "Asy\n(cm²)", "Asx / ml\n(cm²/ml)", "Asy / ml\n(cm²/ml)"]
    b2 = next(r for r in rows if r["N° Semelle"] == "S B2")
    src = next(l for l in lot["semelles"] if l["nom"] == "S B2")
    # vraies valeurs numériques, unités converties (kN → MN), acier réparti par mètre
    assert b2["Ns total\n(MN)"] == pytest.approx(src["entree"]["ns_kn"] / 1000, abs=1e-3)
    assert isinstance(b2["A\n(m)"], float)
    assert b2["Asx / ml\n(cm²/ml)"] == pytest.approx(src["resultat"]["asx_cm2"] / src["resultat"]["B_m"], abs=0.01)
    assert b2["Poinçonnement"] == "OK" and b2["État"] == "Vérifié"


def test_synthese_bilan(lot):
    ws = classeur(lot)["Synthèse"]
    valeurs = {r[0].value: [c.value for c in r[1:6]] for r in ws.iter_rows() if r[0].value in ("Poteaux", "Total")}
    assert valeurs["Poteaux"] == [45, 45, 0, 0, 0]
    assert valeurs["Total"] == [124, 124, 0, 0, 0]


def test_lignes_incompletes_et_a_revoir_gardent_la_raison():
    r = e.lot(e.LotInput(
        poteaux=[{"id": "P2", "nom": "P2", "a_cm": 20, "b_cm": 20, "lf_m": 2.1, "nu_kn": 4000}],
        voiles=[{"id": "V1", "nom": "V1", "niveau": "RDC", "longueur_m": 4, "ep_cm": 18, "n_kn": None}],
    ))
    wb = classeur(r)
    _, pot = lignes(wb["Poteaux"])
    assert pot[0]["État"] == "À revoir" and "5 % B" in pot[0]["Remarques"]
    _, voi = lignes(wb["Voiles"])
    assert voi[0]["État"] == "Incomplet" and voi[0]["σmax\n(MPa)"] is None and "n_kn" in voi[0]["Remarques"]
    assert wb["Synthèse"] is not None


def test_endpoint_excel_et_telechargement(tmp_path, monkeypatch, lot):
    import report_service as rs
    monkeypatch.setattr(rs, "OUT", tmp_path)
    rep = rs.excel(rs.ExcelInput(projet="Immeuble R+4 — Casablanca", lot=lot, bureau={}))
    assert rep["fichier"].startswith("Note_de_Calcul_Immeuble_R_4_Casablanca_") and rep["fichier"].endswith(".xlsx")
    assert (tmp_path / rep["fichier"]).stat().st_size == rep["octets"]
    assert pathlib.Path(rs.excel_telecharger(rep["fichier"]).path) == tmp_path / rep["fichier"]
    from fastapi import HTTPException
    for nom in ("../secret.xlsx", "..\\secret.xlsx", "note.html", "absent.xlsx"):
        with pytest.raises(HTTPException):
            rs.excel_telecharger(nom)


# ---------- métré béton et acier ----------
def test_metre_cas_calcule_a_la_main(lot):
    import metre as M
    m = M.metre(lot)
    p = next(l for l in m["lignes"] if l["famille"] == "poteaux" and l["nom"] == "P A1" and l["niveau"] == "RDC")
    # poteau 40 × 40, h = 3,00 m : béton 0,40 × 0,40 × 3,00 = 0,480 m³
    assert p["beton_m3"] == pytest.approx(0.48)
    # 6 HA12, L = 3,00 + 50 × 0,012 = 3,60 m ; 6 × 3,60 × 0,888 = 19,18 kg
    assert (p["principal_nb"], p["principal_d_mm"], p["principal_l_m"]) == (6, 12, pytest.approx(3.6))
    assert p["principal_kg"] == pytest.approx(19.18, abs=0.01)
    assert p["ratio_kg_m3"] == pytest.approx(p["acier_kg"] / 0.48, abs=0.1)
    # voiles : 10 × 4,00 × 0,18 × 3,00 = 21,6 m³
    assert next(f for f in m["familles"] if f["famille"] == "Voiles")["beton_m3"] == pytest.approx(21.6)
    # le métré et les plans donnent le même acier
    assert m["acier_total_kg"] == pytest.approx(m["poids_nomenclature_kg"], abs=0.5)
    assert m["beton_total_m3"] == pytest.approx(sum(l["beton_m3"] for l in m["lignes"]), abs=1e-3)
    # barres commerciales : arrondi supérieur de L / 12
    for d in m["par_diametre"]:
        assert d["barres"] == -(-d["longueur_m"] // 12)
    assert sum(d["part_pct"] for d in m["par_diametre"]) == pytest.approx(100, abs=0.5)


def test_metre_element_non_verifie_sans_acier(lot):
    import metre as M
    lot2 = {**lot, "poteaux": [dict(l) for l in lot["poteaux"]]}
    lot2["poteaux"][0].update(statut="a_revoir")
    m = M.metre(lot2)
    p = m["lignes"][0]
    assert p["beton_m3"] == pytest.approx(0.48) and p["acier_kg"] is None and p["type"] is None


def test_feuilles_metre_dans_le_classeur(lot):
    wb = classeur(lot)
    assert wb.sheetnames[-5:] == ["Métré poteaux", "Métré poutres", "Métré semelles", "Métré voiles", "Récapitulatif métré"]
    for f in ("poteaux", "poutres", "semelles", "voiles"):
        entetes, rangs = lignes(wb[f"Métré {f}"])
        assert "Béton\n(m³)" in entetes and "Ratio\n(kg/m³)" in entetes and entetes[0] == "Repère"
        assert len(rangs) == len(lot[f])
    assert wb["Métré poteaux"]["A2"].value.startswith("Métré détaillé des poteaux")
    recap = [c.value for r in wb["Récapitulatif métré"].iter_rows() for c in r if c.value is not None]
    assert "Barres de 12 m" in recap and "Ratio acier / béton armé" in recap
    assert not any(isinstance(v, str) and "ALERTE" in v for v in recap)



def test_plans_un_detail_par_element():
    import plans_ferraillage as pf
    o = ro.ossature_simulation()
    lot_ = e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    _, par_type = pf.dessiner_plans(lot_, PROJET, {}, o["trame_x_m"], o["trame_y_m"])
    _, par_el = pf.dessiner_plans(lot_, PROJET, {}, o["trame_x_m"], o["trame_y_m"], par_element=True)
    assert par_el["types"] == {f: len(lot_[f]) for f in ("poteaux", "poutres", "semelles", "voiles", "dalles")}
    assert par_el["poids_total_kg"] == pytest.approx(par_type["poids_total_kg"], abs=0.5)   # même acier
    assert len(par_el["planches"]) > len(par_type["planches"])
