"""Import d'un modèle depuis Excel : alternative à Robot.

Bénayfacile fournit un classeur modèle (une feuille par famille d'éléments). L'utilisateur
le remplit à la main, ou y colle les tableaux de résultats exportés de Robot. Le fichier
importé produit la même « ossature » que la lecture Robot (voir robot_ossature.py) :
le calcul en lot, la note, l'Excel et les plans DXF fonctionnent sans changement.

Règles : une donnée illisible n'est jamais devinée. La ligne est conservée avec une
valeur vide (le calcul en lot la marque « Incomplet ») et une remarque cite la feuille,
la ligne et la colonne.
"""
from __future__ import annotations

import io
import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from robot_ossature import COEF_LF, nom_niveau

# (clé de l'ossature, en-tête affiché, requis, nombre ?, alias acceptés à l'import)
Colonne = Tuple[str, str, bool, bool, Tuple[str, ...]]

FEUILLES: Dict[str, List[Colonne]] = {
    "poteaux": [
        ("nom", "Nom", True, False, ("element", "poteau", "repere")),
        ("niveau", "Niveau", False, False, ("etage",)),
        ("axe", "Axe (ex. B2)", False, False, ("file", "axe")),
        ("a_cm", "a (cm)", True, True, ("a", "cote a", "largeur")),
        ("b_cm", "b (cm)", True, True, ("b", "cote b", "profondeur")),
        ("hauteur_m", "Hauteur d'étage (m)", False, True, ("hauteur", "he", "l0", "longueur")),
        ("lf_m", "lf (m)", False, True, ("lf", "longueur de flambement")),
        ("nu_kn", "Nu ELU (kN)", True, True, ("nu", "n elu", "effort normal elu", "fx elu")),
        ("ns_kn", "Ns ELS (kN)", False, True, ("ns", "n els", "effort normal els", "fx els")),
        ("mx_knm", "Mx ELU (kN.m)", False, True, ("mx", "my elu robot")),
        ("my_knm", "My ELU (kN.m)", False, True, ("my", "mz")),
    ],
    "poutres": [
        ("nom", "Nom", True, False, ("element", "poutre", "repere")),
        ("niveau", "Niveau", False, False, ("etage",)),
        ("b_cm", "b (cm)", True, True, ("b", "largeur")),
        ("h_cm", "h (cm)", True, True, ("h", "hauteur")),
        ("portee_m", "Portée (m)", False, True, ("portee", "longueur", "l")),
        ("mu_knm", "Mu ELU (kN.m)", True, True, ("mu", "m elu", "moment elu")),
        ("ms_knm", "Ms ELS (kN.m)", False, True, ("ms", "m els", "moment els")),
        ("vu_kn", "Vu ELU (kN)", False, True, ("vu", "v elu", "effort tranchant", "tranchant")),
    ],
    "semelles": [
        ("nom", "Nom", True, False, ("element", "semelle", "repere")),
        ("axe", "Axe (ex. B2)", False, False, ("file", "axe")),
        ("a_poteau_cm", "Poteau a (cm)", True, True, ("a", "poteau a", "a poteau")),
        ("b_poteau_cm", "Poteau b (cm)", True, True, ("b", "poteau b", "b poteau")),
        ("ns_kn", "Ns ELS (kN)", True, True, ("ns", "n els", "effort normal els")),
        ("nu_kn", "Nu ELU (kN)", False, True, ("nu", "n elu", "effort normal elu")),
        ("mx_knm", "Mx (kN.m)", False, True, ("mx",)),
        ("my_knm", "My (kN.m)", False, True, ("my",)),
    ],
    "voiles": [
        ("nom", "Nom", True, False, ("element", "voile", "repere")),
        ("niveau", "Niveau", False, False, ("etage",)),
        ("longueur_m", "Longueur L (m)", True, True, ("longueur", "l")),
        ("ep_cm", "Épaisseur e (cm)", True, True, ("epaisseur", "e", "ep")),
        ("hauteur_m", "Hauteur (m)", False, True, ("hauteur", "he")),
        ("n_kn", "N ELU (kN)", True, True, ("n", "n elu", "effort normal")),
        ("m_knm", "M ELU (kN.m)", False, True, ("m", "m elu", "moment")),
        ("v_kn", "V ELU (kN)", False, True, ("v", "v elu", "effort tranchant")),
    ],
}
TITRES = {"poteaux": "Poteaux", "poutres": "Poutres", "semelles": "Semelles", "voiles": "Voiles"}
TRAME = "Trame"

ENCRE, FOND_TETE, GRIS = "0F1F38", "E6EBF1", "4F5D70"


def _norme(texte) -> str:
    """En-tête comparable : minuscules, sans accents, sans unité ni ponctuation."""
    t = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\([^)]*\)", " ", t)                   # unités entre parenthèses
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return t


def _nombre(v) -> Optional[float]:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, (int, float)):
        return float(v)
    t = str(v).strip().replace(" ", "").replace(" ", "").replace(" ", "").replace(",", ".")
    return float(t)


# ───────────────────────── classeur modèle ─────────────────────────

def creer_modele() -> bytes:
    wb = Workbook()
    lisez = wb.active
    lisez.title = "Lisez-moi"
    lignes = [
        ("Bénayfacile — modèle d'import", True),
        ("", False),
        ("1. Remplissez une feuille par famille : Poteaux, Poutres, Semelles, Voiles (une ligne par élément).", False),
        ("2. Unités imposées : cm pour les sections, m pour les longueurs, kN et kN.m pour les efforts.", False),
        ("3. Efforts de calcul : ELU (1,35 G + 1,5 Q) et ELS (G + Q), en valeur absolue, comme dans Robot.", False),
        ("4. Colonnes en gras : obligatoires. Une ligne incomplète est importée puis signalée « Incomplet ».", False),
        ("5. lf vide : 0,7 × hauteur d'étage (poteau encastré en pied, BAEL B.8.3,31).", False),
        ("6. Feuille Trame (facultative) : positions des files en mètres, pour le plan de fondation DXF.", False),
        ("7. Vous pouvez coller les tableaux de résultats de Robot : gardez les en-têtes de ce modèle.", False),
        ("", False),
        ("Exemple de poteau : Nom P B2, Niveau RDC, Axe B2, a 40, b 40, Hauteur 3, Nu 1711, Ns 1245, Mx 51, My 26", False),
        ("Exemple de poutre : Nom Pt A1-A2, Niveau RDC, b 25, h 50, Portée 6, Mu 120, Ms 87, Vu 90", False),
    ]
    for i, (texte, gras) in enumerate(lignes, start=1):
        c = lisez.cell(row=i, column=1, value=texte)
        c.font = Font(bold=gras, size=14 if gras else 11, color=ENCRE if gras else "000000")
    lisez.column_dimensions["A"].width = 110

    for cle, colonnes in FEUILLES.items():
        ws = wb.create_sheet(TITRES[cle])
        for j, (_, entete, requis, nombre, _) in enumerate(colonnes, start=1):
            c = ws.cell(row=1, column=j, value=entete)
            c.font = Font(bold=requis, color=ENCRE if requis else GRIS)
            c.fill = PatternFill("solid", fgColor=FOND_TETE)
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            lettre = c.column_letter
            ws.column_dimensions[lettre].width = max(12, len(entete) + 3)
            if nombre:   # garde-fou à la saisie : nombre ≥ 0
                dv = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True,
                                    showErrorMessage=True, errorTitle="Valeur invalide",
                                    error="Saisissez un nombre positif, dans l'unité de la colonne.")
                dv.add(f"{lettre}2:{lettre}2000")
                ws.add_data_validation(dv)
        ws.freeze_panes = "A2"
        ws.row_dimensions[1].height = 30

    tr = wb.create_sheet(TRAME)
    for j, t in enumerate(("Files X (m)", "Files Y (m)"), start=1):
        c = tr.cell(row=1, column=j, value=t)
        c.font = Font(bold=True, color=ENCRE)
        c.fill = PatternFill("solid", fgColor=FOND_TETE)
        tr.column_dimensions[c.column_letter].width = 16
    tr.cell(row=1, column=4, value="Positions cumulées depuis la file 1 / A, ex. 0, 6, 12").font = Font(italic=True, color=GRIS)
    tr.freeze_panes = "A2"

    flux = io.BytesIO()
    wb.save(flux)
    return flux.getvalue()


# ───────────────────────── lecture ─────────────────────────

def _feuille(wb, cle: str):
    for ws in wb.worksheets:
        if _norme(ws.title) in (cle, _norme(TITRES[cle]), cle.rstrip("x").rstrip("s")):
            return ws
    return None


def _correspondances(entetes: List[str], colonnes: List[Colonne]) -> Dict[int, Colonne]:
    """Indice de colonne → définition, d'après l'en-tête exact puis les alias."""
    vus, carte = set(), {}
    normes = [_norme(e) for e in entetes]
    for col in colonnes:
        cles = [_norme(col[1])] + [_norme(a) for a in col[4]]
        for j, n in enumerate(normes):
            if j not in vus and n and n in cles:
                carte[j] = col
                vus.add(j)
                break
    return carte


def lire_classeur(octets: bytes) -> dict:
    try:
        wb = load_workbook(io.BytesIO(octets), data_only=True, read_only=True)
    except Exception as e:
        raise ValueError(f"le fichier n'est pas un classeur Excel lisible (.xlsx) : {e}") from e

    oss: Dict[str, list] = {"poteaux": [], "poutres": [], "semelles": [], "voiles": []}
    remarques: List[str] = []
    for cle, colonnes in FEUILLES.items():
        ws = _feuille(wb, cle)
        if ws is None:
            continue
        lignes = list(ws.iter_rows(values_only=True))
        if not lignes:
            continue
        carte = _correspondances(list(lignes[0]), colonnes)
        manquantes = [c[1] for c in colonnes if c[2] and c not in carte.values()]
        if manquantes:
            remarques.append(f"{ws.title} : colonne(s) obligatoire(s) absente(s) : {', '.join(manquantes)}.")
        for i, ligne in enumerate(lignes[1:], start=2):
            if not any(v not in (None, "") for v in ligne):
                continue
            el: dict = {c[0]: None for c in colonnes}
            for j, (k, entete, _, nombre, _) in carte.items():
                v = ligne[j] if j < len(ligne) else None
                if nombre:
                    try:
                        el[k] = _nombre(v)
                    except (TypeError, ValueError):
                        remarques.append(f"{ws.title}, ligne {i} : « {entete} » n'est pas un nombre ({v!r}).")
                        el[k] = None
                    if el[k] is not None and el[k] < 0:
                        el[k] = abs(el[k])     # efforts en valeur absolue, comme la lecture Robot
                else:
                    el[k] = None if v is None else str(v).strip() or None
            nom = el.get("nom") or f"{TITRES[cle][:-1]} ligne {i}"
            el["nom"] = nom
            el["id"] = f"X-{cle}-{i}"
            # valeurs par défaut documentées dans « Lisez-moi »
            if cle == "poteaux":
                if el.get("lf_m") is None and el.get("hauteur_m"):
                    el["lf_m"] = round(COEF_LF * el["hauteur_m"], 2)
                el["mx_knm"] = el.get("mx_knm") or 0.0
                el["my_knm"] = el.get("my_knm") or 0.0
            if cle == "semelles":
                el["mx_knm"] = el.get("mx_knm") or 0.0
                el["my_knm"] = el.get("my_knm") or 0.0
            if cle == "voiles" and el.get("hauteur_m") is None:
                el["hauteur_m"] = 3.0
            oss[cle].append(el)

    trame_x: List[float] = []
    trame_y: List[float] = []
    ws = next((w for w in wb.worksheets if _norme(w.title) == "trame"), None)
    if ws is not None:
        for i, ligne in enumerate(list(ws.iter_rows(values_only=True))[1:], start=2):
            for j, cible in ((0, trame_x), (1, trame_y)):
                v = ligne[j] if j < len(ligne) else None
                try:
                    n = _nombre(v)
                except (TypeError, ValueError):
                    remarques.append(f"Trame, ligne {i} : valeur ignorée ({v!r}).")
                    continue
                if n is not None:
                    cible.append(n)
    if not (trame_x and trame_y) and oss["semelles"]:
        remarques.append("Pas de feuille Trame : le plan de fondation DXF ne sera pas dessiné (les détails le seront).")

    total = sum(len(v) for v in oss.values())
    if total == 0:
        reconnues = [ws.title for ws in wb.worksheets if any(_feuille(wb, k) is ws for k in FEUILLES)]
        if reconnues:   # le modèle Bénayfacile, mais sans aucune ligne remplie
            raise ValueError(
                "le classeur est le modèle vide : ajoutez au moins une ligne (un élément) sous les en-têtes "
                f"des feuilles {', '.join(reconnues)}, puis enregistrez et importez-le de nouveau")
        trouvees = ", ".join(ws.title for ws in wb.worksheets) or "aucune"
        raise ValueError(
            f"ce classeur n'a pas le format du modèle Bénayfacile (feuilles trouvées : {trouvees} ; attendues : "
            "Poteaux, Poutres, Semelles, Voiles). Téléchargez le modèle Excel et recopiez-y vos éléments")

    niveaux_vus = []
    for el in oss["poteaux"] + oss["poutres"] + oss["voiles"]:
        if el.get("niveau") and el["niveau"] not in niveaux_vus:
            niveaux_vus.append(el["niveau"])
    oss.update({
        "niveaux": niveaux_vus or [nom_niveau(0)],
        "trame_x_m": sorted(set(trame_x)), "trame_y_m": sorted(set(trame_y)),
        "source": "excel", "remarques": remarques,
        "hypotheses": ["Données saisies dans le classeur importé ; efforts pris en valeur absolue.",
                       "lf = 0,7 × hauteur d'étage quand la colonne lf est vide."],
        "resume": {k: len(oss[k]) for k in ("poteaux", "poutres", "semelles", "voiles")},
    })
    return oss
