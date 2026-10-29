"""Replay faults on isolated examples and keep the published observation current."""
import hashlib
import json
from pathlib import Path
import runpy
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = runpy.run_path(str(ROOT / "scripts/run_readonly_example.py"))


class ReadonlyExampleTests(unittest.TestCase):
    def test_injected_findings_and_targeted_impact_are_reproducible_without_writes(self):
        observed = EXAMPLE["observe"]()["observations"]
        self.assertTrue(observed["all_audit_input_bytes_mtimes_and_file_lists_unchanged"])
        self.assertTrue(observed["base_fixture_unchanged"])
        self.assertEqual(observed["changed_source_claims"], ["C-STATE"])
        self.assertEqual(observed["unaffected_claims_after_state_change"], ["C-CATALOG"])
        self.assertTrue(observed["different_historical_context_not_flagged"])

    def test_published_observation_matches_the_tools_and_replay_source(self):
        record = json.loads((ROOT / "examples/readonly-checks/observation.json").read_text(encoding="utf-8"))
        for name, expected in record["sources"].items():
            with self.subTest(name=name):
                actual = hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                self.assertEqual(actual, expected)
