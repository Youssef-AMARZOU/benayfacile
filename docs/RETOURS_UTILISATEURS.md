# Bénayfacile — Retours utilisateurs et user stories

> Chaque retour terrain est noté tel qu'il a été exprimé, puis traduit en user story avec des
> critères d'acceptation vérifiables. Le statut indique ce qui est livré et ce qui reste à faire.

## R1 — « Il ne me donne qu'une seule chose » (21/11/2026)

**Contexte.** Un testeur (ingénieur) a ouvert un modèle Robot réel et généré les plans DXF.

**Retour, traduit de la darija :**
1. « Il ne me donne qu'une seule chose : le détail de fondation, et pas les autres étages. »
2. Capture de l'écran Lecture du modèle : l'application a détecté **27 niveaux (RDC à R+26)**, 56 poteaux et 13 semelles.
   « Regarde combien de niveaux il a détectés, et il n'en a donné qu'un. »
3. « Pour les poutres en fondation, on pourrait changer leur nom : on les appelle des **longrines**.
   Et celles qui sont aux extrémités, on les appelle des **chaînages**. »

**Diagnostic.**

| # | Cause | Gravité |
|---|---|---|
| a | Toutes les planches A1 étaient côte à côte dans l'espace objet, sans onglet de présentation. AutoCAD s'ouvrait sur la première, le plan de fondation, et le reste était hors écran. | Bloquant (perçu) |
| b | Le dossier n'a pas de plan par niveau. Il contient le plan de fondation, puis des planches par famille (poteaux, poutres, voiles) regroupées par type. Il n'y a ni plan de coffrage par étage, ni dessin des dalles, planchers ou balcons. | Majeur |
| c | Le bouton « Générer le plan DXF (semelles) » de la Synthèse ne dessinait que des semelles, sur une trame fictive (0/6/12 × 0/5/10 m), avec une semelle inventée (2,27 × 2,27 m, 13 HA14) quand aucune n'était calculée. Contraire à la règle « aucune valeur inventée ». | Majeur |
| d | Vocabulaire : toutes les poutres s'appellent « poutres ». Sur un dossier marocain, les poutres du niveau fondation sont des **longrines** et les poutres de rive sont des **chaînages**. | Mineur, mais crédibilité |

### US1 — Voir tout le dossier à l'ouverture *(livrée)*

> **En tant qu'** ingénieur BET, **quand** j'ouvre le DXF dans AutoCAD, **je veux** voir chaque planche dans son propre
> onglet, **pour** ne pas croire que le dossier se limite au plan de fondation.

- [x] Une présentation A1 par planche, nommée « 01 Plan de fondation », « 02 Ferraillage des semelles »… « Nomenclature des aciers ».
- [x] L'espace objet s'ouvre sur l'ensemble des planches.
- [x] Après génération, l'application liste les planches produites et dit où les trouver dans AutoCAD.

### US2 — Un seul dossier de plans, sans valeur inventée *(livrée)*

> **En tant qu'** ingénieur BET, **je veux** que le bouton DXF de la Synthèse produise le même dossier que la Lecture du
> modèle, **et** qu'il me dise ce qui manque au lieu de dessiner un exemple.

- [x] Le bouton s'appelle « Générer le dossier de plans DXF ». Il dessine le dossier complet du modèle envoyé à la synthèse.
- [x] Sans modèle, il explique qu'il faut la position et le niveau des éléments, et renvoie vers Lecture du modèle.
- [x] Plus de semelle ni de trame par défaut dans l'interface.

### US3 — Un plan de coffrage par niveau *(livrée, première version)*

> **En tant qu'** ingénieur BET, **pour** un bâtiment de N niveaux lu dans Robot, **je veux** une planche de coffrage par
> niveau (fondation, RDC, R+1… terrasse), **pour** remettre au chantier et au dossier d'autorisation un jeu de plans
> complet sans redessiner dans AutoCAD.

- [x] Une planche par niveau : trame et axes cotés, poteaux et voiles coupés (hachurés), poutres en tireté avec leur
      section, type de chaque élément (P1, Pt2, V1…) identique à la note, tableau des éléments du plancher.
- [x] Les niveaux consécutifs identiques sont regroupés : « Coffrage plancher haut R+2 à R+4 ».
- [x] Les poutres du niveau le plus bas sont rangées au niveau « Fondation » (planche « Coffrage niveau fondation »),
      et non plus au RDC.
- [x] Dalles et balcons lus dans Robot dessinés et repérés sur leur niveau (contour, épaisseur).
- [x] L'écran annonce le nombre de plans de coffrage et les niveaux couverts.
- [x] Un élément sans position connue est listé « position inconnue », jamais placé au hasard ; un élément non vérifié
      est dessiné avec son nom suivi de « * ».
- [ ] Planchers à corps creux : sens de portée des poutrelles (les panneaux Robot ne portent pas cette information).
- [ ] Classeur Excel importé : colonnes de position pour les poutres et les voiles (aujourd'hui seuls les poteaux ont un axe).
- [ ] Vérifier sur le modèle réel du testeur (27 niveaux, sous-sol) : regroupement, échelle et lisibilité.

### US4 — Longrines et chaînages *(à faire)*

> **En tant qu'** ingénieur BET au Maroc, **je veux** que les poutres du niveau fondation soient appelées **longrines** et
> les poutres de rive **chaînages**, dans les plans, la nomenclature et la note, **pour** que le dossier parle la langue
> du chantier.

- [ ] Poutre au niveau fondation → « Longrine », préfixe de type « L » (L1, L2…).
- [ ] Poutre de rive, sur le contour du niveau → « Chaînage », préfixe « Ch ».
- [ ] Les autres poutres restent « Poutre », préfixe « Pt ».
- [ ] La règle de détection (niveau, position sur la trame) est écrite dans le code et testée. Un cas ambigu est signalé, pas deviné.
- [ ] À valider avec l'ingénieur : le chaînage reçoit-il des dispositions propres (RPS 2011, chaînages horizontaux) ?

## R2 — Ce que montre la vidéo « bnayfacile » sur Instagram (21/11/2026)

**Contexte.** Une vidéo sponsorisée du compte « bnayfacile » montre le parcours attendu, en darija : « GTA 6 est sorti…
et moi j'ai un modèle dans Robot » → « le bâtiment complètement calculé » → « les plans de ferraillage en DXF » →
« les coupes et les élévations » → « béton et acier » → « et le métré » → « tout est calculé » → « prêts pour AutoCAD ».

**Ce qu'on y voit**, et l'écart avec l'application :

| Montré dans la vidéo | Dans Bénayfacile | Écart |
|---|---|---|
| Modèle Robot avec sous-sol, mezzanine et 4 étages, lu en entier | Lecture COM ou classeur Excel | À confirmer sur un modèle avec sous-sol |
| Un DXF « tous les étages » : vues en plan par niveau, ferraillage des voiles en série | Plans de coffrage par niveau (US3) et planches par famille | Pas encore de plan de ferraillage par niveau |
| Coupes et élévations (voiles, poutres) | Élévation des poutres et des voiles, coupes des poteaux | Pas de coupe générale du bâtiment |
| Métré Excel détaillé par poteau : repère, étage, type, section, hauteur, **béton (m³)**, aciers longitudinaux, cadres, **épingles**, longueurs, poids | Export Excel des résultats et nomenclature des aciers | Pas de volume de béton, pas d'épingles |
| Récapitulatif : nombre d'éléments, béton total, acier total, **ratio kg/m³**, poids par diamètre et **nombre de barres de 12 m** | Poids par diamètre | Pas de béton, de ratio ni de barres commerciales |
| Note de calcul des semelles en Word, tableau de toutes les semelles | Note HTML / PDF | Pas d'export Word |

### US5 — Métré béton et acier *(livrée, première version)*

> **En tant qu'** ingénieur ou métreur, **je veux** pour chaque élément le volume de béton et le poids d'acier, et un
> récapitulatif avec le ratio kg/m³ et le nombre de barres de 12 m par diamètre, **pour** chiffrer le gros œuvre et
> commander l'acier.

- [x] Volume de béton par élément (poteau a × b × h, poutre b × h × l, semelle A × B × H, voile L × e × h), par famille et total.
- [x] Feuille « Métré détaillé » : une ligne par élément (repère, axe, niveau, type, section, béton, aciers principaux, cadres, autres aciers, poids, ratio).
- [ ] Épingles des poteaux et des voiles : à ajouter quand l'ingénieur fixe la règle (aujourd'hui annoncées « non prévues »).
- [x] Ratio acier / béton (kg/m³) par élément, par famille et global.
- [ ] Comparaison à une fourchette usuelle : seulement avec une source.
- [x] Nombre de barres commerciales de 12 m par diamètre et par usage (longueur totale / 12, arrondi supérieur, chutes
      non optimisées et dites comme telles).
- [x] Le métré et la nomenclature des plans donnent le même poids d'acier (contrôlé ; écart signalé « ALERTE ECART ARITHMETIQUE »).
- [ ] Reprendre le récapitulatif dans la note de calcul.

## Généralisation : tout modèle Robot, pas seulement l'exemple R+4

L'exemple R+4 est une trame régulière 3 × 3. Pour ne pas construire l'outil sur ce seul cas, un modèle volontairement
irrégulier est testé (`tests/test_modele_irregulier.py`) : 27 niveaux, 4 × 28 files de portées inégales (repères
jusqu'à AB), poteaux manquants, sections qui changent avec la hauteur, éléments dans un ordre quelconque (environ
4 000 éléments). Ce test a révélé et fait corriger :

- **ordre des niveaux** : il suivait la numérotation des barres ; il suit maintenant l'altitude (Fondation, S-2, S-1,
  RDC, R+1…) ;
- **repères de files** : au-delà de Z, les repères devenaient des symboles ; ils continuent en AA, AB… ;
- **bâtiment long** : un plan de 105 m tombait au 1:500, illisible ; le plan reste au 1:100 et se découpe en parties
  (« partie 1/3 ») coupées sur les files, avec les repères d'origine.

Options ajoutées pour coller aux usages montrés dans la vidéo R2 :

- détails de ferraillage **par type** (dossier d'exécution) ou **un par élément** (chaque poteau, poutre, voile dessiné) ;
- métré en **une feuille par famille** (« Métré poteaux », « Métré poutres »…) plus le récapitulatif.

### Limites connues, à traiter

- [ ] Plan de fondation : pas encore découpé pour un bâtiment long (même méthode que les plans de coffrage à appliquer).
- [x] Noms de niveaux : les **étages définis dans Robot** sont repris quand ils tombent sur un plancher du modèle ;
      sinon RDC, R+1… depuis le plancher le plus bas. *Lecture de `Structure.Storeys` (Name, Level) écrite d'après l'API
      RobotOM, à confirmer sur un vrai fichier.*
- [x] Panneaux non rectangulaires (dalle en L) : contour réel dans la vue 3D et sur le plan de coffrage ; le calcul de la
      dalle reste fait sur le rectangle englobant, et c'est signalé dans les remarques de lecture.
- [ ] Voile avec ouverture : encore réduit à sa plus grande longueur.
- [ ] Semelles filantes sous voiles : pas encore déduites du modèle.

### À vérifier chez le testeur (modèle réel, Robot installé)

1. Ouvrir son modèle 27 niveaux, « Calculer tout le modèle ».
2. « Plans de ferraillage (DXF) », détails **par type** puis **un par élément** ; ouvrir chaque DXF dans AutoCAD :
   onglets en bas, plans de coffrage par niveau, regroupement des étages courants, lisibilité (échelle, textes).
3. « Exporter en Excel » : feuilles « Métré … » et « Récapitulatif métré » ; comparer béton et acier à son propre métré
   sur deux ou trois éléments.
4. Noter : noms de niveaux attendus, éléments « position inconnue » ou « non dessinés », temps de génération.

### US6 — Voir le modèle en 3D *(livrée, première version)*

> **En tant qu'** ingénieur BET, **après** avoir lu mon modèle Robot, **je veux** le voir en 3D dans l'application, comme
> dans Robot, **pour** vérifier d'un coup d'œil que tout a été lu (niveaux, files, poteaux, poutres, voiles, dalles) et,
> après le calcul, repérer les éléments à reprendre.

- [x] Vue 3D dans « Projet Robot » dès la lecture du modèle : poteaux, poutres, voiles, dalles, semelles à leur position.
- [x] Files repérées au sol, niveaux nommés sur le côté ; vues Iso, Face, Côté, Dessus ; tourner, déplacer, zoomer.
- [x] Filtre par famille et « jusqu'au niveau » (utile pour un bâtiment de 27 niveaux).
- [x] Après le calcul : vert vérifié, rouge à revoir ou en erreur, ocre incomplet ; bulle au survol (repère, niveau,
      section, état).
- [x] Sans bibliothèque ni réseau (canvas du navigateur) ; thème clair et sombre.
- [x] Altitude de chaque élément lue dans Robot ; à défaut, cumul des hauteurs d'étage (signalé si supposé).
- [ ] À vérifier sur le modèle réel : lisibilité au-delà de 2 000 éléments, panneaux non rectangulaires.

## Audit de généralisation et de passage à l'échelle (21/11/2026)

Demande : « généralisation, scalabilité et adaptabilité dans toute l'app, 3D comprise ». Un faux modèle Robot reprend
des situations que l'exemple R+4 n'a pas (`tests/test_robot_generalisation.py`). Ce qui supposait un modèle « propre » :

| Où | Problème trouvé | Correction |
|---|---|---|
| Lecture Robot : niveaux | chaque altitude de nœud créait un étage (nœud à mi-hauteur, palier, acrotère) | étages = altitudes des planchers (poutres et panneaux horizontaux, pondérés par leur longueur) ; une altitude portant moins de 25 % du plus grand plancher est « secondaire » et rattachée au plancher inférieur (signalé) |
| Lecture Robot : files | chaque abscisse de nœud créait une file (bout de palier, nœud intermédiaire) | files tirées des poteaux et voiles seulement |
| Lecture Robot : semelles | seulement sous les poteaux du niveau le plus bas | sous tout poteau qui ne repose ni sur un autre poteau ni sur un plancher : fondations à plusieurs altitudes, terrain en pente |
| Lecture Robot : panneaux | un panneau de plus de 50 cm de dénivelé devenait un voile (toiture en pente, rampe) | classement par la normale du panneau : horizontal, vertical ou incliné ; les inclinés ne sont pas calculés, ils sont montrés et signalés |
| Lecture Robot : noms | toujours RDC, R+1… | noms des étages Robot repris quand ils existent |
| Libellés de niveaux (Excel, Robot) | seuls Fondation, S-n, RDC, R+n étaient rangés ; « Étage 1 », « SS1 », « N+2 », « Terrasse »… tombaient au hasard | libellés usuels reconnus ; par altitude dès que le modèle la donne (plans et 3D) |
| Vue 3D | style relu pour chaque élément à chaque image ; cadrage qui dépasse la pile au-delà de ~100 000 points ; dalles en rectangle ; barres inclinées absentes | jetons lus une fois par image, un dessin par image, cadrage en boucle ; contour réel ; « Autres » en gris ; repères de files espacés quand la trame est dense. Mesuré : 34 800 éléments, 0,1 s par image |
| Moteur | l'axe neutre ELS balayait 2 000 points (90 % du temps de calcul en lot) | racine exacte du trinôme (mêmes résultats, test calculé à la main) : calcul en lot de 1 424 éléments en 0,6 s au lieu de 7,8 s |
| Note de calcul | pas d'export Word | export .docx tiré de la même note que l'aperçu, équations Word natives |
