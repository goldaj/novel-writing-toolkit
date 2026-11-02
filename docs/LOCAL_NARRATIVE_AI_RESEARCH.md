# Recherche et trajectoire : IA locale pour mémoire narrative

**Étude datée du 2 novembre 2026. Statut : étude et implémentation d'un pont de données, PAS d'installation d'une IA locale ni d'évaluation de qualité sur un roman réel.**
Ce dépôt est **public**. Aucune donnée du roman privé Résurrectés n'y est copiée.

## Objectif narratif précis

Il faut produire une mémoire exploitable pour comprendre si une modification à la page 8 modifie des comportements, révélations, motivations ou conséquences à la page 200, **sans** déclarer problématique une variation uniquement littéraire. Une même action peut garder sa validité grâce à une justification de remplacement. Une absence d'impact *détecté* n'est jamais la preuve d'une absence d'impact.

La sortie cible comprend : événement sourcé et ordonné ; personnages et aliases ; vérité du monde ; savoir de chaque personnage et son moment d'acquisition ; buts et croyances ; relations et états ; déclencheurs ; liens causaux alternatifs et transitifs ; conséquences plus loin ; décisions et incertitudes documentées. Les événements doivent citer une version, un fichier et un passage précis. Les règles causales doivent être **revues**, pas inférées comme certitudes à partir de la seule proximité des scènes.

## Options techniques examinées

| Composition | Fonction | Intérêt | Risque |
| --- | --- | --- | --- |
| **Ollama + Google LangExtract** | Première option de prototype : inférence locale et extraction sourcée de passages | Découpage des longs textes, extraction structurée, modèle local ; pas d'API payante par défaut | LangExtract ne fabrique pas un graphe causal fiable sans passes de consolidation, modèle/structure à tester |
| **LM Studio + pipeline Python** | Serveur d'inférence local alternatif, avec interface graphique | API locale de type OpenAI, facilité d'exploration des modèles | Comportement exact de l'extraction et des sorties contraintes à vérifier sur chaque modèle |
| **Gemini API (offre gratuite selon limites)** | Alternative hébergée, sans GPU local | Disponibilité possible sans achat de carte | Quotas, Internet et données envoyées à un tiers ; **pas adapté par défaut à un manuscrit privé** |
| **Qwen3 Embedding 0.6B** | Recherche sémantique locale sur les scènes distantes | Réduit les occasions de manquer un effet n'utilisant pas le même vocabulaire | Peut confondre proximité thématique et causalité ; métriques de rappel indispensables |

### Modèles à benchmarker, aucun gagnant établi

1. **Gemma 4 12B** : candidat initial pour extraction et raisonnement sur les textes.
2. **Qwen 3.5 9B** : alternative généralement plus légère.
3. **Ministral 3 14B** : autre candidat multilingue pour les textes français.
4. **Qwen 3.5 27B** : option à étudier sur matériel disposant de plus de VRAM/RAM.

Les catalogues et variantes changent : **revalider avant téléchargement** l'existence des tags, les licences, la quantification, la taille, les contraintes matérielles et la fenêtre réellement prise en charge. Les ordres de grandeur communiqués lors de l'étude étaient respectivement ~8 Go, ~7 Go, ~9 Go et ~17–20 Go pour des variantes quantifiées, mais **les poids sur disque ne sont pas la mémoire totale nécessaire**. Les contextes très longs utilisent davantage de RAM/VRAM et peuvent devenir lents. Sur 8 Go de VRAM, commencer plutôt par une classe 4B/9B ; avec 12 Go, étudier les 9B/12B ; avec 24 Go, considérer aussi 27B. Le débit CPU et la qualité du français doivent être mesurés, pas supposés.

### Références officielles à vérifier lors de la mise en œuvre

- Ollama : https://ollama.com/ et https://docs.ollama.com/api/introduction
- Google LangExtract : https://github.com/google/langextract
- LM Studio : https://lmstudio.ai/docs/app/api et https://lmstudio.ai/docs/developer/openai-compat/structured-output
- Ollama modèles : https://ollama.com/library ; recherche Gemma 4, Qwen 3.5, Ministral 3 et Qwen3-Embedding
- Google Gemini API : https://ai.google.dev/gemini-api/docs/pricing et https://ai.google.dev/gemini-api/terms

**Données personnelles et inédites :** une offre « gratuite » distante n'est pas synonyme de confidentialité. Vérifier conditions d'utilisation et politiques de traitement des données avant tout envoi ; aucune API externe ne doit être appelée sans demande explicite.

## Architecture recommandée

```text
projet / project.json + manuscrit versionné
  → paragraphes et scènes sourcés (IDs stables + empreinte du texte)
  → extraction locale par chapitre (personnages, actions, révélations, états)
  → résolution des identités et normalisation des faits
  → mémoire de vérité + chronologie + savoir individuel et croyances
  → consolidation interchapitres des contradictions et changements d'état
  → graphes de motivations et de causes alternatives (validation humaine)
  → pont chronology_to_dossier.py
  → dossier v1 (before / after, because_any)
  → analyse comparative : passages à reprendre et alternatives justificatives
```

L'IA n'avale pas 100 000 mots en une seule demande ; elle lit des scènes et produit des fiches courtes et ancrées. Une seconde passe relie les fiches entre chapitres. Une troisième passe cherche **à dessein les conséquences lointaines** par entités, recherche lexicale, éventuellement embeddings, et parcours des dépendances. Les citations doivent être vérifiées contre le fichier du manuscrit et la version concernée.

**Important :** détecter une contradiction de chronologie ne suffit pas à savoir si elle est une incohérence, un mensonge voulu, une erreur d'un témoin, un flash-back ou une révélation. La mémoire doit séparer `world_true`, `character_believes`, `character_knows` et `reader_knows`, avec dates d'acquisition et sources.

## Pont déjà codé : conversion vers Narrative Impact v1

`tools/chronology_to_dossier.py` convertit un **index de mémoire** (`schema_version:1`, `events` contenant `id`, `description`, `evidence`) et une **carte de liens annotés** (`format_version:1`, `manual_facts`, `rules`, `because_any`) en `dossier` directement lisible par `tools/narrative_impact.py --dossier`.

Un exemple minimal de liens, entièrement fictif :

```json
{
  "format_version": 1,
  "aliases": ["Mira"],
  "manual_facts": [
    {"id":"F_TECHNIQUE","label":"Mira a appris une autre technique",
     "evidence":{"path":"chapter_02.txt","line":15}}
  ],
  "rules": [
    {
      "id":"R_OUVERTURE",
      "label":"Justification de l'ouverture du portail",
      "because_any":[["E001"],["F_TECHNIQUE"]],
      "evidence_terms":["portail","ouvre"],
      "review_note":"Relire la scène où Mira ouvre le portail"
    },
    {
      "id":"R_FUITE",
      "because_any":[["rule:R_OUVERTURE","E008"]],
      "evidence_terms":["fuite","parvient"]
    }
  ]
}
```

Les chaînes de `because_any` sont en **OU** entre sous-listes ; chaque sous-liste est en **ET**. Une référence `rule:R_OUVERTURE` crée une dépendance transitive. Le convertisseur teste ces liens avec le **vrai validateur et évaluateur du toolkit** ; il refuse les cycles et identifiants manquants. Les faits conservant le même ID entre les versions sont présumés de même signification, mais **cela reste une hypothèse éditoriale**, pas une analyse sémantique.

Commande :

```bash
python tools/chronology_to_dossier.py /chemin/prive/memoire_evenements_v0_1.json /chemin/prive/relations_v0_1.json --out /chemin/prive/dossier_v0_1.json
python tools/narrative_impact.py /chemin/prive/version1 /chemin/prive/version2 --dossier /chemin/prive/dossier_v0_1.json --html-out /chemin/prive/rapport.html
```

Le **dossier initial** issu d'une seule version contient logiquement `before = after = present` pour les événements connus. Il constitue le **référentiel**, pas un détecteur de modifications magiques. Pour une véritable révision, fournir `--revised` (index de nouvelle version avec IDs stables), ou `--overrides` (fichier JSON de valeurs `present` / `absent` explicitement validées par l'auteur). Des modifications de sens sans changement d'ID demandent une relecture : le convertisseur ne les déduit pas tout seul.

Le format v1 ne représente pas encore correctement tous les états temporels : un fait peut devenir vrai puis faux au sein d'une même version ; une croyance peut être erronée ; une cause est parfois implicite. La prochaine évolution de schéma devra distinguer les **faits de canon**, les **événements datés**, les **connaissances** et les **dépendances vérifiées** ; la rétrocompatibilité v1 est à maintenir.

## Benchmark proposé avant d'ajouter une IA

Tester les moteurs avec un roman privé autorisé, une mémoire de référence vérifiée et **cinq mutations contrôlées** : (1) suppression de l'apprentissage d'une compétence utilisée plus tard, (2) révélation connue trop tôt, (3) événement pivot supprimé avec conséquences toujours présentes, (4) simple changement de couleur sans signification, (5) cause remplacée par une justification explicite.

Mesurer **rappel causal**, précision, faux positifs, nombre de références exactes, respect de l'ordre temporel, cohérence des savoirs, temps, RAM/VRAM et pourcentage du roman effectivement examiné. Vérifier toutes les conclusions sur des scènes du texte, pas seulement sur la sortie d'un modèle.

La mémoire manuelle existante de *Résurrectés* (89 événements, 18 relations) sert de **référence initiale partielle**, pas de vérité exhaustive et pas de données à publier ici. Un benchmark qui ne regarde que cette mémoire sous-estimera ses propres manques.

## Plan de réalisation après sélection

1. Évaluer 2 modèles locaux sur extraits fictifs et roman privé : JSON strict, extraction sourcée, stabilité des identités.
2. Intégrer LangExtract et Ollama sur le PC, sans API distante par défaut.
3. Produire des **fiches chronologiques par personnage**, et une table « sait / ignore / croit / a appris ».
4. Consolidation interchapitres, recherche sémantique locale et validation des liens proposés.
5. Adapter automatiquement les *mémoires de deux versions*, réviser les faits transformés et produire un rapport lisible des impacts.
6. Préparer un fonctionnement incrémental et des tests de non-régression des causalités.

**État actuel :** analyse d'architecture et **convertisseur déterministe** livrés. Aucun modèle Ollama, LangExtract ou LM Studio n'a été intégré, ni benchmark effectué, ni données de livre inédit copiées vers ce dépôt public.
