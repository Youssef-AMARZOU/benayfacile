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
# Constantes RobotOM : lues dans la bibliothèque de types (win32com makepy) quand elle
# est générée ; les valeurs de repli sont celles de l'API Robot 2020+, à vérifier sur
# chaque version installée.
def _const(nom: str, defaut: int) -> int:
    try:
        from win32com.client import constants  # type: ignore
        return int(getattr(constants, nom))
    except Exception:
        return defaut


I_OT_PANEL = _const("I_OT_PANEL", 5)
I_LT_BAR_SECTION = _const("I_LT_BAR_SECTION", 1)
I_LT_PANEL_THICKNESS = _const("I_LT_PANEL_THICKNESS", 18)
POSITIONS = (0.0, 0.25, 0.5, 0.75, 1.0)


def choisir_cas(cas: Sequence[Tuple[int, str]], cas_elu: Optional[int], cas_els: Optional[int]) -> Tuple[Optional[int], Optional[int]]:
    """Numéros des combinaisons ELU / ELS : imposés, sinon reconnus par leur nom."""
    def cherche(mot: str) -> Optional[int]:
        for num, nom in cas:
            if mot in (nom or "").upper():
                return num
        return None
    return (cas_elu or cherche("ELU"), cas_els or cherche("ELS"))


def _iter_collection(col):
    for i in range(1, col.Count + 1):
        yield col.Get(i)


def _label(objet, type_label: int) -> str:
    try:
        return objet.GetLabelName(type_label) or ""
    except Exception:
        return ""


def extraire_ossature_com(projet, cas_elu: Optional[int] = None, cas_els: Optional[int] = None) -> dict:
    """Lit le projet Robot ouvert. Chaque élément illisible est signalé, pas inventé."""
    struct = projet.Structure
    resultats = projet.Results
    remarques: List[str] = []

    cas = []
    for c in _iter_collection(struct.Cases.GetAll()):
        cas.append((int(c.Number), str(c.Name)))
    elu, els = choisir_cas(cas, cas_elu, cas_els)
    if elu is None:
        remarques.append("Aucune combinaison « ELU » trouvée : indiquez son numéro (cas_elu).")
    if els is None:
        remarques.append("Aucune combinaison « ELS » trouvée : indiquez son numéro (cas_els).")

    noeuds: Dict[int, Tuple[float, float, float]] = {}
    for n in _iter_collection(struct.Nodes.GetAll()):
        noeuds[int(n.Number)] = (float(n.X), float(n.Y), float(n.Z))
    niveaux = niveaux_depuis_z([p[2] for p in noeuds.values()])
    trame_x = niveaux_depuis_z([p[0] for p in noeuds.values()], tol=0.10)
    trame_y = niveaux_depuis_z([p[1] for p in noeuds.values()], tol=0.10)

    def efforts_barre(num: int, cas_num: Optional[int]) -> Optional[dict]:
        if cas_num is None:
            return None
        fx = fz = my = mz = 0.0
        for pos in POSITIONS:
            f = resultats.Bars.Forces.Value(num, cas_num, pos)
            fx = max(fx, abs(f.FX)); fz = max(fz, abs(f.FZ))
            my = max(my, abs(f.MY)); mz = max(mz, abs(f.MZ))
        return {"n": fx / 1e3, "v": fz / 1e3, "my": my / 1e3, "mz": mz / 1e3}   # N → kN

    poteaux, poutres, pieds = [], [], {}
    for barre in _iter_collection(struct.Bars.GetAll()):
        num = int(barre.Number)
        try:
            p1, p2 = noeuds[int(barre.StartNode)], noeuds[int(barre.EndNode)]
        except KeyError:
            continue
        genre = classer_barre(p1, p2)
        if genre is None:
            remarques.append(f"Barre {num} inclinée : non traitée.")
            continue
        section_nom = _label(barre, I_LT_BAR_SECTION)
        dims = dimensions_section(section_nom)
        bas = p1 if p1[2] <= p2[2] else p2
        niv = indice_niveau(bas[2], niveaux)
        longueur = math.dist(p1, p2)
        try:
            u, s = efforts_barre(num, elu), efforts_barre(num, els)
        except Exception as e:
            u = s = None
            remarques.append(f"Barre {num} : efforts illisibles ({e}).")
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

    # semelles : réactions aux nœuds d'appui en pied des poteaux du niveau bas
    semelles = []
    noeud_par_point = {v: k for k, v in noeuds.items()}
    for num, (bas, pot) in pieds.items():
        n_num = noeud_par_point.get(bas)
        ns = nu = None
        mx = my = 0.0
        try:
            if elu is not None:
                r = resultats.Nodes.Reactions.Value(n_num, elu)
                nu, mx, my = abs(r.FZ) / 1e3, abs(r.MX) / 1e3, abs(r.MY) / 1e3
            if els is not None:
                ns = abs(resultats.Nodes.Reactions.Value(n_num, els).FZ) / 1e3
        except Exception as e:
            remarques.append(f"Nœud {n_num} : réactions illisibles ({e}).")
        semelles.append({"id": f"S{n_num}", "nom": f"S {pot['axe']}", "axe": pot["axe"],
                         "a_poteau_cm": pot["a_cm"], "b_poteau_cm": pot["b_cm"],
                         "ns_kn": round(ns, 1) if ns is not None else None,
                         "nu_kn": round(nu, 1) if nu is not None else None,
                         "mx_knm": round(mx, 1), "my_knm": round(my, 1)})

    # voiles : panneaux verticaux ; géométrie lue, efforts réduits à saisir (non exposés simplement par l'API)
    voiles = []
    try:
        panneaux = struct.Objects.GetAll()
        for i in range(1, panneaux.Count + 1):
            obj = panneaux.Get(i)
            if int(getattr(obj, "ObjectType", -1)) != I_OT_PANEL:
                continue
            pts = [(float(p.X), float(p.Y), float(p.Z)) for p in _iter_collection(obj.Main.DefPoints)] \
                if hasattr(obj.Main, "DefPoints") else []
            if len(pts) < 3:
                continue
            zs = [p[2] for p in pts]
            if max(zs) - min(zs) < 0.5:          # panneau horizontal : dalle
                continue
            horiz = max(math.dist(a[:2], b[:2]) for a in pts for b in pts)
            voiles.append({"id": f"V{obj.Number}", "nom": f"V {obj.Number}",
                           "niveau": nom_niveau(indice_niveau(min(zs), niveaux)),
                           "longueur_m": round(horiz, 2),
                           "ep_cm": epaisseur_depuis_nom(_label(obj, I_LT_PANEL_THICKNESS)),
                           "n_kn": None, "m_knm": None, "v_kn": None})
        if voiles:
            remarques.append("Voiles : géométrie lue dans Robot ; saisissez N, M, V (résultats réduits) avant calcul.")
    except Exception as e:
        remarques.append(f"Panneaux : lecture impossible ({e}).")

    for el in poteaux + poutres:
        if el.get("a_cm", el.get("b_cm")) is None:
            remarques.append(f"{el['nom']} : section « {el.get('section_robot') or '?'} » non reconnue.")
            break

    oss = {"poteaux": poteaux, "poutres": poutres, "semelles": semelles, "voiles": voiles,
           "niveaux": [nom_niveau(i) for i in range(max(len(niveaux) - 1, 1))],
           "trame_x_m": trame_x, "trame_y_m": trame_y,
           "source": "robot", "cas_elu": elu, "cas_els": els,
           "cas": [{"numero": n, "nom": nom} for n, nom in cas],
           "hypotheses": ["Efforts : enveloppe des valeurs absolues sur 5 sections par barre.",
                          "lf = 0,7·l0 pour les poteaux (à adapter si nécessaire)."],
           "remarques": remarques}
    oss["resume"] = _resume(oss)
    return oss
