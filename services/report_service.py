"""Service Rapport — génération de la NOTE DE CALCUL (HTML imprimable A4).

Entrée : état de session complet (Robot + modules moteur + bureau).
Port : 8004
"""
from __future__ import annotations
import datetime
import html
import json
import pathlib
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

HERE = pathlib.Path(__file__).resolve().parent
# BNAY_DATA : dossier de données inscriptible (fixé par le lanceur .exe)
DATA = pathlib.Path(__import__("os").environ.get("BNAY_DATA", str(HERE.parent)))
REFS = DATA / "referentiels"
OUT = DATA / "output"
OUT.mkdir(exist_ok=True)

app = FastAPI(title="Bénayfacile — Service Rapport", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm;
  @bottom-left  { content: "Bénayfacile — Note de calcul"; font-size: 8pt; color:#889; }
  @bottom-center{ content: "Page " counter(page) " / " counter(pages); font-size: 8pt; color:#889; }
  @bottom-right { content: "Indice A — " attr(data-date); font-size: 8pt; color:#889; } }
* { box-sizing: border-box; }
body { font-family: Georgia, 'Times New Roman', serif; font-size: 10.5pt; color:#1a2233; margin:0; }
h1 { font-size: 22pt; color:#0e2a47; border-bottom: 3px solid #c9a227; padding-bottom:6px; margin-top:0; }
h2 { font-size: 14pt; color:#ffffff; background:#0e2a47; padding:6px 10px; border-radius:3px; margin-top:22px; }
h3 { font-size: 11.5pt; color:#0e2a47; border-bottom:1px solid #c9a227; padding-bottom:3px; }
.cover { text-align:center; padding: 60px 30px 30px; }
.cover .brand { font-size: 30pt; font-weight: bold; color:#0e2a47; letter-spacing:1px; }
.cover .tag { color:#c9a227; font-size: 12pt; letter-spacing:3px; text-transform:uppercase; }
.box { border:1.5px solid #0e2a47; border-radius:6px; padding: 12px 16px; margin: 10px auto; max-width: 600px; }
table { border-collapse: collapse; width:100%; margin: 10px 0; font-size: 8.5pt; }
th { background:#0e2a47; color:#fff; padding:5px 6px; text-align:left; font-size:8pt; }
td { border-bottom: 1px solid #d8dcea; padding:4px 6px; }
tr:nth-child(even) td { background:#f4f6fb; }
.ok { color:#0a7d2c; font-weight:bold; }
.ko { color:#b3001b; font-weight:bold; }
.audit td, .audit th { font-size:7.5pt; }
.small { font-size:8pt; color:#556; }
.formula { background:#f7f4e8; border-left:3px solid #c9a227; padding:6px 10px; font-family: 'Consolas', monospace; font-size:8pt; margin:6px 0; }
.sig { margin-top:36px; }
.sig td { border:none; background:none; }
hr.gold { border:none; border-top:2px solid #c9a227; margin: 18px 0; }
.footer-note { font-size:8pt; color:#667; border-top:1px solid #c9a227; padding-top:6px; margin-top:20px; }
"""

def esc(v: Any) -> str:
    return html.escape(str(v))

def row(label: str, value: Any) -> str:
    return f"<tr><td style='width:55%'>{esc(label)}</td><td><b>{esc(value)}</b></td></tr>"

def dict_table(d: dict, skip=()) -> str:
    rows = []
    for k, v in d.items():
        if k in skip:
            continue
        if isinstance(v, (dict, list)):
            continue
        rows.append(row(k, v))
    return "<table>" + "".join(rows) + "</table>" if rows else ""

def audit_table(audit) -> str:
    if not audit:
        return ""
    rows = []
    for a in audit:
        if isinstance(a, dict):
            st = a.get("statut", "")
            cls = "ok" if st == "OK" else "ko"
            rows.append(f"<tr><td>{esc(a.get('ligne',''))}</td><td>{esc(a.get('recalcule',''))}</td>"
                        f"<td>{esc(a.get('declare',''))}</td><td>{esc(a.get('ecart',''))}</td>"
                        f"<td class='{cls}'>{esc(st)}</td></tr>")
    return ("<h3>Audit arithmétique</h3><table class='audit'><tr><th>Ligne</th><th>Recalculé</th>"
            "<th>Document/déclaré</th><th>Écart</th><th>Statut</th></tr>" + "".join(rows) + "</table>")

def alerts(modules: dict) -> tuple[list, list]:
    """Retourne (alertes_critiques, avertissements)."""
    critiques, avert = [], []
    def visit(name, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("avertissements", "notes", "attention") and isinstance(v, list):
                    for x in v:
                        avert.append(f"[{name}] {x}")
                elif k == "audit" and isinstance(v, list):
                    for a in v:
                        if isinstance(a, dict) and a.get("statut") != "OK":
                            critiques.append(f"[{name} — ALERTE ECART ARITHMETIQUE] {a.get('ligne')} : recalculé {a.get('recalcule')} vs déclaré {a.get('declare')}")
                else:
                    visit(name, v)
        elif isinstance(obj, list):
            for it in obj:
                visit(name, it)
    for name, mod in modules.items():
        visit(name, mod)
    return critiques, avert


class NoteInput(BaseModel):
    projet: str = "Projet"
    client: str = ""
    site: str = ""
    indice: str = "A"
    robot: Optional[dict] = None
    sismique: Optional[dict] = None
    poteaux: Optional[list] = None
    poutres: Optional[list] = None
    semelles_isolees: Optional[list] = None
    semelles_filantes: Optional[list] = None
    voiles: Optional[list] = None
    bureau: Optional[dict] = None


def build_note(inp: NoteInput) -> str:
    bur = inp.bureau or json.loads((REFS / "bureau.json").read_text(encoding="utf-8"))
    now = datetime.date.today().strftime("%d/%m/%Y")
    aud_modules = {k: v for k, v in inp.model_dump().items() if isinstance(v, (list, dict)) and v and k not in ("bureau",)}
    alertes, avertissements = alerts(aud_modules)

    parts = [f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Note de calcul — {esc(inp.projet)}</title>
<style>{CSS}</style></head><body data-date="{now}">"""]

    # ---- page de garde
    parts.append(f"""<div class="cover">
<div class="brand">BÉNAYFACILE</div><div class="tag">Bureau d'études structure</div>
<div class="box">
<h1 style="border:none;text-align:center">NOTE DE CALCUL</h1>
<div class="small" style="text-align:center">Structure béton armé — BAEL 91 rév. 99 · RPS 2000 v2011</div>
<hr class="gold">
<table>
{row("Projet", inp.projet)}
{row("Client", inp.client or "—")}
{row("Site", inp.site or "—")}
{row("Indice", inp.indice)}
{row("Date", now)}
{row("Bureau", bur.get("nom", ""))}
{row("Adresse", bur.get("adresse", ""))}
{row("Tél / Email", f"{bur.get('telephone','')} — {bur.get('email','')}")}
{row("RC / ICE / Patente", f"{bur.get('rc','')} — {bur.get('ice','')} — {bur.get('patente','')}")}
{row("Ingénieur", bur.get("ingenieur", ""))}
</table></div></div>""")

    # ---- 1. Objet & références
    parts.append("""<h2>1 — Objet et références</h2>
<p>La présente note justifie le dimensionnement de la structure mentionnée ci-dessus (poteaux, poutres, voiles,
fondations superficielles) sur la base des hypothèses et références suivantes.</p>
<h3>1.1 Références normatives</h3>
<ul>
<li><b>BAEL 91 révisées 99</b> — Règles techniques de conception et de calcul des ouvrages et constructions en béton armé,
Fascicule 62, titre I<sup>er</sup> du CCTG (DTU P18-702), mars 1992, + Amendement A1 (février 2000). Articles cités :
A.4.2, A.4.3, A.4.5, A.8.1, B.8.3, B.8.4,1.</li>
<li><b>RPS 2000 — version 2011</b> — Règlement de Construction Parasismique (Ministère de l'Habitat, Royaume du Maroc),
révisant le décret 2-02-177 (décret 2-24-766 du 22/10/2024). Articles cités : 3.1, 3.3, 5.2, 6.2, 6.3, 7.2.</li>
<li><b>Logiciel de modèle</b> : Robot Structural Analysis Structural (Autodesk) — extraction par COM (Interop.RobotOM).</li>
</ul>
<h3>1.2 Hypothèses générales</h3>
<ul>
<li>Béton fc28 = 25 MPa (sauf mention contraire) ; acier HA fe = 500 MPa (γs = 1,15) ; γb = 1,5.</li>
<li>Enrobage : 30 mm (poteaux/poutres courants), 50 mm (semelles).</li>
<li>Fissuration considérée : <b>préjudiciable</b> (σst limité par A.4.5,33) sauf indication contraire.</li>
<li>θ = 1 (durée d'application des charges &gt; 24 h).</li>
<li>λ ≤ 70 (B.8.4,1) ; λ &gt; 70 → justification A.4.4 / Annexe E.7 obligatoire.</li>
<li>Sismique : approche statique équivalente (H ≤ 60 m, T ≤ 2 s, bâtiment régulier) ; sinon méthode modale.</li>
</ul>""")

    # ---- 2. Modèle Robot
    parts.append("<h2>2 — Modèle de calcul (Robot Structural Analysis)</h2>")
    if inp.robot:
        r = inp.robot
        parts.append(dict_table(r, skip=("niveaux", "combination_list", "combinaisons")))
        if isinstance(r.get("niveaux"), list):
            parts.append("<h3>Masses par niveau</h3><table><tr><th>Niveau</th><th>Altitude (m)</th><th>Wi (kN)</th></tr>")
            for n in r["niveaux"]:
                parts.append(f"<tr><td>{esc(n.get('nom'))}</td><td>{esc(n.get('altitude_m'))}</td><td>{esc(n.get('w_kn'))}</td></tr>")
            parts.append("</table>")
        if isinstance(r.get("combinaisons"), list):
            parts.append("<h3>Combinaisons</h3><ul>" + "".join(f"<li>{esc(c)}</li>" for c in r["combinaisons"]) + "</ul>")
        parts.append(f"<p class='small'>Mode d'extraction : <b>{esc(r.get('mode', 'simulation'))}</b> — "
                     + esc(json.dumps(r.get("robot_com", {}), ensure_ascii=False)) + "</p>")
    else:
        parts.append("<p><i>Modèle non fourni dans la synthèse (module Robot non renseigné).</i></p>")

    # ---- 3. Vérification sismique
    parts.append("<h2>3 — Vérification sismique (RPS 2000 v2011)</h2>")
    if inp.sismique:
        s = inp.sismique
        parts.append(f"""<div class="formula">F = υ·S·D·I·W/K &nbsp;&nbsp;;&nbsp;&nbsp; W = G + ψ·Q &nbsp;&nbsp;;&nbsp;&nbsp;
Fn = (F − Ft)·Wn·hn / ΣWi·hi ; Ft = 0 si T≤0,7 s, sinon 0,07·T·F</div>""")
        parts.append(dict_table(s, skip=("Fn", "hypotheses", "sources")))
        if isinstance(s.get("Fn"), list):
            parts.append("<h3>Répartition verticale des efforts sismiques</h3>"
                         "<table><tr><th>Niveau</th><th>Wi (kN)</th><th>hn (m)</th><th>Fn (kN)</th></tr>")
            for n in s["Fn"]:
                parts.append(f"<tr><td>{esc(n.get('niveau'))}</td><td>{esc(n.get('Wn_kn'))}</td>"
                             f"<td>{esc(n.get('hn_m'))}</td><td>{esc(n.get('Fn_kn'))}</td></tr>")
            parts.append("</table>")
        for h in (s.get("hypotheses") or []):
            parts.append(f"<p class='small'>• {esc(h)}</p>")
        for h in (s.get("sources") or []):
            parts.append(f"<p class='small'>Source : {esc(h)}</p>")
        parts.append(audit_table(s.get("audit")))
    else:
        parts.append("<p><i>Module vérification sismique non renseigné.</i></p>")

    # ---- 4. Poteaux
    parts.append("<h2>4 — Poteaux (compression centrée + flexion composée, BAEL B.8.4,1)</h2>")
    if inp.poteaux:
        parts.append("""<table><tr><th>Repère</th><th>a×b (cm)</th><th>lf (m)</th><th>λ</th><th>α</th>
<th>Nu (kN)</th><th>As calc. (cm²)</th><th>As ret.</th><th>Nu,lim (kN)</th><th>Statut</th></tr>""")
        for i, p in enumerate(inp.poteaux):
            fer = p.get("ferraillage", {})
            nu_lim = p.get("nu_lim_kn_avec_as_fournie")
            ok = "OK" if (nu_lim or 0) >= p.get("nu_kn", 0) else "INSUFFISANT"
            parts.append(f"<tr><td>P{i+1}</td><td>{esc(p.get('a_cm'))}×{esc(p.get('b_cm'))}</td>"
                         f"<td>{esc(p.get('lf_m'))}</td><td>{esc(p.get('lambda'))}</td><td>{esc(p.get('alpha'))}</td>"
                         f"<td>{esc(p.get('nu_kn'))}</td><td>{esc(p.get('as_calculee_cm2'))}</td>"
                         f"<td>{esc(fer.get('choix',''))}</td><td>{esc(nu_lim)}</td><td>{esc(ok)}</td></tr>")
        parts.append("</table>")
        for i, p in enumerate(inp.poteaux):
            parts.append(f"<h3>Poteau P{i+1} — détail</h3>")
            parts.append(f"<div class='formula'>Nu,lim = α·[Br·fc28/(0,9·γb) + A·fe/γs] ; λ = lf/i ; α = 0,85/(1+0,2(λ/35)²) λ≤50 ; α = 0,6(50/λ)² (50&lt;λ≤70)</div>")
            parts.append(dict_table({k: v for k, v in p.items() if k not in ("flexion_composee", "ferraillage", "audit")}))
            parts.append("<p><b>Flexion composée</b> : " + esc(json.dumps(p.get("flexion_composee", {}), ensure_ascii=False)) + "</p>")
            parts.append(audit_table(p.get("audit")))
    else:
        parts.append("<p><i>Aucun poteau calculé.</i></p>")

    # ---- 5. Poutres
    parts.append("<h2>5 — Poutres (flexion simple ELU, ELS, tranchant)</h2>")
    if inp.poutres:
        parts.append("""<table><tr><th>Repère</th><th>b×h (cm)</th><th>d (m)</th><th>μ</th><th>As (cm²)</th>
<th>Ferraillage</th><th>ELS σst (MPa)</th><th>τu (MPa)</th></tr>""")
        for i, p in enumerate(inp.poutres):
            els = p.get("els", {})
            tau = p.get("effort_tranchant", {})
            parts.append(f"<tr><td>PL{i+1}</td><td>{esc(p.get('b_cm'))}×{esc(p.get('h_cm'))}</td><td>{esc(p.get('d_m'))}</td><td>{esc(p.get('mu'))}</td>"
                         f"<td>{esc(p.get('as_retenue_cm2'))}</td><td>{esc(p.get('ferraillage',{}).get('choix',''))}</td>"
                         f"<td>{esc(els.get('sigma_st_mpa'))}/{esc(els.get('sigma_st_lim_mpa'))}</td>"
                         f"<td>{esc(tau.get('tau_u_mpa'))}</td></tr>")
        parts.append("</table>")
        for i, p in enumerate(inp.poutres):
            parts.append(f"<h3>Poutre PL{i+1}</h3>")
            parts.append(f"<div class='formula'>μ = Mu/(b·d²·σbc) ; α = 1,25(1−√(1−2μ)) ; Z = d(1−0,4α) ; As = Mu/(Z·fe/γs) ; As,min = 0,23·b·d·ft28/fe</div>")
            parts.append(dict_table({k: v for k, v in p.items() if k not in ("els", "effort_tranchant", "ferraillage", "audit")}))
            parts.append("<p><b>ELS</b> : " + esc(json.dumps(p.get("els", {}), ensure_ascii=False)) + "</p>")
            parts.append("<p><b>Effort tranchant</b> : " + esc(json.dumps(p.get("effort_tranchant", {}), ensure_ascii=False)) + "</p>")
            parts.append(audit_table(p.get("audit")))
    else:
        parts.append("<p><i>Aucune poutre calculée.</i></p>")

    # ---- 6/7. Semelles
    for key, titre in (("semelles_isolees", "Semelles isolées (méthode des bielles)"),
                       ("semelles_filantes", "Semelles filantes (méthode des bielles)")):
        data = getattr(inp, key)
        parts.append(f"<h2>{6 if key=='semelles_isolees' else 7} — {esc(titre)}</h2>")
        if data:
            parts.append("""<table><tr><th>N°</th><th>Poids (T)</th><th>Mx (T.m)</th><th>My (T.m)</th><th>A (m)</th><th>B (m)</th><th>H (m)</th><th>d (m)</th>
<th>Asx (cm²)</th><th>Asy (cm²)</th><th>Acier X</th><th>Acier Y</th></tr>""")
            for i, s in enumerate(data):
                parts.append(f"<tr><td>S{i+1}</td><td>{esc(s.get('poids_T'))}</td><td>0</td><td>0</td>"
                             f"<td>{esc(s.get('A_m'))}</td><td>{esc(s.get('B_m'))}</td><td>{esc(s.get('H_m'))}</td><td>{esc(s.get('d_m'))}</td>"
                             f"<td>{esc(s.get('asx_cm2'))}</td><td>{esc(s.get('asy_cm2'))}</td>"
                             f"<td>{esc(s.get('acier_x'))}</td><td>{esc(s.get('acier_y'))}</td></tr>")
            parts.append("</table>")
            parts.append("""<div class="formula">σ = N/(A·B) ≤ σsol ; semelle rigide : h ≥ (A−a)/4 ; As = Nu·(A−a)/(8·d·fe/γs) ; poinçonnement : Nu ≤ 0,045·uc·h·fc28/γb</div>""")
            for i, s in enumerate(data):
                parts.append(f"<h3>S{i+1}</h3>")
                parts.append(dict_table({k: v for k, v in s.items() if k not in ("choix_x", "choix_y", "poinconnement", "avertissements", "audit")}))
                parts.append("<p><b>Poinçonnement</b> : " + esc(json.dumps(s.get("poinconnement", {}), ensure_ascii=False)) + "</p>")
                if s.get("avertissements"):
                    for a in s["avertissements"]:
                        parts.append(f"<p class='ko'>⚠ {esc(a)}</p>")
                parts.append(audit_table(s.get("audit")))
        else:
            parts.append("<p><i>Aucune semelle calculée.</i></p>")

    # ---- 8. Voiles
    parts.append("<h2>8 — Voiles de contreventement</h2>")
    if inp.voiles:
        parts.append("""<table><tr><th>Repère</th><th>L (m)</th><th>ép. (cm)</th><th>Mode</th><th>σmax (MPa)</th><th>σmin</th><th>τu (MPa)</th><th>As rive (cm²)</th></tr>""")
        for i, v in enumerate(inp.voiles):
            parts.append(f"<tr><td>V{i+1}</td><td>{esc(v.get('longueur_m'))}</td><td>{esc(v.get('ep_cm'))}</td><td>{esc(v.get('mode'))}</td>"
                         f"<td>{esc(v.get('sigma_max_mpa'))}</td><td>{esc(v.get('sigma_min_mpa'))}</td>"
                         f"<td>{esc(v.get('tau_u_mpa'))}</td><td>{esc(v.get('as_rive_cm2'))}</td></tr>")
        parts.append("</table>")
        for i, v in enumerate(inp.voiles):
            parts.append(f"<h3>Voile V{i+1}</h3>")
            parts.append(dict_table({k: v for k, v in v.items() if k not in ("audit", "rivet", "rive", "horiz", "attention")}))
            for a in (v.get("attention") or []):
                parts.append(f"<p class='small'>⚠ {esc(a)}</p>")
            parts.append(audit_table(v.get("audit")))
    else:
        parts.append("<p><i>Aucun voile calculé.</i></p>")

    # ---- 9. Synthèse & alertes
    parts.append("<h2>9 — Synthèse arithmétique et alertes</h2>")
    if alertes:
        for a in alertes:
            parts.append(f"<p class='ko'>■ {esc(a)}</p>")
    else:
        parts.append("<p class='ok'>Aucune incohérence arithmétique détectée par l'audit automatique (Qté × PU = Total, recalculs de formules).</p>")
    if avertissements:
        parts.append("<h3>Avertissements et points de vigilance (à revoir par l'ingénieur)</h3>")
        for a in avertissements:
            parts.append(f"<p class='note' style='font-size:9.5pt'>▪ {esc(a)}</p>")

    # ---- 10. Conclusion
    parts.append(f"""<h2>10 — Conclusion</h2>
<p>Les éléments présentés ci-dessus ont été dimensionnés selon les hypothèses des articles 1 à 8 et les références
normatives citées. Les valeurs annotées de la mention « ALERTE ECART ARITHMETIQUE » éventuelle doivent être
revues avant émission des plans d'exécution. La note ne dispense pas de la vérification finale par l'ingénieur
chargé du projet (art. B.8.5 BAEL ; art. 7.3 RPS pour les zones critiques ND2/ND3).</p>
<hr class="gold">
<table class="sig"><tr><td style="width:50%">
<p><b>{esc(bur.get('nom',''))}</b><br>{esc(bur.get('adresse',''))}</p>
<p style="margin-top:48px">________________________<br>Le {esc(bur.get('ingenieur', 'Ingénieur Structure'))}</p>
</td><td><div class="box" style="margin:0"><b>CACHET / SIGNATURE</b><br><br><br><br></div></td></tr></table>
<p class="footer-note">Document généré par Bénayfacile le {now} — Sources : BAEL 91 rév. 99 (DTU P18-702), RPS 2000 v2011.
En cas de divergence avec les textes officiels, ces derniers font foi.</p>""")

    parts.append("</body></html>")
    return "".join(parts)


@app.get("/health")
def health():
    return {"service": "report", "status": "ok"}

@app.post("/note", response_class=HTMLResponse)
def note(inp: NoteInput):
    return HTMLResponse(content=build_note(inp))

@app.post("/note/save")
def note_save(inp: NoteInput):
    h = build_note(inp)
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = OUT / f"note_de_calcul_{now}.html"
    chemin.write_text(h, encoding="utf-8")
    return {"fichier": chemin.name, "octets": chemin.stat().st_size}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8004)
