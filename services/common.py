"""Helpers communs — audit arithmétique et sélection de barres (BE pratique marocain)."""
from __future__ import annotations

# Diamètres normalisés utilisés dans les BET marocains (mm)
DIAMETRES = [8, 10, 12, 14, 16, 20, 25, 32]

def section_bar(d_mm: float) -> float:
    """Section d'une barre en cm²."""
    return 3.141592653589793 * (d_mm / 10.0) ** 2 / 4.0


def choisir_barres(as_requis_cm2: float, d_max_mm: float = 32.0, n_max: int = 16,
                   dn_min_mm: float = 8.0, symetrique: bool = False) -> dict:
    """Choisit (n × Ø) minimisant la section totale pour couvrir as_requis_cm2.

    Retourne dict(n, diametre_mm, as_fournie_cm2, ecart_cm2, surdimensionnement_pct).
    """
    if as_requis_cm2 <= 0:
        return {"n": 0, "diametre_mm": 0, "as_fournie_cm2": 0.0, "ecart_cm2": 0.0,
                "surdimensionnement_pct": 0.0, "choix": "aucune armature requise par le calcul"}
    best = None
    for d in DIAMETRES:
        if d > d_max_mm:
            continue
        sf = section_bar(d)
        import math
        n = math.ceil(as_requis_cm2 / sf)
        if symetrique and n % 2 == 1:
            n += 1
        if n > n_max:
            continue
        cand = {"n": n, "diametre_mm": d, "as_fournie_cm2": round(n * sf, 2)}
        cand["ecart_cm2"] = round(cand["as_fournie_cm2"] - as_requis_cm2, 2)
        cand["surdimensionnement_pct"] = round(100.0 * cand["ecart_cm2"] / as_requis_cm2, 1)
        # préférence BET : petit surdimensionnement (≤5 % idéal, ≤15 % acceptable),
        # puis barre la plus grosse (moins de barres), puis moins de barres
        pct = cand["surdimensionnement_pct"]
        bucket = 0 if pct <= 5 else (1 if pct <= 15 else 2)
        key = (bucket, -d, n)
        if best is None or key < best[0]:
            best = (key, cand)
    if best is None:
        d = d_max_mm
        import math
        n = math.ceil(as_requis_cm2 / section_bar(d))
        if symetrique and n % 2 == 1:
            n += 1
        cand = {"n": n, "diametre_mm": d, "as_fournie_cm2": round(n * section_bar(d), 2)}
        cand["ecart_cm2"] = round(cand["as_fournie_cm2"] - as_requis_cm2, 2)
        cand["surdimensionnement_pct"] = None
        best = (None, cand)
    cand = best[1]
    cand["choix"] = f"{cand['n']} HA{cand['diametre_mm']:.0f}"
    return cand


def audit_ligne(libelle: str, calcul: float, declare: float, tolerance: float = 0.01) -> dict:
    """Audit arithmétique : compare un calcul refait à une valeur déclarée."""
    ok = abs(calcul - declare) <= tolerance
    return {"ligne": libelle, "recalcule": round(calcul, 4), "declare": round(declare, 4),
            "ecart": round(calcul - declare, 4), "statut": "OK" if ok else "ALERTE ECART ARITHMETIQUE"}


def fmt(x, ndigits=2):
    try:
        return round(float(x), ndigits)
    except (TypeError, ValueError):
        return x


# ───────────────────────── repères de files et niveaux ─────────────────────────

def lettre_file(j: int) -> str:
    """Repère de file en Y : 0 → A … 25 → Z, 26 → AA, 27 → AB… (comme les colonnes d'un tableur)."""
    s = ""
    j += 1
    while j:
        j, r = divmod(j - 1, 26)
        s = chr(65 + r) + s
    return s


def indice_file(lettres: str) -> int:
    """Inverse de lettre_file : A → 0, Z → 25, AA → 26."""
    n = 0
    for c in lettres:
        n = n * 26 + (ord(c) - 64)
    return n - 1


_RE_NIV = None


def rang_niveau(nom: str) -> tuple:
    """Clé de tri des niveaux de bas en haut, quel que soit le libellé employé par le bureau ou par Robot :
    Fondation / Infrastructure / Radier ; sous-sols (S-2, SS1, Sous-sol 1, R-1, N-1) ; RDC / Rez-de-chaussée / R+0 ;
    étages (R+1, N+1, Étage 1, 1er étage, Niveau 3) ; Mezzanine ; Terrasse / Toiture / Buanderie / Édicule en tête ;
    des libellés d'altitude (« +6,12 », « Niv. +6.12 m », « Z = 6.12 ») se classent entre eux par altitude,
    après les libellés d'étage (aucune hauteur d'étage n'est supposée pour les mêler).
    Un libellé inconnu se place après, dans son ordre d'apparition (tri stable)."""
    import re as _re
    n = (nom or "").strip().lower()
    n = n.replace("é", "e").replace("è", "e").replace("ê", "e")
    if _re.match(r"(fondation|infrastructure|radier|longrine)", n):
        return (0, -1000.0)
    m = _re.match(r"(?:s(?:ous[- ]?sol)?|ss|sous-sol|r|n|niv(?:eau)?\.?)\s*-\s*(\d+)$", n) \
        or _re.match(r"(?:ss|sous[- ]?sol|s)\s*(\d+)$", n)
    if m:
        return (0, -float(m.group(1)))
    if _re.match(r"(rdc|rez[- ]de[- ]chaussee|rdj|rez[- ]de[- ]jardin)(?![a-z])", n) or _re.match(r"[rn]\s*\+\s*0$", n):
        return (0, 0.0)
    m = _re.match(r"(?:[rn]|niv(?:eau)?\.?|etage)\s*\+?\s*(\d+)$", n) or _re.match(r"(\d+)\s*(?:er|e|eme|ème)?\s*etage$", n)
    if m:
        return (0, float(m.group(1)))
    if n.startswith("mezzanine"):
        return (0, 0.5)
    if _re.match(r"(terrasse|toiture|buanderie|edicule|acrotere|cage)", n):
        return (0, 9000.0)
    m = _re.match(r"(?:niv(?:eau)?\.?|z\s*=|altitude)?\s*([+-]?\d+(?:[.,]\d+)?)\s*m?$", n)
    if m:
        return (1, float(m.group(1).replace(",", ".")))
    return (2, 0.0)


def trier_niveaux(noms, z_par_niveau=None) -> list:
    """Niveaux de bas en haut. Quand l'altitude de chaque niveau est connue (modèle Robot), elle décide ;
    sinon le libellé (rang_niveau). « Fondation » reste en bas dans tous les cas."""
    noms = list(dict.fromkeys(n for n in noms if n))
    z = z_par_niveau or {}
    if noms and all(z.get(n) is not None for n in noms if not rang_niveau(n) == (0, -1000.0)):
        return sorted(noms, key=lambda n: (-1e9 if rang_niveau(n) == (0, -1000.0) else z[n]))
    return sorted(noms, key=rang_niveau)


def cote_niveau(z, ascii_seul: bool = False) -> str:
    """Cote altimétrique lisible : +0,00 / −0,20 (m). ascii_seul : signe « - » (textes DXF)."""
    if z is None:
        return "—"
    t = f"{float(z):+.2f}".replace(".", ",")
    if t in ("-0,00", "+0,00"):
        return "±0,00"
    return t if ascii_seul else t.replace("-", "−")


# ───────────────────── catégories des éléments horizontaux et des poteaux ─────────────────────
# Une poutre est une « poutre » (porte un plancher), une « longrine » (relie les semelles au niveau
# des fondations) ou un « chaînage » (ne porte pas de plancher : sous un mur, en rive…). Un tronçon
# de poteau sous le plancher bas, entre la semelle et ce plancher, est un « fût » (amorce de poteau).

CATEGORIES_POUTRE = {
    "poutre": {"prefixe": "Pt", "libelle": "Poutre", "pluriel": "Poutres"},
    "longrine": {"prefixe": "L", "libelle": "Longrine", "pluriel": "Longrines"},
    "chainage": {"prefixe": "Ch", "libelle": "Chaînage", "pluriel": "Chaînages"},
}
ROLES_POTEAU = {
    "poteau": {"prefixe": "P", "libelle": "Poteau", "pluriel": "Poteaux"},
    "fut": {"prefixe": "F", "libelle": "Fût", "pluriel": "Fûts"},
}
_MOTS_CATEGORIE = (
    ("longrine", ("LONGRINE", "LONGRINES", "LONGR", "LONG", "LGR", "LG")),
    ("chainage", ("CHAINAGE", "CHAINAGES", "CHAIN", "CHN", "CH")),
    ("poutre", ("POUTRE", "POUTRES", "PTR", "PT")),
)


def _jetons(nom: str) -> set:
    """Mots d'un nom de section ou de type (« LG 30x40 », « Longrine_25x40 », « CH25X25 » → LG, LONGRINE, CH…)."""
    import re as _re
    import unicodedata
    s = unicodedata.normalize("NFD", nom or "").encode("ascii", "ignore").decode().upper()
    out = set()
    for t in _re.split(r"[^A-Z0-9]+", s):
        if not t:
            continue
        out.add(t)
        m = _re.match(r"([A-Z]+)\d", t)
        if m:
            out.add(m.group(1))
    return out


def categorie_par_nom(*noms: str):
    """(catégorie, motif) si un des noms (section, type de barre…) désigne explicitement une longrine, un chaînage
    ou une poutre ; None sinon. Le nom donné dans Robot par le projeteur prime sur toute déduction géométrique."""
    for nom in noms:
        jetons = _jetons(nom)
        for cat, mots in _MOTS_CATEGORIE:
            if jetons & set(mots):
                return cat, f"nom « {nom.strip()} »"
    return None


def dans_polygone(x: float, y: float, contour, tol: float = 0.05) -> bool:
    """Point (x, y) à l'intérieur du contour ou sur un de ses bords (à tol près, m)."""
    import math as _m
    n = len(contour)
    if n < 3:
        return False
    for k in range(n):
        x1, y1 = contour[k][0], contour[k][1]
        x2, y2 = contour[(k + 1) % n][0], contour[(k + 1) % n][1]
        dx, dy = x2 - x1, y2 - y1
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / l2))
        if _m.hypot(x - x1 - t * dx, y - y1 - t * dy) <= tol:
            return True
    dedans = False
    for k in range(n):
        x1, y1 = contour[k][0], contour[k][1]
        x2, y2 = contour[(k + 1) % n][0], contour[(k + 1) % n][1]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            dedans = not dedans
    return dedans


def aire_polygone(contour) -> float:
    """Aire (m²) d'un contour plan, formule du lacet (sommets dans l'ordre, sens indifférent)."""
    n = len(contour)
    return abs(sum(contour[k][0] * contour[(k + 1) % n][1] - contour[(k + 1) % n][0] * contour[k][1]
                   for k in range(n))) / 2.0 if n >= 3 else 0.0
