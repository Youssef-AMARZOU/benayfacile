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


def rang_niveau(nom: str) -> tuple:
    """Clé de tri des niveaux de bas en haut : Fondation, sous-sols (S-2, S-1), RDC, R+1, R+2…
    Un libellé inconnu se place après, dans son ordre d'apparition (tri stable)."""
    import re as _re
    n = (nom or "").strip()
    if n.lower().startswith("fondation"):
        return (0, -1000)
    m = _re.match(r"(?i)s(?:ous-sol)?\s*-?\s*(\d+)$", n)
    if m:
        return (0, -int(m.group(1)))
    if n.upper() == "RDC":
        return (0, 0)
    m = _re.match(r"(?i)r\s*\+\s*(\d+)$", n)
    if m:
        return (0, int(m.group(1)))
    return (1, 0)
