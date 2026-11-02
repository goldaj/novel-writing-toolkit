"""Synthetic tests, with no excerpts from any private book."""
from __future__ import annotations
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import chronology_to_dossier as bridge
from narrative_impact import dossier, evaluate


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.memory = {"schema_version":1,"source_commit":"fictif",
                       "events":[{"id":"E1","description":"Mira apprend à réparer"},
                                 {"id":"E2","description":"Mira franchit le portail"},
                                 {"id":"E3","description":"Mira porte un manteau vert"}]}
        self.links = {"format_version":1,"aliases":["Mira"],"manual_facts":[
            {"id":"F_ALT","label":"Mira connaît une autre méthode",
             "evidence":{"path":"chapter_02.txt","line":3}}],
            "rules":[
                {"id":"R1","because_any":[["E1"],["F_ALT"]],"evidence_terms":["apprend","méthode"]},
                {"id":"R2","because_any":[["rule:R1","E2"]],"evidence_terms":["portail"]}]}

    def test_baseline_and_changes_use_actual_toolkit_format(self):
        first = bridge.convert(self.memory, self.links)
        self.assertTrue(first["provenance"]["baseline"])
        self.assertEqual(len(first["facts"]),4)
        self.assertTrue(all(f["before"] == f["after"] for f in first["facts"]))
        self.assertTrue(all(v["supported"] for v in evaluate(dossier(first),"after").values()))
        changed = bridge.convert(self.memory,self.links,overrides={"E1":"absent"})
        b,a = evaluate(dossier(changed),"before"),evaluate(dossier(changed),"after")
        self.assertNotEqual(b["R1"]["support_paths"],a["R1"]["support_paths"])
        self.assertTrue(a["R2"]["supported"])
        removed = bridge.convert(self.memory,self.links,overrides={"E1":"absent","F_ALT":"absent"})
        self.assertFalse(evaluate(dossier(removed),"after")["R2"]["supported"])
        self.assertFalse(any(x["id"]=="E3" for r in removed["rules"] for g in r["because_any"]
                             for x in g if "id" in x))

    def test_two_versions_and_invalid_refs(self):
        revised = {"schema_version":1,"events":[self.memory["events"][1]]}
        out=bridge.convert(self.memory,self.links,revised)
        self.assertEqual(next(x for x in out["facts"] if x["id"]=="E1")["after"],"absent")
        bad=json.loads(json.dumps(self.links))
        bad["rules"][0]["because_any"]=[["MISSING"]]
        with self.assertRaisesRegex(ValueError,"Unknown upstream fact"):
            bridge.convert(self.memory,bad)
        bad["rules"][0]["because_any"]=[["rule:R2"]]
        with self.assertRaisesRegex(ValueError,"cycle"):
            bridge.convert(self.memory,bad)
        with self.assertRaisesRegex(ValueError,"Overrides"):
            bridge.convert(self.memory,self.links,overrides={"not_known":"absent"})

    def test_cli_does_not_overwrite_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            m,l,o=root/"memory.json",root/"links.json",root/"out.json"
            m.write_text(json.dumps(self.memory),encoding="utf-8")
            l.write_text(json.dumps(self.links),encoding="utf-8")
            command=[str(m),str(l),"--out",str(o)]
            self.assertEqual(bridge.cli(command),0)
            self.assertEqual(bridge.cli(command),2)
            self.assertEqual(bridge.cli(command+["--force"]),0)
            self.assertEqual(bridge.cli([str(m),str(l),"--out",str(m),"--force"]),2)
            self.assertEqual(json.loads(m.read_text()),self.memory)


if __name__ == "__main__":
    unittest.main()
