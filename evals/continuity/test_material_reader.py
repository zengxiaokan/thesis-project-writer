import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("material_reader.py")


class MaterialReaderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="thesis-content-log-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        (self.project / "a.py").write_bytes(b"VALUE = 1\n")
        self.log = self.base / "reads.jsonl"
        self.read = runpy.run_path(str(SCRIPT))["read_material"]

    def test_hash_inventory_and_content_reads_are_separate_events(self):
        before = (self.project / "a.py").stat().st_mtime_ns
        self.read(self.project, self.log, inventory=True)
        result = self.read(self.project, self.log, paths=["a.py"])
        events = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["action"] for item in events], ["inventory", "content_read"])
        self.assertEqual(result["files"][0]["text"], "VALUE = 1\n")
        self.assertEqual((self.project / "a.py").stat().st_mtime_ns, before)
        self.assertEqual({p.name for p in self.project.iterdir()}, {"a.py"})

    def test_log_cannot_be_written_inside_audited_materials(self):
        from audit_common import InputError
        with self.assertRaises(InputError):
            self.read(self.project, self.project / "log.jsonl", paths=["a.py"])
        self.assertFalse((self.project / "log.jsonl").exists())

    def test_external_hard_link_log_cannot_mutate_project_source(self):
        from audit_common import InputError
        source = self.project / "a.py"
        before = (source.read_bytes(), source.stat().st_mtime_ns)
        try:
            os.link(str(source), str(self.log))
        except OSError as error:
            self.skipTest("Hard links unavailable: " + str(error))
        with self.assertRaises(InputError):
            self.read(self.project, self.log, paths=["a.py"])
        self.assertEqual((source.read_bytes(), source.stat().st_mtime_ns), before)
        self.assertEqual({p.name for p in self.project.iterdir()}, {"a.py"})
