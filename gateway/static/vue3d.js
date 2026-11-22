/* Bénayfacile — vue 3D du modèle (poteaux, poutres, voiles, dalles, semelles).
   Canvas 2D, projection orthographique, sans bibliothèque ni réseau.
   Usage : const v = Vue3D(conteneur); v.charger(ossature); v.etats(lot);   */
(function () {
  'use strict';

  const lettreFile = (j) => { let s = ''; j += 1; while (j) { const r = (j - 1) % 26; s = String.fromCharCode(65 + r) + s; j = Math.floor((j - 1) / 26); } return s; };
  const indiceFile = (l) => [...l].reduce((n, c) => n * 26 + c.charCodeAt(0) - 64, 0) - 1;
  // de bas en haut, mêmes règles que common.rang_niveau : Fondation ; S-2, SS1, Sous-sol 1, R-1 ; RDC ;
  // R+1, N+1, Étage 1, 1er étage, Niveau 3 ; Mezzanine ; Terrasse… ; altitudes entre elles ; inconnus à la fin
  const rangNiveau = (nom) => {
    const n = String(nom || '').trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    if (/^(fondation|infrastructure|radier|longrine)/.test(n)) return -1e6;
    let m = n.match(/^(?:s(?:ous[- ]?sol)?|ss|r|n|niv(?:eau)?\.?)\s*-\s*(\d+)$/) || n.match(/^(?:ss|sous[- ]?sol|s)\s*(\d+)$/);
    if (m) return -(+m[1]);
    if (/^(rdc|rez[- ]de[- ]chaussee|rdj|rez[- ]de[- ]jardin)(?![a-z])/.test(n) || /^[rn]\s*\+\s*0$/.test(n)) return 0;
    m = n.match(/^(?:[rn]|niv(?:eau)?\.?|etage)\s*\+?\s*(\d+)$/) || n.match(/^(\d+)\s*(?:er|e|eme)?\s*etage$/);
    if (m) return +m[1];
    if (n.startsWith('mezzanine')) return 0.5;
    if (/^(terrasse|toiture|buanderie|edicule|acrotere|cage)/.test(n)) return 9000;
    m = n.match(/^(?:niv(?:eau)?\.?|z\s*=|altitude)?\s*([+-]?\d+(?:[.,]\d+)?)\s*m?$/);
    if (m) return 1e5 + parseFloat(m[1].replace(',', '.'));
    return 1e7;
  };
  const FAMILLES = [['poteaux', 'Poteaux'], ['poutres', 'Poutres'], ['voiles', 'Voiles'], ['dalles', 'Dalles'],
                    ['semelles', 'Semelles'], ['autres', 'Autres']];
  const ETATS = { verifie: 'Vérifié', a_revoir: 'À revoir', erreur: 'Erreur', incomplet: 'Incomplet' };
  const CATEGORIES = { poutre: 'Poutre', longrine: 'Longrine', chainage: 'Chaînage' };
  const VUES = { iso: [-0.75, 0.55], face: [0, 0.02], cote: [-Math.PI / 2, 0.02], dessus: [0, Math.PI / 2 - 0.001] };

  function Vue3D(conteneur) {
    conteneur.innerHTML = `
      <div class="v3d-barre" role="toolbar" aria-label="Vue 3D">
        <span class="v3d-groupe">${Object.entries({ iso: 'Iso', face: 'Face', cote: 'Côté', dessus: 'Dessus' })
          .map(([k, t]) => `<button type="button" class="btn ghost small" data-vue="${k}">${t}</button>`).join('')}</span>
        <span class="v3d-groupe">${FAMILLES
          .map(([k, t]) => `<label class="v3d-case"><input type="checkbox" data-fam="${k}" checked> ${t}</label>`).join('')}</span>
        <label class="v3d-case">Jusqu'au niveau <select data-niv></select></label>
      </div>
      <div class="v3d-zone"><canvas class="v3d-canvas" tabindex="0" role="img"></canvas><div class="v3d-bulle" hidden></div></div>
      <div class="v3d-legende"></div>`;
    const cv = conteneur.querySelector('canvas'), ctx = cv.getContext('2d');
    const bulle = conteneur.querySelector('.v3d-bulle'), legende = conteneur.querySelector('.v3d-legende');
    const selNiv = conteneur.querySelector('[data-niv]');
    const st = { prims: [], niveaux: [], yaw: VUES.iso[0], pitch: VUES.iso[1], zoom: 1, px: 0, py: 0,
                 fam: Object.fromEntries(FAMILLES.map(([k]) => [k, true])), nivMax: null, rang: {}, jetons: {},
                 etats: {}, centre: [0, 0, 0], rayon: 1, trame: { x: [], y: [] }, supposee: false, ecran: [] };

    // jetons de couleur lus une fois par dessin (getComputedStyle par élément coûte cher sur un grand modèle)
    let style = null;
    const jeton = (n, d) => {
      if (!(n in st.jetons)) st.jetons[n] = ((style || (style = getComputedStyle(conteneur))).getPropertyValue(n).trim() || d);
      return st.jetons[n];
    };
    let attente = 0;
    const demander = () => { if (!attente) attente = requestAnimationFrame(() => { attente = 0; dessiner(); }); };
    const plusHaut = (a, b) => (st.rang[a] ?? rangNiveau(a)) > (st.rang[b] ?? rangNiveau(b));

    // ---------- géométrie ----------
    function charger(o) {
      const tx = o.trame_x_m || [], ty = o.trame_y_m || [];
      st.trame = { x: tx, y: ty };
      const xyAxe = (axe) => {
        const m = String(axe || '').match(/^([A-Z]+)(\d+)$/); if (!m) return null;
        const j = indiceFile(m[1]), i = +m[2] - 1;
        return (i < tx.length && j < ty.length) ? [tx[i], ty[j]] : null;
      };
      // altitude des niveaux : z lu dans le modèle, sinon cumul des hauteurs d'étage
      let noms = [...new Set([...(o.poteaux || []), ...(o.voiles || []), ...(o.poutres || []), ...(o.dalles || [])]
        .map(e => e.niveau).filter(Boolean))];
      const zNiv = {}, hNiv = {};
      for (const p of [...(o.poteaux || []), ...(o.voiles || [])]) {
        if (p.z_m != null) zNiv[p.niveau] = Math.min(zNiv[p.niveau] ?? Infinity, p.z_m);
        if (p.hauteur_m) hNiv[p.niveau] = Math.max(hNiv[p.niveau] || 0, p.hauteur_m);
      }
      // par altitude quand chaque étage en a une (noms Robot quelconques), sinon par libellé
      const fond = (n) => /^fondation/i.test(n);
      noms = noms.every(n => fond(n) || isFinite(zNiv[n] ?? NaN))
        ? noms.sort((a, b) => (fond(a) ? -1e9 : zNiv[a]) - (fond(b) ? -1e9 : zNiv[b]))
        : noms.sort((a, b) => rangNiveau(a) - rangNiveau(b));
      const connues = Object.values(hNiv);
      const hDefaut = connues.length ? connues.sort((a, b) => a - b)[connues.length >> 1] : 3.0;
      st.supposee = !connues.length;
      let z = 0;
      for (const n of noms.filter(n => !/^fondation/i.test(n))) {
        if (zNiv[n] == null || !isFinite(zNiv[n])) zNiv[n] = z;
        z = zNiv[n] + (hNiv[n] || hDefaut);
      }
      const hDe = (n) => hNiv[n] || hDefaut;
      // dalle du plancher bas sans altitude lue : au niveau des pieds des poteaux
      const zPieds = [...(o.poteaux || []), ...(o.semelles || [])].map(e => e.z_m).filter(z => z != null);
      const zBas = o.fondation?.z_plancher_bas_m ?? (zPieds.length ? Math.min(...zPieds) : 0);
      st.rang = Object.fromEntries(noms.map((n, i) => [n, fond(n) ? -1 : i]));
      const prims = [];
      for (const p of o.poteaux || []) {
        const xy = (p.x_m != null && p.y_m != null) ? [p.x_m, p.y_m] : xyAxe(p.axe); if (!xy) continue;
        const z0 = p.z_m ?? zNiv[p.niveau] ?? 0, h = p.hauteur_m || hDe(p.niveau);
        prims.push({ fam: 'poteaux', id: p.id, nom: p.nom, niveau: p.niveau,
                     info: (p.role === 'fut' ? 'fût ' : '') + (p.a_cm ? `${p.a_cm}×${p.b_cm} cm` : ''),
                     pts: [[xy[0], xy[1], z0], [xy[0], xy[1], z0 + h]], ep: (p.a_cm || 30) / 100 });
      }
      for (const b of o.poutres || []) {
        if ([b.x1_m, b.y1_m, b.x2_m, b.y2_m].some(v => v == null)) continue;
        const zb = b.z_m ?? (/^fondation/i.test(b.niveau) ? 0 : (zNiv[b.niveau] ?? 0) + hDe(b.niveau));
        const cat = CATEGORIES[b.categorie] ? b.categorie : 'poutre';
        prims.push({ fam: 'poutres', cat, id: b.id, nom: b.nom, niveau: b.niveau,
                     info: (cat !== 'poutre' ? CATEGORIES[cat].toLowerCase() + ' ' : '') + (b.b_cm ? `${b.b_cm}×${b.h_cm} cm` : ''),
                     pts: [[b.x1_m, b.y1_m, b.z1_m ?? zb], [b.x2_m, b.y2_m, b.z2_m ?? zb]], ep: (b.b_cm || 25) / 100 });
      }
      for (const v of o.voiles || []) {
        if ([v.x1_m, v.y1_m, v.x2_m, v.y2_m].some(c => c == null)) continue;
        const z0 = v.z_m ?? zNiv[v.niveau] ?? 0, h = v.hauteur_m || hDe(v.niveau);
        prims.push({ fam: 'voiles', id: v.id, nom: v.nom, niveau: v.niveau, info: v.ep_cm ? `ép. ${v.ep_cm} cm` : '',
                     pts: [[v.x1_m, v.y1_m, z0], [v.x2_m, v.y2_m, z0], [v.x2_m, v.y2_m, z0 + h], [v.x1_m, v.y1_m, z0 + h]] });
      }
      for (const d of o.dalles || []) {
        if ([d.xmin_m, d.xmax_m, d.ymin_m, d.ymax_m].some(c => c == null)) continue;
        const zd = d.z_m ?? (fond(d.niveau || '') ? zBas : (zNiv[d.niveau] ?? 0) + hDe(d.niveau));
        const contour = Array.isArray(d.contour_m) && d.contour_m.length >= 3 ? d.contour_m.map(c => [c[0], c[1], zd])
          : [[d.xmin_m, d.ymin_m, zd], [d.xmax_m, d.ymin_m, zd], [d.xmax_m, d.ymax_m, zd], [d.xmin_m, d.ymax_m, zd]];
        prims.push({ fam: 'dalles', id: d.id, nom: d.nom, niveau: d.niveau, info: d.type === 'balcon' ? 'balcon' : (d.h_cm ? `h = ${d.h_cm} cm` : 'dalle'),
                     pts: contour });
      }
      for (const s of o.semelles || []) {
        const xy = (s.x_m != null && s.y_m != null) ? [s.x_m, s.y_m] : xyAxe(s.axe); if (!xy) continue;
        prims.push({ fam: 'semelles', id: s.id, nom: s.nom, niveau: 'Fondation', info: '', base: xy, z: s.z_m ?? 0, pts: [[xy[0], xy[1], s.z_m ?? 0]] });
      }
      // éléments que le calcul ne traite pas (barres et panneaux inclinés) : montrés pour que le modèle soit complet
      for (const a of o.autres || []) {
        if (!Array.isArray(a.pts) || a.pts.length < 2) continue;
        prims.push({ fam: 'autres', id: a.id, nom: a.nom, niveau: '', info: `${a.genre || ''} — non calculé`, pts: a.pts, ep: 0.1 });
      }
      st.prims = prims;
      st.niveaux = noms;
      st.zNiv = zNiv;
      selNiv.innerHTML = `<option value="">tous (${noms.length})</option>` + noms.map(n => `<option>${n}</option>`).join('');
      st.nivMax = null;
      cadrer();
      st.etats = {};
      legendeMaj();
      dessiner();
    }

    // dimensions des semelles et état de chaque élément après le calcul
    function etats(lot) {
      st.etats = {};
      for (const fam of ['poteaux', 'poutres', 'semelles', 'voiles', 'dalles'])
        for (const l of (lot && lot[fam]) || []) if (l.id != null) st.etats[l.id] = { statut: l.statut, r: l.resultat };
      for (const p of st.prims) {
        if (p.fam !== 'semelles') continue;
        const r = st.etats[p.id]?.r;
        if (r && r.A_m && r.B_m) {
          const [x, y] = p.base, a = r.A_m / 2, b = r.B_m / 2, z = p.z - (r.H_m || 0);
          p.pts = [[x - a, y - b, z], [x + a, y - b, z], [x + a, y + b, z], [x - a, y + b, z]];
          p.info = `${r.A_m.toFixed(2)} × ${r.B_m.toFixed(2)} m`;
        }
      }
      cadrer(false);
      legendeMaj();
      dessiner();
    }

    function cadrer(reinit = true) {
      const mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
      for (const p of st.prims) for (const q of p.pts) for (let k = 0; k < 3; k++) {
        if (q[k] < mn[k]) mn[k] = q[k];
        if (q[k] > mx[k]) mx[k] = q[k];
      }
      if (!isFinite(mn[0])) { st.centre = [0, 0, 0]; st.rayon = 1; return; }
      st.centre = mn.map((v, k) => (v + mx[k]) / 2);
      st.rayon = Math.max(1, Math.hypot(mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]) / 2);
      st.min = mn; st.max = mx;
      if (reinit) { st.zoom = 1; st.px = 0; st.py = 0; }
    }

    // ---------- projection ----------
    function proj(p, W, H) {
      const [cx, cy, cz] = st.centre, cyw = Math.cos(st.yaw), syw = Math.sin(st.yaw), cp = Math.cos(st.pitch), sp = Math.sin(st.pitch);
      const dx = p[0] - cx, dy = p[1] - cy, dz = p[2] - cz;
      const x1 = dx * cyw - dy * syw, y1 = dx * syw + dy * cyw;
      const k = Math.min(W, H) / (2.15 * st.rayon) * st.zoom;
      return [W / 2 + st.px + x1 * k, H / 2 + st.py - (dz * cp - y1 * sp) * k, y1 * cp + dz * sp, k];
    }

    function couleur(p) {
      const e = st.etats[p.id]?.statut;
      if (e === 'verifie') return jeton('--verifie', '#2f6b3a');
      if (e === 'a_revoir' || e === 'erreur') return jeton('--non-verifie', '#b3301d');
      if (e === 'incomplet') return jeton('--attention', '#7a4f00');
      if (p.fam === 'autres') return jeton('--graphite-3', '#888');
      if (p.cat === 'longrine') return jeton('--v3d-longrines', '#5b4a8a');
      if (p.cat === 'chainage') return jeton('--v3d-chainages', '#6a7d2f');
      return jeton(`--v3d-${p.fam}`, '#3a8a8a');
    }

    function visible(p) {
      if (!st.fam[p.fam]) return false;
      if (st.nivMax == null) return true;
      if (p.fam === 'semelles' || /^fondation/i.test(p.niveau)) return true;
      return !p.niveau || !plusHaut(p.niveau, st.nivMax);
    }

    function dessiner() {
      st.jetons = {}; style = null;
      const dpr = window.devicePixelRatio || 1, W = conteneur.querySelector('.v3d-zone').clientWidth || 600, H = Math.max(320, Math.min(560, W * 0.62));
      if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) {
        cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); cv.style.width = W + 'px'; cv.style.height = H + 'px';
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.fillStyle = jeton('--v3d-fond', '#f4f3ef'); ctx.fillRect(0, 0, W, H);
      if (!st.prims.length) {
        ctx.fillStyle = jeton('--graphite-3', '#666'); ctx.font = '13px ' + jeton('--police-texte', 'sans-serif');
        ctx.textAlign = 'center'; ctx.fillText('Aucun élément positionné dans ce modèle.', W / 2, H / 2); return;
      }
      const texte = jeton('--graphite-2', '#444'), axes = jeton('--v3d-axes', '#b3301d'), police = jeton('--police-texte', 'sans-serif');
      // trame au sol
      const z0 = st.min ? st.min[2] : 0, { x: tx, y: ty } = st.trame;
      ctx.lineWidth = 1; ctx.setLineDash([6, 3, 1, 3]); ctx.strokeStyle = axes; ctx.globalAlpha = 0.55;
      const ligne = (a, b) => { const p = proj(a, W, H), q = proj(b, W, H); ctx.beginPath(); ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); ctx.stroke(); };
      if (tx.length && ty.length) {
        const ex = 0.06 * st.rayon;
        tx.forEach(x => ligne([x, ty[0] - ex, z0], [x, ty[ty.length - 1] + ex, z0]));
        ty.forEach(y => ligne([tx[0] - ex, y, z0], [tx[tx.length - 1] + ex, y, z0]));
      }
      ctx.setLineDash([]); ctx.globalAlpha = 1;
      // éléments, du plus loin au plus proche
      const vis = st.prims.filter(visible).map(p => {
        const sp = p.pts.map(q => proj(q, W, H));
        return { p, sp, d: sp.reduce((s, q) => s + q[2], 0) / sp.length };
      }).sort((a, b) => a.d - b.d);
      st.ecran = vis;
      for (const { p, sp } of vis) {
        const c = couleur(p), k = sp[0][3];
        if (p.pts.length >= 3) {
          ctx.beginPath(); sp.forEach((q, i) => i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])); ctx.closePath();
          ctx.globalAlpha = p.fam === 'dalles' ? 0.18 : 0.42; ctx.fillStyle = c; ctx.fill();
          ctx.globalAlpha = 0.9; ctx.strokeStyle = c; ctx.lineWidth = 1; ctx.stroke(); ctx.globalAlpha = 1;
        } else if (p.pts.length === 2) {
          ctx.strokeStyle = c; ctx.lineCap = 'round';
          ctx.lineWidth = Math.max(p.fam === 'poteaux' ? 2.2 : 1.4, Math.min(7, (p.ep || 0.3) * k));
          ctx.beginPath(); ctx.moveTo(sp[0][0], sp[0][1]); ctx.lineTo(sp[1][0], sp[1][1]); ctx.stroke();
        } else {
          ctx.fillStyle = c; ctx.beginPath(); ctx.arc(sp[0][0], sp[0][1], 3, 0, 7); ctx.fill();
        }
      }
      // repères de files et niveaux
      ctx.font = `11px ${police}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      if (tx.length && ty.length) {
        const ex = 0.1 * st.rayon;
        const bulle_ = (pt, t) => { const q = proj(pt, W, H); ctx.strokeStyle = axes; ctx.fillStyle = jeton('--v3d-fond', '#fff');
          ctx.beginPath(); ctx.arc(q[0], q[1], 9, 0, 7); ctx.fill(); ctx.stroke(); ctx.fillStyle = axes; ctx.fillText(t, q[0], q[1] + 0.5); };
        const pas = (vals, pt) => {          // un repère sur k si les bulles se chevauchent à l'écran
          if (vals.length < 2) return 1;
          const a = proj(pt(vals[0]), W, H), b = proj(pt(vals[vals.length - 1]), W, H);
          const moyen = Math.hypot(b[0] - a[0], b[1] - a[1]) / (vals.length - 1);
          return Math.max(1, Math.ceil(20 / Math.max(moyen, 1e-6)));
        };
        const kx = pas(tx, x => [x, ty[0] - ex, z0]), ky = pas(ty, y => [tx[0] - ex, y, z0]);
        tx.forEach((x, i) => { if (i % kx === 0 || i === tx.length - 1) bulle_([x, ty[0] - ex, z0], String(i + 1)); });
        ty.forEach((y, j) => { if (j % ky === 0 || j === ty.length - 1) bulle_([tx[0] - ex, y, z0], lettreFile(j)); });
      }
      if (st.min) {
        ctx.textAlign = 'right'; ctx.fillStyle = texte;
        // coin du bâtiment le plus à gauche à l'écran, pour que les niveaux restent hors du dessin quelle que soit la rotation
        const coins = [[st.min[0], st.min[1]], [st.max[0], st.min[1]], [st.max[0], st.max[1]], [st.min[0], st.max[1]]];
        const coin = coins.reduce((a, c) => proj([c[0], c[1], 0], W, H)[0] < proj([a[0], a[1], 0], W, H)[0] ? c : a);
        let dernierY = Infinity;
        for (const n of st.niveaux) {
          if (/^fondation/i.test(n) || (st.nivMax != null && plusHaut(n, st.nivMax))) continue;
          const q = proj([coin[0], coin[1], st.zNiv[n] ?? 0], W, H);
          q[0] -= 14;
          if (Math.abs(q[1] - dernierY) < 12) continue;           // évite les libellés superposés
          ctx.fillText(n, q[0] - 6, q[1]); dernierY = q[1];
        }
      }
      cv.setAttribute('aria-label', `Vue 3D : ${vis.length} éléments affichés sur ${st.niveaux.length} niveaux`);
    }

    function legendeMaj() {
      const n = (f) => st.prims.filter(p => p.fam === f).length;
      const calc = Object.keys(st.etats).length;
      const puce = (v, t) => `<span class="v3d-puce" style="background:var(${v})"></span>${t}`;
      legende.innerHTML = (calc
        ? [puce('--verifie', 'vérifié'), puce('--non-verifie', 'à revoir / erreur'), puce('--attention', 'incomplet')].join(' ')
        : [puce('--v3d-poteaux', 'poteaux'), puce('--v3d-poutres', 'poutres'),
           ...(st.prims.some(p => p.cat === 'longrine') ? [puce('--v3d-longrines', 'longrines')] : []),
           ...(st.prims.some(p => p.cat === 'chainage') ? [puce('--v3d-chainages', 'chaînages')] : []),
           puce('--v3d-voiles', 'voiles'), puce('--v3d-dalles', 'dalles')].join(' '))
        + ` <span class="v3d-compte">${n('poteaux')} poteaux · ${n('poutres')} poutres · ${n('voiles')} voiles · ${n('dalles')} panneaux · ${st.niveaux.length} niveaux`
        + (n('autres') ? ` · ${n('autres')} élément(s) incliné(s) non calculé(s), en gris` : '')
        + (st.supposee ? ' · hauteur d’étage non lue : 3,00 m supposés pour l’affichage' : '')
        + '</span><span class="v3d-aide">Glisser : tourner · Maj + glisser : déplacer · Molette : zoom · Double-clic : recentrer</span>';
    }

    // ---------- interaction ----------
    let glisse = null;
    cv.addEventListener('pointerdown', (e) => { glisse = { x: e.clientX, y: e.clientY, pan: e.shiftKey || e.button === 1 || e.button === 2 }; cv.setPointerCapture(e.pointerId); });
    cv.addEventListener('pointerup', () => { glisse = null; });
    cv.addEventListener('contextmenu', (e) => e.preventDefault());
    cv.addEventListener('pointermove', (e) => {
      if (glisse) {
        const dx = e.clientX - glisse.x, dy = e.clientY - glisse.y; glisse.x = e.clientX; glisse.y = e.clientY;
        if (glisse.pan) { st.px += dx; st.py += dy; } else { st.yaw -= dx * 0.008; st.pitch = Math.max(-0.05, Math.min(Math.PI / 2 - 0.001, st.pitch + dy * 0.008)); }
        bulle.hidden = true; demander(); return;
      }
      survol(e);
    });
    cv.addEventListener('pointerleave', () => { bulle.hidden = true; });
    cv.addEventListener('wheel', (e) => {
      e.preventDefault();
      const r = cv.getBoundingClientRect(), f = e.deltaY < 0 ? 1.15 : 1 / 1.15;
      const mx = e.clientX - r.left - r.width / 2 - st.px, my = e.clientY - r.top - r.height / 2 - st.py;
      st.zoom = Math.max(0.2, Math.min(40, st.zoom * f)); st.px -= mx * (f - 1); st.py -= my * (f - 1);
      demander();
    }, { passive: false });
    cv.addEventListener('dblclick', () => { st.zoom = 1; st.px = 0; st.py = 0; dessiner(); });
    cv.addEventListener('keydown', (e) => {
      const pas = { ArrowLeft: [0.1, 0], ArrowRight: [-0.1, 0], ArrowUp: [0, -0.1], ArrowDown: [0, 0.1] }[e.key];
      if (pas) { e.preventDefault(); st.yaw += pas[0]; st.pitch = Math.max(-0.05, Math.min(Math.PI / 2 - 0.001, st.pitch + pas[1])); dessiner(); }
      if (e.key === '+' || e.key === '-') { st.zoom *= e.key === '+' ? 1.15 : 1 / 1.15; dessiner(); }
    });

    function survol(e) {
      const r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
      let best = null, bd = 8;
      for (const { p, sp } of st.ecran) {
        let d;
        if (sp.length === 2) {
          const [a, b] = sp, vx = b[0] - a[0], vy = b[1] - a[1], l2 = vx * vx + vy * vy || 1;
          const t = Math.max(0, Math.min(1, ((x - a[0]) * vx + (y - a[1]) * vy) / l2));
          d = Math.hypot(x - a[0] - t * vx, y - a[1] - t * vy);
        } else {
          const cx = sp.reduce((s, q) => s + q[0], 0) / sp.length, cy = sp.reduce((s, q) => s + q[1], 0) / sp.length;
          d = Math.hypot(x - cx, y - cy) * 0.5;
        }
        if (d <= bd) { bd = d; best = p; }
      }
      if (!best) { bulle.hidden = true; return; }
      const e_ = st.etats[best.id];
      bulle.textContent = [best.nom, best.niveau, best.info, e_ ? ETATS[e_.statut] || e_.statut : null].filter(Boolean).join(' · ');
      bulle.style.left = `${x + 12}px`; bulle.style.top = `${y + 10}px`; bulle.hidden = false;
    }

    conteneur.querySelector('.v3d-barre').addEventListener('click', (e) => {
      const b = e.target.closest('[data-vue]'); if (!b) return;
      [st.yaw, st.pitch] = VUES[b.dataset.vue]; st.zoom = 1; st.px = 0; st.py = 0; dessiner();
    });
    conteneur.querySelector('.v3d-barre').addEventListener('change', (e) => {
      if (e.target.dataset.fam) st.fam[e.target.dataset.fam] = e.target.checked;
      if (e.target.hasAttribute('data-niv')) st.nivMax = e.target.value || null;
      dessiner();
    });
    if (window.ResizeObserver) new ResizeObserver(demander).observe(conteneur);
    // changement de thème clair / sombre : redessiner avec les nouveaux jetons
    if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change', dessiner);
    new MutationObserver(dessiner).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-style'] });

    return { charger, etats, dessiner };
  }

  window.Vue3D = Vue3D;
})();
