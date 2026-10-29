import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest


SUITE = Path(__file__).resolve().parent
prepare = runpy.run_path(str(SUITE / "prepare.py"))["prepare"]


class InputIsolationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="thesis-eval-copy-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()

    def test_runner_copy_contains_only_raw_inputs_and_selected_rules(self):
        run = self.root / "run"
        metadata = self.root / "private/run.json"
        prepare("repair-dispatch", "current", run, metadata)
        self.assertEqual({p.name for p in run.iterdir()}, {"input", "rules", "RUNNER.md"})
        self.assertTrue((run / "rules/SKILL.md").is_file())
        actual = json.loads(metadata.read_text(encoding="utf-8"))
        for name, expected in actual["files_sha256"].items():
            self.assertEqual(hashlib.sha256((run / name).read_bytes()).hexdigest(), expected)
        self.assertFalse(any("grading" in p.parts for p in run.rglob("*")))

    def test_no_skill_condition_has_no_injected_rule_file(self):
        run = self.root / "run"
        prepare("inventory-transfer", "none", run, self.root / "private.json")
        self.assertEqual(list((run / "rules").iterdir()), [])
        self.assertTrue((run / "input/task.md").is_file())

    def test_repeated_output_is_rejected_without_overwriting(self):
        run = self.root / "run"
        metadata = self.root / "private.json"
        prepare("repair-dispatch", "none", run, metadata)
        before = metadata.read_bytes()
        with self.assertRaises(ValueError):
            prepare("repair-dispatch", "candidate", run, metadata)
        self.assertEqual(metadata.read_bytes(), before)

    def test_identity_metadata_cannot_be_placed_in_runner_copy(self):
        run = self.root / "run"
        with self.assertRaises(ValueError):
            prepare("repair-dispatch", "none", run, run / "identity.json")
        self.assertFalse(run.exists())
