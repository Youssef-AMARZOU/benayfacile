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
    assert wb.sheetnames == ["Synthèse", "Poteaux", "Poutres", "Semelles", "Voiles"]
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
