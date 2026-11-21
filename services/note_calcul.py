"""Note de calcul — présentation d'un bureau d'études structure (BET) marocain.

Structure attendue par les bureaux de contrôle pour un dossier d'exécution :
  page de garde (intervenants, phase, tableau des indices, visas)
  sommaire
  1 Présentation de l'ouvrage           5 Étude sismique (RPS 2000 v2011)
  2 Règlements et documents de référence 6 Dimensionnement des éléments
  3 Hypothèses de calcul                   (tableau par type + exemple de calcul détaillé)
  4 Modélisation                         7 Quantités de béton et d'acier
                                         8 Conclusion, réserves et visas

Les éléments identiques sont regroupés en types (P1, Pt1, S1, V1), comme sur les
plans ; un exemple de calcul détaillé est donné pour l'élément le plus sollicité de
chaque famille, avec les valeurs numériques substituées dans les formules du BAEL.
Mise en page A4 : en-tête et pied de page sur chaque page (sauf la garde), pagination.
"""
from __future__ import annotations

import datetime
import html
import math
import re
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

GAMMA_B, GAMMA_S, ETA_HA = 1.5, 1.15, 1.6

# ═════════════════════ mise en forme LaTeX : polices, formules ═════════════════════

import base64
import pathlib

from tex_mathml import mathml

POLICES = pathlib.Path(__file__).resolve().parent / "polices"


def _police(nom: str) -> str:
    try:
        return base64.b64encode((POLICES / nom).read_bytes()).decode()
    except OSError:      # police absente : le navigateur se rabat sur une police à empattements
        return ""


def polices_css() -> str:
    """Police des formules embarquée (Latin Modern Math, licence GUST, voir polices/GUST-FONT-LICENSE.txt) :
    les formules gardent leur rendu partout, y compris en PDF. Le texte utilise Arial, police système."""
    faces = []
    for famille, fichier, graisse, style in (
            ("Latin Modern Math", "latinmodern-math.woff2", "normal", "normal"),):
        b64 = _police(fichier)
        if b64:
            faces.append(f'@font-face {{ font-family: "{famille}"; font-weight: {graisse}; font-style: {style}; '
                         f'src: url(data:font/woff2;base64,{b64}) format("woff2"); }}')
    return "\n".join(faces)


def tx(x, n: int = 2) -> str:
    r"""Nombre au format français, en syntaxe LaTeX : 1\,295{,}6."""
    if x is None:
        return r"\text{—}"
    if not isinstance(x, (int, float)):
        return r"\text{" + str(x) + "}"
    return f"{x:,.{n}f}".replace(",", "\x00").replace(".", "{,}").replace("\x00", r"\,")


class Equations:
    """Formules centrées et numérotées (1), (2)… comme l'environnement equation de LaTeX."""

    def __init__(self):
        self.n = 0

    def __call__(self, tex: str) -> str:
        self.n += 1
        return f'<div class="equation">{mathml(tex, bloc=True)}<span class="no">({self.n})</span></div>'


def im(tex: str) -> str:
    """Formule dans le texte."""
    return mathml(tex)


def esc(v: Any) -> str:
    return html.escape("" if v is None else str(v))


def fr(x: Any, n: int = 2) -> str:
    """Nombre au format français : 1 234,56."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "—"
    if not isinstance(x, (int, float)):
        return esc(x)
    t = f"{x:,.{n}f}".replace(",", "\u202f").replace(".", ",")
    return t


def _css_chaine(t: str) -> str:
    return '"' + str(t).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


# ───────────────────────── matériaux ─────────────────────────

def materiaux(inp: dict) -> dict:
    m = dict((inp.get("lot") or {}).get("materiaux") or {})
    fc = float(m.get("fc28_mpa") or _premier(inp, "fc28_mpa") or 25.0)
    fe = float(m.get("fe_mpa") or 500.0)
    fiss = m.get("fissuration") or "prejudiciable"
    sol = m.get("sigma_sol_bar") or next((s.get("sigma_sol_bar") for s in (inp.get("semelles_isolees") or [])
                                          if s.get("sigma_sol_bar")), None)
    ft = 0.6 + 0.06 * fc
    lim_prej = min(2 / 3 * fe, max(0.5 * fe, 110 * math.sqrt(ETA_HA * ft)))
    sigma_st = {"peu_prejudiciable": 2 / 3 * fe, "prejudiciable": lim_prej, "tres_prejudiciable": 0.8 * lim_prej}[fiss]
    return {
        "fc28": fc, "ft28": ft, "fbu": 0.85 * fc / GAMMA_B, "sigma_bc": 0.6 * fc,
        "Eij": 11000 * fc ** (1 / 3), "Evj": 3700 * fc ** (1 / 3),
        "fe": fe, "fsu": fe / GAMMA_S, "sigma_st": sigma_st, "fissuration": fiss,
        "sigma_sol": sol,
        "enrobage_poteau": m.get("enrobage_poteau_mm", 30), "enrobage_poutre": m.get("enrobage_poutre_mm", 40),
        "enrobage_semelle": m.get("enrobage_semelle_mm", 50),
    }


def _premier(inp: dict, cle: str):
    for fam in ("poteaux", "poutres", "voiles"):
        for e in inp.get(fam) or []:
            if e.get(cle):
                return e[cle]
    return None


SYSTEMES = {"portiques_ba": "portiques en béton armé", "voile_portique": "système mixte voiles-portiques",
            "voile": "voiles en béton armé", "voiles_couples": "voiles couplés",
            "acier_noeuds_rigides": "portiques en acier à nœuds rigides", "ossature_contreventee": "ossature contreventée en acier"}
CLASSES = {"classe_I": "Classe I (bâtiments d'importance vitale)", "classe_II": "Classe II (bâtiments du grand public)",
           "classe_III": "Classe III (bâtiments ordinaires)"}
DUCTILITE = {"ND1": "ND1 (ductilité limitée)", "ND2": "ND2 (ductilité moyenne)", "ND3": "ND3 (ductilité élevée)"}

FISSURATION = {"peu_prejudiciable": "peu préjudiciable", "prejudiciable": "préjudiciable",
               "tres_prejudiciable": "très préjudiciable"}


# ───────────────────────── vérifications et types ─────────────────────────

def ok_poteau(p: dict) -> bool:
    fc = p.get("flexion_composee") or {}
    tm = fc.get("taux_utilisation_moment")
    return ((p.get("nu_rapport") or 0) <= 1 and p.get("section_suffisante", True) is not False
            and p.get("applicable_b841", True) is not False and not fc.get("capacite_insuffisante")
            and not (isinstance(tm, (int, float)) and tm > 1))


def ok_poutre(p: dict) -> bool:
    return ((p.get("els") or {}).get("sigma_st_ok", True) and (p.get("effort_tranchant") or {}).get("tau_u_ok", True)
            and p.get("mode", "simple") == "simple")


def ok_semelle(s: dict) -> bool:
    return bool((s.get("poinconnement") or {}).get("ok", True)) and (s.get("sigma_min_bar") or 0) >= 0


def ok_voile(v: dict) -> bool:
    return bool(v.get("compression_ok", True)) and bool(v.get("tau_ok", True))


def _nom(e: dict, i: int, prefixe: str) -> str:
    return f"{e.get('nom')}{' (' + e['niveau'] + ')' if e.get('niveau') else ''}" if e.get("nom") else f"{prefixe}{i + 1}"


def grouper(elements: List[dict], cle, prefixe: str, verif) -> List[dict]:
    groupes: "OrderedDict[tuple, dict]" = OrderedDict()
    for i, e in enumerate(elements):
        g = groupes.setdefault(cle(e), {"elements": [], "noms": [], "ok": True})
        g["elements"].append(e)
        g["noms"].append(_nom(e, i, prefixe))
        g["ok"] = g["ok"] and verif(e)
    out = []
    for n, g in enumerate(groupes.values(), start=1):
        g["code"] = f"{prefixe}{n}"
        out.append(g)
    return out


def liste_noms(noms: List[str], maxi: int = 4) -> str:
    if len(noms) <= maxi:
        return ", ".join(noms)
    return ", ".join(noms[:maxi]) + f" et {len(noms) - maxi} autres"


def etat(ok: bool) -> str:
    return '<span class="ok">Vérifié</span>' if ok else '<span class="ko">À reprendre</span>'


# ───────────────────────── fragments HTML ─────────────────────────

class Tableaux:
    r"""Légendes numérotées « Tableau 1 — … », comme \caption dans LaTeX."""

    def __init__(self):
        self.n = 0

    def legende(self, titre: Optional[str]) -> str:
        if not titre:
            return ""
        self.n += 1
        return f"<caption>Tableau {self.n} — {titre}</caption>"


TAB = Tableaux()
LIGNES_INSECABLES = 8      # en dessous, le tableau n'est jamais coupé entre deux pages


def ent(libelle: str, unite: str = "") -> str:
    """En-tête de colonne : libellé, puis l'unité sur une seconde ligne."""
    return f'{libelle}<br><span class="u">({unite})</span>' if unite else libelle


def _insecable(html_tableau: str, nb_lignes: int) -> str:
    return f'<div class="bloc">{html_tableau}</div>' if nb_lignes <= LIGNES_INSECABLES else html_tableau


_INSECABLE = re.compile(r"\d+ HA\d+|HA\d+ e=\d+|\d+(?:,\d+)? × \d+(?:,\d+)?|\S+ à \S+")


def _cellule(v) -> str:
    """« 7 HA10 », « 25 × 50 », « R+2 à R+4 » ne se coupent jamais. Pas d'espace insécable :
    dans Latin Modern il est plus large qu'une espace ordinaire."""
    return _INSECABLE.sub(lambda m: f'<span class="nw">{m.group(0)}</span>', str(v))


def tableau(entetes: List[str], lignes: List[List[str]], classes: Optional[List[str]] = None, cls: str = "",
            largeurs: Optional[List[int]] = None, titre: Optional[str] = None) -> str:
    """largeurs : colonnes en % (mise en page fixe, comme tabularx) ; sinon largeur automatique.
    titre : légende numérotée au-dessus du tableau."""
    classes = classes or [""] * len(entetes)
    cols = ("<colgroup>" + "".join(f'<col style="width:{w}%">' for w in largeurs) + "</colgroup>") if largeurs else ""
    if largeurs:
        cls = (cls + " fixe").strip()
    th = "".join(f'<th class="{c}">{e}</th>' for e, c in zip(entetes, classes))
    # « 7 HA10 » ne se coupe jamais entre le nombre et le diamètre
    corps = "".join("<tr>" + "".join(f'<td class="{c}">{_cellule(v)}</td>' for v, c in zip(l, classes))
                    + "</tr>" for l in lignes)
    t = f'<table class="{cls}">{TAB.legende(titre)}{cols}<thead><tr>{th}</tr></thead><tbody>{corps}</tbody></table>'
    return _insecable(t, len(lignes))


def kv(lignes: List[Tuple[str, str]], cls: str = "kv", titre: Optional[str] = None,
       entetes: Tuple[str, str] = ("Désignation", "Valeur")) -> str:
    """Tableau à deux colonnes (désignation, valeur)."""
    tete = f"<thead><tr><th>{entetes[0]}</th><th>{entetes[1]}</th></tr></thead>" if titre else ""
    t = (f'<table class="{cls}">{TAB.legende(titre)}{tete}<tbody>'
         + "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in lignes) + "</tbody></table>")
    return _insecable(t, len(lignes))


def kv4(lignes: List[Tuple[str, str, str, str]], titre: str) -> str:
    """Hypothèses : désignation, symbole (LaTeX), valeur, unité — la présentation usuelle d'un BET."""
    rangs = [[d, im(sym) if sym else "—", v, u or "—"] for d, sym, v, u in lignes]
    return tableau(["Désignation", "Symbole", "Valeur", "Unité"], rangs, ["", "c", "n", ""], "hyp",
                   largeurs=[44, 30, 14, 12], titre=titre)


def reperes(groupe: dict, prefixe: str) -> str:
    """Repères distincts du type (« A1, C1, A3 »), sans le préfixe ni le niveau."""
    vus: List[str] = []
    for e in groupe["elements"]:
        r = str(e.get("nom") or "").strip()
        if r.startswith(prefixe + " "):
            r = r[len(prefixe) + 1:]
        if r and r not in vus:
            vus.append(r)
    return ", ".join(vus) or "—"


def niveaux(groupe: dict) -> str:
    """Niveaux concernés : « RDC », « RDC, R+1 » ou « R+2 à R+4 »."""
    vus: List[str] = []
    for e in groupe["elements"]:
        n = e.get("niveau")
        if n and n not in vus:
            vus.append(n)
    if not vus:
        return "—"
    return ", ".join(vus) if len(vus) <= 2 else f"{vus[0]} à {vus[-1]}"


def calcul(lignes: List[Tuple[str, str, str]]) -> str:
    """Exemple de calcul : (désignation, formule avec valeurs, résultat)."""
    return '<table class="calcul"><tbody>' + "".join(
        f"<tr><td class='des'>{d}</td><td class='form'>{f}</td><td class='res'>{r}</td></tr>" for d, f, r in lignes) + "</tbody></table>"


CSS = r"""
@page { size: A4; margin: 25mm 18mm 22mm 20mm;
  @top-left { content: %(entete_g)s; font: bold 8.5pt Arial, Helvetica, sans-serif; color: #000;
    vertical-align: bottom; padding-bottom: 2mm; border-bottom: .75pt solid #000; }
  @top-right { content: %(entete_d)s; font: 8.5pt Arial, Helvetica, sans-serif; color: #000;
    vertical-align: bottom; padding-bottom: 2mm; border-bottom: .75pt solid #000; }
  @bottom-left { content: %(pied_g)s; font: 8pt Arial, Helvetica, sans-serif; color: #333;
    vertical-align: top; padding-top: 2mm; border-top: .5pt solid #000; }
  @bottom-center { content: none; border-top: .5pt solid #000; }
  @bottom-right { content: "Page " counter(page) " / " counter(pages); font: 8pt Arial, Helvetica, sans-serif; color: #333;
    vertical-align: top; padding-top: 2mm; border-top: .5pt solid #000; }
}
@page :first { margin: 12mm;
  @top-left { content: none; border: none; } @top-right { content: none; border: none; }
  @bottom-left { content: none; border: none; } @bottom-center { content: none; border: none; } @bottom-right { content: none; border: none; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font: 10pt/1.4 Arial, Helvetica, "Liberation Sans", sans-serif; color: #000; }
.ecran { max-width: 172mm; margin: 0 auto; padding: 12mm 0; }
@media print { .ecran { max-width: none; padding: 0; } }
p { margin: 0 0 6pt; text-align: justify; hyphens: auto; }
math { font-family: "Latin Modern Math", "Cambria Math", serif; font-size: 1.08em; }
h2, h3, h4 { font-weight: bold; break-after: avoid; }
h2 { font-size: 13pt; margin: 2pt 0 10pt; padding: 3pt 6pt; color: #fff; background: #8a3324; }
h2 .num { display: inline-block; min-width: 1.6em; }
h3 { font-size: 11pt; margin: 14pt 0 6pt; color: #8a3324; border-bottom: .75pt solid #8a3324; padding-bottom: 1pt; }
h4 { font-size: 10pt; margin: 12pt 0 4pt; text-decoration: underline; }
ul { margin: 4pt 0 8pt; padding-left: 1.5em; } li { margin: 2pt 0; text-align: justify; }
/* tableaux quadrillés, comme dans les notes des bureaux d'études */
table { width: 100%; border-collapse: collapse; margin: 4pt 0 12pt; font-size: 9pt; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
th, td { padding: 2.5pt 4pt; vertical-align: middle; text-align: left; border: .5pt solid #000; }
thead th { font-weight: bold; background: #e9e2d3; text-align: center; vertical-align: middle; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
thead th, thead th.n { white-space: normal; text-align: center; }
th .u { font-weight: normal; font-size: 8pt; }
caption { caption-side: top; text-align: center; font-size: 9pt; font-weight: bold; padding: 0 0 3pt; }
.bloc { break-inside: avoid; }   /* tableau court : jamais coupé entre deux pages */
p:has(+ .bloc), p:has(+ .equation), .equation:has(+ .bloc), h3:has(+ .bloc), h3:has(+ p + .bloc),
h2 + p { break-after: avoid; }   /* le texte qui l'annonce reste avec lui */
table.hyp td:nth-child(2) { text-align: center; }
td.c, th.c { text-align: center; }
.nw { white-space: nowrap; }
table.kv th { width: 45%; font-weight: bold; background: #f4f0e6; }
table.calcul td { padding: 3pt 5pt; }
table.calcul td.des { width: 24%; font-weight: bold; background: #f4f0e6; }
table.calcul td.res { width: 20%; text-align: right; white-space: nowrap; font-weight: bold; }
table.calcul math { math-style: normal; }   /* fractions en taille d'affichage */
table.fixe { table-layout: fixed; }
table.fixe td.el { overflow-wrap: anywhere; }
.equation { display: flex; align-items: center; margin: 8pt 0 10pt; break-inside: avoid; }
.equation math { flex: 1; }
.equation .no { width: 3em; text-align: right; }
.ok, .ko { white-space: nowrap; font-weight: bold; }
.ok { color: #1f5c32; } .ko { color: #b01e1e; }
.note { font-size: 8.5pt; }
.reserve { border: .75pt solid #b01e1e; padding: 5pt 8pt; margin: 8pt 0; }
.saut { break-before: page; }

/* page de garde : cadre double, frise de zellige, cartouche quadrillé */
.garde { height: 272mm; border: 2.25pt double #000; display: flex; flex-direction: column; overflow: hidden; }
.garde .frise { height: 10mm; background: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40' viewBox='0 0 40 40'><rect width='40' height='40' fill='%238a3324'/><g fill='%231f4d3a'><path d='M0 0H8L0 8Z'/><path d='M40 0H32L40 8Z'/><path d='M0 40H8L0 32Z'/><path d='M40 40H32L40 32Z'/></g><g fill='%23efe3c4'><rect x='9' y='9' width='22' height='22'/><rect x='9' y='9' width='22' height='22' transform='rotate(45 20 20)'/></g><g fill='%238a3324'><rect x='14' y='14' width='12' height='12'/><rect x='14' y='14' width='12' height='12' transform='rotate(45 20 20)'/></g><g fill='%231f4d3a'><rect x='17' y='17' width='6' height='6' transform='rotate(45 20 20)'/></g></svg>") repeat-x; background-size: 10mm 10mm; border-bottom: .75pt solid #000; }
.garde .bet { display: flex; gap: 6mm; align-items: center; padding: 6mm 8mm; border-bottom: .75pt solid #000; }
.garde .bet img { max-height: 22mm; max-width: 45mm; }
.garde .bet-nom { font-size: 14pt; font-weight: bold; color: #8a3324; text-transform: uppercase; }
.garde .bet-coord { font-size: 8.5pt; margin-top: 1mm; }
.garde .corps { flex: 1; display: flex; flex-direction: column; padding: 0 8mm; text-align: center; }
.garde .t1 { margin: 22mm auto 0; padding: 5mm 14mm; border: 1.5pt solid #000; font-size: 24pt; font-weight: bold;
  text-transform: uppercase; letter-spacing: .04em; }
.garde .sur-titre { font-size: 11pt; font-weight: bold; margin-top: 6mm; }
.garde .objet { font-size: 13pt; font-weight: bold; color: #8a3324; margin: 8mm 6mm 10mm; }
.garde table.inter { width: 100%; text-align: left; }
.garde .pied { margin-top: auto; padding-bottom: 6mm; text-align: left; }
.garde .visas { display: flex; margin-top: -1pt; }
.garde .visa { flex: 1; border: .5pt solid #000; height: 28mm; padding: 2mm 3mm; font-size: 8.5pt; font-weight: bold; position: relative; }
.garde .visa + .visa { border-left: none; }
.garde .visa img { position: absolute; right: 3mm; bottom: 2mm; max-height: 22mm; max-width: 38mm; }
.garde .bande-bas { border-top: .75pt solid #000; padding: 3mm 8mm; display: flex; justify-content: space-between; font-size: 8.5pt; }
.garde .frise.bas { border-bottom: none; border-top: .75pt solid #000; }

/* sommaire */
.sommaire { list-style: none; padding: 0; margin: 8pt 0; }
.sommaire > li { font-weight: bold; margin: 8pt 0 2pt; display: flex; flex-direction: column; }
.sommaire > li > a, .sommaire li a { color: inherit; text-decoration: none; }
.sommaire .sn { display: inline-block; min-width: 2em; }
.sommaire ol { list-style: none; padding-left: 2em; margin: 2pt 0 0; font-weight: normal; }
.sommaire ol li { margin: 1.5pt 0; }
/* conclusion et signatures restent sur la même page */
.conclusion { display: inline-block; width: 100%; }   /* bloc insécable : jamais coupé entre deux pages */
/* bloc de signatures : un rang de tableau, que le navigateur ne coupe pas entre deux pages */
table.signatures { margin-top: 12mm; table-layout: fixed; break-inside: avoid; }
table.signatures td { width: 33.3%; height: 34mm; padding: 2mm 3mm 0; font-size: 9pt; font-weight: bold; position: relative; vertical-align: top; }
table.signatures img { position: absolute; right: 2mm; bottom: 2mm; max-height: 24mm; max-width: 38mm; }
"""


# ───────────────────────── sections ─────────────────────────

def page_de_garde(inp: dict, bur: dict, date: str) -> str:
    logo = f'<img src="data:image/png;base64,{esc(bur["logo_base64"])}" alt="">' if bur.get("logo_base64") else ""
    cachet = f'<img src="data:image/png;base64,{esc(bur["cachet_base64"])}" alt="">' if bur.get("cachet_base64") else ""
    coord = " — ".join(x for x in [bur.get("adresse"), f"Tél. {bur['telephone']}" if bur.get("telephone") else "",
                                   bur.get("email")] if x)
    ident = " — ".join(f"{k} {bur[c]}" for k, c in (("RC", "rc"), ("ICE", "ice"), ("Patente", "patente"), ("IF", "if_")) if bur.get(c))
    inter = [("Maître d'ouvrage", inp.get("client")), ("Architecte", inp.get("architecte")),
             ("Bureau d'études structure", bur.get("nom")), ("Bureau de contrôle", inp.get("controle")),
             ("Laboratoire (étude géotechnique)", inp.get("laboratoire")), ("Situation", inp.get("site"))]
    return f"""<section class="garde">
  <div class="frise"></div>
  <div class="bet">{logo}<div><div class="bet-nom">{esc(bur.get('nom') or "Bureau d'études structure")}</div>
    <div class="bet-coord">{esc(coord)}</div><div class="bet-coord">{esc(ident)}</div></div></div>
  <div class="corps">
    <div class="t1">Note de calcul</div>
    <div class="sur-titre">Structure en béton armé — Phase : {esc(inp.get('phase') or 'Exécution')}</div>
    <div class="objet">{esc(inp.get('objet') or inp.get('projet') or 'Projet')}</div>
    {kv([("Projet", esc(inp.get('projet') or '—'))] + [(k, esc(v) if v else '—') for k, v in inter]
         + [("Phase", esc(inp.get('phase') or 'Exécution'))], "kv inter")}
    <div class="pied">
      {tableau(["Indice", "Date", "Objet de la révision", "Établi par", "Vérifié par"],
               [[esc(inp.get('indice') or 'A'), date, "Première diffusion", esc(bur.get('ingenieur') or ''), ""]],
               ["c", "c", "", "", ""])}
      <div class="visas"><div class="visa">Bureau d'études — cachet et signature{cachet}</div>
        <div class="visa">Bureau de contrôle — visa</div></div>
    </div>
  </div>
  <div class="bande-bas"><span>Règlements : BAEL 91 révisé 99 — RPS 2000 version 2011</span>
    <span>Indice {esc(inp.get('indice') or 'A')} du {date}</span></div>
  <div class="frise bas"></div>
</section>"""


SOMMAIRE = [
    ("s1", "Présentation de l'ouvrage", []), ("s2", "Règlements et documents de référence", []),
    ("s3", "Hypothèses de calcul", ["Béton", "Acier", "Enrobages et fissuration", "Sol de fondation", "Charges", "Combinaisons d'actions"]),
    ("s4", "Modélisation", []), ("s5", "Étude sismique (RPS 2000 version 2011)", []),
    ("s6", "Dimensionnement des éléments", ["Poteaux", "Poutres", "Semelles", "Voiles", "Dalles et balcons", "Planchers à corps creux"]),
    ("s7", "Quantités de béton et d'acier", []), ("s8", "Conclusion, réserves et visas", []),
]


def sommaire() -> str:
    lignes = []
    for ident, titre, sous in SOMMAIRE:
        n = ident[1:]
        s = "".join(f"<li><span class='sn'>{n}.{k}</span>{esc(x)}</li>" for k, x in enumerate(sous, start=1))
        lignes.append(f'<li><a href="#{ident}"><span class="sn">{n}</span>{esc(titre)}</a>{f"<ol>{s}</ol>" if s else ""}</li>')
    return f'<h2 class="saut">Table des matières</h2><ol class="sommaire">{"".join(lignes)}</ol>'


def h2(num: int, ident: str, titre: str, saut: bool = False) -> str:
    return f'<h2 id="{ident}" class="{"saut" if saut else ""}"><span class="num">{num}.</span>{esc(titre)}</h2>'


def presentation(inp: dict) -> str:
    oss = (inp.get("robot") or {}).get("ossature") or {}
    niveaux = oss.get("niveaux") or []
    s = inp.get("sismique") or {}
    d = s.get("donnees") or {}
    systeme = SYSTEMES.get(d.get("systeme"))
    lignes = [
        ("Objet", esc(inp.get("objet") or inp.get("projet") or "—")),
        ("Situation", esc(inp.get("site") or "—")),
        ("Niveaux", esc(", ".join(niveaux)) if niveaux else "—"),
        ("Hauteur totale", f"{fr(d.get('hauteur_m'))} m" if d.get("hauteur_m") else "—"),
        ("Système de contreventement", esc(systeme) if systeme else "—"),
        ("Fondations", "superficielles (semelles isolées)" if inp.get("semelles_isolees") else "—"),
    ]
    nb = [(n, len(inp.get(k) or [])) for n, k in (("poteaux", "poteaux"), ("poutres", "poutres"),
                                                    ("semelles", "semelles_isolees"), ("voiles", "voiles"))]
    compte = ", ".join(f"{c} {n}" for n, c in nb if c)
    return (h2(1, "s1", "Présentation de l'ouvrage", saut=True)
            + f"<p>La présente note a pour objet la justification de la structure en béton armé de l'ouvrage décrit ci-dessous. "
              f"Les efforts proviennent du modèle de calcul ; les hypothèses que nous avons retenues sont exposées au chapitre 3. "
              f"L'étude porte sur {esc(compte) or 'les éléments calculés'}.</p>"
            + kv(lignes, titre="Caractéristiques générales de l'ouvrage"))


def reglements(inp: dict) -> str:
    docs = [
        "<b>BAEL 91 révisé 99</b> — Règles techniques de conception et de calcul des ouvrages et constructions en béton armé suivant la méthode des états limites (DTU P 18-702).",
        "<b>RPS 2000 version 2011</b> — Règlement de construction parasismique applicable aux bâtiments au Maroc.",
        "<b>NF P 06-001</b> — Charges d'exploitation des bâtiments ; <b>NF P 06-004</b> — Charges permanentes et charges d'exploitation dues aux forces de pesanteur.",
        "<b>DTU 13.12</b> — Règles pour le calcul des fondations superficielles.",
    ]
    if inp.get("laboratoire"):
        docs.append(f"<b>Rapport géotechnique</b> établi par {esc(inp['laboratoire'])}.")
    docs.append("<b>Plans d'architecture</b> de l'ouvrage" + (f" ({esc(inp['architecte'])})." if inp.get("architecte") else "."))
    return (h2(2, "s2", "Règlements et documents de référence")
            + "<p>Les calculs ont été menés conformément aux règlements et documents suivants :</p>") + "<ul>" + "".join(f"<li>{d}</li>" for d in docs) + "</ul>"


def hypotheses(inp: dict, m: dict) -> str:
    oss = (inp.get("robot") or {}).get("ossature") or {}
    charges_modele = [h for h in (oss.get("hypotheses") or []) if "G =" in h or "kN/m²" in h]
    q = [["Habitation, logements", "1,50"], ["Bureaux", "2,50"], ["Escaliers, circulations", "2,50"],
         ["Balcons", "3,50"], ["Terrasse non accessible", "1,00"], ["Terrasse accessible", "1,50"]]
    sol = fr(m["sigma_sol"]) if m["sigma_sol"] else "à préciser"
    return "".join([
        h2(3, "s3", "Hypothèses de calcul"),
        "<p>Nous avons retenu les caractéristiques suivantes pour les matériaux, le sol de fondation et les charges.</p>",
        "<h3>3.1 Béton</h3>",
        kv4([("Résistance caractéristique à 28 jours", r"f_{c28}", fr(m["fc28"], 0), "MPa"),
             ("Résistance à la traction", r"f_{t28} = 0{,}6 + 0{,}06 \, f_{c28}", fr(m["ft28"]), "MPa"),
             ("Coefficient de sécurité", r"\gamma_b", "1,50", ""),
             ("Résistance de calcul en compression", r"f_{bu} = \frac{0{,}85 \, f_{c28}}{\theta \, \gamma_b}", fr(m["fbu"]), "MPa"),
             ("Contrainte limite de service", r"\overline{\sigma}_{bc} = 0{,}6 \, f_{c28}", fr(m["sigma_bc"], 1), "MPa"),
             ("Module de déformation instantanée", r"E_{ij} = 11\,000 \, f_{c28}^{1/3}", fr(m["Eij"], 0), "MPa"),
             ("Module de déformation différée", r"E_{vj} = 3\,700 \, f_{c28}^{1/3}", fr(m["Evj"], 0), "MPa")],
            "Caractéristiques du béton"),
        "<h3>3.2 Acier</h3>",
        kv4([("Nuance (haute adhérence)", "", f"FeE{fr(m['fe'], 0)}", ""),
             ("Limite d'élasticité", r"f_e", fr(m["fe"], 0), "MPa"),
             ("Coefficient de sécurité", r"\gamma_s", "1,15", ""),
             ("Résistance de calcul", r"f_{su} = f_e / \gamma_s", fr(m["fsu"], 1), "MPa"),
             ("Module d'élasticité", r"E_s", "200 000", "MPa"),
             ("Coefficient de fissuration", r"\eta", "1,6", "")],
            "Caractéristiques de l'acier"),
        "<h3>3.3 Enrobages et fissuration</h3>",
        kv4([("Enrobage des poteaux", "c", fr(m["enrobage_poteau"], 0), "mm"),
             ("Enrobage des poutres", "c", fr(m["enrobage_poutre"], 0), "mm"),
             ("Enrobage des fondations", "c", fr(m["enrobage_semelle"], 0), "mm"),
             ("Fissuration", "", esc(FISSURATION.get(m["fissuration"], m["fissuration"])), ""),
             ("Contrainte limite de l'acier en service", r"\overline{\sigma}_{st}", fr(m["sigma_st"], 1), "MPa")],
            "Enrobages et fissuration"),
        "<h3>3.4 Sol de fondation</h3>",
        kv4([("Contrainte admissible du sol", r"\overline{\sigma}_{sol}", sol, "bar" if m["sigma_sol"] else "")],
            "Sol de fondation"),
        "<p>Cette valeur est celle du rapport géotechnique"
        + (f" établi par {esc(inp['laboratoire'])}" if inp.get("laboratoire") else "") + ".</p>",
        "<h3>3.5 Charges</h3>",
        ("<p>Les charges permanentes G et d'exploitation Q appliquées dans le modèle sont les suivantes :</p><ul>"
         + "".join(f"<li>{esc(h)}</li>" for h in charges_modele) + "</ul>"
         if charges_modele else "<p>Les charges permanentes G et d'exploitation Q sont celles appliquées dans le modèle de calcul.</p>"),
        "<p>Pour mémoire, nous rappelons au tableau ci-dessous les charges d'exploitation réglementaires.</p>",
        tableau(["Usage", ent(im("Q"), "kN/m²")], q, ["", "n"], largeurs=[70, 30],
                titre="Charges d'exploitation de référence (NF P 06-001)"),
        "<h3>3.6 Combinaisons d'actions</h3>",
        "<p>Les sollicitations de calcul résultent des combinaisons suivantes :</p>",
        tableau(["État limite", "Combinaison"],
                [["ELU fondamental", im(r"1{,}35 \, G + 1{,}5 \, Q")], ["ELS", im("G + Q")],
                 ["Accidentelle sismique (RPS 2011)", im(r"G + \psi \, Q \pm E") + ", avec " + im(r"\psi") + " fonction de l'usage"]],
                largeurs=[40, 60], titre="Combinaisons d'actions"),
    ])


def modelisation(inp: dict) -> str:
    r = inp.get("robot") or {}
    oss = r.get("ossature") or {}
    source = {"robot": "lecture du modèle Robot Structural Analysis (Autodesk)",
              "excel": "classeur de données importé", "simulation": "exemple de démonstration"}.get(r.get("mode"), "saisie directe des efforts")
    lignes = [("Origine des efforts", esc(source))]
    if r.get("nom"):
        lignes.append(("Modèle", esc(r["nom"])))
    if oss.get("resume"):
        lignes.append(("Éléments", esc(", ".join(f"{v} {k}" for k, v in oss["resume"].items() if v))))
    if oss.get("cas_elu") or oss.get("cas_els"):
        lignes.append(("Combinaisons lues", f"ELU n° {esc(oss.get('cas_elu'))}, ELS n° {esc(oss.get('cas_els'))}"))
    comb = r.get("combinaisons") or []
    if comb:
        lignes.append(("Cas et combinaisons du modèle", esc(", ".join(map(str, comb[:12])))))
    hyp = [h for h in (oss.get("hypotheses") or []) if "G =" not in h]
    return (h2(4, "s4", "Modélisation")
            + "<p>La structure a été modélisée en trois dimensions ; les efforts utilisés dans cette note proviennent de ce modèle, "
              "pour les combinaisons définies au paragraphe 3.6.</p>" + kv(lignes, titre="Données du modèle de calcul")
            + ("<ul>" + "".join(f"<li>{esc(h)}</li>" for h in hyp) + "</ul>" if hyp else ""))


def sismique(inp: dict) -> str:
    s = inp.get("sismique")
    out = [h2(5, "s5", "Étude sismique (RPS 2000 version 2011)")]
    if not s:
        out.append("<p>L'étude sismique n'a pas été jointe à cette note.</p>")
        return "".join(out)
    d = s.get("donnees") or {}
    out.append("<p>Le bâtiment étant régulier en plan et en élévation, d'une hauteur inférieure à 60 m et d'une période "
               "fondamentale inférieure à 2 s, nous avons appliqué la méthode statique équivalente du RPS 2000 version 2011. "
               "La force sismique latérale à la base s'écrit :</p>")
    out.append(EQ(r"F = \frac{\upsilon \, S \, D \, I \, W}{K} \qquad \text{avec} \qquad W = G + \psi \, Q"))
    donnees = [(k, v) for k, v in (
        ("Zone de vitesse", f"Zone {d['zone_vitesse']}" if d.get("zone_vitesse") is not None else None),
        ("Site", d.get("site")), ("Classe de l'ouvrage", CLASSES.get(d.get("classe"), d.get("classe"))),
        ("Système de contreventement", SYSTEMES.get(d.get("systeme"), d.get("systeme"))),
        ("Niveau de ductilité", DUCTILITE.get(d.get("ductilite"), d.get("ductilite")))) if v]
    if donnees:
        out.append(kv([(k, esc(v)) for k, v in donnees], titre="Données sismiques du site et de l'ouvrage"))
    out.append(kv4([("Coefficient de vitesse", r"\upsilon", fr(s.get("nu_m_s")), ""),
                    ("Coefficient de site", "S", fr(s.get("S")), ""),
                    ("Coefficient d'importance", "I", fr(s.get("I")), ""),
                    ("Coefficient de comportement", "K", fr(s.get("K")), ""),
                    ("Coefficient d'usage", r"\psi", fr(s.get("psi")), ""),
                    ("Période fondamentale", "T", fr(s.get("T_s"), 3), "s"),
                    ("Facteur d'amplification dynamique", "D", fr(s.get("D"), 3), ""),
                    ("Poids sismique", "W", fr(s.get("W_kn"), 0), "kN"),
                    ("Effort sismique à la base", "F", f"<b>{fr(s.get('F_base_kn'), 1)}</b>", "kN"),
                    ("Force au sommet", "F_t", fr(s.get("Ft_kn"), 1), "kN")], "Paramètres du calcul sismique"))
    if s.get("W_kn") and s.get("F_base_kn"):
        out.append("<p>Numériquement, " + im(rf"F = \frac{{{tx(s.get('nu_m_s'))} \times {tx(s.get('S'))} \times {tx(s.get('D'), 3)} "
                                             rf"\times {tx(s.get('I'))} \times {tx(s.get('W_kn'), 0)}}}{{{tx(s.get('K'))}}} = {tx(s.get('F_base_kn'), 1)}\ \text{{kN}}")
                   + f" : l'effort sismique à la base représente ainsi {fr(100 * s['F_base_kn'] / s['W_kn'], 1)} % du poids sismique du bâtiment.</p>")
    if s.get("Fn"):
        out.append("<h3>Répartition verticale</h3>")
        out.append("<p>Cet effort est réparti sur la hauteur du bâtiment, proportionnellement aux masses et aux hauteurs des niveaux :</p>")
        out.append(EQ(r"F_n = \frac{(F - F_t) \, W_n \, h_n}{\sum W_i \, h_i}"))
        out.append(tableau(["Niveau", ent(im("W_n"), "kN"), ent(im("h_n"), "m"), ent(im("F_n"), "kN")],
                           [[esc(n.get("niveau")), fr(n.get("Wn_kn"), 0), fr(n.get("hn_m")), fr(n.get("Fn_kn"), 1)] for n in s["Fn"]],
                           ["", "n", "n", "n"], largeurs=[34, 22, 22, 22], titre="Répartition verticale de l'effort sismique"))
    for h in s.get("hypotheses") or []:
        out.append(f'<p class="note">{esc(h)}</p>')
    return "".join(out)


# ── dimensionnement par famille ──

def section_poteaux(liste: List[dict], m: dict) -> str:
    out = ["<h3>6.1 Poteaux</h3>",
           "<p>Les poteaux sont justifiés en compression centrée selon l'article B.8.4,1 du BAEL (méthode forfaitaire) :</p>",
           EQ(r"N_u \le N_{u,\lim} = \alpha \left[ \frac{B_r \, f_{c28}}{0{,}9 \, \gamma_b} + \frac{A \, f_e}{\gamma_s} \right]"),
           "<p>où " + im(r"B_r") + " est la section réduite, " + im("A") + " la section d'acier et " + im(r"\alpha")
           + " le coefficient de flambement, fonction de l'élancement " + im(r"\lambda = l_f / i") + " :</p>",
           EQ(r"\alpha = \frac{0{,}85}{1 + 0{,}2 \left( \frac{\lambda}{35} \right)^2} \quad \text{pour} \quad \lambda \le 50"),
           "<p>Nous vérifions en complément leur résistance en flexion composée sous les moments issus du modèle.</p>"]
    if not liste:
        return "".join(out + ["<p>Aucun poteau calculé.</p>"])
    types = grouper(liste, lambda p: (p.get("a_cm"), p.get("b_cm"), (p.get("ferraillage") or {}).get("choix")), "P", ok_poteau)
    lignes = []
    for t in types:
        e = max(t["elements"], key=lambda p: p.get("nu_rapport") or 0)
        lignes.append([t["code"], f"{fr(e.get('a_cm'), 0)} × {fr(e.get('b_cm'), 0)}", str(len(t["elements"])),
                       esc(reperes(t, "P")), esc(niveaux(t)), fr(e.get("nu_kn"), 0), fr(e.get("nu_lim_kn_avec_as_fournie"), 0),
                       fr(e.get("nu_rapport"), 2), esc((e.get("ferraillage") or {}).get("choix")), etat(t["ok"])])
    out.append("<p>Les poteaux de même section et de même ferraillage sont regroupés en types :</p>")
    out.append(tableau(["Type", ent("a × b", "cm"), "Nb", "Repères", "Niveaux", ent(im("N_u") + " max", "kN"),
                        ent(im(r"N_{u,\lim}"), "kN"), "Taux", "Ferraillage", "État"],
                       lignes, ["", "c", "c", "el", "", "n", "n", "n", "", "c"],
                       largeurs=[6, 10, 5, 18, 12, 9, 9, 7, 13, 11], titre="Types de poteaux"))
    p = max(liste, key=lambda x: x.get("nu_rapport") or 0)
    a, b = p.get("a_cm") or 0, p.get("b_cm") or 0
    fer = p.get("ferraillage") or {}
    fc = p.get("flexion_composee") or {}
    i_min = min(a, b) / 100 / math.sqrt(12)
    A = fer.get("as_fournie_cm2") or 0
    out.append(f"<h4>Exemple de calcul : poteau le plus sollicité, {esc(_nom(p, 0, 'P'))}</h4>")
    out.append("<p>Nous détaillons ci-dessous le calcul du poteau le plus chargé de l'ouvrage ; les autres poteaux suivent la même démarche.</p>")
    alpha_tex = (rf"\alpha = \frac{{0{{,}}85}}{{1 + 0{{,}}2 \left( \frac{{{tx(p.get('lambda'))}}}{{35}} \right)^2}}"
                 if (p.get("lambda") or 0) <= 50 else rf"\alpha = 0{{,}}6 \left( \frac{{50}}{{{tx(p.get('lambda'))}}} \right)^2")
    lignes_calc = [
        ("Section", im(rf"B = a \times b = {tx(a, 0)} \times {tx(b, 0)}\ \text{{cm}}"), f"{fr(p.get('B_m2'), 4)} m²"),
        ("Rayon de giration", im(rf"i = \frac{{a}}{{\sqrt{{12}}}} = \frac{{{tx(min(a, b) / 100)}}}{{\sqrt{{12}}}}"), f"{fr(i_min, 4)} m"),
        ("Élancement", im(rf"\lambda = \frac{{l_f}}{{i}} = \frac{{{tx(p.get('lf_m'))}}}{{{tx(i_min, 4)}}}"), fr(p.get("lambda"), 2)),
        ("Coefficient de flambement", im(alpha_tex), fr(p.get("alpha"), 4)),
        ("Section réduite", im(rf"B_r = (a - 2)(b - 2) = {tx(a - 2, 0)} \times {tx(b - 2, 0)}\ \text{{cm}}^2"), f"{fr(p.get('Br_m2'), 4)} m²"),
        ("Acier mis en place", esc(fer.get("choix")), f"{fr(A)} cm²"),
        ("Effort normal limite", im(rf"N_{{u,\lim}} = {tx(p.get('alpha'), 4)} \left[ \frac{{{tx(p.get('Br_m2'), 4)} \times {tx(m['fc28'], 0)}}}{{1{{,}}35}} "
                                    rf"+ \frac{{{tx(A / 1e4, 6)} \times {tx(m['fe'], 0)}}}{{1{{,}}15}} \right] \times 10^3"),
         f"{fr(p.get('nu_lim_kn_avec_as_fournie'), 1)} kN"),
        ("On vérifie que", im(rf"N_u = {tx(p.get('nu_kn'), 1)}\ \text{{kN}} \le N_{{u,\lim}}"), etat((p.get("nu_rapport") or 0) <= 1)),
        ("Section minimale", im(rf"A_{{\min}} = \max\left(4\ \text{{cm}}^2/\text{{m}} \times u \,;\; 0{{,}}2\,\%\, B\right)"),
         f"{fr(max(p.get('as_min_long_cm2') or 0, p.get('as_min_sect_cm2') or 0))} cm²"),
        ("Section maximale", im(r"A_{\max} = 5\,\%\, B"), f"{fr(p.get('as_max_5pct_cm2'))} cm²"),
    ]
    if fc.get("moment_capable_knm") is not None:
        lignes_calc.append(("Flexion composée", im(rf"M = {tx(fc.get('moment_applique_knm'), 1)}\ \text{{kN·m}} \le M_{{Rd}} = {tx(fc.get('moment_capable_knm'), 1)}\ \text{{kN·m}}"),
                            f"taux {fr(fc.get('taux_utilisation_moment'), 2)}" if fc.get("taux_utilisation_moment") is not None else "—"))
    out.append(calcul(lignes_calc))
    return "".join(out)


def section_poutres(liste: List[dict], m: dict) -> str:
    out = ["<h3>6.2 Poutres</h3>",
           "<p>Les poutres sont dimensionnées en flexion simple à l'ELU, avec le diagramme rectangulaire simplifié :</p>",
           EQ(r"\mu = \frac{M_u}{b \, d^2 \, f_{bu}} \;,\qquad \alpha = 1{,}25 \left( 1 - \sqrt{1 - 2\mu} \right) \;,\qquad Z = d \, (1 - 0{,}4\,\alpha) \;,\qquad A_s = \frac{M_u}{Z \, f_{su}}"),
           "<p>Elles sont ensuite vérifiées à l'ELS (" + im("n = 15") + ") et à l'effort tranchant. "
           f"La fissuration étant {FISSURATION.get(m['fissuration'], '')}, la contrainte de l'acier en service est limitée à "
           + im(r"\overline{\sigma}_{st}") + " ; lorsque cette limite gouverne, nous avons augmenté la section d'acier "
           "en conséquence. Les barres retenues tiennent dans la largeur de la poutre, en un ou deux lits.</p>"]
    if not liste:
        return "".join(out + ["<p>Aucune poutre calculée.</p>"])
    types = grouper(liste, lambda p: (p.get("b_cm"), p.get("h_cm"), (p.get("ferraillage") or {}).get("choix")), "Pt", ok_poutre)
    lignes = []
    for t in types:
        e = max(t["elements"], key=lambda p: p.get("as_retenue_cm2") or 0)
        els, tau = e.get("els") or {}, e.get("effort_tranchant") or {}
        lignes.append([t["code"], f"{fr(e.get('b_cm'), 0)} × {fr(e.get('h_cm'), 0)}", str(len(t["elements"])),
                       esc(reperes(t, "Pt")), esc(niveaux(t)),
                       fr(e.get("mu_knm"), 1) if e.get("mu_knm") is not None else "—", fr(e.get("as_retenue_cm2")),
                       esc((e.get("ferraillage") or {}).get("choix")),
                       f"{fr(els.get('sigma_st_mpa'), 0)} / {fr(els.get('sigma_st_lim_mpa'), 0)}",
                       f"{fr(tau.get('tau_u_mpa'), 2)} / {fr(tau.get('tau_u_lim_mpa'), 2)}", etat(t["ok"])])
    out.append("<p>Les poutres de même section et de même ferraillage sont regroupées en types :</p>")
    out.append(tableau(["Type", ent("b × h", "cm"), "Nb", "Repères", "Niveaux", ent(im("M_u"), "kN·m"), ent(im("A_s"), "cm²"),
                        "Ferraillage", ent(im(r"\sigma_{st} / \overline{\sigma}_{st}"), "MPa"), ent(im(r"\tau_u / \overline{\tau}_u"), "MPa"), "État"],
                       lignes, ["", "c", "c", "el", "", "n", "n", "", "n", "n", "c"],
                       largeurs=[5, 9, 4, 14, 11, 8, 7, 11, 10, 11, 10], titre="Types de poutres"))
    p = max(liste, key=lambda x: x.get("mu_knm") or x.get("as_retenue_cm2") or 0)
    els, tau = p.get("els") or {}, p.get("effort_tranchant") or {}
    b, d = (p.get("b_cm") or 0) / 100, p.get("d_m") or 0
    mu = p.get("mu_knm")
    out.append(f"<h4>Exemple de calcul : poutre la plus sollicitée, {esc(_nom(p, 0, 'Pt'))}</h4>")
    out.append(calcul([
        ("Section", im(rf"b \times h = {tx(p.get('b_cm'), 0)} \times {tx(p.get('h_cm'), 0)}\ \text{{cm}} \;,\quad d = {tx(d, 3)}\ \text{{m}}"), ""),
        ("Moment ultime", im(rf"M_u = {tx(mu, 1)}\ \text{{kN·m}}") if mu is not None else im("M_u"), ""),
        ("Moment réduit", im(rf"\mu = \frac{{{tx(mu, 1)} \times 10^{{-3}}}}{{{tx(b)} \times {tx(d, 3)}^2 \times {tx(m['fbu'])}}}"),
         im(rf"{tx(p.get('mu'), 4)} < \mu_{{\lim}} = {tx(p.get('mu_lim'), 3)}")),
        ("Bras de levier", im(r"Z = d \, (1 - 0{,}4\,\alpha)"), f"{fr(p.get('z_m'), 3)} m"),
        ("Acier à l'ELU", im(rf"A_s = \frac{{{tx(mu, 1)} \times 10^{{-3}}}}{{{tx(p.get('z_m'), 3)} \times {tx(m['fsu'], 1)}}}"),
         f"{fr(p.get('as_cm2') or p.get('as_elu_cm2'))} cm²"),
        ("Non-fragilité", im(r"A_{\min} = 0{,}23 \, b \, d \, \frac{f_{t28}}{f_e}"), f"{fr(p.get('as_non_fragilite_cm2'))} cm²"),
        ("Dimensionnement", esc(p.get("dimensionnement") or "ELU"), f"{fr(p.get('as_retenue_cm2'))} cm²"),
        ("Acier mis en place", esc((p.get("ferraillage") or {}).get("choix")), f"{fr((p.get('ferraillage') or {}).get('as_fournie_cm2'))} cm²"),
        ("ELS : axe neutre", im(r"\frac{b \, y^2}{2} - 15 \, A \, (d - y) = 0"), im(rf"y = {tx(els.get('axe_neutre_y_m'), 3)}\ \text{{m}}")),
        ("ELS : béton", im(rf"\sigma_{{bc}} = {tx(els.get('sigma_bc_mpa'))}\ \text{{MPa}} \le 0{{,}}6 \, f_{{c28}} = {tx(m['sigma_bc'], 1)}\ \text{{MPa}}"),
         etat(els.get("sigma_bc_ok", True))),
        ("ELS : acier", im(rf"\sigma_{{st}} = {tx(els.get('sigma_st_mpa'), 1)}\ \text{{MPa}} \le {tx(els.get('sigma_st_lim_mpa'), 1)}\ \text{{MPa}}"),
         etat(els.get("sigma_st_ok", True))),
        ("Effort tranchant", im(rf"\tau_u = \frac{{V_u}}{{b \, d}} = {tx(tau.get('tau_u_mpa'), 3)}\ \text{{MPa}} \le {tx(tau.get('tau_u_lim_mpa'))}\ \text{{MPa}}"),
         etat(tau.get("tau_u_ok", True))),
        ("Armatures transversales", im(r"A_t / s_t"), f"{fr(tau.get('at_cm2_par_m'))} cm²/m"),
    ]))
    return "".join(out)


def section_semelles(liste: List[dict], m: dict) -> str:
    out = ["<h3>6.3 Semelles</h3>",
           "<p>Les fondations sont des semelles isolées rigides, calculées par la méthode des bielles. "
           "Nous vérifions la contrainte transmise au sol et la résistance au poinçonnement sous le poteau :</p>",
           EQ(r"A \, B \ge \frac{N_s}{\overline{\sigma}_{sol}} \;,\qquad h \ge \frac{A - a}{4} \;,\qquad A_s = \frac{N_u \, (A - a)}{8 \, d \, f_{su}}"),
           EQ(r"N_u \le 0{,}045 \, u_c \, h \, \frac{f_{c28}}{\gamma_b}")]
    if not liste:
        return "".join(out + ["<p>Aucune semelle calculée.</p>"])
    types = grouper(liste, lambda s: (s.get("A_m"), s.get("B_m"), s.get("H_m"), s.get("acier_x"), s.get("acier_y")), "S", ok_semelle)
    lignes = []
    for t in types:
        e = max(t["elements"], key=lambda s: s.get("nu_kn_utilise") or 0)
        lignes.append([t["code"], str(len(t["elements"])), esc(reperes(t, "S")), fr(e.get("A_m")), fr(e.get("B_m")), fr(e.get("H_m")),
                       fr(e.get("sigma_max_bar"), 2), esc(e.get("acier_x")), esc(e.get("acier_y")), etat(t["ok"])])
    out.append(tableau(["Type", "Nb", "Repères", ent(im("A"), "m"), ent(im("B"), "m"), ent(im("H"), "m"), ent(im(r"\sigma_{\max}"), "bar"),
                        "Nappe X", "Nappe Y", "État"], lignes, ["", "c", "el", "n", "n", "n", "n", "", "", "c"],
                       largeurs=[6, 5, 23, 8, 8, 8, 9, 11, 11, 11], titre="Types de semelles"))
    s = max(liste, key=lambda x: x.get("nu_kn_utilise") or 0)
    po = s.get("poinconnement") or {}
    out.append(f"<h4>Exemple de calcul : semelle la plus chargée, {esc(_nom(s, 0, 'S'))}</h4>")
    out.append(calcul([
        ("Dimensions", im(rf"A \times B \times H = {tx(s.get('A_m'))} \times {tx(s.get('B_m'))} \times {tx(s.get('H_m'))}\ \text{{m}} \;,\quad d = {tx(s.get('d_m'))}\ \text{{m}}"), ""),
        ("Contrainte du sol", im(rf"\sigma_{{\max}} = {tx(s.get('sigma_max_bar'), 3)}\ \text{{bar}} \le \overline{{\sigma}}_{{sol}} = {tx(s.get('sigma_sol_bar'))}\ \text{{bar}}"),
         etat((s.get("sigma_max_bar") or 0) <= (s.get("sigma_sol_bar") or 1e9) * 1.0001)),
        ("Effort ultime", im(rf"N_u = {tx(s.get('nu_kn_utilise'), 1)}\ \text{{kN}}"), ""),
        ("Nappe X", im(r"A_{sx} = \frac{N_u \, (A - a)}{8 \, d \, f_{su}}"), f"{fr(s.get('asx_cm2'))} cm² — {esc(s.get('acier_x'))}"),
        ("Nappe Y", im(r"A_{sy} = \frac{N_u \, (B - b)}{8 \, d \, f_{su}}"), f"{fr(s.get('asy_cm2'))} cm² — {esc(s.get('acier_y'))}"),
        ("Poinçonnement", im(rf"N_u = {tx(po.get('nu_utilise_kn'), 1)} \le 0{{,}}045 \, u_c \, h \, \frac{{f_{{c28}}}}{{\gamma_b}} = {tx(po.get('nu_poinc_kn'), 1)}\ \text{{kN}}"),
         etat(po.get("ok", True))),
        ("Poids propre", im(r"P = A \, B \, H \times 2{,}5"), f"{fr(s.get('poids_T'))} t"),
    ]))
    for a in s.get("avertissements") or []:
        out.append(f'<p class="note">{esc(a)}</p>')
    return "".join(out)


def section_voiles(liste: List[dict], m: dict) -> str:
    out = ["<h3>6.4 Voiles</h3>",
           "<p>Les voiles sont vérifiés en contraintes normales dans leur plan. Lorsque la section est partiellement tendue, "
           "les armatures de rive reprennent l'effort de traction ; ailleurs, nous retenons les sections minimales réparties :</p>",
           EQ(r"\sigma = \frac{N}{e \, L} \pm \frac{6 \, M}{e \, L^2} \;,\qquad \sigma_{\max} \le 0{,}6 \, f_{c28} \;,\qquad \tau_u = \frac{V}{e \, L}")]
    if not liste:
        return "".join(out + ["<p>Aucun voile calculé.</p>"])
    types = grouper(liste, lambda v: (v.get("longueur_m"), v.get("ep_cm"), round(v.get("as_rive_cm2") or 0, 1)), "V", ok_voile)
    lignes = []
    for t in types:
        e = max(t["elements"], key=lambda v: v.get("sigma_max_mpa") or 0)
        lignes.append([t["code"], f"{fr(e.get('longueur_m'))} × {fr(e.get('ep_cm'), 0)}", str(len(t["elements"])),
                       esc(reperes(t, "V")), esc(niveaux(t)),
                       fr(e.get("sigma_max_mpa")), fr(e.get("sigma_min_mpa")), fr(e.get("tau_u_mpa"), 3), fr(e.get("as_rive_cm2")),
                       f"{fr(e.get('as_vert_par_m_cm2'))} / {fr(e.get('as_horiz_par_m_cm2'))}", etat(t["ok"])])
    out.append(tableau(["Type", ent("L × e", "m × cm"), "Nb", "Repères", "Niveaux", ent(im(r"\sigma_{\max}"), "MPa"),
                        ent(im(r"\sigma_{\min}"), "MPa"), ent(im(r"\tau_u"), "MPa"), ent("As rive", "cm²"), ent("As V / H", "cm²/m"), "État"],
                       lignes, ["", "c", "c", "el", "", "n", "n", "n", "n", "n", "c"],
                       largeurs=[6, 10, 4, 9, 11, 9, 9, 8, 8, 14, 12], titre="Types de voiles"))
    v = max(liste, key=lambda x: x.get("sigma_max_mpa") or 0)
    e_m, L = (v.get("ep_cm") or 0) / 100, v.get("longueur_m") or 0
    out.append(f"<h4>Exemple de calcul : voile le plus sollicité, {esc(_nom(v, 0, 'V'))}</h4>")
    out.append(calcul([
        ("Section", im(rf"L \times e = {tx(L)} \times {tx(e_m)}\ \text{{m}}"), f"{fr(L * e_m, 3)} m²"),
        ("Efforts", im(rf"N = {tx(v.get('n_kn'), 1)}\ \text{{kN}} \;,\; M = {tx(v.get('m_knm'), 1)}\ \text{{kN·m}} \;,\; V = {tx(v.get('v_kn'), 1)}\ \text{{kN}}"), ""),
        ("Contrainte maximale", im(r"\sigma_{\max} = \frac{N}{e \, L} + \frac{6 \, M}{e \, L^2}"), f"{fr(v.get('sigma_max_mpa'), 2)} MPa"),
        ("Contrainte minimale", im(r"\sigma_{\min} = \frac{N}{e \, L} - \frac{6 \, M}{e \, L^2}"), f"{fr(v.get('sigma_min_mpa'), 2)} MPa"),
        ("On vérifie que", im(rf"\sigma_{{\max}} \le 0{{,}}6 \, f_{{c28}} = {tx(0.6 * m['fc28'], 1)}\ \text{{MPa}}"), etat(v.get("compression_ok", True))),
        ("Cisaillement", im(rf"\tau_u = {tx(v.get('tau_u_mpa'), 3)}\ \text{{MPa}} \le {tx(v.get('tau_u_lim_mpa'))}\ \text{{MPa}}"), etat(v.get("tau_ok", True))),
        ("Section", esc(v.get("mode")), f"As rive = {fr(v.get('as_rive_cm2'))} cm²"),
    ]))
    return "".join(out)


def _fleche(e: dict) -> Tuple[str, str, str]:
    """Ligne d'exemple : conditions de dispense du calcul de flèche (valeur / limite)."""
    f = e.get("fleche") or {}
    cond = " ; ".join(f"{c['nom']} : {fr(c['valeur'], 4)} / {fr(c['limite'], 4)}" for c in f.get("conditions") or [])
    return (f"Flèche ({esc(f.get('article') or '—')})", esc(cond or "—"),
            "Dispensée" if f.get("dispense") else "<b>À calculer</b>")


def _choix(r: Optional[dict]) -> str:
    f = (r or {}).get("ferraillage") or {}
    return esc(f.get("choix") or "—")


def section_dalles(dalles: List[dict], balcons: List[dict], m: dict) -> str:
    out = ["<h3>6.5 Dalles et balcons</h3>"]
    if not dalles and not balcons:
        return "".join(out + ["<p>Aucune dalle ni aucun balcon calculé.</p>"])
    if dalles:
        out.append("<p>Les dalles pleines sont calculées comme des panneaux rectangulaires uniformément chargés, appuyés sur "
                   "leur contour (BAEL A.8.2). Avec " + im(r"\rho = l_x / l_y") + ", un panneau tel que " + im(r"\rho < 0{,}4")
                   + " ne porte que dans le sens " + im("l_x") + " ; sinon, les moments isostatiques sont (Annexe E3) :</p>")
        out.append(EQ(r"M_{0x} = \mu_x \, p_u \, l_x^2 \;,\qquad M_{0y} = \mu_y \, M_{0x} \;,\qquad "
                      r"\mu_x = \frac{1}{8 \left( 1 + 2{,}4 \, \rho^3 \right)} \;,\qquad \mu_y = \rho^3 \left( 1{,}9 - 0{,}9 \, \rho \right) \ge 0{,}25"))
        out.append("<p>Les moments en travée et sur appuis tiennent compte de la continuité du panneau, avec "
                   + im(r"M_t + \frac{M_w + M_e}{2} \ge 1{,}25 \, M_0") + " (A.8.2,32). Les dalles sont sans armatures d'effort "
                   "tranchant lorsque " + im(r"\tau_u \le 0{,}05 \, f_{c28}") + " (A.5.2,2). Le calcul de la flèche est dispensé si "
                   + im(r"h / l_x \ge M_{tx} / (20 \, M_{0x})") + " et " + im(r"A_x / (b \, d) \le 2 / f_e")
                   + " (B.7.5) ; sinon, la dalle est signalée et sa flèche doit être calculée.</p>")
        lignes = []
        for i, d in enumerate(dalles):
            r = d.get("resultats") or {}
            lignes.append([esc(d.get("nom") or f"D{i + 1}"), esc(d.get("niveau") or "—"),
                           f"{fr(d.get('lx_m'))} × {fr(d.get('ly_m'))}", fr(d.get("h_cm"), 0), fr(d.get("rho"), 2),
                           fr((d.get("charges") or {}).get("pu_kn_m2"), 2), fr(d.get("m0x_knm"), 2),
                           _choix(r.get("x_travee")), _choix(r.get("y_travee")), _choix(r.get("appuis")), etat(bool(d.get("verifie")))])
        out.append(tableau(["Repère", "Niv.", ent(im(r"l_x \times l_y"), "m"), ent("h", "cm"), im(r"\rho"), ent(im("p_u"), "kN/m²"),
                            ent(im("M_{0x}"), "kN·m/m"), "Travée x", "Travée y", "Chapeaux", "État"],
                           lignes, ["", "", "c", "n", "n", "n", "n", "", "", "", "c"],
                           largeurs=[8, 6, 11, 5, 5, 7, 8, 12, 12, 12, 14], titre="Dalles pleines"))
        d = max(dalles, key=lambda x: x.get("m0x_knm") or 0)
        r = d.get("resultats") or {}
        x = r.get("x_travee") or {}
        c = d.get("charges") or {}
        out.append(f"<h4>Exemple de calcul : dalle la plus sollicitée, {esc(_nom(d, 0, 'D'))}</h4>")
        out.append(calcul([
            ("Charges", im(rf"p_u = 1{{,}}35 \times {tx(c.get('g_kn_m2'))} + 1{{,}}5 \times {tx(c.get('q_kn_m2'))}"), f"{fr(c.get('pu_kn_m2'), 2)} kN/m²"),
            ("Élancement", im(rf"\rho = \frac{{{tx(d.get('lx_m'))}}}{{{tx(d.get('ly_m'))}}}"), fr(d.get("rho"), 3)),
            ("Moment isostatique", im(rf"M_{{0x}} = {tx(d.get('mu_x'), 4)} \times {tx(c.get('pu_kn_m2'), 3)} \times {tx(d.get('lx_m'))}^2"), f"{fr(d.get('m0x_knm'), 2)} kN·m/m"),
            ("Moment en travée", im(rf"M_{{tx}} = {tx((d.get('coefficients') or {}).get('travee'))} \, M_{{0x}}"), f"{fr(x.get('m_elu_knm'), 2)} kN·m/m"),
            ("Moment réduit", im(rf"\mu = \frac{{M_{{tx}}}}{{b \, d^2 \, f_{{bu}}}} \;,\; d = {tx(x.get('d_m'), 3)}\ \text{{m}}"), fr(x.get("mu"), 4)),
            ("Acier à l'ELU", im(r"A_s = \frac{M_{tx}}{Z \, f_{su}}"), f"{fr(x.get('as_elu_cm2_m'), 2)} cm²/m"),
            ("Acier minimal", im(r"A_{\min} = \max \left( \rho_0 \, \frac{3 - \rho}{2} \, b \, h \;;\; 0{,}23 \, b \, d \, \frac{f_{t28}}{f_e} \right)"), f"{fr(x.get('as_min_cm2_m'), 2)} cm²/m"),
            ("Acier mis en place", _choix(x), f"{fr((x.get('ferraillage') or {}).get('as_fournie_cm2_m'), 2)} cm²/m"),
            _fleche(d),
        ]))
    if balcons:
        out.append("<p>Les balcons sont calculés comme des consoles encastrées, par bande de 1 m. Les aciers principaux sont "
                   "placés en <b>nappe supérieure</b>, zone tendue de la console, et prolongés dans la dalle intérieure. "
                   "Le moment d'encastrement tient compte du garde-corps " + im("P") + " au bord libre et de la poussée "
                   + im("H") + " sur la main courante, à la hauteur " + im("h_g") + " :</p>")
        out.append(EQ(r"M_u = 1{,}35 \left( \frac{g \, l^2}{2} + P \, l \right) + 1{,}5 \left( \frac{q \, l^2}{2} + H \, h_g \right) \;,\qquad "
                      r"V_u = 1{,}35 \left( g \, l + P \right) + 1{,}5 \, q \, l"))
        lignes = []
        for i, b in enumerate(balcons):
            lignes.append([esc(b.get("nom") or f"B{i + 1}"), esc(b.get("niveau") or "—"), fr(b.get("longueur_m")), fr(b.get("h_cm"), 0),
                           fr(b.get("mu_knm"), 2), fr(b.get("vu_kn"), 2), _choix(b.get("nappe_superieure")), _choix(b.get("repartition")),
                           fr(b.get("prolongement_chapeaux_m")), etat(bool(b.get("verifie")))])
        out.append(tableau(["Repère", "Niveau", ent("l", "m"), ent("h", "cm"), ent(im("M_u"), "kN·m/m"), ent(im("V_u"), "kN/m"),
                            "Nappe supérieure", "Répartition", ent("Ancrage", "m"), "État"],
                           lignes, ["", "", "n", "n", "n", "n", "", "", "n", "c"],
                           largeurs=[8, 8, 6, 6, 10, 9, 15, 14, 11, 13], titre="Balcons en porte-à-faux"))
        b = max(balcons, key=lambda x: x.get("mu_knm") or 0)
        c = b.get("charges") or {}
        s = b.get("nappe_superieure") or {}
        els = s.get("els") or {}
        l = b.get("longueur_m")
        out.append(f"<h4>Exemple de calcul : balcon le plus sollicité, {esc(_nom(b, 0, 'B'))}</h4>")
        out.append(calcul([
            ("Charges", im(rf"g = {tx(c.get('g_kn_m2'))}\ \text{{kN/m²}} \;,\; q = {tx(c.get('q_kn_m2'))}\ \text{{kN/m²}} \;,\; P = {tx(c.get('garde_corps_kn_m'))}\ \text{{kN/m}}"), ""),
            ("Moment d'encastrement", im(rf"M_u = 1{{,}}35 \left( \frac{{{tx(c.get('g_kn_m2'))} \times {tx(l)}^2}}{{2}} + {tx(c.get('garde_corps_kn_m'))} \times {tx(l)} \right) + 1{{,}}5 \left( \frac{{{tx(c.get('q_kn_m2'))} \times {tx(l)}^2}}{{2}} + {tx(c.get('poussee_kn_m'))} \times {tx(c.get('hauteur_main_courante_m'))} \right)"),
             f"{fr(b.get('mu_knm'), 2)} kN·m/m"),
            ("Moment réduit", im(rf"\mu = \frac{{M_u}}{{b \, d^2 \, f_{{bu}}}} \;,\; d = {tx(b.get('d_m'), 3)}\ \text{{m}}"), fr(s.get("mu"), 4)),
            ("Acier à l'ELU", im(r"A_s = \frac{M_u}{Z \, f_{su}}"), f"{fr(s.get('as_elu_cm2_m'), 2)} cm²/m"),
            ("ELS : acier", im(rf"\sigma_{{st}} = {tx(els.get('sigma_st_mpa'), 1)}\ \text{{MPa}} \le {tx(els.get('sigma_st_lim_mpa'), 1)}\ \text{{MPa}}"),
             etat(bool(els.get("sigma_st_ok", True)))),
            ("Acier mis en place (haut)", _choix(s), f"{fr((s.get('ferraillage') or {}).get('as_fournie_cm2_m'), 2)} cm²/m"),
            ("Ancrage des chapeaux", im(rf"\max \left( l \;;\; l_s \right) = \max \left( {tx(l)} \;;\; {tx(b.get('ls_m'))} \right)"),
             f"{fr(b.get('prolongement_chapeaux_m'))} m"),
            ("Effort tranchant", im(rf"\tau_u = {tx((b.get('cisaillement') or {}).get('tau_u_mpa'), 3)}\ \text{{MPa}} \le 0{{,}}05 \, f_{{c28}}"),
             etat(bool((b.get("cisaillement") or {}).get("ok", True)))),
            _fleche(b),
        ]))
        out.append("<p class='note'>" + " ".join(esc(x) for x in (b.get("dispositions") or [])) + "</p>")
    return "".join(out)


def section_planchers(planchers: List[dict], m: dict) -> str:
    out = ["<h3>6.6 Planchers à corps creux</h3>"]
    if not planchers:
        return "".join(out + ["<p>Aucun plancher à corps creux calculé.</p>"])
    out.append("<p>Les planchers à corps creux sont constitués de hourdis posés sur des poutrelles en T, coiffés d'une dalle "
               "de compression armée d'un treillis soudé. Chaque poutrelle est calculée comme une poutre continue de largeur "
               "de table " + im(r"b = b_0 + 2 \, b_1") + ", avec " + im(r"b_1 \le \min \left( l_0 / 2 \;;\; l / 10 \right)")
               + " (A.4.1,3). Les moments sont obtenus par la méthode forfaitaire lorsque ses conditions sont remplies "
               "(B.6.2,21), sinon par la méthode de Caquot (B.6.2,22) :</p>")
    out.append(EQ(r"M_t + \frac{M_w + M_e}{2} \ge \max \left( 1{,}05 \;;\; 1 + 0{,}3 \, \alpha \right) M_0 \;,\qquad "
                  r"M_a = \frac{p_w \, l_w'^3 + p_e \, l_e'^3}{8{,}5 \left( l_w' + l_e' \right)}"))
    out.append("<p>La flèche est dispensée de calcul si " + im(r"h / l \ge 1 / 22{,}5") + ", " + im(r"h / l \ge M_t / (15 \, M_0)")
               + " et " + im(r"A / (b_0 \, d) \le 3{,}6 / f_e") + " (B.6.8,424) ; sinon elle est calculée par la méthode "
               "de l'inertie fissurée (B.6.5,2) :</p>")
    out.append(EQ(r"\Delta f_t = f_{gv} - f_{ji} + f_{pi} - f_{gi} \le f_{adm} \;,\qquad f = \frac{M \, l^2}{10 \, E \, I_f}"))
    lignes = []
    for i, p in enumerate(planchers):
        t = p.get("travees") or []
        calc = [(x.get("fleche") or {}).get("calcul") for x in t if (x.get("fleche") or {}).get("calcul")]
        pire = max(calc, key=lambda c: (c.get("delta_ft_mm") or 0) / (c.get("f_adm_mm") or 1), default=None)
        fl = [f"{fr(pire.get('delta_ft_mm'), 1)} / {fr(pire.get('f_adm_mm'), 1)} mm" if pire else "dispensée"]
        lignes.append([esc(p.get("nom") or f"PL{i + 1}"), esc(p.get("niveau") or "—"), esc(p.get("designation") or "—"),
                       " ; ".join(fr(l) for l in p.get("travees_m") or []), esc(p.get("methode") or "—"),
                       " / ".join(esc((x.get("ferraillage") or {}).get("choix") or "—") for x in t),
                       esc((p.get("dalle_compression") or {}).get("choix") or "—"), " ; ".join(fl), etat(bool(p.get("verifie")))])
    out.append(tableau(["Repère", "Niv.", "Type", ent("Portées", "m"), "Méthode", "Aciers bas", "Dalle de compression",
                        ent("Flèche Δft / adm.", "pire travée"), "État"], lignes, ["", "", "c", "", "", "", "", "c", "c"],
                       largeurs=[7, 11, 7, 12, 11, 12, 14, 13, 13], titre="Planchers à corps creux"))
    p = max(planchers, key=lambda x: max((t.get("mt_knm") or 0) for t in x.get("travees") or [{}]))
    t = max(p.get("travees") or [{}], key=lambda x: x.get("mt_knm") or 0)
    c = p.get("charges") or {}
    elu = t.get("elu") or {}
    out.append(f"<h4>Exemple de calcul : travée la plus sollicitée du plancher {esc(p.get('nom') or 'PL1')}</h4>")
    lignes_calc = [
        ("Charges par poutrelle", im(rf"p_u = 1{{,}}35 \times {tx(c.get('g_kn_m'), 3)} + 1{{,}}5 \times {tx(c.get('q_kn_m'), 3)}"),
         f"{fr(c.get('pu_kn_m'), 2)} kN/m"),
        ("Moment isostatique", im(rf"M_0 = \frac{{{tx(c.get('pu_kn_m'), 3)} \times {tx(t.get('portee_m'))}^2}}{{8}}"), f"{fr(t.get('m0_knm'), 2)} kN·m"),
        ("Moment en travée", esc(f"méthode {p.get('methode')}"), f"{fr(t.get('mt_knm'), 2)} kN·m"),
        ("Table de compression", im(rf"M_{{tu}} = b \, h_0 \, f_{{bu}} \left( d - h_0 / 2 \right) \;,\; b = {tx(t.get('b_cm'), 0)}\ \text{{cm}}"),
         f"{fr(elu.get('mtu_knm'), 2)} kN·m"),
        ("Moment réduit", im(rf"\mu = \frac{{M_t}}{{b \, d^2 \, f_{{bu}}}} \;,\; d = {tx(p.get('d_m'), 3)}\ \text{{m}}")
         + "<br>" + esc(elu.get("cas") or ""), fr(elu.get("mu"), 4)),
        ("Acier à l'ELU", im(r"A_s = \frac{M_t}{Z \, f_{su}}"), f"{fr(elu.get('as_elu_cm2'), 2)} cm²"),
        ("Aciers en travée", esc((t.get("ferraillage") or {}).get("choix") or "—"), f"{fr((t.get('ferraillage') or {}).get('as_fournie_cm2'), 2)} cm²"),
        ("Effort tranchant", im(rf"\tau_u = {tx((t.get('cisaillement') or {}).get('tau_u_mpa'), 3)}\ \text{{MPa}} \le {tx((t.get('cisaillement') or {}).get('tau_lim_mpa'))}\ \text{{MPa}}"),
         esc((t.get("etriers") or {}).get("choix") or "—")),
    ]
    f = t.get("fleche") or {}
    if f.get("calcul"):
        cf = f["calcul"]
        lignes_calc.append(("Flèche (B.6.5,2)", im(rf"\Delta f_t = {tx(cf.get('fgv_mm'))} - {tx(cf.get('fji_mm'))} + {tx(cf.get('fpi_mm'))} - {tx(cf.get('fgi_mm'))}"),
                            f"{fr(cf.get('delta_ft_mm'), 2)} / {fr(cf.get('f_adm_mm'), 1)} mm"))
    else:
        lignes_calc.append(("Flèche", "conditions de B.6.8,424 satisfaites", "dispensée"))
    ts = p.get("dalle_compression") or {}
    lignes_calc.append(("Dalle de compression", im(rf"A_\perp = \frac{{4 \, L}}{{f_e}} = {tx(ts.get('a_perp_cm2_m'))}\ \text{{cm²/m}}"),
                        esc(ts.get("choix") or "—")))
    out.append(calcul(lignes_calc))
    return "".join(out)


def quantites(inp: dict) -> str:
    out = [h2(7, "s7", "Quantités de béton et d'acier")]
    lot = inp.get("lot")
    if not lot:
        out.append("<p>Les quantités sont établies à partir du calcul de tout le modèle (écran « Projet Robot »). "
                   "Elles ne sont pas disponibles pour les éléments calculés un par un.</p>")
        return "".join(out)
    vol = {}
    for fam, f in (("poteaux", lambda e, r: (e.get("a_cm") or 0) * (e.get("b_cm") or 0) / 1e4 * (e.get("hauteur_m") or 3.0)),
                   ("poutres", lambda e, r: (e.get("b_cm") or 0) * (e.get("h_cm") or 0) / 1e4 * (e.get("portee_m") or 0)),
                   ("semelles", lambda e, r: (r.get("A_m") or 0) * (r.get("B_m") or 0) * (r.get("H_m") or 0)),
                   ("voiles", lambda e, r: (e.get("longueur_m") or 0) * (e.get("ep_cm") or 0) / 100 * (e.get("hauteur_m") or 3.0))):
        vol[fam] = sum(f(l.get("entree") or {}, l.get("resultat") or {}) for l in lot.get(fam) or [] if l.get("resultat"))
    try:
        from plans_ferraillage import nomenclature, poids_ml
        nomen = nomenclature(lot)
        acier = {fam: sum(x["poids_kg"] for x in nomen["lignes"] if x["famille"] == fam) for fam in vol}
    except Exception:   # quantités d'acier indisponibles : le béton reste utile
        nomen, acier = None, {}
    noms = {"poteaux": "Poteaux", "poutres": "Poutres", "semelles": "Semelles", "voiles": "Voiles"}
    lignes = []
    for fam, v in vol.items():
        if not v:
            continue
        kg = acier.get(fam)
        lignes.append([noms[fam], fr(v, 2), fr(kg, 0) if kg is not None else "—", fr(kg / v, 0) if kg and v else "—"])
    tv, ta = sum(vol.values()), sum(acier.values()) if acier else None
    lignes.append(["<b>Total</b>", f"<b>{fr(tv, 2)}</b>", f"<b>{fr(ta, 0)}</b>" if ta else "—", f"<b>{fr(ta / tv, 0)}</b>" if ta and tv else "—"])
    out.append("<p>Le tableau ci-dessous récapitule les quantités de béton et d'acier des éléments étudiés. Elles sont "
               "données à titre indicatif pour l'estimation et ne remplacent pas le métré des plans d'exécution.</p>")
    out.append(tableau(["Famille", ent("Béton", "m³"), ent("Acier", "kg"), ent("Ratio", "kg/m³")], lignes, ["", "n", "n", "n"],
                       largeurs=[37, 21, 21, 21], titre="Quantités de béton et d'acier par famille"))
    if nomen:
        out.append(tableau(["Diamètre", ent("Masse linéique", "kg/m"), ent("Poids", "kg")],
                           [[f"HA{d}", fr(poids_ml(d), 3), fr(kg, 1)] for d, kg in nomen["par_diametre_kg"].items()],
                           ["", "n", "n"], largeurs=[37, 31, 32], titre="Acier par diamètre"))
    out.append('<p class="note">Béton : volumes géométriques des éléments calculés (hors dalles, longrines et escaliers). '
               "Acier : longueurs façonnées des éléments vérifiés, recouvrements et crochets compris (voir la nomenclature des plans).</p>")
    return "".join(out)


def conclusion(inp: dict, bur: dict, date: str) -> str:
    reserves = []
    for fam, verif, nom in (("poteaux", ok_poteau, "Poteau"), ("poutres", ok_poutre, "Poutre"),
                            ("semelles_isolees", ok_semelle, "Semelle"), ("voiles", ok_voile, "Voile"),
                            ("dalles", lambda d: bool(d.get("verifie")), "Dalle"), ("balcons", lambda b: bool(b.get("verifie")), "Balcon"),
                            ("planchers", lambda p: bool(p.get("verifie")), "Plancher")):
        for i, e in enumerate(inp.get(fam) or []):
            if not verif(e):
                reserves.append(f"{nom} {_nom(e, i, nom[0])}")
    lignes_audit, alertes = 0, []
    for fam, nom in (("poteaux", "Poteau"), ("poutres", "Poutre"), ("semelles_isolees", "Semelle"), ("voiles", "Voile"),
                     ("dalles", "Dalle"), ("balcons", "Balcon"), ("planchers", "Plancher")):
        for i, e in enumerate(inp.get(fam) or []):
            for a in e.get("audit") or []:
                lignes_audit += 1
                if a.get("statut") != "OK":
                    alertes.append(f"{nom} {_nom(e, i, nom[0])} : {a.get('ligne')} (écart {a.get('ecart')})")
    out = ['<div class="conclusion">', h2(8, "s8", "Conclusion, réserves et visas")]
    if alertes:
        out.append('<div class="reserve"><b>ALERTE ECART ARITHMETIQUE.</b> Le recalcul indépendant ne retrouve pas les '
                   f"valeurs suivantes : {esc(' ; '.join(alertes))}. Ces résultats ne doivent pas être utilisés avant correction.</div>")
    if lignes_audit:
        out.append(f"<p>Contrôle arithmétique : {lignes_audit} lignes de calcul ont été recalculées indépendamment ; "
                   + ("toutes sont conformes.</p>" if not alertes else f"{len(alertes)} présentent un écart (voir ci-dessus).</p>"))
    if reserves:
        out.append('<div class="reserve"><b>Réserves.</b> Les éléments suivants ne sont pas vérifiés ; ils devront être '
                   f"redimensionnés avant l'établissement des plans d'exécution : {esc(liste_noms(reserves, 20))}.</div>")
        out.append("<p>Sous réserve de la reprise de ces éléments, les autres éléments étudiés satisfont aux vérifications "
                   "présentées dans cette note.</p>")
    else:
        out.append("<p>À l'issue des vérifications présentées dans cette note, l'ensemble des éléments étudiés satisfait aux "
                   "états limites ultimes et de service, selon les hypothèses du chapitre 3 et les règlements du chapitre 2.</p>")
    out.append("<p>Les plans d'exécution reprendront les dispositions constructives du BAEL 91 révisé 99 et du RPS 2000 "
               "version 2011, notamment l'espacement réduit des cadres dans les zones critiques des poteaux et des poutres.</p>")
    cachet = f'<img src="data:image/png;base64,{esc(bur["cachet_base64"])}" alt="">' if bur.get("cachet_base64") else ""
    out.append(f"""<table class="signatures"><tr>
  <td><b>Établi par</b><br>{esc(bur.get('ingenieur') or '')}<br>{esc(bur.get('nom') or '')}<br>Le {date}{cachet}</td>
  <td><b>Vérifié par</b></td>
  <td><b>Visa du bureau de contrôle</b><br>{esc(inp.get('controle') or '')}</td>
</tr></table>""")
    out.append("</div>")
    return "".join(out)


def construire(inp: dict, bur: dict) -> str:
    global EQ, TAB
    EQ = Equations()
    TAB = Tableaux()
    date = datetime.date.today().strftime("%d/%m/%Y")
    m = materiaux(inp)
    titre = inp.get("projet") or "Projet"
    css = polices_css() + CSS
    for cle, valeur in (("%(entete_g)s", bur.get("nom") or "Bureau d'études structure"),
                        ("%(entete_d)s", f"{titre} — Note de calcul"),
                        ("%(pied_g)s", f"Indice {inp.get('indice') or 'A'} — {date}")):
        css = css.replace(cle, _css_chaine(valeur))
    corps = [
        page_de_garde(inp, bur, date), sommaire(), presentation(inp), reglements(inp), hypotheses(inp, m),
        modelisation(inp), sismique(inp),
        h2(6, "s6", "Dimensionnement des éléments"),
        section_poteaux(inp.get("poteaux") or [], m), section_poutres(inp.get("poutres") or [], m),
        section_semelles((inp.get("semelles_isolees") or []) + (inp.get("semelles_filantes") or []), m),
        section_voiles(inp.get("voiles") or [], m),
        section_dalles(inp.get("dalles") or [], inp.get("balcons") or [], m),
        section_planchers(inp.get("planchers") or [], m),
        quantites(inp), conclusion(inp, bur, date),
    ]
    return (f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Note de calcul — {esc(titre)}</title>'
            f'<style>{css}</style></head><body><div class="ecran">{"".join(corps)}</div></body></html>')
