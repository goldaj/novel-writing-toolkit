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

## Export livre numérique EPUB 3 (branche du 29 octobre 2026)

La nouvelle commande `python tools/manuscript_pipeline.py epub mon-roman --author "Nom d'auteur"` produit `mon-roman/manuscript.epub` après contrôle qualité des sections. Format EPUB 3 reflowable avec table des matières, chapitres XHTML et métadonnées. Python standard uniquement, aucune transmission du manuscrit. Refus d'écrasement sans `--force`, sortie confinée au projet.

**[Guide EPUB, tests et limites](docs/EPUB_EXPORT.md)**. Cette branche est empilée sur la PR #2 du workflow générique ; aucun des scripts historiques ni des textes privés n'a été modifié. Tests XML/ZIP automatiques, validation par liseuse/EPUBCheck à faire avant diffusion.

## Impact narratif des révisions (2 novembre 2026)

**Narrative Impact** recherche les conséquences d'un changement plusieurs chapitres plus loin. Le moteur local (`tools/narrative_impact.py`) combine modifications de paragraphes, recherche transversale et dossier facultatif de faits/règles de causalité. Un module IA séparé (`tools/narrative_impact_ai.py`) propose des hypothèses sémantiques avec citations contrôlées, mais **n'envoie des extraits de manuscrit à OpenAI que sous `--allow-upload` avec une clé API explicite**. Les résultats restent soumis à la relecture humaine.

[Guide de démarrage, exemples fictifs et limites](docs/NARRATIVE_IMPACT.md). Tests unitaires et CI Python 3.10/3.12, zéro contenu littéraire personnel committé.

## Vers une mémoire narrative construite par IA locale (novembre 2026)

[Étude d'architecture et comparaison des solutions](docs/LOCAL_NARRATIVE_AI_RESEARCH.md) : Ollama + LangExtract privilégiés, LM Studio en alternative, modèles Gemma 4/Qwen 3.5/Ministral à évaluer, extraction sourcée et mémoire chronologique interchapitres. **Aucune IA locale n'est encore intégrée.** Le convertisseur hors ligne [chronology_to_dossier.py](tools/chronology_to_dossier.py) transforme une mémoire d'événements + relations annotées en dossier causal attendu par `narrative_impact.py`; tests synthétiques sans manuscrit privé.


## Narrative Intelligence Engine v1 (branche du 12 novembre 2026)

Le moteur de mémoire sourcée permet d'examiner une chronologie hors ordre des chapitres, les savoirs individuels, les faits du monde et les conséquences causales transitives d'une révision. Rapports privés JSON/HTML, aucune API ni modification de texte. Démonstration fictive dans examples/narrative-intelligence. Lire docs/NARRATIVE_INTELLIGENCE_ENGINE.md. Aucune validation sémantique complète d'un roman réel n'est revendiquée.

### Suggestions d'annotation assistées par modèle local (optionnelles)

tools/narrative_local_assist.py propose des annotations littéraires à partir de paragraphes envoyés uniquement à un serveur Ollama local explicitement autorisé. Les citations candidates sont vérifiées dans les extraits réellement fournis, sans validation du sens. Aucun candidat n'est automatiquement accepté dans la mémoire. Guide : docs/NARRATIVE_INTELLIGENCE_ENGINE.md. Les tests utilisent des réponses simulées, pas un modèle réel.
