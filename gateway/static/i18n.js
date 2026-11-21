/* Bénayfacile — interface en français (langue source) ou en anglais.

   Le français reste la langue du code et des livrables (note de calcul, Excel, plans DXF :
   documents réglementaires au Maroc). En anglais, l'interface est traduite au rendu :
   chaque texte affiché est cherché dans EN (correspondance exacte) puis dans MOTIFS
   (phrases contenant des valeurs). Le texte français d'origine est conservé, ce qui
   permet de rebasculer instantanément. Les contenus saisis par l'utilisateur (noms de
   projet, d'éléments) sont exclus via translate="no". */
'use strict';

const EN = new Map(Object.entries({
  // structure, navigation, réglages
  "Aller au contenu": "Skip to content", "Modules de calcul": "Design modules",
  "Projet": "Project", "Projet Robot": "Robot project", "Éléments": "Members", "Poteau": "Column", "Poutre": "Beam",
  "Semelles isolées": "Pad footings", "Semelles filantes": "Strip footings", "Voiles": "Shear walls", "Bâtiment": "Building",
  "Vérification sismique": "Seismic check", "Livrables": "Deliverables", "Synthèse de calcul": "Calculation summary",
  "Réglages": "Settings", "Votre bureau": "Your office", "Maître d'ouvrage": "Client", "Indice": "Revision",
  "Sans titre": "Untitled", "Les textes officiels BAEL et RPS font foi.": "The official BAEL and RPS texts prevail.",
  "Affichage": "Display", "Style": "Style", "Maroc": "Moroccan", "Stade": "Stadium", "Plan": "Blueprint", "Niveau": "Level", "Guidé": "Guided", "Expert": "Expert", "Thème": "Theme", "Auto": "Auto",
  "Clair": "Light", "Sombre": "Dark", "Taille du texte": "Text size", "Langue": "Language", "Normale": "Normal",
  "Grande": "Large", "Très grande": "Extra large", "Suit le réglage de Windows": "Follows the Windows setting",
  "Aides sous les champs, verdicts en clair, conseils": "Help under fields, plain-language verdicts, advice",
  "Écran dense, détail JSON, raccourcis clavier": "Dense screen, JSON detail, keyboard shortcuts",
  "Entrée : calculer. Alt + 1 à 9 : changer de module.": "Enter: calculate. Alt + 1 to 9: switch module.",
  "Moteur de calcul prêt": "Calculation engine ready", "vérification des services…": "checking services…",
  "Passerelle injoignable. Relancez Bénayfacile.": "Gateway unreachable. Restart Bénayfacile.",
  // projet Robot
  "Lecture du modèle Robot Structural Analysis et calcul de tous les éléments : poteaux, poutres, semelles, voiles (BAEL 91 rév. 99)":
    "Reads the Robot Structural Analysis model and designs every member: columns, beams, footings, shear walls (BAEL 91 rev. 99)",
  "Modèle": "Model",
  "Objet": "Purpose",
  "Architecte": "Architect",
  "Bureau de contrôle": "Control office",
  "Laboratoire (étude géotechnique)": "Laboratory (geotechnical study)",
  "Phase": "Stage",
  "Esquisse": "Sketch",
  "APS": "Outline design",
  "APD": "Detailed design",
  "Autorisation de construire": "Building permit",
  "DCE": "Tender documents",
  "Exécution": "Construction",
  "La note suit la présentation d’un bureau d’études : page de garde et intervenants, règlements, hypothèses, étude sismique, ferraillage par type avec un exemple de calcul détaillé, quantités, conclusion et réserves.": "The report follows an engineering office's layout: cover page and parties, codes, assumptions, seismic study, reinforcement by type with a detailed worked example, quantities, conclusion and reservations.",
  "Développé par M. Youssef AMARZOU — Digital & AI Engineer": "Developed by Mr. Youssef AMARZOU — Digital & AI Engineer",
  "Du modèle Robot au plan de ferraillage": "From the Robot model to the reinforcement drawings",
  "Lecture du modèle, calcul BAEL 91 / RPS 2011, note de calcul, Excel et plans DXF": "Model reading, BAEL 91 / RPS 2011 design, calculation report, Excel and DXF drawings",
  "Importer un classeur Excel": "Import an Excel workbook",
  "Sans Robot :": "Without Robot:",
  "Compléments": "Add-ons",
  "Dalles et balcons": "Slabs and balconies", "Planchers à corps creux": "Hollow-block floors",
  "Dalle pleine": "Solid slab",
  "Balcon en porte-à-faux": "Cantilever balcony",
  "Calculer la dalle": "Calculate the slab",
  "Calculer le balcon": "Calculate the balcony",
  "Résultat — dalle": "Result — slab",
  "Résultat — balcon": "Result — balcony",
  "Continuité du panneau": "Panel continuity",
  "Panneau de rive": "Edge panel",
  "Panneau intermédiaire": "Interior panel",
  "Panneau isolé (isostatique)": "Single panel (simply supported)",
  "Nappe supérieure (principale)": "Top layer (main)",
  "Chapeaux sur appuis": "Top bars over supports",
  "Logiciels sur ce poste": "Software on this computer",
  "logiciels dont Bénayfacile se sert, détectés sur ce poste": "software Bénayfacile relies on, detected on this computer",
  "Vérifier à nouveau": "Check again",
  "Installé": "Installed",
  "Non installé": "Not installed",
  "voir les compléments": "see the add-ons",
  "Logiciels utiles (Robot, tableur, lecteur DXF) :": "Useful software (Robot, spreadsheet, DXF viewer):",
  "Modèle Excel de Bénayfacile": "Bénayfacile Excel template",
  "Tous les compléments sont présents sur ce poste.": "All add-ons are present on this computer.",
  "Bénayfacile n'installe rien lui-même : les boutons ouvrent la page officielle de chaque éditeur dans votre navigateur. Après une installation, cliquez sur « Vérifier à nouveau ».": "Bénayfacile installs nothing itself: the buttons open each publisher's official page in your browser. After installing, click “Check again”.",
  "téléchargez le modèle Excel": "download the Excel template",
  ", remplissez-le, puis importez-le.": ", fill it in, then import it.",
  "Classeur Excel": "Excel workbook",
  "Hypothèses de l'import": "Import assumptions",
  "Données saisies dans le classeur importé ; efforts pris en valeur absolue.": "Data entered in the imported workbook; forces taken as absolute values.",
  "lf = 0,7 × hauteur d'étage quand la colonne lf est vide.": "lf = 0.7 × storey height when the lf column is empty.",
  "Pas de feuille Trame : le plan de fondation DXF ne sera pas dessiné (les détails le seront).": "No Trame sheet: the DXF foundation plan will not be drawn (the details will).",
  "Ouvrir un fichier Robot (.rtd)": "Open a Robot file (.rtd)",
  "Lire le projet déjà ouvert dans Robot": "Read the project already open in Robot",
  "Chemin du fichier Robot (.rtd)": "Robot file path (.rtd)",
  "Ouvrir dans Robot": "Open in Robot",
  "Choisissez votre fichier Robot : Bénayfacile le fait ouvrir et calculer par Robot, puis lit tous les éléments. Robot Structural Analysis doit être installé sur ce poste.": "Choose your Robot file: Bénayfacile has Robot open and analyse it, then reads every member. Robot Structural Analysis must be installed on this PC.",
  "Ouverture du projet dans Robot et analyse… Cela peut prendre quelques minutes.": "Opening the project in Robot and running the analysis… This can take a few minutes.",
  "Chemin complet du fichier, par exemple copié depuis l'Explorateur (Maj + clic droit, « Copier en tant que chemin d'accès »).": "Full file path, e.g. copied from File Explorer (Shift + right-click, “Copy as path”).", "Lire le modèle Robot": "Read the Robot model", "Essayer avec l'exemple R+4": "Try the G+4 example",
  "Ouvrez votre projet dans Robot et lancez l'analyse, puis lisez le modèle.": "Open your project in Robot and run the analysis, then read the model.",
  "Robot Structural Analysis n'est pas détecté. Ouvrez votre projet dans Robot, lancez l'analyse, puis réessayez.":
    "Robot Structural Analysis was not detected. Open your project in Robot, run the analysis, then try again.",
  "Pour découvrir Bénayfacile sans Robot, utilisez « Essayer avec l'exemple R+4 ».": "To explore Bénayfacile without Robot, use “Try the G+4 example”.",
  "Lecture du modèle…": "Reading the model…", "Source": "Source", "Niveaux": "Levels", "Poteaux": "Columns", "Poutres": "Beams",
  "Semelles": "Footings", "Exemple de démonstration R+4": "G+4 demonstration example", "Robot (lecture COM)": "Robot (COM link)",
  "Hypothèses de la simulation": "Simulation assumptions", "Hypothèses de la lecture": "Reading assumptions",
  "Poteaux : descente de charges par surfaces d'influence, ELU 1,35G + 1,5Q, lf = 0,7·l0.": "Columns: load take-down by tributary areas, ULS 1.35G + 1.5Q, lf = 0.7·l0.",
  "Poutres : M = pl²/10 en travée, V = 1,15·pl/2 (continuité forfaitaire).": "Beams: M = pl²/10 at mid-span, V = 1.15·pl/2 (simplified continuity).",
  "Semelles : efforts en pied des poteaux du RDC.": "Footings: forces at the base of the ground-floor columns.",
  "Voiles : efforts sismiques forfaitaires de démonstration.": "Shear walls: simplified demonstration seismic forces.",
  "Efforts : enveloppe des valeurs absolues sur 5 sections par barre.": "Forces: envelope of absolute values at 5 sections per bar.",
  "lf = 0,7·l0 pour les poteaux (à adapter si nécessaire).": "lf = 0.7·l0 for columns (adjust if needed).",
  "Matériaux et sol": "Materials and soil", "Fissuration": "Cracking", "Peu préjudiciable": "Non-detrimental",
  "Préjudiciable": "Detrimental", "Très préjudiciable": "Highly detrimental", "Calculer tout le modèle": "Design the whole model",
  "Envoyer à la synthèse": "Send to summary", "Exporter en Excel": "Export to Excel", "Plans de ferraillage (DXF)": "Reinforcement drawings (DXF)",
  "Résultats": "Results", "Lisez le modèle, puis lancez le calcul : chaque élément est dimensionné et vérifié.": "Read the model, then run the design: every member is sized and checked.",
  "éléments": "members", "vérifiés": "verified", "à revoir": "to review", "incomplets": "incomplete", "À revoir seulement": "To review only",
  "Élément": "Member", "Section": "Section", "Ferraillage": "Reinforcement", "État": "Status", "Vérifié": "Verified", "À revoir": "To review",
  "Incomplet": "Incomplete", "Erreur": "Error", "Non vérifié": "Not verified",
  "Aucun élément à revoir dans cette famille.": "No member to review in this group.", "Tout le modèle": "Whole model",
  "Création du classeur…": "Creating the workbook…", "Dessin des plans…": "Drawing…", "Classeur enregistré dans": "Workbook saved in",
  "Portée (m)": "Span (m)", "L × e": "L × t", "A × B (m)": "A × B (m)", "Acier X / Y": "Steel X / Y",
  // en-têtes et libellés de formulaires
  "Données": "Input", "Résultat": "Result", "Calculer": "Calculate", "Ajouter à la synthèse": "Add to summary",
  "Saisissez les données puis lancez le calcul.": "Enter the input, then run the calculation.", "Calcul en cours…": "Calculating…",
  "BAEL 91 rév. 99 — B.8.4,1 compression centrée (Nu,lim = α·[Br·fc28/0,9γb + A·fe/γs]) + flexion composée numérique":
    "BAEL 91 rev. 99 — B.8.4,1 axial compression (Nu,lim = α·[Br·fc28/0.9γb + A·fe/γs]) + numerical combined bending",
  "lf — longueur de flambement (m)": "lf — buckling length (m)", "Nu — effort normal ELU (kN)": "Nu — ULS axial force (kN)",
  "Enrobage (mm)": "Concrete cover (mm)",
  "BAEL 91 rév. 99 — flexion simple ELU (diagramme rectangulaire 0,8 yu) + ELS (n=15) + effort tranchant":
    "BAEL 91 rev. 99 — ULS simple bending (rectangular block 0.8 yu) + SLS (n = 15) + shear",
  "Mu (kN.m)": "Mu (kN.m)", "Vu (kN)": "Vu (kN)", "Ms service (optionnel) (kN.m)": "Ms service (optional) (kN.m)",
  "Peu préjudiciable (σst ≤ 2/3 fe)": "Non-detrimental (σst ≤ 2/3 fe)", "Préjudiciable (A.4.5,33)": "Detrimental (A.4.5,33)",
  "Très préjudiciable (A.4.5,34)": "Highly detrimental (A.4.5,34)", "Semelles Isolées": "Pad Footings", "Semelles Filantes": "Strip Footings",
  "BAEL/BE — méthode des bielles (semelle rigide, h ≥ (A−a)/4) — As = Nu·(A−a)/(8·d·σs)": "BAEL — strut-and-tie method (rigid footing, h ≥ (A−a)/4) — As = Nu·(A−a)/(8·d·σs)",
  "BAEL/BE — méthode des bielles (semelle rigide, h ≥ (A−a)/4) — As = Nu·(A−a)/(8·d·σs) — par mètre linéaire": "BAEL — strut-and-tie method (rigid footing, h ≥ (A−a)/4) — As = Nu·(A−a)/(8·d·σs) — per linear metre",
  "Ns — effort service (kN)": "Ns — service axial force (kN)", "Nu — ELU (optionnel, défaut 1.5·Ns) (kN)": "Nu — ULS (optional, default 1.5·Ns) (kN)",
  "Poteau/voile a (cm)": "Column/wall a (cm)", "Poteau/voile b (cm)": "Column/wall b (cm)", "σsol admissible (bar)": "Allowable soil pressure (bar)",
  "Voiles de Contreventement": "Shear Walls",
  "BAEL B.8.4 / pratique BET — σ = N/(e·L) ± 6M/(e·L²) ; rive dimensionnée si section partiellement comprimée":
    "BAEL B.8.4 / office practice — σ = N/(t·L) ± 6M/(t·L²); boundary zones designed if the section is partly in tension",
  "L — longueur du voile (m)": "L — wall length (m)", "ép. (cm)": "thickness (cm)", "N — effort normal ELU (kN)": "N — ULS axial force (kN)",
  "V — effort tranchant ELU (kN)": "V — ULS shear force (kN)", "Vérification Sismique": "Seismic Check",
  "RPS 2000 — version 2011 · approche statique équivalente (F = υ·S·D·I·W/K, eq. 6.1)": "RPS 2000 — 2011 version · equivalent static method (F = υ·S·D·I·W/K, eq. 6.1)",
  "Modèle Robot": "Robot model", "Charger le modèle Robot": "Load the Robot model", "Données sismiques": "Seismic input",
  "H — hauteur totale (m)": "H — total height (m)", "L — longueur contreventement (m)": "L — bracing length (m)",
  "G — charges permanentes (kN)": "G — dead loads (kN)", "Q — charges d'exploitation (kN)": "Q — imposed loads (kN)", "Usage (ψ)": "Occupancy (ψ)",
  "Habitation / administratif (ψ=0.20)": "Residential / offices (ψ = 0.20)", "Usage périodique public (ψ=0.30)": "Periodic public use (ψ = 0.30)",
  "Restaurants / salles de classe (ψ=0.40)": "Restaurants / classrooms (ψ = 0.40)", "Longue durée — entrepôts… (ψ=1.00)": "Long-term — storage… (ψ = 1.00)",
  "Zone de vitesse υ (Tableau 5.1)": "Velocity zone υ (Table 5.1)", "Rapport Za / Zv (Fig. 5.3 vs Fig. 5.2)": "Za / Zv ratio (Fig. 5.3 vs Fig. 5.2)",
  "Site (Tableau 5.2)": "Site (Table 5.2)", "S1 — Rocher / sol ferme < 30 m (S=1.0)": "S1 — Rock / firm soil < 30 m (S = 1.0)",
  "S2 — Sol ferme ≥ 30 m / meuble < 30 m (S=1.2)": "S2 — Firm soil ≥ 30 m / loose < 30 m (S = 1.2)",
  "S3 — Sol meuble ≥ 15 m / mou < 10 m (S=1.4)": "S3 — Loose soil ≥ 15 m / soft < 10 m (S = 1.4)", "S4 — Sol mou ≥ 10 m (S=1.8)": "S4 — Soft soil ≥ 10 m (S = 1.8)",
  "S5 — Conditions spéciales (à justifier)": "S5 — Special conditions (to be justified)", "Classe (Tableau 3.1)": "Class (Table 3.1)",
  "Classe I — bâtiments stratégiques / grande importance (I=1.3)": "Class I — strategic / high-importance buildings (I = 1.3)",
  "Classe II — grand public (I=1.2)": "Class II — public buildings (I = 1.2)", "Classe III — bâtiments ordinaires (I=1.0)": "Class III — ordinary buildings (I = 1.0)",
  "Système de contreventement (Tableau 3.3)": "Lateral system (Table 3.3)", "Portiques en béton armé": "RC frames", "Voile + Portique": "Wall + frame",
  "Voiles couplés": "Coupled walls", "Acier — portiques à nœuds rigides": "Steel — moment frames", "Ossature contreventée (acier)": "Braced frame (steel)",
  "Ductilité": "Ductility", "ND1 — faible ductilité": "ND1 — low ductility", "ND2 — ductilité moyenne": "ND2 — medium ductility",
  "ND3 — grande ductilité": "ND3 — high ductility", "Évaluation de T": "Period T", "T manuelle (Robot)": "Manual T (Robot)",
  "T manuelle (s) — si « manuelle »": "Manual T (s) — if “manual”", "Amortissement (%)": "Damping (%)", "Calculer la force sismique": "Calculate the seismic force",
  "Répartition verticale": "Vertical distribution", "Acrotère": "Parapet", "Masse participante (%)": "Participating mass (%)",
  "T ≤ 2 s et H ≤ 60 m : OK": "T ≤ 2 s and H ≤ 60 m: OK",
  "Approche statique équivalente applicable si bâtiment régulier (art. 3.2/4.3).": "Equivalent static method applies to regular buildings (art. 3.2/4.3).",
  "Si analyse modale faite : V_modal ≥ 0,90 × V_SE (art. 6.4.1).": "If a modal analysis is run: V_modal ≥ 0.90 × V_SE (art. 6.4.1).",
  "Modèle SIMULÉ (Robot non piloté). Pour un modèle réel : lancer Robot, ouvrir le projet, puis POST /extract.": "SIMULATED model (Robot not connected). For a real model: start Robot, open the project, then read it again.",
  "Chargez le modèle Robot ou saisissez les données, puis calculez la force sismique.": "Load the Robot model or enter the input, then calculate the seismic force.",
  // synthèse, bureau, aperçu
  "Synthèse de Calcul": "Calculation Summary", "Note de calcul HTML (page de garde, références BAEL/RPS, calculs, audit arithmétique) + plan DXF A3":
    "HTML calculation report (cover page, BAEL/RPS references, calculations, arithmetic audit) + A3 DXF drawing",
  "Client": "Client", "Site": "Site", "Charger l'exemple R+4": "Load the G+4 example", "Éléments collectés": "Collected members",
  "Générer la note de calcul": "Generate the calculation report", "Sauvegarder la note (serveur /output)": "Save the report (output folder)",
  "Générer le plan DXF (semelles)": "Generate the DXF drawing (footings)", "Télécharger le DXF": "Download the DXF", "Aperçu": "Preview",
  "La note assemble la page de garde, les références normatives, les hypothèses, le modèle Robot, la vérification sismique, chaque élément calculé, un audit arithmétique ligne à ligne et les alertes.":
    "The report assembles the cover page, code references, assumptions, the Robot model, the seismic check, every designed member, a line-by-line arithmetic audit and warnings.",
  "Aucun élément pour l’instant. Calculez un élément, puis « Ajouter à la synthèse ». Ou chargez le scénario démo R+4.": "No member yet. Design a member, then “Add to summary”. Or load the G+4 example.",
  "Génération de la note de calcul…": "Generating the calculation report…", "Sauvegarde…": "Saving…", "Génération du plan DXF…": "Generating the DXF drawing…",
  "Note de calcul affichée. Bouton « Imprimer / PDF » pour l'enregistrer en PDF.": "Calculation report shown. Use “Print / PDF” to save it as PDF.",
  "Plan DXF généré (calques AXES/COFFRAGE/ACIER_LONG/CADRES/COTATION/CARTOUCHE).": "DXF drawing generated (layers AXES/COFFRAGE/ACIER_LONG/CADRES/COTATION/CARTOUCHE).",
  "Scénario démo chargé : Robot (simulation) + sismique + 1 poteau + 1 poutre + 1 semelle + 1 voile. Générez la note ou le DXF.":
    "Example loaded: Robot (simulation) + seismic + 1 column + 1 beam + 1 footing + 1 wall. Generate the report or the DXF.",
  "Données de votre bureau": "Your Office Details", "reprises sur la page de garde de la note de calcul et dans le cartouche DXF": "shown on the report cover page and in the DXF title block",
  "Identité": "Identity", "Nom du bureau": "Office name", "Adresse": "Address", "Téléphone": "Phone", "Email": "Email",
  "Ingénieur chargé du projet": "Engineer in charge", "Enregistrer": "Save", "Ces données sont enregistrées dans": "These details are stored in",
  ". Les champs « logo » et « cachet » peuvent être ajoutés au format base64 (clés logo_base64 / cachet_base64).": ". “Logo” and “stamp” can be added in base64 (keys logo_base64 / cachet_base64).",
  "Modifiez les valeurs puis enregistrez.": "Edit the values, then save.", "enregistrement…": "saving…",
  "Données enregistrées. Elles apparaîtront dans la prochaine note de calcul et le prochain plan DXF.": "Details saved. They will appear in the next report and DXF drawing.",
  "Note de calcul": "Calculation report", "Imprimer / PDF": "Print / PDF", "Fermer": "Close", "Note + plan DXF": "Report + DXF drawing",
  "Page de garde et cartouche": "Cover page and title block", "Méthode des bielles": "Strut-and-tie method", "BAEL 91 · flexion simple": "BAEL 91 · simple bending",
  "Exemple — immeuble R+4": "Example — G+4 building",
  "Exemple de démonstration — immeuble R+4": "Demonstration example — G+4 building", "Démonstration": "Demonstration", "Détail brut (JSON)": "Raw detail (JSON)",
  // résultats
  "λ (lf/i)": "λ (lf/i)", "Rapport Nu/Nu,lim": "Nu/Nu,lim ratio", "As calc.": "As req.", "MRd (flexion composée)": "MRd (combined bending)",
  "Taux util. moment": "Moment utilisation", "As calc. (cm²)": "As req. (cm²)", "As retenue (cm²)": "As provided (cm²)", "σst OK ?": "σst OK?",
  "At (cm²/m)": "Asw (cm²/m)", "Poids (T)": "Weight (t)", "Acier X": "Steel X", "Acier Y": "Steel Y", "Poinçonnement": "Punching shear",
  "As par mètre linéaire": "As per linear metre", "Mode": "Mode", "Compression OK ?": "Compression OK?", "As rive (cm²)": "As boundary (cm²)",
  "As vert. min (cm²/m)": "As vert. min (cm²/m)", "As horiz. min (cm²/m)": "As horiz. min (cm²/m)", "F — effort à la base (kN)": "F — base shear (kN)",
  "ω (modes supérieurs)": "ω (higher modes)", "OUI": "YES", "NON": "NO", "NON VÉRIFIÉ": "NOT VERIFIED",
  "section entièrement comprimée": "section fully in compression", "section partiellement comprimée — aciers de rive dimensionnés": "section partly in tension — boundary steel designed",
  "λ > 35 : ne retenir que les armatures augmentant la rigidité (les plus éloignées du plan de flambement).": "λ > 35: count only the bars that increase stiffness (furthest from the buckling plane).",
  "Voile : vérifier aussi effort tranchant RPS (art. 7.2.2.2 — ω) et dispositions ND2/ND3 (zones critiques, art. 7.3.1).": "Wall: also check RPS shear (art. 7.2.2.2 — ω) and ND2/ND3 detailing (critical zones, art. 7.3.1).",
  "Contrainte de service en traction sous la semelle : risque de soulèvement — justification spéciale requise.": "Tension under the footing at service: uplift risk — special justification required.",
  "Poinçonnement non vérifié : augmenter H ou fc28.": "Punching shear not verified: increase H or fc28.",
  // conseils des verdicts (mode Guidé)
  "Augmentez la section ou fc28.": "Increase the section or fc28.",
  "Agrandissez la section : l'acier nécessaire dépasse 5 % du béton.": "Enlarge the section: the steel needed exceeds 5% of the concrete.",
  "Réduisez la longueur de flambement ou augmentez la section.": "Reduce the buckling length or increase the section.",
  "Augmentez la section ou réduisez les moments.": "Increase the section or reduce the moments.",
  "Augmentez la hauteur ou la section d'acier (contrainte de service de l'acier dépassée).": "Increase the depth or the steel area (steel service stress exceeded).",
  "Augmentez la largeur ou la hauteur (cisaillement trop élevé).": "Increase the width or depth (shear too high).",
  "Augmentez la hauteur pour éviter les aciers comprimés.": "Increase the depth to avoid compression steel.",
  "Augmentez l'épaisseur H ou fc28 (poinçonnement).": "Increase the thickness H or fc28 (punching shear).",
  "Agrandissez la semelle ou recentrez la charge (soulèvement).": "Enlarge the footing or centre the load (uplift).",
  "Augmentez l'épaisseur ou fc28 (compression trop élevée).": "Increase the thickness or fc28 (compression too high).",
  "Augmentez l'épaisseur (cisaillement trop élevé).": "Increase the thickness (shear too high).",
}));

// aides et glossaire du mode Guidé
[
  [AIDE.fc, "Concrete strength at 28 days. Typical: 25 MPa (C25); 30 MPa for more heavily loaded members."],
  [AIDE.fe, "Steel yield strength: 500 MPa for the usual FeE500 bars, 400 for FeE400."],
  [AIDE.enrobage, "Distance from the face to the nearest bar: 30 mm indoors, 40 to 50 mm when damp or buried."],
  [AIDE['p-a'], "Section side. At least 25 cm in seismic zones (RPS 2011)."], [AIDE['p-b'], "Other section side. At least 25 cm in seismic zones (RPS 2011)."],
  [AIDE['p-lf'], "Buckling length: 0.7 × storey height for a column fixed at its base (BAEL B.8.3,31)."],
  [AIDE['p-nu'], "ULS design axial force (1.35 G + 1.5 Q), from Robot or a load take-down."],
  [AIDE['p-mx'], "ULS moment about the x axis. 0 for a concentric column."], [AIDE['p-my'], "ULS moment about the y axis. 0 for a concentric column."],
  [AIDE['pt-b'], "Beam width, often the column width. At least 20 cm (RPS 2011)."],
  [AIDE['pt-h'], "Total depth. Typical preliminary sizing: span / 12 to span / 10."],
  [AIDE['pt-mu'], "Maximum ULS mid-span bending moment."], [AIDE['pt-vu'], "Maximum ULS shear force, near the support."],
  [AIDE['pt-ms'], "Service (SLS) moment. Left empty, Mu / 1.5 is used."],
  [AIDE.fis, "Detrimental for members exposed to weather; highly detrimental in aggressive environments (sea front, soil)."],
  [AIDE.ns, "Service axial force carried by the column (G + Q)."], [AIDE.nu, "ULS axial force. Left empty, 1.5 × Ns is used."],
  [AIDE.a, "Size of the column (or wall thickness) bearing on the footing."], [AIDE.b, "Other size of the column bearing on the footing."],
  [AIDE.sig, "Allowable soil pressure, from the geotechnical report. Typically 1.5 to 3 bar."],
  [AIDE.mx, "Moment at the column base; 0 if the load is concentric."],
  [AIDE['v-l'], "Wall length in plan."], [AIDE['v-ep'], "Thickness: at least 15 cm and he / 20 (RPS 2011)."],
  [AIDE['v-n'], "ULS axial force carried by the wall."], [AIDE['v-m'], "In-plane moment, mostly from earthquake."], [AIDE['v-v'], "In-plane shear force."],
  [AIDE['s-h'], "Total building height above the foundations."], [AIDE['s-l'], "Building length in the direction studied (formula 6.6)."],
  [AIDE['s-g'], "Total dead loads of the building (self-weight, finishes, partitions)."], [AIDE['s-q'], "Total imposed loads of the building."],
  [AIDE['s-usage'], "Sets ψ, the share of imposed loads counted in the seismic mass."],
  [AIDE['s-zv'], "Velocity zone of the municipality (RPS 2011 map, figure 5.2)."],
  [AIDE['s-rapport'], "Compares the municipality's acceleration and velocity zones (figures 5.2 and 5.3)."],
  [AIDE['s-site'], "Ground type under the building, from the geotechnical report."],
  [AIDE['s-classe'], "Building importance: class III for ordinary housing."],
  [AIDE['s-sys'], "System resisting the earthquake; it sets the behaviour factor K."],
  [AIDE['s-duc'], "Target ductility: ND1 for small buildings in low-seismicity zones."],
  [AIDE['s-tmeth'], "Period formula, or “manual T” to use the period computed by Robot."],
  [AIDE['s-tman'], "Fundamental period from Robot's modal analysis."], [AIDE['s-amort'], "5% for reinforced concrete."],
  [GLOSSAIRE['λ (lf/i)'], "Slenderness. Above 70, the BAEL simplified method no longer applies."],
  [GLOSSAIRE['α'], "Capacity reduction due to buckling."], [GLOSSAIRE['Nu,lim'], "Maximum axial force the column can carry with the chosen bars."],
  [GLOSSAIRE['Rapport Nu/Nu,lim'], "Share of capacity used: must stay at or below 1."], [GLOSSAIRE['As calc.'], "Required steel area."],
  [GLOSSAIRE['MRd (flexion composée)'], "Moment the section can carry under the axial force Nu."],
  [GLOSSAIRE['Taux util. moment'], "Share of bending capacity used: must stay at or below 1."],
  [GLOSSAIRE['μ'], "Reduced moment. Above μlim, compression steel would be needed."],
  [GLOSSAIRE['μlim'], "Limit above which the section needs compression steel."],
  [GLOSSAIRE['Z (m)'], "Lever arm between tension steel and compressed concrete."], [GLOSSAIRE['σbc ELS (MPa)'], "Concrete compression at service."],
  [GLOSSAIRE['σst ELS (MPa)'], "Steel stress at service, limited according to cracking."], [GLOSSAIRE['σst OK ?'], "Does the steel stay below its service limit?"],
  [GLOSSAIRE['τu (MPa)'], "Shear stress, compared with its limit."], [GLOSSAIRE['At (cm²/m)'], "Link area per metre."],
  [GLOSSAIRE['σmax (bar)'], "Maximum pressure under the footing, to compare with the allowable soil pressure."],
  [GLOSSAIRE['σmin (bar)'], "Minimum pressure: if negative, the footing lifts on one side."],
  [GLOSSAIRE['Poinçonnement'], "The column must not punch through the footing."], [GLOSSAIRE['σmax (MPa)'], "Maximum compression in the wall."],
  [GLOSSAIRE['Compression OK ?'], "Does compression stay below 0.6 fc28?"], [GLOSSAIRE['As rive (cm²)'], "Bars concentrated at the wall ends."],
  [GLOSSAIRE.S, "Site coefficient (ground type)."], [GLOSSAIRE.I, "Building importance factor."],
  [GLOSSAIRE.K, "Behaviour factor: the structure's ability to dissipate energy."], [GLOSSAIRE.D, "Dynamic amplification factor, read from the RPS spectrum."],
  [GLOSSAIRE['T (s)'], "Fundamental period of the building."], [GLOSSAIRE['F — effort à la base (kN)'], "Total horizontal earthquake force, to distribute over the levels."],
].forEach(([fr, en]) => fr && EN.set(fr, en));
CONSEILS.forEach(([, fr], i) => EN.set(fr, [
  "Increase the column section or fc28.", "Enlarge the column: the steel needed exceeds 5% of the concrete.",
  "Reduce the buckling length or increase the section.", "Increase the section or reduce the load eccentricity.",
  "Increase the beam depth or the steel area.", "Increase the section width or depth.",
  "Increase the beam depth to avoid compression steel.", "Increase the footing thickness H or fc28.",
  "Enlarge the footing or centre the load.", "Increase the wall thickness or fc28.",
  "Complete the value in Robot (or in the model), then run the design again.", "Correct the value in Robot: it is outside the design range.",
][i]));

/* Nombres au format anglais : « 1 187 » → « 1,187 », « 0,57 » → « 0.57 ». */
function nombresEN(t) {
  return String(t)
    .replace(/(\d),(\d)/g, '$1.$2')                              // décimale : 0,57 → 0.57
    .replace(/(\d)[\u202f\u00a0 ](?=\d{3}(?!\d))/g, '$1,');      // milliers : 1 187 → 1,187
}
const tr = (t) => EN.get(t) ?? t;
const CHAMPS_EN = {
  'a': 'a', 'b': 'b', 'lf': 'lf', 'Nu': 'Nu', 'Mx': 'Mx', 'My': 'My', 'fc28': 'fc28', 'fe': 'fe', 'Enrobage': 'Cover', 'h': 'h',
  'Mu': 'Mu', 'Vu': 'Vu', 'Ms service': 'Ms service', 'Ns': 'Ns', 'Poteau/voile a': 'Column/wall a', 'Poteau/voile b': 'Column/wall b',
  'σsol admissible': 'Allowable soil pressure', 'L': 'L', 'ép.': 'Thickness', 'N': 'N', 'M': 'M', 'V': 'V', 'H': 'H', 'G': 'G', 'Q': 'Q',
  'T manuelle': 'Manual T', 'Amortissement': 'Damping', 'Zone de vitesse υ': 'Velocity zone υ',
};
const MESSAGES_EN = [
  [/^est obligatoire$/, () => 'is required'], [/^doit être supérieur à (.+)$/, m => `must be greater than ${m[1]}`],
  [/^doit être au moins égal à (.+)$/, m => `must be at least ${m[1]}`], [/^doit être inférieur à (.+)$/, m => `must be less than ${m[1]}`],
  [/^doit être au plus égal à (.+)$/, m => `must be at most ${m[1]}`], [/^doit être un nombre entier$/, () => 'must be a whole number'],
  [/^doit être un nombre$/, () => 'must be a number'], [/^doit être un texte$/, () => 'must be text'],
];
function erreurChampEN(item) {
  for (const [re, f] of MESSAGES_EN) {
    const i = item.search(/ (est obligatoire|doit être .+)$/);
    if (i < 0) break;
    const lib = item.slice(0, i), msg = item.slice(i + 1), m = msg.match(re);
    if (m) return `${CHAMPS_EN[lib] ?? lib} ${f(m)}`;
  }
  return item;
}
const PROBLEMES_EN = [
  [/^taux d'utilisation en flexion composée = (.+) > 1$/, m => `combined bending utilisation = ${m[1]} > 1`],
  [/^section insuffisante en flexion composée \(aucun moment repris sous Nu\)$/, () => 'section too small in combined bending (no moment capacity under Nu)'],
  [/^As = (.+) cm² > 5 % B = (.+) cm² : section trop petite$/, m => `As = ${m[1]} cm² > 5% B = ${m[2]} cm²: section too small`],
  [/^λ > 70 : méthode forfaitaire non applicable$/, () => 'λ > 70: simplified method not applicable'],
  [/^σst ELS dépassée$/, () => 'SLS σst exceeded'], [/^aciers comprimés nécessaires \(μ > μlim\)$/, () => 'compression steel needed (μ > μlim)'],
  [/^poinçonnement non vérifié$/, () => 'punching shear not verified'], [/^traction sous la semelle$/, () => 'tension under the footing'],
  [/^compression > 0,6 fc28$/, () => 'compression > 0.6 fc28'], [/^donnée manquante : (.+)$/, m => `missing input: ${m[1]}`],
  [/^calcul impossible : (.+)$/, m => `calculation failed: ${m[1]}`],
];

/* Phrases contenant des valeurs. */
const MOTIFS = [
  [/^Corrigez (?:le champ|les champs) : (.+)\.$/, m => `Fix ${m[1].includes(' ; ') ? 'these fields' : 'this field'}: ${m[1].split(' ; ').map(erreurChampEN).join('; ')}.`],
  [/^(.+) (est obligatoire|doit être .+)\.$/, m => `${erreurChampEN(`${m[1]} ${m[2]}`)}.`],
  [/^(Lecture du modèle impossible|Export impossible|Plans impossibles|Enregistrement impossible|Chargement de la démo impossible)\. (.+)$/,
    m => `${{ 'Lecture du modèle impossible': 'Could not read the model', 'Export impossible': 'Export failed', 'Plans impossibles': 'Drawings failed', 'Enregistrement impossible': 'Could not save', 'Chargement de la démo impossible': 'Could not load the example' }[m[1]]}. ${traduire(m[2])}`],
  [/^Le moteur de calcul ne répond pas\. Relancez Bénayfacile, puis réessayez\.$/, () => 'The calculation engine is not responding. Restart Bénayfacile, then try again.'],
  [/^Erreur interne du service de calcul\. Le détail est dans le journal de Bénayfacile\.$/, () => 'Internal error in the calculation service. Details are in the Bénayfacile log.'],
  [/^Le poteau reçoit (.+) kN pour une capacité de (.+) kN(?: \((\d+) % utilisés\))?\. Ferraillage : (.+)\.$/,
    m => `The column carries ${m[1]} kN against a capacity of ${m[2]} kN${m[3] ? ` (${m[3]}% used)` : ''}. Reinforcement: ${traduire(m[4])}.`],
  [/^Aciers en partie basse : (.+)\. Cadres : (.+) cm² par mètre\.$/, m => `Bottom bars: ${m[1]}. Links: ${m[2]} cm² per metre.`],
  [/^Semelle de (.+) × (.+) m, épaisseur (.+) m\. Nappe X : (.+), nappe Y : (.+)\.$/, m => `Footing ${m[1]} × ${m[2]} m, ${m[3]} m thick. X layer: ${m[4]}, Y layer: ${m[5]}.`],
  [/^Compression maximale (.+) MPa(?:, aciers de rive (.+) cm²)?\.$/, m => `Maximum compression ${m[1]} MPa${m[2] ? `, boundary steel ${m[2]} cm²` : ''}.`],
  [/^Effort sismique à la base : (.+) kN(?:, soit (\d+) % du poids sismique)?\. Période T = (.+) s\.$/,
    m => `Seismic base shear: ${m[1]} kN${m[2] ? `, i.e. ${m[2]}% of the seismic weight` : ''}. Period T = ${m[3]} s.`],
  [/^Que faire : (.+)$/, m => `What to do: ${m[1].split(/(?<=\.) /).map(tr).join(' ')}`],
  [/^Augmentez la section : sous cet effort normal, elle ne reprend plus aucun moment\.$/, () => 'Increase the section: under this axial force it carries no moment.'],
  [/^(\d+) HA(\d+) \((symétrique|barres d'angles)\)$/, m => `${m[1]} HA${m[2]} (${m[3] === 'symétrique' ? 'symmetrical' : 'corner bars'})`],
  [/^(.+) éléments prêts\. Lancez « Calculer tout le modèle »\.$/, m => `${m[1]} members ready. Run “Design the whole model”.`],
  [/^(\d+) à revoir$/, m => `${m[1]} to review`],
  [/^Service indisponible : (.+)$/, m => `Service unavailable: ${m[1]}`],
  [/^Élément ajouté à la synthèse \((.+)\)\.$/, m => `Member added to the summary (${m[1]}).`],
  [/^(\d+) éléments envoyés à la synthèse\.$/, m => `${m[1]} members sent to the summary.`],
  [/^Vérification sismique ajoutée à la synthèse\.$/, () => 'Seismic check added to the summary.'],
  [/^Télécharger (.+?)(?: \((\d+) octets\))?$/, m => `Download ${m[1]}${m[2] ? ` (${m[2]} bytes)` : ''}`],
  [/^Note sauvegardée : (.+) \((\d+) octets\)\.$/, m => `Report saved: ${m[1]} (${m[2]} bytes).`],
  [/^(\d+) planches A1 — (.+) — (.+) éléments dessinés, (.+) kg d'acier\.$/,
    m => `${m[1]} A1 sheets — ${m[2].replace(/poteaux/, 'columns').replace(/poutres/, 'beams').replace(/semelles/, 'footings').replace(/voiles/, 'walls')} — ${m[3]} members drawn, ${m[4]} kg of steel.`],
  [/^(\d+) non dessinés \(à revoir\)\.$/, m => `${m[1]} not drawn (to review).`],
  [/^(Poteaux|Poutres|Semelles isolées|Semelles filantes|Voiles) #(\d+)$/, m => `${tr(m[1])} #${m[2]}`],
  [/^H augmentée de (.+) m à (.+) m pour satisfaire le poinçonnement\.$/, m => `H increased from ${m[1]} m to ${m[2]} m to satisfy punching shear.`],
  [/^As = (.+) cm² > 5 % B = (.+) cm² \(BAEL A\.8\.1,22\) : section de béton insuffisante, augmenter a × b\.$/,
    m => `As = ${m[1]} cm² > 5% B = ${m[2]} cm² (BAEL A.8.1,22): concrete section too small, increase a × b.`],
  [/^ex\. (.+)$/, m => `e.g. ${m[1]}`],
  [/^Classeur importé : (.+)\.$/, m => `Workbook imported: ${m[1]}.`],
  [/^Import impossible : le classeur est le modèle vide : ajoutez au moins une ligne \(un élément\) sous les en-têtes des feuilles (.+), puis enregistrez et importez-le de nouveau\.$/,
    m => `Import failed: the workbook is the empty template. Add at least one row (one member) under the headers of the ${m[1]} sheets, then save and import it again.`],
  [/^Import impossible : ce classeur n'a pas le format du modèle Bénayfacile \(feuilles trouvées : (.+) ; attendues : Poteaux, Poutres, Semelles, Voiles\)\. Téléchargez le modèle Excel et recopiez-y vos éléments\.$/,
    m => `Import failed: this workbook is not in the Bénayfacile template format (sheets found: ${m[1]}; expected: Poteaux, Poutres, Semelles, Voiles). Download the Excel template and copy your members into it.`],
  [/^Import impossible : (.+)\.$/, m => `Import failed: ${m[1]}.`],
  [/^(.+), ligne (\d+) : « (.+) » n'est pas un nombre \((.+)\)\.$/, m => `${m[1]}, row ${m[2]}: “${m[3]}” is not a number (${m[4]}).`],
  [/^(.+) : colonne\(s\) obligatoire\(s\) absente\(s\) : (.+)\.$/, m => `${m[1]}: missing required column(s): ${m[2]}.`],
  [/^Projet ouvert dans Robot : (.+)\.$/, m => `Project opened in Robot: ${m[1]}.`],
  [/^Analyse lancée dans Robot \(résultats absents du fichier\)\.$/, () => 'Analysis run in Robot (results were missing from the file).'],
  [/^Ouverture impossible : (.+)\.$/, m => `Could not open: ${m[1]}.`],
  [/^Robot n'a pas pu ouvrir ce projet : (.+)\. Vérifiez que Robot Structural Analysis est installé avec sa licence sur ce poste\.$/,
    m => `Robot could not open this project: ${m[1]}. Check that Robot Structural Analysis and its licence are installed on this PC.`],
  [/^— (.+)$/, m => { const r = traduire(m[1]); return r === m[1] ? null : `— ${r}`; }],
  [/^(.+) : (ok|.+)$/, m => (['robot', 'engine', 'dxf', 'report'].includes(m[1]) ? `${m[1]}: ${m[2]}` : null)],
  ...PROBLEMES_EN,
];

function traduire(texte) {
  const t = String(texte).trim();
  if (!t) return texte;
  if (EN.has(t)) return texte.replace(t, EN.get(t));
  for (const [re, f] of MOTIFS) {
    const m = t.match(re);
    if (m) { const r = f(m); if (r != null) return texte.replace(t, nombresEN(r)); }
  }
  return texte;
}

/* ---- application au DOM ---- */
const ATTRS = ['title', 'aria-label', 'placeholder', 'data-feuille'];
const origTexte = new WeakMap(), dernierTexte = new WeakMap(), origAttrs = new WeakMap();
let langueCourante = 'fr';
function exclu(n) {
  const el = n.nodeType === 1 ? n : n.parentElement;
  return !el || el.closest('script, style, pre, code, [translate="no"]');
}
function traiterTexte(n) {
  if (exclu(n)) return;
  if (dernierTexte.get(n) !== n.nodeValue) origTexte.set(n, n.nodeValue);   // modifié par l'application
  const orig = origTexte.get(n);
  const v = langueCourante === 'en' ? traduire(orig) : orig;
  if (n.nodeValue !== v) n.nodeValue = v;
  dernierTexte.set(n, v);
}
function traiterElement(el) {
  if (exclu(el)) return;
  let o = origAttrs.get(el);
  if (!o) { o = {}; origAttrs.set(el, o); }
  for (const a of ATTRS) {
    if (!el.hasAttribute(a)) continue;
    const cur = el.getAttribute(a);
    if (o[a] === undefined || (cur !== o[a] && cur !== o[`${a}:en`])) o[a] = cur;
    const v = langueCourante === 'en' ? traduire(o[a]) : o[a];
    o[`${a}:en`] = v;
    if (cur !== v) el.setAttribute(a, v);
  }
}
function traduireSousArbre(racine) {
  if (racine.nodeType === 3) return traiterTexte(racine);
  if (racine.nodeType !== 1) return;
  traiterElement(racine);
  const w = document.createTreeWalker(racine, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT);
  while (w.nextNode()) (w.currentNode.nodeType === 3 ? traiterTexte : traiterElement)(w.currentNode);
}
const observateur = new MutationObserver((mutations) => {
  observateur.disconnect();
  for (const m of mutations) {
    if (m.type === 'characterData') traiterTexte(m.target);
    else if (m.type === 'attributes') traiterElement(m.target);
    else m.addedNodes.forEach(traduireSousArbre);
  }
  observer();
});
function observer() {
  observateur.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
}
function definirLangue(langue) {
  langueCourante = langue === 'en' ? 'en' : 'fr';
  document.documentElement.lang = langueCourante;
  document.title = langueCourante === 'en' ? 'Bénayfacile — Structural design (BAEL / RPS)' : 'Bénayfacile — BET Structure (BAEL / RPS)';
  observateur.disconnect();
  traduireSousArbre(document.body);
  observer();
}
const LOCALE = () => (langueCourante === 'en' ? 'en-GB' : 'fr-FR');
