# Export EPUB 3 sans dépendances — 29 octobre 2026

## Pourquoi

Le pipeline `init` / `check` / `build` assemble un texte brut et génère un rapport de qualité. Il ne produisait pas de livre lisible sur liseuse. Ce chantier ajoute `epub`, une véritable sortie **EPUB 3 reflowable**, depuis les sections déjà validées, et non un HTML renommé.

## Utiliser dans PyCharm ou en ligne de commande

```bash
python tools/manuscript_pipeline.py init mon-roman --chapters 3 --title "Mon roman"
# Compléter mon-roman/sections/chapter_01.txt etc.
python tools/manuscript_pipeline.py check mon-roman
python tools/manuscript_pipeline.py epub mon-roman --author "Nom d'auteur"
# => mon-roman/manuscript.epub
```

Options : `--language fr` (ou `fr-FR`), `--output nom.epub` pour un chemin **relatif au dossier projet**, `--json` pour le bilan QA en sortie standard, `--force` pour écraser **explicitement** un EPUB précédemment généré. Les fichiers de sections et `project.json` ne peuvent jamais être cibles d'export. L'export ne commence **que si `check` réussit**.

## Structure EPUB produite

`tools/epub_export.py` écrit une archive ZIP avec :
- première entrée non compressée `mimetype` contenant exactement `application/epub+zip` ;
- `META-INF/container.xml` pointant vers `EPUB/package.opf` ;
- manifeste OPF 3 avec langue, titre, identifiant stable lié au contenu, créateur optionnel, date de modification, fichiers et ordre du `spine` ;
- `EPUB/nav.xhtml` avec une table des matières listant les chapitres ;
- `EPUB/text/chapter-001.xhtml` etc., UTF-8 et XML valide, titres de section et paragraphes ;
- `EPUB/styles/main.css` : mise en page reflowable simple.

Le contenu est échappé systématiquement (**aucun HTML embarqué depuis le manuscrit**). Les paragraphes sont formés à partir des lignes séparées par une ligne vide ; les lignes commençant par `## ` deviennent des sous-titres. Le reste est traité comme du texte brut. Cela ne constitue **pas** un moteur Markdown complet : les italiques, images, notes de bas de page et styles complexes ne sont pas interprétés.

Le fichier est écrit dans un répertoire temporaire du dossier cible puis remplacé atomiquement après contrôle d'intégrité de la ZIP, pour éviter de conserver un livre partiellement écrit en cas d'erreur. La sortie est privée, dans le projet local, pas dans le dépôt.

## Tests et limites

```bash
python -m unittest discover -s tests -v
python tools/manuscript_pipeline.py epub --help
```

`tests/test_epub_export.py` couvre : signature ZIP et ordre `mimetype`, manifeste/titres/auteur/ordre des chapitres, table des matières, échappement de `&` et `<`, conformité XML de toutes les pages, refus de l'écrasement sans `--force`, protection contre les chemins hors projet, blocage après un contrôle qualité raté, et caractères incompatibles avec XML.

**Limites de preuve :** cette suite automatise la structure XML/ZIP et la non-destruction ; elle ne remplace pas un validateur EPUBCheck officiel ni un essai visuel réel sur Kobo/Kindle/Calibre. Une compatibilité universelle ne doit donc pas être revendiquée. Il n'y a pas d'images/couverture ni de polices embarquées dans cette première version. Le champ `dcterms:modified` reflète l'export du jour, donc deux exports ne sont pas byte-identiques.

## Reprise Codex

- Branche `feat/epub-export-manuscript-20261029` empilée sur `feat/generic-manuscript-workflow-20261029` (PR #2). Examiner aussi PR #1 de revue ; ne pas fusionner sans la base.
- Lire `README.md`, `AGENTS.md`, `docs/GENERIC_WORKFLOW.md` et `docs/CHATGPT_PROJECT_HISTORY.md`. Ne pas modifier ni supprimer les anciens scripts du projet littéraire d'origine.
- Vérifier Python 3.10 et 3.12 par CI, ouvrir un EPUB synthétique dans Calibre et lancer EPUBCheck si disponible, avant toute publication ou intégration.
- Ensuite : couverture optionnelle, styles configurables, gestion des citations et vrais titres Markdown, comparaison EPUB générés, export PDF/DOCX uniquement si demandé dans un flux adapté. Une compatibilité réelle avec les EPUB3 complets et liseuses nécessite des tests supplémentaires.
- Aucun manuscrit, brouillon, dialogue, corpus privé ni donnée d'auteur réelle n'a été consulté, généré ou committé.
