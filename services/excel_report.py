"""Classeur Excel des résultats du calcul en lot (« Note de calcul » tabulaire).

Une feuille de synthèse, puis une feuille par famille : Poteaux, Poutres,
Semelles, Voiles ; enfin le métré béton et acier (détail par élément et
récapitulatif par famille et par diamètre, voir metre.py). Les valeurs sont de vrais nombres (pas du texte) pour que le
bureau d'études puisse trier, filtrer et recalculer ; chaque ligne garde son
état (vérifié, à revoir, incomplet, erreur) et la raison.

Entrée : la réponse de POST /lot du moteur (voir engine_service.lot).
"""
from __future__ import annotations

import datetime
import io
from typing import Callable, List, Optional, Sequence, Tuple

from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

GRAPHITE = "1E2730"
ARMATURE = "B8321F"
VERIFIE = "2F6B3A"
FOND_TETE = "E9EAE6"
FOND_REVOIR = "F6E1DD"
FOND_INCOMPLET = "F7EDD6"

ETATS = {"verifie": "Vérifié", "a_revoir": "À revoir", "incomplet": "Incomplet", "erreur": "Erreur"}
TRAIT = Side(style="thin", color="B9BDB7")
TRAIT_FORT = Side(style="medium", color=GRAPHITE)

# (en-tête, unité, extracteur(ligne) -> valeur, format numérique, largeur)
Colonne = Tuple[str, str, Callable[[dict], object], Optional[str], float]


def _r(l: dict, *chemin, defaut=None):
    """Valeur imbriquée dans le résultat d'une ligne (None si absent)."""
    v = l.get("resultat")
    for c in chemin:
        if not isinstance(v, dict):
            return defaut
        v = v.get(c)
    return defaut if v is None else v


def _e(l: dict, cle: str):
    return (l.get("entree") or {}).get(cle)


def _div(a, b, k=1.0):
    try:
        return round(a / b * k, 2) if a is not None and b else None
    except TypeError:
        return None


def _mn(kn):
    return round(kn / 1000.0, 3) if isinstance(kn, (int, float)) else None


F2, F3, F1 = "0.00", "0.000", "0.0"

POTEAUX: List[Colonne] = [
    ("Élément", "", lambda l: l.get("nom"), None, 11),
    ("Rôle", "", lambda l: "Fût" if _e(l, "role") == "fut" else "Poteau", None, 8),
    ("Niveau", "", lambda l: l.get("niveau"), None, 8),
    ("a", "cm", lambda l: _e(l, "a_cm"), F1, 7),
    ("b", "cm", lambda l: _e(l, "b_cm"), F1, 7),
    ("lf", "m", lambda l: _e(l, "lf_m"), F2, 7),
    ("Nu", "kN", lambda l: _e(l, "nu_kn"), F1, 9),
    ("Ns", "kN", lambda l: _e(l, "ns_kn"), F1, 9),
    ("Mx", "kN.m", lambda l: _e(l, "mx_knm"), F1, 8),
    ("My", "kN.m", lambda l: _e(l, "my_knm"), F1, 8),
    ("λ", "", lambda l: _r(l, "lambda"), F2, 7),
    ("α", "", lambda l: _r(l, "alpha"), F3, 7),
    ("Nu,lim", "kN", lambda l: _r(l, "nu_lim_kn_avec_as_fournie"), F1, 9),
    ("Nu / Nu,lim", "", lambda l: _r(l, "nu_rapport"), F3, 10),
    ("As calculée", "cm²", lambda l: _r(l, "as_calculee_cm2"), F2, 10),
    ("As fournie", "cm²", lambda l: _r(l, "ferraillage", "as_fournie_cm2"), F2, 10),
    ("Ferraillage", "", lambda l: _r(l, "ferraillage", "choix"), None, 24),
]

def _categorie(l: dict) -> str:
    from common import CATEGORIES_POUTRE
    c = _e(l, "categorie") or "poutre"
    return CATEGORIES_POUTRE.get(c, CATEGORIES_POUTRE["poutre"])["libelle"]


POUTRES: List[Colonne] = [
    ("Élément", "", lambda l: l.get("nom"), None, 13),
    ("Catégorie", "", _categorie, None, 11),
    ("Niveau", "", lambda l: l.get("niveau"), None, 8),
    ("b", "cm", lambda l: _e(l, "b_cm"), F1, 7),
    ("h", "cm", lambda l: _e(l, "h_cm"), F1, 7),
    ("Portée", "m", lambda l: _e(l, "portee_m"), F2, 8),
    ("Mu", "kN.m", lambda l: _e(l, "mu_knm"), F1, 9),
    ("Ms", "kN.m", lambda l: _e(l, "ms_knm"), F1, 9),
    ("Vu", "kN", lambda l: _e(l, "vu_kn"), F1, 8),
    ("μ", "", lambda l: _r(l, "mu"), F3, 7),
    ("As calculée", "cm²", lambda l: _r(l, "as_cm2"), F2, 10),
    ("As retenue", "cm²", lambda l: _r(l, "as_retenue_cm2"), F2, 10),
    ("Ferraillage", "", lambda l: _r(l, "ferraillage", "choix"), None, 14),
    ("σst ELS", "MPa", lambda l: _r(l, "els", "sigma_st_mpa"), F1, 9),
    ("σst lim", "MPa", lambda l: _r(l, "els", "sigma_st_lim_mpa"), F1, 9),
    ("τu", "MPa", lambda l: _r(l, "effort_tranchant", "tau_u_mpa"), F3, 8),
    ("At / st", "cm²/m", lambda l: _r(l, "effort_tranchant", "at_cm2_par_m"), F2, 9),
]

# Colonnes de la note semelles du bureau (Pu / Ns en MN, aciers totaux et par mètre)
SEMELLES: List[Colonne] = [
    ("N° Semelle", "", lambda l: l.get("nom"), None, 11),
    ("Poteau", "cm", lambda l: (f"{_e(l, 'a_poteau_cm'):g} × {_e(l, 'b_poteau_cm'):g}"
                                if _e(l, "a_poteau_cm") and _e(l, "b_poteau_cm") else None), None, 9),
    ("Pu total", "MN", lambda l: _mn(_r(l, "nu_kn_utilise") or _e(l, "nu_kn")), F3, 9),
    ("Ns total", "MN", lambda l: _mn(_e(l, "ns_kn")), F3, 9),
    ("A", "m", lambda l: _r(l, "A_m"), F2, 7),
    ("B", "m", lambda l: _r(l, "B_m"), F2, 7),
    ("H", "m", lambda l: _r(l, "H_m"), F2, 7),
    ("Asx", "cm²", lambda l: _r(l, "asx_cm2"), F2, 8),
    ("Asy", "cm²", lambda l: _r(l, "asy_cm2"), F2, 8),
    ("Asx / ml", "cm²/ml", lambda l: _div(_r(l, "asx_cm2"), _r(l, "B_m")), F2, 9),   # nappe X répartie sur B
    ("Asy / ml", "cm²/ml", lambda l: _div(_r(l, "asy_cm2"), _r(l, "A_m")), F2, 9),   # nappe Y répartie sur A
    ("Acier X", "", lambda l: _r(l, "acier_x"), None, 11),
    ("Acier Y", "", lambda l: _r(l, "acier_y"), None, 11),
    ("σmax", "bar", lambda l: _r(l, "sigma_max_bar"), F3, 8),
    ("Poinçonnement", "", lambda l: (None if l.get("resultat") is None
                                     else ("OK" if _r(l, "poinconnement", "ok") else "NON")), None, 13),
]

VOILES: List[Colonne] = [
    ("Élément", "", lambda l: l.get("nom"), None, 9),
    ("Niveau", "", lambda l: l.get("niveau"), None, 8),
    ("L", "m", lambda l: _e(l, "longueur_m"), F2, 7),
    ("e", "cm", lambda l: _e(l, "ep_cm"), F1, 7),
    ("N", "kN", lambda l: _e(l, "n_kn"), F1, 9),
    ("M", "kN.m", lambda l: _e(l, "m_knm"), F1, 9),
    ("V", "kN", lambda l: _e(l, "v_kn"), F1, 8),
    ("σmax", "MPa", lambda l: _r(l, "sigma_max_mpa"), F2, 8),
    ("σmin", "MPa", lambda l: _r(l, "sigma_min_mpa"), F2, 8),
    ("τu", "MPa", lambda l: _r(l, "tau_u_mpa"), F3, 8),
    ("As rive", "cm²", lambda l: _r(l, "as_rive_cm2"), F2, 8),
    ("As vert.", "cm²/m", lambda l: _r(l, "as_vert_par_m_cm2"), F2, 9),
    ("As horiz.", "cm²/m", lambda l: _r(l, "as_horiz_par_m_cm2"), F2, 9),
]

FAMILLES = [
    ("poteaux", "Poteaux", "BAEL 91 rév. 99 — B.8.4,1 compression centrée + flexion composée", POTEAUX),
    ("poutres", "Poutres", "BAEL 91 rév. 99 — flexion simple ELU, ELS, effort tranchant", POUTRES),
    ("semelles", "Semelles", "Méthode des bielles — As = Nu·(A−a)/(8·d·σs), poinçonnement", SEMELLES),
    ("voiles", "Voiles", "BAEL B.8.4 — σ = N/(e·L) ± 6M/(e·L²)", VOILES),
]


def _entete(ws, projet: dict, titre: str, normes: str, largeur: int) -> int:
    """Bloc-titre en haut de feuille ; renvoie la ligne de l'en-tête du tableau."""
    ws["A1"] = projet.get("projet") or "Projet"
    ws["A1"].font = Font(name="Calibri", size=14, bold=True, color=GRAPHITE)
    ws["A2"] = f"{titre} — {normes}"
    ws["A2"].font = Font(size=10, color="4A5560")
    infos = [projet.get("client"), projet.get("site"),
             f"Indice {projet.get('indice')}" if projet.get("indice") else None,
             datetime.date.today().strftime("%d/%m/%Y")]
    ws["A3"] = "   ".join(i for i in infos if i)
    ws["A3"].font = Font(size=9, color="7D8790")
    for c in range(1, largeur + 1):
        ws.cell(row=3, column=c).border = Border(bottom=TRAIT_FORT)
    return 5


def _feuille(wb: Workbook, nom: str, normes: str, colonnes: Sequence[Colonne], lignes: List[dict], projet: dict):
    ws = wb.create_sheet(nom)
    cols = list(colonnes) + [("État", "", lambda l: ETATS.get(l.get("statut"), l.get("statut")), None, 11),
                             ("Remarques", "", lambda l: " ; ".join(l.get("problemes") or []) or None, None, 46)]
    n = len(cols)
    tete = _entete(ws, projet, nom, normes, n)

    for j, (titre, unite, _, _, larg) in enumerate(cols, start=1):
        c = ws.cell(row=tete, column=j, value=f"{titre}\n({unite})" if unite else titre)
        c.font = Font(bold=True, color=GRAPHITE, size=10)
        c.fill = PatternFill("solid", fgColor=FOND_TETE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=TRAIT_FORT, top=TRAIT)
        ws.column_dimensions[get_column_letter(j)].width = larg
    ws.row_dimensions[tete].height = 32

    for i, ligne in enumerate(lignes, start=tete + 1):
        for j, (_, _, f, fmt, _) in enumerate(cols, start=1):
            try:
                v = f(ligne)
            except Exception:
                v = None
            c = ws.cell(row=i, column=j, value=v)
            c.border = Border(bottom=TRAIT)
            if fmt and isinstance(v, (int, float)):
                c.number_format = fmt
                c.alignment = Alignment(horizontal="right")
            if j == n:
                c.alignment = Alignment(wrap_text=True, vertical="top")
                c.font = Font(size=9, color="4A5560")
        etat = ws.cell(row=i, column=n - 1)
        etat.font = Font(bold=True, color={"verifie": VERIFIE, "incomplet": "8A5A00"}.get(ligne.get("statut"), ARMATURE))

    derniere = tete + max(len(lignes), 1)
    zone = f"A{tete + 1}:{get_column_letter(n)}{derniere}"
    col_etat = get_column_letter(n - 1)
    # surlignage des lignes à reprendre (reste juste si l'utilisateur trie ou filtre)
    ws.conditional_formatting.add(zone, FormulaRule(
        formula=[f'OR(${col_etat}{tete + 1}="À revoir",${col_etat}{tete + 1}="Erreur")'],
        fill=PatternFill("solid", fgColor=FOND_REVOIR)))
    ws.conditional_formatting.add(zone, FormulaRule(
        formula=[f'${col_etat}{tete + 1}="Incomplet"'], fill=PatternFill("solid", fgColor=FOND_INCOMPLET)))
    ws.auto_filter.ref = f"A{tete}:{get_column_letter(n)}{derniere}"
    ws.freeze_panes = ws.cell(row=tete + 1, column=2)
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = f"{tete}:{tete}"
    return ws


def _arm(l: dict, cle: str):
    return _r(l, "resultats", cle, "ferraillage", "choix")


DALLES: List[Colonne] = [
    ("Élément", "", lambda l: l.get("nom"), None, 11),
    ("Niveau", "", lambda l: l.get("niveau"), None, 9),
    ("Appui", "", lambda l: "terre-plein" if _e(l, "appui") == "terre_plein" else "longrines / poutres", None, 16),
    ("lx", "m", lambda l: _e(l, "lx_m"), F2, 7),
    ("ly", "m", lambda l: _e(l, "ly_m"), F2, 7),
    ("h", "cm", lambda l: _e(l, "h_cm"), F1, 7),
    ("g sup.", "kN/m²", lambda l: _e(l, "g_sup_kn_m2"), F2, 8),
    ("q", "kN/m²", lambda l: _e(l, "q_kn_m2"), F2, 8),
    ("pu", "kN/m²", lambda l: _r(l, "charges", "pu_kn_m2"), F2, 8),
    ("M0x", "kN.m/m", lambda l: _r(l, "m0x_knm"), F2, 8),
    ("As x", "cm²/m", lambda l: _r(l, "resultats", "x_travee", "as_retenue_cm2_m"), F2, 8),
    ("As y", "cm²/m", lambda l: _r(l, "resultats", "y_travee", "as_retenue_cm2_m"), F2, 8),
    ("Travée lx", "", lambda l: _arm(l, "x_travee"), None, 12),
    ("Travée ly", "", lambda l: _arm(l, "y_travee"), None, 12),
    ("Chapeaux", "", lambda l: _arm(l, "appuis"), None, 12),
    ("Treillis", "", lambda l: _r(l, "treillis", "designation"), None, 20),
]


def classeur_resultats(lot: dict, projet: dict, bureau: Optional[dict] = None) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    _entete(ws, projet, "Note de calcul", "BAEL 91 rév. 99 · RPS 2000 v2011", 6)
    bureau = bureau or {}
    r = 5
    for k, v in [("Bureau d'études", bureau.get("nom")), ("Ingénieur", bureau.get("ingenieur")),
                 ("Projet", projet.get("projet")), ("Maître d'ouvrage", projet.get("client")),
                 ("Site", projet.get("site")), ("Indice", projet.get("indice")),
                 ("Date", datetime.date.today().strftime("%d/%m/%Y"))]:
        ws.cell(row=r, column=1, value=k).font = Font(color="4A5560")
        ws.cell(row=r, column=2, value=v or "—").font = Font(bold=True)
        r += 1

    r += 1
    m = lot.get("materiaux") or {}
    ws.cell(row=r, column=1, value="Matériaux et sol").font = Font(bold=True, size=12, color=GRAPHITE)
    r += 1
    for k, v, u in [("fc28", m.get("fc28_mpa"), "MPa"), ("fe", m.get("fe_mpa"), "MPa"),
                    ("σsol admissible", m.get("sigma_sol_bar"), "bar"),
                    ("Fissuration", {"peu_prejudiciable": "Peu préjudiciable", "prejudiciable": "Préjudiciable",
                                     "tres_prejudiciable": "Très préjudiciable"}.get(m.get("fissuration"), m.get("fissuration")), "")]:
        ws.cell(row=r, column=1, value=k).font = Font(color="4A5560")
        ws.cell(row=r, column=2, value=v)
        ws.cell(row=r, column=3, value=u).font = Font(color="7D8790")
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Bilan").font = Font(bold=True, size=12, color=GRAPHITE)
    r += 1
    entetes = ["Famille", "Éléments", "Vérifiés", "À revoir", "Incomplets", "Erreurs"]
    for j, t in enumerate(entetes, start=1):
        c = ws.cell(row=r, column=j, value=t)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=FOND_TETE)
        c.border = Border(bottom=TRAIT_FORT)
    r += 1
    total = [0] * 5
    for cle, nom, _, _ in FAMILLES + ([("dalles", "Dalles", "", None)] if lot.get("dalles") else []):
        lignes = lot.get(cle) or []
        valeurs = [len(lignes)] + [sum(1 for l in lignes if l.get("statut") == s)
                                   for s in ("verifie", "a_revoir", "incomplet", "erreur")]
        total = [a + b for a, b in zip(total, valeurs)]
        ws.cell(row=r, column=1, value=nom)
        for j, v in enumerate(valeurs, start=2):
            c = ws.cell(row=r, column=j, value=v)
            if j >= 4 and v:
                c.font = Font(bold=True, color=ARMATURE)
        r += 1
    ws.cell(row=r, column=1, value="Total").font = Font(bold=True)
    for j, v in enumerate(total, start=2):
        c = ws.cell(row=r, column=j, value=v)
        c.font = Font(bold=True)
        c.border = Border(top=TRAIT_FORT)
    r += 2
    ws.cell(row=r, column=1, value="Les textes officiels BAEL et RPS font foi. Résultats à vérifier par l'ingénieur "
                                   "responsable avant exécution.").font = Font(italic=True, size=9, color="7D8790")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 34
    for col in "CDEF":
        ws.column_dimensions[col].width = 12

    for cle, nom, normes, colonnes in FAMILLES:
        _feuille(wb, nom, normes, colonnes, lot.get(cle) or [], projet)
    if lot.get("dalles"):
        _feuille(wb, "Dalles", "BAEL 91 rév. 99 — A.8.2, Annexe E3 (dalles pleines, dont dalles de fondation)",
                 DALLES, lot["dalles"], projet)
    wb.metre = feuilles_metre(wb, lot, projet)
    return wb


def classeur_octets(lot: dict, projet: dict, bureau: Optional[dict] = None) -> bytes:
    flux = io.BytesIO()
    classeur_resultats(lot, projet, bureau).save(flux)
    return flux.getvalue()


# ───────────────────────── métré béton et acier ─────────────────────────

NOMS_FAMILLE = {"poteaux": "Poteau", "poutres": "Poutre", "semelles": "Semelle", "voiles": "Voile"}

METRE = [
    ("Élément", "", lambda l: l.get("rubrique") or NOMS_FAMILLE.get(l["famille"]), None, 12),
    ("Repère", "", lambda l: l["nom"], None, 12),
    ("Axe", "", lambda l: l["axe"], None, 7),
    ("Niveau", "", lambda l: l["niveau"], None, 9),
    ("Type", "", lambda l: l["type"], None, 7),
    ("Section", "cm", lambda l: l["section"], None, 16),
    ("Hauteur / portée", "m", lambda l: l["longueur_m"], "0.00", 10),
    ("Béton", "m³", lambda l: l["beton_m3"], "0.000", 10),
    ("Aciers principaux", "", lambda l: l["principal"], None, 13),
    ("Ø princ.", "mm", lambda l: l["principal_d_mm"], "0", 8),
    ("Nb barres", "", lambda l: l["principal_nb"], "0", 8),
    ("Long. unitaire", "m", lambda l: l["principal_l_m"], "0.00", 10),
    ("Long. totale", "m", lambda l: round(l["principal_nb"] * l["principal_l_m"], 2) if l["principal_nb"] else None, "0.00", 10),
    ("Poids princ.", "kg", lambda l: l["principal_kg"], "0.0", 10),
    ("Ø cadres", "mm", lambda l: l["cadres_d_mm"], "0", 8),
    ("Nb cadres", "", lambda l: l["cadres_nb"], "0", 8),
    ("Long. unit. cadre", "m", lambda l: l["cadres_l_m"], "0.00", 10),
    ("Poids cadres", "kg", lambda l: l["cadres_kg"], "0.0", 10),
    ("Autres aciers", "kg", lambda l: l["autres_kg"], "0.0", 10),
    ("Poids total", "kg", lambda l: l["acier_kg"], "0.0", 10),
    ("Ratio", "kg/m³", lambda l: l["ratio_kg_m3"], "0.0", 9),
]


def _table(ws, r: int, entetes: Sequence[str], rangs: Sequence[Sequence], formats: Sequence[Optional[str]],
           total: Optional[Sequence] = None) -> int:
    """Petit tableau à en-tête grisé ; renvoie la ligne qui suit."""
    for j, t in enumerate(entetes, start=1):
        c = ws.cell(row=r, column=j, value=t)
        c.font = Font(bold=True, color=GRAPHITE)
        c.fill = PatternFill("solid", fgColor=FOND_TETE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=TRAIT_FORT, top=TRAIT)
    for rang in rangs:
        r += 1
        for j, (v, fmt) in enumerate(zip(rang, formats), start=1):
            c = ws.cell(row=r, column=j, value=v)
            c.border = Border(bottom=TRAIT)
            if fmt and isinstance(v, (int, float)):
                c.number_format = fmt
    if total:
        r += 1
        for j, (v, fmt) in enumerate(zip(total, formats), start=1):
            c = ws.cell(row=r, column=j, value=v)
            c.font = Font(bold=True)
            c.border = Border(top=TRAIT_FORT)
            if fmt and isinstance(v, (int, float)):
                c.number_format = fmt
    return r + 2


def feuilles_metre(wb: Workbook, lot: dict, projet: dict) -> dict:
    """Feuilles « Métré poteaux », « Métré poutres »… (une ligne par élément) et « Récapitulatif métré »."""
    from metre import metre
    m = metre(lot)
    for fam, titre in (("poteaux", "poteaux"), ("poutres", "poutres"), ("semelles", "semelles"), ("voiles", "voiles"),
                       ("dalles", "dalles")):
        ls = [l for l in m["lignes"] if l["famille"] == fam]
        if ls:
            ws_f = _feuille(wb, f"Métré {titre}", "béton et acier par élément", METRE[1:], ls, projet)
            ws_f["A2"] = f"Métré détaillé des {titre} — béton et acier"

    ws = wb.create_sheet("Récapitulatif métré")
    _entete(ws, projet, "Récapitulatif du métré", "béton et acier", 7)
    r = 5
    ws.cell(row=r, column=1, value="Totaux").font = Font(bold=True, size=12, color=GRAPHITE)
    r += 1
    for k, v, fmt, u in [("Nombre d'éléments", len(m["lignes"]), "0", ""),
                         ("Béton", m["beton_total_m3"], "0.000", "m³"),
                         ("Acier", m["acier_total_kg"], "#,##0.0", "kg"),
                         ("Ratio acier / béton armé", m["ratio_kg_m3"], "0.0", "kg/m³"),
                         (f"Barres de {m['longueur_commerciale_m']:g} m", m["barres_total"], "0", "barres")]:
        ws.cell(row=r, column=1, value=k).font = Font(color="4A5560")
        c = ws.cell(row=r, column=2, value=v)
        c.font = Font(bold=True)
        c.number_format = fmt
        ws.cell(row=r, column=3, value=u).font = Font(color="7D8790")
        r += 1
    r += 1
    ws.cell(row=r, column=1, value="Par famille").font = Font(bold=True, size=12, color=GRAPHITE)
    r = _table(ws, r + 1, ["Rubrique", "Éléments", "Béton (m³)", "Acier (kg)", "Ratio (kg/m³)", "Détail acier (kg)", "Non ferraillés"],
               [[f["famille"], f["elements"], f["beton_m3"], f["acier_kg"], f["ratio_kg_m3"],
                 " ; ".join(f"{u} {kg:.1f}" for u, kg in f["acier_par_usage_kg"].items()), f["non_ferrailles"] or None]
                for f in m["familles"]],
               [None, "0", "0.000", "#,##0.0", "0.0", None, "0"],
               ["Total", len(m["lignes"]), m["beton_total_m3"], m["acier_total_kg"], m["ratio_kg_m3"], None, None])
    ws.cell(row=r, column=1, value="Par diamètre et usage").font = Font(bold=True, size=12, color=GRAPHITE)
    L = m["longueur_commerciale_m"]
    r = _table(ws, r + 1, ["Diamètre", "Usage", "kg/m", "Longueur totale (m)", "Poids (kg)", f"Barres de {L:g} m"],
               [[f"HA{d['diametre_mm']}", d["usage"], d["kg_m"], d["longueur_m"], d["poids_kg"], d["barres"]]
                for d in m["par_diametre_usage"]],
               [None, None, "0.000", "#,##0.00", "#,##0.0", "0"])
    ws.cell(row=r, column=1, value="Par diamètre (toutes utilisations)").font = Font(bold=True, size=12, color=GRAPHITE)
    r = _table(ws, r + 1, ["Diamètre", "Longueur totale (m)", "Poids (kg)", "% du total", f"Barres de {L:g} m"],
               [[f"HA{d['diametre_mm']}", d["longueur_m"], d["poids_kg"], d["part_pct"], d["barres"]] for d in m["par_diametre"]],
               [None, "#,##0.00", "#,##0.0", "0.0", "0"],
               ["Total", round(sum(d["longueur_m"] for d in m["par_diametre"]), 2), m["acier_total_kg"], 100.0, m["barres_total"]])
    ws.cell(row=r, column=1, value="Hypothèses du métré").font = Font(bold=True, size=12, color=GRAPHITE)
    notes = list(m["hypotheses"])
    if m["sans_beton"]:
        notes.append("Sans béton (dimension manquante) : " + ", ".join(m["sans_beton"]) + ".")
    for h in notes:
        r += 1
        ws.cell(row=r, column=1, value=f"• {h}").font = Font(size=9, color="4A5560")
    if abs(m["acier_total_kg"] - m["poids_nomenclature_kg"]) > 0.5:
        r += 2
        ws.cell(row=r, column=1, value=f"ALERTE ECART ARITHMETIQUE : métré {m['acier_total_kg']} kg, nomenclature des plans "
                                        f"{m['poids_nomenclature_kg']} kg.").font = Font(bold=True, color=ARMATURE)
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 18
    for col, w in zip("CDEFG", (14, 18, 14, 48, 14)):
        ws.column_dimensions[col].width = w
    return {"beton_total_m3": m["beton_total_m3"], "acier_total_kg": m["acier_total_kg"],
            "ratio_kg_m3": m["ratio_kg_m3"], "barres_total": m["barres_total"],
            "longueur_commerciale_m": m["longueur_commerciale_m"]}
