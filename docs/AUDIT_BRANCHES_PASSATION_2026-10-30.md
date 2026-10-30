# Audit de branches et passation agent — 2026-10-30

**Projet :** Chaîne générique d'assemblage et d'export de manuscrits. La présente passe est une lecture statique GitHub/README/AGENTS ; aucun test ou build exécuté et aucune validation utilisateur supposée.

## Branches : base `main`
- `chatgpt/review-20261024` (`3bf9390067f6cd8a2128e9dbd19e6a99f709977a`) : branche à réévaluer par comparaison SHA avant suppression
- `feat/epub-export-manuscript-20261029` (`649818a96f0699aaaccdff7a965e1d75a66be270`) : comparaison directe behind (ahead 0, behind 14)
- `feat/generic-manuscript-workflow-20261029` (`e100d99c38d3cd682adaaf75c12fdbcd0da6ec0a`) : branche à réévaluer par comparaison SHA avant suppression
- `main` (`e8fbaaa3cb54bea1df2f617a27d0122d5f99aa87`) : branche de référence, conserver

## Pull requests
- [#3](https://github.com/goldaj/novel-writing-toolkit/pull/3) : fusionnée. `feat/epub-export-manuscript-20261029` vers `main`.
- [#2](https://github.com/goldaj/novel-writing-toolkit/pull/2) : fusionnée. `feat/generic-manuscript-workflow-20261029` vers `main`.
- [#1](https://github.com/goldaj/novel-writing-toolkit/pull/1) : fusionnée. `chatgpt/review-20261024` vers `main`.

## Mise à l'épreuve du travail réalisé
Vérifier portabilité des chemins, ordre des chapitres, encodage Unicode, métadonnées EPUB, structure ZIP/OPF/navigation et absence de fuite de textes privés dans les fixtures. Ne pas supprimer scripts legacy ; les tests synthétiques ne valident pas un lecteur EPUB réel.

## Prochain agent : étapes
Lire docs/GENERIC_WORKFLOW.md, lancer tests unittest sur exemples factices, valider un EPUB avec un validateur indépendant, ouvrir dans lecteur réel et ne publier aucun manuscrit.

## Sécurité et méthode de consolidation
Relire `README.md` (# Novel Writing Toolkit), `AGENTS.md`, `docs/CHATGPT_PROJECT_HISTORY.md`. Les branches fusionnées historiquement peuvent encore exister ; leur suppression exige vérification des références externes et des SHA. Ne pas déplacer de textes privés ou de secrets. Aucun code, PR, branch ni déploiement modifié dans cette passe ; seul ce document a été ajouté.
