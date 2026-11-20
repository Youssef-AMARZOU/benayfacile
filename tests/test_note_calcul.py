"""Note de calcul au format d'un bureau d'études : structure, formules, polices, réserves."""
import html as html_
import json
import pathlib
import re
import sys
import xml.dom.minidom

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "services"))

import engine_service as e  # noqa: E402
import note_calcul as nc  # noqa: E402
import robot_ossature as ro  # noqa: E402

BUREAU = {"nom": "BET Atlas", "ingenieur": "Ing. Exemple", "adresse": "Casablanca", "rc": "123"}


@pytest.fixture(scope="module")
def note_r4():
    o = ro.ossature_simulation()
    lot = e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}, materiaux={"sigma_sol_bar": 2.0}))
    syn = lambda fam, extra=lambda l: {}: [{**l["resultat"], "nom": l["nom"], "niveau": l.get("niveau"), **extra(l)}
                                          for l in lot[fam] if l.get("resultat")]
    demo = json.loads((RACINE / "examples" / "demo_inputs.json").read_text(encoding="utf-8"))
    inp = {"projet": "Résidence Atlas", "client": "Client", "site": "Casablanca", "indice": "B", "phase": "Exécution",
           "objet": "Construction d'un immeuble R+4", "controle": "Contrôle Exemple", "laboratoire": "Labo Exemple",
           "lot": lot, "robot": {"mode": "simulation", "ossature": o},
           "sismique": {**e.sismique(e.SismiqueInput(**demo["sismique"])), "donnees": demo["sismique"]},
           "poteaux": syn("poteaux", lambda l: {"nu_kn": l["entree"]["nu_kn"]}),
           "poutres": syn("poutres", lambda l: {"mu_knm": l["entree"]["mu_knm"]}),
           "semelles_isolees": syn("semelles"), "voiles": syn("voiles")}
    return nc.construire(inp, BUREAU), inp


def test_plan_type_bureau_d_etudes(note_r4):
    html = html_.unescape(note_r4[0])
    for titre in ("Note de calcul", "Table des matières", "Présentation de l'ouvrage", "Règlements et documents de référence",
                  "Hypothèses de calcul", "Modélisation", "Étude sismique", "Dimensionnement des éléments",
                  "Quantités de béton et d'acier", "Conclusion, réserves et visas"):
        assert titre in html, titre
    for intervenant in ("Contrôle Exemple", "Labo Exemple", "BET Atlas", "Exécution"):
        assert intervenant in html


def test_formules_mathml_bien_formees_et_numerotees(note_r4):
    html, _ = note_r4
    formules = re.findall(r"<math .*?</math>", html, flags=re.S)
    assert len(formules) > 60
    for f in formules:
        xml.dom.minidom.parseString(f)
    numeros = [int(n) for n in re.findall(r'<span class="no">\((\d+)\)</span>', html)]
    assert numeros == list(range(1, len(numeros) + 1)) and len(numeros) >= 8


def test_police_des_formules_embarquee(note_r4):
    html, _ = note_r4
    assert 'font-family: "Latin Modern Math"' in html          # formules : police mathématique embarquée
    assert '"Segoe UI"' in html                                 # texte : police système sans empattement
    assert html.count("data:font/woff2;base64,") == 1
    assert (RACINE / "services" / "polices" / "GUST-FONT-LICENSE.txt").exists()


def test_exemples_de_calcul_avec_valeurs_reelles(note_r4):
    html, inp = note_r4
    p = max(inp["poteaux"], key=lambda x: x["nu_rapport"])
    assert f"poteau le plus sollicité, {p['nom']}" in html
    assert f'{nc.fr(p["nu_lim_kn_avec_as_fournie"], 1)} kN' in html     # Nu,lim du poteau, valeur affichée
    assert "Exemple de calcul : poutre la plus sollicitée" in html and "semelle la plus chargée" in html


def test_types_regroupes_et_quantites(note_r4):
    html, inp = note_r4
    assert ">P1<" in html and ">Pt1<" in html and ">S1<" in html and ">V1<" in html
    assert 'Ratio<br><span class="u">(kg/m³)</span>' in html and "Acier par diamètre" in html
    assert "HA32" not in html                       # aciers de poutre constructibles


def test_tableaux_legendes_numerotees_et_hypotheses_en_quatre_colonnes(note_r4):
    html, _ = note_r4
    numeros = [int(n) for n in re.findall(r"<caption>Tableau (\d+) — ", html)]
    assert numeros == list(range(1, len(numeros) + 1)) and len(numeros) >= 15
    for titre in ("Caractéristiques du béton", "Types de poteaux", "Types de poutres", "Acier par diamètre"):
        assert f"— {titre}</caption>" in html, titre
    assert "<th>Symbole</th>" in html.replace('<th class="c">Symbole</th>', "<th>Symbole</th>")
    assert "Repères" in html and "Niveaux" in html


def test_reserves_listees_quand_un_element_echoue(note_r4):
    _, inp = note_r4
    inp2 = dict(inp)
    inp2["poteaux"] = [dict(inp["poteaux"][0], nu_rapport=1.3)] + inp["poteaux"][1:]
    html = nc.construire(inp2, BUREAU)
    assert "Réserves." in html and inp["poteaux"][0]["nom"] in html.split("Réserves.")[1]


def test_note_sans_lot_ni_sismique():
    html = nc.construire({"projet": "Petit projet", "poutres": [e.poutre(e.PoutreInput(b_cm=25, h_cm=50, mu_knm=80, vu_kn=60))]}, {})
    assert "L'étude sismique n'a pas été jointe" in html and "ne sont pas disponibles" in html
    assert "Aucun poteau calculé." in html
