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
