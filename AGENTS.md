# AGENTS.md — Novel Writing Toolkit

## Avant de travailler
1. Lire `README.md` et les documents techniques pertinents, puis **`docs/CHATGPT_PROJECT_HISTORY.md`** pour les demandes, décisions et lacunes du contexte.
2. Scripts Python de préparation, extraction, assemblage, métriques, mise en paragraphes et contrôle qualité pour manuscrits, extraits d'un atelier littéraire privé.
3. Ne jamais publier roman, brouillons, corpus privés, exports de conversations personnels, chemins Windows individuels ou secrets. Tester progressivement les scripts avant de promettre une bibliothèque générique.

## Exécution et vérification
- Python 3.10+ ; inspecter les scripts `tools/*.py` et leurs options `--help` quand disponibles ; les chemins hérités peuvent être à corriger.
- Utiliser de petites modifications contrôlables. Ne pas écraser ni supprimer des fichiers ou anciennes versions sans demande explicite.
- Distinguer hypothèses, code présent, essais effectivement exécutés et éléments encore à valider.

## Passation à Codex et archivage permanent
- **Document de référence de la conversation :** `docs/CHATGPT_PROJECT_HISTORY.md` ; il peut être incomplet et le dit explicitement.
- Après chaque intervention, mettre à jour ce document si une décision, une contrainte, une étape ou un nouveau contexte pertinent change. Référencer les nouveaux messages de l'utilisateur et de l'assistant lorsque leur texte exact est accessible.
- Format : date ISO et fuseau si connus, rôle `Utilisateur` ou `Assistant`, mention `verbatim` seulement pour un texte exact. Sinon `résumé reconstruit, non verbatim`. Ne pas inventer d'heure ni de citation.
- Si l'historique intégral n'est pas disponible, le signaler et demander un export réel plutôt que fabriquer une transcription. Préserver les exports existants sans les réécrire.
- Exclure secrets, identifiants, données personnelles et contenus non destinés à la publication. Le niveau de visibilité de ce dépôt s'applique aussi aux documents ajoutés.

## Nouvelle architecture (29/10/2026)

Le `tools/manuscript_pipeline.py` est la voie générique recommandée pour créer, valider et assembler les nouveaux projets. Lire `docs/GENERIC_WORKFLOW.md` avant toute modification. Les anciens scripts restent liés à leur projet d'origine, ne pas les supprimer ni les modifier en masse.

- Tests synthétiques : `python -m unittest discover -s tests -v` (Python 3.10 et 3.12 via CI).
- Préserver les manuscrits, rapports et dossiers de travail personnels *hors* du dépôt public.
- La CLI refuse les chemins qui sortent du dossier du manuscrit et l'écrasement silencieux de sections.
- Ne pas prétendre qu'une IA écrit ou corrige les textes : il s'agit d'un assembleur et de contrôles déterministes, sans appel réseau.
- Priorités de reprise : interface locale, profils éditoriaux, migration progressive des utilitaires historiques ; voir `docs/GENERIC_WORKFLOW.md`.
