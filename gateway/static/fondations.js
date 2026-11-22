/* Bénayfacile — carte « Fondations » de l'écran Projet Robot (cahier des besoins US1, US2, US4).
   Fûts et niveau supérieur de chaque fût, catégories des poutres du niveau fondation (modifiables),
   dalles pleines de fondation (lues dans Robot ou ajoutées : épaisseur, charges, appui, treillis),
   couches sous le dallage pour la coupe. Aucune valeur n'est proposée à la place de l'ingénieur.
   Usage : const f = Fondations(conteneur, quandModifie); f.charger(ossature); f.dallesFondation();   */
(function () {
  'use strict';

  const CATS = [['poutre', 'Poutre', 'Pt'], ['longrine', 'Longrine', 'L'], ['chainage', 'Chaînage', 'Ch']];
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const lettre = (j) => { let s = ''; j += 1; while (j) { const r = (j - 1) % 26; s = String.fromCharCode(65 + r) + s; j = Math.floor((j - 1) / 26); } return s; };
  const cote = (z) => (z == null ? '—' : Math.abs(z) < 0.005 ? '±0,00' : (z > 0 ? '+' : '−') + Math.abs(z).toFixed(2).replace('.', ','));
  const nb = (v) => (v === '' || v == null || Number.isNaN(+v) ? null : +v);
  const m2 = (v) => (v == null ? '—' : (+v).toFixed(2).replace('.', ','));

  function Fondations(conteneur, quandModifie) {
    const st = { o: null, couches: '', message: '' };

    function couches() {
      return st.couches.split('\n').map(l => l.trim()).filter(Boolean).map(l => {
        const [nom, ep] = l.split(/[;|]/).map(t => (t || '').trim());
        const e = nb((ep || '').replace(',', '.').replace(/\s*cm$/i, ''));
        return { nom, ep_cm: e && e > 0 ? e : null };
      }).filter(c => c.nom);
    }

    function dallesFondation() {
      const o = st.o; if (!o) return [];
      const cs = couches();
      return (o.dalles || []).filter(d => d.role === 'fondation').map(d => ({ ...d, couches: cs }));
    }

    function charger(o) {
      st.o = o; o.dalles = o.dalles || []; st.message = '';
      rendre();
    }

    function zPlancherBas(o) {
      if (o.fondation?.z_plancher_bas_m != null) return o.fondation.z_plancher_bas_m;
      const zs = (o.semelles || []).map(s => s.z_m).filter(z => z != null);
      return zs.length ? Math.min(...zs) : null;
    }

    function rendre() {
      const o = st.o;
      if (!o) { conteneur.innerHTML = ''; return; }
      const f = o.fondation || null;
      const sem = o.semelles || [];
      const futs = sem.filter(s => s.fut && s.fut.z_haut_m != null);
      const pb = (o.poutres || []).map((b, i) => [b, i]).filter(([b]) => b.niveau === 'Fondation');
      const df = (o.dalles || []).map((d, i) => [d, i]).filter(([d]) => d.role === 'fondation');
      const tx = o.trame_x_m || [], ty = o.trame_y_m || [];
      let h = '';

      // US4 — niveau supérieur de chaque fût
      h += '<h3 class="sous">Fûts de poteaux — niveau supérieur</h3>';
      if (f && f.zone_futs) h += `<p class="small">Fûts modélisés entre les semelles et le plancher bas (z = ${cote(f.z_plancher_bas_m)} m) : ${esc(f.motif)}.</p>`;
      else if (futs.length) h += '<p class="small">Le poteau part de l\'appui du modèle : le fût, de la semelle à ce niveau, n\'est pas modélisé ; sa hauteur dépend du niveau d\'assise des semelles (rapport géotechnique).'
        + (f && f.motif ? ` ${esc(f.motif)}.` : '') + '</p>';
      if (futs.length) {
        const lignes = futs.map(s => `<tr><td translate="no"><b>${esc(s.nom)}</b></td><td>${esc(s.fut.a_cm ?? '?')} × ${esc(s.fut.b_cm ?? '?')}</td>
          <td class="num">${s.fut.z_bas_m != null ? cote(s.fut.z_bas_m) : 'selon assise'}</td><td class="num"><b>${cote(s.fut.z_haut_m)}</b></td>
          <td class="num">${s.fut.hauteur_m != null ? m2(s.fut.hauteur_m) : 'non modélisé'}</td></tr>`).join('');
        const table = `<div class="table-defile"><table class="lot fond-table"><tr><th>Semelle</th><th>Section du fût (cm)</th><th class="num">Dessus semelle (m)</th>
          <th class="num">N.S. fût (m)</th><th class="num">Hauteur (m)</th></tr>${lignes}</table></div>`;
        h += futs.length > 8 ? `<details><summary>Niveau supérieur des ${futs.length} fûts</summary>${table}</details>` : table;
        h += '<p class="small">Cotes : Z du modèle Robot (±0,00 = Z 0). Elles figurent sur le plan de fondation, les coupes des semelles et la coupe du dallage.</p>';
      } else {
        h += '<p class="small">Aucune semelle positionnée : les fûts ne peuvent pas être repérés pour ce modèle.</p>';
      }

      // US2 — longrines, chaînages, poutres du niveau fondation
      h += '<h3 class="sous">Longrines, chaînages et poutres du niveau fondation</h3>';
      if (pb.length) {
        const n = (c) => pb.filter(([b]) => (b.categorie || 'poutre') === c).length;
        h += `<p class="small">${CATS.map(([c, l]) => `${n(c)} ${l.toLowerCase()}(s)`).join(' · ')} — catégories déduites du nom de section dans Robot ou de la position (une longrine relie deux semelles ; un chaînage ne porte pas de dalle). Corrigez-les si besoin : elles décident du repère (L, Ch, Pt) et du dessin.</p>`;
        const lignes = pb.map(([b, i]) => `<tr><td translate="no"><b>${esc(b.nom)}</b></td><td>${esc(b.b_cm ?? '?')} × ${esc(b.h_cm ?? '?')}</td>
          <td><select data-cat="${i}" aria-label="Catégorie de ${esc(b.nom)}">${CATS.map(([c, l]) => `<option value="${c}" ${c === (b.categorie || 'poutre') ? 'selected' : ''}>${l}</option>`).join('')}</select></td>
          <td class="small">${esc(b.categorie_motif || '')}</td></tr>`).join('');
        h += `<details><summary>Voir et modifier les ${pb.length} éléments</summary><div class="table-defile"><table class="lot fond-table">
          <tr><th>Élément</th><th>b × h (cm)</th><th>Catégorie</th><th>Motif</th></tr>${lignes}</table></div></details>`;
      } else {
        h += '<p class="small">Aucune poutre au niveau des fondations dans ce modèle.</p>';
      }

      // US1 — dalles pleines de fondation
      h += '<h3 class="sous">Dalles pleines de fondation</h3>';
      h += '<p class="small">Calculées comme des dalles pleines portées par les longrines de leur contour (BAEL A.8.2) ; le sol n\'est pas compté comme appui. Un dallage « sur terre-plein » est dessiné mais pas justifié par l\'application. Saisissez les charges g (revêtements, hors poids propre) et q.</p>';
      if (df.length) {
        const lignes = df.map(([d, i]) => {
          const lx = d.xmax_m != null ? d.xmax_m - d.xmin_m : d.lx_m, ly = d.ymax_m != null ? d.ymax_m - d.ymin_m : d.ly_m;
          const inp = (k, lib, w = 5) => `<input type="number" step="any" data-d="${i}" data-k="${k}" value="${esc(d[k] ?? '')}" aria-label="${lib} de ${esc(d.nom)}" style="width:${w}em">`;
          const ts = d.armature === 'treillis';
          return `<tr><td translate="no"><b>${esc(d.nom)}</b>${d.source === 'saisie' ? ' <span class="badge">ajoutée</span>' : ''}</td>
            <td class="num">${m2(lx)} × ${m2(ly)}</td><td>${inp('h_cm', 'Épaisseur (cm)', 4)}</td><td>${inp('g_sup_kn_m2', 'g (kN/m²)')}</td><td>${inp('q_kn_m2', 'q (kN/m²)')}</td>
            <td><select data-d="${i}" data-k="appui" aria-label="Appui de ${esc(d.nom)}"><option value="">portée (longrines)</option>
              <option value="terre_plein" ${d.appui === 'terre_plein' ? 'selected' : ''}>sur terre-plein</option></select></td>
            <td><select data-d="${i}" data-k="armature" aria-label="Armature de ${esc(d.nom)}"><option value="">barres du calcul</option>
              <option value="treillis" ${ts ? 'selected' : ''}>treillis soudé</option></select>
              ${ts ? `Ø ${inp('ts_diametre_mm', 'Diamètre du treillis (mm)', 3.5)} maille ${inp('ts_maille_cm', 'Maille (cm)', 3.5)}` : ''}</td>
            <td>${d.source === 'saisie' ? `<button class="btn ghost small" data-suppr="${i}" aria-label="Supprimer ${esc(d.nom)}">✕</button>` : ''}</td></tr>`;
        }).join('');
        h += `<div class="table-defile"><table class="lot fond-table"><tr><th>Dalle</th><th class="num">lx × ly (m)</th><th>e (cm)</th><th>g (kN/m²)</th>
          <th>q (kN/m²)</th><th>Appui</th><th>Armature</th><th></th></tr>${lignes}</table></div>`;
      } else {
        h += '<p class="small">Aucune dalle au niveau du plancher bas dans le modèle. Ajoutez-en une ci-dessous.</p>';
      }
      if (tx.length > 1 && ty.length > 1) {
        const ox = (sel) => tx.map((v, i) => `<option value="${i}" ${i === sel ? 'selected' : ''}>${i + 1}</option>`).join('');
        const oy = (sel) => ty.map((v, j) => `<option value="${j}" ${j === sel ? 'selected' : ''}>${lettre(j)}</option>`).join('');
        h += `<div class="fond-ajout"><span>Ajouter une dalle entre les files</span>
          <label>de <select id="fd-x1">${ox(0)}</select></label><label>à <select id="fd-x2">${ox(1)}</select></label>
          <label>et de <select id="fd-y1">${oy(0)}</select></label><label>à <select id="fd-y2">${oy(1)}</select></label>
          <label>e (cm) <input id="fd-h" type="number" step="any" style="width:4em" placeholder="ex. 15"></label>
          <button class="btn small" id="fd-ajouter">Ajouter la dalle</button></div>`;
      } else {
        h += '<p class="small">Pas de trame lue dans ce modèle : la position d\'une dalle ajoutée ne peut pas être définie.</p>';
      }
      if (st.message) h += `<p class="warn">${esc(st.message)}</p>`;

      // US3 — couches sous le dallage (coupe transversale)
      h += `<h3 class="sous">Couches sous la dalle (coupe du dallage)</h3>
        <div class="field"><label for="fd-couches">Une couche par ligne, de haut en bas : désignation ; épaisseur (cm). Laissez vide si rien n'est défini.</label>
        <textarea id="fd-couches" rows="3" placeholder="Béton de propreté ; 5&#10;Film polyane&#10;Hérisson ; 20">${esc(st.couches)}</textarea></div>`;
      conteneur.innerHTML = h;
    }

    conteneur.addEventListener('change', (e) => {
      const o = st.o; if (!o) return;
      const t = e.target;
      if (t.dataset.cat != null) {
        const b = o.poutres[+t.dataset.cat];
        b.categorie = t.value;
        b.categorie_motif = 'choisie par l\'utilisateur';
        const pre = CATS.find(c => c[0] === t.value)[2];
        b.nom = String(b.nom || '').replace(/^(Pt|L|Ch)\s/, pre + ' ');
        rendre(); quandModifie && quandModifie('categorie');
      } else if (t.dataset.d != null) {
        const d = o.dalles[+t.dataset.d];
        const k = t.dataset.k;
        d[k] = t.tagName === 'SELECT' ? (t.value || null) : nb(t.value);
        if (t.tagName === 'SELECT') rendre();
        quandModifie && quandModifie('dalle');
      } else if (t.id === 'fd-couches') {
        st.couches = t.value; quandModifie && quandModifie('couches');
      }
    });
    conteneur.addEventListener('click', (e) => {
      const o = st.o; if (!o) return;
      const s = e.target.closest('[data-suppr]');
      if (s) { o.dalles.splice(+s.dataset.suppr, 1); st.message = ''; rendre(); quandModifie && quandModifie('dalle'); return; }
      if (e.target.id !== 'fd-ajouter') return;
      const tx = o.trame_x_m, ty = o.trame_y_m;
      const [i1, i2] = [+conteneur.querySelector('#fd-x1').value, +conteneur.querySelector('#fd-x2').value].sort((a, b) => a - b);
      const [j1, j2] = [+conteneur.querySelector('#fd-y1').value, +conteneur.querySelector('#fd-y2').value].sort((a, b) => a - b);
      const h = nb(conteneur.querySelector('#fd-h').value);
      if (i1 === i2 || j1 === j2) { st.message = 'Choisissez deux files différentes dans chaque direction.'; rendre(); return; }
      if (!h || h <= 0) { st.message = 'Saisissez l\'épaisseur de la dalle (cm).'; rendre(); return; }
      const n = o.dalles.filter(d => d.source === 'saisie').length + 1;
      const [x1, x2, y1, y2] = [tx[i1], tx[i2], ty[j1], ty[j2]];
      o.dalles.push({
        id: `DFM${n}`, nom: `DF M${n}`, niveau: 'Fondation', role: 'fondation', type: 'dalle', source: 'saisie',
        axes: `${i1 + 1}-${i2 + 1} / ${lettre(j1)}-${lettre(j2)}`,
        xmin_m: x1, xmax_m: x2, ymin_m: y1, ymax_m: y2, z_m: zPlancherBas(o), rectangulaire: true,
        contour_m: [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], h_cm: h, g_sup_kn_m2: null, q_kn_m2: null,
      });
      st.message = '';
      rendre(); quandModifie && quandModifie('dalle');
    });

    return { charger, dallesFondation, couches };
  }

  window.Fondations = Fondations;
})();
