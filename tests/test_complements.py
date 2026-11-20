"""Compléments : détection des logiciels externes et liens officiels."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import complements as c  # noqa: E402


def test_detection_par_cles_de_registre():
    presentes = {("HKCR", r"Excel.Application\CLSID"), ("HKCR", r".dxf\OpenWithProgids")}
    r = {x["id"]: x for x in c.detecter(existe=lambda ruche, cle: (ruche, cle) in presentes)}
    assert r["robot"]["installe"] is False and "AEC Collection" in r["robot"]["conseil"]
    assert r["tableur"]["installe"] is True and r["tableur"]["trouves"] == ["Microsoft Excel"] and r["tableur"]["conseil"] is None
    assert r["dxf"]["trouves"] == ["Programme associé aux fichiers .dxf"]


def test_liens_officiels_en_https_seulement():
    for x in c.detecter(existe=lambda *_: False):
        assert x["liens"] and all(l["url"].startswith("https://") for l in x["liens"])
    piege = [{**c.BESOINS[0], "liens": [("Faux", "http://exemple.invalid/robot.exe")]}]
    assert c.detecter(piege, existe=lambda *_: False)[0]["liens"] == []


def test_route_complements():
    import robot_service as rs
    ids = [x["id"] for x in rs.complements()["complements"]]
    assert ids == ["robot", "tableur", "dxf"]
