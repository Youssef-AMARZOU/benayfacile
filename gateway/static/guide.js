/* Bénayfacile — mode Guidé : aides de saisie, verdicts en clair, glossaire, conseils.
   Chargé avant app.js. Tout est affiché dans les deux modes et masqué par CSS
   (html[data-niveau="expert"]), si bien que changer de mode ne recalcule rien. */
'use strict';

/* Aide sous chaque champ : clé = id complet, ou suffixe après le premier « - » (p-fc → fc). */
const AIDE = {
  fc: "Résistance du béton à 28 jours. Courant : 25 MPa (B25) ; 30 MPa pour les éléments plus chargés.",
  fe: "Limite élastique de l'acier : 500 MPa pour les HA FeE500 courants, 400 pour FeE400.",
  enrobage: "Distance du parement à l'acier le plus proche : 30 mm à l'intérieur, 40 à 50 mm en milieu humide ou enterré.",
  'p-a': "Côté de la section. Au moins 25 cm en zone sismique (RPS 2011).",
  'p-b': "Autre côté de la section. Au moins 25 cm en zone sismique (RPS 2011).",
  'p-lf': "Longueur de flambement : 0,7 × hauteur d'étage pour un poteau encastré en pied (BAEL B.8.3,31).",
  'p-nu': "Effort normal de calcul ELU (1,35 G + 1,5 Q), lu dans Robot ou par descente de charges.",
  'p-mx': "Moment autour de l'axe x, à l'ELU. 0 pour un poteau centré.",
  'p-my': "Moment autour de l'axe y, à l'ELU. 0 pour un poteau centré.",
  'pt-b': "Largeur de la poutre, souvent celle du poteau. Au moins 20 cm (RPS 2011).",
  'pt-h': "Hauteur totale. Pré-dimensionnement courant : portée / 12 à portée / 10.",
  'pt-mu': "Moment fléchissant maximal en travée, à l'ELU.",
  'pt-vu': "Effort tranchant maximal à l'ELU, près de l'appui.",
  'pt-ms': "Moment de service (ELS). Laissé vide, il est pris égal à Mu / 1,5.",
  'd-lx': "Petite portée du panneau, entre nus des poutres ou voiles qui le portent.",
  'd-ly': "Grande portée du panneau. Si lx/ly < 0,4, la dalle ne porte que dans le sens lx.",
  'd-h': "Épaisseur. Pré-dimensionnement courant : lx/40 à lx/35 (panneau continu), lx/30 (isolé), 16 cm au moins entre logements.",
  'd-g': "Revêtement, chape, enduit et cloisons ; le poids propre (25 kN/m³ × h) est ajouté automatiquement.",
  'd-q': "Habitation 1,5 ; bureaux 2,5 ; escaliers et circulations 2,5 kN/m² (NF P 06-001).",
  'd-cont': "Rive : panneau en bord de plancher. Intermédiaire : panneau entouré d'autres panneaux.",
  'p-trav': "Portées libres des poutrelles entre nus des poutres porteuses, séparées par « ; ». Une seule valeur : travée isostatique.",
  'p-hourdis': "Hauteur du corps creux : 16 pour un plancher 16+4, 20 pour un 20+5.",
  'p-h0': "Épaisseur de la dalle de compression coulée sur les hourdis.",
  'p-b0': "Largeur de la nervure de la poutrelle, d'après le fabricant ou le coffrage.",
  'p-ent': "Distance entre axes de deux poutrelles voisines, fixée par la largeur du hourdis.",
  'p-gp': "Poids propre du plancher fini (hourdis + poutrelles + dalle de compression), donné par le fabricant des hourdis.",
  'p-g': "Revêtement, chape, enduit sous plafond et cloisons ; le poids propre du plancher est saisi à part.",
  'p-q': "Habitation 1,5 ; bureaux 2,5 ; escaliers et circulations 2,5 kN/m² (NF P 06-001).",
  'p-type': "Préfabriquées : reprise de bétonnage entre poutrelle et dalle de compression, les étriers sont calculés avec k = 0.",
  'b-l': "Longueur en console, du nu de la poutre ou du voile d'appui jusqu'au bord libre.",
  'b-h': "Épaisseur à l'encastrement. Pré-dimensionnement courant : au moins l/10.",
  'b-g': "Revêtement, forme de pente et étanchéité ; le poids propre est ajouté automatiquement.",
  'b-q': "Balcons : 3,5 kN/m² (NF P 06-001).",
  'b-p': "Poids du garde-corps, de l'acrotère ou du muret au bord libre. Un mur maçonné en bout pèse beaucoup : ne l'oubliez pas.",
  'b-hh': "Poussée horizontale des personnes sur la main courante (à prendre selon l'usage).",
  fis: "Préjudiciable pour les éléments exposés aux intempéries ; très préjudiciable en milieu agressif (bord de mer, sol).",
  ns: "Effort normal de service transmis par le poteau (G + Q).",
  nu: "Effort normal ELU. Laissé vide, 1,5 × Ns est utilisé.",
  a: "Dimension du poteau (ou épaisseur du voile) posé sur la semelle.",
  b: "Autre dimension du poteau posé sur la semelle.",
  sig: "Contrainte admissible du sol, donnée par l'étude géotechnique. Ordre de grandeur : 1,5 à 3 bar.",
  sol: "Contrainte admissible du sol, donnée par l'étude géotechnique. Ordre de grandeur : 1,5 à 3 bar.",
  mx: "Moment transmis en pied de poteau ; 0 si la charge est centrée.",
  my: "Moment transmis en pied de poteau ; 0 si la charge est centrée.",
  'v-l': "Longueur du voile en plan.",
  'v-ep': "Épaisseur : au moins 15 cm et he / 20 (RPS 2011).",
  'v-n': "Effort normal ELU repris par le voile.",
  'v-m': "Moment dans le plan du voile, dû surtout au séisme.",
  'v-v': "Effort tranchant dans le plan du voile.",
  's-h': "Hauteur totale du bâtiment au-dessus des fondations.",
  's-l': "Longueur du bâtiment dans la direction étudiée (formule 6.6).",
  's-g': "Charges permanentes totales du bâtiment (poids propre, revêtements, cloisons).",
  's-q': "Charges d'exploitation totales du bâtiment.",
  's-usage': "Fixe ψ, la part des charges d'exploitation comptée dans la masse sismique.",
  's-zv': "Zone de vitesse de la commune (carte RPS 2011, figure 5.2).",
  's-rapport': "Compare les zones d'accélération et de vitesse de la commune (figures 5.2 et 5.3).",
  's-site': "Nature du sol sous le bâtiment, d'après le rapport géotechnique.",
  's-classe': "Importance du bâtiment : classe III pour l'habitation courante.",
  's-sys': "Système qui reprend le séisme ; il fixe le coefficient de comportement K.",
  's-duc': "Niveau de ductilité visé : ND1 pour les petits bâtiments en zone peu sismique.",
  's-tmeth': "Formule de la période propre, ou « T manuelle » pour reprendre la période calculée par Robot.",
  's-tman': "Période fondamentale lue dans l'analyse modale de Robot.",
  's-amort': "5 % pour le béton armé.",
  'rb-chemin': "Chemin complet du fichier, par exemple copié depuis l'Explorateur (Maj + clic droit, « Copier en tant que chemin d'accès »).",
};
function aideChamp(id) {
  if (AIDE[id]) return AIDE[id];
  const suffixe = id.split('-').slice(1).join('-');
  return AIDE[suffixe] || null;
}

/* Glossaire des grandeurs affichées dans les résultats (clé = libellé de la ligne). */
const GLOSSAIRE = {
  'λ (lf/i)': "Élancement. Au-delà de 70, la méthode forfaitaire du BAEL ne s'applique plus.",
  'α': "Réduction de capacité due au flambement.",
  'Nu,lim': "Effort maximal que le poteau peut reprendre avec les aciers choisis.",
  'Rapport Nu/Nu,lim': "Part de la capacité utilisée : doit rester inférieure ou égale à 1.",
  'As calc.': "Section d'acier nécessaire.",
  'MRd (flexion composée)': "Moment que la section peut reprendre sous l'effort normal Nu.",
  'Taux util. moment': "Part de la capacité en flexion utilisée : doit rester inférieure ou égale à 1.",
  'μ': "Moment réduit. Au-delà de μlim, il faudrait des aciers comprimés.",
  'μlim': "Limite au-delà de laquelle la section a besoin d'aciers comprimés.",
  'Z (m)': "Bras de levier entre les aciers tendus et le béton comprimé.",
  'σbc ELS (MPa)': "Compression du béton en service.",
  'σst ELS (MPa)': "Contrainte de l'acier en service, limitée selon la fissuration.",
  'σst OK ?': "L'acier reste-t-il sous sa limite en service ?",
  'τu (MPa)': "Contrainte de cisaillement, comparée à sa limite.",
  'At (cm²/m)': "Section d'armatures transversales (cadres) par mètre.",
  'σmax (bar)': "Pression maximale sous la semelle, à comparer à la contrainte admissible du sol.",
  'σmin (bar)': "Pression minimale : négative, la semelle se soulève d'un côté.",
  'Poinçonnement': "Le poteau ne doit pas percer la semelle.",
  'σmax (MPa)': "Compression maximale dans le voile.",
  'Compression OK ?': "La compression reste-t-elle sous 0,6 fc28 ?",
  'As rive (cm²)': "Aciers concentrés aux extrémités du voile.",
  'S': "Coefficient de site (nature du sol).", 'I': "Coefficient d'importance du bâtiment.",
  'K': "Coefficient de comportement : capacité de la structure à dissiper l'énergie.",
  'D': "Facteur d'amplification dynamique, lu sur le spectre RPS.",
  'T (s)': "Période fondamentale du bâtiment.",
  'F — effort à la base (kN)': "Effort horizontal total dû au séisme, à répartir sur les niveaux.",
};

/* Conseils pour les problèmes du calcul en lot (motif du message → action). */
const CONSEILS = [
  [/Nu\/Nu,lim/, "Augmentez la section du poteau ou fc28."],
  [/5 % B/, "Agrandissez la section du poteau : l'acier nécessaire dépasse 5 % du béton."],
  [/λ > 70/, "Réduisez la longueur de flambement ou augmentez la section."],
  [/flexion composée/, "Augmentez la section ou réduisez l'excentricité de la charge."],
  [/σst ELS/, "Augmentez la hauteur de la poutre ou la section d'acier."],
  [/τu/, "Augmentez la largeur ou la hauteur de la section."],
  [/aciers comprimés/, "Augmentez la hauteur de la poutre pour éviter les aciers comprimés."],
  [/poinçonnement/, "Augmentez l'épaisseur H de la semelle ou fc28."],
  [/traction sous la semelle/, "Agrandissez la semelle ou recentrez la charge."],
  [/0,6 fc28/, "Augmentez l'épaisseur du voile ou fc28."],
  [/donnée manquante/, "Complétez la donnée dans Robot (ou dans le modèle), puis relancez le calcul."],
  [/doit être/, "Corrigez la valeur dans Robot, elle est hors du domaine de calcul."],
];
function conseil(probleme) {
  const c = CONSEILS.find(([re]) => re.test(probleme));
  return c ? c[1] : null;
}

/* Verdict en clair après un calcul unitaire. */
function boiteVerdict(ok, phrase, actions = []) {
  return `<div class="guide-verdict ${ok ? 'ok' : 'ko'}" role="status">
    <strong>${ok ? 'Vérifié' : 'Non vérifié'}</strong> <span>${phrase}</span>
    ${actions.length ? `<p class="que-faire">Que faire : ${actions.join(' ')}</p>` : ''}</div>`;
}
const fmt = (v, n = 0) => (typeof v === 'number' ? v.toLocaleString('fr-FR', { maximumFractionDigits: n }) : v);

const VERDICTS = {
  poteau(r) {
    const tm = r.flexion_composee?.taux_utilisation_moment;
    const pb = [];
    if ((r.nu_rapport ?? 0) > 1) pb.push("Augmentez la section ou fc28.");
    if (r.warn) pb.push("Agrandissez la section : l'acier nécessaire dépasse 5 % du béton.");
    if (r.applicable_b841 === false) pb.push("Réduisez la longueur de flambement ou augmentez la section.");
    if (r.flexion_composee?.capacite_insuffisante) pb.push("Augmentez la section : sous cet effort normal, elle ne reprend plus aucun moment.");
    else if (typeof tm === 'number' && tm > 1) pb.push("Augmentez la section ou réduisez les moments.");
    const pct = r.nu_rapport != null ? Math.round(r.nu_rapport * 100) : null;
    return boiteVerdict(!pb.length,
      `Le poteau reçoit ${fmt(r.nu_kn)} kN pour une capacité de ${fmt(r.nu_lim_kn_avec_as_fournie)} kN${pct != null ? ` (${pct} % utilisés)` : ''}. Ferraillage : ${r.ferraillage?.choix || '—'}.`, pb);
  },
  poutre(r) {
    const pb = [];
    if (r.els && !r.els.sigma_st_ok) pb.push("Augmentez la hauteur ou la section d'acier (contrainte de service de l'acier dépassée).");
    if (r.effort_tranchant && !r.effort_tranchant.tau_u_ok) pb.push("Augmentez la largeur ou la hauteur (cisaillement trop élevé).");
    if (r.mode && r.mode !== 'simple') pb.push("Augmentez la hauteur pour éviter les aciers comprimés.");
    return boiteVerdict(!pb.length,
      `Aciers en partie basse : ${r.ferraillage?.choix || '—'}. Cadres : ${fmt(r.effort_tranchant?.at_cm2_par_m, 2)} cm² par mètre.`, pb);
  },
  semelle(r) {
    const pb = [];
    if (!r.poinconnement?.ok) pb.push("Augmentez l'épaisseur H ou fc28 (poinçonnement).");
    if (r.sigma_min_bar < 0) pb.push("Agrandissez la semelle ou recentrez la charge (soulèvement).");
    return boiteVerdict(!pb.length,
      `Semelle de ${fmt(r.A_m, 2)} × ${fmt(r.B_m, 2)} m, épaisseur ${fmt(r.H_m, 2)} m. Nappe X : ${r.acier_x}, nappe Y : ${r.acier_y}.`, pb);
  },
  voile(r) {
    const pb = [];
    if (!r.compression_ok) pb.push("Augmentez l'épaisseur ou fc28 (compression trop élevée).");
    if (!r.tau_ok) pb.push("Augmentez l'épaisseur (cisaillement trop élevé).");
    return boiteVerdict(!pb.length,
      `Compression maximale ${fmt(r.sigma_max_mpa, 2)} MPa${r.as_rive_cm2 ? `, aciers de rive ${fmt(r.as_rive_cm2, 2)} cm²` : ''}.`, pb);
  },
  dalle(r) {
    const pb = (r.remarques || []).filter(x => !/élancée/.test(x)).map(x => x.replace(/^[a-z_]+ : /, ''));
    return boiteVerdict(r.verifie,
      `Dalle ${r.un_sens ? 'portant dans un seul sens' : 'portant dans les deux sens'}. Travée x : ${r.resultats?.x_travee?.ferraillage?.choix || '—'} ; travée y : ${r.resultats?.y_travee?.ferraillage?.choix || '—'} ; chapeaux : ${r.resultats?.appuis?.ferraillage?.choix || '—'}.`, pb);
  },
  balcon(r) {
    const pb = (r.remarques || []).filter(x => !/élancé/.test(x));
    return boiteVerdict(r.verifie,
      `Moment d'encastrement ${fmt(r.mu_knm, 2)} kN·m/m. Aciers principaux en haut : ${r.nappe_superieure?.ferraillage?.choix || '—'}, prolongés de ${fmt(r.prolongement_chapeaux_m, 2)} m dans la dalle intérieure.`, pb);
  },
  plancher(r) {
    const pb = r.remarques || [];
    const t = r.travees || [];
    return boiteVerdict(r.verifie,
      `Plancher ${r.designation}, ${t.length} travée${t.length > 1 ? 's' : ''} (méthode ${r.methode}). Aciers bas : ${t.map(x => x.ferraillage?.choix || '—').join(' / ')} ; dalle de compression : ${r.dalle_compression?.choix || '—'}.`, pb);
  },
  sismique(r) {
    const part = r.W_kn ? Math.round(100 * r.F_base_kn / r.W_kn) : null;
    return boiteVerdict(true,
      `Effort sismique à la base : ${fmt(r.F_base_kn)} kN${part != null ? `, soit ${part} % du poids sismique` : ''}. Période T = ${fmt(r.T_s, 2)} s.`);
  },
};
