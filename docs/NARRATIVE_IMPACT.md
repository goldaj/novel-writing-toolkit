# Narrative Impact : cohérence causale entre deux révisions d'un roman

**Objectif :** distinguer un changement de description d'un changement qui remet en cause une motivation, une scène ou ses conséquences, parfois plusieurs dizaines de chapitres plus loin.

Cet outil ne remplace pas une relecture éditoriale. Ses trois niveaux de preuve sont distincts : passages textuels retrouvés, liens de causalité déclarés par l'auteur, hypothèses émises par un modèle IA. Une absence de lien détecté ne prouve jamais l'absence d'impact.

## Démarrage local sans API

Préparer deux **copies locales** du même projet compatible avec `manuscript_pipeline.py`, chacune avec `project.json` et ses fichiers de chapitres. Ne jamais pousser ces copies dans ce dépôt public.

```bash
python tools/narrative_impact.py examples/narrative-impact/avant examples/narrative-impact/apres --dossier examples/narrative-impact/dossier.json --json-out /tmp/impacts.json --html-out /tmp/impacts.html
```

Le HTML présente les paragraphes modifiés, les candidats d'échos lointains et les conséquences tracées. Le JSON est destiné à d'autres outils. L'analyse sans `--dossier` fonctionne mais se limite aux changements textuels et aux candidats lexicaux à vérifier. Cette comparaison n'envoie aucun contenu sur un réseau.

### Contrat des faits et des causes

Le dossier JSON est facultatif et suit cette structure :

```json
{
  "format_version": 1,
  "aliases": ["Léo"],
  "facts": [
    {"id":"taille","before":"petit","after":"grand"},
    {"id":"constitution","before":"chétif","after":"chétif"},
    {"id":"yeux","before":"verts","after":"bleus"}
  ],
  "rules": [
    {
      "id":"brimades", "label":"La maltraitance est justifiée",
      "because_any":[[{"fact":"taille","equals":"petit"}],[{"fact":"constitution","equals":"chétif"}]],
      "evidence_terms":["brimad","maltrait"]
    },
    {
      "id":"fuite","label":"La fuite dépend des brimades",
      "because_any":[[{"rule":"brimades"}]],
      "evidence_terms":["fui","fuir"]
    }
  ]
}
```

La valeur de `because_any` représente des justifications alternatives (OU) ; chaque liste interne exprime des conditions cumulatives (ET). Les conditions peuvent pointer vers un fait ou une autre règle : ainsi le changement de taille peut avoir un effet transitive sur une fuite racontée au chapitre 80. Les cycles et références inexistantes sont rejetés.

Résultats typiques : `alternative_justification`, `justification_lost_with_remaining_scene`, `justification_lost_scene_not_found`, `support_preserved`, `newly_justified`, `no_declared_dependency`. Ce dernier statut signifie seulement **qu'aucun lien n'a été déclaré**. Les mots de scènes servent de **recherche lexicale**, non de validation sémantique. Même une justification alternative compatible avec la règle doit être **réellement lisible dans la scène**.

Dans l'exemple, petit → grand est compensé par chétif (dans le contrat déclaratif), les brimades persistent au chapitre 2 et la fuite au chapitre 3 ; les yeux verts → bleus sont considérés sans *dépendance déclarée*. L'outil ne dira pas que ce changement est objectivement sans incidence dans un roman complet.

## Assistance IA, facultative et avec consentement explicite

Elle peut proposer des faits modifiés, explorer des raisons implicites et chercher leurs conséquences ou substitutions. Cela implique un service externe **uniquement lorsqu'il est choisi** ; contrairement au moteur local, le mode IA envoie des extraits du manuscrit aux API d'OpenAI. L'abonnement ChatGPT ne fournit pas de quota API gratuit. Lire les conditions de traitement des données et maîtriser coûts et confidentialité avant utilisation.

Mettre la clé dans la variable d'environnement `OPENAI_API_KEY` (jamais dans la commande ou dans Git), choisir un modèle compatible avec les sorties structurées et autoriser explicitement le transfert :

```bash
python tools/narrative_impact_ai.py examples/narrative-impact/avant examples/narrative-impact/apres --model MODELE_COMPATIBLE --allow-upload --max-changes 8 --contexts 28 --json-out /tmp/hypotheses.json --html-out /tmp/hypotheses.html
```

Pipeline : (1) chaque bloc changé est fourni au modèle qui propose jusqu'à cinq modifications de faits avec **citations exactes** des deux versions, (2) le programme recherche des candidats dans tous les chapitres sur des critères lexicaux, (3) le modèle examine des passages sourcés pour proposer une causalité, un remplacement de justification ou une incertitude, (4) le programme vérifie que les citations renvoient bien à des paragraphes réellement transmis ; toute citation invalide dégrade la conclusion en `uncertain`.

**Limite de couverture :** les changements de texte sont bornés par `--max-changes` (8 par défaut) et les extraits candidats par `--contexts` (28). Le rapport indique les blocs non traités. Un événement très lointain sans mot commun peut ne pas être récupéré. Même avec citations, une IA peut mal comprendre l'intention, les causes, les personnages, les mensonges et la focalisation ; **la confirmation humaine reste obligatoire**. Les tests automatisés simulent l'API, aucun appel réel n'a été vérifié dans la CI.

Documentation officielle du format des réponses : https://platform.openai.com/docs/guides/structured-outputs . L'implémentation utilise l'API Responses avec `text.format.json_schema`, `strict=true` et `store=false`.

## Confidentialité, livraison et limites

- Aucun manuscrit privé ni texte de l'utilisateur n'est stocké dans ce dépôt. L'exemple est intégralement fictif.
- Les rapports JSON/HTML **contiennent des extraits** : les garder dans un dossier personnel, hors de Git public.
- Le moteur local n'écrit jamais dans les chapitres ; les sorties n'écrasent pas un rapport existant sans `--force`.
- Un gros déplacement de scènes peut apparaître comme suppression + ajout dans le diff. Les chapitres peuvent être réordonnés ou ajoutés, mais leur correspondance se fait actuellement par **chemin relatif**, non par identité sémantique.
- La validation de causalité déclarative suppose que le dossier rédigé par l'auteur est correct ; il ne prouve pas automatiquement que le texte justifie ces faits.
- Le résultat IA repose sur un échantillon de paragraphes : il sert à orienter la lecture, **pas à certifier l'absence d'incohérence**.
- Tests : `python -m unittest discover -s tests -v` sous Python 3.10 et 3.12. Les scripts historiques, le manuscrit, le pipeline `build` et l'export EPUB restent inchangés.

## Développements ultérieurs réellement utiles

1. Extraction d'une bible canonique chronologique par personnage, avec origine et date de validité de chaque fait.
2. Recherche sémantique multi-passes et indexation de tous les chapitres, au-delà des mots communs.
3. Alignement des scènes déplacées, fusionnées ou séparées entre versions.
4. Suivi des obligations scénaristiques, motivations, promesses, connaissances et mensonges, avec voies alternatives.
5. Benchmarks aveugles annotés par un auteur pour mesurer précision, rappel et taux de faux positifs sur des textes longs.
6. Interface de validation « accepté / corrigé / volontaire » avec export des décisions vers une bible de continuité.

**Pas de réécriture automatique d'un roman à partir d'une conclusion non vérifiée.**

## Pont pour une mémoire chronologique existante

Le [convertisseur de mémoires chronologiques](../tools/chronology_to_dossier.py) accepte un index d'événements sourcé et un fichier séparé décrivant **explicitement les dépendances causales**. Il en déduit le fichier `--dossier` compatible avec ce module. Il est **hors ligne**, ne fait aucune extraction IA et ne garantit aucune cohérence sémantique. Voir [l'étude sur la future IA locale](LOCAL_NARRATIVE_AI_RESEARCH.md), les limites du format baseline et les exemples de commande. Les fichiers de mémoire d'un roman privé doivent rester dans leur dépôt privé.
