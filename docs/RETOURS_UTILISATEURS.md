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

### US3 — Un plan de coffrage par niveau *(à faire)*

> **En tant qu'** ingénieur BET, **pour** un bâtiment de N niveaux lu dans Robot, **je veux** une planche de coffrage par
> niveau (fondation, RDC, R+1… terrasse), **pour** remettre au chantier et au dossier d'autorisation un jeu de plans
> complet sans redessiner dans AutoCAD.

- [ ] Une planche par niveau détecté : trame et axes cotés, poteaux, poutres avec leur section, voiles, repères identiques à ceux de la note.
- [ ] Les niveaux identiques (étage courant) peuvent être regroupés sur une seule planche, avec la mention « R+2 à R+25 ».
- [ ] Dalles, planchers à corps creux (sens de portée des poutrelles) et balcons représentés et repérés.
- [ ] L'écran annonce, avant génération, le nombre de planches et la liste des niveaux couverts.
- [ ] Les éléments sans position (calculés un par un) sont listés comme « non dessinés », jamais placés au hasard.

### US4 — Longrines et chaînages *(à faire)*

> **En tant qu'** ingénieur BET au Maroc, **je veux** que les poutres du niveau fondation soient appelées **longrines** et
> les poutres de rive **chaînages**, dans les plans, la nomenclature et la note, **pour** que le dossier parle la langue
> du chantier.

- [ ] Poutre au niveau fondation → « Longrine », préfixe de type « L » (L1, L2…).
- [ ] Poutre de rive, sur le contour du niveau → « Chaînage », préfixe « Ch ».
- [ ] Les autres poutres restent « Poutre », préfixe « Pt ».
- [ ] La règle de détection (niveau, position sur la trame) est écrite dans le code et testée. Un cas ambigu est signalé, pas deviné.
- [ ] À valider avec l'ingénieur : le chaînage reçoit-il des dispositions propres (RPS 2011, chaînages horizontaux) ?
