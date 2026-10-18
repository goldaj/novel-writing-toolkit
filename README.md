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
