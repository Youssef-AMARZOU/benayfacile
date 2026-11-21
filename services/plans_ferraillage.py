"""Plans de ferraillage DXF de tout le modèle, à partir du calcul en lot.

Un seul fichier DXF, plusieurs feuilles A1 côte à côte dans l'espace objet :
  1. Plan de fondation (implantation des semelles sur la trame, 1:100)
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


CLES = {"poteaux": ("P", _cle_poteau), "poutres": ("Pt", _cle_poutre),
        "semelles": ("S", _cle_semelle), "voiles": ("V", _cle_voile)}


def grouper(lot: dict) -> Tuple[Dict[str, List[dict]], List[dict]]:
    """Types par famille (éléments vérifiés) et liste des éléments non dessinés."""
    types, ecartes = {}, []
    for fam, (prefixe, cle) in CLES.items():
        groupes: "OrderedDict[tuple, dict]" = OrderedDict()
        for l in lot.get(fam) or []:
            if l.get("statut") != "verifie" or not l.get("resultat"):
                ecartes.append({"famille": fam, "nom": l.get("nom"), "niveau": l.get("niveau"),
                                "statut": l.get("statut"), "raison": " ; ".join(l.get("problemes") or [])})
                continue
            try:
                k = cle(l)
            except (KeyError, TypeError):
                ecartes.append({"famille": fam, "nom": l.get("nom"), "niveau": l.get("niveau"),
                                "statut": "incomplet", "raison": "données de dessin manquantes"})
                continue
            groupes.setdefault(k, {"lignes": []})["lignes"].append(l)
        types[fam] = []
        for i, g in enumerate(groupes.values(), start=1):
            g["code"] = f"{prefixe}{i}"
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
    return []


def nomenclature(lot: dict) -> dict:
    """Types, positions et poids : la partie « calcul » des plans (sans dessin)."""
    types, ecartes = grouper(lot)
    mat = lot.get("materiaux") or {}
    poteaux_rdc = {l.get("axe"): l for l in lot.get("poteaux") or []
                   if l.get("niveau") == "RDC" and l.get("resultat")}
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
           "TEXTE": 7, "CARTOUCHE": 7, "NOMENCLATURE": 3, "BETON_PROPRETE": 8}
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
    D.rect(sx + A / 2 - a / 2, sy + H, a, 14, "COFFRAGE", 35)
    D.ligne((sx + c, sy + c), (sx + A - c, sy + c), "ACIER_LONG", 50)
    for xx in (sx + c, sx + A - c):
        D.ligne((xx, sy + c), (xx, sy + c + 10 * dx / 1000 * k), "ACIER_LONG", 50)
    n_a, d_a = t["attentes"]
    for xx in (sx + A / 2 - a / 2 + 2, sx + A / 2 + a / 2 - 2):
        D.ligne((xx, sy + c + 1), (xx, sy + H + 14), "ACIER_LONG", 35)
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


def plan_fondation(D: Dessin, types: Dict[str, List[dict]], trame_x: Sequence[float], trame_y: Sequence[float]):
    ex, ey = (trame_x[-1] - trame_x[0]) or 1.0, (trame_y[-1] - trame_y[0]) or 1.0
    dispo_l, dispo_h = A1[0] - 2 * MARGE - 230 - 80, A1[1] - 2 * MARGE - 40 - 70
    ech = next((e for e in (50, 100, 200, 500) if ex * 1000 / e <= dispo_l and ey * 1000 / e <= dispo_h), 500)
    k = 1000.0 / ech
    P = Planche(D, "Plan de fondation", f"Implantation des semelles sur la trame — échelle 1:{ech} — cotes en mètres", (0, 0))
    lx, ly = ex * k, ey * k
    gx = P.x0 + MARGE + 40 + (dispo_l - lx) / 2
    gy = P.y0 + MARGE + 45 + (dispo_h - ly) / 2
    for i, xv in enumerate(trame_x):
        px = gx + (xv - trame_x[0]) * k
        D.ligne((px, gy - 15), (px, gy + ly + 15), "AXES", 13, "DASHDOT")
        D.msp.add_circle((px, gy + ly + 21), 4.5, dxfattribs={"layer": "AXES"})
        D.texte(str(i + 1), px, gy + ly + 21, 3.8, MC, "AXES")
    for j, yv in enumerate(trame_y):
        py = gy + (yv - trame_y[0]) * k
        D.ligne((gx - 15, py), (gx + lx + 15, py), "AXES", 13, "DASHDOT")
        D.msp.add_circle((gx - 21, py), 4.5, dxfattribs={"layer": "AXES"})
        D.texte(chr(65 + j), gx - 21, py, 3.8, MC, "AXES")
    for i in range(len(trame_x) - 1):
        x1, x2 = gx + (trame_x[i] - trame_x[0]) * k, gx + (trame_x[i + 1] - trame_x[0]) * k
        D.cote((x1, gy - 18), (x2, gy - 18), f"{trame_x[i + 1] - trame_x[i]:.2f}", 4)
    for j in range(len(trame_y) - 1):
        y1, y2 = gy + (trame_y[j] - trame_y[0]) * k, gy + (trame_y[j + 1] - trame_y[0]) * k
        D.cote((gx + lx + 30, y1), (gx + lx + 30, y2), f"{trame_y[j + 1] - trame_y[j]:.2f}", -4)
    lignes_tab = []
    for t in types.get("semelles", []):
        r = t["rep"]["resultat"]
        for l in t["lignes"]:
            axe = l.get("axe") or ""
            m = re.match(r"([A-Z])(\d+)$", axe)
            if not m:
                continue
            j, i = ord(m.group(1)) - 65, int(m.group(2)) - 1
            if i >= len(trame_x) or j >= len(trame_y):
                continue
            cx, cy = gx + (trame_x[i] - trame_x[0]) * k, gy + (trame_y[j] - trame_y[0]) * k
            A, B = r["A_m"] * k, r["B_m"] * k
            D.rect(cx - A / 2, cy - B / 2, A, B, "COFFRAGE", 50)
            a = (l["entree"].get("a_poteau_cm") or 30) / 100 * k
            b = (l["entree"].get("b_poteau_cm") or 30) / 100 * k
            D.rect(cx - a / 2, cy - b / 2, a, b, "COFFRAGE", 35)
            h = D.msp.add_hatch(color=7, dxfattribs={"layer": "COFFRAGE"})
            h.paths.add_polyline_path([(cx - a / 2, cy - b / 2), (cx + a / 2, cy - b / 2),
                                       (cx + a / 2, cy + b / 2), (cx - a / 2, cy + b / 2)], is_closed=True)
            D.texte(f"{t['code']}  ({axe})", cx + A / 2 + 1.5, cy + B / 2 + 1.5, 3.0, BL, "TEXTE")
        x_, y_ = _barres(r["choix_x"]), _barres(r["choix_y"])
        lignes_tab.append([t["code"], len(t["lignes"]), f"{r['A_m']:.2f}", f"{r['B_m']:.2f}", f"{r['H_m']:.2f}",
                           f"{x_[0]} HA{x_[1]}", f"{y_[0]} HA{y_[1]}"])
    tx = P.x0 + A1[0] - MARGE - 200
    D.texte("Tableau des semelles", tx, P.y0 + A1[1] - MARGE - 40, 4.0)
    D.tableau(tx, P.y0 + A1[1] - MARGE - 45, ["Type", "Nb", "A (m)", "B (m)", "H (m)", "Nappe X", "Nappe Y"],
              [18, 12, 22, 22, 22, 32, 32], lignes_tab, 6.0)
    return P


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
    noms = {"poteaux": "Poteaux", "poutres": "Poutres", "semelles": "Semelles", "voiles": "Voiles"}
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
                   trame_y: Sequence[float]) -> Tuple[ezdxf.document.Drawing, dict]:
    nomen = nomenclature(lot)
    types, ecartes, mat = nomen["types"], nomen["ecartes"], lot.get("materiaux") or {}
    D = Dessin(projet, bureau or {})
    if types.get("semelles") and trame_x and trame_y:
        plan_fondation(D, types, list(trame_x), list(trame_y))
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
        "types": {fam: len(liste) for fam, liste in types.items()},
        "elements_dessines": sum(len(t["lignes"]) for liste in types.values() for t in liste),
        "elements_non_dessines": len(ecartes),
        "poids_total_kg": nomen["poids_total_kg"],
        "par_diametre_kg": nomen["par_diametre_kg"],
    }
    return D.doc, resume
