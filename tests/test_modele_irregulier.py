"""Modèle irrégulier, sans rapport avec l'exemple R+4 : 27 niveaux, trame inégale de 28 files en Y
(repères au-delà de Z), poteaux manquants, sections qui changent avec la hauteur, éléments mélangés.
Vérifie que plans et métré ne dépendent pas de la régularité de l'exemple."""
import pathlib
import random
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import engine_service as e  # noqa: E402
import metre as M  # noqa: E402
import plans_ferraillage as pf  # noqa: E402
from common import indice_file, lettre_file, rang_niveau  # noqa: E402
from robot_ossature import nom_niveau  # noqa: E402

NIVEAUX = 27                                   # RDC à R+26, comme le modèle du testeur
TX = [0.0, 4.2, 9.35, 13.0]                     # portées inégales
TY = [round(sum([3.1, 4.65, 2.9, 5.2][k % 4] for k in range(j)), 2) for j in range(28)]


def section(niv: int) -> float:
    return 50.0 if niv < 6 else 40.0 if niv < 15 else 30.0


@pytest.fixture(scope="module")
def modele():
    rnd = random.Random(7)
    points = [(i, j) for i in range(len(TX)) for j in range(len(TY)) if rnd.random() > 0.15]   # poteaux manquants
    poteaux, poutres = [], []
    for niv in range(NIVEAUX):
        a = section(niv)
        for (i, j) in points:
            poteaux.append({"id": f"P{i}-{j}-{niv}", "nom": f"P {lettre_file(j)}{i + 1}", "niveau": nom_niveau(niv),
                            "axe": f"{lettre_file(j)}{i + 1}", "x_m": TX[i], "y_m": TY[j],
                            "a_cm": a, "b_cm": a, "hauteur_m": 3.06, "lf_m": 2.14,
                            "nu_kn": round(60.0 * (NIVEAUX - niv) + 40, 1), "mx_knm": 8.0, "my_knm": 4.0})
        pts = set(points)
        for (i, j) in points:
            if (i + 1, j) in pts:      # poutre suivant X vers le poteau voisin
                l = TX[i + 1] - TX[i]
                poutres.append({"id": f"B{i}-{j}-{niv}", "nom": f"Pt {niv}-{i}-{j}", "niveau": nom_niveau(niv),
                                "x1_m": TX[i], "y1_m": TY[j], "x2_m": TX[i + 1], "y2_m": TY[j],
                                "b_cm": 30.0, "h_cm": 45.0 if l < 5 else 55.0, "portee_m": l,
                                "mu_knm": round(14.0 * l * l / 10, 1), "ms_knm": round(10.0 * l * l / 10, 1),
                                "vu_kn": round(14.0 * l * 0.58, 1)})
    rnd.shuffle(poteaux)          # ordre quelconque, comme les numéros de barres d'un vrai modèle
    rnd.shuffle(poutres)
    lot = e.lot(e.LotInput(poteaux=poteaux, poutres=poutres))
    return lot, points


def test_repere_de_files_au_dela_de_z():
    assert [lettre_file(j) for j in (0, 25, 26, 27, 51, 52)] == ["A", "Z", "AA", "AB", "AZ", "BA"]
    assert all(indice_file(lettre_file(j)) == j for j in range(200))
    assert pf._xy_axe("AB3", TX, TY) == (TX[2], TY[27])


def test_niveaux_tries_de_bas_en_haut():
    noms = ["R+10", "RDC", "Fondation", "R+2", "S-1", "R+1", "Terrasse", "S-2"]
    assert sorted(noms, key=rang_niveau) == ["Fondation", "S-2", "S-1", "RDC", "R+1", "R+2", "R+10", "Terrasse"]


def test_plans_modele_irregulier(modele):
    lot, points = modele
    doc, res = pf.dessiner_plans(lot, {"projet": "Irrégulier"}, {}, TX, TY)
    # chaque niveau couvert une fois, de bas en haut malgré l'ordre mélangé
    assert res["niveaux_dessines"] == [nom_niveau(i) for i in range(NIVEAUX)]
    coffrages = [t for t in res["planches"] if t.startswith("Coffrage")]
    # les étages de même section et même ferraillage sont regroupés : bien moins de planches que de niveaux
    assert 3 <= len(coffrages) < NIVEAUX
    assert not doc.audit().has_errors
    textes = {t.dxf.text for t in doc.modelspace().query("TEXT")}
    assert {"AA", "AB"} <= textes                                    # repères de files au-delà de Z dessinés
    assert not any(t in textes for t in ("[", "\\", "]"))            # plus de caractères après Z
    assert len(doc.layouts.names_in_taborder()) == len(res["planches"]) + 1


def test_metre_modele_irregulier(modele):
    lot, points = modele
    m = M.metre(lot)
    # béton des poteaux : Σ a² × 3,06 m sur tous les niveaux
    attendu = sum((section(n) / 100) ** 2 * 3.06 * len(points) for n in range(NIVEAUX))
    assert next(f for f in m["familles"] if f["famille"] == "Poteaux")["beton_m3"] == pytest.approx(attendu, rel=1e-4)
    assert m["acier_total_kg"] == pytest.approx(m["poids_nomenclature_kg"], abs=0.5)
    assert all(l["beton_m3"] for l in m["lignes"])


def test_batiment_long_decoupe_au_1_100(modele):
    """105 m de long : plutôt qu'un plan illisible au 1:500, des parties au 1:100 coupées sur les files."""
    lot, points = modele
    doc, res = pf.dessiner_plans(lot, {"projet": "Irrégulier"}, {}, TX, TY)
    parties = [t for t in res["planches"] if t.startswith("Coffrage plancher haut RDC à R+5")]
    assert len(parties) >= 2 and parties[0].endswith(f"partie 1/{len(parties)}")
    textes = [t.dxf.text for t in doc.modelspace().query("TEXT")]
    sous_titres = [t for t in textes if "poutres en tireté" in t]
    assert sous_titres and all("échelle 1:100" in t for t in sous_titres)
    # chaque partie garde les repères d'origine : la dernière file AB n'est dessinée que sur la dernière partie
    assert textes.count("AB") >= 1 and "A" in textes
    assert any(t.startswith("Files 1-4 / ") for t in textes)
