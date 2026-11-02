"""Opt-in AI analysis tests run entirely offline with fake model responses."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import manuscript_pipeline as pipeline
import narrative_impact_ai as ai


class NarrativeAITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.old = root / "old"
        self.new = root / "new"
        for d in (self.old,self.new):
            pipeline.initialize(d, 3, "Fiction synthétique")
        def chapter(d,n,text):
            (d / "sections" / f"chapter_{n:02}.txt").write_text(
                f"Chapitre {n}\n\n{text}\n",encoding="utf-8")
        chapter(self.old, 1, "Léo était petit et chétif. Ses yeux étaient verts.")
        chapter(self.new, 1, "Léo était grand mais chétif. Ses yeux étaient bleus.")
        chapter(self.old, 2, "Léo était maltraité par ses camarades.")
        chapter(self.new, 2, "Léo était maltraité par ses camarades.")
        chapter(self.old, 3, "Léo s'enfuit loin de la ville à cause des brimades.")
        chapter(self.new, 3, "Léo s'enfuit loin de la ville à cause des brimades.")

    def fake(self, name, schema, payload):
        if name == "narrative_claims":
            return {"claims": [
                {"subject":"Léo", "before":"petit", "after":"grand",
                 "old_quote":"petit", "new_quote":"grand",
                 "category":"character_trait","search_terms":["maltraité","brimades","chétif"]},
                {"subject":"Léo", "before":"yeux verts", "after":"yeux bleus",
                 "old_quote":"yeux étaient verts","new_quote":"yeux étaient bleus",
                 "category":"style_or_surface","search_terms":["yeux"]},
            ]}
        if "yeux" in payload["claim"]["before"]:
            return {"verdict":"no_detectable_narrative_impact",
                    "explanation":"La couleur des yeux ne motive aucune scène citée.",
                    "confidence":"low","references":[],"next_checks":[]}
        return {
            "verdict":"alternative_justification_found",
            "explanation":"La chétivité peut rester une vulnérabilité malgré la taille.",
            "confidence":"medium",
            "references":[{"version":"new","chapter":"sections/chapter_01.txt",
                           "paragraph":2,"quote":"chétif","role":"new_justification"}],
            "next_checks":["Vérifier les motivations des camarades"],
        }

    def test_lexical_retrieval_finds_distant_effect_and_accepts_valid_quote(self):
        change={"after":[{"chapter":"sections/chapter_01.txt","paragraph":2}]}
        from narrative_impact import paragraphs
        old, oc=paragraphs(self.old)
        new, nc=paragraphs(self.new)
        claim={"subject":"Léo","before":"petit","after":"grand",
               "search_terms":["maltraité","brimades","chétif"]}
        selected=ai.select_context(claim,change,old,new,oc,nc)
        self.assertTrue(any(p["chapter"]=="sections/chapter_03.txt" for p in selected))
        refs, invalid=ai.validate_references({"references":[{
            "version":"new","chapter":"sections/chapter_03.txt",
            "paragraph":2,"quote":"brimades","role":"later_consequence"
        }]},old,new,selected)
        self.assertEqual(invalid,0)
        self.assertEqual(len(refs),1)

    def test_full_review_marks_model_judgments_as_hypotheses(self):
        report=ai.assess(self.old,self.new,"fake-model",self.fake)
        self.assertEqual(report["ai"]["changes_processed"],1)
        self.assertEqual(len(report["ai"]["assessments"]),2)
        self.assertTrue(all(item["review_required"] for item in report["ai"]["assessments"]))
        self.assertEqual([i["verdict"] for i in report["ai"]["assessments"]],
                         ["alternative_justification_found","no_detectable_narrative_impact"])
        self.assertIn("Hypothèses",ai.render_ai_html(report))

    def test_reject_fabricated_quotes_and_unexposed_citations(self):
        def bad(name,schema,payload):
            if name=="narrative_claims":
                return {"claims":[{"subject":"Léo","before":"petit","after":"grand",
                     "old_quote":"petit","new_quote":"grand",
                     "category":"character_trait","search_terms":["maltraité"]}]}
            return {"verdict":"alternative_justification_found","explanation":"Intuition",
                    "confidence":"high","references":[{"version":"new",
                    "chapter":"sections/chapter_03.txt","paragraph":2,"quote":"Léo a volé",
                    "role":"new_justification"}],"next_checks":[]}
        report=ai.assess(self.old,self.new,"fake",bad)
        row=report["ai"]["assessments"][0]
        self.assertEqual(row["verdict"],"uncertain")
        self.assertEqual(row["confidence"],"low")
        self.assertEqual(row["invalid_model_references"],1)
        self.assertEqual(row["evidence"],[])

    def test_reject_fabricated_changes(self):
        def liar(name,schema,payload):
            return {"claims":[{"subject":"Léo","before":"petit","after":"grand",
                "old_quote":"jamais dans le texte","new_quote":"grand",
                "category":"character_trait","search_terms":["brimades"]}]}
        result=ai.assess(self.old,self.new,"fake",liar)
        self.assertEqual(result["ai"]["assessments"][0]["rejected_model_claims"],1)

    def test_empty_claims_no_review_calls(self):
        calls=[]
        def silent(name,schema,payload):
            calls.append(name)
            return {"claims":[]}
        report=ai.assess(self.old,self.new,"mock",silent)
        self.assertEqual(calls,["narrative_claims"])
        self.assertEqual(report["ai"]["assessments"],[])

    def test_output_text_checks_response_shape(self):
        res={"status":"completed","output":[{"type":"message","content":[
            {"type":"output_text","text":'{"claims":[]}'}]}]}
        self.assertEqual(json.loads(ai.output_text(res)),{"claims":[]})
        with self.assertRaises(ai.ProjectError):
            ai.output_text({"status":"incomplete","output":[]})
        with self.assertRaises(ai.ProjectError):
            ai.output_text({"status":"completed","output":[]})

    def test_quote_not_exposed_in_context_cannot_count_as_evidence(self):
        from narrative_impact import paragraphs
        old, _ = paragraphs(self.old)
        new, _ = paragraphs(self.new)
        excerpt = "Léo s'enfuit"
        claimed = {"references":[{"version":"new","chapter":"sections/chapter_03.txt",
                   "paragraph":2,"quote":"brimades","role":"later_consequence"}]}
        exposed = [{"version":"new","chapter":"sections/chapter_03.txt",
                    "paragraph":2,"excerpt":excerpt,"line":3}]
        valid, invalid = ai.validate_references(claimed, old, new, exposed)
        self.assertEqual(valid, [])
        self.assertEqual(invalid, 1)

    def test_cli_without_explicit_consent_never_calls_model(self):
        dest=Path(self.tmp.name)/"out.json"
        result=ai.cli([str(self.old),str(self.new),"--model","whatever",
                       "--json-out",str(dest)])
        self.assertEqual(result,2)
        self.assertFalse(dest.exists())

    def test_schema_strictly_require_all_fields(self):
        for schema in (ai.SCHEMA_CLAIMS,ai.SCHEMA_REVIEW):
            self.assertFalse(schema["additionalProperties"])
            self.assertEqual(set(schema["properties"]),set(schema["required"]))


if __name__ == "__main__":
    unittest.main()
