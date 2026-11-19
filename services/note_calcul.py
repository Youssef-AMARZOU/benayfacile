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
    """Latin Modern embarquée (licence GUST, voir polices/GUST-FONT-LICENSE.txt) : la note
    garde son rendu LaTeX partout, y compris enregistrée ou imprimée en PDF."""
    faces = []
    for famille, fichier, graisse, style in (
            ("Latin Modern Roman", "lmroman10-regular.woff2", "normal", "normal"),
            ("Latin Modern Roman", "lmroman10-bold.woff2", "bold", "normal"),
            ("Latin Modern Roman", "lmroman10-italic.woff2", "normal", "italic"),
            ("Latin Modern Math", "latinmodern-math.woff2", "normal", "normal")):
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

def tableau(entetes: List[str], lignes: List[List[str]], classes: Optional[List[str]] = None, cls: str = "",
            largeurs: Optional[List[int]] = None) -> str:
    """largeurs : colonnes en % (mise en page fixe, comme tabularx) ; sinon largeur automatique."""
    classes = classes or [""] * len(entetes)
    cols = ("<colgroup>" + "".join(f'<col style="width:{w}%">' for w in largeurs) + "</colgroup>") if largeurs else ""
    if largeurs:
        cls = (cls + " fixe").strip()
    th = "".join(f'<th class="{c}">{e}</th>' for e, c in zip(entetes, classes))
    # « 7 HA10 » ne se coupe jamais entre le nombre et le diamètre
    corps = "".join("<tr>" + "".join(f'<td class="{c}">{str(v).replace(" HA", chr(160) + "HA")}</td>' for v, c in zip(l, classes))
                    + "</tr>" for l in lignes)
    return f'<table class="{cls}">{cols}<thead><tr>{th}</tr></thead><tbody>{corps}</tbody></table>'


def kv(lignes: List[Tuple[str, str]], cls: str = "kv") -> str:
    return f'<table class="{cls}">' + "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in lignes) + "</table>"


def calcul(lignes: List[Tuple[str, str, str]]) -> str:
    """Exemple de calcul : (désignation, formule avec valeurs, résultat)."""
    return '<table class="calcul"><tbody>' + "".join(
        f"<tr><td class='des'>{d}</td><td class='form'>{f}</td><td class='res'>{r}</td></tr>" for d, f, r in lignes) + "</tbody></table>"


CSS = r"""
@page { size: A4; margin: 24mm 20mm 22mm 20mm;
  @top-left { content: %(entete_g)s; font: italic 9pt "Latin Modern Roman", serif; vertical-align: bottom; padding-bottom: 2.5mm; border-bottom: .4pt solid #000; }
  @top-right { content: %(entete_d)s; font: italic 9pt "Latin Modern Roman", serif; vertical-align: bottom; padding-bottom: 2.5mm; border-bottom: .4pt solid #000; }
  @bottom-left { content: %(pied_g)s; font: 9pt "Latin Modern Roman", serif; vertical-align: top; padding-top: 3mm; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 9pt "Latin Modern Roman", serif; vertical-align: top; padding-top: 3mm; }
}
@page :first { margin: 16mm;
  @top-left { content: none; border: none; } @top-right { content: none; border: none; }
  @bottom-left { content: none; } @bottom-right { content: none; } }
* { box-sizing: border-box; }
html { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font: 10.5pt/1.38 "Latin Modern Roman", "Latin Modern Math", "CMU Serif", "Cambria", "Times New Roman", serif;
  color: #000; font-kerning: normal; font-variant-ligatures: common-ligatures; }
.ecran { max-width: 170mm; margin: 0 auto; padding: 12mm 0; }
@media print { .ecran { max-width: none; padding: 0; } }
p { margin: 0 0 6pt; text-align: justify; hyphens: auto; }
p + p { text-indent: 1.5em; }
math { font-family: "Latin Modern Math", "Cambria Math", serif; font-size: 1.05em; }
h2, h3, h4 { font-family: inherit; font-weight: bold; break-after: avoid; }
h2 { font-size: 14.4pt; margin: 20pt 0 8pt; }
h2 .num { display: inline-block; min-width: 1.6em; }
h3 { font-size: 12pt; margin: 14pt 0 6pt; }
h4 { font-size: 10.5pt; margin: 12pt 0 4pt; }
ul { margin: 4pt 0 8pt; padding-left: 1.6em; } li { margin: 2pt 0; text-align: justify; }
/* tableaux à la manière de booktabs : filets horizontaux seulement */
table { width: 100%; border-collapse: collapse; margin: 6pt 0 12pt; font-size: 9.5pt; border-top: 1pt solid #000; border-bottom: 1pt solid #000; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
th, td { padding: 2.5pt 6pt; vertical-align: top; text-align: left; border: none; }
thead th { font-weight: bold; border-bottom: .5pt solid #000; }
td.n, th.n { text-align: right; font-variant-numeric: tabular-nums lining-nums; white-space: nowrap; }
thead th, thead th.n { white-space: normal; vertical-align: bottom; }
td.c, th.c { text-align: center; }
table.kv th { width: 52%; font-weight: normal; }
table.kv tr + tr th, table.kv tr + tr td { border-top: .25pt solid #c8c8c8; }
table.calcul td { padding: 3pt 6pt; }
table.calcul tr + tr td { border-top: .25pt solid #c8c8c8; }
table.calcul td.des { width: 27%; font-style: italic; }
table.calcul td.res { width: 22%; text-align: right; white-space: nowrap; }
table.calcul math { math-style: normal; }   /* fractions en taille d'affichage, comme \displaystyle */
table.fixe { table-layout: fixed; }
table.fixe td.el { overflow-wrap: anywhere; }
.ok, .ko { white-space: nowrap; }
.equation { display: flex; align-items: center; margin: 8pt 0 10pt; break-inside: avoid; }
.equation math { flex: 1; }
.equation .no { width: 3em; text-align: right; }
.ok { font-weight: bold; color: #1b5e20; } .ko { font-weight: bold; color: #b71c1c; }
.note { font-size: 9pt; }
.reserve { border-left: 2pt solid #b71c1c; padding: 4pt 0 4pt 10pt; margin: 8pt 0; }
.saut { break-before: page; }

/* page de garde, dans l'esprit d'un \begin{titlepage} */
.garde { height: 264mm; display: flex; flex-direction: column; text-align: center; }
.garde .bet { display: flex; gap: 8mm; align-items: center; justify-content: center; }
.garde .bet img { max-height: 20mm; max-width: 40mm; }
.garde .bet-nom { font-size: 14pt; font-weight: bold; font-variant: small-caps; letter-spacing: .04em; }
.garde .bet-coord { font-size: 9pt; }
.garde .filet { border-top: 1.2pt solid #000; border-bottom: .4pt solid #000; height: 3pt; margin: 12mm 0 10mm; }
.garde .titre .t1 { font-size: 24.88pt; font-weight: bold; letter-spacing: .02em; }
.garde .titre .t2 { font-size: 12pt; font-variant: small-caps; letter-spacing: .08em; margin-top: 3mm; }
.garde .objet { font-size: 14pt; font-style: italic; margin: 10mm 10mm 0; }
.garde .filet.bas { margin: 10mm 0 8mm; }
.garde table.inter { width: 78%; margin: 0 auto; text-align: left; }
.garde table.inter th { width: 45%; }
.garde .pied { margin-top: auto; text-align: left; }
.garde .visas { display: flex; gap: 6mm; margin-top: 4mm; }
.garde .visa { flex: 1; border: .5pt solid #000; height: 28mm; padding: 2mm 3mm; font-size: 9pt; font-style: italic; position: relative; }
.garde .visa img { position: absolute; right: 3mm; bottom: 2mm; max-height: 22mm; max-width: 38mm; }
.garde .refs { font-size: 9pt; text-align: center; margin-top: 4mm; font-variant: small-caps; letter-spacing: .05em; }

/* sommaire, façon \tableofcontents */
.sommaire { list-style: none; padding: 0; margin: 8pt 0; }
.sommaire > li { font-weight: bold; margin: 9pt 0 3pt; display: flex; }
.sommaire > li > a, .sommaire li a { color: inherit; text-decoration: none; }
.sommaire .sn { display: inline-block; min-width: 2em; }
.sommaire ol { list-style: none; padding-left: 2em; margin: 2pt 0 0; font-weight: normal; }
.sommaire ol li { margin: 2pt 0; }
.sommaire > li { flex-direction: column; }
/* conclusion et signatures restent sur la même page */
.conclusion { display: inline-block; width: 100%; }   /* bloc insécable : jamais coupé entre deux pages */
/* bloc de signatures : un rang de tableau, que le navigateur ne coupe pas entre deux pages */
table.signatures { margin-top: 12mm; border: none; table-layout: fixed; break-inside: avoid; }
table.signatures td { width: 33.3%; height: 34mm; border-top: .5pt solid #000; padding: 3mm 4mm 0 0; font-size: 9.5pt; position: relative; }
table.signatures td + td { padding-left: 4mm; }
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
  <div class="bet">{logo}<div><div class="bet-nom">{esc(bur.get('nom') or "Bureau d'études structure")}</div>
    <div class="bet-coord">{esc(coord)}</div><div class="bet-coord">{esc(ident)}</div></div></div>
  <div class="filet"></div>
  <div class="titre"><div class="t1">Note de calcul</div><div class="t2">Structure en béton armé — gros œuvre</div></div>
  <div class="objet">{esc(inp.get('objet') or inp.get('projet') or 'Projet')}</div>
  <div class="filet bas"></div>
  {kv([("Projet", esc(inp.get('projet') or '—'))] + [(k, esc(v) if v else '—') for k, v in inter]
       + [("Phase", esc(inp.get('phase') or 'Exécution'))], "kv inter")}
  <div class="pied">
    {tableau(["Indice", "Date", "Objet de la révision", "Établi par", "Vérifié par"],
             [[esc(inp.get('indice') or 'A'), date, "Première diffusion", esc(bur.get('ingenieur') or ''), ""]],
             ["c", "c", "", "", ""])}
    <div class="visas"><div class="visa">Bureau d'études — cachet et signature{cachet}</div>
      <div class="visa">Bureau de contrôle — visa</div></div>
    <div class="refs">BAEL 91 révisé 99 — RPS 2000 version 2011</div>
  </div>
</section>"""


SOMMAIRE = [
    ("s1", "Présentation de l'ouvrage", []), ("s2", "Règlements et documents de référence", []),
    ("s3", "Hypothèses de calcul", ["Béton", "Acier", "Enrobages et fissuration", "Sol de fondation", "Charges", "Combinaisons d'actions"]),
    ("s4", "Modélisation", []), ("s5", "Étude sismique (RPS 2000 version 2011)", []),
    ("s6", "Dimensionnement des éléments", ["Poteaux", "Poutres", "Semelles", "Voiles"]),
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
            + kv(lignes))


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
    sol = (f"{fr(m['sigma_sol'])} bar" if m["sigma_sol"] else "à préciser par l'étude géotechnique")
    return "".join([
        h2(3, "s3", "Hypothèses de calcul"),
        "<p>Nous avons retenu les caractéristiques suivantes pour les matériaux, le sol de fondation et les charges.</p>",
        "<h3>3.1 Béton</h3>",
        kv([("Résistance caractéristique à 28 jours fc28", f"{fr(m['fc28'], 0)} MPa"),
            ("Résistance à la traction ft28 = 0,6 + 0,06·fc28", f"{fr(m['ft28'])} MPa"),
            ("Résistance de calcul fbu = 0,85·fc28 / (θ·γb), γb = 1,5", f"{fr(m['fbu'])} MPa"),
            ("Contrainte limite de service σbc = 0,6·fc28", f"{fr(m['sigma_bc'], 1)} MPa"),
            ("Module instantané Eij = 11 000·fc28^(1/3)", f"{fr(m['Eij'], 0)} MPa"),
            ("Module différé Evj = 3 700·fc28^(1/3)", f"{fr(m['Evj'], 0)} MPa")]),
        "<h3>3.2 Acier</h3>",
        kv([("Nuance", f"Haute adhérence FeE{fr(m['fe'], 0)}"),
            ("Limite d'élasticité fe", f"{fr(m['fe'], 0)} MPa"),
            ("Résistance de calcul fsu = fe / γs, γs = 1,15", f"{fr(m['fsu'], 1)} MPa"),
            ("Module d'élasticité Es", "200 000 MPa"),
            ("Coefficient de fissuration η", "1,6")]),
        "<h3>3.3 Enrobages et fissuration</h3>",
        kv([("Enrobage des poteaux", f"{fr(m['enrobage_poteau'], 0)} mm"), ("Enrobage des poutres", f"{fr(m['enrobage_poutre'], 0)} mm"),
            ("Enrobage des fondations", f"{fr(m['enrobage_semelle'], 0)} mm"),
            ("Fissuration", FISSURATION.get(m["fissuration"], m["fissuration"])),
            ("Contrainte limite de l'acier en service σst", f"{fr(m['sigma_st'], 1)} MPa")]),
        "<h3>3.4 Sol de fondation</h3>",
        kv([("Contrainte admissible du sol σsol", sol),
            ("Source", esc(f"rapport géotechnique — {inp['laboratoire']}") if inp.get("laboratoire") else "rapport géotechnique")]),
        "<h3>3.5 Charges</h3>",
        ("<p>Les charges permanentes G et d'exploitation Q appliquées dans le modèle sont les suivantes :</p><ul>"
         + "".join(f"<li>{esc(h)}</li>" for h in charges_modele) + "</ul>"
         if charges_modele else "<p>Les charges permanentes G et d'exploitation Q sont celles appliquées dans le modèle de calcul.</p>"),
        "<p>Pour mémoire, nous rappelons les charges d'exploitation réglementaires (NF P 06-001) :</p>",
        tableau(["Usage", "Q (kN/m²)"], q, ["", "n"]),
        "<h3>3.6 Combinaisons d'actions</h3>",
        "<p>Les sollicitations de calcul résultent des combinaisons suivantes :</p>",
        tableau(["État limite", "Combinaison"],
                [["ELU fondamental", "1,35 G + 1,5 Q"], ["ELS", "G + Q"],
                 ["Accidentelle sismique (RPS 2011)", "G + ψ·Q ± E, avec ψ fonction de l'usage"]]),
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
              "pour les combinaisons définies au paragraphe 3.6.</p>" + kv(lignes)
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
    out.append(kv([(k, esc(v)) for k, v in donnees] + [
        ("Coefficient de vitesse " + im(r"\upsilon"), fr(s.get("nu_m_s"))), ("Coefficient de site " + im("S"), fr(s.get("S"))),
        ("Coefficient d'importance " + im("I"), fr(s.get("I"))), ("Coefficient de comportement " + im("K"), fr(s.get("K"))),
        ("Coefficient d'usage " + im(r"\psi"), fr(s.get("psi"))), ("Période fondamentale " + im("T"), f"{fr(s.get('T_s'), 3)} s"),
        ("Facteur d'amplification dynamique " + im("D"), fr(s.get("D"), 3)), ("Poids sismique " + im("W"), f"{fr(s.get('W_kn'), 0)} kN"),
        ("Effort sismique à la base " + im("F"), f"<b>{fr(s.get('F_base_kn'), 1)} kN</b>"),
        ("Force au sommet " + im("F_t"), f"{fr(s.get('Ft_kn'), 1)} kN")]))
    if s.get("W_kn") and s.get("F_base_kn"):
        out.append("<p>Numériquement, " + im(rf"F = \frac{{{tx(s.get('nu_m_s'))} \times {tx(s.get('S'))} \times {tx(s.get('D'), 3)} "
                                             rf"\times {tx(s.get('I'))} \times {tx(s.get('W_kn'), 0)}}}{{{tx(s.get('K'))}}} = {tx(s.get('F_base_kn'), 1)}\ \text{{kN}}")
                   + f" : l'effort sismique à la base représente ainsi {fr(100 * s['F_base_kn'] / s['W_kn'], 1)} % du poids sismique du bâtiment.</p>")
    if s.get("Fn"):
        out.append("<h3>Répartition verticale</h3>")
        out.append("<p>Cet effort est réparti sur la hauteur du bâtiment, proportionnellement aux masses et aux hauteurs des niveaux :</p>")
        out.append(EQ(r"F_n = \frac{(F - F_t) \, W_n \, h_n}{\sum W_i \, h_i}"))
        out.append(tableau(["Niveau", im("W_n") + " (kN)", im("h_n") + " (m)", im("F_n") + " (kN)"],
                           [[esc(n.get("niveau")), fr(n.get("Wn_kn"), 0), fr(n.get("hn_m")), fr(n.get("Fn_kn"), 1)] for n in s["Fn"]],
                           ["", "n", "n", "n"]))
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
                       esc(liste_noms(t["noms"])), fr(e.get("nu_kn"), 0), fr(e.get("nu_lim_kn_avec_as_fournie"), 0),
                       fr(e.get("nu_rapport"), 2), esc((e.get("ferraillage") or {}).get("choix")), etat(t["ok"])])
    out.append("<p>Les poteaux de même section et de même ferraillage sont regroupés en types :</p>")
    out.append(tableau(["Type", "a × b (cm)", "Nb", "Éléments", im("N_u") + " max (kN)", im(r"N_{u,\lim}") + " (kN)",
                        im(r"N_u / N_{u,\lim}"), "Ferraillage", "État"],
                       lignes, ["", "c", "c", "el", "n", "n", "n", "", "c"], largeurs=[5, 9, 5, 29, 9, 9, 9, 14, 11]))
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
        lignes.append([t["code"], f"{fr(e.get('b_cm'), 0)} × {fr(e.get('h_cm'), 0)}", str(len(t["elements"])), esc(liste_noms(t["noms"])),
                       fr(e.get("mu_knm"), 1) if e.get("mu_knm") is not None else "—", fr(e.get("as_retenue_cm2")),
                       esc((e.get("ferraillage") or {}).get("choix")),
                       f"{fr(els.get('sigma_st_mpa'), 0)} / {fr(els.get('sigma_st_lim_mpa'), 0)}",
                       f"{fr(tau.get('tau_u_mpa'), 2)} / {fr(tau.get('tau_u_lim_mpa'), 2)}", etat(t["ok"])])
    out.append("<p>Les poutres de même section et de même ferraillage sont regroupées en types :</p>")
    out.append(tableau(["Type", "b × h (cm)", "Nb", "Éléments", im("M_u") + " (kN·m)", im("A_s") + " (cm²)", "Ferraillage",
                        im(r"\sigma_{st}") + " / lim (MPa)", im(r"\tau_u") + " / lim (MPa)", "État"],
                       lignes, ["", "c", "c", "el", "n", "n", "", "n", "n", "c"], largeurs=[5, 9, 5, 25, 8, 7, 11, 10, 9, 11]))
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
        lignes.append([t["code"], str(len(t["elements"])), esc(liste_noms(t["noms"])), fr(e.get("A_m")), fr(e.get("B_m")), fr(e.get("H_m")),
                       fr(e.get("sigma_max_bar"), 2), esc(e.get("acier_x")), esc(e.get("acier_y")), etat(t["ok"])])
    out.append(tableau(["Type", "Nb", "Éléments", im("A") + " (m)", im("B") + " (m)", im("H") + " (m)", im(r"\sigma_{\max}") + " (bar)",
                        "Nappe X", "Nappe Y", "État"], lignes, ["", "c", "el", "n", "n", "n", "n", "", "", "c"], largeurs=[6, 5, 25, 7, 7, 7, 9, 11, 11, 12]))
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
        lignes.append([t["code"], f"{fr(e.get('longueur_m'))} × {fr(e.get('ep_cm'), 0)}", str(len(t["elements"])), esc(liste_noms(t["noms"])),
                       fr(e.get("sigma_max_mpa")), fr(e.get("sigma_min_mpa")), fr(e.get("tau_u_mpa"), 3), fr(e.get("as_rive_cm2")),
                       f"{fr(e.get('as_vert_par_m_cm2'))} / {fr(e.get('as_horiz_par_m_cm2'))}", etat(t["ok"])])
    out.append(tableau(["Type", "L (m) × e (cm)", "Nb", "Éléments", im(r"\sigma_{\max}") + " (MPa)", im(r"\sigma_{\min}") + " (MPa)",
                        im(r"\tau_u") + " (MPa)", "As rive (cm²)", "As V / H (cm²/m)", "État"],
                       lignes, ["", "c", "c", "el", "n", "n", "n", "n", "n", "c"], largeurs=[5, 10, 5, 23, 8, 8, 8, 8, 14, 11]))
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
    out.append(tableau(["Famille", "Béton (m³)", "Acier (kg)", "Ratio (kg/m³)"], lignes, ["", "n", "n", "n"]))
    if nomen:
        out.append("<h3>Acier par diamètre</h3>")
        out.append(tableau(["Diamètre", "kg/m", "Poids (kg)"],
                           [[f"HA{d}", fr(poids_ml(d), 3), fr(kg, 1)] for d, kg in nomen["par_diametre_kg"].items()],
                           ["", "n", "n"]))
    out.append('<p class="note">Béton : volumes géométriques des éléments calculés (hors dalles, longrines et escaliers). '
               "Acier : longueurs façonnées des éléments vérifiés, recouvrements et crochets compris (voir la nomenclature des plans).</p>")
    return "".join(out)


def conclusion(inp: dict, bur: dict, date: str) -> str:
    reserves = []
    for fam, verif, nom in (("poteaux", ok_poteau, "Poteau"), ("poutres", ok_poutre, "Poutre"),
                            ("semelles_isolees", ok_semelle, "Semelle"), ("voiles", ok_voile, "Voile")):
        for i, e in enumerate(inp.get(fam) or []):
            if not verif(e):
                reserves.append(f"{nom} {_nom(e, i, nom[0])}")
    out = ['<div class="conclusion">', h2(8, "s8", "Conclusion, réserves et visas")]
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
    global EQ
    EQ = Equations()
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
        quantites(inp), conclusion(inp, bur, date),
    ]
    return (f'<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8"><title>Note de calcul — {esc(titre)}</title>'
            f'<style>{css}</style></head><body><div class="ecran">{"".join(corps)}</div></body></html>')
