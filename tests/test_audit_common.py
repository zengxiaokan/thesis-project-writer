"""Scope checks shared by the read-only audit tools."""
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest import mock


MODULE = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/audit_common.py"))
Reader, InputError = MODULE["Reader"], MODULE["InputError"]


class ReaderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="thesis-reader-")
        self.addCleanup(temp.cleanup)
        self.parent = Path(temp.name).resolve()
        self.root = self.parent / "project"
        self.root.mkdir()
        self.reader = Reader(self.root)

    def test_parent_escape_absolute_path_and_windows_drive_are_rejected(self):
        for name in ("../outside.txt", "..\\outside.txt", str(self.parent / "outside.txt"), "C:relative.txt", "a.md:hidden"):
            with self.subTest(name=name):
                with self.assertRaises(InputError):
                    self.reader.path(name)

    def test_hash_modes_are_explicit_and_read_does_not_change_content_or_mtime(self):
        path = self.root / "材料.txt"
        path.write_bytes(b"a\r\nb\r\n")
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertNotEqual(self.reader.fingerprint("材料.txt", "bytes"),
                            self.reader.fingerprint("材料.txt", "text-lf"))
        self.assertEqual(self.reader.read_text("材料.txt"), "a\r\nb\r\n")
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        (self.root / "data.json").write_text('{"claims":[],"claims":[1]}', encoding="utf-8")
        with self.assertRaises(InputError):
            self.reader.load_json("data.json")

    def test_unknown_hash_mode_is_rejected(self):
        (self.root / "a.txt").write_text("source", encoding="utf-8")
        with self.assertRaises(InputError):
            self.reader.fingerprint("a.txt", "unknown")

    def test_old_python_link_loop_error_is_a_controlled_input_error(self):
        with mock.patch.object(Path, "resolve", side_effect=RuntimeError("Symlink loop")):
            with self.assertRaises(InputError):
                self.reader.path("a.txt")

    @unittest.skipUnless(sys.platform == "win32", "Windows reparse points only")
    def test_junction_cannot_read_a_source_outside_the_selected_root(self):
        import _winapi
        if not hasattr(_winapi, "CreateJunction"):
            self.skipTest("CreateJunction is unavailable")
        external = self.parent / "external"
        external.mkdir()
        (external / "source.txt").write_text("outside", encoding="utf-8")
        link = self.root / "linked"
        _winapi.CreateJunction(str(external), str(link))
        self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        with self.assertRaises(InputError):
            self.reader.read_bytes("linked/source.txt")
        self.assertEqual(self.reader.accessed, set())
