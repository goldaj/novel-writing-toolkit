# Audit contradictoire et passation — goldaj/novel-writing-toolkit

2026-10-30 : 4 branches, 3 PR et fichiers racine vérifiés. **Aucun export EPUB ni test local exécuté**.

## Branches
`main` : `5e7c80c345bdc5a524449b4931be0644d662f5d1`.
- `chatgpt/review-20261024` : behind, 0 commit(s) exclusif(s), 22 de retard ; contenu déjà dans main, candidate nettoyage.
- `feat/epub-export-manuscript-20261029` : behind, 0 commit(s) exclusif(s), 12 de retard ; contenu déjà dans main, candidate nettoyage.
- `feat/generic-manuscript-workflow-20261029` : behind, 0 commit(s) exclusif(s), 11 de retard ; contenu déjà dans main, candidate nettoyage.

## PR
- [#3](https://github.com/goldaj/novel-writing-toolkit/pull/3) : closed, fusionnée, feat: export validated manuscripts as reflowable EPUB 3 books.
- [#2](https://github.com/goldaj/novel-writing-toolkit/pull/2) : closed, fusionnée, feat: generic offline manuscript creation, assembly and editorial QA.
- [#1](https://github.com/goldaj/novel-writing-toolkit/pull/1) : closed, fusionnée, [ChatGPT] Tests d'assemblage portable d'un manuscrit générique.

## Arborescence
`.github`, `.gitignore`, `AGENTS.md`, `README.md`, `docs`, `tests`, `tools`.

## Défauts potentiels à rechercher
1. Vérifier la cohérence du pipeline manuscrit : création de chapitres, ordre, notes, métadonnées, titres et caractères spéciaux français/japonais.
2. Export EPUB 3 : tester dans plusieurs lecteurs, table des matières, liens internes, images, navigation et package XML valide.
3. Contrôler la fidélité intégrale du contenu source : aucune réécriture, omission de passage ou altération silencieuse.
4. Vérifier l'usage générique et hors ligne de l'outil, sans contamination par les projets narratifs privés.
5. Relancer la CI, les tests d'assemblage et d'EPUB ; distinguer tests passés en CI antérieure et test exécuté maintenant.
6. Les anciennes branches sont déjà ancêtres du code de référence ; ne pas créer de PR de fusion redondante et vérifier les références avant suppression.
