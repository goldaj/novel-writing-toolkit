# Novel Writing Toolkit

**Outils Python pour la production et la qualité éditoriale de manuscrits longs**

Un ensemble de scripts créés dans le cadre d'un projet de roman. Le code a été extrait d'un dépôt de travail privé : **seuls les outils sont publiés, jamais le manuscrit, ses brouillons ni les exports de conversations**.

## Fonctions

| Script | Fonction |
| --- | --- |
| `tools/assemble_manuscript.py` | Assembler les sections et contrôler la structure et la longueur |
| `tools/manuscript_metrics.py` | Mesures lexicales, phrases, sections et statistiques |
| `tools/final_manuscript_qa.py` | QA éditoriale, structure, intégrité et contrôle final |
| `tools/prose_style_metrics.py` | Mesurer des caractéristiques stylistiques |
| `tools/reflow_narrative_paragraphs.py` | Recomposer des paragraphes |
| `tools/prepare_manuscript_sections.py` | Préparer les sections de travail |
| `tools/extract_docx_corpus.py` | Extraire un corpus à partir de documents Word |
| `tools/extract_chatgpt_shares.py` | Extraire des données depuis des exports accessibles |

## Utilisation

Python 3.10+ recommandé. Inspecter les options de chaque programme avec `python tools/<script>.py --help` quand elles sont disponibles.

**Attention :** certains scripts de cette première extraction sont encore liés à l'arborescence Windows et aux conventions éditoriales du projet d'origine. Le dépôt conserve cette version historique pour pouvoir la refactoriser progressivement ; il ne s'agit pas encore d'une bibliothèque générique prête à installer.

## Évolutions prévues

- Remplacer les chemins locaux codés en dur par une CLI paramétrable.
- Ajouter des jeux de données synthétiques, des tests et une CI.
- Unifier les sorties JSON et les rapports QA.

## Confidentialité

Le contenu littéraire original n'est pas inclus. Fournir ses propres documents localement. Ne pas publier de documents privés, de jetons, de mots de passe ou d'exports personnels.

## Parcours produit

Ce projet démontre la conception d'un workflow, l'automatisation de tâches répétitives, la définition de règles de contrôle et l'itération sur un processus de production réel.

## Nouveau : workflow générique sans dépendances (2026-10-29)

Lancer `python tools/manuscript_pipeline.py init mon-roman --chapters 5`, remplir les fichiers `mon-roman/sections/` puis exécuter `python tools/manuscript_pipeline.py check mon-roman` et `python tools/manuscript_pipeline.py build mon-roman`. L'assemblage vérifie les en-têtes, la longueur et les règles de qualité sans exposer les textes. Les rapports JSON permettent une intégration ultérieure dans une interface. Les fichiers sources ne sont jamais écrasés par le build. Les anciens outils restent disponibles sans modification.

**[Guide complet d'utilisation et de reprise pour Codex](docs/GENERIC_WORKFLOW.md).** Tests : `python -m unittest discover -s tests -v`. Conserver les vrais manuscrits hors du dépôt public.
