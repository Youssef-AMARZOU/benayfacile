"""Projet Robot : lecture de l'ossature (sans Robot) et calcul en lot."""
import pathlib
import sys
from types import SimpleNamespace as NS

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import engine_service as e  # noqa: E402
import robot_ossature as ro  # noqa: E402


# ---------- fonctions de lecture ----------
@pytest.mark.parametrize("nom, attendu", [
    ("B 30x50", (30.0, 50.0)), ("R30*30", (30.0, 30.0)), ("BA 25 x 60", (25.0, 60.0)),
    ("300x500", (30.0, 50.0)), ("POT 40×40", (40.0, 40.0)), ("IPE 200", None), ("", None),
])
def test_dimensions_section(nom, attendu):
    assert ro.dimensions_section(nom) == attendu


@pytest.mark.parametrize("nom, attendu", [("Voile 18", 18.0), ("ep=0.20", 20.0), ("BA200", 20.0), ("TH", None)])
def test_epaisseur_depuis_nom(nom, attendu):
    assert ro.epaisseur_depuis_nom(nom) == attendu


def test_classer_barre():
    assert ro.classer_barre((0, 0, 0), (0, 0, 3)) == "poteau"
    assert ro.classer_barre((0, 0, 3), (6, 0, 3)) == "poutre"
    assert ro.classer_barre((0, 0, 0), (3, 0, 3)) is None      # barre inclinée
    assert ro.classer_barre((1, 1, 1), (1, 1, 1)) is None      # longueur nulle


def test_niveaux_et_axes():
    niv = ro.niveaux_depuis_z([0.0, 3.01, 2.99, 6.0, 0.02])
    assert niv == [0.0, 2.99, 6.0]
    assert ro.indice_niveau(3.0, niv) == 1
    assert ro.libelle_axe(6.0, 5.0, [0, 6, 12], [0, 5, 10]) == "B2"


def test_choisir_cas():
    cas = [(1, "G"), (2, "Q"), (7, "ELU 1.35G+1.5Q"), (8, "ELS G+Q")]
    assert ro.choisir_cas(cas, None, None) == (7, 8)
    assert ro.choisir_cas(cas, 3, None) == (3, 8)                 # numéro imposé
    assert ro.choisir_cas([(1, "G")], None, None) == (None, None)


# ---------- simulation : descente de charges ----------
def test_simulation_comptes_et_descente_de_charges():
    o = ro.ossature_simulation()
    assert o["resume"] == {"poteaux": 45, "poutres": 60, "semelles": 9, "voiles": 10}
    centre = {p["niveau"]: p["nu_kn"] for p in o["poteaux"] if p["axe"] == "B2"}
    # l'effort croît vers la base, la terrasse (R+4) porte le moins
    valeurs = [centre[n] for n in ["R+4", "R+3", "R+2", "R+1", "RDC"]]
    assert valeurs == sorted(valeurs)
    # poteau central RDC : 5 planchers × 30 m² × pu (≈ 11,0 kN/m², terrasse ≈ 10,95) + poids propres
    assert 1600 < centre["RDC"] < 1800
    # la semelle B2 reprend le pied du poteau B2 du RDC
    s = next(s for s in o["semelles"] if s["axe"] == "B2")
    assert s["nu_kn"] == centre["RDC"]


# ---------- calcul en lot ----------
def test_lot_simulation_tout_verifie():
    o = ro.ossature_simulation()
    r = e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    assert r["resume"]["total"] == 124
    assert r["resume"]["verifie"] == 124
    p = next(l for l in r["poteaux"] if l["nom"] == "P B2" and l["niveau"] == "RDC")
    assert 0 < p["resultat"]["nu_rapport"] < 1


def test_lot_signale_les_elements_incomplets_et_hors_domaine():
    r = e.lot(e.LotInput(
        poteaux=[
            {"id": "P1", "nom": "P1", "a_cm": None, "b_cm": 30, "lf_m": 2.1, "nu_kn": 900},   # section non lue
            {"id": "P2", "nom": "P2", "a_cm": 20, "b_cm": 20, "lf_m": 2.1, "nu_kn": 4000},    # surchargé
        ],
        voiles=[{"id": "V1", "nom": "V1", "longueur_m": 4, "ep_cm": 18, "n_kn": None}],    # efforts à saisir
        poutres=[{"id": "B1", "nom": "B1", "b_cm": 5, "h_cm": 50, "mu_knm": 100}],          # b hors domaine
    ))
    statuts = {l["id"]: l["statut"] for fam in ("poteaux", "voiles", "poutres") for l in r[fam]}
    assert statuts == {"P1": "incomplet", "P2": "a_revoir", "V1": "incomplet", "B1": "erreur"}
    p2 = next(l for l in r["poteaux"] if l["id"] == "P2")
    assert any("5 % B" in pb for pb in p2["problemes"])
    assert r["resume"] == {"total": 4, "verifie": 0, "a_revoir": 1, "incomplet": 2, "erreur": 1}


# ---------- extraction COM, sur un faux projet Robot ----------
class Coll:
    def __init__(self, items):
        self.items = list(items)
        self.Count = len(self.items)

    def Get(self, i):
        return self.items[i - 1]


def faux_projet(cas=None, forces_par_cas=None):
    """Faux projet calqué sur RobotOM : les résultats sont sous Structure.Results ;
    le projet lui-même n'a pas d'attribut Results (comme IRobotProject)."""
    noeuds = [NS(Number=1, X=0.0, Y=0.0, Z=0.0), NS(Number=2, X=0.0, Y=0.0, Z=3.0),
              NS(Number=3, X=6.0, Y=0.0, Z=3.0), NS(Number=4, X=6.0, Y=0.0, Z=0.0)]

    def barre(num, a, b, section):
        return NS(Number=num, StartNode=a, EndNode=b, GetLabelName=lambda t, s=section: s)

    barres = [barre(1, 1, 2, "B 40x40"), barre(2, 4, 3, "B 40x40"), barre(3, 2, 3, "B 25x50")]
    forces = {1: dict(FX=-1.2e6, FZ=1e4, MY=3e4, MZ=1e4), 2: dict(FX=-1.0e6, FZ=1e4, MY=2e4, MZ=0.0),
              3: dict(FX=0.0, FZ=9e4, MY=1.2e5, MZ=0.0)}

    coef = forces_par_cas or {7: 1.0, 8: 1 / 1.4}

    def valeur_barre(num, cas, pos):
        return NS(**{c: v * coef[cas] for c, v in forces[num].items()})

    def reaction(noeud, cas):
        return NS(FZ=1.2e6 * coef[cas], MX=0.0, MY=0.0)

    struct = NS(
        Cases=NS(GetAll=lambda: Coll(cas or [NS(Number=1, Name="G"), NS(Number=7, Name="ELU"), NS(Number=8, Name="ELS")])),
        Nodes=NS(GetAll=lambda: Coll(noeuds)),
        Bars=NS(GetAll=lambda: Coll(barres)),
        Objects=NS(GetAll=lambda: Coll([])),
    )
    struct.Results = NS(Available=True, Bars=NS(Forces=NS(Value=valeur_barre)), Nodes=NS(Reactions=NS(Value=reaction)))
    return NS(Structure=struct)


def test_extraction_com_portique():
    o = ro.extraire_ossature_com(faux_projet())
    assert o["cas_elu"] == 7 and o["cas_els"] == 8
    assert o["resume"] == {"poteaux": 2, "poutres": 1, "semelles": 2, "voiles": 0}
    p1 = next(p for p in o["poteaux"] if p["id"] == "P1")
    assert (p1["a_cm"], p1["b_cm"], p1["nu_kn"], p1["lf_m"]) == (40.0, 40.0, 1200.0, 2.1)
    assert p1["ns_kn"] == pytest.approx(1200 / 1.4, abs=0.1)
    poutre = o["poutres"][0]
    assert (poutre["b_cm"], poutre["h_cm"], poutre["mu_knm"], poutre["vu_kn"], poutre["portee_m"]) == (25.0, 50.0, 120.0, 90.0, 6.0)
    s = o["semelles"][0]
    assert s["nu_kn"] == 1200.0 and s["a_poteau_cm"] == 40.0
    # le lot calcule directement ce qui a été lu
    r = e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    assert r["resume"]["incomplet"] == 0 and r["resume"]["erreur"] == 0


def test_resultats_lus_sous_structure_comme_robotom():
    """IRobotProject n'a pas d'attribut Results : tout passe par Structure.Results."""
    projet = faux_projet()
    assert not hasattr(projet, "Results")
    o = ro.extraire_ossature_com(projet)
    assert o["poteaux"][0]["nu_kn"] == 1200.0 and not any("non lu" in r for r in o["remarques"])


def test_combinaisons_reconstituees_depuis_g_et_q():
    """Projet sans combinaisons : ELU = 1,35 G + 1,5 Q et ELS = G + Q, cas par cas."""
    cas = [NS(Number=1, Name="PERM1", Nature=0, Type=0), NS(Number=2, Name="EXPL1", Nature=1, Type=0)]
    o = ro.extraire_ossature_com(faux_projet(cas=cas, forces_par_cas={1: 0.5, 2: 0.2}))
    p1 = next(p for p in o["poteaux"] if p["id"] == "P1")
    assert p1["nu_kn"] == pytest.approx(1200 * (1.35 * 0.5 + 1.5 * 0.2), abs=0.1)
    assert p1["ns_kn"] == pytest.approx(1200 * 0.7, abs=0.1)
    assert any("1,35 G + 1,5 Q reconstituée" in r for r in o["remarques"])


def test_combinaisons_en_anglais_et_cas_inconnus():
    cas = [(1, "DL1", None, 0), (2, "LL1", None, 0), (5, "ULS", None, 1), (6, "SLS", None, 1)]
    assert ro.combinaisons_de_calcul(cas)[:2] == ([(5, 1.0)], [(6, 1.0)])
    elu, els, rem = ro.combinaisons_de_calcul([(1, "Vent", 2, 0)])
    assert elu is None and els is None and len(rem) == 2


def test_erreurs_de_lecture_regroupees():
    projet = faux_projet()
    projet.Structure.Results.Bars.Forces.Value = lambda *a: (_ for _ in ()).throw(RuntimeError("pas de résultats"))
    o = ro.extraire_ossature_com(projet)
    lignes = [r for r in o["remarques"] if r.startswith("Efforts des barres")]
    assert len(lignes) == 1 and "3 élément(s)" in lignes[0]


def test_poteau_section_trop_petite_est_signalee():
    # 20×20 sous 4000 kN : As calculé ≫ 5 % B (A.8.1,22), même si Nu/Nu,lim < 1 avec 16 HA32
    r = e.poteau(e.PoteauInput(a_cm=20, b_cm=20, lf_m=2.1, nu_kn=4000))
    assert r["section_suffisante"] is False and "A.8.1,22" in r["warn"]
    assert e.poteau(e.PoteauInput(a_cm=40, b_cm=40, lf_m=2.1, nu_kn=1700))["warn"] is None


def test_lot_erreurs_de_saisie_en_clair():
    r = e.lot(e.LotInput(poutres=[{"id": "B1", "nom": "B1", "b_cm": 5, "h_cm": 50, "mu_knm": 100}]))
    assert r["poutres"][0]["problemes"] == ["b_cm doit être supérieur à 10"]


def test_modele_demo_seulement_sur_demande(monkeypatch):
    import robot_service as rs
    monkeypatch.setattr(rs, "robot_disponible", lambda: (False, "Robot absent"))
    sans = rs.model()
    assert sans["mode"] == "indisponible" and "ossature" not in sans      # jamais de données d'exemple en silence
    avec = rs.model(demo=True)
    assert avec["mode"] == "simulation" and avec["ossature"]["resume"]["poteaux"] == 45


def test_lecture_com_via_projet_ouvert(monkeypatch):
    """Lecture d'un projet Robot ouvert : robot.Project (RobotOM), sans démarrer Robot."""
    import robot_service as rs
    projet = faux_projet()
    projet.Name, projet.IsActive = "Résidence test", True
    robot = NS(Name="Autodesk Robot", Project=projet)
    appels = []
    monkeypatch.setattr(rs, "connecter_robot", lambda lancer=False: appels.append(lancer) or robot)
    m = rs.model()
    assert m["mode"] == "robot" and m["nom"] == "Résidence test"
    assert m["ossature"]["resume"]["poteaux"] == 2 and m["ossature"]["cas_elu"] == 7
    assert "ELU" in m["combinaisons"]
    assert appels[0] is False                     # la vérification ne lance jamais Robot


def test_lecture_com_sans_projet_ouvert(monkeypatch):
    import robot_service as rs
    robot = NS(Name="Autodesk Robot", Project=NS(IsActive=False))
    monkeypatch.setattr(rs, "connecter_robot", lambda lancer=False: robot)
    m = rs.model()
    assert m["mode"] == "indisponible" and "aucun projet" in m["notes"][0]


def _robot_avec_fichier(resultats_disponibles):
    """Faux Robot : Project.Open et CalcEngine.Calculate enregistrent leurs appels."""
    appels = []
    projet = faux_projet()
    projet.Name, projet.IsActive = "Residence.rtd", True
    projet.Open = lambda chemin: appels.append(("open", chemin))
    projet.CalcEngine = NS(Calculate=lambda: appels.append(("calcul",)) or 0)
    projet.Structure.Results.Available = resultats_disponibles
    return NS(Name="Autodesk Robot", Project=projet), appels


def test_ouvrir_rtd_lance_l_analyse_si_resultats_absents(tmp_path, monkeypatch):
    import robot_service as rs
    f = tmp_path / "Residence.rtd"; f.write_bytes(b"rtd")
    robot, appels = _robot_avec_fichier(resultats_disponibles=False)
    monkeypatch.setattr(rs, "connecter_robot", lambda lancer=False: robot)
    m = rs.ouvrir(rs.OuvrirInput(chemin=str(f)))
    assert m["mode"] == "robot" and m["ossature"]["resume"]["poteaux"] == 2
    assert appels == [("open", str(f.resolve())), ("calcul",)]
    assert m["notes"][0] == "Projet ouvert dans Robot : Residence.rtd."
    assert robot.Visible == 1                         # Robot reste visible (licence, messages)


def test_ouvrir_rtd_sans_recalcul_si_resultats_presents(tmp_path, monkeypatch):
    import robot_service as rs
    f = tmp_path / "Residence.rtd"; f.write_bytes(b"rtd")
    robot, appels = _robot_avec_fichier(resultats_disponibles=True)
    monkeypatch.setattr(rs, "connecter_robot", lambda lancer=False: robot)
    rs.ouvrir(rs.OuvrirInput(chemin=str(f)))
    assert appels == [("open", str(f.resolve()))]


def test_ouvrir_refuse_un_mauvais_fichier(tmp_path, monkeypatch):
    import robot_service as rs
    monkeypatch.setattr(rs, "connecter_robot", lambda lancer=False: (_ for _ in ()).throw(AssertionError("Robot ne doit pas être appelé")))
    autre = tmp_path / "plan.dxf"; autre.write_text("x")
    for chemin, attendu in ((str(autre), "(.rtd)"), (str(tmp_path / "absent.rtd"), "introuvable")):
        m = rs.ouvrir(rs.OuvrirInput(chemin=chemin))
        assert m["mode"] == "indisponible" and attendu in m["notes"][0]


def test_robot_absent_a_l_ouverture(tmp_path, monkeypatch):
    import robot_service as rs
    f = tmp_path / "Residence.rtd"; f.write_bytes(b"rtd")
    def pas_de_robot(lancer=False):
        raise OSError("Classe non enregistrée")
    monkeypatch.setattr(rs, "connecter_robot", pas_de_robot)
    m = rs.ouvrir(rs.OuvrirInput(chemin=str(f)))
    assert m["mode"] == "indisponible" and "installé avec sa licence" in m["notes"][0]
