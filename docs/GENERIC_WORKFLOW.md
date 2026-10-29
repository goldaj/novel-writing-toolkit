# Workflow générique de manuscrit

Le nouveau `tools/manuscript_pipeline.py` (Python 3.10+, sans dépendances) fournit un vrai processus hors ligne : initialisation d'un roman, validation des chapitres, assemblage dans l'ordre, rapport qualité JSON et sécurité d'écriture. Les scripts historiques de *Résurrectés* sont conservés tels quels. Aucun manuscrit privé n'est fourni.

## Démarrage rapide

```bash
python tools/manuscript_pipeline.py init mon-roman --chapters 5 --title "Mon roman"
# Remplir les fichiers mon-roman/sections/chapter_XX.txt.
python tools/manuscript_pipeline.py check mon-roman
python tools/manuscript_pipeline.py build mon-roman
```

`init` crée un `project.json` et des chapitres comportant leur en-tête. `check` ne modifie rien. `build` écrit `manuscript.txt` et `manuscript-report.json` seulement après validation. Les fichiers existants ne sont remplacés qu'avec `--force`. Les options `--output` et `--report` personnalisent les chemins de sortie, toujours relatifs à la racine du projet.

## Configuration du roman

Exemple de `project.json` :

```json
{
  "format_version": 1,
  "title": "Mon roman",
  "minimum_words": 0,
  "maximum_words": null,
  "required_phrases": [],
  "forbidden_phrases": [],
  "sections": [
    {"file": "sections/chapter_01.txt", "heading": "Chapitre 1"},
    {"file": "sections/chapter_02.txt", "heading": "Chapitre 2"}
  ]
}
```

On peut définir autant de sections que nécessaire (jusqu'à 500), avec des intitulés exacts personnalisés, y compris prologue et épilogue. `minimum_words` doit être un entier positif ou nul, `maximum_words` peut être `null`.

## Contrôles fonctionnels

**Bloquants** : chapitre absent ou invalide UTF-8, en-tête différent de celui du manifeste, caractère nul, total de mots hors limites, phrase requise absente ou phrase interdite présente. Code retour `1` ; aucune sortie manuscrit n'est produite en cas d'échec.

**Alertes non bloquantes** : espaces en fin de ligne, caractère de remplacement, répétition d'un long paragraphe de 80 caractères ou plus et sections très courtes (moins de 45 % de la médiane, pour au moins trois sections). Ces alertes sont des suggestions, pas une évaluation littéraire.

Le rapport comprend la longueur, le nombre de paragraphes et phrases, la longueur moyenne des phrases par section, les erreurs/alertes et le SHA-256 du texte assemblé. `--json` sur `check` ou `build` produit une sortie machine. Code retour `0` quand les contraintes passent ; `2` pour une erreur de configuration ou d'écriture.

## Confidentialité et robustesse

Le script travaille uniquement sur disque local et ne publie rien. Les sections sont confinées au dossier du projet, même en cas de liens symboliques ; aucun chemin de sortie ne peut écraser une section ou la configuration. Les fichiers de sortie sont remplacés atomiquement **individuellement**, pas comme une transaction à deux fichiers. Ne pas committer de vrais manuscrits, de rapports ou de dossiers de travail personnels dans ce dépôt public. Les rapports de QA peuvent contenir des noms de fichiers et des phrases de configuration : les garder privés.

L'analyse des phrases et des mots est approximative, pas une grammaire française complète. Ce moteur n'écrit pas de roman et n'a aucune IA embarquée.

## Vérifications et reprise Codex

Tests : `python -m unittest discover -s tests -v`. CI : `.github/workflows/python-tests.yml`, Python 3.10 et 3.12. Tester également un projet factice créé par `init`. Lire `AGENTS.md`, `README.md` et `docs/CHATGPT_PROJECT_HISTORY.md` avant reprise.

Priorités suivantes :
1. Ajouter une interface locale HTML de suivi des chapitres et graphiques d'évolution, sans téléverser les textes.
2. Configurer des profils de longueur et d'alertes pour album jeunesse, roman et feuilleton.
3. Migrer progressivement les scripts historiques d'assemblage et QA pour réutiliser le moteur générique, sans perdre les règles spécifiques du roman original.
4. Ajouter des tests de bout en bout des sorties et de régression sur plusieurs encodages.
5. Unifier les rapports JSON des outils actuels et concevoir une comparaison entre deux versions de manuscrit.

Développé sur `feat/generic-manuscript-workflow-20261029` le 2026-10-29, sans modification des textes littéraires.
