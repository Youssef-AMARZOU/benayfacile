"""Métré béton et acier du modèle calculé en lot.

Détail par élément (repère, axe, niveau, type, section, béton, aciers principaux,
cadres, autres aciers, poids, ratio) et récapitulatif (par famille, par diamètre,
nombre de barres commerciales).

L'acier vient de la nomenclature des plans (plans_ferraillage.nomenclature) :
le métré et les plans donnent donc le même poids. Seuls les éléments vérifiés
ont un ferraillage ; les autres sont comptés en béton et signalés.

Conventions (à valider par l'ingénieur ; reprises dans le classeur) :
  - béton brut par élément : poteau a × b × hauteur d'étage, poutre b × h × portée
    entre axes, semelle A × B × H, voile L × e × hauteur ; les nœuds poteau-poutre
    sont comptés deux fois (léger excès, du côté de la sécurité pour la commande) ;
  - barres commerciales : longueur totale / longueur commerciale, arrondi supérieur,
    sans optimisation des chutes.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from typing import Dict, List, Optional

from common import CATEGORIES_POUTRE, aire_polygone
from plans_ferraillage import nomenclature, poids_ml

LONGUEUR_COMMERCIALE_M = 12.0   # longueur usuelle des barres HA livrées au Maroc ; paramètre, pas une valeur normative

FAMILLES = OrderedDict([("poteaux", "Poteaux"), ("poutres", "Poutres"), ("semelles", "Semelles"), ("voiles", "Voiles"),
                        ("dalles", "Dalles")])


def rubrique(fam: str, e: dict) -> str:
    """Rubrique du métré : la famille, précisée par la catégorie (longrines, chaînages, fûts, dalles de fondation)."""
    if fam == "poutres":
        return CATEGORIES_POUTRE.get(e.get("categorie") or "poutre", CATEGORIES_POUTRE["poutre"])["pluriel"]
    if fam == "poteaux" and e.get("role") == "fut":
        return "Fûts"
    if fam == "dalles" and e.get("role") == "fondation":
        return "Dalles de fondation"
    return FAMILLES[fam]


def usage(designation: str) -> str:
    """Usage d'une position de la nomenclature, d'après sa désignation."""
    d = designation.lower()
    for mot, nom in (("treillis", "Treillis"), ("cadre", "Cadres"), ("épingle", "Épingles"), ("attente", "Attentes"),
                     ("montage", "Montage"),
                     ("potelet", "Potelets"), ("verticale", "Verticales"), ("horizontale", "Horizontales"),
                     ("nappe", "Nappes")):
        if mot in d:
            return nom
    return "Longitudinales"


def _section_et_volume(fam: str, e: dict, r: Optional[dict]) -> tuple:
    """(section lisible, longueur ou hauteur en m, volume de béton en m³) ; None si une dimension manque."""
    if fam == "poteaux":
        a, b, h = e.get("a_cm"), e.get("b_cm"), e.get("hauteur_m")
        if None in (a, b, h):
            return (None, h, None)
        return (f"{a:g} × {b:g}", h, a * b / 1e4 * h)
    if fam == "poutres":
        b, h, l = e.get("b_cm"), e.get("h_cm"), e.get("portee_m")
        if None in (b, h, l):
            return (None, l, None)
        return (f"{b:g} × {h:g}", l, b * h / 1e4 * l)
    if fam == "semelles":
        if not r or None in (r.get("A_m"), r.get("B_m"), r.get("H_m")):
            return (None, None, None)
        return (f"{r['A_m']:.2f} × {r['B_m']:.2f} × {r['H_m']:.2f} m", r["H_m"], r["A_m"] * r["B_m"] * r["H_m"])
    if fam == "voiles":
        l, ep, h = e.get("longueur_m"), e.get("ep_cm"), e.get("hauteur_m")
        if None in (l, ep, h):
            return (None, h, None)
        return (f"{l:g} m × {ep:g}", h, l * ep / 100 * h)
    if fam == "dalles":
        # surface : contour du panneau s'il est connu (dalle en L comprise), sinon lx × ly ; × épaisseur
        h = e.get("h_cm")
        if e.get("contour_m") and len(e["contour_m"]) >= 3:
            aire = aire_polygone(e["contour_m"])
        elif all(e.get(k) is not None for k in ("xmin_m", "xmax_m", "ymin_m", "ymax_m")):
            aire = (e["xmax_m"] - e["xmin_m"]) * (e["ymax_m"] - e["ymin_m"])
        elif e.get("lx_m") is not None and e.get("ly_m") is not None:
            aire = e["lx_m"] * e["ly_m"]
        else:
            aire = None
        if h is None or not aire:
            return (None, None, None)
        return (f"{aire:.2f} m² × {h:g}", None, aire * h / 100)
    return (None, None, None)


def metre(lot: dict, longueur_commerciale_m: float = LONGUEUR_COMMERCIALE_M) -> dict:
    nomen = nomenclature(lot)
    type_de = {id(l): t for liste in nomen["types"].values() for t in liste for l in t["lignes"]}
    lignes: List[dict] = []
    sans_beton: List[str] = []
    for fam, nom_fam in FAMILLES.items():
        for l in lot.get(fam) or []:
            e, r = l.get("entree") or {}, l.get("resultat")
            section, longueur, vol = _section_et_volume(fam, e, r)
            t = type_de.get(id(l))
            pos = t["positions"] if t else []
            principal = next((p for p in pos if usage(p["designation"]) not in ("Cadres", "Épingles", "Attentes", "Montage")), None)
            cadres = next((p for p in pos if usage(p["designation"]) == "Cadres"), None)
            kg_pos = [round(p["nombre"] * p["longueur_m"] * poids_ml(p["diametre_mm"]), 2) for p in pos]
            kg_princ = kg_pos[pos.index(principal)] if principal else 0.0
            kg_cad = kg_pos[pos.index(cadres)] if cadres else 0.0
            kg_tot = round(sum(kg_pos), 2) if t else None
            if vol is None:
                sans_beton.append(f"{nom_fam[:-1]} {l.get('nom')}{' · ' + l['niveau'] if l.get('niveau') else ''}")
            lignes.append({
                "famille": fam, "rubrique": rubrique(fam, e), "nom": l.get("nom"), "axe": l.get("axe"), "niveau": l.get("niveau"),
                "type": t["code"] if t else None, "statut": l.get("statut"),
                "section": section, "longueur_m": longueur, "beton_m3": round(vol, 4) if vol is not None else None,
                "principal": f"{principal['nombre']} HA{principal['diametre_mm']}" if principal else None,
                "principal_d_mm": principal["diametre_mm"] if principal else None,
                "principal_nb": principal["nombre"] if principal else None,
                "principal_l_m": principal["longueur_m"] if principal else None,
                "principal_kg": kg_princ if t else None,
                "cadres_d_mm": cadres["diametre_mm"] if cadres else None,
                "cadres_nb": cadres["nombre"] if cadres else None,
                "cadres_l_m": cadres["longueur_m"] if cadres else None,
                "cadres_kg": kg_cad if t else None,
                "autres_kg": round(kg_tot - kg_princ - kg_cad, 2) if t else None,
                "acier_kg": kg_tot,
                "ratio_kg_m3": round(kg_tot / vol, 1) if t and vol else None,
            })

    # récapitulatif par rubrique (famille précisée par la catégorie : longrines, chaînages, fûts…)
    rubrique_type = {(fam, t["code"]): rubrique(fam, t["rep"].get("entree") or {})
                     for fam, liste in nomen["types"].items() for t in liste}
    familles = []
    for nom_fam in OrderedDict.fromkeys(x["rubrique"] for x in lignes):
        ls = [x for x in lignes if x["rubrique"] == nom_fam]
        par_usage: Dict[str, float] = OrderedDict()
        for x in (n for n in nomen["lignes"] if rubrique_type.get((n["famille"], n["type"])) == nom_fam):
            u = usage(x["designation"])
            par_usage[u] = round(par_usage.get(u, 0) + x["poids_kg"], 1)
        beton = round(sum(x["beton_m3"] or 0 for x in ls), 3)
        acier = round(sum(par_usage.values()), 1)
        beton_arme = sum(x["beton_m3"] or 0 for x in ls if x["acier_kg"] is not None)
        familles.append({"famille": nom_fam, "elements": len(ls), "beton_m3": beton, "acier_par_usage_kg": dict(par_usage),
                         "acier_kg": acier, "ratio_kg_m3": round(acier / beton_arme, 1) if beton_arme else None,
                         "non_ferrailles": sum(1 for x in ls if x["acier_kg"] is None)})

    # par diamètre et usage, puis par diamètre toutes utilisations
    par_du: Dict[tuple, dict] = OrderedDict()
    for x in sorted(nomen["lignes"], key=lambda n: (n["diametre_mm"], usage(n["designation"]))):
        k = (x["diametre_mm"], usage(x["designation"]))
        d = par_du.setdefault(k, {"diametre_mm": k[0], "usage": k[1], "kg_m": round(poids_ml(k[0]), 3),
                                  "longueur_m": 0.0, "poids_kg": 0.0})
        d["longueur_m"] = round(d["longueur_m"] + x["longueur_totale_m"], 2)
        d["poids_kg"] = round(d["poids_kg"] + x["poids_kg"], 1)
    for d in par_du.values():
        d["barres"] = math.ceil(d["longueur_m"] / longueur_commerciale_m - 1e-9)
    par_d: Dict[int, dict] = OrderedDict()
    for d in par_du.values():
        s = par_d.setdefault(d["diametre_mm"], {"diametre_mm": d["diametre_mm"], "longueur_m": 0.0, "poids_kg": 0.0})
        s["longueur_m"] = round(s["longueur_m"] + d["longueur_m"], 2)
        s["poids_kg"] = round(s["poids_kg"] + d["poids_kg"], 1)
    acier_total = round(sum(s["poids_kg"] for s in par_d.values()), 1)
    for s in par_d.values():
        s["barres"] = math.ceil(s["longueur_m"] / longueur_commerciale_m - 1e-9)
        s["part_pct"] = round(100 * s["poids_kg"] / acier_total, 1) if acier_total else 0.0

    beton_total = round(sum(f["beton_m3"] for f in familles), 3)
    non_comptes = list(OrderedDict.fromkeys(nc for liste in nomen["types"].values() for t in liste
                                            for nc in t.get("non_comptes") or []))
    beton_arme = sum(x["beton_m3"] or 0 for x in lignes if x["acier_kg"] is not None)
    return {
        "lignes": lignes, "familles": familles,
        "par_diametre_usage": list(par_du.values()), "par_diametre": list(par_d.values()),
        "beton_total_m3": beton_total, "acier_total_kg": acier_total,
        "ratio_kg_m3": round(acier_total / beton_arme, 1) if beton_arme else None,
        "barres_total": sum(s["barres"] for s in par_d.values()),
        "longueur_commerciale_m": longueur_commerciale_m,
        "poids_nomenclature_kg": nomen["poids_total_kg"],
        "sans_beton": sans_beton,
        "hypotheses": [
            "Béton brut : poteau a × b × hauteur d'étage, poutre b × h × portée entre axes, semelle A × B × H, "
            "voile L × e × hauteur ; nœuds poteau-poutre comptés deux fois (léger excès).",
            "Acier : nomenclature des plans de ferraillage (longueurs façonnées, crochets, ancrages et recouvrements "
            "compris), masse volumique 7 850 kg/m³.",
            f"Barres commerciales de {longueur_commerciale_m:g} m : longueur totale / {longueur_commerciale_m:g}, "
            "arrondi supérieur, sans optimisation des chutes.",
            "Épingles : non prévues par les dispositions constructives retenues ; à ajouter si l'ingénieur en dispose.",
            "Éléments non vérifiés : béton compté, acier non compté (ferraillage à reprendre).",
            "Dalles : béton = surface du contour × épaisseur ; nappes inférieures sur le contour − 2 enrobages, "
            "crochets de 10 Ø compris.",
        ] + non_comptes,
    }
