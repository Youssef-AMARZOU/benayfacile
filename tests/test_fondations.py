"""Fondations lues dans un modèle Robot : fûts de poteaux, plancher bas, longrines, chaînages, poutres,
dalles de fondation (cahier des besoins : US1, US2, US4).

Les faux modèles reprennent trois dispositions courantes au Maroc, sans être calqués sur un projet :
  A. semelles à −1,50 m, fûts jusqu'au plancher bas à −0,20 m (longrines non nommées), dalle sur une travée ;
  B. appuis du modèle au niveau des longrines (Z = 0), longrines nommées « LG » dans Robot ;
  C. sous-sol entouré de voiles, semelles à −3,00 m.
"""
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import robot_ossature as ro  # noqa: E402
from common import categorie_par_nom, cote_niveau, dans_polygone, aire_polygone  # noqa: E402


class Coll:
    def __init__(self, items):
        self.items = list(items)
        self.Count = len(self.items)

    def Get(self, i):
        return self.items[i - 1]


class Modele:
    """Petit constructeur de faux projet Robot (nœuds, barres, panneaux, efforts constants)."""

    def __init__(self):
        self.noeuds, self.barres, self.objets = {}, [], []

    def n(self, x, y, z):
        for k, v in self.noeuds.items():
            if v == (x, y, z):
                return k
        k = len(self.noeuds) + 1
        self.noeuds[k] = (x, y, z)
        return k

    def barre(self, a, b, section):
        num = len(self.barres) + 1
        self.barres.append(NS(Number=num, StartNode=self.n(*a), EndNode=self.n(*b), GetLabelName=lambda t, s=section: s))
        return num

    def panneau(self, num, pts, label):
        self.objets.append(NS(Number=num, Main=NS(DefPoints=Coll([NS(X=x, Y=y, Z=z) for x, y, z in pts])),
                              GetLabelName=lambda t, s=label: s))

    def projet(self, etages=None):
        struct = NS(Cases=NS(GetAll=lambda: Coll([NS(Number=1, Name="ELU"), NS(Number=2, Name="ELS")])),
                    Nodes=NS(GetAll=lambda: Coll([NS(Number=k, X=v[0], Y=v[1], Z=v[2]) for k, v in self.noeuds.items()])),
                    Bars=NS(GetAll=lambda: Coll(self.barres)), Objects=NS(GetAll=lambda: Coll(self.objets)))
        if etages is not None:
            struct.Storeys = Coll([NS(Name=a, Level=b) for a, b in etages])
        struct.Results = NS(Available=True, Bars=NS(Forces=NS(Value=lambda num, c, pos: NS(FX=-4e5, FZ=3e4, MY=5e4, MZ=1e4))),
                            Nodes=NS(Reactions=NS(Value=lambda nd, c: NS(FZ=5e5, MX=0.0, MY=0.0))))
        return NS(Structure=struct)


XS, YS = (0.0, 5.0, 10.0), (0.0, 4.5)


def cadre(m, z_bas, z_haut, section="B 30x30"):
    for x in XS:
        for y in YS:
            m.barre((x, y, z_bas), (x, y, z_haut), section)


def poutres_plancher(m, z, section="B 25x45"):
    for y in YS:
        for a, b in zip(XS, XS[1:]):
            m.barre((a, y, z), (b, y, z), section)
    for x in XS:
        m.barre((x, YS[0], z), (x, YS[1], z), section)


def modele_a():
    """Semelles −1,50 ; fûts → −0,20 (plancher bas) ; étages à 3,00 et 6,00."""
    m = Modele()
    cadre(m, -1.5, -0.2)                        # fûts
    cadre(m, -0.2, 3.0)
    cadre(m, 3.0, 6.0)
    poutres_plancher(m, -0.2)                   # liaisons entre fûts, sans nom particulier
    chainage = m.barre((2.5, 0.0, -0.2), (2.5, 4.5, -0.2), "B 20x25")     # sous un mur, hors dalle
    poutre_pb = m.barre((7.5, 0.0, -0.2), (7.5, 4.5, -0.2), "B 25x40")    # sous la dalle de la travée 5–10
    m.panneau(50, [(5, 0, -0.2), (10, 0, -0.2), (10, 4.5, -0.2), (5, 4.5, -0.2)], "DALLE 15")
    poutres_plancher(m, 3.0)
    poutres_plancher(m, 6.0)
    return m, chainage, poutre_pb


@pytest.fixture(scope="module")
def oss_a():
    m, ch, pt = modele_a()
    return ro.extraire_ossature_com(m.projet()), ch, pt


def test_futs_sous_le_plancher_bas(oss_a):
    o, _, _ = oss_a
    assert o["fondation"]["zone_futs"] is True
    assert o["niveaux"] == ["RDC", "R+1"]                          # les fûts ne sont pas un étage
    futs = [p for p in o["poteaux"] if p["role"] == "fut"]
    assert len(futs) == 6 and {p["niveau"] for p in futs} == {"Fondation"}
    assert all(p["nom"].startswith("F ") for p in futs)
    assert {p["niveau"] for p in o["poteaux"] if p["role"] == "poteau"} == {"RDC", "R+1"}
    assert any("Fûts de poteaux" in r for r in o["remarques"])


def test_niveau_superieur_de_chaque_fut(oss_a):
    o, _, _ = oss_a
    assert len(o["semelles"]) == 6                                 # sous les fûts, pas sous les poteaux du RDC
    for s in o["semelles"]:
        f = s["fut"]
        assert (f["z_bas_m"], f["z_haut_m"], f["hauteur_m"], f["modelise"]) == (-1.5, -0.2, 1.3, True)
        assert (f["a_cm"], f["b_cm"]) == (30.0, 30.0)
    assert o["fondation"]["z_dessus_futs_m"] == -0.2


def test_longrines_chainages_poutres_du_plancher_bas(oss_a):
    o, ch, pt = oss_a
    fond = {b["id"]: b for b in o["poutres"] if b["niveau"] == "Fondation"}
    assert len(fond) == 7 + 2
    liaisons = [b for b in fond.values() if b["id"] not in (f"B{ch}", f"B{pt}")]
    assert {b["categorie"] for b in liaisons} == {"longrine"}
    assert all("relie deux semelles" in b["categorie_motif"] for b in liaisons)
    assert fond[f"B{ch}"]["categorie"] == "chainage" and fond[f"B{ch}"]["nom"] == f"Ch {ch}"
    assert fond[f"B{pt}"]["categorie"] == "poutre" and "porte un panneau" in fond[f"B{pt}"]["categorie_motif"]
    etage = [b for b in o["poutres"] if b["niveau"] != "Fondation"]
    assert {b["categorie"] for b in etage} == {"poutre"}           # aucun panneau aux étages : poutres par défaut
    assert any("Niveau fondation" in r and "longrine" in r for r in o["remarques"])


def test_dalle_de_fondation(oss_a):
    o, _, _ = oss_a
    df = [d for d in o["dalles"] if d.get("role") == "fondation"]
    assert len(df) == 1 and df[0]["id"] == "DF50" and df[0]["niveau"] == "Fondation" and df[0]["h_cm"] == 15.0
    assert df[0]["g_sup_kn_m2"] is None and df[0]["q_kn_m2"] is None          # charges à saisir, jamais inventées


def modele_b():
    """Appuis à Z = 0, longrines nommées « LG 30x40 » au même niveau, étages 3,00 et 6,00."""
    m = Modele()
    cadre(m, 0.0, 3.0)
    cadre(m, 3.0, 6.0)
    poutres_plancher(m, 0.0, "LG 30x40")
    poutres_plancher(m, 3.0)
    poutres_plancher(m, 6.0)
    return m


def test_appuis_au_niveau_des_longrines_fut_non_modelise():
    o = ro.extraire_ossature_com(modele_b().projet())
    assert o["fondation"]["zone_futs"] is False and o["niveaux"] == ["RDC", "R+1"]
    assert all(p["role"] == "poteau" for p in o["poteaux"])
    for s in o["semelles"]:
        f = s["fut"]
        assert f["modelise"] is False and f["z_haut_m"] == 0.0 and f["hauteur_m"] is None
        assert "niveau d'assise" in f["source"]
    fond = [b for b in o["poutres"] if b["niveau"] == "Fondation"]
    assert fond and all(b["categorie"] == "longrine" and "LG 30x40" in b["categorie_motif"] for b in fond)


def test_longrines_nommees_decident_d_une_zone_de_futs_haute():
    """Zone de 2,00 m (plus de la moitié d'un étage de 3,00 m) : ce sont des fûts parce que le projeteur a nommé
    les poutres du plancher bas « longrines » dans Robot."""
    m = Modele()
    cadre(m, -2.2, -0.2)
    cadre(m, -0.2, 2.8)
    cadre(m, 2.8, 5.8)
    poutres_plancher(m, -0.2, "Longrine 25x40")
    poutres_plancher(m, 2.8)
    poutres_plancher(m, 5.8)
    o = ro.extraire_ossature_com(m.projet())
    assert o["fondation"]["zone_futs"] is True and "nommées longrines" in o["fondation"]["motif"]
    assert o["niveaux"] == ["RDC", "R+1"]


def test_sous_sol_entoure_de_voiles():
    m = Modele()
    cadre(m, -3.0, 0.0)
    cadre(m, 0.0, 3.0)
    cadre(m, 3.0, 6.0)
    for z in (0.0, 3.0, 6.0):
        poutres_plancher(m, z)
    m.panneau(60, [(0, 0, -3.0), (10, 0, -3.0), (10, 0, 0.0), (0, 0, 0.0)], "VOILE 20")
    o = ro.extraire_ossature_com(m.projet())
    assert o["fondation"]["zone_futs"] is False and "voiles" in o["fondation"]["motif"]
    assert o["niveaux"] == ["S-1", "RDC", "R+1"]                    # étage entièrement sous Z = 0 : sous-sol
    assert {p["niveau"] for p in o["poteaux"] if p["z_m"] == -3.0} == {"S-1"}
    assert any("Sous-sols" in r for r in o["remarques"])
    assert {s["fut"]["z_haut_m"] for s in o["semelles"]} == {-3.0}


def test_etages_robot_priment_sur_la_detection():
    m, _, _ = modele_a()
    o = ro.extraire_ossature_com(m.projet(etages=[("Vide sanitaire", -1.5), ("Rez-de-chaussée", -0.2), ("Étage 1", 3.0)]))
    assert o["fondation"]["zone_futs"] is False                    # Robot y définit un étage : ce n'est pas un fût
    assert o["niveaux"][:3] == ["Vide sanitaire", "Rez-de-chaussée", "Étage 1"]


# ---------- fonctions pures ----------
@pytest.mark.parametrize("nom,attendu", [
    ("LG 30x40", "longrine"), ("Longrine_25x40", "longrine"), ("LONG 30*40", "longrine"), ("lg25x40", "longrine"),
    ("CH 20x25", "chainage"), ("Chaînage 25", "chainage"), ("CH25X25", "chainage"),
    ("PT 25x50", "poutre"), ("Poutre 30x60", "poutre"),
    ("B 25x50", None), ("P 30x30", None), ("BA 25 x 60", None), ("", None),
])
def test_categorie_par_nom(nom, attendu):
    r = categorie_par_nom(nom)
    assert (r[0] if r else None) == attendu


def test_categorie_poutre_regles():
    assert ro.categorie_poutre("B 25x40", "", True, True, None)[0] == "longrine"
    assert ro.categorie_poutre("B 25x40", "", True, False, True)[0] == "poutre"
    assert ro.categorie_poutre("B 25x40", "", True, False, False)[0] == "chainage"
    assert ro.categorie_poutre("B 25x40", "", False, False, None)[0] == "poutre"
    assert ro.categorie_poutre("B 25x40", "", False, False, False)[0] == "chainage"
    assert ro.categorie_poutre("CH 20x20", "", True, True, None)[0] == "chainage"          # le nom prime
    assert ro.categorie_poutre("B 25x40", "Poutre BA", True, True, None)[0] == "longrine"  # type Robot par défaut ignoré
    assert ro.categorie_poutre("B 25x40", "Longrine", False, False, True)[0] == "longrine"  # type personnalisé


def test_zone_futs_regles():
    assert ro.zone_futs([-0.2, 3.0, 6.0], -1.5)[0] is True                   # 1,30 ≤ ½ × 3,20
    assert ro.zone_futs([3.0, 6.0], 0.0)[0] is False                          # RDC porté par les semelles
    assert ro.zone_futs([0.0, 3.0], 0.0)[0] is False                          # appuis au plancher bas : rien dessous
    assert ro.zone_futs([-0.2], -1.5)[0] is False                             # un seul plancher : étage
    assert ro.zone_futs([-0.2, 3.0], -1.5, voiles=[(-1.5, -0.2)])[0] is False
    assert ro.zone_futs([-0.2, 3.0], -1.5, etages=[("VS", -1.5)])[0] is False


def test_noms_des_niveaux_sous_sols():
    assert ro.noms_des_niveaux([-6.0, -3.0, 0.0, 3.0, 6.0]) == ["S-2", "S-1", "RDC", "R+1", "R+2"]
    assert ro.noms_des_niveaux([-1.0, 3.2, 6.1]) == ["RDC", "R+1", "R+2"]   # étage à cheval sur Z = 0 : RDC
    assert ro.noms_des_niveaux([0.0, 3.0]) == ["RDC", "R+1"]


def test_outils_geometriques():
    carre = [(0, 0), (4, 0), (4, 3), (0, 3)]
    assert dans_polygone(2, 1.5, carre) and dans_polygone(4, 1.0, carre) and not dans_polygone(5, 1, carre)
    en_l = [(0, 0), (10, 0), (10, 5), (4.5, 5), (4.5, 2.5), (0, 2.5)]
    assert not dans_polygone(2, 4, en_l) and dans_polygone(7, 4, en_l)
    assert aire_polygone(carre) == 12.0 and aire_polygone(en_l) == pytest.approx(10 * 5 - 4.5 * 2.5)
    assert cote_niveau(-0.2) == "−0,20" and cote_niveau(0) == "±0,00" and cote_niveau(3) == "+3,00"
    assert cote_niveau(-0.2, ascii_seul=True) == "-0,20"


# ---------- US1 : dalle pleine de fondation dans le calcul en lot ----------
import engine_service as eng  # noqa: E402
import dalles as dl  # noqa: E402

DF = {"id": "DF50", "nom": "DF 50", "niveau": "Fondation", "role": "fondation",
      "xmin_m": 5.0, "xmax_m": 10.0, "ymin_m": 0.0, "ymax_m": 4.5, "h_cm": 15.0,
      "g_sup_kn_m2": 1.5, "q_kn_m2": 2.5}


def lot_dalles(*dalles_):
    return eng.lot(eng.LotInput(dalles=list(dalles_)))


def test_dalle_de_fondation_calculee_a_la_main():
    """lx = 4,50, ly = 5,00 (contour du panneau), h = 15 cm, g = 25 × 0,15 + 1,5 = 5,25 kN/m², q = 2,5 kN/m² :
    pu = 1,35 × 5,25 + 1,5 × 2,5 = 10,8375 kN/m² ; ρ = 0,9 → μx = 1 / (8 (1 + 2,4 × 0,729)) = 0,045461 ;
    M0x = 0,045461 × 10,8375 × 4,5² = 9,977 kN·m/m ; isostatique : Mtx = M0x ;
    d = 0,15 − 0,050 − 0,005 = 0,095 m (enrobage des fondations 50 mm) ; μ = 9,977e-3 / (0,095² × 14,17) = 0,0780 ;
    α = 0,1017 ; Z = 0,0911 m ; As = 9,977e-3 / (0,0911 × 434,8) = 2,52 cm²/m."""
    l = lot_dalles(DF)["dalles"][0]
    r = l["resultat"]
    assert (l["entree"]["lx_m"], l["entree"]["ly_m"]) == (4.5, 5.0)
    assert r["charges"]["pu_kn_m2"] == pytest.approx(10.8375, abs=1e-3)
    assert r["m0x_knm"] == pytest.approx(9.98, abs=0.01)
    xt = r["resultats"]["x_travee"]
    assert xt["d_m"] == pytest.approx(0.095, abs=1e-6)
    assert xt["as_elu_cm2_m"] == pytest.approx(2.52, abs=0.01)
    assert any("isostatique" in h for h in r["hypotheses"]) and any("longrines" in h for h in r["hypotheses"])
    assert all(a["statut"] == "OK" for a in r["audit"])
    assert l["statut"] in ("verifie", "a_revoir") and lot_dalles(DF)["resume"]["total"] == 1


def test_treillis_soude_section_a_la_main_et_controle():
    # TS Ø6 maille 15 : π × 0,6² / 4 × 100 / 15 = 1,885 cm²/m
    assert dl.section_treillis_cm2_m(6, 15) == pytest.approx(1.885, abs=1e-3)
    faible = lot_dalles({**DF, "armature": "treillis", "ts_diametre_mm": 6, "ts_maille_cm": 15})["dalles"][0]
    assert faible["statut"] == "a_revoir" and faible["resultat"]["treillis"]["ok"] is False
    assert any("Ax treillis" in p for p in faible["problemes"])            # 1,89 < 2,52 cm²/m : signalé
    fort = lot_dalles({**DF, "armature": "treillis", "ts_diametre_mm": 10, "ts_maille_cm": 15})["dalles"][0]
    t = fort["resultat"]["treillis"]
    r = fort["resultat"]["resultats"]
    assert t["as_cm2_m"] == pytest.approx(5.24, abs=0.01)
    assert t["ok"] == (t["as_cm2_m"] >= r["x_travee"]["as_retenue_cm2_m"] and t["as_cm2_m"] >= r["y_travee"]["as_retenue_cm2_m"]
                       and 15 <= min(fort["resultat"]["espacements_max_cm"].values()))


def test_dalle_sans_charges_incomplete_et_dallage_signale():
    sans = lot_dalles({**DF, "g_sup_kn_m2": None})["dalles"][0]
    assert sans["statut"] == "incomplet" and "g_sup_kn_m2" in sans["problemes"][0]
    ts_incomplet = lot_dalles({**DF, "armature": "treillis", "ts_diametre_mm": 6})["dalles"][0]
    assert ts_incomplet["statut"] == "incomplet" and "ts_maille_cm" in ts_incomplet["problemes"][0]
    dallage = lot_dalles({**DF, "appui": "terre_plein", "g_sup_kn_m2": None, "q_kn_m2": None,
                          "armature": "treillis", "ts_diametre_mm": 6, "ts_maille_cm": 15})["dalles"][0]
    assert dallage["statut"] == "a_revoir" and "DTU 13.3" in dallage["problemes"][0]
    assert dallage["resultat"]["treillis"]["as_cm2_m"] == 1.88          # 1,88496 arrondi au centième
    sans_geo = lot_dalles({"id": "X", "h_cm": 15, "g_sup_kn_m2": 1, "q_kn_m2": 1})["dalles"][0]
    assert sans_geo["statut"] == "incomplet" and "dimensions" in sans_geo["problemes"][0]


def test_lot_sans_dalle_inchange():
    import robot_ossature as ro_
    o = ro_.ossature_simulation()
    r = eng.lot(eng.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    assert r["dalles"] == [] and r["resume"]["total"] == 124


# ---------- plans, métré, classeur et note sur le modèle A (US1 à US4) ----------
import io as _io  # noqa: E402

import plans_ferraillage as pf  # noqa: E402
import metre as mt  # noqa: E402

COUCHES = [{"nom": "Béton de propreté", "ep_cm": 5}, {"nom": "Film polyane", "ep_cm": None},
           {"nom": "Hérisson", "ep_cm": 20}]


def lot_modele_a(**dalle):
    m, _, _ = modele_a()
    o = ro.extraire_ossature_com(m.projet())
    for d in o["dalles"]:
        if d.get("role") == "fondation":
            d.update(g_sup_kn_m2=1.5, q_kn_m2=2.5, couches=COUCHES, **dalle)
    return o, eng.lot(eng.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles", "dalles")}))


@pytest.fixture(scope="module")
def dossier_a():
    o, lot = lot_modele_a(h_cm=20, continuite="intermediaire", armature="treillis", ts_diametre_mm=10, ts_maille_cm=15)
    doc, res = pf.dessiner_plans(lot, {"projet": "Fondations"}, {}, o["trame_x_m"], o["trame_y_m"], dalles=o["dalles"])
    return o, lot, doc, res


def test_repères_par_categorie(dossier_a):
    _, lot, _, _ = dossier_a
    types, _ = pf.grouper(lot)
    codes = {t["code"][:2] if t["code"][:2] in ("Pt", "Ch", "DF") else t["code"][0] for liste in types.values() for t in liste}
    assert {"L", "Pt", "S", "DF"} <= codes          # le chaînage de ce modèle n'est pas vérifié : pas de type
    for t in types["poutres"]:
        cat = t["rep"]["entree"]["categorie"]
        assert t["code"].startswith({"longrine": "L", "chainage": "Ch", "poutre": "Pt"}[cat])


def test_plan_de_fondation_et_coupe_du_dallage(dossier_a):
    _, lot, doc, res = dossier_a
    assert res["planches"][:2] == ["Plan de fondation", "Coupe transversale du dallage de fondation"]
    assert res["planches_fondation"] == 1 and res["coupes_dallage"] == 1
    assert not doc.audit().has_errors
    msp = doc.modelspace()
    calques = {e.dxf.layer for e in msp}
    assert {"LONGRINES", "CHAINAGES", "SEMELLES", "NIVEAUX", "COUCHES"} <= calques     # représentations distinctes
    textes = [t.dxf.text for t in msp.query("TEXT")]
    assert sum(t == "N.S. fût -0,20" for t in textes) == 6                             # une cote par fût (US4)
    assert "Fûts de poteaux — niveau supérieur (N.S.)" in textes
    assert any(t.startswith("DF1 — dalle pleine portée par les longrines — e = 20 cm") for t in textes)
    assert "Hérisson — 20 cm" in textes and "Film polyane" in textes and "sol support" in textes      # couches (US3)
    assert any(t.startswith("Nappe inférieure : TS %%c10 maille 15") for t in textes)
    assert any(t.startswith("N.S. fûts -0,20") for t in textes) and any("Plancher bas (Z modèle) -0,20" in t for t in textes)
    assert any(t.startswith("Légende") for t in textes)
    assert any(t.startswith("N.S. fût -0,20 (fût 1.30 m)") for t in textes)            # coupe de la semelle (US4)


def test_metre_rubriques_et_dalle_a_la_main(dossier_a):
    _, lot, _, _ = dossier_a
    m = mt.metre(lot)
    rubriques = {f["famille"]: f for f in m["familles"]}
    assert {"Fûts", "Poteaux", "Longrines", "Chaînages", "Poutres", "Semelles", "Dalles de fondation"} <= set(rubriques)
    df = next(x for x in m["lignes"] if x["famille"] == "dalles")
    assert df["beton_m3"] == pytest.approx(5.0 * 4.5 * 0.20, abs=1e-4)                  # 4,500 m³
    fut = next(x for x in m["lignes"] if x["rubrique"] == "Fûts")
    assert fut["beton_m3"] == pytest.approx(0.30 * 0.30 * 1.30, abs=1e-4)               # 0,117 m³
    if lot["dalles"][0]["statut"] == "verifie":
        assert df["acier_kg"] and any("recouvrements" in h for h in m["hypotheses"])
    assert abs(m["acier_total_kg"] - m["poids_nomenclature_kg"]) <= 0.5


def test_classeur_et_note(dossier_a):
    from openpyxl import load_workbook
    import excel_report as xr
    import report_service as rs
    _, lot, _, _ = dossier_a
    wb = load_workbook(_io.BytesIO(xr.classeur_octets(lot, {"projet": "Fondations"}, {})))
    assert "Dalles" in wb.sheetnames and "Métré dalles" in wb.sheetnames
    entetes = [c.value for c in wb["Poutres"][5]]
    assert "Catégorie" in entetes
    pot = [dict(l["resultat"], nom=l["nom"], niveau=l["niveau"], nu_kn=l["entree"]["nu_kn"], role=l["entree"]["role"])
           for l in lot["poteaux"] if l.get("resultat")]
    pou = [dict(l["resultat"], nom=l["nom"], niveau=l["niveau"], mu_knm=l["entree"]["mu_knm"], categorie=l["entree"]["categorie"])
           for l in lot["poutres"] if l.get("resultat")]
    sem = [dict(l["resultat"], nom=l["nom"], fut=l["entree"]["fut"]) for l in lot["semelles"] if l.get("resultat")]
    dal = [dict(l["resultat"], nom=l["nom"], niveau=l["niveau"], role="fondation") for l in lot["dalles"] if l.get("resultat")]
    h = rs.build_note(rs.NoteInput(projet="Fondations", lot=lot, poteaux=pot, poutres=pou, semelles_isolees=sem, dalles=dal,
                                   bureau={"nom": "BET"}))
    assert "Les fûts (F)" in h and "longrines (L)" in h and "chaînages (Ch)" in h
    assert "N.S. fût" in h and "−0,20" in h
    assert "Les dalles de fondation (DF)" in h
    assert "Longrines" in h and "Dalles de fondation" in h                              # quantités par rubrique


def test_plan_de_fondation_decoupe_pour_un_batiment_long():
    o = ro.ossature_simulation(trame_x=[6.0 * i for i in range(31)], trame_y=(0, 5, 10), nb_niveaux=1)
    lot = eng.lot(eng.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    doc, res = pf.dessiner_plans(lot, {"projet": "Long"}, {}, o["trame_x_m"], o["trame_y_m"])
    parties = [t for t in res["planches"] if t.startswith("Plan de fondation")]
    assert len(parties) == res["planches_fondation"] >= 2 and parties[0].endswith("partie 1/%d" % len(parties))
    textes = [t.dxf.text for t in doc.modelspace().query("TEXT")]
    # chaque semelle est cotée ; celles d'une file de coupe figurent sur les deux parties, comme en coffrage
    assert sum(t.startswith("N.S. fût ±0,00") for t in textes) >= len(o["semelles"])
