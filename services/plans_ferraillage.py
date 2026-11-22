"""Plans de ferraillage DXF de tout le modèle, à partir du calcul en lot.

Un seul fichier DXF, plusieurs feuilles A1 côte à côte dans l'espace objet :
  1. Plan de fondation (implantation des semelles sur la trame, 1:100)
  1 bis. Plans de coffrage : une planche par niveau (niveaux identiques regroupés),
     poteaux et voiles coupés, poutres en tireté, panneaux de dalle et balcons
  2. Semelles : vue en plan + coupe par type (1:25)
  3. Poteaux : coupe par type (1:10), cadres et zones critiques
  4. Poutres : élévation (1:50) + coupe (1:20) par type
  5. Voiles : élévation par type (1:50)
  6. Nomenclature des aciers (repère, Ø, nombre, longueurs, poids)

Les éléments identiques sont regroupés en types (P1, P2… / Pt1… / S1… / V1…),
comme sur un dossier d'exécution. Seuls les éléments « vérifiés » sont
dessinés ; les autres sont listés sur la feuille (à reprendre avant exécution).

Dispositions constructives retenues (à valider par l'ingénieur) :
  - poteaux : cadres Øt ≥ Øl/3 (HA8, HA10 si Øl > 20) ; zone courante
    st ≤ min(15 Øl, 40 cm, a + 10 cm) (BAEL A.8.1,3) ; zones critiques
    lc = max(he/6, b, 45 cm), st ≤ min(8 Øl, b/4, 15 cm) (RPS 2011, ND1) ;
    recouvrement 50 Øl ;
  - poutres : cadres HA8 à 2 brins, st ≤ min(At/(At/st), 0,9 d, 40 cm) ;
    zones critiques 2h, st ≤ min(h/4, 12 Øl, 30 cm) ; aciers de montage
    2 HA12 (3 si b > 30 cm) ; ancrages 40 Ø ;
  - semelles : deux nappes, crochets 10 Ø, attentes = aciers du poteau du RDC ;
  - voiles : deux nappes HA10, s ≤ min(30 cm, 1,5 e), potelets de rive.
"""
from __future__ import annotations

import datetime
import math
import re
from collections import OrderedDict
from typing import Dict, List, Optional, Sequence, Tuple

import ezdxf
from ezdxf.enums import TextEntityAlignment
from ezdxf.units import MM

from common import (CATEGORIES_POUTRE, ROLES_POTEAU, cote_niveau, indice_file, lettre_file,  # noqa: F401
                    rang_niveau, trier_niveaux)

# ───────────────────────── aciers ─────────────────────────

def section_cm2(d_mm: float) -> float:
    return math.pi * d_mm ** 2 / 400.0


def poids_ml(d_mm: float) -> float:
    """kg/m : 7850 kg/m³ × π d²/4."""
    return round(7850 * math.pi * (d_mm / 1000.0) ** 2 / 4.0, 3)


def _arr(v: float, pas: float = 0.01, mini: float = 0.05) -> float:
    """Arrondi inférieur au centimètre, au moins 5 cm (espacement réalisable)."""
    return max(mini, math.floor(v / pas + 1e-9) * pas)


def _barres(d: Optional[dict]) -> Optional[Tuple[int, int]]:
    if not d or not d.get("n") or not d.get("diametre_mm"):
        return None
    return int(d["n"]), int(round(d["diametre_mm"]))


def cadres_poteau(a_cm: float, b_cm: float, h_m: float, d_long: int) -> dict:
    t = 8 if d_long <= 20 else 10
    petit = min(a_cm, b_cm) / 100.0
    st_c = _arr(min(15 * d_long / 1000.0, 0.40, petit + 0.10))
    st_z = _arr(min(8 * d_long / 1000.0, 0.25 * petit, 0.15))
    lc = max(h_m / 6.0, max(a_cm, b_cm) / 100.0, 0.45)
    lc = min(lc, h_m / 2.0)
    n_z = 2 * math.ceil(lc / st_z)
    n_c = max(math.ceil((h_m - 2 * lc) / st_c) - 1, 0)
    return {"diametre_mm": t, "st_courant_m": st_c, "st_critique_m": st_z, "lc_m": round(lc, 2),
            "nombre": n_z + n_c + 1}


def cadres_poutre(b_cm: float, h_cm: float, portee_m: float, d_m: float, d_long: int, at_cm2_m: float) -> dict:
    for t in (8, 10):                     # HA10 si des HA8 imposeraient moins de 7 cm
        s_req = 2 * section_cm2(t) / at_cm2_m if at_cm2_m and at_cm2_m > 0 else 0.40
        if s_req >= 0.07:
            break
    st = _arr(min(s_req, 0.9 * d_m, 0.40))
    h = h_cm / 100.0
    st_z = _arr(min(h / 4.0, 12 * d_long / 1000.0, 0.30, st))
    lc = min(2 * h, portee_m / 2.0)
    n = 2 * math.ceil(lc / st_z) + max(math.ceil((portee_m - 2 * lc) / st) - 1, 0) + 1
    return {"diametre_mm": t, "st_courant_m": st, "st_critique_m": st_z, "lc_m": round(lc, 2), "nombre": n}


def _pos(rep: str, designation: str, d: int, nb: int, l_m: float) -> dict:
    return {"rep": rep, "designation": designation, "diametre_mm": d, "nombre": nb,
            "longueur_m": round(l_m, 2)}


# ───────────────────────── types d'éléments ─────────────────────────

def _cle_poteau(l):
    e, r = l["entree"], l["resultat"]
    return (e["a_cm"], e["b_cm"], round(e.get("hauteur_m") or 3.0, 2), _barres(r.get("ferraillage")))


def _cle_poutre(l):
    e, r = l["entree"], l["resultat"]
    cad = cadres_poutre(e["b_cm"], e["h_cm"], e.get("portee_m") or 5.0, r.get("d_m") or e["h_cm"] / 100 * 0.9,
                        (_barres(r.get("ferraillage")) or (0, 12))[1], (r.get("effort_tranchant") or {}).get("at_cm2_par_m"))
    return (e["b_cm"], e["h_cm"], round(e.get("portee_m") or 5.0, 2), _barres(r.get("ferraillage")), cad["st_courant_m"])


def _cle_semelle(l):
    r = l["resultat"]
    return (r["A_m"], r["B_m"], r["H_m"], _barres(r.get("choix_x")), _barres(r.get("choix_y")),
            l["entree"].get("a_poteau_cm"), l["entree"].get("b_poteau_cm"))


def _cle_voile(l):
    e, r = l["entree"], l["resultat"]
    return (e["longueur_m"], e["ep_cm"], round(e.get("hauteur_m") or 3.0, 2), r.get("as_vert_par_m_cm2"),
            r.get("as_horiz_par_m_cm2"), _barres(r.get("rive")))


def _cle_dalle(l):
    e, r = l["entree"], l["resultat"]
    rr = r["resultats"]
    choix = tuple((rr.get(k) or {}).get("ferraillage", {}).get("choix") for k in ("x_travee", "y_travee", "appuis"))
    return (round(e["lx_m"], 2), round(e["ly_m"], 2), e["h_cm"]) + choix + ((r.get("treillis") or {}).get("designation"),)


CLES = {"poteaux": ("P", _cle_poteau), "poutres": ("Pt", _cle_poutre),
        "semelles": ("S", _cle_semelle), "voiles": ("V", _cle_voile), "dalles": ("D", _cle_dalle)}


def prefixe_type(fam: str, l: dict) -> str:
    """Repère de type : P (poteau), F (fût), Pt (poutre), L (longrine), Ch (chaînage), S, V, D, DF (dalle de fondation)."""
    e = l.get("entree") or {}
    if fam == "poutres":
        return CATEGORIES_POUTRE.get(e.get("categorie") or "poutre", CATEGORIES_POUTRE["poutre"])["prefixe"]
    if fam == "poteaux":
        return ROLES_POTEAU.get(e.get("role") or "poteau", ROLES_POTEAU["poteau"])["prefixe"]
    if fam == "dalles":
        return "DF" if e.get("role") == "fondation" else "D"
    return CLES[fam][0]


def grouper(lot: dict, par_element: bool = False) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """Types par famille (éléments vérifiés) et liste des éléments non dessinés.
    par_element : un « type » par élément (un détail dessiné pour chaque élément, au lieu d'un par type)."""
    types, ecartes = {}, []
    for fam, (prefixe, cle) in CLES.items():
        groupes: "OrderedDict[tuple, dict]" = OrderedDict()
        for l in lot.get(fam) or []:
            if l.get("statut") != "verifie" or not l.get("resultat"):
                ecartes.append({"famille": fam, "nom": l.get("nom"), "niveau": l.get("niveau"),
                                "statut": l.get("statut"), "raison": " ; ".join(l.get("problemes") or [])})
                continue
            try:
                pre = prefixe_type(fam, l)
                k = (pre,) + tuple(cle(l))
                if par_element:
                    k = (pre, id(l))
            except (KeyError, TypeError):
                ecartes.append({"famille": fam, "nom": l.get("nom"), "niveau": l.get("niveau"),
                                "statut": "incomplet", "raison": "données de dessin manquantes"})
                continue
            groupes.setdefault(k, {"lignes": [], "prefixe": pre})["lignes"].append(l)
        types[fam] = []
        compteurs: Dict[str, int] = {}
        for g in groupes.values():
            compteurs[g["prefixe"]] = compteurs.get(g["prefixe"], 0) + 1
            g["code"] = f"{g['prefixe']}{compteurs[g['prefixe']]}"
            g["rep"] = g["lignes"][0]
            g["elements"] = [f"{l.get('nom')}{' · ' + l['niveau'] if l.get('niveau') else ''}" for l in g["lignes"]]
            types[fam].append(g)
    return types, ecartes


def positions_type(fam: str, t: dict, mat: dict, poteaux_rdc: Dict[str, dict]) -> List[dict]:
    """Nomenclature d'UN élément du type (repères, Ø, nombre, longueur unitaire)."""
    l = t["rep"]
    e, r = l["entree"], l["resultat"]
    if fam == "poteaux":
        n, d = _barres(r["ferraillage"])
        h = e.get("hauteur_m") or 3.0
        c = mat.get("enrobage_poteau_mm", 30) / 1000.0
        cad = cadres_poteau(e["a_cm"], e["b_cm"], h, d)
        t_ = cad["diametre_mm"]
        lcad = 2 * ((e["a_cm"] / 100 - 2 * c) + (e["b_cm"] / 100 - 2 * c)) + 2 * 10 * t_ / 1000
        t["cadres"] = cad
        return [_pos("1", "Barres longitudinales (recouvrement 50 Ø)", d, n, h + 50 * d / 1000),
                _pos("2", f"Cadres e = {cad['st_critique_m'] * 100:.0f} / {cad['st_courant_m'] * 100:.0f} cm", t_, cad["nombre"], lcad)]
    if fam == "poutres":
        n, d = _barres(r["ferraillage"])
        L = e.get("portee_m") or 5.0
        c = mat.get("enrobage_poutre_mm", 40) / 1000.0
        d_utile = r.get("d_m") or e["h_cm"] / 100 * 0.9
        cad = cadres_poutre(e["b_cm"], e["h_cm"], L, d_utile, d, (r.get("effort_tranchant") or {}).get("at_cm2_par_m"))
        n_sup = 3 if e["b_cm"] > 30 else 2
        tc = cad["diametre_mm"]
        lcad = 2 * ((e["b_cm"] / 100 - 2 * c) + (e["h_cm"] / 100 - 2 * c)) + 2 * 10 * tc / 1000
        t["cadres"], t["montage"] = cad, (n_sup, 12)
        return [_pos("1", "Aciers inférieurs (ancrages 40 Ø)", d, n, L + 2 * 40 * d / 1000),
                _pos("2", "Aciers de montage (chapeaux)", 12, n_sup, L + 2 * 40 * 12 / 1000),
                _pos("3", f"Cadres e = {cad['st_critique_m'] * 100:.0f} / {cad['st_courant_m'] * 100:.0f} cm", tc, cad["nombre"], lcad)]
    if fam == "semelles":
        nx, dx = _barres(r["choix_x"])
        ny, dy = _barres(r["choix_y"])
        c = mat.get("enrobage_semelle_mm", 50) / 1000.0
        pos = [_pos("1", "Nappe inférieure X (crochets 10 Ø)", dx, nx, r["A_m"] - 2 * c + 2 * 10 * dx / 1000),
               _pos("2", "Nappe inférieure Y (crochets 10 Ø)", dy, ny, r["B_m"] - 2 * c + 2 * 10 * dy / 1000)]
        pot = poteaux_rdc.get(l.get("axe") or "")
        att = _barres((pot or {}).get("resultat", {}).get("ferraillage")) if pot else None
        n_a, d_a = att or (4, 12)
        t["attentes"] = (n_a, d_a)
        pos.append(_pos("3", "Attentes du poteau (retour 20 Ø, recouvrement 50 Ø)", d_a, n_a,
                        r["H_m"] - c + 20 * d_a / 1000 + 50 * d_a / 1000))
        return pos
    if fam == "voiles":
        L, ep = e["longueur_m"], e["ep_cm"] / 100.0
        h = e.get("hauteur_m") or 3.0
        c = 0.03
        smax = min(0.30, 1.5 * ep)
        s_v = _arr(min(section_cm2(10) / max((r.get("as_vert_par_m_cm2") or 1) / 2, 1e-6), smax))
        s_h = _arr(min(section_cm2(10) / max((r.get("as_horiz_par_m_cm2") or 1) / 2, 1e-6), smax))
        n_v = 2 * (math.floor((L - 2 * c) / s_v) + 1)
        n_h = 2 * (math.floor(h / s_h) + 1)
        rive = _barres(r.get("rive")) or (4, 12)
        if rive[1] < 12 or rive[0] < 4:          # potelet : au moins 4 HA12 (même section d'acier au minimum)
            rive = (max(4, math.ceil(rive[0] * section_cm2(rive[1]) / section_cm2(12))), 12)
        t["espacements"] = (s_v, s_h)
        t["rive_barres"] = rive
        return [_pos("1", f"Verticales 2 nappes e = {s_v * 100:.0f} cm", 10, n_v, h + 50 * 10 / 1000),
                _pos("2", f"Horizontales 2 nappes e = {s_h * 100:.0f} cm", 10, n_h, L - 2 * c + 2 * 10 * 10 / 1000),
                _pos("3", "Potelets de rive (2 extrémités)", rive[1], 2 * rive[0], h + 50 * rive[1] / 1000)]
    if fam == "dalles":
        # longueurs : contour du panneau (axes des appuis) − 2 enrobages, + 2 crochets de 10 Ø pour les barres HA
        lx, ly = e["lx_m"], e["ly_m"]
        rr = r["resultats"]
        c = max(r["h_cm"] / 100 - rr["x_travee"]["d_m"] - 0.005, 0.0)     # enrobage retenu par le calcul (d = h − c − Ø/2)
        t["enrobage_m"] = c
        ts = r.get("treillis")
        pos = []
        if ts:
            d, st = ts["diametre_mm"], ts["maille_cm"] / 100
            pos.append(_pos("1", f"Treillis soudé {ts['designation']} — fils sens lx", d, math.floor((ly - 2 * c) / st) + 1, lx - 2 * c))
            pos.append(_pos("2", f"Treillis soudé {ts['designation']} — fils sens ly", d, math.floor((lx - 2 * c) / st) + 1, ly - 2 * c))
            t["non_comptes"] = ["Treillis : recouvrements entre panneaux non compris (calepinage à faire)."]
        else:
            t["non_comptes"] = []
            for rep_, cle_, l_barre, l_rep, sens in (("1", "x_travee", lx, ly, "lx"), ("2", "y_travee", ly, lx, "ly")):
                f = rr[cle_]["ferraillage"]
                d, st = f["diametre_mm"], f["espacement_cm"] / 100
                pos.append(_pos(rep_, f"Nappe inférieure sens {sens} {f['choix']} (crochets 10 Ø)", d,
                                math.floor((l_rep - 2 * c) / st) + 1, l_barre - 2 * c + 2 * 10 * d / 1000))
        fa = (rr.get("appuis") or {}).get("ferraillage") or {}
        if fa.get("choix"):
            t["non_comptes"].append(f"Chapeaux {fa['choix']} : longueur d'arrêt à définir par l'ingénieur, non comptés.")
        return pos
    return []


def poteaux_sur_semelles(lot: dict) -> Dict[str, dict]:
    """Par axe, le poteau calculé qui part de la semelle (fût s'il existe, sinon le poteau le plus bas) :
    ses barres donnent les attentes de la semelle, quel que soit le nom des niveaux (Robot, Excel)."""
    choix: Dict[str, tuple] = {}
    for l in lot.get("poteaux") or []:
        if not l.get("resultat") or not l.get("axe"):
            continue
        e = l.get("entree") or {}
        z = e.get("z_m") if e.get("z_m") is not None else (0.0 if l.get("niveau") == "RDC" else 1e9)
        cle = (0 if e.get("role") == "fut" else 1, z)
        if l["axe"] not in choix or cle < choix[l["axe"]][0]:
            choix[l["axe"]] = (cle, l)
    return {axe: l for axe, (_, l) in choix.items()}


def nomenclature(lot: dict, par_element: bool = False) -> dict:
    """Types, positions et poids : la partie « calcul » des plans (sans dessin)."""
    types, ecartes = grouper(lot, par_element)
    mat = lot.get("materiaux") or {}
    poteaux_rdc = poteaux_sur_semelles(lot)
    lignes, par_diam = [], {}
    for fam, liste in types.items():
        for t in liste:
            t["positions"] = positions_type(fam, t, mat, poteaux_rdc)
            nb_el = len(t["lignes"])
            for p in t["positions"]:
                l_tot = round(p["nombre"] * p["longueur_m"] * nb_el, 2)
                kg = round(l_tot * poids_ml(p["diametre_mm"]), 1)
                lignes.append({"famille": fam, "type": t["code"], "nb_elements": nb_el, **p,
                               "longueur_totale_m": l_tot, "poids_kg": kg})
                par_diam[p["diametre_mm"]] = round(par_diam.get(p["diametre_mm"], 0) + kg, 1)
    return {"types": types, "ecartes": ecartes, "lignes": lignes,
            "par_diametre_kg": dict(sorted(par_diam.items())),
            "poids_total_kg": round(sum(par_diam.values()), 1)}


# ───────────────────────── dessin ─────────────────────────

CALQUES = {"AXES": 1, "COFFRAGE": 7, "ACIER_LONG": 6, "CADRES": 4, "COTATION": 2,
           "TEXTE": 7, "CARTOUCHE": 7, "NOMENCLATURE": 3, "BETON_PROPRETE": 8,
           "LONGRINES": 5, "CHAINAGES": 3, "SEMELLES": 7, "NIVEAUX": 2, "COUCHES": 8}
# représentation des éléments horizontaux (US2) : poutre en tireté, longrine hachurée, chaînage quadrillé
STYLE_POUTRE = {"poutre": ("COFFRAGE", "DASHED", None), "longrine": ("LONGRINES", None, "ANSI31"),
                "chainage": ("CHAINAGES", None, "ANSI37")}
A1 = (841.0, 594.0)
MARGE = 15.0
CART_L, CART_H = 190.0, 58.0
ESPACE_FEUILLES = 60.0
MC = TextEntityAlignment.MIDDLE_CENTER
ML = TextEntityAlignment.MIDDLE_LEFT
BL = TextEntityAlignment.BOTTOM_LEFT


class Planche:
    """Une feuille A1 : cadre, titre, cartouche, et placement des vues en cellules."""

    def __init__(self, dessin: "Dessin", titre: str, sous_titre: str, cellule: Tuple[float, float]):
        self.d = dessin
        self.num = len(dessin.planches) + 1
        self.x0 = (self.num - 1) * (A1[0] + ESPACE_FEUILLES)
        self.y0 = 0.0
        self.titre, self.sous_titre = titre, sous_titre
        self.cw, self.ch = cellule
        self.cx = self.x0 + MARGE + 10
        self.cy = self.y0 + A1[1] - MARGE - 30          # haut de la zone utile
        self.bas = self.y0 + MARGE + CART_H + 8
        dessin.planches.append(self)
        self._cadre()

    def _cadre(self):
        m, x0, y0 = self.d.msp, self.x0, self.y0
        W, H = A1
        m.add_lwpolyline([(x0, y0), (x0 + W, y0), (x0 + W, y0 + H), (x0, y0 + H)], close=True,
                         dxfattribs={"layer": "CARTOUCHE", "lineweight": 18})
        m.add_lwpolyline([(x0 + MARGE, y0 + MARGE), (x0 + W - MARGE, y0 + MARGE), (x0 + W - MARGE, y0 + H - MARGE),
                          (x0 + MARGE, y0 + H - MARGE)], close=True, dxfattribs={"layer": "CARTOUCHE", "lineweight": 50})
        self.d.texte(self.titre, x0 + MARGE + 10, y0 + H - MARGE - 14, 8.0, BL, "TEXTE")
        self.d.texte(self.sous_titre, x0 + MARGE + 10, y0 + H - MARGE - 22, 3.5, BL, "TEXTE")
        self.d.cartouche(x0 + W - MARGE - CART_L, y0 + MARGE, self.titre, self.num)

    def _libre(self, x: float, y: float, w: float, h: float) -> bool:
        """La cellule (coin haut-gauche x, y) tient dans la feuille sans toucher le cartouche
        ni l'encadré « non dessinés » placé au-dessus de lui."""
        if x + w > self.x0 + A1[0] - MARGE - 5:
            return False
        bas = self.y0 + MARGE + 5
        if x + w > self.x0 + A1[0] - MARGE - CART_L - 5:
            bas = self.y0 + MARGE + CART_H + 75
        return y - h >= bas

    def cellule(self) -> Optional[Tuple[float, float]]:
        """Coin haut-gauche de la cellule suivante (rangées de gauche à droite), ou None si pleine."""
        w, h = self.cw, self.ch
        gauche = self.x0 + MARGE + 10
        for _ in range(2):                       # rangée courante, sinon rangée suivante
            if self._libre(self.cx, self.cy, w, h):
                pos = (self.cx, self.cy)
                self.cx += w
                return pos
            if self.cx == gauche:                 # même une rangée neuve ne tient pas
                break
            self.cx, self.cy = gauche, self.cy - h
        while self.cy - h >= self.y0 + MARGE + 5:  # rangée neuve trop basse à droite : tenter plus bas à gauche
            if self._libre(self.cx, self.cy, w, h):
                pos = (self.cx, self.cy)
                self.cx += w
                return pos
            self.cx, self.cy = gauche, self.cy - h
        return None


class Dessin:
    def __init__(self, projet: dict, bureau: dict):
        self.doc = ezdxf.new("R2010", setup=True)
        self.doc.units = MM
        self.msp = self.doc.modelspace()
        for nom, couleur in CALQUES.items():
            if nom in self.doc.layers:
                self.doc.layers.get(nom).color = couleur
            else:
                self.doc.layers.add(nom, color=couleur)
        self.doc.styles.new("BNAY", dxfattribs={"font": "arial.ttf"})
        self.projet, self.bureau = projet, bureau
        self.planches: List[Planche] = []
        self.date = datetime.date.today().strftime("%d/%m/%Y")

    # primitives (coordonnées feuille, mm)
    def texte(self, t, x, y, h=2.5, align=BL, calque="TEXTE"):
        t = str(t).replace("Ø", "%%c")           # symbole diamètre AutoCAD
        self.msp.add_text(t, height=h, dxfattribs={"layer": calque, "style": "BNAY"}).set_placement((x, y), align=align)

    def rect(self, x, y, w, h, calque="COFFRAGE", ep=35):
        self.msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True,
                                dxfattribs={"layer": calque, "lineweight": ep})

    def ligne(self, p1, p2, calque="ACIER_LONG", ep=35, type_trait=None):
        att = {"layer": calque, "lineweight": ep}
        if type_trait:
            att["linetype"] = type_trait
        self.msp.add_line(p1, p2, dxfattribs=att)

    def hachure(self, pts, motif=None, echelle=0.4, calque="COFFRAGE", couleur=8):
        """Hachure d'un contour fermé : motif AutoCAD (ANSI31, GRAVEL…) ou remplissage plein."""
        h = self.msp.add_hatch(color=couleur, dxfattribs={"layer": calque})
        if motif:
            h.set_pattern_fill(motif, scale=echelle, color=couleur)
        h.paths.add_polyline_path(pts, is_closed=True)

    def niveau(self, x, y, texte, calque="NIVEAUX", gauche=False):
        """Repère de niveau : triangle pointe en bas posé sur la ligne de niveau (x, y), cote à côté."""
        self.msp.add_lwpolyline([(x - 1.6, y + 2.6), (x + 1.6, y + 2.6), (x, y)], close=True,
                                dxfattribs={"layer": calque, "lineweight": 18})
        self.ligne((x - 3, y), (x + 3, y), calque, 18)
        self.texte(texte, x - 2.5 if gauche else x + 2.5, y + 3.2, 2.2,
                   TextEntityAlignment.BOTTOM_RIGHT if gauche else BL, calque)

    def barre(self, x, y, r, calque="ACIER_LONG"):
        self.msp.add_circle((x, y), r, dxfattribs={"layer": calque})
        h = self.msp.add_hatch(dxfattribs={"layer": calque})
        h.paths.add_edge_path().add_arc((x, y), r, 0, 360)

    def cote(self, p1, p2, texte, decalage=6.0):
        """Cote linéaire simple (horizontale ou verticale) : ligne, traits obliques, valeur."""
        (x1, y1), (x2, y2) = p1, p2
        if abs(y2 - y1) < 1e-6:
            y = y1 - decalage
            self.ligne((x1, y), (x2, y), "COTATION", 13)
            for x in (x1, x2):
                self.ligne((x, y1 - 1), (x, y - 1.5), "COTATION", 13)
                self.ligne((x - 1, y - 1), (x + 1, y + 1), "COTATION", 25)
            self.texte(texte, (x1 + x2) / 2, y + 1.2, 2.2, TextEntityAlignment.BOTTOM_CENTER, "COTATION")
        else:
            x = x1 - decalage
            self.ligne((x, y1), (x, y2), "COTATION", 13)
            for y in (y1, y2):
                self.ligne((x1 - 1, y), (x - 1.5, y), "COTATION", 13)
                self.ligne((x - 1, y - 1), (x + 1, y + 1), "COTATION", 25)
            t = self.msp.add_text(texte, height=2.2, dxfattribs={"layer": "COTATION", "rotation": 90, "style": "BNAY"})
            t.set_placement((x - 1.2, (y1 + y2) / 2), align=TextEntityAlignment.BOTTOM_CENTER)

    def tableau(self, x, y, entetes: Sequence[str], largeurs: Sequence[float], lignes: Sequence[Sequence],
                h_ligne=5.0, calque="NOMENCLATURE") -> float:
        """Tableau à traits ; renvoie l'ordonnée sous le tableau."""
        W = sum(largeurs)
        self.rect(x, y - h_ligne, W, h_ligne, calque, 35)
        xc = x
        for t, w in zip(entetes, largeurs):
            self.texte(t, xc + 1.2, y - h_ligne / 2, 2.2, ML, calque)
            xc += w
        yc = y - h_ligne
        for ligne in lignes:
            xc = x
            for v, w in zip(ligne, largeurs):
                self.texte("" if v is None else v, xc + 1.2, yc - h_ligne / 2, 2.0, ML, calque)
                xc += w
            yc -= h_ligne
            self.ligne((x, yc), (x + W, yc), calque, 13)
        xc = x
        for w in list(largeurs) + [0]:
            self.ligne((xc, y), (xc, yc), calque, 13)
            xc += w
        return yc

    def cartouche(self, x, y, titre_feuille, num):
        B, p = self.bureau or {}, self.projet
        self.rect(x, y, CART_L, CART_H, "CARTOUCHE", 50)
        for dy in (14, 30, 44):
            self.ligne((x, y + dy), (x + CART_L, y + dy), "CARTOUCHE", 25)
        self.ligne((x + 140, y), (x + 140, y + 30), "CARTOUCHE", 25)
        self.texte(B.get("nom") or "Bureau d'études", x + 3, y + 51, 3.6)
        self.texte(f"{B.get('adresse', '')}  {B.get('telephone', '')}".strip() or " ", x + 3, y + 46.5, 2.0)
        self.texte(p.get("projet") or "Projet", x + 3, y + 37.5, 3.6)
        self.texte(f"{p.get('client') or ''}   {p.get('site') or ''}".strip() or " ", x + 3, y + 32.5, 2.2)
        self.texte(titre_feuille, x + 3, y + 21, 3.0)
        self.texte(f"Ingénieur : {B.get('ingenieur') or '—'}", x + 3, y + 16, 2.0)
        self.texte(f"Date : {self.date}    BAEL 91 rév. 99 / RPS 2011", x + 3, y + 5.5, 2.0)
        self.texte("Indice", x + 143, y + 24, 2.0)
        self.texte(p.get("indice") or "A", x + 165, y + 18, 6.0, MC)
        self.texte("Planche", x + 143, y + 9.5, 2.0)
        self.texte(f"{num:02d}", x + 165, y + 4.5, 4.0, MC)

    def ecartes(self, planche: Planche, liste: List[dict]):
        """Encadré : éléments non dessinés de la famille (à reprendre)."""
        if not liste:
            return
        x = planche.x0 + A1[0] - MARGE - CART_L
        y = planche.y0 + MARGE + CART_H + 6
        lignes = [f"{e['nom']}{' · ' + e['niveau'] if e.get('niveau') else ''} — {e['statut']}" for e in liste[:12]]
        if len(liste) > 12:
            lignes.append(f"… et {len(liste) - 12} autres")
        h = 8 + 3.6 * len(lignes)
        self.rect(x, y, CART_L, h, "ACIER_LONG", 35)
        self.texte("Non dessinés : à reprendre avant exécution", x + 3, y + h - 5, 2.6, BL, "ACIER_LONG")
        for i, t in enumerate(lignes):
            self.texte(t, x + 3, y + h - 9 - 3.6 * i, 2.0, BL, "TEXTE")


def _liste_elements(elements: List[str], largeur_car: int = 60) -> List[str]:
    """Liste d'éléments repliée sur plusieurs lignes."""
    lignes, cour = [], ""
    for el in elements:
        if len(cour) + len(el) + 2 > largeur_car:
            lignes.append(cour.rstrip(", "))
            cour = ""
        cour += el + ", "
    if cour:
        lignes.append(cour.rstrip(", "))
    return lignes


def _repartir(n: int, a: float, b: float) -> List[Tuple[float, float]]:
    """Positions de n barres dans un cadre a × b (coins d'abord, puis faces les plus longues)."""
    coins = [(0, 0), (a, 0), (a, b), (0, b)]
    reste = max(n - 4, 0)
    pts = coins[:min(n, 4)]
    if reste:
        long_x = a >= b
        par_face = [reste // 2 + reste % 2, reste // 2]
        for face, k in enumerate(par_face):
            for i in range(1, k + 1):
                f = i / (k + 1)
                if long_x:
                    pts.append((a * f, 0 if face == 0 else b))
                else:
                    pts.append((0 if face == 0 else a, b * f))
    return pts


# ── vues par famille (échelle : mm feuille par m réel) ──

def vue_poteau(D: Dessin, x, y, t: dict, mat: dict):
    e, r = t["rep"]["entree"], t["rep"]["resultat"]
    k = 100.0                                            # 1:10
    a, b = e["a_cm"] / 100 * k, e["b_cm"] / 100 * k
    c = mat.get("enrobage_poteau_mm", 30) / 1000 * k
    n, d = _barres(r["ferraillage"])
    cad = t["cadres"]
    ox, oy = x + 18, y - 22 - b
    D.rect(ox, oy, a, b, "COFFRAGE", 50)
    D.rect(ox + c, oy + c, a - 2 * c, b - 2 * c, "CADRES", 35)
    D.ligne((ox + c, oy + b - c), (ox + c + 5, oy + b - c - 5), "CADRES", 35)        # crochet 135°
    D.ligne((ox + c, oy + b - c), (ox + c + 5, oy + b - c - 1.5), "CADRES", 35)
    rb = max(d / 1000 * k / 2, 0.6)
    ib = c + cad["diametre_mm"] / 1000 * k + rb
    for (px, py) in _repartir(n, a - 2 * ib, b - 2 * ib):
        D.barre(ox + ib + px, oy + ib + py, rb)
    D.cote((ox, oy), (ox + a, oy), f"{e['a_cm']:g}")
    D.cote((ox, oy), (ox, oy + b), f"{e['b_cm']:g}")
    D.texte(f"{t['code']}  —  {e['a_cm']:g} × {e['b_cm']:g}", x + 4, y - 8, 4.0)
    tx = ox + a + 10
    D.texte(f"{n} HA{d}", tx, oy + b - 3, 2.8, BL, "ACIER_LONG")
    D.texte(f"Cadres HA{cad['diametre_mm']}", tx, oy + b - 9, 2.6, BL, "CADRES")
    D.texte(f"e = {cad['st_critique_m'] * 100:.0f} cm sur {cad['lc_m'] * 100:.0f} cm", tx, oy + b - 14, 2.2, BL, "CADRES")
    D.texte(f"en tête et pied, {cad['st_courant_m'] * 100:.0f} cm ailleurs", tx, oy + b - 18, 2.2, BL, "CADRES")
    D.texte(f"{cad['nombre']} cadres / niveau", tx, oy + b - 23, 2.2, BL, "CADRES")
    if d < 12:
        D.texte(f"%%c{d} < 12 mm : non conforme RPS 2011 (%%cl ≥ 12 mm) — à reprendre", x + 4, y - 14, 2.4, BL, "ACIER_LONG")
    for i, ligne in enumerate(_liste_elements(t["elements"], 70)[:4]):
        D.texte(ligne, x + 4, oy - 14 - 3.4 * i, 2.0)


def vue_poutre(D: Dessin, x, y, t: dict, mat: dict):
    e, r = t["rep"]["entree"], t["rep"]["resultat"]
    L = e.get("portee_m") or 5.0
    k = 20.0                                              # élévation 1:50
    hb = e["h_cm"] / 100 * k
    lw = L * k
    c = mat.get("enrobage_poutre_mm", 40) / 1000 * k
    n, d = _barres(r["ferraillage"])
    n_sup, d_sup = t["montage"]
    cad = t["cadres"]
    ox, oy = x + 18, y - 26 - hb
    D.rect(ox, oy, lw, hb, "COFFRAGE", 50)
    for px in (ox - 6, ox + lw):                          # appuis (poteaux)
        D.rect(px, oy - 8, 6, hb + 16, "COFFRAGE", 25)
    anc = 40 * d / 1000 * k
    D.ligne((ox - anc / 2, oy + c), (ox + lw + anc / 2, oy + c), "ACIER_LONG", 50)
    D.ligne((ox - anc / 2, oy + hb - c), (ox + lw + anc / 2, oy + hb - c), "ACIER_LONG", 35)
    lc = cad["lc_m"] * k
    xs, pos = [], 0.05 * k
    while pos <= lw - 0.05 * k + 1e-6:
        xs.append(pos)
        pas = cad["st_critique_m"] if (pos < lc or pos > lw - lc) else cad["st_courant_m"]
        pos += pas * k
    for xx in xs:
        D.ligne((ox + xx, oy + c * 0.6), (ox + xx, oy + hb - c * 0.6), "CADRES", 13)
    D.cote((ox, oy - 8), (ox + lw, oy - 8), f"{L:.2f} m", 4)
    D.texte(f"Cadres HA{cad['diametre_mm']}   zone critique {cad['lc_m'] * 100:.0f} cm : e = {cad['st_critique_m'] * 100:.0f} cm   —   "
            f"zone courante : e = {cad['st_courant_m'] * 100:.0f} cm", ox, oy + hb + 4, 2.2, BL, "CADRES")
    D.texte(f"{n} HA{d} (inf.)", ox + lw / 2, oy - 22, 2.6, TextEntityAlignment.BOTTOM_CENTER, "ACIER_LONG")
    D.texte(f"{n_sup} HA{d_sup} (montage)", ox + lw / 2, oy + hb + 9, 2.4, TextEntityAlignment.BOTTOM_CENTER, "ACIER_LONG")
    # coupe 1:20
    ks = 50.0
    bs, hs, cs = e["b_cm"] / 100 * ks, e["h_cm"] / 100 * ks, mat.get("enrobage_poutre_mm", 40) / 1000 * ks
    sx, sy = ox + lw + 22, oy + hb / 2 - hs / 2
    D.rect(sx, sy, bs, hs, "COFFRAGE", 50)
    D.rect(sx + cs, sy + cs, bs - 2 * cs, hs - 2 * cs, "CADRES", 35)
    rb = max(d / 1000 * ks / 2, 0.6)
    ib = cs + cad["diametre_mm"] / 1000 * ks + rb
    for i in range(n):
        px = ib + (bs - 2 * ib) * (i / (n - 1) if n > 1 else 0.5)
        D.barre(sx + px, sy + ib, rb)
    rs = max(d_sup / 1000 * ks / 2, 0.6)
    for i in range(n_sup):
        px = ib + (bs - 2 * ib) * (i / (n_sup - 1) if n_sup > 1 else 0.5)
        D.barre(sx + px, sy + hs - ib, rs)
    D.cote((sx, sy), (sx + bs, sy), f"{e['b_cm']:g}", 5)
    D.texte(f"{t['code']}  —  {e['b_cm']:g} × {e['h_cm']:g}   portée {L:.2f} m", x + 4, y - 8, 4.0)
    for i, ligne in enumerate(_liste_elements(t["elements"], 95)[:3]):
        D.texte(ligne, x + 4, oy - 30 - 3.4 * i, 2.0)


def vue_semelle(D: Dessin, x, y, t: dict, mat: dict):
    e, r = t["rep"]["entree"], t["rep"]["resultat"]
    k = 40.0                                              # 1:25
    A, B, H = r["A_m"] * k, r["B_m"] * k, r["H_m"] * k
    c = mat.get("enrobage_semelle_mm", 50) / 1000 * k
    nx, dx = _barres(r["choix_x"])
    ny, dy = _barres(r["choix_y"])
    a, b = (e.get("a_poteau_cm") or 30) / 100 * k, (e.get("b_poteau_cm") or 30) / 100 * k
    # vue en plan
    ox, oy = x + 18, y - 18 - B
    D.rect(ox, oy, A, B, "COFFRAGE", 50)
    D.rect(ox + A / 2 - a / 2, oy + B / 2 - b / 2, a, b, "COFFRAGE", 35)
    for i in range(nx):                                  # barres parallèles à A, réparties sur B
        yy = oy + c + (B - 2 * c) * (i / (nx - 1) if nx > 1 else 0.5)
        D.ligne((ox + c, yy), (ox + A - c, yy), "ACIER_LONG", 25)
    for i in range(ny):
        xx = ox + c + (A - 2 * c) * (i / (ny - 1) if ny > 1 else 0.5)
        D.ligne((xx, oy + c), (xx, oy + B - c), "ACIER_LONG", 18)
    D.cote((ox, oy), (ox + A, oy), f"A = {r['A_m']:.2f}", 5)
    D.cote((ox, oy), (ox, oy + B), f"B = {r['B_m']:.2f}", 5)
    # coupe
    sx, sy = ox + A + 26, oy + B / 2 - H / 2
    D.rect(sx - 2, sy - 2, A + 4, 2, "BETON_PROPRETE", 13)
    D.rect(sx, sy, A, H, "COFFRAGE", 50)
    fut = e.get("fut") or {}
    dispo = max((y - 12) - (sy + H), 14)                    # place au-dessus de la semelle dans la cellule
    h_fut = fut["hauteur_m"] * k if fut.get("hauteur_m") else None
    hf = min(h_fut, dispo) if h_fut else 14
    D.rect(sx + A / 2 - a / 2, sy + H, a, hf, "COFFRAGE", 35)
    if h_fut and h_fut > dispo:                              # fût plus haut que la place : coupure
        yc = sy + H + hf - 3
        D.ligne((sx + A / 2 - a / 2 - 2, yc - 1.5), (sx + A / 2 + a / 2 + 2, yc + 1.5), "COFFRAGE", 25)
    if fut.get("z_haut_m") is not None:
        D.niveau(sx + A / 2 + a / 2 + 4, sy + H + hf,
                 f"N.S. fût {cote_niveau(fut['z_haut_m'], True)}" + (f" (fût {fut['hauteur_m']:.2f} m)" if fut.get("hauteur_m") else ""))
    if fut.get("z_bas_m") is not None:
        D.niveau(sx + A + 4, sy + H, f"Dessus semelle {cote_niveau(fut['z_bas_m'], True)}")
    D.ligne((sx + c, sy + c), (sx + A - c, sy + c), "ACIER_LONG", 50)
    for xx in (sx + c, sx + A - c):
        D.ligne((xx, sy + c), (xx, sy + c + 10 * dx / 1000 * k), "ACIER_LONG", 50)
    n_a, d_a = t["attentes"]
    for xx in (sx + A / 2 - a / 2 + 2, sx + A / 2 + a / 2 - 2):
        D.ligne((xx, sy + c + 1), (xx, sy + H + min(hf, 14)), "ACIER_LONG", 35)
    D.cote((sx, sy), (sx, sy + H), f"H = {r['H_m']:.2f}", 5)
    D.texte(f"{t['code']}  —  {r['A_m']:.2f} × {r['B_m']:.2f} × {r['H_m']:.2f} m", x + 4, y - 8, 4.0)
    D.texte(f"X : {nx} HA{dx}    Y : {ny} HA{dy}    attentes {n_a} HA{d_a}", x + 4, oy - 16, 2.4, BL, "ACIER_LONG")
    for i, ligne in enumerate(_liste_elements(t["elements"], 70)[:2]):
        D.texte(ligne, x + 4, oy - 21 - 3.4 * i, 2.0)


def vue_voile(D: Dessin, x, y, t: dict, mat: dict):
    e = t["rep"]["entree"]
    L, h = e["longueur_m"], e.get("hauteur_m") or 3.0
    k = 20.0                                              # 1:50
    lw, hw = L * k, h * k
    s_v, s_h = t["espacements"]
    rive_n, rive_d = t["rive_barres"]
    ox, oy = x + 18, y - 20 - hw
    D.rect(ox, oy, lw, hw, "COFFRAGE", 50)
    xx = 0.03 * k
    while xx <= lw - 0.03 * k + 1e-6:
        D.ligne((ox + xx, oy), (ox + xx, oy + hw), "ACIER_LONG", 13)
        xx += s_v * k
    yy = 0.0
    while yy <= hw + 1e-6:
        D.ligne((ox, oy + yy), (ox + lw, oy + yy), "CADRES", 13)
        yy += s_h * k
    for bx in (ox + 2, ox + lw - 2):
        D.ligne((bx, oy), (bx, oy + hw), "ACIER_LONG", 70)
    D.cote((ox, oy), (ox + lw, oy), f"L = {L:.2f} m", 5)
    D.cote((ox, oy), (ox, oy + hw), f"{h:.2f}", 5)
    D.texte(f"{t['code']}  —  L = {L:.2f} m   e = {e['ep_cm']:g} cm", x + 4, y - 8, 4.0)
    D.texte(f"2 nappes HA10 : verticales e = {s_v * 100:.0f} cm, horizontales e = {s_h * 100:.0f} cm", x + 4, oy - 16, 2.4, BL, "ACIER_LONG")
    D.texte(f"Potelets de rive : {rive_n} HA{rive_d} à chaque extrémité", x + 4, oy - 20.5, 2.4, BL, "ACIER_LONG")
    for i, ligne in enumerate(_liste_elements(t["elements"], 80)[:2]):
        D.texte(ligne, x + 4, oy - 25 - 3.4 * i, 2.0)


def planches_famille(D: Dessin, fam: str, titre: str, sous_titre: str, cellule, vue, types, mat, ecartes):
    if not types.get(fam):
        return
    P = Planche(D, titre, sous_titre, cellule)
    D.ecartes(P, [e for e in ecartes if e["famille"] == fam])
    for t in types[fam]:
        pos = P.cellule()
        if pos is None:
            P = Planche(D, f"{titre} (suite)", sous_titre, cellule)
            pos = P.cellule()
        vue(D, pos[0], pos[1], t, mat)


def planche_nomenclature(D: Dessin, nomen: dict):
    P = Planche(D, "Nomenclature des aciers", "Poids : 7850 kg/m³ — longueurs façonnées, crochets et recouvrements compris", (0, 0))
    entetes = ["Type", "Rep.", "Désignation", "%%c", "Nb/élt", "Nb élts", "L unit. (m)", "L tot. (m)", "Poids (kg)"]
    larg = [16, 10, 92, 12, 16, 16, 22, 22, 22]
    x, y = P.x0 + MARGE + 10, P.y0 + A1[1] - MARGE - 40
    noms = {"poteaux": "Poteaux", "poutres": "Poutres", "semelles": "Semelles", "voiles": "Voiles", "dalles": "Dalles"}
    for fam, nom in noms.items():
        lignes = [l for l in nomen["lignes"] if l["famille"] == fam]
        if not lignes:
            continue
        rangs = [[l["type"], l["rep"], l["designation"], f"HA{l['diametre_mm']}", l["nombre"], l["nb_elements"],
                  f"{l['longueur_m']:.2f}", f"{l['longueur_totale_m']:.2f}", f"{l['poids_kg']:.1f}"] for l in lignes]
        besoin = 12 + 5.0 * (len(rangs) + 1)
        if y - besoin < P.y0 + MARGE + 10:
            x += sum(larg) + 15
            y = P.y0 + A1[1] - MARGE - 40
            if x + sum(larg) > P.x0 + A1[0] - MARGE:
                P = Planche(D, "Nomenclature des aciers (suite)", P.sous_titre, (0, 0))
                x, y = P.x0 + MARGE + 10, P.y0 + A1[1] - MARGE - 40
        total = round(sum(l["poids_kg"] for l in lignes), 1)
        D.texte(f"{nom} — {total:.1f} kg", x, y, 3.6)
        y = D.tableau(x, y - 3, entetes, larg, rangs, 5.0) - 10
    # récapitulatif par diamètre (au-dessus du cartouche)
    rx, ry = P.x0 + A1[0] - MARGE - CART_L, P.y0 + MARGE + CART_H + 12 + 6.0 * (len(nomen["par_diametre_kg"]) + 2)
    D.texte("Récapitulatif par diamètre", rx, ry + 2, 3.6)
    rangs = [[f"HA{d}", f"{poids_ml(d):.3f}", f"{kg:.1f}"] for d, kg in nomen["par_diametre_kg"].items()]
    rangs.append(["Total", "", f"{nomen['poids_total_kg']:.1f}"])
    D.tableau(rx, ry, ["%%c", "kg/m", "Poids (kg)"], [40, 50, 50], rangs, 6.0)


# ───────────────────────── plans de coffrage par niveau ─────────────────────────

def _xy_axe(axe: Optional[str], trame_x: Sequence[float], trame_y: Sequence[float]) -> Optional[Tuple[float, float]]:
    """Repère « B2 » → (x, y) sur la trame (lettre = file en Y, chiffre = file en X)."""
    m = re.match(r"([A-Z]+)(\d+)$", axe or "")
    if not m:
        return None
    j, i = indice_file(m.group(1)), int(m.group(2)) - 1
    if i >= len(trame_x) or j >= len(trame_y):
        return None
    return float(trame_x[i]), float(trame_y[j])


def _segment(e: dict, trame_x, trame_y) -> Optional[Tuple[float, float, float, float]]:
    """Extrémités en plan d'une poutre ou d'un voile : coordonnées lues, sinon nom « Pt A1-A2 » sur la trame."""
    if all(e.get(k) is not None for k in ("x1_m", "y1_m", "x2_m", "y2_m")):
        return float(e["x1_m"]), float(e["y1_m"]), float(e["x2_m"]), float(e["y2_m"])
    m = re.search(r"([A-Z]+\d+)-([A-Z]+\d+)$", e.get("nom") or "")
    if m:
        a, b = _xy_axe(m.group(1), trame_x, trame_y), _xy_axe(m.group(2), trame_x, trame_y)
        if a and b:
            return a[0], a[1], b[0], b[1]
    return None


def texte_armature_dalle(e: dict, r: Optional[dict]) -> str:
    """Armatures d'une dalle en clair : treillis, ou nappes HA du calcul, ou ce qui a été saisi."""
    r = r or {}
    if r.get("treillis"):
        return r["treillis"]["designation"] + " (nappe inférieure)"
    rr = r.get("resultats") or {}
    morceaux = [f"{lib} {(rr.get(k) or {}).get('ferraillage', {}).get('choix')}"
                for k, lib in (("x_travee", "sens lx"), ("y_travee", "sens ly"), ("appuis", "chapeaux"))
                if (rr.get(k) or {}).get("ferraillage", {}).get("choix")]
    if morceaux:
        return " ; ".join(morceaux)
    if e.get("armature") == "treillis" and e.get("ts_diametre_mm") and e.get("ts_maille_cm"):
        return f"TS Ø{e['ts_diametre_mm']:g} maille {e['ts_maille_cm']:g} × {e['ts_maille_cm']:g} cm (saisi)"
    return "armatures à calculer"


def _boite(e: dict) -> Optional[Tuple[float, float, float, float]]:
    if all(e.get(k) is not None for k in ("xmin_m", "ymin_m", "xmax_m", "ymax_m")):
        return (float(e["xmin_m"]), float(e["ymin_m"]), float(e["xmax_m"]), float(e["ymax_m"]))
    return None


def elements_niveau(lot: dict, dalles: Sequence[dict], trame_x, trame_y,
                    codes: Dict[int, str]) -> Tuple["OrderedDict[str, List[dict]]", List[dict]]:
    """Éléments placés en plan, rangés par niveau (ordre du bâtiment), et éléments sans position connue.

    Un plan de coffrage « plancher haut N » montre les poteaux et voiles du niveau N (coupés) et les
    poutres et panneaux du plancher qui les couvre (même libellé de niveau dans l'extraction). Le niveau
    « Fondation » réunit semelles, fûts, longrines, chaînages, poutres et dalles du plancher bas.
    Les éléments non vérifiés sont dessinés (la géométrie est connue) mais repérés par leur nom suivi de « * ».
    """
    ordre: List[str] = []
    z_niv: Dict[str, float] = {}

    def vu(n, z):
        if n and n not in ordre:
            ordre.append(n)
        if n and z is not None:
            z_niv[n] = min(z_niv.get(n, float("inf")), float(z))

    for fam in ("poteaux", "voiles", "poutres"):
        for l in lot.get(fam) or []:
            e = l.get("entree") or {}
            vu(l.get("niveau") or e.get("niveau"), e.get("z_m") if fam != "poutres" else None)
    if lot.get("semelles"):
        vu("Fondation", None)
    for l in lot.get("dalles") or []:
        vu(l.get("niveau") or (l.get("entree") or {}).get("niveau"), None)
    for d in dalles:
        vu(d.get("niveau"), None)
    # de bas en haut : par altitude quand le modèle la donne (libellés Robot quelconques), sinon par libellé
    ordre = trier_niveaux(ordre, z_niv)
    par_niveau: "OrderedDict[str, List[dict]]" = OrderedDict((n, []) for n in ordre)
    sans_position: List[dict] = []

    def etiquette(l):
        return codes.get(id(l)) or f"{l.get('nom')}*"

    for l in lot.get("poteaux") or []:
        e = l.get("entree") or {}
        xy = (float(e["x_m"]), float(e["y_m"])) if e.get("x_m") is not None and e.get("y_m") is not None \
            else _xy_axe(l.get("axe") or e.get("axe"), trame_x, trame_y)
        if xy is None or not e.get("a_cm") or not e.get("b_cm"):
            sans_position.append({"famille": "poteaux", "nom": l.get("nom"), "niveau": l.get("niveau"), "statut": "position inconnue"})
            continue
        par_niveau[l.get("niveau")].append({"genre": "poteau", "role": e.get("role") or "poteau", "x": xy[0], "y": xy[1],
                                            "a": e["a_cm"], "b": e["b_cm"], "code": etiquette(l), "verifie": id(l) in codes})
    for fam, genre, ep in (("poutres", "poutre", "b_cm"), ("voiles", "voile", "ep_cm")):
        for l in lot.get(fam) or []:
            e = l.get("entree") or {}
            seg = _segment(e, trame_x, trame_y)
            if seg is None or not e.get(ep):
                sans_position.append({"famille": fam, "nom": l.get("nom"), "niveau": l.get("niveau"), "statut": "position inconnue"})
                continue
            el = {"genre": genre, "seg": seg, "ep": e[ep], "h": e.get("h_cm"), "code": etiquette(l), "verifie": id(l) in codes}
            if genre == "poutre":
                el["categorie"] = e.get("categorie") or "poutre"
            par_niveau[l.get("niveau")].append(el)
    for l in lot.get("semelles") or []:
        e, r = l.get("entree") or {}, l.get("resultat") or {}
        xy = (float(e["x_m"]), float(e["y_m"])) if e.get("x_m") is not None and e.get("y_m") is not None \
            else _xy_axe(l.get("axe") or e.get("axe"), trame_x, trame_y)
        if xy is None:
            sans_position.append({"famille": "semelles", "nom": l.get("nom"), "niveau": "Fondation", "statut": "position inconnue"})
            continue
        par_niveau["Fondation"].append({"genre": "semelle", "x": xy[0], "y": xy[1], "A": r.get("A_m"), "B": r.get("B_m"),
                                        "a": e.get("a_poteau_cm"), "b": e.get("b_poteau_cm"), "axe": l.get("axe"),
                                        "fut": e.get("fut") or {}, "code": etiquette(l), "verifie": id(l) in codes})
    calculees = set()
    for l in lot.get("dalles") or []:
        e = l.get("entree") or {}
        calculees.add(e.get("id"))
        boite = _boite(e)
        niv = l.get("niveau") or e.get("niveau")
        if boite is None or not niv:
            sans_position.append({"famille": "dalles", "nom": l.get("nom"), "niveau": niv, "statut": "position inconnue"})
            continue
        par_niveau[niv].append({"genre": "dalle", "role": e.get("role"), "appui": e.get("appui"), "box": boite,
                                "contour": e.get("contour_m"), "rectangulaire": e.get("rectangulaire", True),
                                "h": e.get("h_cm"), "armature": texte_armature_dalle(e, l.get("resultat")),
                                "code": etiquette(l), "verifie": id(l) in codes})
    for d in dalles:
        if d.get("id") is not None and d.get("id") in calculees:
            continue                                   # déjà placée avec son calcul
        if any(d.get(k) is None for k in ("xmin_m", "xmax_m", "ymin_m", "ymax_m")) or not d.get("niveau"):
            sans_position.append({"famille": "dalles", "nom": d.get("nom"), "niveau": d.get("niveau"), "statut": "position inconnue"})
            continue
        par_niveau[d["niveau"]].append({"genre": d.get("type") or "dalle", "role": d.get("role"),
                                        "box": (d["xmin_m"], d["ymin_m"], d["xmax_m"], d["ymax_m"]),
                                        "contour": d.get("contour_m"), "rectangulaire": d.get("rectangulaire", True),
                                        "h": d.get("h_cm"), "code": d.get("nom") or "D", "verifie": True})
    return par_niveau, sans_position


def _signature(elements: List[dict]) -> tuple:
    """Deux niveaux de même signature ont le même plan de coffrage (mêmes éléments, mêmes sections, mêmes types)."""
    def cle(el):
        g = [el.get("x"), el.get("y")] + list(el.get("seg") or ()) + list(el.get("box") or ())
        return (el["genre"], tuple(round(v, 2) for v in g if v is not None), el.get("a"), el.get("b"),
                el.get("ep"), el.get("h"), el["code"])
    return tuple(sorted((cle(el) for el in elements), key=repr))


def regrouper_niveaux(par_niveau: "OrderedDict[str, List[dict]]") -> List[Tuple[List[str], List[dict]]]:
    """Niveaux consécutifs identiques regroupés (étage courant) ; un niveau vide n'a pas de planche."""
    groupes: List[Tuple[List[str], List[dict]]] = []
    prec = None
    for niv, els in par_niveau.items():
        if not els:
            prec = None
            continue
        sig = _signature(els)
        if groupes and sig == prec:
            groupes[-1][0].append(niv)
        else:
            groupes.append(([niv], els))
        prec = sig
    return groupes


def titre_coffrage(niveaux: List[str]) -> str:
    if niveaux == ["Fondation"]:
        return "Coffrage niveau fondation"
    nom = niveaux[0] if len(niveaux) == 1 else f"{niveaux[0]} à {niveaux[-1]}"
    return f"Coffrage plancher haut {nom}"


DISPO_PLAN = (A1[0] - 2 * MARGE - 230 - 80, A1[1] - 2 * MARGE - 40 - 70)   # zone de dessin d'une planche (mm)
ECHELLE_MAX_COFFRAGE = 100        # au-delà, le plan est découpé en parties plutôt que réduit (lisibilité des sections)


def _etendue(els: List[dict], trame_x: Sequence[float], trame_y: Sequence[float]) -> Tuple[float, float, float, float]:
    xs = list(trame_x) + [el["x"] for el in els if "x" in el]
    ys = list(trame_y) + [el["y"] for el in els if "y" in el]
    for el in els:
        if "seg" in el:
            xs += [el["seg"][0], el["seg"][2]]; ys += [el["seg"][1], el["seg"][3]]
        if "box" in el:
            xs += [el["box"][0], el["box"][2]]; ys += [el["box"][1], el["box"][3]]
    return min(xs), max(xs), min(ys), max(ys)


def _dans(el: dict, f: Tuple[float, float, float, float], tol: float = 0.05) -> bool:
    """L'élément touche la fenêtre (x0, x1, y0, y1) : il est dessiné sur cette partie."""
    x0, x1, y0, y1 = f
    if "x" in el:
        pts = [(el["x"], el["y"])]
    elif "seg" in el:
        a, b, c, d = el["seg"]
        if max(a, c) < x0 - tol or min(a, c) > x1 + tol or max(b, d) < y0 - tol or min(b, d) > y1 + tol:
            return False
        return True
    else:
        a, b, c, d = el["box"]
        return not (c < x0 - tol or a > x1 + tol or d < y0 - tol or b > y1 + tol)
    return all(x0 - tol <= x <= x1 + tol and y0 - tol <= y <= y1 + tol for x, y in pts)


def decouper_plan(els: List[dict], trame_x: Sequence[float], trame_y: Sequence[float]) -> Tuple[int, List[tuple]]:
    """Échelle et fenêtres du plan. Le plan tient sur une planche jusqu'au 1:100 ; sinon il est découpé
    en parties suivant sa plus grande dimension, aux files de la trame les plus proches (repères conservés)."""
    x0, x1, y0, y1 = _etendue(els, trame_x, trame_y)
    ex, ey = (x1 - x0) or 1.0, (y1 - y0) or 1.0
    dl, dh = DISPO_PLAN
    for ech in (50, ECHELLE_MAX_COFFRAGE):
        if ex * 1000 / ech <= dl and ey * 1000 / ech <= dh:
            return ech, [(x0, x1, y0, y1)]
    ech = ECHELLE_MAX_COFFRAGE
    if ey * 1000 / ech > dh and ey / dh >= ex / dl:          # découpe suivant Y
        n = math.ceil(ey * 1000 / ech / dh)
        coupes = _coupes(y0, y1, n, trame_y)
        if ex * 1000 / ech > dl:                              # trop large aussi : échelle 1:200
            ech = 200
        return ech, [(x0, x1, a, b) for a, b in zip(coupes, coupes[1:])]
    n = math.ceil(ex * 1000 / ech / dl)
    coupes = _coupes(x0, x1, n, trame_x)
    if ey * 1000 / ech > dh:
        ech = 200
    return ech, [(a, b, y0, y1) for a, b in zip(coupes, coupes[1:])]


def _coupes(a: float, b: float, n: int, files: Sequence[float]) -> List[float]:
    """n parties égales entre a et b, chaque coupe ramenée sur la file la plus proche."""
    coupes = [a]
    for k in range(1, n):
        v = a + (b - a) * k / n
        v = min(files, key=lambda f: abs(f - v)) if files else v
        if coupes[-1] < v < b:
            coupes.append(v)
    return coupes + [b]


def _legende(D: Dessin, P: Planche, els: List[dict]):
    """Légende des représentations présentes sur la planche (en bas à gauche, hors du dessin)."""
    cats = {el.get("categorie") for el in els if el["genre"] == "poutre"}
    roles = {el.get("role") for el in els if el["genre"] == "poteau"}
    genres = {el["genre"] for el in els}
    items = [(c, CATEGORIES_POUTRE[c]["libelle"] + (" (sous plancher, en tireté)" if c == "poutre" else ""))
             for c in ("poutre", "longrine", "chainage") if c in cats]
    items += [(r_, "Fût de poteau (coupé)" if r_ == "fut" else "Poteau (coupé)") for r_ in ("fut", "poteau") if r_ in roles]
    items += [(g, lib) for g, lib in (("voile", "Voile (coupé)"), ("semelle", "Semelle"), ("dalle", "Dalle / dallage"))
              if g in genres]
    if not items:
        return
    x, y = P.x0 + MARGE + 10, P.y0 + MARGE + 6
    D.texte("Légende :", x, y + 0.5, 2.6)
    x += 20
    for code, lib in items:
        pts = [(x, y), (x + 14, y), (x + 14, y + 5), (x, y + 5)]
        if code in STYLE_POUTRE:
            calque, trait, motif = STYLE_POUTRE[code]
            D.ligne(pts[0], pts[1], calque, 35, trait)
            D.ligne(pts[3], pts[2], calque, 35, trait)
            if motif:
                D.ligne(pts[1], pts[2], calque, 35)
                D.ligne(pts[3], pts[0], calque, 35)
                D.hachure(pts, motif, 0.6, calque, CALQUES[calque])
        elif code in ("fut", "poteau", "voile"):
            D.rect(x, y, 14, 5, "COFFRAGE", 35)
            D.hachure(pts, None, calque="COFFRAGE", couleur=7 if code != "voile" else 8)
        elif code == "semelle":
            D.rect(x, y, 14, 5, "SEMELLES", 35)
        else:
            D.rect(x, y, 14, 5, "BETON_PROPRETE", 18)
            D.ligne(pts[0], pts[2], "BETON_PROPRETE", 13)
        D.texte(lib, x + 16, y + 1, 2.2)
        x += 16 + 1.45 * len(lib) + 8


def _tableaux_fondation(D: Dessin, tx: float, ty: float, els: List[dict], types: Dict[str, List[dict]]) -> float:
    """Tableaux du plan de fondation : semelles, fûts (niveau supérieur, US4), éléments du plancher bas."""
    def unique(vals, fmt):
        vs = sorted({round(v, 3) for v in vals if v is not None})
        return fmt(vs[0]) if len(vs) == 1 else ("variable" if vs else "—")

    rangs = []
    for t in types.get("semelles", [])[:20]:
        r = t["rep"]["resultat"]
        x_, y_ = _barres(r["choix_x"]), _barres(r["choix_y"])
        nsf = unique([(l["entree"].get("fut") or {}).get("z_haut_m") for l in t["lignes"]], lambda v: cote_niveau(v, True))
        rangs.append([t["code"], len(t["lignes"]), f"{r['A_m']:.2f}", f"{r['B_m']:.2f}", f"{r['H_m']:.2f}",
                      f"{x_[0]} HA{x_[1]}", f"{y_[0]} HA{y_[1]}", nsf])
    if rangs:
        D.texte("Tableau des semelles", tx, ty, 4.0)
        ty = D.tableau(tx, ty - 5, ["Type", "Nb", "A (m)", "B (m)", "H (m)", "Nappe X", "Nappe Y", "N.S. fût"],
                       [16, 10, 18, 18, 18, 26, 26, 22], rangs, 5.5) - 10
    # fûts : modélisés (tronçons de poteau sous le plancher bas) ou non modélisés (appui au niveau du plancher bas)
    rangs = []
    codes_fut = {(round(el["x"], 2), round(el["y"], 2)): el["code"] for el in els
                 if el["genre"] == "poteau" and el.get("role") == "fut"}
    groupes: "OrderedDict[tuple, List[str]]" = OrderedDict()
    for el in els:
        f = el.get("fut") or {}
        if el["genre"] != "semelle" or f.get("z_haut_m") is None:
            continue
        cle = (el.get("a"), el.get("b"), f.get("z_bas_m"), f["z_haut_m"], f.get("hauteur_m"))
        groupes.setdefault(cle, []).append(codes_fut.get((round(el["x"], 2), round(el["y"], 2)), "—"))
    for (a, b, zb, zh, hf), codes_ in list(groupes.items())[:20]:
        rangs.append([", ".join(sorted(set(codes_)))[:14], len(codes_), f"{a:g} × {b:g}" if a and b else "—",
                      cote_niveau(zb, True) if zb is not None else "selon assise", cote_niveau(zh, True),
                      f"{hf:.2f}" if hf is not None else "non modélisé"])
    if rangs:
        D.texte("Fûts de poteaux — niveau supérieur (N.S.)", tx, ty, 4.0)
        ty = D.tableau(tx, ty - 5, ["Type", "Nb", "Section (cm)", "Dessus sem.", "N.S. fût", "Haut. (m)"],
                       [16, 10, 34, 30, 30, 34], rangs, 5.5) - 6
        if any(x[-1] == "non modélisé" for x in rangs):
            D.texte("Fûts non modélisés : le poteau part de l'appui du modèle ; hauteur selon le niveau d'assise", tx, ty, 2.2)
            D.texte("des semelles (rapport géotechnique).", tx, ty - 3.4, 2.2)
            ty -= 8
        ty -= 4
    comptes: "OrderedDict[tuple, int]" = OrderedDict()
    for el in els:
        if el["genre"] == "poutre":
            cle = (CATEGORIES_POUTRE[el.get("categorie") or "poutre"]["libelle"], el["code"],
                   f"{el['ep']:g} × {el['h']:g}" if el.get("h") else f"b = {el['ep']:g}")
        elif el["genre"] in ("dalle", "balcon"):
            nature = "Dallage" if el.get("appui") == "terre_plein" else ("Dalle de fondation" if el.get("role") == "fondation" else "Dalle")
            cle = (nature, el["code"], f"e = {el['h']:g}" if el.get("h") else "—")
        else:
            continue
        comptes[cle] = comptes.get(cle, 0) + 1
    if comptes:
        D.texte("Éléments du plancher bas", tx, ty, 4.0)
        ty = D.tableau(tx, ty - 5, ["Élément", "Type", "Section (cm)", "Nb"], [48, 34, 70, 22],
                       [[a, b, c, n] for (a, b, c), n in list(comptes.items())[:30]], 5.0) - 6
    D.texte("Cotes de niveau en mètres : Z du modèle Robot (±0,00 = Z 0).", tx, ty, 2.2)
    return ty - 4


def planche_coffrage(D: Dessin, niveaux: List[str], els: List[dict], trame_x: Sequence[float], trame_y: Sequence[float],
                     ech: Optional[int] = None, fenetre: Optional[tuple] = None, partie: Optional[Tuple[int, int]] = None,
                     types: Optional[Dict[str, List[dict]]] = None):
    fondation = niveaux == ["Fondation"]
    if fenetre is None:
        ech, fen = decouper_plan(els, trame_x, trame_y)
        fenetre = fen[0]
    fx0, fx1, fy0, fy1 = fenetre
    tol = 0.05
    # files visibles sur cette partie, avec leur repère d'origine
    ax_x = [(i, v) for i, v in enumerate(trame_x) if fx0 - tol <= v <= fx1 + tol]
    ax_y = [(j, v) for j, v in enumerate(trame_y) if fy0 - tol <= v <= fy1 + tol]
    trame_x, trame_y = [v for _, v in ax_x], [v for _, v in ax_y]
    ox, x1_, oy, y1_ = _etendue(els, trame_x, trame_y)
    ex, ey = (x1_ - ox) or 1.0, (y1_ - oy) or 1.0
    dispo_l, dispo_h = DISPO_PLAN
    k = 1000.0 / ech
    if fondation:
        titre = "Plan de fondation"
        sous = (f"Semelles, fûts, longrines, chaînages et dalles du plancher bas — échelle 1:{ech} — cotes en mètres, "
                "niveaux : Z du modèle")
    else:
        titre = titre_coffrage(niveaux)
        sous = (f"Niveaux {', '.join(niveaux)} identiques — " if len(niveaux) > 1 else "") + \
            f"poteaux et voiles coupés, poutres en tireté — échelle 1:{ech} — cotes en mètres"
    titre += f" — partie {partie[0]}/{partie[1]}" if partie and partie[1] > 1 else ""
    if partie and partie[1] > 1 and ax_x and ax_y:
        sous = f"Files {ax_x[0][0] + 1}-{ax_x[-1][0] + 1} / {lettre_file(ax_y[0][0])}-{lettre_file(ax_y[-1][0])} — " + sous
    P = Planche(D, titre, sous, (0, 0))
    gx = P.x0 + MARGE + 40 + (dispo_l - ex * k) / 2
    gy = P.y0 + MARGE + 45 + (dispo_h - ey * k) / 2

    def pt(x, y):
        return gx + (x - ox) * k, gy + (y - oy) * k

    # trame : axes repérés et cotés
    if trame_x and trame_y:
        _, yb = pt(0, min(trame_y)); _, yh = pt(0, max(trame_y))
        xg, _ = pt(min(trame_x), 0); xd, _ = pt(max(trame_x), 0)
        for i, xv in ax_x:
            px, _ = pt(xv, 0)
            D.ligne((px, yb - 15), (px, yh + 15), "AXES", 13, "DASHDOT")
            D.msp.add_circle((px, yh + 21), 4.5, dxfattribs={"layer": "AXES"})
            D.texte(str(i + 1), px, yh + 21, 3.8, MC, "AXES")
        for j, yv in ax_y:
            _, py = pt(0, yv)
            D.ligne((xg - 15, py), (xd + 15, py), "AXES", 13, "DASHDOT")
            D.msp.add_circle((xg - 21, py), 4.5, dxfattribs={"layer": "AXES"})
            D.texte(lettre_file(j), xg - 21, py, 3.8, MC, "AXES")
        for i in range(len(trame_x) - 1):
            D.cote((pt(trame_x[i], 0)[0], yb - 18), (pt(trame_x[i + 1], 0)[0], yb - 18), f"{trame_x[i + 1] - trame_x[i]:.2f}", 4)
        for j in range(len(trame_y) - 1):
            D.cote((xd + 30, pt(0, trame_y[j])[1]), (xd + 30, pt(0, trame_y[j + 1])[1]), f"{trame_y[j + 1] - trame_y[j]:.2f}", -4)

    def bande(x1, y1, x2, y2, larg_m, calque, type_trait=None, remplir=False, motif=None):
        """Bande de largeur larg_m centrée sur le segment (poutre, voile)."""
        (a1, b1), (a2, b2) = pt(x1, y1), pt(x2, y2)
        lg = math.hypot(a2 - a1, b2 - b1) or 1.0
        nx, ny = -(b2 - b1) / lg * larg_m * k / 2, (a2 - a1) / lg * larg_m * k / 2
        coins = [(a1 + nx, b1 + ny), (a2 + nx, b2 + ny), (a2 - nx, b2 - ny), (a1 - nx, b1 - ny)]
        D.ligne(coins[0], coins[1], calque, 35, type_trait)
        D.ligne(coins[3], coins[2], calque, 35, type_trait)
        if remplir:
            D.ligne(coins[1], coins[2], calque, 35)
            D.ligne(coins[3], coins[0], calque, 35)
            D.hachure(coins, motif, min(0.8, max(0.45, larg_m * k / 9.5)), calque, CALQUES.get(calque, 8) if motif else 8)
        lg_n = math.hypot(nx, ny) or 1.0
        bande.decalage = (nx / lg_n * (larg_m * k / 2 + 1.2), ny / lg_n * (larg_m * k / 2 + 1.2))
        return (a1 + a2) / 2, (b1 + b2) / 2, math.degrees(math.atan2(b2 - b1, a2 - a1))

    def texte_tourne(t, x, y, angle):
        if 90 < angle % 360 <= 270:
            angle -= 180
        D.msp.add_text(str(t).replace("Ø", "%%c"), height=2.4,
                       dxfattribs={"layer": "TEXTE", "style": "BNAY", "rotation": angle}).set_placement(
            (x, y), align=TextEntityAlignment.BOTTOM_CENTER)

    for el in els:                       # panneaux d'abord, sous le reste
        if "box" in el:
            (a1, b1), (a2, b2) = pt(el["box"][0], el["box"][1]), pt(el["box"][2], el["box"][3])
            if el.get("contour") and not el.get("rectangulaire", True):     # panneau en L, trapèze… : son vrai contour
                D.msp.add_lwpolyline([pt(x, y) for x, y in el["contour"]], close=True,
                                     dxfattribs={"layer": "BETON_PROPRETE", "lineweight": 18})
            else:
                D.rect(a1, b1, a2 - a1, b2 - b1, "BETON_PROPRETE", 18)
                D.ligne((a1, b1), (a2, b2), "BETON_PROPRETE", 13)
            if el.get("role") == "fondation":
                nature = "dallage" if el.get("appui") == "terre_plein" else "dalle pleine"
            else:
                nature = "balcon" if el["genre"] == "balcon" else "dalle"
            D.texte(f"{el['code']} — {nature}" + (f" h = {el['h']:g} cm" if el.get("h") else ""),
                    (a1 + a2) / 2, (b1 + b2) / 2 + 3, 2.6, MC, "TEXTE")
            if el.get("armature"):
                D.texte(el["armature"], (a1 + a2) / 2, (b1 + b2) / 2 - 1.5, 2.0, MC, "TEXTE")
    xy_poteaux = {(round(el["x"], 2), round(el["y"], 2)) for el in els if el["genre"] == "poteau"}
    for el in els:                       # semelles sous les poteaux
        if el["genre"] != "semelle":
            continue
        cx, cy = pt(el["x"], el["y"])
        A, B = (el.get("A") or 0) * k, (el.get("B") or 0) * k
        if A and B:
            D.rect(cx - A / 2, cy - B / 2, A, B, "SEMELLES", 50)
        a, b = (el.get("a") or 0) / 100 * k, (el.get("b") or 0) / 100 * k
        if a and b and (round(el["x"], 2), round(el["y"], 2)) not in xy_poteaux:     # amorce : poteau partant de l'appui
            coins = [(cx - a / 2, cy - b / 2), (cx + a / 2, cy - b / 2), (cx + a / 2, cy + b / 2), (cx - a / 2, cy + b / 2)]
            D.rect(cx - a / 2, cy - b / 2, a, b, "COFFRAGE", 50)
            D.hachure(coins, None, calque="COFFRAGE", couleur=7)
        dx, dy = max(A, a) / 2 + 1.5, max(B, b) / 2 + 1.5
        D.texte(f"{el['code']} ({el.get('axe') or ''})", cx + dx, cy + dy, 2.6, BL, "TEXTE")
        z = (el.get("fut") or {}).get("z_haut_m")
        if z is not None:                # niveau supérieur du fût (US4)
            D.texte(f"N.S. fût {cote_niveau(z, True)}", cx + dx, cy - dy - 2.4, 2.0, BL, "NIVEAUX")
    for el in els:
        if el["genre"] == "poutre":
            calque, trait, motif = STYLE_POUTRE.get(el.get("categorie") or "poutre", STYLE_POUTRE["poutre"])
            x, y, ang = bande(*el["seg"], el["ep"] / 100, calque, trait, remplir=bool(motif), motif=motif)
            if motif:                    # bande hachurée : le repère se lit à côté, pas dessus
                dx_, dy_ = bande.decalage
                if dy_ < 0 or (abs(dy_) < 1e-9 and dx_ < 0):
                    dx_, dy_ = -dx_, -dy_
                x, y = x + dx_, y + dy_ - 1
            texte_tourne(f"{el['code']} {el['ep']:g}×{el['h']:g}" if el.get("h") else el["code"], x, y + 1, ang)
        elif el["genre"] == "voile":
            x, y, ang = bande(*el["seg"], el["ep"] / 100, "COFFRAGE", None, remplir=True)
            texte_tourne(f"{el['code']} ép. {el['ep']:g}", x + 3, y, ang)
    for el in els:
        if el["genre"] == "poteau":
            cx, cy = pt(el["x"], el["y"])
            a, b = el["a"] / 100 * k, el["b"] / 100 * k
            coins = [(cx - a / 2, cy - b / 2), (cx + a / 2, cy - b / 2), (cx + a / 2, cy + b / 2), (cx - a / 2, cy + b / 2)]
            D.rect(cx - a / 2, cy - b / 2, a, b, "COFFRAGE", 50)
            D.hachure(coins, None, calque="COFFRAGE", couleur=7)
            if fondation:                # le repère de la semelle est en haut à droite : le fût à gauche
                D.texte(f"{el['code']} {el['a']:g}×{el['b']:g}", cx - a / 2 - 1.2, cy + b / 2 + 1.2, 2.2,
                        TextEntityAlignment.BOTTOM_RIGHT, "TEXTE")
            else:
                D.texte(f"{el['code']} {el['a']:g}×{el['b']:g}", cx + a / 2 + 1.2, cy + b / 2 + 1.2, 2.4, BL, "TEXTE")
    _legende(D, P, els)

    tx = P.x0 + A1[0] - MARGE - 190
    ty = P.y0 + A1[1] - MARGE - 40
    if fondation:
        _tableaux_fondation(D, tx, ty, els, types or {})
        if any(not el["verifie"] for el in els):
            D.texte("* élément non vérifié : type non attribué, à reprendre avant exécution.", tx, P.y0 + MARGE + CART_H + 8,
                    2.4, BL, "ACIER_LONG")
        return P
    # tableau des éléments du plancher, à droite
    comptes: "OrderedDict[tuple, int]" = OrderedDict()
    noms = {"poteau": "Poteau", "poutre": "Poutre", "voile": "Voile", "dalle": "Dalle", "balcon": "Balcon"}
    for el in sorted(els, key=lambda e: list(noms).index(e["genre"]) if e["genre"] in noms else 9):
        if el["genre"] == "poteau":
            sec = f"{el['a']:g} × {el['b']:g}"
        elif el["genre"] in ("poutre", "voile"):
            sec = f"{el['ep']:g} × {el['h']:g}" if el.get("h") else f"ép. {el['ep']:g}"
        else:
            sec = f"h = {el['h']:g}" if el.get("h") else "—"
        nom = noms.get(el["genre"], el["genre"])
        if el["genre"] == "poutre":
            nom = CATEGORIES_POUTRE[el.get("categorie") or "poutre"]["libelle"]
        elif el["genre"] == "poteau" and el.get("role") == "fut":
            nom = "Fût"
        cle = (nom, el["code"], sec)
        comptes[cle] = comptes.get(cle, 0) + 1
    D.texte("Éléments du plancher" + (" (par niveau)" if len(niveaux) > 1 else ""), tx, ty, 4.0)
    rangs = [[g, c, s_, n] for (g, c, s_), n in list(comptes.items())[:60]]
    yfin = D.tableau(tx, ty - 5, ["Élément", "Type", "Section (cm)", "Nb"], [40, 50, 60, 20], rangs, 5.0)
    if any(not el["verifie"] for el in els):
        D.texte("* élément non vérifié : type non attribué, à reprendre avant exécution.", tx, yfin - 6, 2.4, BL, "ACIER_LONG")
    return P


def planches_coffrage(D: Dessin, lot: dict, types: Dict[str, List[dict]], dalles: Sequence[dict],
                      trame_x: Sequence[float], trame_y: Sequence[float], apres_fondation=None) -> Tuple[List[List[str]], int]:
    """Plan de fondation (niveau Fondation, découpé si nécessaire), puis une planche de coffrage par niveau
    (niveaux identiques regroupés). Renvoie (groupes de niveaux des plans de coffrage, planches du plan de fondation)."""
    codes = {id(l): t["code"] for liste in types.values() for t in liste for l in t["lignes"]}
    par_niveau, sans_position = elements_niveau(lot, dalles, list(trame_x), list(trame_y), codes)
    groupes = regrouper_niveaux(par_niveau)
    fondation = [g for g in groupes if g[0] == ["Fondation"]]
    coffrages = [g for g in groupes if g[0] != ["Fondation"]]
    etat = {"premiere": True, "fondation": 0}

    def dessiner(niveaux, els):
        ech, fenetres = decouper_plan(els, list(trame_x), list(trame_y))
        for n, f in enumerate(fenetres, start=1):
            sous_els = [el for el in els if _dans(el, f)]
            P = planche_coffrage(D, niveaux, sous_els, list(trame_x), list(trame_y), ech, f, (n, len(fenetres)), types)
            if niveaux == ["Fondation"]:
                etat["fondation"] += 1
            if etat["premiere"] and sans_position:
                D.ecartes(P, sans_position)
            etat["premiere"] = False

    for niveaux, els in fondation:
        dessiner(niveaux, els)
    if apres_fondation:
        apres_fondation()
    for niveaux, els in coffrages:
        dessiner(niveaux, els)
    if not groupes and sans_position:
        P = Planche(D, "Coffrage — éléments sans position", "Positions en plan inconnues : plans de coffrage impossibles", (0, 0))
        D.ecartes(P, sans_position)
    return [n for n, _ in coffrages], etat["fondation"]


# ───────────────────────── coupe transversale du dallage de fondation (US3) ─────────────────────────

# motif de hachure et échelle (feuille en mm) par nature de couche, d'après sa désignation
MOTIFS_COUCHE = (("hérisson", "GRAVEL", 0.15), ("herisson", "GRAVEL", 0.15), ("gravier", "GRAVEL", 0.15),
                 ("tout-venant", "GRAVEL", 0.15), ("propreté", "AR-CONC", 0.03), ("proprete", "AR-CONC", 0.03),
                 ("béton", "AR-CONC", 0.05), ("beton", "AR-CONC", 0.05), ("sable", "AR-SAND", 0.05),
                 ("isol", "ANSI37", 0.8), ("polyst", "ANSI37", 0.8), ("terre", "EARTH", 0.8), ("remblai", "EARTH", 0.8))


def _motif_couche(nom: str) -> Tuple[str, float]:
    n = (nom or "").lower()
    for mot, motif, ech in MOTIFS_COUCHE:
        if mot in n:
            return motif, ech
    return "ANSI31", 0.8


def couches_dallage(e: dict) -> List[Tuple[str, Optional[float]]]:
    """Couches sous la dalle, de haut en bas, telles que saisies : [(désignation, épaisseur en cm ou None)]."""
    out = []
    for c in e.get("couches") or []:
        nom = (c.get("nom") if isinstance(c, dict) else c[0]) or ""
        ep = c.get("ep_cm") if isinstance(c, dict) else (c[1] if len(c) > 1 else None)
        if nom.strip():
            out.append((nom.strip(), float(ep) if ep not in (None, "") and float(ep) > 0 else None))
    return out


def _longrine_de_rive(lot: dict, boite, codes: Dict[int, str]) -> Optional[dict]:
    """Longrine (ou poutre) du plancher bas qui borde la dalle : elle est dessinée comme appui dans la coupe."""
    cands = []
    for l in lot.get("poutres") or []:
        e = l.get("entree") or {}
        if l.get("niveau") != "Fondation" or not e.get("b_cm") or not e.get("h_cm"):
            continue
        if None in (e.get("x1_m"), e.get("y1_m"), e.get("x2_m"), e.get("y2_m")):
            continue
        sur_bord = boite and all(
            (abs(x - boite[0]) <= 0.05 or abs(x - boite[2]) <= 0.05 or abs(y - boite[1]) <= 0.05 or abs(y - boite[3]) <= 0.05)
            for x, y in ((e["x1_m"], e["y1_m"]), (e["x2_m"], e["y2_m"])))
        cands.append((0 if sur_bord else 1, 0 if e.get("categorie") == "longrine" else 1, -e["h_cm"], l))
    if not cands:
        return None
    l = min(cands, key=lambda c: c[:3])[3]
    e = l["entree"]
    return {"code": codes.get(id(l)) or l.get("nom"), "b": e["b_cm"], "h": e["h_cm"],
            "categorie": e.get("categorie") or "poutre", "z": e.get("z_m")}


def vue_coupe_dallage(D: Dessin, x: float, y: float, lignes: List[dict], codes: Dict[int, str], lot: dict, mat: dict):
    """Coupe type 1:10 d'une dalle de fondation : épaisseur, armatures et leur position, couches, niveaux."""
    l0 = lignes[0]
    e, r = l0["entree"], l0.get("resultat") or {}
    k = 100.0                                                  # 1:10
    h = e["h_cm"] / 100.0
    lx = e.get("lx_m") or 2.0
    Lv = min(lx, 2.0)                                          # longueur de dalle représentée (coupure au-delà)
    rr = r.get("resultats") or {}
    c = (h - rr["x_travee"]["d_m"] - 0.005) if rr else mat.get("enrobage_semelle_mm", 50) / 1000.0
    lg = _longrine_de_rive(lot, _boite(e), codes)
    xs, yt = x + 60, y - 45                                    # nu de l'appui, dessus de la dalle
    xe = xs + Lv * k
    noms = ", ".join(sorted({codes.get(id(l)) or f"{l.get('nom')}*" for l in lignes}))
    nature = "dallage sur terre-plein" if e.get("appui") == "terre_plein" else "dalle pleine portée par les longrines"
    D.texte(f"{noms} — {nature} — e = {e['h_cm']:g} cm", x + 4, y - 8, 4.0)
    # appui : longrine de rive
    if lg:
        b_, h_ = lg["b"] / 100 * k, lg["h"] / 100 * k
        D.rect(xs - b_, yt - h_, b_, h_, "COFFRAGE", 50)
        cl = mat.get("enrobage_poutre_mm", 40) / 1000 * k
        D.rect(xs - b_ + cl, yt - h_ + cl, b_ - 2 * cl, h_ - 2 * cl, "CADRES", 25)
        for px in (xs - b_ + cl + 1.2, xs - cl - 1.2):
            for py in (yt - h_ + cl + 1.2, yt - cl - 1.2):
                D.barre(px, py, 0.8)
        D.texte(f"{lg['code']} {lg['b']:g}×{lg['h']:g} ({CATEGORIES_POUTRE[lg['categorie']]['libelle'].lower()})",
                xs - b_, yt + 4, 2.4, BL, "TEXTE")
        x_gauche = xs - b_
    else:
        D.ligne((xs, yt + 3), (xs, yt - h * k - 8), "COFFRAGE", 35)
        D.texte("appui (voir plan de fondation)", xs - 2, yt + 4, 2.2, TextEntityAlignment.BOTTOM_RIGHT, "TEXTE")
        x_gauche = xs
    # dalle, coupure à droite
    yb = yt - h * k
    D.ligne((xs, yt), (xe, yt), "COFFRAGE", 50)
    D.ligne((xs, yb), (xe, yb), "COFFRAGE", 50)
    D.msp.add_lwpolyline([(xe, yt + 2), (xe, yt - h * k * 0.35), (xe - 2.5, yt - h * k * 0.5),
                          (xe + 2.5, yt - h * k * 0.6), (xe, yt - h * k * 0.65), (xe, yb - 2)],
                         dxfattribs={"layer": "COFFRAGE", "lineweight": 18})
    # armatures (US3) : nappe inférieure coupée suivant lx — barres du sens lx en long, du sens ly en points
    ts = r.get("treillis")
    if ts or (e.get("armature") == "treillis" and e.get("ts_diametre_mm") and e.get("ts_maille_cm")):
        d1 = d2 = (ts or {}).get("diametre_mm") or e["ts_diametre_mm"]
        s2 = ((ts or {}).get("maille_cm") or e["ts_maille_cm"]) / 100.0
        lib_inf = (ts or {}).get("designation") or f"TS Ø{d1:g} maille {e['ts_maille_cm']:g}"
    elif rr:
        f1, f2 = rr["x_travee"]["ferraillage"], rr["y_travee"]["ferraillage"]
        d1, d2, s2 = f1["diametre_mm"], f2["diametre_mm"], f2["espacement_cm"] / 100.0
        lib_inf = f"{f1['choix']} (sens lx)  +  {f2['choix']} (sens ly)"
    else:
        d1 = d2 = s2 = None
        lib_inf = "armatures à calculer"
    if d1:
        y1 = yb + (c + d1 / 2000) * k
        D.ligne((x_gauche + 3 if lg else xs + 2, y1), (xe - 3, y1), "ACIER_LONG", 35)
        y2 = y1 + (d1 + d2) / 2000 * k
        xx = xs + s2 * k / 2
        while xx < xe - 3:
            D.barre(xx, y2, max(d2 / 2000 * k, 0.45))
            xx += s2 * k
        D.texte(f"Nappe inférieure : {lib_inf}", xs + 4, yb - 4, 2.2, TextEntityAlignment.TOP_LEFT, "ACIER_LONG")
    ch = (rr.get("appuis") or {}).get("ferraillage") or {}
    if ch.get("choix") and lg:
        dch = ch["diametre_mm"]
        ych = yt - (c + dch / 2000) * k
        D.ligne((x_gauche + 3, ych), (xs + 0.3 * Lv * k, ych), "ACIER_LONG", 35, "DASHED")
        D.texte(f"Chapeaux {ch['choix']} — longueur d'arrêt à définir", xs + 0.3 * Lv * k + 2, ych + 0.6, 2.0, BL, "ACIER_LONG")
    # épaisseur et enrobage
    D.cote((xe + 4, yb), (xe + 4, yt), f"{e['h_cm']:g}", -6)
    D.texte(f"enrobage {c * 100:.1f} cm", xe + 14, yb + 3.4, 2.0)
    # couches sous la dalle, de haut en bas (si elles sont définies)
    couches = couches_dallage(e)
    ycur = yb
    y_etiq = [yb + 3.0]                                         # étiquettes à droite, sans chevauchement

    def etiquette(texte, y_voulu):
        y_ = min(y_voulu, y_etiq[0] - 3.4)
        D.texte(texte, xe + 14, y_, 2.2)
        y_etiq[0] = y_

    for nom, ep in couches:
        if ep:
            hgt = ep / 100 * k
            pts = [(xs, ycur - hgt), (xe, ycur - hgt), (xe, ycur), (xs, ycur)]
            D.ligne(pts[0], pts[1], "COUCHES", 25)
            motif, ech = _motif_couche(nom)
            D.hachure(pts, motif, ech, "COUCHES", 8)
            D.cote((xe + 4, ycur - hgt), (xe + 4, ycur), f"{ep:g}", -6)
            etiquette(f"{nom} — {ep:g} cm", ycur - hgt / 2 - 1)
            ycur -= hgt
        else:                                                  # film ou membrane : un trait
            D.ligne((xs, ycur - 0.6), (xe, ycur - 0.6), "COUCHES", 50)
            etiquette(nom, ycur - 2.2)
            ycur -= 1.2
    if couches:
        pts = [(xs, ycur - 8), (xe, ycur - 8), (xe, ycur), (xs, ycur)]
        D.hachure(pts, "EARTH", 0.8, "COUCHES", 8)
        etiquette("sol support", ycur - 5)
    # niveaux (US4) : plancher bas et dessus des fûts, Z du modèle
    z_pb = e.get("z_m")
    futs = sorted({round((l.get("entree") or {}).get("fut", {}).get("z_haut_m"), 3) for l in lot.get("semelles") or []
                   if ((l.get("entree") or {}).get("fut") or {}).get("z_haut_m") is not None})
    if z_pb is not None:
        D.niveau(xs + 0.55 * Lv * k, yt, f"Plancher bas (Z modèle) {cote_niveau(z_pb, True)}")
    if futs:
        D.niveau(x_gauche - 4, yt, "N.S. fûts " + (cote_niveau(futs[0], True) if len(futs) == 1 else "variable (voir plan)"),
                 gauche=True)
    # texte
    yl = min(ycur - 14, yt - (lg["h"] / 100 * k if lg else 0) - 10, yb - 12)
    lignes_txt = [f"Armatures : {texte_armature_dalle(e, r)} — enrobage {c * 100:.1f} cm."]
    lignes_txt.append("Couches sous la dalle (de haut en bas) : "
                      + ("; ".join(f"{n} {ep:g} cm" if ep else n for n, ep in couches) if couches
                         else "non définies — à préciser (béton de propreté, film, hérisson…)."))
    if e.get("appui") == "terre_plein":
        lignes_txt.append("Dallage sur terre-plein : justification (DTU 13.3) non faite par l'application — à valider.")
    else:
        lignes_txt.append("Dalle calculée portée par les longrines de son contour (BAEL A.8.2) ; le sol n'est pas compté comme appui.")
    if lx > Lv:
        lignes_txt.append(f"Coupe représentée sur {Lv:.2f} m depuis l'appui (portée lx = {lx:.2f} m).")
    for i, t in enumerate(lignes_txt):
        D.texte(t, x + 4, yl - 4 * i, 2.3)


def planche_coupes_dallage(D: Dessin, lot: dict, types: Dict[str, List[dict]], mat: dict) -> int:
    """Une planche « Coupe transversale du dallage de fondation » : une coupe type par dalle de fondation
    différente (épaisseur, appui, armatures, couches). Renvoie le nombre de coupes dessinées."""
    codes = {id(l): t["code"] for liste in types.values() for t in liste for l in t["lignes"]}
    vues: "OrderedDict[tuple, List[dict]]" = OrderedDict()
    for l in lot.get("dalles") or []:
        e = l.get("entree") or {}
        if e.get("role") != "fondation" or not e.get("h_cm"):
            continue
        cle = (e["h_cm"], e.get("appui"), texte_armature_dalle(e, l.get("resultat")), tuple(couches_dallage(e)))
        vues.setdefault(cle, []).append(l)
    if not vues:
        return 0
    titre = "Coupe transversale du dallage de fondation"
    sous = "Coupe type par dalle — échelle 1:10 — armatures, couches et niveaux (Z du modèle Robot, en m)"
    P = Planche(D, titre, sous, (395, 235))
    for ls in vues.values():
        pos = P.cellule()
        if pos is None:
            P = Planche(D, f"{titre} (suite)", sous, (395, 235))
            pos = P.cellule()
        vue_coupe_dallage(D, pos[0], pos[1], ls, codes, lot, mat)
    return len(vues)


def nom_presentation(num: int, titre: str) -> str:
    """Nom d'onglet AutoCAD : « 01 Plan de fondation » (caractères interdits retirés, 64 car. au plus)."""
    return f"{num:02d} " + re.sub(r'[<>/\\":;?*|=`]', " ", titre).strip()[:60]


def presentations(D: Dessin):
    """Une présentation (onglet) A1 par planche, avec une fenêtre à l'échelle 1:1 sur la feuille de l'espace objet,
    et l'espace objet ouvert sur l'ensemble des planches : l'utilisateur voit tout le dossier à l'ouverture."""
    W, H = A1
    for P in D.planches:
        lay = D.doc.layouts.new(nom_presentation(P.num, P.titre))
        lay.page_setup(size=(W, H), margins=(0, 0, 0, 0), units="mm")
        lay.add_viewport(center=(W / 2, H / 2), size=(W, H),
                         view_center_point=(P.x0 + W / 2, P.y0 + H / 2), view_height=H)
    if D.planches and "Layout1" in D.doc.layouts:
        D.doc.layouts.delete("Layout1")
    largeur = len(D.planches) * (W + ESPACE_FEUILLES) - ESPACE_FEUILLES
    D.doc.set_modelspace_vport(height=max(H, largeur * 0.6) * 1.05, center=(largeur / 2, H / 2))


def dessiner_plans(lot: dict, projet: dict, bureau: Optional[dict], trame_x: Sequence[float],
                   trame_y: Sequence[float], dalles: Optional[Sequence[dict]] = None,
                   par_element: bool = False) -> Tuple[ezdxf.document.Drawing, dict]:
    nomen = nomenclature(lot, par_element)
    types, ecartes, mat = nomen["types"], nomen["ecartes"], lot.get("materiaux") or {}
    D = Dessin(projet, bureau or {})
    coupes = {"n": 0}

    def coupes_dallage():
        coupes["n"] = planche_coupes_dallage(D, lot, types, mat)

    niveaux, n_fondation = planches_coffrage(D, lot, types, list(dalles or []), trame_x, trame_y, coupes_dallage)
    planches_famille(D, "semelles", "Ferraillage des semelles", "Vue en plan et coupe — échelle 1:25",
                     (260, 150), vue_semelle, types, mat, ecartes)
    planches_famille(D, "poteaux", "Ferraillage des poteaux", "Coupes — échelle 1:10 — zones critiques RPS 2011",
                     (200, 120), vue_poteau, types, mat, ecartes)
    planches_famille(D, "poutres", "Ferraillage des poutres", "Élévation 1:50 et coupe 1:20",
                     (270, 105), vue_poutre, types, mat, ecartes)
    planches_famille(D, "voiles", "Ferraillage des voiles", "Élévation — échelle 1:50",
                     (200, 120), vue_voile, types, mat, ecartes)
    if nomen["lignes"]:
        planche_nomenclature(D, nomen)
    presentations(D)
    resume = {
        "planches": [p.titre for p in D.planches],
        "niveaux_dessines": [n for g in niveaux for n in g],
        "planches_coffrage": len(niveaux),
        "planches_fondation": n_fondation, "coupes_dallage": coupes["n"],
        "types": {fam: len(liste) for fam, liste in types.items()},
        "elements_dessines": sum(len(t["lignes"]) for liste in types.values() for t in liste),
        "elements_non_dessines": len(ecartes),
        "poids_total_kg": nomen["poids_total_kg"],
        "par_diametre_kg": nomen["par_diametre_kg"],
    }
    return D.doc, resume
