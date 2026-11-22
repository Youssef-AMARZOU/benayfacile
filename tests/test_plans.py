"""Plans de ferraillage DXF : types, dispositions constructives, nomenclature, dessin."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import engine_service as e  # noqa: E402
import plans_ferraillage as pf  # noqa: E402
import robot_ossature as ro  # noqa: E402

PROJET = {"projet": "Immeuble R+4", "client": "SARL Exemple", "site": "Casablanca", "indice": "A"}


@pytest.fixture(scope="module")
def simulation():
    o = ro.ossature_simulation()
    lot = e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    return o, lot


# ---------- dispositions constructives ----------
def test_poids_lineique():
    assert pf.poids_ml(8) == pytest.approx(0.395, abs=1e-3)
    assert pf.poids_ml(12) == pytest.approx(0.888, abs=1e-3)
    assert pf.poids_ml(25) == pytest.approx(3.853, abs=1e-3)


def test_cadres_poteau_bael_et_rps():
    c = pf.cadres_poteau(40, 40, 3.0, 12)
    # courant : min(15×12 mm, 40 cm, 40+10 cm) = 18 cm ; critique : min(8×12 mm, 40/4, 15) = 9 cm
    assert (c["diametre_mm"], c["st_courant_m"], c["st_critique_m"]) == (8, 0.18, 0.09)
    assert c["lc_m"] == 0.5                         # max(300/6, 40, 45 cm)
    assert pf.cadres_poteau(50, 50, 3.0, 25)["diametre_mm"] == 10   # Øt ≥ Øl/3


def test_cadres_poutre_passent_en_ha10_si_ha8_trop_serres():
    faible = pf.cadres_poutre(25, 50, 6.0, 0.45, 12, 3.0)
    assert faible["diametre_mm"] == 8 and faible["st_courant_m"] == 0.33
    fort = pf.cadres_poutre(25, 50, 6.0, 0.45, 25, 16.0)          # HA8 donnerait 6 cm
    assert fort["diametre_mm"] == 10 and fort["st_courant_m"] >= 0.09
    assert fort["st_critique_m"] <= min(0.50 / 4, 12 * 0.025, 0.30)


# ---------- types et nomenclature ----------
def test_types_regroupent_les_elements_identiques(simulation):
    _, lot = simulation
    n = pf.nomenclature(lot)
    assert {f: len(t) for f, t in n["types"].items()} == {"poteaux": 2, "poutres": 4, "semelles": 3, "voiles": 2, "dalles": 0}
    assert sum(len(t["lignes"]) for liste in n["types"].values() for t in liste) == 124
    assert n["ecartes"] == []
    s3 = next(t for t in n["types"]["semelles"] if t["elements"] == ["S B2"])   # semelle centrale, seule de son type
    assert s3["attentes"] == pf._barres(next(l for l in lot["poteaux"] if l["nom"] == "P B2"
                                             and l["niveau"] == "RDC")["resultat"]["ferraillage"])


def test_nomenclature_poids_coherents(simulation):
    _, lot = simulation
    n = pf.nomenclature(lot)
    for l in n["lignes"]:
        assert l["nombre"] > 0 and l["longueur_m"] > 0
        assert l["longueur_totale_m"] == pytest.approx(l["nombre"] * l["longueur_m"] * l["nb_elements"], abs=0.05)
        assert l["poids_kg"] == pytest.approx(l["longueur_totale_m"] * pf.poids_ml(l["diametre_mm"]), abs=0.1)
    assert n["poids_total_kg"] == pytest.approx(sum(n["par_diametre_kg"].values()), abs=0.5)
    # ordre de grandeur : quelques tonnes pour l'ossature d'un R+4 de 120 m² (hors dalles)
    assert 4000 < n["poids_total_kg"] < 15000


def test_potelets_de_rive_au_moins_4_ha12(simulation):
    _, lot = simulation
    n = pf.nomenclature(lot)
    for t in n["types"]["voiles"]:
        assert t["rive_barres"][0] >= 4 and t["rive_barres"][1] >= 12


def test_elements_non_verifies_ne_sont_pas_dessines(simulation):
    _, lot = simulation
    lot2 = {**lot, "poteaux": [dict(l) for l in lot["poteaux"]]}
    lot2["poteaux"][0].update(statut="a_revoir", problemes=["Nu/Nu,lim = 1.2 > 1"])
    types, ecartes = pf.grouper(lot2)
    assert sum(len(t["lignes"]) for t in types["poteaux"]) == 44
    assert ecartes == [{"famille": "poteaux", "nom": lot2["poteaux"][0]["nom"], "niveau": lot2["poteaux"][0]["niveau"],
                        "statut": "a_revoir", "raison": "Nu/Nu,lim = 1.2 > 1"}]


# ---------- dessin ----------
def test_dessin_complet_valide(simulation):
    o, lot = simulation
    doc, res = pf.dessiner_plans(lot, PROJET, {"nom": "BET"}, o["trame_x_m"], o["trame_y_m"])
    assert [t for t in res["planches"] if not t.startswith("Coffrage")] == [
        "Plan de fondation", "Ferraillage des semelles", "Ferraillage des poteaux",
        "Ferraillage des poutres", "Ferraillage des voiles", "Nomenclature des aciers"]
    assert res["elements_dessines"] == 124 and res["elements_non_dessines"] == 0
    assert not doc.audit().has_errors
    msp = doc.modelspace()
    textes = [t.dxf.text for t in msp.query("TEXT")]
    assert not any("Ø" in t for t in textes)                      # symbole AutoCAD %%c, pas de glyphe Unicode
    assert any("%%c" in t for t in textes)
    calques = {ent.dxf.layer for ent in msp}
    assert {"AXES", "COFFRAGE", "ACIER_LONG", "CADRES", "COTATION", "CARTOUCHE", "NOMENCLATURE"} <= calques
    # chaque planche A1 a son cartouche : le titre de la planche y figure
    for titre in res["planches"]:
        assert textes.count(titre) >= 2                          # titre de planche + cartouche
    # une présentation (onglet AutoCAD) par planche, dans l'ordre, avec une fenêtre sur sa feuille
    onglets = doc.layouts.names_in_taborder()
    assert onglets == ["Model"] + [f"{i:02d} {t}" for i, t in enumerate(res["planches"], start=1)]
    for i, nom in enumerate(onglets[1:]):
        vues = [v for v in doc.layouts.get(nom).viewports() if v.dxf.status != 1]
        assert len(vues) == 1
        assert vues[0].dxf.view_center_point.x == pytest.approx(i * (pf.A1[0] + pf.ESPACE_FEUILLES) + pf.A1[0] / 2)


def test_nom_presentation_sans_caracteres_interdits():
    nom = pf.nom_presentation(3, 'Coupe A/B : "test"' + "x" * 80)
    assert nom.startswith("03 Coupe A B") and len(nom) <= 63
    assert not set('<>/\\":;?*|=`') & set(nom)


def test_ecartes_affiches_sur_la_planche(simulation):
    o, lot = simulation
    lot2 = {**lot, "poteaux": [dict(l) for l in lot["poteaux"]]}
    lot2["poteaux"][0].update(statut="a_revoir", problemes=["x"])
    doc, res = pf.dessiner_plans(lot2, PROJET, {}, o["trame_x_m"], o["trame_y_m"])
    textes = [t.dxf.text for t in doc.modelspace().query("TEXT")]
    assert "Non dessinés : à reprendre avant exécution" in textes
    assert res["elements_non_dessines"] == 1


def test_endpoint_plans_et_telechargement(tmp_path, monkeypatch, simulation):
    import dxf_service as ds
    from fastapi import HTTPException
    o, lot = simulation
    monkeypatch.setattr(ds, "OUT", tmp_path)
    rep = ds.plans(ds.PlansInput(projet="Immeuble R+4 — Casablanca", lot=lot,
                                 trame_x_m=o["trame_x_m"], trame_y_m=o["trame_y_m"], bureau={"nom": "BET"}))
    assert rep["fichier"].startswith("Plans_Ferraillage_Immeuble_R_4_Casablanca_") and rep["fichier"].endswith(".dxf")
    assert (tmp_path / rep["fichier"]).stat().st_size == rep["octets"]
    assert pathlib.Path(ds.download(rep["fichier"]).path) == tmp_path / rep["fichier"]
    for nom in ("..\\..\\secret.dxf", "../x.dxf", "note.html", "absent.dxf"):
        with pytest.raises(HTTPException):
            ds.download(nom)


# ---------- plans de coffrage par niveau ----------
def test_positions_sur_la_trame():
    tx, ty = [0, 6, 12], [0, 5, 10]
    assert pf._xy_axe("B2", tx, ty) == (6.0, 5.0)          # lettre = file Y, chiffre = file X
    assert pf._xy_axe("D1", tx, ty) is None                 # hors trame : jamais deviné
    assert pf._segment({"nom": "Pt A1-A2"}, tx, ty) == (0.0, 0.0, 6.0, 0.0)
    assert pf._segment({"nom": "Pt 12"}, tx, ty) is None
    assert pf._segment({"x1_m": 1, "y1_m": 2, "x2_m": 3, "y2_m": 2, "nom": "Pt 12"}, tx, ty) == (1, 2, 3, 2)
    assert ro.niveau_plancher(0) == "Fondation" and ro.niveau_plancher(1) == "RDC" and ro.niveau_plancher(3) == "R+2"


def test_coffrage_un_plan_par_niveau_regroupe(simulation):
    o, lot = simulation
    doc, res = pf.dessiner_plans(lot, PROJET, {}, o["trame_x_m"], o["trame_y_m"])
    assert res["niveaux_dessines"] == ["RDC", "R+1", "R+2", "R+3", "R+4"]       # chaque niveau, une seule fois
    coffrages = [t for t in res["planches"] if t.startswith("Coffrage")]
    assert len(coffrages) == res["planches_coffrage"] >= 1
    assert res["planches"][0] == "Plan de fondation" and res["planches"][1].startswith("Coffrage")
    assert not doc.audit().has_errors
    textes = [t.dxf.text for t in doc.modelspace().query("TEXT")]
    assert any(t.startswith("V1 ép. 18") for t in textes)                      # voiles de pignon placés


def test_regroupement_des_niveaux_identiques():
    p = {"genre": "poteau", "x": 0.0, "y": 0.0, "a": 30, "b": 30, "code": "P1", "verifie": True}
    q = {**p, "a": 40, "b": 40, "code": "P2"}
    from collections import OrderedDict
    g = pf.regrouper_niveaux(OrderedDict([("RDC", [q]), ("R+1", [p]), ("R+2", [dict(p)]), ("R+3", []), ("R+4", [p])]))
    assert [n for n, _ in g] == [["RDC"], ["R+1", "R+2"], ["R+4"]]               # un niveau vide coupe le groupe
    assert pf.titre_coffrage(["R+1", "R+2"]) == "Coffrage plancher haut R+1 à R+2"
    assert pf.titre_coffrage(["Fondation"]) == "Coffrage niveau fondation"


def test_elements_sans_position_signales_et_dalles_dessinees(simulation):
    o, lot = simulation
    lot2 = {**lot, "poutres": [dict(l) for l in lot["poutres"]]}
    l0 = lot2["poutres"][0]
    l0["entree"] = {k: v for k, v in l0["entree"].items() if not k.startswith(("x1", "y1", "x2", "y2"))} | {"nom": "Pt 999"}
    dalles = [{"nom": "D 7", "niveau": "R+1", "type": "dalle", "h_cm": 16,
               "xmin_m": 0, "xmax_m": 6, "ymin_m": 0, "ymax_m": 5}]
    doc, res = pf.dessiner_plans(lot2, PROJET, {}, o["trame_x_m"], o["trame_y_m"], dalles)
    textes = [t.dxf.text for t in doc.modelspace().query("TEXT")]
    assert any("— position inconnue" in t for t in textes)
    assert "D 7 — dalle h = 16 cm" in textes


def test_altitudes_pour_la_vue_3d():
    """Chaque élément de la simulation porte son altitude : poteau et voile en pied, poutre au plancher qu'elle porte."""
    o = ro.ossature_simulation()
    h = 3.0
    for p in o["poteaux"]:
        niv = 0 if p["niveau"] == "RDC" else int(p["niveau"][2:])
        assert p["z_m"] == pytest.approx(niv * h)
    for b in o["poutres"]:
        niv = 0 if b["niveau"] == "RDC" else int(b["niveau"][2:])
        assert b["z_m"] == pytest.approx((niv + 1) * h)
    assert all(v["z_m"] is not None and v["hauteur_m"] == h for v in o["voiles"])
    assert all(s["z_m"] == 0.0 for s in o["semelles"])
