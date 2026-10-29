# Contexte ChatGPT pour Novel Writing Toolkit

**Initialisé le 2026-10-24. Couverture : partielle, sauf les sources originales référencées explicitement.** Codex doit lire ce fichier après `AGENTS.md` et avant toute reprise du projet. Une mémoire reconstruite n'est pas la totalité du chat.

## Projet confirmé par le dépôt
- Dépôt : `goldaj/novel-writing-toolkit`.
- Objet : Scripts Python de préparation, extraction, assemblage, métriques, mise en paragraphes et contrôle qualité pour manuscrits, extraits d'un atelier littéraire privé.
- Contraintes : Ne jamais publier roman, brouillons, corpus privés, exports de conversations personnels, chemins Windows individuels ou secrets. Tester progressivement les scripts avant de promettre une bibliothèque générique.
- Validation : Python 3.10+ ; inspecter les scripts `tools/*.py` et leurs options `--help` quand disponibles ; les chemins hérités peuvent être à corriger.

## Échanges attestés ou sources à lire

2026-10-18 — Assistant, résumé reconstruit, non verbatim : extraction des outils éditoriaux vers un dépôt public séparé des manuscrits privés.

Les conversations du roman et les textes littéraires privés ne doivent PAS être copiés dans ce dépôt public, même pour aider Codex.

2026-10-24 — Utilisateur (verbatim, heure non vérifiable) : « je te demande de lire mes repo git où tu es le dernier utilisateur, de rajouter un AGENTS.md pertinent s'il n'y en a pas. Mais en plus, tu rajoutera un document repérable par codex (peut être le référencer dans le AGENTS.md justement ?) où tu mets l'intégralité de nos échanges liés à ce projet. Mes questions, tes réponses (de sorte à les différencier) et les horodatages si tu les as. »

## Limites de couverture, fidélité et mise à jour
- Les passages marqués `verbatim` sont des extraits exacts disponibles dans le contexte ; les résumés ne doivent **jamais** être cités comme du dialogue mot pour mot. Aucune réponse complète de l'assistant n'a été inventée.
- Pour obtenir l'intégralité des questions, réponses et horodatages : intégrer un export authentique des conversations pertinentes ; conserver l'ordre et le rôle des messages, et expurger avant publication les éléments sensibles et hors projet.
- En intervention future, ajouter en bas les nouveaux dialogues sourcés et les décisions vérifiées, sans effacer les entrées précédentes. Ce journal et `AGENTS.md` sont versionnés dans Git.

## 2026-10-24 — Revue parallèle multi-dépôts, heure non attestée

**Utilisateur (verbatim)** :

> tu vois tout le boulot qu'on a fait sur la conversation Avancement projets codex ?
> Tu vas refaire la même chose sur TOUT mon repo git. Tu vas commencer par les projets les plus gros, regarder ce que tu peux faire dessus et le faire sur ta branch (même consignes que sur l'autre conversation).
> Tu vas ensuite me faire un rapport très succint des projets que t'as touché et de ce que t'as avancé dessus.
> Amuse toi !

**Assistant (résumé reconstruit, non verbatim)** : Outil de manuscrit rendu générique (dossiers d'entrée, chemin de sortie, manifeste au bon nom), tests synthétiques et CI. Branche `chatgpt/review-20261024` uniquement, aucun changement direct de `main`.

**Validation :** consulter les checks de la PR. Les tests n'ont pas été exécutés localement. Confiance élevée dans la portée du correctif ciblé, validation fonctionnelle complète non attestée. Codex doit relire et tester avant intégration.

## Intervention du 2026-10-29

- Utilisateur (verbatim, heure précise indisponible) : « Continue en boucle de chercher de nouveaux sujets ».
- Assistant (résumé reconstruit, non verbatim) : sélection du dépôt `novel-writing-toolkit` après inventaire de plusieurs projets ; décision d'ajouter une expérience générique d'assemblage et QA sans importer les manuscrits privés et sans casser les utilitaires historiques.
- Code ajouté : `tools/manuscript_pipeline.py` ; tests : `tests/test_manuscript_pipeline.py` ; CI : `.github/workflows/python-tests.yml` ; guide : `docs/GENERIC_WORKFLOW.md`. CLI `init`, `check`, `build`, rapports QA et contrôle de sécurité des chemins.
- Tests CI de la première itération : un test négatif incorrect a été identifié et corrigé. Exécution suivante du commit 9c10f18a6e8df574b267d0d0790828d761bc5cbd : **succès** sur GitHub Actions (https://github.com/goldaj/novel-writing-toolkit/actions/runs/40845795041). Suivre les CI des commits ultérieurs avant fusion.
- Limitations : pas de navigation locale ni de rapport HTML, pas de migration des anciens scripts, pas de manuscrit réel testé. Aucune transcription complète des anciennes conversations n'est disponible. Voir le guide pour la passation.
