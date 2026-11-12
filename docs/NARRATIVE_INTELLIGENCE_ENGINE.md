# Narrative Intelligence Engine v1

Date : 12 novembre 2026. Statut : fonctionnalité expérimentale, sans IA ni API réseau obligatoire. Python 3.10+ et bibliothèque standard uniquement. Le moteur agit uniquement sur des manuscrits et annotations fournis localement.

## Vision produit et périmètre PO

Problème : un changement au chapitre 2 peut invalider une motivation au chapitre 40. Une simple recherche de mots ne distingue pas vérité du monde, croyance des personnages, chronologie et dépendances causales.

**Promesse v1** : analyser une mémoire narrative **explicitement annotée par l'auteur**, valider ses ancrages textuels, produire une chronologie temporelle, examiner connaissances et contradictions, puis guider la relecture des scènes impactées entre deux versions. Les conclusions sont des alertes de relecture, jamais une certification de cohérence ou une réécriture automatique.

**Exclus** : extraction automatique fiable depuis un roman, interprétation des intentions implicites, garantie de cohérence littéraire, mise à jour automatique des manuscrits, publication de textes privés, facturation API, serveur ou comptes.

## Démarrage et livrables

Depuis la racine du dépôt :

    python tools/narrative_intelligence.py audit examples/narrative-intelligence/avant examples/narrative-intelligence/memory-before.json --json-out rapport.json --html-out rapport.html

    python tools/narrative_intelligence.py compare examples/narrative-intelligence/avant examples/narrative-intelligence/apres examples/narrative-intelligence/memory-before.json examples/narrative-intelligence/memory-after.json --json-out evolution.json --html-out evolution.html

    python -m unittest discover -s tests -v

Sous Windows, les mêmes commandes fonctionnent avec Python installé. Les fichiers de sortie peuvent être placés dans un dossier personnel. Les HTML sont consultables hors ligne et filtrables. La commande refuse par défaut d'écraser les rapports, même existants ; --force doit être explicite. Elle refuse toujours d'écraser ses propres fichiers d'entrée.

Livrables : tools/narrative_memory.py (modèle et analyse), tools/narrative_intelligence.py (CLI et HTML/JSON), tests/test_narrative_intelligence.py (contrats synthétiques), exemples fictifs. Les outils d'assemblage, d'EPUB et d'analyse de paragraphes existants restent intacts.

## Modèle de données

Un manuscrit utilise le project.json déjà supporté par manuscript_pipeline.py. La mémoire est un fichier JSON séparé avec schema_version = 1 et cinq tableaux :

- characters : id, name, aliases optionnels.
- events : id, label, time_index optionnel, precedes (IDs ultérieurs), participants, requires_knowledge, source.
- facts : id, subject (personnage ou world), attribute, value, from_event et until_event optionnels, confidence (confirmed ou tentative), source.
- knowledge : id, character, fact, state (knows, believes, suspects), since_event et until_event optionnels, believed_value optionnel, source.
- dependencies : id, effect_event, because_any, source.

Tout enregistrement autre qu'un personnage requiert une source de forme :

    "source": {"chapter": "sections/chapter_01.txt", "quote": "La phrase authentique ici."}

La citation est cherchée dans un chapitre déclaré par project.json, après normalisation des espaces. Si elle disparaît, une alerte stale_source apparaît. Les chemins non déclarés, IDs manquants, références inconnues et cycles sont refusés.

Les relations because_any sont un OU de groupes ET, par exemple :

    "because_any": [
      ["fact:map=usable", "knowledge:k_map"],
      ["fact:rope=ready"]
    ]

Les jetons sont event:ID, fact:ID, fact:ID=valeur, knowledge:ID. Ils décrivent des hypothèses causales établies par l'auteur, pas des inférences naturelles.

Les temps fictionnels sont des entiers time_index ; null ou absent signifie temps indéterminé. Les intervalles des faits et connaissances sont [début inclus, fin exclue]. Une incertitude temporelle mène au statut uncertain, jamais à une invention de date. Les états des causes sont supported, unsupported et uncertain.

## Critères d'acceptation et cas QA

1. **Flashback** : ordonnancement par time_index plutôt que chapitre ; cycles et contraintes precedes impossibles rejetés.
2. **Connaissance** : un événement qui requiert une information acquise ultérieurement est signalé ; l'absence de déclaration produit une piste de relecture, pas un verdict.
3. **Monde versus croyances** : deux faits mondiaux incompatibles et confirmés, simultanément valables, sont signalés ; une croyance divergente n'est pas fusionnée avec la vérité du monde.
4. **Cause lointaine** : changement d'une propriété de carte au chapitre 1, perte de soutien de la traversée au chapitre 2, et impact sur une scène du chapitre 3 via le graphe.
5. **Alternative** : une corde peut remplacer une carte et maintenir une justification déclarée ; la révision mérite tout de même une vérification éditoriale.
6. **Provenance** : un extrait devenu introuvable est signalé ; le moteur n'invente pas de citations.
7. **Confidentialité et intégrité** : zéro requête réseau ; HTML échappé ; pas d'écrasement de la source ni modification du manuscrit.
8. **Compatibilité** : les tests existants continuent de fonctionner en Python 3.10 et 3.12.

## Architecture et responsabilités

Entrée : projet manuscrit local + mémoire JSON annotée.
Contrat : contrôles du manifeste, des IDs, des citations, des graphes et des intervalles.
Moteur : chronologie, états du monde, connaissances par personnage, causes à trois valeurs.
Révisions : calcul de différences textuelles via narrative_impact.py + différence de mémoire + propagation transitive par graphe annoté.
Sortie : rapport JSON structuré et HTML autonome (sans ressources externes).

- PO : valeur utilisateur, critères de succès, exclusion des artifices de complexité.
- Architecte : schéma v1 et niveaux de preuve, compatibilité, réversibilité.
- Développeur : API locale réutilisable, non intrusive et déterministe.
- QA : scénarios fictifs positifs et négatifs, invariants et protections d'écriture.
- Sécurité : absence de réseau et séparation stricte public/privé.
- Expert éditorial : validation des liens causaux et des anomalies.
- DevOps : CI, branche isolée, aucune fusion automatique.

## Limitations, risques et décision de mise en production

La précision et le rappel sur un roman réel ne sont pas mesurés. Les événements, faits et causes doivent être annotés correctement. Des scènes déplacées ou fusionnées sous un autre identifiant ne sont pas automatiquement alignées. Une citation peut rester textuellement présente tout en ayant changé de sens. Le graphe ne découvre pas les conséquences implicites.

L'HTML/JSON peut contenir des citations privées : conserver les sorties hors des dépôts publics. Pour un manuscrit réel, les annotations et rapports doivent rester dans un dossier local ou dépôt privé explicitement choisi.

**Go technique** : CI verte et revue d'intégration ; **Go produit** : campagne privée sur un roman long avec exemples annotés, mesure des faux positifs et validation par l'auteur. Ce second seuil n'est pas atteint par les seuls tests synthétiques.

## Suite de la feuille de route

- Importateur de mémoire du roman privé Résurrectés, exclusivement dans son dépôt privé, sans réplication publique.
- Alignement d'événements renommés, déplacés ou fusionnés entre révisions.
- Extracteur assisté par IA **locale** avec citations et validation humaine, jamais accepté automatiquement.
- Interface de revue où l'auteur qualifie les alertes : vrai problème, faux positif, intention volontaire.
- Mesure de précision, rappel, coût et temps de relecture ; scénarios sur manuscrits longs et régressions de performance.

Lire également docs/NARRATIVE_IMPACT.md et docs/LOCAL_NARRATIVE_AI_RESEARCH.md. Les anciens travaux et formats ne sont ni effacés ni invalidés.
