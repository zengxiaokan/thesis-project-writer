#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Behavioral checks for bounded, read-only material discovery."""
import sys
sys.dont_write_bytecode = True

import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = runpy.run_path(str(SCRIPTS / "inventory_sources.py"))
inventory_sources = MODULE["inventory_sources"]
InputError = MODULE["InputError"]
Reader = MODULE["Reader"]


class InventorySourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)

    def write(self, relative, data=b"source\n"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def snapshot(self):
        files = {}
        directories = set()
        for parent, names, filenames in os.walk(str(self.root)):
            parent = Path(parent)
            directories.update((parent / name).relative_to(self.root).as_posix() for name in names)
            for name in filenames:
                path = parent / name
                files[path.relative_to(self.root).as_posix()] = (path.read_bytes(), path.stat().st_mtime_ns)
        return files, directories

    def test_metadata_listing_keeps_same_names_and_business_background(self):
        self.write("modules/enrollment/service.py", b"enroll()\n")
        self.write("modules/payment/service.py", b"pay()\n")
        self.write("jobs/reconcile/service.py", b"reconcile()\n")
        before = self.snapshot()
        with mock.patch.object(Reader, "read_bytes", side_effect=AssertionError("Metadata listing must not read file contents")):
            report = inventory_sources(self.root)
        self.assertEqual([entry["path"] for entry in report["files"]], [
            "jobs/reconcile/service.py", "modules/enrollment/service.py", "modules/payment/service.py",
        ])
        self.assertEqual(report["status"], "listed")
        self.assertTrue(report["coverage"]["metadata_only"])
        self.assertEqual(report["coverage"]["content_hash_reads"], 0)
        self.assertFalse(report["coverage"]["business_modules_assessed"])
        self.assertFalse(report["coverage"]["model_content_reads_measured"])
        for entry in report["files"]:
            self.assertEqual(set(entry), {"path", "bytes", "mtime_ns"})
        self.assertEqual(before, self.snapshot())

    def test_exclusions_are_visible_and_do_not_hide_background_entries(self):
        self.write("src/node_modules/vendor/package.js")
        self.write(".git/config")
        self.write("dist/generated.js")
        self.write("archive/raw/old.py")
        self.write("backend/worker.py")
        self.write("background/run.py")
        self.write("build", b"A regular file with an excluded directory name.\n")
        before = self.snapshot()
        report = inventory_sources(self.root, excludes=["archive/raw"])
        self.assertEqual({entry["path"] for entry in report["files"]}, {"backend/worker.py", "background/run.py", "build"})
        excluded = {entry["path"]: entry["reason"] for entry in report["excluded"]}
        self.assertEqual(excluded, {
            ".git": "default_directory_name", "dist": "default_directory_name",
            "src/node_modules": "default_directory_name", "archive/raw": "explicit_directory",
        })
        self.assertIn("node_modules", report["coverage"]["default_excluded_names"])
        self.assertEqual(report["coverage"]["explicit_excluded_directories"], ["archive/raw"])
        self.assertEqual(before, self.snapshot())

    def test_named_default_can_be_disabled_for_a_business_directory(self):
        self.write("build/domain.py")
        report = inventory_sources(self.root, use_default_excludes=False)
        self.assertEqual(report["files"][0]["path"], "build/domain.py")
        self.assertEqual(report["excluded"], [])
        self.assertEqual(report["coverage"]["default_excluded_names"], [])

    @unittest.skipUnless(os.name == "nt", "Case-insensitive Windows paths")
    def test_case_equivalent_exclusion_is_honored_on_windows(self):
        self.write("archive/raw/old.py")
        self.write(".GIT/config")
        report = inventory_sources(self.root, excludes=["ARCHIVE/RAW"])
        self.assertEqual(report["files"], [])
        self.assertEqual({item["path"] for item in report["excluded"]}, {"archive/raw", ".GIT"})

    def test_hash_modes_preserve_raw_byte_accounting_and_source_state(self):
        data = b"first\r\nsecond\r\n\xff\rthird"
        self.write("materials/raw.bin", data)
        before = self.snapshot()
        exact = inventory_sources(self.root, hash_files=True)
        normalized = inventory_sources(self.root, hash_files=True, hash_mode="text-lf")
        self.assertEqual(exact["files"][0]["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(normalized["files"][0]["sha256"], hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest())
        self.assertNotEqual(exact["files"][0]["sha256"], normalized["files"][0]["sha256"])
        self.assertEqual(normalized["files"][0]["hash_mode"], "text-lf")
        for report in (exact, normalized):
            self.assertFalse(report["coverage"]["metadata_only"])
            self.assertEqual(report["coverage"]["content_hash_attempts"], 1)
            self.assertEqual(report["coverage"]["content_hash_reads"], 1)
            self.assertEqual(report["coverage"]["content_hash_bytes"], len(data))
        self.assertEqual(before, self.snapshot())

    def test_later_inventory_discovers_new_module_without_claiming_understanding(self):
        self.write("modules/accounts/service.py")
        earlier = inventory_sources(self.root)
        self.write("jobs/expired_hold/service.py")
        later = inventory_sources(self.root)
        earlier_paths = {item["path"] for item in earlier["files"]}
        later_paths = {item["path"] for item in later["files"]}
        self.assertEqual(later_paths - earlier_paths, {"jobs/expired_hold/service.py"})
        self.assertFalse(later["coverage"]["business_modules_assessed"])

    def test_invalid_exclusion_or_option_is_rejected_without_source_changes(self):
        self.write("source.py")
        before = self.snapshot()
        for value in (["."], ["../outside"], [str(self.root)], ["C:/external"], ["source.py:stream"], ["source.py"], [""], ["bad\nname"]):
            with self.subTest(value=value), self.assertRaises(InputError):
                inventory_sources(self.root, excludes=value)
        for options in ({"excludes": "archive"}, {"excludes": [None]}, {"hash_mode": "sha1"}, {"hash_files": 1}, {"use_default_excludes": "no"}):
            with self.subTest(options=options), self.assertRaises(InputError):
                inventory_sources(self.root, **options)
        self.assertEqual(before, self.snapshot())

    def test_missing_configured_exclusion_is_visible(self):
        self.write("src/main.py")
        report = inventory_sources(self.root, excludes=["no-longer-present"])
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["findings"][0]["code"], "exclude_directory_missing")
        self.assertEqual(report["findings"][0]["path"], "no-longer-present")
        self.assertEqual(report["coverage"]["explicit_excluded_directories"], ["no-longer-present"])

    def test_hash_failure_retains_metadata_and_reports_incomplete_read(self):
        self.write("src/main.py")
        with mock.patch.object(Reader, "read_bytes", side_effect=PermissionError("synthetic denied read")):
            report = inventory_sources(self.root, hash_files=True)
        self.assertEqual(report["status"], "partial")
        self.assertEqual(report["files"][0]["hash_status"], "unreadable")
        self.assertNotIn("sha256", report["files"][0])
        self.assertEqual(report["findings"][0]["code"], "hash_unreadable")
        self.assertEqual(report["coverage"]["content_hash_attempts"], 1)
        self.assertEqual(report["coverage"]["content_hash_reads"], 0)
        self.assertEqual(report["coverage"]["content_hash_bytes"], 0)

    def test_cli_isolated_bootstrap_and_unicode_json_are_read_only(self):
        self.write("中文目录/同名.py", "示例\r\n".encode("utf-8"))
        before = self.snapshot()
        result = subprocess.run([
            sys.executable, "-I", "-B", str(SCRIPTS / "inventory_sources.py"),
            "--root", str(self.root), "--hash", "--hash-mode", "text-lf",
        ], capture_output=True, encoding="ascii", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(report["files"][0]["path"], "中文目录/同名.py")
        self.assertEqual(report["files"][0]["sha256"], hashlib.sha256("示例\n".encode("utf-8")).hexdigest())
        self.assertEqual(before, self.snapshot())

    def test_cli_bad_scope_returns_json_instead_of_traceback(self):
        result = subprocess.run([
            sys.executable, "-I", "-B", str(SCRIPTS / "inventory_sources.py"),
            "--root", str(self.root), "--exclude", "../outside",
        ], capture_output=True, encoding="ascii", check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout)["status"], "input_error")

    def test_cli_option_errors_and_help_are_json(self):
        for options in ([], ["--root", str(self.root), "--hash-mode", "sha1"], ["--unknown"]):
            with self.subTest(options=options):
                result = subprocess.run([
                    sys.executable, "-I", "-B", str(SCRIPTS / "inventory_sources.py"),
                ] + options, capture_output=True, encoding="ascii", check=False)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stderr, "")
                self.assertEqual(json.loads(result.stdout)["status"], "input_error")
        result = subprocess.run([
            sys.executable, "-I", "-B", str(SCRIPTS / "inventory_sources.py"), "--help",
        ], capture_output=True, encoding="ascii", check=False)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout)["status"], "usage")

    @unittest.skipUnless(os.name == "nt", "Windows junction behavior")
    def test_junction_outside_root_is_not_followed(self):
        import _winapi
        if not hasattr(_winapi, "CreateJunction"):
            self.skipTest("Junction API unavailable")
        with tempfile.TemporaryDirectory() as external_name:
            external = Path(external_name).resolve()
            (external / "secret.py").write_bytes(b"outside\n")
            link = self.root / "linked-background"
            _winapi.CreateJunction(str(external), str(link))
            try:
                self.write("jobs/actual.py")
                report = inventory_sources(self.root, hash_files=True)
                self.assertEqual([entry["path"] for entry in report["files"]], ["jobs/actual.py"])
                self.assertEqual(report["coverage"]["content_hash_reads"], 1)
                self.assertEqual(report["skipped"], [{"path": "linked-background", "reason": "linked_directory_skipped"}])
                self.assertEqual(report["status"], "partial")
                with self.assertRaises(InputError):
                    inventory_sources(link)
            finally:
                link.rmdir()
            self.assertEqual((external / "secret.py").read_bytes(), b"outside\n")


if __name__ == "__main__":
    unittest.main()
