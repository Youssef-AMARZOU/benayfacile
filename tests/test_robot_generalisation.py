"""Lecture d'un modèle Robot quelconque : niveaux, trame, fondations et éléments non courants.

Le faux modèle reprend des situations réelles que le portique de démonstration n'a pas : hauteurs d'étage
inégales, nœud à mi-hauteur d'un poteau, palier d'escalier, fondation décalée, contreventement incliné,
toiture en pente, panneau en L, étages nommés dans Robot.
"""
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import robot_ossature as ro  # noqa: E402
from common import rang_niveau, trier_niveaux  # noqa: E402


class Coll:
    def __init__(self, items):
        self.items = list(items)
        self.Count = len(self.items)

    def Get(self, i):
        return self.items[i - 1]


Z = (0.0, 3.2, 6.1, 9.0)          # hauteurs d'étage 3,20 / 2,90 / 2,90 m
XS, YS = (0.0, 4.5, 10.0), (0.0, 5.0)


def modele(etages=None):
    noeuds, barres, objets = {}, [], []

    def n(x, y, z):
        for k, v in noeuds.items():
            if v == (x, y, z):
                return k
        k = len(noeuds) + 1
        noeuds[k] = (x, y, z)
        return k

    def barre(a, b, section):
        barres.append(NS(Number=len(barres) + 1, StartNode=a, EndNode=b, GetLabelName=lambda t, s=section: s))
        return len(barres)

    for x in XS:
        for y in YS:
            if (x, y) == (0.0, 0.0):            # poteau coupé par un nœud à mi-hauteur au RDC
                m = n(x, y, 1.6)
                barre(n(x, y, 0.0), m, "P 30x30")
                barre(m, n(x, y, Z[1]), "P 30x30")
            elif (x, y) == (10.0, 5.0):          # fondation plus basse (terrain en pente)
                barre(n(x, y, -1.0), n(x, y, Z[1]), "P 30x30")
            else:
                barre(n(x, y, 0.0), n(x, y, Z[1]), "P 30x30")
            for k in (1, 2):
                barre(n(x, y, Z[k]), n(x, y, Z[k + 1]), "P 30x30")
    for z in Z[1:]:
        for y in YS:
            for x1, x2 in zip(XS, XS[1:]):
                barre(n(x1, y, z), n(x2, y, z), "P 25x45")
        for x in XS:
            barre(n(x, YS[0], z), n(x, YS[1], z), "P 25x45")
    palier = barre(n(0.0, 0.0, 1.6), n(2.3, 0.0, 1.6), "P 20x30")             # palier d'escalier
    diag = barre(n(4.5, 0.0, 0.0), n(10.0, 0.0, Z[1]), "TUBE 100x5")          # contreventement

    def obj(num, pts, label):
        objets.append(NS(Number=num, Main=NS(DefPoints=Coll([NS(X=x, Y=y, Z=z) for x, y, z in pts])),
                         GetLabelName=lambda t, s=label: s))

    obj(100, [(0, 0, Z[1]), (10, 0, Z[1]), (10, 5, Z[1]), (4.5, 5, Z[1]), (4.5, 2.5, Z[1]), (0, 2.5, Z[1])], "DALLE 16")
    obj(101, [(0, 0, Z[2]), (4.5, 0, Z[2]), (4.5, 5, Z[2]), (0, 5, Z[2])], "DALLE 16")
    obj(102, [(10, 0, 0), (10, 5, 0), (10, 5, Z[1]), (10, 0, Z[1])], "VOILE 20")
    obj(103, [(0, 0, Z[3]), (10, 0, Z[3]), (10, 5, Z[3] + 1.8), (0, 5, Z[3] + 1.8)], "TOITURE 14")   # pente 36 %

    def valeur(num, cas, pos):
        return NS(FX=-5e5, FZ=2e4, MY=4e4, MZ=1e4)

    struct = NS(Cases=NS(GetAll=lambda: Coll([NS(Number=1, Name="ELU"), NS(Number=2, Name="ELS")])),
                Nodes=NS(GetAll=lambda: Coll([NS(Number=k, X=v[0], Y=v[1], Z=v[2]) for k, v in noeuds.items()])),
                Bars=NS(GetAll=lambda: Coll(barres)), Objects=NS(GetAll=lambda: Coll(objets)))
    if etages is not None:
        struct.Storeys = Coll([NS(Name=a, Level=b) for a, b in etages])
    struct.Results = NS(Available=True, Bars=NS(Forces=NS(Value=valeur)),
                        Nodes=NS(Reactions=NS(Value=lambda nd, c: NS(FZ=6e5, MX=0.0, MY=0.0))))
    return NS(Structure=struct), palier, diag


@pytest.fixture(scope="module")
def oss():
    projet, palier, diag = modele()
    return ro.extraire_ossature_com(projet), palier, diag


def test_niveaux_par_planchers_pas_par_noeuds(oss):
    o, palier, _ = oss
    # le nœud à 1,60 m (mi-hauteur, palier) ne crée pas d'étage ; la fondation à −1,00 m non plus
    assert o["niveaux"] == ["RDC", "R+1", "R+2"]
    assert o["altitudes_m"] == [-1.0, 3.2, 6.1, 9.0]
    assert {p["niveau"] for p in o["poteaux"] if p["z_m"] < 3.0} == {"RDC"}
    assert next(b for b in o["poutres"] if b["id"] == f"B{palier}")["niveau"] == "Fondation"
    assert any("altitude(s) secondaire(s)" in r for r in o["remarques"])


def test_trame_depuis_les_poteaux_pas_depuis_les_noeuds(oss):
    o, _, _ = oss
    assert o["trame_x_m"] == list(XS) and o["trame_y_m"] == list(YS)      # 2,30 (bout du palier) n'est pas une file


def test_semelles_sous_les_pieds_reels(oss):
    o, _, _ = oss
    assert len(o["semelles"]) == len(XS) * len(YS)                      # une par file, pas sous le tronçon haut
    basse = next(s for s in o["semelles"] if (s["x_m"], s["y_m"]) == (10.0, 5.0))
    assert basse["z_m"] == -1.0


def test_elements_non_courants_gardes_et_signales(oss):
    o, _, diag = oss
    genres = {a["genre"] for a in o["autres"]}
    assert genres == {"barre inclinée", "panneau incliné"}
    assert any(a["id"] == f"I{diag}" for a in o["autres"])
    assert len(o["voiles"]) == 1                                         # la toiture en pente n'est pas un voile
    assert any("barre(s) inclinée(s)" in r for r in o["remarques"])


def test_dalle_non_rectangulaire_signalee(oss):
    o, _, _ = oss
    d = next(d for d in o["dalles"] if d["id"] == "D100")
    assert d["rectangulaire"] is False and len(d["contour_m"]) == 6
    assert next(d for d in o["dalles"] if d["id"] == "D101")["rectangulaire"] is True
    assert any("non rectangulaire" in r for r in o["remarques"])


def test_noms_d_etages_robot_repris():
    projet, _, _ = modele(etages=[("Sous-sol", -1.0), ("Étage 1", 3.2), ("Étage 2", 6.1)])
    o = ro.extraire_ossature_com(projet)
    assert o["niveaux"] == ["Sous-sol", "Étage 1", "Étage 2"]
    assert {p["niveau"] for p in o["poteaux"]} == {"Sous-sol", "Étage 1", "Étage 2"}
    assert any("repris des étages définis dans Robot" in r for r in o["remarques"])


def test_classer_panneau():
    assert ro.classer_panneau([(0, 0, 3), (5, 0, 3), (5, 4, 3), (0, 4, 3)]) == "horizontal"
    assert ro.classer_panneau([(0, 0, 0), (5, 0, 0), (5, 0, 3), (0, 0, 3)]) == "vertical"
    assert ro.classer_panneau([(0, 0, 0), (10, 0, 0), (10, 5, 1.8), (0, 5, 1.8)]) == "incline"
    # grand panneau presque plat (pente 0,5 %) : horizontal ; petite rampe raide : inclinée
    assert ro.classer_panneau([(0, 0, 3), (40, 0, 3), (40, 20, 3.1), (0, 20, 3.1)]) == "horizontal"


@pytest.mark.parametrize("noms", [
    ["Terrasse", "Étage 2", "1er étage", "RDC", "Sous-sol 1", "SS2", "Fondation"],
    ["N+3", "R-1", "Rez-de-chaussée", "Niveau 1", "Mezzanine"],
])
def test_libelles_de_niveaux_usuels(noms):
    rangs = [rang_niveau(n) for n in noms]
    assert all(r[0] == 0 for r in rangs), noms                           # aucun libellé usuel « inconnu »


def test_tri_par_altitude_quand_connue():
    assert trier_niveaux(["Haut", "Bas", "Fondation"], {"Haut": 6.0, "Bas": 0.0}) == ["Fondation", "Bas", "Haut"]
    assert trier_niveaux(["R+1", "RDC", "X"], {"R+1": 3.0}) == ["RDC", "R+1", "X"]  # altitude partielle : libellés


def test_chaine_complete_sur_le_modele_irregulier():
    """Calcul, plans (contour réel du panneau en L), métré et note Word sur le même modèle."""
    import engine_service as e
    import metre as M
    import note_docx as nd
    import plans_ferraillage as pf
    import report_service as rs
    projet, _, _ = modele(etages=[("Sous-sol", -1.0), ("Étage 1", 3.2), ("Étage 2", 6.1)])
    o = ro.extraire_ossature_com(projet)
    for v in o["voiles"]:
        v.update(n_kn=300, m_knm=50, v_kn=40)            # efforts réduits des voiles : saisis par l'ingénieur
    lot = e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    assert lot["resume"]["erreur"] == 0
    doc, res = pf.dessiner_plans(lot, {"projet": "Irrégulier"}, {}, o["trame_x_m"], o["trame_y_m"], dalles=o["dalles"])
    assert res["niveaux_dessines"] == ["Sous-sol", "Étage 1", "Étage 2"]      # ordre des altitudes
    assert res["planches"][0] == "Plan de fondation" and res["planches_fondation"] == 1       # le niveau Fondation
    polys = [p for p in doc.modelspace().query("LWPOLYLINE") if p.dxf.layer == "BETON_PROPRETE"]
    assert any(len(p) == 6 for p in polys)                                                # panneau en L dessiné tel quel
    m = M.metre(lot)
    assert m["sans_beton"] == [] and m["beton_total_m3"] > 0
    pot = [dict(l["resultat"], nom=l["nom"], niveau=l["niveau"], nu_kn=l["entree"]["nu_kn"]) for l in lot["poteaux"]]
    html = rs.build_note(rs.NoteInput(projet="Irrégulier", lot=lot, poteaux=pot, bureau={"nom": "BET"}))
    _, stats = nd.docx_depuis_html(html)
    assert stats["tableaux"] > 0 and stats["titres"] > 0
