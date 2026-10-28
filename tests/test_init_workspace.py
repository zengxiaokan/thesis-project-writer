"""Regression checks for workspace creation; all writes use temporary directories."""
import ast
import builtins
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "init_workspace.py"
MODULE = runpy.run_path(str(SCRIPT))
initialize = MODULE["initialize"]


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="thesis-skill-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        self.root.mkdir()

    def snapshot(self, root=None):
        root = root or self.root
        return {
            path.relative_to(root).as_posix(): (
                path.read_bytes(), path.stat().st_mtime_ns
            )
            for path in root.rglob("*") if path.is_file()
        }

    def test_dry_run_never_writes_and_reports_only_missing_paths(self):
        result = initialize(self.root, dry_run=True, profile="software")
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(result["created_files"], [])
        self.assertEqual(result["created_directories"], [])
        self.assertIn("thesis/README.md", result["planned_files"])
        self.assertIn("thesis/evidence", result["planned_directories"])
        initialize(self.root, profile="software")
        before = self.snapshot()
        result = initialize(self.root, dry_run=True, profile="software")
        self.assertEqual(result["planned_files"], [])
        self.assertEqual(result["planned_directories"], [])
        self.assertEqual(self.snapshot(), before)

    def test_repeated_run_preserves_contents_and_mtimes(self):
        first = initialize(self.root, profile="software")
        self.assertTrue(first["created_files"])
        self.assertEqual(first["planned_files"], [])
        self.assertEqual(first["planned_directories"], [])
        custom = self.root / "thesis" / "README.md"
        custom.write_text("已有题目和正式交付路径\n", encoding="utf-8")
        before = self.snapshot()
        repeated = initialize(self.root, profile="software")
        self.assertEqual(repeated["created_or_planned"], [])
        self.assertEqual(repeated["created_directories"], [])
        self.assertEqual(self.snapshot(), before)

    def test_intake_upgrade_preserves_answers_and_returns_continuation(self):
        initialize(self.root)
        before = self.snapshot()
        result = initialize(self.root, profile="software")
        for relative, original in before.items():
            self.assertEqual(self.snapshot()[relative], original)
        actions = {item["path"]: item["action"] for item in result["continuation_required"]}
        for name in ("README.md", "progress.md", "intake/interview.md",
                     "intake/positioning.md", "intake/environment.md"):
            self.assertIn("thesis/" + name, actions)
        self.assertIn("不重复访谈", actions["thesis/intake/interview.md"])
        self.assertIn("不能自动确认", actions["thesis/intake/positioning.md"])
        self.assertIn("thesis/tests/README.md", result["created_files"])

    def test_profiles_add_only_their_own_specialized_directories(self):
        expected = {
            "intake": ("intake",),
            "software": ("evidence/modules", "tests", "resources/screenshots"),
            "empirical": ("materials/data", "materials/instruments", "analysis"),
            "experimental": ("materials/protocols", "materials/records", "analysis"),
            "literature": ("materials/literature", "analysis"),
            "theoretical": ("materials/sources", "analysis"),
            "mixed": ("materials", "analysis"),
        }
        for profile, directories in expected.items():
            with self.subTest(profile=profile):
                parent = self.root / profile
                parent.mkdir()
                result = initialize(parent, profile=profile)
                workspace = Path(result["workspace"])
                for directory in directories:
                    self.assertTrue((workspace / directory).is_dir())
                if profile not in ("intake", "software"):
                    self.assertFalse((workspace / "tests").exists())
                    self.assertFalse((workspace / "resources/screenshots").exists())
                    self.assertTrue((workspace / "research-facts.md").is_file())
                if profile == "intake":
                    self.assertEqual(len(result["created_files"]), 5)
                    self.assertFalse((workspace / "chapters").exists())

    def test_profile_change_preserves_old_sources_and_reports_stale_entry(self):
        initialize(self.root, profile="empirical")
        original = self.snapshot()
        result = initialize(self.root, profile="literature")
        current = self.snapshot()
        for name, contents in original.items():
            self.assertEqual(current[name], contents)
        self.assertTrue((self.root / "thesis/materials/literature").is_dir())
        self.assertTrue((self.root / "thesis/materials/data").is_dir())
        actions = {item["path"] for item in result["continuation_required"]}
        self.assertIn("thesis/materials/README.md", actions)
        self.assertIn("thesis/progress.md", actions)

    def test_parent_entry_reuses_existing_chinese_workspace(self):
        workspace = self.root / "论文"
        workspace.mkdir()
        result = initialize(self.root)
        self.assertEqual(Path(result["workspace"]), workspace)
        self.assertFalse((self.root / "thesis").exists())

    def test_direct_workspace_avoids_nesting_and_preserves_parent_rules(self):
        workspace = self.root / "thesis"
        workspace.mkdir()
        rules = self.root / "AGENTS.md"
        rules.write_text("既有仓库规则", encoding="utf-8")
        result = initialize(workspace=workspace, profile="software")
        self.assertEqual(Path(result["workspace"]), workspace)
        self.assertFalse((workspace / "thesis").exists())
        self.assertEqual(rules.read_text(encoding="utf-8"), "既有仓库规则")
        self.assertTrue((workspace / "AGENTS.md").is_file())

    def test_ambiguous_workspace_requires_explicit_selection(self):
        (self.root / "thesis").mkdir()
        (self.root / "论文").mkdir()
        with self.assertRaisesRegex(ValueError, "Both"):
            initialize(self.root)
        self.assertEqual(self.snapshot(), {})
        result = initialize(self.root, directory="论文")
        self.assertEqual(Path(result["workspace"]), self.root / "论文")

    def test_invalid_and_escaping_directory_names_fail_without_writes(self):
        invalid = ("", " ", ".", "..", "../escape", "..\\escape", "a/b", "a\\b",
                   "D:work", "a*", 'a"', "end.", "end ", "CON", "con.txt",
                   "LPT1", "COM¹", "AUX .md", "CONIN$", "bad\x00name", "bad\nname")
        for name in invalid:
            with self.subTest(name=repr(name)):
                with self.assertRaises(ValueError):
                    initialize(self.root, directory=name)
                self.assertEqual(list(self.root.iterdir()), [])

    def test_ancestor_file_conflict_fails_before_creating_other_directories(self):
        for ancestor in ("evidence", "resources"):
            with self.subTest(ancestor=ancestor):
                parent = self.root / (ancestor + "-conflict")
                workspace = parent / "thesis"
                workspace.mkdir(parents=True)
                (workspace / ancestor).write_text("必须保留", encoding="utf-8")
                before = self.snapshot(parent)
                with self.assertRaises((ValueError, OSError)):
                    initialize(parent, profile="software")
                self.assertEqual(self.snapshot(parent), before)
                self.assertEqual({path.name for path in workspace.iterdir()}, {ancestor})

    def test_file_destination_directory_conflict_fails_before_writes(self):
        workspace = self.root / "thesis"
        (workspace / "README.md").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "incompatible type"):
            initialize(self.root, profile="software")
        self.assertEqual({path.name for path in workspace.iterdir()}, {"README.md"})

    def test_symlink_escape_fails_before_writes(self):
        outside = self.base / "outside"
        outside.mkdir()
        link = self.root / "thesis"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest("Directory symlink creation is unavailable: " + str(exc))
        with self.assertRaisesRegex(ValueError, "escapes"):
            initialize(self.root, profile="software")
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(list(self.root.iterdir()), [link])

    def create_junction(self, target, link):
        import _winapi
        if not hasattr(_winapi, "CreateJunction"):
            self.skipTest("This Python build does not provide CreateJunction")
        _winapi.CreateJunction(str(target), str(link))
        # Remove the junction itself before TemporaryDirectory performs cleanup.
        self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        self.assertFalse(link.is_symlink())
        self.assertTrue(MODULE["is_link_or_reparse"](link))

    @unittest.skipUnless(sys.platform == "win32", "Windows junctions only")
    def test_junction_to_sibling_in_project_fails_before_writes(self):
        workspace = self.root / "thesis"
        workspace.mkdir()
        target = self.root / "unrelated-assets"
        target.mkdir()
        self.create_junction(target, workspace / "resources")
        with self.assertRaisesRegex(ValueError, "reparse|escapes"):
            initialize(self.root, profile="software")
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual({path.name for path in workspace.iterdir()}, {"resources"})

    @unittest.skipUnless(sys.platform == "win32", "Windows junctions only")
    def test_junction_outside_project_fails_before_writes(self):
        workspace = self.root / "thesis"
        workspace.mkdir()
        target = self.base / "outside-project"
        target.mkdir()
        self.create_junction(target, workspace / "resources")
        with self.assertRaisesRegex(ValueError, "reparse|escapes"):
            initialize(self.root, profile="software")
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual({path.name for path in workspace.iterdir()}, {"resources"})

    @unittest.skipUnless(sys.platform == "win32", "Windows junctions only")
    def test_junction_within_workspace_is_also_rejected(self):
        workspace = self.root / "thesis"
        target = workspace / "shared-assets"
        target.mkdir(parents=True)
        self.create_junction(target, workspace / "resources")
        with self.assertRaisesRegex(ValueError, "reparse"):
            initialize(self.root, profile="software")
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual({path.name for path in workspace.iterdir()},
                         {"resources", "shared-assets"})

    @unittest.skipUnless(sys.platform == "win32", "Windows junctions only")
    def test_direct_workspace_rejects_junction_before_resolution(self):
        target = self.root / "actual-thesis"
        target.mkdir()
        link = self.root / "linked-thesis"
        self.create_junction(target, link)
        with self.assertRaisesRegex(ValueError, "reparse"):
            initialize(workspace=link, profile="software")
        self.assertEqual(list(target.iterdir()), [])

    def test_explicit_workspace_requires_existing_directory(self):
        with self.assertRaises((ValueError, OSError)):
            initialize(workspace=self.root / "missing")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_direct_workspace_and_parent_arguments_are_mutually_exclusive(self):
        for arguments in ({"root": self.root}, {"directory": "thesis"}):
            with self.subTest(arguments=arguments):
                with self.assertRaisesRegex(ValueError, "cannot be combined"):
                    initialize(workspace=self.root, **arguments)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_direct_workspace_and_invalid_argument_combinations(self):
        workspace = self.root / "论文"
        workspace.mkdir()
        command = [sys.executable, "-B", str(SCRIPT)]
        result = subprocess.run(command + ["--workspace", str(workspace), "--dry-run"],
                                capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(Path(json.loads(result.stdout)["workspace"]), workspace)
        for conflicting in (["--root", str(self.root)], ["--directory", "论文"]):
            result = subprocess.run(command + ["--workspace", str(workspace)] + conflicting,
                                    capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2)
        self.assertEqual(list(workspace.iterdir()), [])

    def test_script_syntax_is_compatible_with_declared_python_38(self):
        ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 8))

    def test_cli_chinese_paths_work_with_ascii_terminal(self):
        workspace = self.root / "论文"
        workspace.mkdir()
        environment = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="ascii")
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--workspace", str(workspace), "--dry-run"],
            env=environment, capture_output=True, text=True, encoding="ascii", check=True,
        )
        self.assertEqual(Path(json.loads(completed.stdout)["workspace"]), workspace)
        self.assertEqual(list(workspace.iterdir()), [])

    @unittest.skipUnless(sys.platform == "win32", "Windows junctions only")
    def test_ancestor_replaced_during_writes_is_rechecked(self):
        workspace = self.root / "thesis"
        target = self.base / "outside-during-write"
        target.mkdir()
        changed = []

        def replace_ancestor_after_first_open(path, *args, **kwargs):
            handle = builtins.open(path, *args, **kwargs)
            if not changed:
                link = workspace / "intake"
                self.assertEqual(list(link.iterdir()), [])
                link.rmdir()
                self.create_junction(target, link)
                changed.append(True)
            return handle

        with mock.patch.dict(initialize.__globals__, {"open": replace_ancestor_after_first_open}):
            with self.assertRaisesRegex(ValueError, "reparse|escapes"):
                initialize(self.root)
        self.assertTrue(changed)
        self.assertEqual(list(target.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
