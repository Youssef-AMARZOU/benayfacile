# BÉNAYFACILE — instructions pour Claude

Bureau d'études structure automatisé : poteaux, poutres, semelles, voiles selon **BAEL 91 mod. 99**
et **RPS 2000 v2011**, depuis un modèle **Autodesk Robot**, avec note de calcul et plans DXF.

## Skills à utiliser

| Tâche | Skill |
|---|---|
| Modèle Robot (`services/robot_service.py`, `robot_ossature.py`), cas de charge, combinaisons, dalles/balcons | `civil-robot-autodesk-engineer` |
| Tout ce qui touche RPS 2011, NM, sol / semelles, contexte marocain | `maroc-civil-standards` |
| Écrire, modifier ou tester une formule (`services/engine_service.py`, `complements.py`, tests) | `civil-calculation-engineer` |
| Avant d'émettre ou d'appeler « finale » une note de calcul, un plan DXF, une release | `professional-review-gate` |

## Sources de vérité (priment sur les valeurs des skills)

- `referentiels/bael.json` et `referentiels/rps.json` : constantes normatives avec `_source`
  (article / tableau du texte officiel). Une valeur marquée *(à vérifier)* dans un skill est remplacée
  par celle du référentiel quand elle y figure. Ne jamais coder en dur une constante normative
  ailleurs : l'ajouter au référentiel avec sa `_source`.
- `referentiels/bureau.json` : données du bureau (page de garde, cartouche) — données client, ne pas
  les publier ni les envoyer hors du poste.

## Règles du projet

- **Aucune valeur inventée** ; un écart est signalé, jamais masqué (audit arithmétique ligne à ligne,
  `services/common.py` : OK / `ALERTE ECART ARITHMETIQUE`, repris dans `services/note_calcul.py`).
- 100 % local (`127.0.0.1`) ; aucun appel réseau dans le moteur.
- Toute formule nouvelle : cas calculé à la main + test dans `tests/` (voir `civil-calculation-engineer`).
- Tests : `python -m pytest tests/` (un échec bloque la CI).
- Vérifier une note générée avec le gate :
  `python ~/.claude/skills/professional-review-gate/scripts/check_deliverable.py <note.md|txt>`
  (sur un export texte de la note HTML). Statut maximal attribuable par Claude : « PRÊT POUR REVUE ».
- Combinaisons Robot : valider avec
  `python ~/.claude/skills/civil-robot-autodesk-engineer/scripts/validate_load_cases.py <cas.json> --seismic rps2011`.
