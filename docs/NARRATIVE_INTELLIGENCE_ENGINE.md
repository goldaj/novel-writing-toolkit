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


## Import des bibles historiques (nouveauté intégrée)

Le convertisseur tools/import_legacy_narrative.py accepte une mémoire d'événements historique, un fichier de connaissances facultatif et un fichier de relations facultatif. Il fonctionne uniquement avec des fichiers locaux, sous le contrôle de leur propriétaire :

    python tools/import_legacy_narrative.py CHEMIN_DU_PROJET CHRONOLOGIE.json --knowledge CONNAISSANCES.json --relations RELATIONS.json --out MEMOIRE_PRIVEE.json

Il identifie les citations par les chemins déclarés dans project.json, même si les archives utilisaient une racine de dépôt plus longue. Il crée des événements et des états épistémiques compatibles avec le moteur v1, puis vérifie le résultat.

**Choix de sûreté** : une séquence de chapitre n'est pas un ordre chronologique fictionnel ; une note de connaissance historique n'est pas une preuve de vérité ; un identifiant de règle sans événement cible n'est pas une causalité fiable. Le convertisseur marque donc ces éléments comme non déterminés, conserve les règles anciennes dans legacy_unmapped_rules, et laisse leur qualification à l'auteur.

Les sorties locales peuvent contenir des citations privées. Ne pas les versionner dans le dépôt public. Le test synthetic tests/test_import_legacy_narrative.py couvre migration, chemins, refus des sorties destructrices et absence d'inférence temporelle.

**Contrat de preuve renforcé** : lorsqu'une citation source ne peut plus être retrouvée, tout soutien causal qui en dépend devient uncertain ; un extrait périmé ne peut pas servir à conclure supported.

## Validation humaine interactive et suivi de décisions

Le rapport HTML propose un statut et une note par anomalie ou conséquence. Choix possibles : à examiner, problème confirmé, choix volontaire, faux positif, réécriture nécessaire. Cliquer sur « Exporter mes décisions (JSON) » crée localement narrative-decisions.json. Aucun compte, serveur ou transfert n'est nécessaire.

Réexaminer après révision :

    python tools/narrative_intelligence.py compare AVANT APRES MEMOIRE_AVANT.json MEMOIRE_APRES.json --review-decisions narrative-decisions.json --json-out rapport.json --html-out rapport.html

Une décision porte une empreinte de l'élément examiné. Si les éléments de preuve changent, elle devient obsolète et l'auteur doit la réexaminer. Une décision ne supprime jamais de diagnostic. Les décisions sur des anomalies désormais absentes restent signalées dans review_warnings. Le JSON peut contenir des notes personnelles : le conserver en privé.

## Importateur de mémoire historique

    python tools/import_legacy_narrative.py PROJET_CHAPITRES chronologie.json --knowledge knowledge.json --relations relations.json --out dossier-prive/import.json

L'importateur préserve les événements annotés, les citations, les notes de connaissance et les règles historiques. Il ne déduit pas les dates fictionnelles de l'ordre des fichiers. Un statut historique de connaissance inconnu devient un soupçon à qualifier plutôt qu'une vérité. Les règles sans événement destinataire certain sont préservées dans legacy_unmapped_rules, sans activation automatique. Il faut les rattacher explicitement aux événements pour bénéficier d'une propagation causale fiable.

## Barrières de validation

Une CI verte prouve la conformité aux scénarios automatisés, pas la cohérence complète d'un roman. La qualification réelle exige un contrôle éditorial des liens, temps, savoirs et faux positifs. Tous les contenus et rapports sur manuscrits privés restent hors du dépôt public.

## Assistance d'extraction par modèle local (expérimentale et facultative)

Le script tools/narrative_local_assist.py peut proposer des candidats événementiels, faits, connaissances et liens causaux à partir des paragraphes d'un manuscrit **local**. Il est désactivé tant que l'utilisateur n'a pas ajouté l'option --allow-local-model. Il ne contacte que http://127.0.0.1:11434/api/generate et refuse les URLs distantes, redirections et proxies.

Exemple avec Ollama installé et un modèle déjà téléchargé sur la machine :

    python tools/narrative_local_assist.py MON_ROMAN --model NOM_DU_MODELE_LOCAL --allow-local-model --max-blocks 20 --out DOSSIER_PRIVE/candidats.json

Le traitement est borné par défaut à 20 blocs de texte. Le rapport donne next_block et all_blocks : utiliser --start-block pour poursuivre sur d'autres blocs, sans recopier aveuglément le JSON dans la mémoire validée. Une citation doit être retrouvée dans le passage effectivement fourni au modèle, sinon la proposition est rejetée. Cela vérifie seulement la présence du texte, **pas** la vérité de l'interprétation.

Chaque candidat a status=pending_author_review et trust=hypothesis. Les faits et liens suggérés doivent être acceptés, corrigés et datés par l'auteur avant de figurer dans la mémoire v1. Aucun ajout automatique de candidats au graphe causal. Le test automatisé simule un modèle ; **aucun Ollama réel, aucune performance sémantique ni précision sur roman complet n'ont été validés**.

Les fichiers JSON de candidats contiennent des extraits du manuscrit et doivent rester privés. Le programme n'émet aucun passage dans les journaux. Un service local peut toutefois avoir sa propre configuration réseau : vérifier la politique du moteur installé avant de lui soumettre du contenu confidentiel. API utilisée : https://docs.ollama.com/api/generate.
