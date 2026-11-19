"""Import d'un modèle depuis Excel (alternative à Robot)."""
import io
import pathlib
import sys

import pytest
from openpyxl import Workbook, load_workbook

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import engine_service as e  # noqa: E402
import import_excel as ix  # noqa: E402
import plans_ferraillage as pf  # noqa: E402
import robot_ossature as ro  # noqa: E402


def remplir(oss: dict, trame=True) -> bytes:
    """Remplit le classeur modèle avec une ossature, comme le ferait un utilisateur."""
    wb = load_workbook(io.BytesIO(ix.creer_modele()))
    for cle, colonnes in ix.FEUILLES.items():
        ws = wb[ix.TITRES[cle]]
        for el in oss[cle]:
            ws.append([el.get(k) for k, *_ in colonnes])
    if trame:
        ws = wb[ix.TRAME]
        for i in range(max(len(oss["trame_x_m"]), len(oss["trame_y_m"]))):
            ws.append([oss["trame_x_m"][i] if i < len(oss["trame_x_m"]) else None,
                       oss["trame_y_m"][i] if i < len(oss["trame_y_m"]) else None])
    flux = io.BytesIO(); wb.save(flux)
    return flux.getvalue()


def lot(oss):
    return e.lot(e.LotInput(**{k: oss[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))


def test_modele_vierge():
    wb = load_workbook(io.BytesIO(ix.creer_modele()))
    assert wb.sheetnames == ["Lisez-moi", "Poteaux", "Poutres", "Semelles", "Voiles", "Trame"]
    assert [c.value for c in wb["Poteaux"][1]][:4] == ["Nom", "Niveau", "Axe (ex. B2)", "a (cm)"]
    assert wb["Poteaux"]["A1"].font.bold and not wb["Poteaux"]["B1"].font.bold      # obligatoire en gras
    assert wb["Poutres"].data_validations.dataValidation                            # nombres ≥ 0


def test_aller_retour_meme_resultat_que_la_lecture_directe():
    """L'exemple R+4 recopié dans le modèle Excel donne exactement le même calcul."""
    direct = ro.ossature_simulation()
    importe = ix.lire_classeur(remplir(direct))
    assert importe["resume"] == direct["resume"] and importe["remarques"] == []
    assert importe["trame_x_m"] == [0, 6, 12] and importe["trame_y_m"] == [0, 5, 10]
    a, b = lot(direct), lot(importe)
    assert b["resume"] == a["resume"] == {"total": 124, "verifie": 124, "a_revoir": 0, "incomplet": 0, "erreur": 0}
    for fam in ("poteaux", "poutres", "semelles", "voiles"):
        assert [l["resultat"] for l in b[fam]] == [l["resultat"] for l in a[fam]]
    # et les plans DXF complets, plan de fondation compris
    doc, res = pf.dessiner_plans(b, {"projet": "Import"}, {}, importe["trame_x_m"], importe["trame_y_m"])
    assert res["planches"][0] == "Plan de fondation" and res["elements_dessines"] == 124
    assert not doc.audit().has_errors


def test_entetes_tolerants_et_nombres_au_format_francais():
    wb = Workbook(); ws = wb.active; ws.title = "POTEAUX"
    ws.append(["Repère", "NU (kN)", "a", "B (cm)", "Hauteur", "Mx"])
    ws.append(["P1", "1 711,2", 40, 40, 3, -51.3])                     # texte français, moment négatif
    flux = io.BytesIO(); wb.save(flux)
    oss = ix.lire_classeur(flux.getvalue())
    p = oss["poteaux"][0]
    assert (p["nom"], p["nu_kn"], p["a_cm"], p["b_cm"], p["lf_m"], p["mx_knm"]) == ("P1", 1711.2, 40, 40, 2.1, 51.3)
    assert lot(oss)["resume"]["verifie"] == 1


def test_valeur_illisible_signalee_et_jamais_devinee():
    wb = load_workbook(io.BytesIO(ix.creer_modele()))
    ws = wb["Poteaux"]
    ws.append(["P1", "RDC", "A1", 30, 30, 3, None, "beaucoup", None, 0, 0])   # Nu illisible
    ws.append(["P2", "RDC", "A2", 30, 30, 3, None, 900, None, 0, 0])
    flux = io.BytesIO(); wb.save(flux)
    oss = ix.lire_classeur(flux.getvalue())
    assert oss["remarques"][0] == "Poteaux, ligne 2 : « Nu ELU (kN) » n'est pas un nombre ('beaucoup')."
    r = lot(oss)
    assert [l["statut"] for l in r["poteaux"]] == ["incomplet", "verifie"]
    assert "Pas de feuille Trame" not in " ".join(oss["remarques"])          # aucune semelle : pas d'alerte


def test_colonne_obligatoire_absente():
    wb = Workbook(); ws = wb.active; ws.title = "Poutres"
    ws.append(["Nom", "b (cm)", "Mu ELU (kN.m)"]); ws.append(["Pt1", 25, 120])
    flux = io.BytesIO(); wb.save(flux)
    oss = ix.lire_classeur(flux.getvalue())
    assert oss["remarques"] == ["Poutres : colonne(s) obligatoire(s) absente(s) : h (cm)."]
    assert lot(oss)["poutres"][0]["statut"] == "incomplet"


@pytest.mark.parametrize("contenu, attendu", [(b"pas un classeur", "pas un classeur Excel"), (None, "le modèle vide")])
def test_fichiers_inexploitables(contenu, attendu):
    octets = contenu if contenu is not None else ix.creer_modele()
    with pytest.raises(ValueError, match=attendu):
        ix.lire_classeur(octets)


def test_endpoints_modele_et_import():
    from fastapi.testclient import TestClient
    import robot_service as rs
    c = TestClient(rs.app)
    m = c.get("/modele-excel")
    assert m.status_code == 200 and "Modele_Benayfacile.xlsx" in m.headers["content-disposition"]
    r = c.post("/import-excel", files={"fichier": ("Residence Al Amal.xlsx", remplir(ro.ossature_simulation()))}).json()
    assert r["mode"] == "excel" and r["nom"] == "Residence Al Amal" and r["ossature"]["resume"]["poteaux"] == 45
    mauvais = c.post("/import-excel", files={"fichier": ("plan.dxf", b"x")}).json()
    assert mauvais["mode"] == "indisponible" and "(.xlsx)" in mauvais["notes"][0]


def test_classeur_d_un_autre_format_explique():
    wb = Workbook(); wb.active.title = "Métré"; wb.create_sheet("Récap")
    wb.active.append(["Désignation", "Quantité"]); wb.active.append(["Béton B25", 42])
    flux = io.BytesIO(); wb.save(flux)
    with pytest.raises(ValueError, match=r"feuilles trouvées : Métré, Récap ; attendues : Poteaux"):
        ix.lire_classeur(flux.getvalue())


def test_modele_vide_cite_les_feuilles_a_remplir():
    with pytest.raises(ValueError, match="sous les en-têtes des feuilles Poteaux, Poutres, Semelles, Voiles"):
        ix.lire_classeur(ix.creer_modele())
