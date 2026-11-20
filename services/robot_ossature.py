"""Ossature d'un modèle Robot : poteaux, poutres, semelles, voiles avec leurs efforts.

Deux sources produisent le même format (« ossature ») :
  - `ossature_simulation()` : bâtiment R+4 de démonstration, efforts par descente
    de charges (surfaces d'influence) — sert sans Robot et dans les tests ;
  - `extraire_ossature_com(projet)` : lecture d'un projet Robot ouvert via l'API
    COM RobotOM (géométrie, sections, efforts ELU / ELS, réactions d'appui).

Le classement des barres (poteau / poutre), la détection des niveaux et la
lecture des sections sont de simples fonctions Python, testées sans Robot.

Format d'un élément (unités : cm, m, kN, kN.m) :
  poteau  : id, nom, niveau, a_cm, b_cm, hauteur_m, lf_m, nu_kn, ns_kn, mx_knm, my_knm
  poutre  : id, nom, niveau, b_cm, h_cm, portee_m, mu_knm, ms_knm, vu_kn
  semelle : id, nom, axe, a_poteau_cm, b_poteau_cm, ns_kn, nu_kn, mx_knm, my_knm
  voile   : id, nom, niveau, longueur_m, ep_cm, n_kn, m_knm, v_kn
Un champ absent ou None signifie « non extrait » : l'élément porte alors une
remarque et le calcul en lot le signale au lieu d'inventer une valeur.
"""
from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Sequence, Tuple

# ───────────────────────── outils géométriques ─────────────────────────

TOL_Z = 0.05          # m : deux altitudes plus proches sont le même niveau
VERTICALE = 0.95      # |dz|/L au-delà : barre verticale (poteau)
HORIZONTALE = 0.10    # |dz|/L en deçà : barre horizontale (poutre)
COEF_LF = 0.7         # lf = 0,7·l0 (poteau encastré en pied, bâtiment à étages, BAEL B.8.3,31)


def nom_niveau(i: int) -> str:
    return "RDC" if i == 0 else f"R+{i}"


def niveaux_depuis_z(altitudes: Sequence[float], tol: float = TOL_Z) -> List[float]:
    """Altitudes distinctes triées (regroupement à `tol` près)."""
    zs: List[float] = []
    for z in sorted(altitudes):
        if not zs or z - zs[-1] > tol:
            zs.append(z)
    return zs


def indice_niveau(z: float, niveaux: Sequence[float], tol: float = TOL_Z) -> int:
    for i, zn in enumerate(niveaux):
        if abs(z - zn) <= tol:
            return i
    return min(range(len(niveaux)), key=lambda i: abs(niveaux[i] - z))


def classer_barre(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> Optional[str]:
    """'poteau', 'poutre' ou None (barre inclinée : ni l'un ni l'autre)."""
    dx, dy, dz = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
    longueur = math.sqrt(dx * dx + dy * dy + dz * dz)
    if longueur < 1e-6:
        return None
    r = abs(dz) / longueur
    if r >= VERTICALE:
        return "poteau"
    if r <= HORIZONTALE:
        return "poutre"
    return None


_DIMS = re.compile(r"(\d+(?:[.,]\d+)?)\s*[xX×*]\s*(\d+(?:[.,]\d+)?)")


def dimensions_section(nom: str) -> Optional[Tuple[float, float]]:
    """Lit « B 30x50 », « R30*30 », « BA 25 x 60 »… → (b, h) en cm.

    Les noms Robot en mm (« 300x500 ») sont ramenés en cm.
    """
    if not nom:
        return None
    m = _DIMS.search(nom)
    if not m:
        return None
    b, h = (float(v.replace(",", ".")) for v in m.groups())
    if b > 150 or h > 300:          # vraisemblablement des mm
        b, h = b / 10.0, h / 10.0
    return round(b, 1), round(h, 1)


def epaisseur_depuis_nom(nom: str) -> Optional[float]:
    """« Voile 18 », « BA20 », « ep=0.20 » → épaisseur en cm."""
    if not nom:
        return None
    m = re.search(r"(\d+(?:[.,]\d+)?)", nom)
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    if v < 1:            # en m
        v *= 100
    elif v > 100:        # en mm
        v /= 10
    return round(v, 1) if 8 <= v <= 100 else None


def libelle_axe(x: float, y: float, trame_x: Sequence[float], trame_y: Sequence[float]) -> str:
    """Repère de file « B2 » (lettres en Y, chiffres en X) si le point est sur la trame."""
    ix = min(range(len(trame_x)), key=lambda i: abs(trame_x[i] - x)) if trame_x else 0
    iy = min(range(len(trame_y)), key=lambda i: abs(trame_y[i] - y)) if trame_y else 0
    return f"{chr(65 + iy)}{ix + 1}"


def _resume(oss: dict) -> dict:
    return {k: len(oss.get(k, [])) for k in ("poteaux", "poutres", "semelles", "voiles")}


# ───────────────────────── simulation R+4 ─────────────────────────

# Hypothèses de charges de la simulation (habitation, BAEL / DTU usuels)
G_PLANCHER = 6.5      # kN/m² : dalle 16 cm (4,0) + revêtements (1,5) + cloisons (1,0)
Q_PLANCHER = 1.5      # kN/m² : habitation
G_TERRASSE = 7.0      # kN/m² : dalle + forme de pente + étanchéité
Q_TERRASSE = 1.0      # kN/m² : terrasse inaccessible
GAMMA_BA = 25.0       # kN/m³


def _pu(g: float, q: float) -> float:
    return 1.35 * g + 1.5 * q


def ossature_simulation(trame_x: Sequence[float] = (0, 6, 12), trame_y: Sequence[float] = (0, 5, 10),
                        hauteur_etage: float = 3.0, nb_niveaux: int = 5) -> dict:
    """R+4 sur trame régulière : descente de charges par surfaces d'influence.

    Niveaux RDC à R+4 (plancher haut de chaque niveau) ; le dernier est la terrasse.
    Poteaux 40×40 aux deux premiers niveaux, 30×30 au-dessus ; poutres 25×50 ;
    deux voiles de 4,00 m × 18 cm sur les pignons ; une semelle par poteau.
    """
    tx, ty = list(trame_x), list(trame_y)

    def demi(trame: List[float], i: int) -> float:
        g = (trame[i] - trame[i - 1]) / 2 if i > 0 else 0.0
        d = (trame[i + 1] - trame[i]) / 2 if i < len(trame) - 1 else 0.0
        return g + d

    def section_poteau(niv: int) -> Tuple[float, float]:
        return (40.0, 40.0) if niv < 2 else (30.0, 30.0)

    poteaux, poutres, semelles, voiles = [], [], [], []
    for ix, x in enumerate(tx):
        for iy, y in enumerate(ty):
            axe = f"{chr(65 + iy)}{ix + 1}"
            surface = demi(tx, ix) * demi(ty, iy)
            rive = ix in (0, len(tx) - 1) or iy in (0, len(ty) - 1)
            for niv in range(nb_niveaux):
                # planchers portés : du niveau `niv` jusqu'à la terrasse
                n_u = n_s = 0.0
                for k in range(niv, nb_niveaux):
                    terrasse = k == nb_niveaux - 1
                    g = G_TERRASSE if terrasse else G_PLANCHER
                    q = Q_TERRASSE if terrasse else Q_PLANCHER
                    a, b = section_poteau(k)
                    pp = GAMMA_BA * a * b / 1e4 * hauteur_etage
                    n_u += _pu(g, q) * surface + 1.35 * pp
                    n_s += (g + q) * surface + pp
                a, b = section_poteau(niv)
                # moments : excentricité additionnelle (BAEL A.4.3,5 : max(2 cm, l/250)),
                # majorée en rive (poutres non équilibrées)
                e0 = max(0.02, hauteur_etage / 250.0) * (2.0 if rive else 1.0)
                poteaux.append({
                    "id": f"P-{axe}-{niv}", "nom": f"P {axe}", "niveau": nom_niveau(niv), "axe": axe,
                    "a_cm": a, "b_cm": b, "hauteur_m": hauteur_etage,
                    "lf_m": round(COEF_LF * hauteur_etage, 2),
                    "nu_kn": round(n_u, 1), "ns_kn": round(n_s, 1),
                    "mx_knm": round(n_u * e0, 1), "my_knm": round(n_u * e0 * 0.5, 1),
                })
            p_rdc = next(p for p in poteaux if p["axe"] == axe and p["niveau"] == "RDC")
            semelles.append({
                "id": f"S-{axe}", "nom": f"S {axe}", "axe": axe,
                "a_poteau_cm": p_rdc["a_cm"], "b_poteau_cm": p_rdc["b_cm"],
                "ns_kn": p_rdc["ns_kn"], "nu_kn": p_rdc["nu_kn"],
                "mx_knm": 0.0, "my_knm": 0.0,
            })

    for niv in range(nb_niveaux):
        terrasse = niv == nb_niveaux - 1
        g = G_TERRASSE if terrasse else G_PLANCHER
        q = Q_TERRASSE if terrasse else Q_PLANCHER
        b, h = 25.0, 50.0
        pp = GAMMA_BA * b * h / 1e4
        # poutres suivant X (portées entre files 1-2, 2-3…) sur chaque file A, B, C…
        for direction, trame, autre in (("X", tx, ty), ("Y", ty, tx)):
            for j, _ in enumerate(autre):
                largeur = demi(list(autre), j)
                for i in range(len(trame) - 1):
                    portee = trame[i + 1] - trame[i]
                    pu = _pu(g, q) * largeur + 1.35 * pp
                    ps = (g + q) * largeur + pp
                    if direction == "X":
                        nom = f"{chr(65 + j)}{i + 1}-{chr(65 + j)}{i + 2}"
                    else:
                        nom = f"{chr(65 + i)}{j + 1}-{chr(65 + i + 1)}{j + 1}"
                    # poutre continue : M ≈ pl²/10 en travée (forfaitaire BAEL annexe E.1 simplifiée)
                    poutres.append({
                        "id": f"B-{direction}-{nom}-{niv}", "nom": f"Pt {nom}", "niveau": nom_niveau(niv),
                        "b_cm": b, "h_cm": h, "portee_m": portee,
                        "mu_knm": round(pu * portee ** 2 / 10.0, 1),
                        "ms_knm": round(ps * portee ** 2 / 10.0, 1),
                        "vu_kn": round(1.15 * pu * portee / 2.0, 1),
                    })

    # voiles de pignon : effort sismique repris à parts égales, croissant vers la base
    for nom, longueur in (("V1", 4.0), ("V2", 4.0)):
        for niv in range(nb_niveaux):
            etages_au_dessus = nb_niveaux - niv
            n = (_pu(G_PLANCHER, Q_PLANCHER) * longueur * 1.5 + 1.35 * GAMMA_BA * 0.18 * longueur * hauteur_etage) * etages_au_dessus
            v = 36.0 * etages_au_dessus                     # kN
            m = v * hauteur_etage * etages_au_dessus / 2.0  # kN.m
            voiles.append({
                "id": f"V-{nom}-{niv}", "nom": nom, "niveau": nom_niveau(niv),
                "longueur_m": longueur, "ep_cm": 18.0,
                "n_kn": round(n, 1), "m_knm": round(m, 1), "v_kn": round(v, 1),
            })

    oss = {"poteaux": poteaux, "poutres": poutres, "semelles": semelles, "voiles": voiles,
           "niveaux": [nom_niveau(i) for i in range(nb_niveaux)],
           "trame_x_m": tx, "trame_y_m": ty,
           "source": "simulation",
           "hypotheses": [
               f"Planchers : G = {G_PLANCHER} kN/m², Q = {Q_PLANCHER} kN/m² ; terrasse : G = {G_TERRASSE}, Q = {Q_TERRASSE} kN/m².",
               "Poteaux : descente de charges par surfaces d'influence, ELU 1,35G + 1,5Q, lf = 0,7·l0.",
               "Poutres : M = pl²/10 en travée, V = 1,15·pl/2 (continuité forfaitaire).",
               "Semelles : efforts en pied des poteaux du RDC.",
               "Voiles : efforts sismiques forfaitaires de démonstration.",
           ]}
    oss["resume"] = _resume(oss)
    return oss


# ───────────────────────── extraction Robot (COM) ─────────────────────────
# Chemins de l'API RobotOM (Robot Structural Analysis 2020 à 2025) :
#   projet.Structure.Nodes / Bars / Cases / Objects / Labels   (modèle)
#   projet.Structure.Results.Bars.Forces.Value(barre, cas, x)  (efforts, N et N·m)
#   projet.Structure.Results.Nodes.Reactions.Value(noeud, cas) (réactions)
# Avec les classes générées par win32com (makepy), un attribut absent de la
# bibliothèque de types lève une erreur : chaque accès suit donc un chemin
# documenté, avec repli, et une lecture qui échoue est signalée, jamais inventée.

def _const(nom: str, defaut: int) -> int:
    """Constante RobotOM ; lue après connexion, quand la bibliothèque de types est chargée."""
    try:
        from win32com.client import constants  # type: ignore
        return int(getattr(constants, nom))
    except Exception:
        return defaut


POSITIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
MOTS_ELU = ("ELU", "ULS", "STR")
MOTS_ELS = ("ELS", "SLS", "CAR", "SER")
_G = re.compile(r"(^|[^A-Z])(G\d*|PERM\w*|DL|DEAD\w*|PP|POIDS\w*|CP|SELF\w*)([^A-Z]|$)")
_Q = re.compile(r"(^|[^A-Z])(Q\d*|EXPL\w*|LL|LIVE\w*|SURCH\w*|IMPOS\w*)([^A-Z]|$)")

# Une combinaison de calcul : liste de (numéro de cas, coefficient)
Combinaison = List[Tuple[int, float]]


def choisir_cas(cas: Sequence[Tuple[int, str]], cas_elu: Optional[int], cas_els: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
    """Numéros des combinaisons ELU / ELS : imposés, sinon reconnus par leur nom (FR ou EN)."""
    def cherche(mots: Sequence[str]) -> Optional[int]:
        for num, nom in cas:
            n = (nom or "").upper()
            if any(re.search(rf"(^|[^A-Z]){m}([^A-Z]|$)", n) for m in mots):
                return num
        return None
    return (cas_elu or cherche(MOTS_ELU), cas_els or cherche(MOTS_ELS))


def combinaisons_de_calcul(cas: Sequence[Tuple[int, str, Optional[int], Optional[int]]],
                           cas_elu: Optional[int] = None, cas_els: Optional[int] = None
                           ) -> Tuple[Optional[Combinaison], Optional[Combinaison], List[str]]:
    """ELU et ELS à lire. `cas` : (numéro, nom, nature, type) de chaque cas Robot.

    1. combinaisons imposées, ou nommées ELU / ELS (ULS / SLS) dans le projet ;
    2. sinon, reconstituées à partir des cas simples, l'analyse étant linéaire :
       ELU = 1,35 ΣG + 1,5 ΣQ, ELS = ΣG + ΣQ.
    """
    remarques: List[str] = []
    elu, els = choisir_cas([(n, nom) for n, nom, _, _ in cas], cas_elu, cas_els)
    if elu is not None and els is not None:
        return [(elu, 1.0)], [(els, 1.0)], remarques
    permanent, exploitation = _const("I_CN_PERMANENT", 0), _const("I_CN_EXPLOATATION", 1)
    simple = _const("I_CT_SIMPLE", 0)
    g, q = [], []
    for num, nom, nature, typ in cas:
        if typ is not None and typ != simple:
            continue
        n = (nom or "").upper()
        if _G.search(n) or (nature == permanent and not _Q.search(n)):
            g.append(num)
        elif _Q.search(n) or nature == exploitation:
            q.append(num)
    if not g:
        if elu is None:
            remarques.append("Aucune combinaison ELU ni cas permanent G reconnu : indiquez le numéro de la combinaison ELU.")
        if els is None:
            remarques.append("Aucune combinaison ELS ni cas permanent G reconnu : indiquez le numéro de la combinaison ELS.")
        return ([(elu, 1.0)] if elu else None), ([(els, 1.0)] if els else None), remarques
    noms = {n: nom for n, nom, _, _ in cas}
    detail = "G = " + " + ".join(noms[n] for n in g) + ("" if not q else " ; Q = " + " + ".join(noms[n] for n in q))
    if elu is None:
        remarques.append(f"Pas de combinaison ELU dans le projet : 1,35 G + 1,5 Q reconstituée ({detail}).")
    if els is None:
        remarques.append(f"Pas de combinaison ELS dans le projet : G + Q reconstituée ({detail}).")
    elu_c = [(elu, 1.0)] if elu else [(n, 1.35) for n in g] + [(n, 1.5) for n in q]
    els_c = [(els, 1.0)] if els else [(n, 1.0) for n in g] + [(n, 1.0) for n in q]
    return elu_c, els_c, remarques


def _typer(obj, interface: str):
    """Objet d'une collection RobotOM vu avec son interface (IRobotBar…) ; sinon tel quel."""
    try:
        from win32com.client import CastTo  # type: ignore
        return CastTo(obj, interface)
    except Exception:
        return obj


def _iter_collection(col, interface: Optional[str] = None):
    for i in range(1, int(col.Count) + 1):
        o = col.Get(i)
        yield _typer(o, interface) if interface else o


def _label(objet, type_label: int) -> str:
    try:
        return objet.GetLabelName(type_label) or ""
    except Exception:
        return ""


def serveur_resultats(projet):
    """IRobotResultServer : Structure.Results (l'API n'en expose pas au niveau du projet)."""
    for chemin in (lambda: projet.Structure.Results, lambda: projet.Results):
        try:
            r = chemin()
            if r is not None:
                return r
        except Exception:
            continue
    raise RuntimeError("résultats inaccessibles dans ce projet Robot")


class _Erreurs:
    """Regroupe les lectures en échec : un message par sorte, avec un exemple."""

    def __init__(self):
        self.par_sorte: Dict[str, List[str]] = {}

    def note(self, sorte: str, qui: str, e: Exception):
        self.par_sorte.setdefault(sorte, []).append(f"{qui} ({e})")

    def remarques(self) -> List[str]:
        out = []
        for sorte, l in self.par_sorte.items():
            out.append(f"{sorte} : {len(l)} élément(s) non lu(s), par exemple {l[0]}." if len(l) > 1 else f"{sorte} : {l[0]}.")
        return out


def _combiner(lire, combinaison: Optional[Combinaison], champs: Sequence[str]) -> Optional[Dict[str, float]]:
    """Somme Σ coef · valeur, champ par champ (analyse linéaire)."""
    if not combinaison:
        return None
    total = dict.fromkeys(champs, 0.0)
    for num, coef in combinaison:
        v = lire(num)
        for c in champs:
            total[c] += coef * float(getattr(v, c))
    return total


def _points_panneau(obj) -> List[Tuple[float, float, float]]:
    """Sommets du contour d'un panneau, par les chemins de l'API connus selon les versions."""
    def depuis(col, attr_point=None):
        pts = []
        for i in range(1, int(col.Count) + 1):
            p = col.Get(i)
            if attr_point:
                p = getattr(_typer(p, "IRobotGeoSegment"), attr_point)
            p = _typer(p, "IRobotGeoPoint3D")
            pts.append((float(p.X), float(p.Y), float(p.Z)))
        return pts

    essais = (
        lambda: depuis(_typer(obj.Main.Geometry, "IRobotGeoContour").Segments, "P1"),
        lambda: depuis(_typer(obj.Main.Geometry, "IRobotGeoPolyline").Segments, "P1"),
        lambda: depuis(obj.Main.DefPoints),
    )
    for essai in essais:
        try:
            pts = essai()
            if len(pts) >= 3:
                return pts
        except Exception:
            continue
    return []


def _section_barre(barre, struct, type_section: int) -> Tuple[str, Optional[Tuple[float, float]]]:
    """Nom de la section et (b, h) en cm : depuis le nom, sinon depuis les données de la section."""
    nom = _label(barre, type_section)
    dims = dimensions_section(nom)
    if dims or not nom:
        return nom, dims
    try:   # section béton nommée librement (« POT1 ») : dimensions lues dans ses données (m)
        lab = struct.Labels.Get(type_section, nom)
        data = _typer(lab.Data, "IRobotBarSectionData")
        conc = _typer(data.Concrete, "IRobotBarSectionConcreteData")
        for b_, h_ in (("I_BSCDV_BEAM_B", "I_BSCDV_BEAM_H"), ("I_BSCDV_COL_B", "I_BSCDV_COL_H")):
            b, h = conc.GetValue(_const(b_, -1)), conc.GetValue(_const(h_, -1))
            if b and h:
                return nom, (round(float(b) * 100, 1), round(float(h) * 100, 1))
    except Exception:
        pass
    return nom, None


def extraire_ossature_com(projet, cas_elu: Optional[int] = None, cas_els: Optional[int] = None) -> dict:
    """Lit le projet Robot ouvert. Chaque élément illisible est signalé, pas inventé."""
    struct = projet.Structure
    resultats = serveur_resultats(projet)
    t_section = _const("I_LT_BAR_SECTION", 1)
    t_epaisseur = _const("I_LT_PANEL_THICKNESS", 18)
    erreurs = _Erreurs()
    remarques: List[str] = []

    cas = []
    for c in _iter_collection(struct.Cases.GetAll(), "IRobotCase"):
        nature = typ = None
        try:
            nature = int(c.Nature)
        except Exception:
            pass
        try:
            typ = int(c.Type)
        except Exception:
            pass
        cas.append((int(c.Number), str(c.Name), nature, typ))
    comb_elu, comb_els, rem_cas = combinaisons_de_calcul(cas, cas_elu, cas_els)
    remarques += rem_cas

    noeuds: Dict[int, Tuple[float, float, float]] = {}
    for n in _iter_collection(struct.Nodes.GetAll(), "IRobotNode"):
        try:
            noeuds[int(n.Number)] = (float(n.X), float(n.Y), float(n.Z))
        except Exception as e:
            erreurs.note("Nœuds", "nœud ?", e)
    if not noeuds:
        raise RuntimeError("le projet ne contient aucun nœud lisible")
    niveaux = niveaux_depuis_z([p[2] for p in noeuds.values()])
    trame_x = niveaux_depuis_z([p[0] for p in noeuds.values()], tol=0.10)
    trame_y = niveaux_depuis_z([p[1] for p in noeuds.values()], tol=0.10)

    efforts = resultats.Bars.Forces
    reactions = resultats.Nodes.Reactions

    def efforts_barre(num: int, comb: Optional[Combinaison]) -> Optional[dict]:
        if not comb:
            return None
        fx = fz = my = mz = 0.0
        for pos in POSITIONS:
            f = _combiner(lambda c: efforts.Value(num, c, pos), comb, ("FX", "FZ", "MY", "MZ"))
            fx = max(fx, abs(f["FX"])); fz = max(fz, abs(f["FZ"]))
            my = max(my, abs(f["MY"])); mz = max(mz, abs(f["MZ"]))
        return {"n": fx / 1e3, "v": fz / 1e3, "my": my / 1e3, "mz": mz / 1e3}   # N → kN

    poteaux, poutres, pieds = [], [], {}
    inclinees = []
    for barre in _iter_collection(struct.Bars.GetAll(), "IRobotBar"):
        try:
            num = int(barre.Number)
            p1, p2 = noeuds[int(barre.StartNode)], noeuds[int(barre.EndNode)]
        except Exception as e:
            erreurs.note("Barres", "barre ?", e)
            continue
        genre = classer_barre(p1, p2)
        if genre is None:
            inclinees.append(num)
            continue
        section_nom, dims = _section_barre(barre, struct, t_section)
        bas = p1 if p1[2] <= p2[2] else p2
        niv = indice_niveau(bas[2], niveaux)
        longueur = math.dist(p1, p2)
        try:
            u, s = efforts_barre(num, comb_elu), efforts_barre(num, comb_els)
        except Exception as e:
            u = s = None
            erreurs.note("Efforts des barres", f"barre {num}", e)
        if genre == "poteau":
            axe = libelle_axe(bas[0], bas[1], trame_x, trame_y)
            el = {"id": f"P{num}", "nom": f"P {axe}", "niveau": nom_niveau(niv), "axe": axe,
                  "a_cm": dims[0] if dims else None, "b_cm": dims[1] if dims else None,
                  "hauteur_m": round(longueur, 2), "lf_m": round(COEF_LF * longueur, 2),
                  "nu_kn": round(u["n"], 1) if u else None, "ns_kn": round(s["n"], 1) if s else None,
                  "mx_knm": round(u["my"], 1) if u else 0.0, "my_knm": round(u["mz"], 1) if u else 0.0,
                  "section_robot": section_nom}
            poteaux.append(el)
            if niv == 0:
                pieds[num] = (bas, el)
        else:
            el = {"id": f"B{num}", "nom": f"Pt {num}", "niveau": nom_niveau(max(niv - 1, 0)),
                  "b_cm": dims[0] if dims else None, "h_cm": dims[1] if dims else None,
                  "portee_m": round(longueur, 2),
                  "mu_knm": round(u["my"], 1) if u else None, "ms_knm": round(s["my"], 1) if s else None,
                  "vu_kn": round(u["v"], 1) if u else None, "section_robot": section_nom}
            poutres.append(el)
    if inclinees:
        remarques.append(f"{len(inclinees)} barre(s) inclinée(s) non traitée(s), par exemple la barre {inclinees[0]}.")

    # semelles : réactions aux nœuds d'appui en pied des poteaux du niveau bas
    semelles = []
    noeud_par_point = {v: k for k, v in noeuds.items()}
    for num, (bas, pot) in pieds.items():
        n_num = noeud_par_point.get(bas)
        ns = nu = None
        mx = my = 0.0
        try:
            r = _combiner(lambda c: reactions.Value(n_num, c), comb_elu, ("FZ", "MX", "MY"))
            if r:
                nu, mx, my = abs(r["FZ"]) / 1e3, abs(r["MX"]) / 1e3, abs(r["MY"]) / 1e3
            r = _combiner(lambda c: reactions.Value(n_num, c), comb_els, ("FZ",))
            if r:
                ns = abs(r["FZ"]) / 1e3
        except Exception as e:
            erreurs.note("Réactions d'appui", f"nœud {n_num}", e)
        semelles.append({"id": f"S{n_num}", "nom": f"S {pot['axe']}", "axe": pot["axe"],
                         "a_poteau_cm": pot["a_cm"], "b_poteau_cm": pot["b_cm"],
                         "ns_kn": round(ns, 1) if ns is not None else None,
                         "nu_kn": round(nu, 1) if nu is not None else None,
                         "mx_knm": round(mx, 1), "my_knm": round(my, 1)})

    # voiles : panneaux verticaux ; géométrie lue, efforts réduits à saisir (non exposés simplement par l'API)
    voiles = []
    try:
        for obj in _iter_collection(struct.Objects.GetAll(), "IRobotObjObject"):
            pts = _points_panneau(obj)
            if len(pts) < 3:
                continue
            zs = [p[2] for p in pts]
            if max(zs) - min(zs) < 0.5:          # panneau horizontal : dalle
                continue
            horiz = max(math.dist(a[:2], b[:2]) for a in pts for b in pts)
            voiles.append({"id": f"V{obj.Number}", "nom": f"V {obj.Number}",
                           "niveau": nom_niveau(indice_niveau(min(zs), niveaux)),
                           "longueur_m": round(horiz, 2),
                           "ep_cm": epaisseur_depuis_nom(_label(obj, t_epaisseur)),
                           "n_kn": None, "m_knm": None, "v_kn": None})
        if voiles:
            remarques.append("Voiles : géométrie lue dans Robot ; saisissez N, M, V (résultats réduits) avant calcul.")
    except Exception as e:
        remarques.append(f"Panneaux : lecture impossible ({e}).")

    remarques += erreurs.remarques()
    sans_section = [el for el in poteaux + poutres if el.get("a_cm", el.get("b_cm")) is None]
    if sans_section:
        el = sans_section[0]
        remarques.append(f"{len(sans_section)} élément(s) dont la section n'est pas reconnue, par exemple {el['nom']} "
                         f"(« {el.get('section_robot') or '?'} ») : saisissez leurs dimensions.")
    if not (poteaux or poutres or voiles):
        remarques.append("Aucun poteau, poutre ni voile reconnu dans ce modèle.")

    oss = {"poteaux": poteaux, "poutres": poutres, "semelles": semelles, "voiles": voiles,
           "niveaux": [nom_niveau(i) for i in range(max(len(niveaux) - 1, 1))],
           "trame_x_m": trame_x, "trame_y_m": trame_y,
           "source": "robot", "cas_elu": comb_elu[0][0] if comb_elu and len(comb_elu) == 1 else None,
           "cas_els": comb_els[0][0] if comb_els and len(comb_els) == 1 else None,
           "cas": [{"numero": n, "nom": nom} for n, nom, _, _ in cas],
           "hypotheses": ["Efforts : enveloppe des valeurs absolues sur 5 sections par barre.",
                          "lf = 0,7·l0 pour les poteaux (à adapter si nécessaire)."],
           "remarques": remarques}
    oss["resume"] = _resume(oss)
    return oss
