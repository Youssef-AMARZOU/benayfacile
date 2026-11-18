/* Bénayfacile — tableau de bord BET (vanilla JS) */
'use strict';
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const state = {
  project: { projet: 'Immeuble R+4 — Casablanca', client: 'SARL Exemple', site: 'Casablanca, Maroc', indice: 'A' },
  robot: null,
  sismique: null,
  poteaux: [], poutres: [], semelles_isolees: [], semelles_filantes: [], voiles: [],
  bureau: {},
};

const MODULES = [
  { id: 'projet', label: 'Projet Robot', groupe: 'Projet', ref: 'Tout le modèle' },
  { id: 'poteau', label: 'Poteau', groupe: 'Éléments', ref: 'BAEL 91 · B.8.4' },
  { id: 'poutre', label: 'Poutre', groupe: 'Éléments', ref: 'BAEL 91 · flexion simple' },
  { id: 'semelle', label: 'Semelles isolées', groupe: 'Éléments', ref: 'Méthode des bielles' },
  { id: 'semelle_filante', label: 'Semelles filantes', groupe: 'Éléments', ref: 'Méthode des bielles' },
  { id: 'voile', label: 'Voiles', groupe: 'Éléments', ref: 'BAEL B.8.4' },
  { id: 'sismique', label: 'Vérification sismique', groupe: 'Bâtiment', ref: 'RPS 2000 v2011' },
  { id: 'synthese', label: 'Synthèse de calcul', groupe: 'Livrables', ref: 'Note + plan DXF' },
  { id: 'bureau', label: 'Votre bureau', groupe: 'Réglages', ref: 'Page de garde et cartouche' },
];

/* Glyphes : la section de chaque élément, aciers en rouge (classe .acier / .acier-l). */
const GLYPHES = {
  projet: '<path d="M4 23V9l9-5 9 5v14"/><path d="M4 23h18 M4 16h18 M4 9.5h18 M13 4.5V23"/><circle class="acier" cx="4" cy="23" r="1.6"/><circle class="acier" cx="13" cy="23" r="1.6"/><circle class="acier" cx="22" cy="23" r="1.6"/>',
  poteau: '<rect x="5" y="5" width="16" height="16"/><rect x="8" y="8" width="10" height="10" stroke-width="1" stroke-dasharray="1.6 1.3"/><circle class="acier" cx="9" cy="9" r="1.7"/><circle class="acier" cx="17" cy="9" r="1.7"/><circle class="acier" cx="9" cy="17" r="1.7"/><circle class="acier" cx="17" cy="17" r="1.7"/>',
  poutre: '<rect x="2" y="8" width="22" height="8"/><path class="acier-l" d="M4 13.6h18"/><path d="M5 16l-2.2 4h4.4z M21 16l-2.2 4h4.4z"/>',
  semelle: '<path d="M10.5 2.5v9 M15.5 2.5v9"/><path d="M10.5 11.5 3 15v6h20v-6l-7.5-3.5"/><path class="acier-l" d="M5 19h16"/>',
  semelle_filante: '<rect x="2" y="7" width="22" height="12"/><rect x="2" y="10.5" width="22" height="5" stroke-width="1"/><path class="acier-l" d="M6 7v12 M11 7v12 M16 7v12 M21 7v12" stroke-dasharray="0" opacity=".9"/>',
  voile: '<rect x="8" y="2" width="10" height="22"/><path class="acier-l" d="M10.5 3.5v19 M15.5 3.5v19"/><path d="M8.5 8h9 M8.5 13h9 M8.5 18h9" stroke-width=".9"/>',
  sismique: '<path d="M2 19.5h22"/><path d="M8 19.5V6h10v13.5 M8 11h10 M8 15.5h10"/><path class="acier-l" d="M2 23.2c1.6-1.8 2.9 1.8 4.5 0s2.9 1.8 4.5 0 2.9 1.8 4.5 0 2.9 1.8 4.5 0 1.9 1.2 2 0"/>',
  synthese: '<path d="M6 2h10l5 5v17H6z"/><path d="M16 2v5h5"/><path class="acier-l" d="M9 12h9"/><path d="M9 15.5h9 M9 19h6"/>',
  bureau: '<rect x="2" y="6" width="22" height="14"/><path d="M2 12.5h22 M15 6v14 M15 16.2h9"/><path class="acier-l" d="M4.5 9.2h8"/>',
};
const glyphe = (id, cls = 'glyphe') => `<svg class="${cls}" viewBox="0 0 26 26" aria-hidden="true">${GLYPHES[id] || ''}</svg>`;
function vide(id, texte = 'Saisissez les données puis lancez le calcul.') {
  return `<div class="vide">${glyphe(id, 'glyphe')}<span>${texte}</span></div>`;
}

/* ---------- helpers ---------- */
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const txt = await r.text();
  let body; try { body = JSON.parse(txt); } catch { body = txt; }
  if (!r.ok) throw new Error((body && body.detail) ? JSON.stringify(body.detail) : (typeof body === 'string' ? body : JSON.stringify(body)));
  return body;
}
function field(id, label, value, type = 'number', step = 'any') {
  return `<div class="field"><label for="${id}">${label}</label>
    <input id="${id}" type="${type}" step="${step}" value="${esc(value)}"></div>`;
}
function select(id, label, options, value) {
  const opts = options.map(([v, l]) => `<option value="${v}" ${v === value ? 'selected' : ''}>${l}</option>`).join('');
  return `<div class="field"><label for="${id}">${label}</label><select id="${id}">${opts}</select></div>`;
}
function row2(a, b) { return `<div class="row">${a}${b}</div>`; }
const VERDICT = { 'OK': 'ok', 'OUI': 'ok', 'NON': 'ko', 'NON VÉRIFIÉ': 'ko' };
/* items : [libellé, valeur, clé?] — « clé » met la ligne en évidence (résultat principal). */
function kv(items) {
  return `<div class="kv">${items.map(([k, v, cle]) => {
    const verdict = VERDICT[String(v ?? '').trim()] || '';
    return `<div class="item${cle ? ' cle' : ''}"><span class="k">${esc(k)}</span><span class="fil"></span><span class="v ${verdict}" title="${esc(v)}">${esc(v ?? '—')}</span></div>`;
  }).join('')}</div>`;
}
function renderRaw(r) { return `<details><summary>Détail brut (JSON)</summary><pre class="raw">${esc(JSON.stringify(r, null, 2))}</pre></details>`; }
function warns(list) { return (list || []).map(w => `<p class="warn">${esc(w)}</p>`).join(''); }
function notes(list) { return (list || []).map(w => `<p class="note">${esc(w)}</p>`).join(''); }
function spinner(el) { el.innerHTML = '<p class="small"><span class="spinner"></span>Calcul en cours…</p>'; }

/* ---------- santé des services ---------- */
async function checkHealth() {
  try {
    const h = await api('/health');
    const entrees = Object.entries(h.services);
    const ko = entrees.filter(([, v]) => !String(v).startsWith('ok'));
    const voyants = entrees.map(([k, v]) =>
      `<span class="voyant ${String(v).startsWith('ok') ? '' : 'ko'}" title="${esc(k)} : ${esc(v)}"></span>`).join('');
    $('health').innerHTML = `<span class="voyants">${voyants}</span>` + (ko.length
      ? `<span class="etat-ko">Service indisponible : ${ko.map(([k]) => esc(k)).join(', ')}</span>`
      : '<span>Moteur de calcul prêt</span>');
  } catch (e) {
    $('health').innerHTML = '<span class="voyants"><span class="voyant ko"></span></span><span class="etat-ko">Passerelle injoignable. Relancez Bénayfacile.</span>';
  }
}

/* ---------- cartouche (bloc-titre) ---------- */
function renderCartouche() {
  const el = $('cartouche'); if (!el) return;
  const p = state.project;
  el.innerHTML = `<div class="c-projet"><div class="c-k">Projet</div><div class="c-v">${esc(p.projet || 'Sans titre')}</div></div>
    <div><div class="c-k">Maître d'ouvrage</div><div class="c-v" title="${esc(p.client)}">${esc(p.client || '—')}</div></div>
    <div class="c-indice"><div class="c-k">Indice</div><div class="c-v">${esc(p.indice || '—')}</div></div>
    <div class="c-foi">Les textes officiels BAEL et RPS font foi.</div>`;
}

/* ---------- synthèse ---------- */
function synthesisPayload() {
  return {
    projet: state.project.projet, client: state.project.client, site: state.project.site,
    indice: state.project.indice,
    robot: state.robot || undefined, sismique: state.sismique || undefined,
    poteaux: state.poteaux, poutres: state.poutres,
    semelles_isolees: state.semelles_isolees, semelles_filantes: state.semelles_filantes,
    voiles: state.voiles, bureau: state.bureau,
  };
}
function addToSynthesis(type, item) {
  state[type].push(item);
  renderSynthesis();
  toast(`Élément ajouté à la synthèse (${type}).`);
}
function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast'; t.setAttribute('role', 'status');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2600);
}
function renderSynthesis() {
  const box = $('synthesis-items'); if (!box) return;
  const groups = [
    ['poteaux', 'Poteaux'], ['poutres', 'Poutres'],
    ['semelles_isolees', 'Semelles isolées'], ['semelles_filantes', 'Semelles filantes'], ['voiles', 'Voiles'],
  ];
  let html = '';
  if (state.robot) html += `<li><span><b>Modèle Robot</b> — ${esc(state.robot.nom)} <span class="badge">${esc(state.robot.mode || 'simulation')}</span></span><button data-del="robot">✕</button></li>`;
  if (state.sismique) html += `<li><span><b>Vérification sismique</b> — F = ${esc(state.sismique.F_base_kn)} kN · T = ${esc(state.sismique.T_s)} s <span class="badge">RPS 2000 v2011</span></span><button data-del="sismique">✕</button></li>`;
  for (const [key, label] of groups) {
    state[key].forEach((item, i) => {
      let desc = '';
      if (key === 'poteaux') desc = `${item.a_cm}×${item.b_cm} cm — Nu ${item.nu_kn} kN — ${item.ferraillage?.choix || ''}`;
      else if (key === 'poutres') desc = `b×h ${item.b_cm}×${item.h_cm} cm — ${item.mu_knm != null ? `Mu ${item.mu_knm} kN.m` : `μ ${item.mu}`} — ${item.ferraillage?.choix || ''}`;
      else if (key === 'voiles') desc = `L = ${item.longueur_m} m — σmax ${item.sigma_max_mpa} MPa`;
      else desc = `A ${item.A_m} × B ${item.B_m} — H ${item.H_m} m — ${item.acier_x} / ${item.acier_y}`;
      const titre = item.nom ? `${item.nom}${item.niveau ? ' · ' + item.niveau : ''}` : `${label} #${i + 1}`;
      html += `<li><span><b>${esc(titre)}</b> — ${esc(desc)}</span><button data-del="${key}" data-idx="${i}">✕</button></li>`;
    });
  }
  box.innerHTML = html || '<li><span class="small">Aucun élément pour l’instant. Calculez un élément, puis « Ajouter à la synthèse ». Ou chargez le scénario démo R+4.</span></li>';
  box.querySelectorAll('button[data-del]').forEach(btn => btn.addEventListener('click', () => {
    const k = btn.dataset.del;
    if (k === 'robot') state.robot = null;
    else if (k === 'sismique') state.sismique = null;
    else state[k].splice(+btn.dataset.idx, 1);
    renderSynthesis();
  }));
}

/* ============ MODULE: PROJET ROBOT (tout le modèle) ============ */
const FAMILLES = [
  { cle: 'poteaux', label: 'Poteaux', synthese: 'poteaux',
    cols: [['Niveau', l => l.niveau], ['Section', l => dim(l.entree.a_cm, l.entree.b_cm)], ['Nu (kN)', l => l.entree.nu_kn, 'n'],
           ['Nu/Nu,lim', l => l.resultat?.nu_rapport, 'n'], ['As (cm²)', l => l.resultat?.as_calculee_cm2, 'n'], ['Ferraillage', l => l.resultat?.ferraillage?.choix]] },
  { cle: 'poutres', label: 'Poutres', synthese: 'poutres',
    cols: [['Niveau', l => l.niveau], ['Section', l => dim(l.entree.b_cm, l.entree.h_cm)], ['Portée (m)', l => l.entree.portee_m, 'n'],
           ['Mu (kN.m)', l => l.entree.mu_knm, 'n'], ['As (cm²)', l => l.resultat?.as_retenue_cm2, 'n'], ['Ferraillage', l => l.resultat?.ferraillage?.choix]] },
  { cle: 'semelles', label: 'Semelles', synthese: 'semelles_isolees',
    cols: [['Poteau', l => dim(l.entree.a_poteau_cm, l.entree.b_poteau_cm)], ['Ns (kN)', l => l.entree.ns_kn, 'n'], ['Nu (kN)', l => l.entree.nu_kn, 'n'],
           ['A × B (m)', l => l.resultat ? `${l.resultat.A_m} × ${l.resultat.B_m}` : null, 'n'], ['H (m)', l => l.resultat?.H_m, 'n'],
           ['Acier X / Y', l => l.resultat ? `${l.resultat.acier_x} / ${l.resultat.acier_y}` : null]] },
  { cle: 'voiles', label: 'Voiles', synthese: 'voiles',
    cols: [['Niveau', l => l.niveau], ['L × e', l => l.entree.longueur_m != null ? `${l.entree.longueur_m} m × ${l.entree.ep_cm ?? '?'} cm` : null],
           ['N (kN)', l => l.entree.n_kn, 'n'], ['M (kN.m)', l => l.entree.m_knm, 'n'], ['σmax (MPa)', l => l.resultat?.sigma_max_mpa, 'n'],
           ['As rive (cm²)', l => l.resultat?.as_rive_cm2, 'n']] },
];
const STATUTS = { verifie: 'Vérifié', a_revoir: 'À revoir', incomplet: 'Incomplet', erreur: 'Erreur' };
function dim(a, b) { return a != null && b != null ? `${a} × ${b}` : null; }

function tabProjet() {
  const vue = { modele: null, lot: null, famille: 'poteaux', aRevoir: false };
  const fissOpts = [['peu_prejudiciable', 'Peu préjudiciable'], ['prejudiciable', 'Préjudiciable'], ['tres_prejudiciable', 'Très préjudiciable']];
  return {
    html: `<h1 class="module-title">Projet Robot <small>Lecture du modèle Robot Structural Analysis et calcul de tous les éléments : poteaux, poutres, semelles, voiles (BAEL 91 rév. 99)</small></h1>
<div class="grid pile"><div class="card projet-commandes">
  <div class="etape">
    <h2>Modèle</h2>
    <div class="actions"><button class="btn" id="rb-lire">Lire le modèle Robot</button></div>
    <div class="result" id="rb-modele"><p class="small">Ouvrez le projet dans Robot, puis lisez-le. Sans Robot, Bénayfacile charge le bâtiment R+4 de démonstration.</p></div>
  </div>
  <div class="etape">
    <h2>Matériaux et sol</h2>
    ${row2(field('rb-fc', "fc28 (MPa)", 25), field('rb-fe', "fe (MPa)", 500))}
    ${row2(field('rb-sol', "σsol admissible (bar)", 2.0), select('rb-fis', "Fissuration", fissOpts, 'prejudiciable'))}
    <div class="actions">
      <button class="btn gold" id="rb-calc" disabled>Calculer tout le modèle</button>
      <button class="btn ghost small" id="rb-add" disabled>Envoyer à la synthèse</button>
    </div>
  </div>
</div>
<div class="card"><h2>Résultats</h2><div class="result" id="rb-res">${vide('projet', 'Lisez le modèle, puis lancez le calcul : chaque élément est dimensionné et vérifié.')}</div></div></div>`,
    init() {
      $('rb-lire').addEventListener('click', async () => {
        const el = $('rb-modele'); el.innerHTML = '<p class="small"><span class="spinner"></span>Lecture du modèle…</p>';
        try {
          const r = await api('/api/robot/model');
          vue.modele = r; vue.lot = null;
          state.robot = r; renderSynthesis();
          const o = r.ossature;
          if (!o) { el.innerHTML = `<p class="warn">Le modèle ne contient pas d'ossature lisible.</p>` + notes(r.notes); return; }
          const source = r.mode === 'robot' ? 'Robot (lecture COM)' : 'Démonstration R+4 (Robot non détecté)';
          el.innerHTML = kv([
            ['Source', source], ['Niveaux', o.niveaux.join(', ')],
            ['Poteaux', o.resume.poteaux, true], ['Poutres', o.resume.poutres, true],
            ['Semelles', o.resume.semelles, true], ['Voiles', o.resume.voiles, true],
          ]) + notes(o.remarques) + `<details><summary>Hypothèses de la ${r.mode === 'robot' ? 'lecture' : 'simulation'}</summary>${notes(o.hypotheses)}</details>`;
          $('rb-calc').disabled = false; $('rb-add').disabled = true;
          const total = o.resume.poteaux + o.resume.poutres + o.resume.semelles + o.resume.voiles;
          $('rb-res').innerHTML = vide('projet', `${total} éléments prêts. Lancez « Calculer tout le modèle ».`);
        } catch (e) { el.innerHTML = `<p class="warn">Lecture impossible : ${esc(e.message)}</p>`; }
      });

      $('rb-calc').addEventListener('click', async () => {
        const o = vue.modele?.ossature; if (!o) return;
        const resEl = $('rb-res'); spinner(resEl);
        try {
          const payload = { poteaux: o.poteaux, poutres: o.poutres, semelles: o.semelles, voiles: o.voiles,
            materiaux: { fc28_mpa: +$('rb-fc').value, fe_mpa: +$('rb-fe').value, sigma_sol_bar: +$('rb-sol').value, fissuration: $('rb-fis').value } };
          vue.lot = await api('/api/engine/lot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          vue.famille = FAMILLES.find(f => vue.lot[f.cle].some(l => l.statut !== 'verifie'))?.cle || 'poteaux';
          dessiner();
          $('rb-add').disabled = false;
        } catch (e) { resEl.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });

      $('rb-add').addEventListener('click', () => {
        if (!vue.lot) return;
        let n = 0;
        for (const f of FAMILLES) {
          state[f.synthese] = vue.lot[f.cle].filter(l => l.resultat).map(l => ({
            ...l.resultat, nom: l.nom, niveau: l.niveau,
            ...(f.cle === 'poteaux' ? { nu_kn: l.entree.nu_kn, mx_knm: l.entree.mx_knm, my_knm: l.entree.my_knm } : {}),
            ...(f.cle === 'poutres' ? { mu_knm: l.entree.mu_knm } : {}),
          }));
          n += state[f.synthese].length;
        }
        renderSynthesis();
        toast(`${n} éléments envoyés à la synthèse.`);
      });

      $('rb-res').addEventListener('click', (e) => {
        const b = e.target.closest('[data-famille]');
        if (b) { vue.famille = b.dataset.famille; dessiner(); }
      });
      $('rb-res').addEventListener('change', (e) => {
        if (e.target.id === 'rb-filtre') { vue.aRevoir = e.target.checked; dessiner(); }
      });

      function dessiner() {
        const lot = vue.lot, s = lot.resume;
        const fam = FAMILLES.find(f => f.cle === vue.famille);
        const lignes = lot[fam.cle].filter(l => !vue.aRevoir || l.statut !== 'verifie');
        const onglets = FAMILLES.map(f => {
          const pb = lot[f.cle].filter(l => l.statut !== 'verifie').length;
          return `<button class="onglet ${f.cle === vue.famille ? 'actif' : ''}" data-famille="${f.cle}">${f.label} <span class="compte">${lot[f.cle].length}</span>${pb ? `<span class="alerte" title="${pb} à revoir">${pb}</span>` : ''}</button>`;
        }).join('');
        const tete = `<tr><th>Élément</th>${fam.cols.map(([t, , n]) => `<th class="${n ? 'num' : ''}">${t}</th>`).join('')}<th>État</th></tr>`;
        const corps = lignes.map(l => `<tr class="st-${l.statut}"><td><b>${esc(l.nom)}</b></td>${fam.cols.map(([, f, n]) => `<td class="${n ? 'num' : ''}">${esc(f(l) ?? '—')}</td>`).join('')}
          <td><span class="etat ${l.statut}">${STATUTS[l.statut]}</span>${l.problemes?.length ? `<div class="probleme">${esc(l.problemes.join(' ; '))}</div>` : ''}</td></tr>`).join('');
        $('rb-res').innerHTML = `<div class="bilan">
            <div><span class="bilan-n">${s.total}</span> éléments</div>
            <div class="ok"><span class="bilan-n">${s.verifie}</span> vérifiés</div>
            <div class="${s.a_revoir ? 'ko' : ''}"><span class="bilan-n">${s.a_revoir}</span> à revoir</div>
            <div class="${s.incomplet + s.erreur ? 'ko' : ''}"><span class="bilan-n">${s.incomplet + s.erreur}</span> incomplets</div>
          </div>
          <div class="onglets">${onglets}<label class="filtre"><input type="checkbox" id="rb-filtre" ${vue.aRevoir ? 'checked' : ''}> À revoir seulement</label></div>
          ${lignes.length ? `<div class="table-defile"><table class="lot">${tete}${corps}</table></div>` : '<p class="small" style="padding:18px 0">Aucun élément à revoir dans cette famille.</p>'}`;
      }
    }
  };
}

/* ============ MODULE: POTEAU ============ */
function tabPoteau() {
  return {
    html: `<h1 class="module-title">Poteau <small>BAEL 91 rév. 99 — B.8.4,1 compression centrée (Nu,lim = α·[Br·fc28/0,9γb + A·fe/γs]) + flexion composée numérique</small></h1>
<div class="grid"><div class="card"><h2>Données</h2>
${row2(field('p-a', "a (cm)", 30), field('p-b', "b (cm)", 30))}
${row2(field('p-lf', "lf — longueur de flambement (m)", 3.0), field('p-nu', "Nu — effort normal ELU (kN)", 950))}
${row2(field('p-mx', "Mx (kN.m)", 25), field('p-my', "My (kN.m)", 10))}
${row2(field('p-fc', "fc28 (MPa)", 25), field('p-fe', "fe (MPa)", 500))}
${field('p-enrobage', "Enrobage (mm)", 30)}
<div class="actions"><button class="btn gold" id="p-calc">Calculer</button>
<button class="btn ghost small" id="p-add" disabled>Ajouter à la synthèse</button></div>
</div>
<div class="card"><h2>Résultat</h2><div class="result" id="p-res">${vide('poteau')}</div></div></div>`,
    init() {
      $('p-calc').addEventListener('click', async () => {
        const payload = { a_cm: +$('p-a').value, b_cm: +$('p-b').value, lf_m: +$('p-lf').value,
          nu_kn: +$('p-nu').value, mx_knm: +$('p-mx').value, my_knm: +$('p-my').value,
          fc28_mpa: +$('p-fc').value, fe_mpa: +$('p-fe').value, cover_mm: +$('p-enrobage').value };
        const resEl = $('p-res'); spinner(resEl);
        try {
          const r = await api('/api/engine/poteau', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          const fc = r.flexion_composee || {};
          resEl.innerHTML = kv([
            ['λ (lf/i)', r.lambda], ['α', r.alpha], ['Nu,lim', r.nu_lim_kn_avec_as_fournie + ' kN'],
            ['Rapport Nu/Nu,lim', r.nu_rapport, true], ['As calc.', r.as_calculee_cm2 + ' cm²'],
            ['Ferraillage', r.ferraillage?.choix, true], ['MRd (flexion composée)', (fc.moment_capable_knm ?? '—') + ' kN.m'],
            ['Taux util. moment', fc.taux_utilisation_moment ?? '—'],
          ]) + notes(r.notes) + warns(r.warn ? [r.warn] : []) + renderRaw(r);
          $('p-add').disabled = false;
          $('p-add').onclick = () => addToSynthesis('poteaux', { ...r, nu_kn: payload.nu_kn, mx_knm: payload.mx_knm, my_knm: payload.my_knm });
        } catch (e) { resEl.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });
    }
  };
}

/* ============ MODULE: SISMIQUE ============ */
function tabSismique() {
  const siteOpts = [['S1', 'S1 — Rocher / sol ferme < 30 m (S=1.0)'], ['S2', 'S2 — Sol ferme ≥ 30 m / meuble < 30 m (S=1.2)'],
    ['S3', 'S3 — Sol meuble ≥ 15 m / mou < 10 m (S=1.4)'], ['S4', 'S4 — Sol mou ≥ 10 m (S=1.8)'], ['S5', 'S5 — Conditions spéciales (à justifier)']];
  const classeOpts = [['classe_I', 'Classe I — bâtiments stratégiques / grande importance (I=1.3)'],
    ['classe_II', 'Classe II — grand public (I=1.2)'], ['classe_III', 'Classe III — bâtiments ordinaires (I=1.0)']];
  const sysOpts = [['portiques_ba', 'Portiques en béton armé'], ['voile_portique', 'Voile + Portique'], ['voile', 'Voiles'], ['voiles_couples', 'Voiles couplés'],
    ['acier_noeuds_rigides', 'Acier — portiques à nœuds rigides'], ['ossature_contreventee', 'Ossature contreventée (acier)']];
  const ducOpts = [['ND1', 'ND1 — faible ductilité'], ['ND2', 'ND2 — ductilité moyenne'], ['ND3', 'ND3 — grande ductilité']];
  const usageOpts = [['habitation_admin', "Habitation / administratif (ψ=0.20)"], ['public_periodique', "Usage périodique public (ψ=0.30)"],
    ['restaurants_salles_classe', "Restaurants / salles de classe (ψ=0.40)"], ['longue_duree', "Longue durée — entrepôts… (ψ=1.00)"]];
  return {
    html: `<h1 class="module-title">Vérification Sismique <small>RPS 2000 — version 2011 · approche statique équivalente (F = υ·S·D·I·W/K, eq. 6.1)</small></h1>
<div class="grid"><div class="card"><h2>Modèle Robot</h2>
<button class="btn" id="s-robot">Charger le modèle Robot (simulation si Robot absent)</button>
<div class="result" id="s-robot-res" style="margin-top:8px"></div>
<h2 class="sous">Données sismiques</h2>
${row2(field('s-h', "H — hauteur totale (m)", 15), field('s-l', "L — longueur contreventement (m)", 12))}
${row2(field('s-g', "G — charges permanentes (kN)", 3800), field('s-q', "Q — charges d'exploitation (kN)", 1200))}
${select('s-usage', "Usage (ψ)", usageOpts, 'habitation_admin')}
${row2(select('s-zv', "Zone de vitesse υ (Tableau 5.1)", [['0','0 — 0.00 m/s'],['1','1 — 0.07 m/s'],['2','2 — 0.10 m/s'],['3','3 — 0.13 m/s'],['4','4 — 0.17 m/s']], '3'),
       select('s-rapport', "Rapport Za / Zv (Fig. 5.3 vs Fig. 5.2)", [['za_gt_zv','Za > Zv'],['za_eq_zv','Za = Zv'],['za_lt_zv','Za < Zv']], 'za_eq_zv'))}
${row2(select('s-site', "Site (Tableau 5.2)", siteOpts, 'S2'), select('s-classe', "Classe (Tableau 3.1)", classeOpts, 'classe_II'))}
${row2(select('s-sys', "Système de contreventement (Tableau 3.3)", sysOpts, 'portiques_ba'), select('s-duc', "Ductilité", ducOpts, 'ND1'))}
${row2(select('s-tmeth', "Évaluation de T", [['portique','Formule 6.4 — 0.075·H¾'],['acier_noeuds_rigides','Formule 6.5 — 0.085·H¾'],['autre','Formule 6.6 — 0.09·H/√L'],['manuel','T manuelle (Robot)']], 'portique'),
       field('s-tman', "T manuelle (s) — si « manuelle »", 0.62))}
${field('s-amort', "Amortissement (%)", 5.0)}
<div class="actions"><button class="btn gold" id="s-calc">Calculer la force sismique</button>
<button class="btn ghost small" id="s-add" disabled>Ajouter à la synthèse</button></div>
</div>
<div class="card"><h2>Résultat</h2><div class="result" id="s-res">${vide('sismique', 'Chargez le modèle Robot ou saisissez les données, puis calculez la force sismique.')}</div></div></div>`,
    init() {
      $('s-robot').addEventListener('click', async () => {
        const el = $('s-robot-res'); el.innerHTML = '<span class="spinner"></span> lecture du modèle…';
        try {
          const r = await api('/api/robot/model');
          el.innerHTML = kv([
            ['Modèle', r.nom], ['Mode', r.mode], ['Niveaux', r.nb_niveaux],
            ['G (kN)', r.masses?.G_kn], ['Q (kN)', r.masses?.Q_kn], ['W (kN)', r.masses?.W_kn],
            ['T1 (s)', r.modal?.T1_s], ['Masse participante (%)', r.modal?.masse_participante_pct],
          ]) + `<p class="small">${esc((r.notes || []).join(' '))}</p>`;
          if (r.masses) { $('s-g').value = r.masses.G_kn; $('s-q').value = r.masses.Q_kn; }
          state.robot = r; renderSynthesis();
        } catch (e) { el.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });
      $('s-calc').addEventListener('click', async () => {
        const payload = { hauteur_m: +$('s-h').value, longueur_contreventement_m: +$('s-l').value,
          g_kn: +$('s-g').value, q_kn: +$('s-q').value, usage: $('s-usage').value,
          zone_vitesse: +$('s-zv').value, rapport_za_zv: $('s-rapport').value, site: $('s-site').value,
          classe: $('s-classe').value, systeme: $('s-sys').value, ductilite: $('s-duc').value,
          periode_methode: $('s-tmeth').value, t_manuel_s: +$('s-tman').value, amortissement_pct: +$('s-amort').value,
          niveaux: state.robot?.niveaux?.map(n => ({ nom: n.nom, w_kn: n.w_kn, h_m: n.altitude_m })) };
        const resEl = $('s-res'); spinner(resEl);
        try {
          const r = await api('/api/engine/sismique', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          resEl.innerHTML = kv([
            ['υ (m/s)', r.nu_m_s], ['S', r.S], ['I', r.I], ['K', r.K], ['ψ', r.psi], ['W (kN)', r.W_kn],
            ['T (s)', r.T_s], ['D', r.D], ['F — effort à la base (kN)', r.F_base_kn, true], ['Ft (kN)', r.Ft_kn], ['ω (modes supérieurs)', r.omega_modes_superieurs],
          ]) + notes(r.hypotheses) + (r.Fn?.length ? `<h3>Répartition verticale</h3><table><tr><th>Niveau</th><th>Wi</th><th>hn</th><th>Fn (kN)</th></tr>${r.Fn.map(n => `<tr><td>${esc(n.niveau)}</td><td>${n.Wn_kn}</td><td>${n.hn_m}</td><td>${n.Fn_kn}</td></tr>`).join('')}</table>` : '') + renderRaw(r);
          $('s-add').disabled = false;
          $('s-add').onclick = () => { state.sismique = r; renderSynthesis(); toast('Vérification sismique ajoutée à la synthèse.'); };
        } catch (e) { resEl.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });
    }
  };
}

/* ============ MODULE: SEMELLES ============ */
function tabSemelle(filante) {
  const p = filante ? 'sf' : 'si';
  const title = filante ? 'Semelles Filantes' : 'Semelles Isolées';
  const normes = "méthode des bielles (semelle rigide, h ≥ (A−a)/4) — As = Nu·(A−a)/(8·d·σs)" + (filante ? " — par mètre linéaire" : "");
  return {
    html: `<h1 class="module-title">${esc(title)} <small>BAEL/BE — ${esc(normes)}</small></h1>
<div class="grid"><div class="card"><h2>Données</h2>
${row2(field(`${p}-ns`, "Ns — effort service (kN)", 950), field(`${p}-nu`, "Nu — ELU (optionnel, défaut 1.5·Ns) (kN)", ''))}
${row2(field(`${p}-a`, "Poteau/voile a (cm)", 30), field(`${p}-b`, "Poteau/voile b (cm)", 30))}
${row2(field(`${p}-sig`, "σsol admissible (bar)", 2.0), field(`${p}-fc`, "fc28 (MPa)", 25))}
${filante ? '' : row2(field(`${p}-mx`, "Mx (kN.m)", 0), field(`${p}-my`, "My (kN.m)", 0))}
${field(`${p}-enrobage`, "Enrobage (mm)", 50)}
<div class="actions"><button class="btn gold" id="${p}-calc">Calculer</button>
<button class="btn ghost small" id="${p}-add" disabled>Ajouter à la synthèse</button></div>
</div>
<div class="card"><h2>Résultat</h2><div class="result" id="${p}-res">${vide(filante ? 'semelle_filante' : 'semelle')}</div></div></div>`,
    init() {
      $(`${p}-calc`).addEventListener('click', async () => {
        const nuRaw = $(`${p}-nu`).value;
        const payload = { ns_kn: +$(`${p}-ns`).value, a_poteau_cm: +$(`${p}-a`).value, b_poteau_cm: +$(`${p}-b`).value,
          sigma_sol_bar: +$(`${p}-sig`).value, fc28_mpa: +$(`${p}-fc`).value, fe_mpa: 500, cover_mm: +$(`${p}-enrobage`).value };
        if (nuRaw !== '') payload.nu_kn = +nuRaw;
        if (!filante) { payload.Mx_knm = +$(`${p}-mx`).value; payload.My_knm = +$(`${p}-my`).value; }
        const resEl = $(`${p}-res`); spinner(resEl);
        try {
          const url = filante ? '/api/engine/semelle_filante' : '/api/engine/semelle';
          const r = await api(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          resEl.innerHTML = kv([
            ['A (m)', r.A_m, true], ['B (m)', r.B_m, true], ['H (m)', r.H_m], ['d (m)', r.d_m],
            ['Poids (T)', r.poids_T], ['σmax (bar)', r.sigma_max_bar], ['σmin (bar)', r.sigma_min_bar],
            ['Asx (cm²)', r.asx_cm2], ['Asy (cm²)', r.asy_cm2], ['Acier X', r.acier_x], ['Acier Y', r.acier_y],
            ['Poinçonnement', r.poinconnement.ok ? 'OK' : 'NON VÉRIFIÉ', true],
          ]) + (filante ? kv([['As par mètre linéaire', r.as_cm2_par_ml + ' cm²/ml']]) : '') +
            warns(r.avertissements) + renderRaw(r);
          $(`${p}-add`).disabled = false;
          $(`${p}-add`).onclick = () => addToSynthesis(filante ? 'semelles_filantes' : 'semelles_isolees', { ...r });
        } catch (e) { resEl.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });
    }
  };
}

/* ============ MODULE: POUTRE ============ */
function tabPoutre() {
  return {
    html: `<h1 class="module-title">Poutre <small>BAEL 91 rév. 99 — flexion simple ELU (diagramme rectangulaire 0,8 yu) + ELS (n=15) + effort tranchant</small></h1>
<div class="grid"><div class="card"><h2>Données</h2>
${row2(field('pt-b', "b (cm)", 25), field('pt-h', "h (cm)", 50))}
${row2(field('pt-mu', "Mu (kN.m)", 120), field('pt-vu', "Vu (kN)", 90))}
${row2(field('pt-fc', "fc28 (MPa)", 25), field('pt-fe', "fe (MPa)", 500))}
${row2(field('pt-enrobage', "Enrobage (mm)", 40), field('pt-ms', "Ms service (optionnel) (kN.m)", ''))}
${select('pt-fis', "Fissuration", [['peu_prejudiciable', 'Peu préjudiciable (σst ≤ 2/3 fe)'], ['prejudiciable', 'Préjudiciable (A.4.5,33)'], ['tres_prejudiciable', 'Très préjudiciable (A.4.5,34)']], 'prejudiciable')}
<div class="actions"><button class="btn gold" id="pt-calc">Calculer</button>
<button class="btn ghost small" id="pt-add" disabled>Ajouter à la synthèse</button></div>
</div>
<div class="card"><h2>Résultat</h2><div class="result" id="pt-res">${vide('poutre')}</div></div></div>`,
    init() {
      $('pt-calc').addEventListener('click', async () => {
        const ms = $('pt-ms').value;
        const payload = { b_cm: +$('pt-b').value, h_cm: +$('pt-h').value, enrobage_mm: +$('pt-enrobage').value,
          fc28_mpa: +$('pt-fc').value, fe_mpa: +$('pt-fe').value, mu_knm: +$('pt-mu').value, vu_kn: +$('pt-vu').value,
          fissuration: $('pt-fis').value };
        if (ms !== '') payload.ms_knm = +ms;
        const resEl = $('pt-res'); spinner(resEl);
        try {
          const r = await api('/api/engine/poutre', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          const els = r.els || {}, tau = r.effort_tranchant || {};
          resEl.innerHTML = kv([
            ['μ', r.mu], ['μlim', r.mu_lim], ['α', r.alpha], ['Z (m)', r.z_m],
            ['As calc. (cm²)', r.as_cm2], ['As retenue (cm²)', r.as_retenue_cm2],
            ['Ferraillage', r.ferraillage?.choix, true], ['σbc ELS (MPa)', els.sigma_bc_mpa], ['σst ELS (MPa)', `${els.sigma_st_mpa} / lim ${els.sigma_st_lim_mpa}`],
            ['σst OK ?', els.sigma_st_ok ? 'OUI' : 'NON'], ['τu (MPa)', `${tau.tau_u_mpa} / lim ${tau.tau_u_lim_mpa}`], ['At (cm²/m)', tau.at_cm2_par_m],
          ]) + renderRaw(r);
          $('pt-add').disabled = false;
          $('pt-add').onclick = () => addToSynthesis('poutres', { ...r, mu_knm: payload.mu_knm });
        } catch (e) { resEl.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });
    }
  };
}

/* ============ MODULE: VOILE ============ */
function tabVoile() {
  return {
    html: `<h1 class="module-title">Voiles de Contreventement <small>BAEL B.8.4 / pratique BET — σ = N/(e·L) ± 6M/(e·L²) ; rive dimensionnée si section partiellement comprimée</small></h1>
<div class="grid"><div class="card"><h2>Données</h2>
${row2(field('v-l', "L — longueur du voile (m)", 4.0), field('v-ep', "ép. (cm)", 18))}
${row2(field('v-n', "N — effort normal ELU (kN)", 1200), field('v-m', "M (kN.m)", 260))}
${row2(field('v-v', "V — effort tranchant ELU (kN)", 180), field('v-fc', "fc28 (MPa)", 25))}
<div class="actions"><button class="btn gold" id="v-calc">Calculer</button>
<button class="btn ghost small" id="v-add" disabled>Ajouter à la synthèse</button></div>
</div>
<div class="card"><h2>Résultat</h2><div class="result" id="v-res">${vide('voile')}</div></div></div>`,
    init() {
      $('v-calc').addEventListener('click', async () => {
        const payload = { longueur_m: +$('v-l').value, ep_cm: +$('v-ep').value, fc28_mpa: +$('v-fc').value, fe_mpa: 500,
          n_kn: +$('v-n').value, m_knm: +$('v-m').value, v_kn: +$('v-v').value };
        const resEl = $('v-res'); spinner(resEl);
        try {
          const r = await api('/api/engine/voile', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          resEl.innerHTML = kv([
            ['Mode', r.mode], ['σmax (MPa)', r.sigma_max_mpa, true], ['σmin (MPa)', r.sigma_min_mpa],
            ['Compression OK ?', r.compression_ok ? 'OUI' : 'NON'], ['τu (MPa)', `${r.tau_u_mpa} / lim ${r.tau_u_lim_mpa}`],
            ['As rive (cm²)', r.as_rive_cm2], ['As vert. min (cm²/m)', r.as_vert_par_m_cm2], ['As horiz. min (cm²/m)', r.as_horiz_par_m_cm2],
          ]) + notes(r.attention) + renderRaw(r);
          $('v-add').disabled = false;
          $('v-add').onclick = () => addToSynthesis('voiles', { ...r });
        } catch (e) { resEl.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });
    }
  };
}

/* ============ MODULE: SYNTHÈSE ============ */
function tabSynthese() {
  return {
    html: `<h1 class="module-title">Synthèse de Calcul <small>Note de calcul HTML (page de garde, références BAEL/RPS, calculs, audit arithmétique) + plan DXF A3</small></h1>
<div class="grid"><div class="card"><h2>Projet</h2>
${field('sy-projet', "Projet", state.project.projet, 'text')}
${row2(field('sy-client', "Client", state.project.client, 'text'), field('sy-site', "Site", state.project.site, 'text'))}
${row2(field('sy-indice', "Indice", state.project.indice, 'text'), `<div class="field"><label>&nbsp;</label><button class="btn small ghost" id="sy-loaddemo">Charger le scénario démo R+4</button></div>`)}
<h2 class="sous">Éléments collectés</h2>
<ul class="items-list" id="synthesis-items"></ul>
<div class="actions-col">
  <button class="btn gold" id="sy-note">Générer la note de calcul</button>
  <button class="btn" id="sy-note-save">Sauvegarder la note (serveur /output)</button>
  <button class="btn" id="sy-dxf">Générer le plan DXF (semelles)</button>
  <a class="btn ghost small" id="sy-dxf-link" style="display:none; text-align:center">Télécharger le DXF</a>
</div>
</div>
<div class="card"><h2>Aperçu</h2><div class="result" id="sy-log">${vide('synthese', 'La note assemble la page de garde, les références normatives, les hypothèses, le modèle Robot, la vérification sismique, chaque élément calculé, un audit arithmétique ligne à ligne et les alertes.')}</div></div></div>`,
    init() {
      // synchroniser les champs projet
      $('sy-projet').addEventListener('input', e => { state.project.projet = e.target.value; renderCartouche(); });
      $('sy-client').addEventListener('input', e => { state.project.client = e.target.value; renderCartouche(); });
      $('sy-site').addEventListener('input', e => state.project.site = e.target.value);
      $('sy-indice').addEventListener('input', e => { state.project.indice = e.target.value; renderCartouche(); });
      $('sy-loaddemo').addEventListener('click', loadDemo);
      renderSynthesis();
      const log = (msg) => { $('sy-log').innerHTML = `<p class="note">${esc(msg)}</p>`; };
      $('sy-note').addEventListener('click', async () => {
        log('Génération de la note de calcul…');
        try {
          const payload = synthesisPayload();
          const r = await fetch('/api/report/note', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          const html = await r.text();
          ouvrirApercuNote(html);
          log('Note de calcul affichée. Bouton « Imprimer / PDF » pour l\'enregistrer en PDF.');
        } catch (e) { log('Erreur : ' + e.message); }
      });
      $('sy-note-save').addEventListener('click', async () => {
        log('Sauvegarde…');
        try {
          const payload = synthesisPayload();
          const r = await api('/api/report/note/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          log(`Note sauvegardée : output/${r.fichier} (${r.octets} octets).`);
        } catch (e) { log('Erreur : ' + e.message); }
      });
      $('sy-dxf').addEventListener('click', async () => {
        log('Génération du plan DXF…');
        try {
          const footings = (state.semelles_isolees.length ? state.semelles_isolees : [{ A_m: 2.27, B_m: 2.27, H_m: 0.49, d_m: 0.43, asx_cm2: 19.6, asy_cm2: 19.6, acier_x: '13 HA14', acier_y: '13 HA14' }])
            .map((s, i) => ({ nom: 'S' + (i + 1), A_m: s.A_m, B_m: s.B_m, H_m: s.H_m, d_m: s.d_m,
              asx_cm2: s.asx_cm2, asy_cm2: s.asy_cm2, acier_x: s.acier_x, acier_y: s.acier_y,
              cote_x_m: [0, 6, 12][i % 3], cote_y_m: [0, 5, 10][Math.floor(i / 3) % 3] }));
          const payload = { projet: state.project.projet, client: state.project.client, site: state.project.site,
            indice: state.project.indice, trame_x_m: [0, 6, 12], trame_y_m: [0, 5, 10],
            footings, bureau: state.bureau, sortie: 'plan_fondation' };
          const r = await api('/api/dxf/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          const a = $('sy-dxf-link');
          a.href = '/api/dxf/download/' + r.fichier;
          a.textContent = `Télécharger ${r.fichier} (${r.octets} octets)`;
          a.style.display = 'inline-block';
          log('Plan DXF généré (calques AXES/COFFRAGE/ACIER_LONG/CADRES/COTATION/CARTOUCHE).');
        } catch (e) { log('Erreur : ' + e.message); }
      });
    }
  };
}

/* ============ MODULE: BUREAU ============ */
function tabBureau() {
  const b = state.bureau;
  return {
    html: `<h1 class="module-title">Données de votre bureau <small>reprises sur la page de garde de la note de calcul et dans le cartouche DXF</small></h1>
<div class="grid"><div class="card"><h2>Identité</h2>
${field('b-nom', "Nom du bureau", b.nom || '', 'text')}
${field('b-adresse', "Adresse", b.adresse || '', 'text')}
${row2(field('b-tel', "Téléphone", b.telephone || '', 'text'), field('b-email', "Email", b.email || '', 'text'))}
${field('b-ing', "Ingénieur chargé du projet", b.ingenieur || '', 'text')}
${row2(field('b-rc', "RC", b.rc || '', 'text'), field('b-ice', "ICE", b.ice || '', 'text'))}
${row2(field('b-patente', "Patente", b.patente || '', 'text'), field('b-if', "IF", b.if_ || '', 'text'))}
<button class="btn gold" id="b-save">Enregistrer</button>
<p class="note">Ces données sont enregistrées dans <code>referentiels/bureau.json</code>. Les champs « logo » et « cachet » peuvent être ajoutés au format base64 (clés logo_base64 / cachet_base64).</p>
</div>
<div class="card"><h2>Aperçu</h2><div class="result" id="b-res">${vide('bureau', 'Modifiez les valeurs puis enregistrez.')}</div></div></div>`,
    init() {
      $('b-save').addEventListener('click', async () => {
        const payload = { nom: $('b-nom').value, adresse: $('b-adresse').value, telephone: $('b-tel').value,
          email: $('b-email').value, ingenieur: $('b-ing').value, rc: $('b-rc').value, ice: $('b-ice').value,
          patente: $('b-patente').value, if_: $('b-if').value };
        const resEl = $('b-res'); resEl.innerHTML = '<span class="spinner"></span> enregistrement…';
        try {
          await api('/api/bureau', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
          state.bureau = { ...state.bureau, ...payload };
          resEl.innerHTML = '<p class="ok">Données enregistrées. Elles apparaîtront dans la prochaine note de calcul et le prochain plan DXF.</p>';
        } catch (e) { resEl.innerHTML = `<p class="warn">Erreur : ${esc(e.message)}</p>`; }
      });
    }
  };
}

/* ---------- démo ---------- */
async function loadDemo() {
  const resEl = $('sy-log'); resEl.innerHTML = '<span class="spinner"></span> chargement du scénario démo…';
  try {
    const demo = await api('/api/demo');
    state.project = { projet: demo.projet, client: demo.client, site: demo.site, indice: 'A' };
    const robot = await api('/api/robot/model');
    state.robot = robot;
    const sisPayload = { ...demo.sismique };
    const rSism = await api('/api/engine/sismique', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sisPayload) });
    state.sismique = rSism;
    state.poteaux = []; state.poutres = []; state.semelles_isolees = []; state.semelles_filantes = []; state.voiles = [];
    for (const p of demo.poteaux) state.poteaux.push(await api('/api/engine/poteau', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }));
    for (const p of demo.poutres) state.poutres.push(await api('/api/engine/poutre', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }));
    for (const p of demo.semelles_isolees) state.semelles_isolees.push(await api('/api/engine/semelle', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }));
    for (const p of demo.voiles) state.voiles.push(await api('/api/engine/voile', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(p) }));
    renderSynthesis(); renderCartouche();
    for (const k of ['projet', 'client', 'site', 'indice']) { const f = $('sy-' + k); if (f) f.value = state.project[k]; }
    resEl.innerHTML = '<p class="ok">Scénario démo chargé : Robot (simulation) + sismique + 1 poteau + 1 poutre + 1 semelle + 1 voile. Générez la note ou le DXF.</p>';
  } catch (e) { resEl.innerHTML = `<p class="warn">Erreur démo : ${esc(e.message)}</p>`; }
}

/* ---------- construction des onglets ---------- */
const builders = { projet: tabProjet, poteau: tabPoteau, sismique: tabSismique, semelle: () => tabSemelle(false),
  semelle_filante: () => tabSemelle(true), poutre: tabPoutre, voile: tabVoile,
  synthese: tabSynthese, bureau: tabBureau };

async function boot() {
  try { state.bureau = await api('/api/bureau'); } catch { state.bureau = {}; }
  const nav = $('tabs'), main = $('main');
  let groupe = null;
  for (const m of MODULES) {
    if (m.groupe !== groupe) {
      groupe = m.groupe;
      const g = document.createElement('div');
      g.className = 'nav-groupe'; g.textContent = groupe;
      nav.appendChild(g);
    }
    const b = document.createElement('button');
    b.innerHTML = `${glyphe(m.id)}<span>${esc(m.label)}</span>`; b.dataset.tab = m.id;
    b.addEventListener('click', () => activate(m.id));
    nav.appendChild(b);
    const section = document.createElement('section');
    section.className = 'tab'; section.id = 'tab-' + m.id;
    const built = builders[m.id]();
    section.innerHTML = built.html;
    const feuille = section.querySelector('.grid > .card:last-child > h2:first-child');
    if (feuille) feuille.dataset.feuille = m.ref;
    main.appendChild(section);
    built.init();
  }
  renderCartouche();
  function activate(id) {
    nav.querySelectorAll('button').forEach(b => {
      const actif = b.dataset.tab === id;
      b.classList.toggle('active', actif);
      if (actif) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current');
    });
    main.scrollTop = 0; window.scrollTo(0, 0);
    main.querySelectorAll('.tab').forEach(s => s.classList.toggle('active', s.id === 'tab-' + id));
  }
  activate('projet');
  checkHealth();
}
boot();


// Aperçu intégré de la note de calcul : fonctionne dans la fenêtre de l'application
// (WebView2) comme dans un navigateur, sans ouvrir de nouvel onglet ni de fenêtre.
function ouvrirApercuNote(html) {
  let ov = document.getElementById('apercu-note');
  if (!ov) {
    ov = document.createElement('div');
    ov.id = 'apercu-note';
    ov.innerHTML = `<div class="apercu-barre"><strong>Note de calcul</strong>
      <span><button class="btn gold small" id="apercu-imprimer">Imprimer / PDF</button>
      <button class="btn ghost small" id="apercu-fermer">Fermer</button></span></div>
      <iframe id="apercu-cadre" title="Note de calcul"></iframe>`;
    document.body.appendChild(ov);
    document.getElementById('apercu-fermer').addEventListener('click', () => { ov.style.display = 'none'; });
    document.getElementById('apercu-imprimer').addEventListener('click', () => {
      const f = document.getElementById('apercu-cadre'); f.contentWindow.focus(); f.contentWindow.print();
    });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') ov.style.display = 'none'; });
  }
  document.getElementById('apercu-cadre').srcdoc = html;
  ov.style.display = 'flex';
}
