"""Observable distribution invariants, independent of the current archive bytes."""
import ast
import io
from pathlib import Path
import runpy
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD = runpy.run_path(str(ROOT / "scripts/build_release.py"))


class ReleaseTests(unittest.TestCase):
    def test_archive_contains_documentation_license_and_version(self):
        payload = BUILD["make_archive"]()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())
            for required in ("README.md", "LICENSE", "VERSION", "SKILL.md", "CHANGELOG.md",
                             ".gitignore", "references/host-adapters.md", "references/figures-and-tables.md",
                             "examples/figures/initializer-flow.dot", "examples/figures/initializer-flow.svg",
                             "examples/figures/render_chart.py", "examples/figures/source_data.csv",
                             "examples/figures/counts.svg", "scripts/check_consistency.py",
                             "scripts/check_evidence_changes.py", "scripts/audit_common.py",
                             "references/consistency-checks.md", "references/evidence-changes.md",
                             "examples/readonly-checks/base/evidence/claims.json",
                             "examples/readonly-checks/observation.json", "scripts/inventory_sources.py",
                             "references/literature-workflow.md", "references/large-materials-and-resume.md",
                             "examples/literature-synthesis/reading-matrix.json"):
                self.assertIn("thesis-project-writer/" + required, names)
            self.assertFalse(any("workspace/" in name or ".github/" in name or "__pycache__" in name
                                 or ("/evals/" in name and not name.endswith("/evals/evals.json")) for name in names))
            self.assertTrue(all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist()))
            self.assertIsNone(archive.testzip())

    def test_archive_is_identical_across_lf_and_crlf_checkout(self):
        expected = BUILD["make_archive"]()
        with tempfile.TemporaryDirectory(prefix="thesis-release-test-") as temporary:
            base = Path(temporary).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            for relative in BUILD["release_files"](ROOT):
                target = base / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                data = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
                target.write_bytes(data.replace(b"\n", b"\r\n"))
            self.assertEqual(BUILD["make_archive"](base), expected)
            self.assertEqual(BUILD["make_archive"](base), BUILD["make_archive"](base))

    def test_public_markdown_links_resolve(self):
        BUILD["verify_links"]()

    def test_link_verifier_handles_real_markdown_and_does_not_read_code_examples(self):
        with tempfile.TemporaryDirectory(prefix="thesis-link-check-") as temporary:
            root = Path(temporary).resolve()
            for relative in BUILD["release_files"](ROOT):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(BUILD["canonical_bytes"](ROOT / relative))
            target = root / "examples/target (1).md"
            target.write_text("A real target\n", encoding="utf-8")
            entry = root / "README.md"
            entry.write_text('[real](<examples/target (1).md>)\n```text\n[fake](absent.md)\n```\n', encoding="utf-8")
            BUILD["verify_links"](root)
            entry.write_text('[broken](absent.md)\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                BUILD["verify_links"](root)

    def test_scripts_support_declared_python_syntax(self):
        for path in (ROOT / "scripts").glob("*.py"):
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 8))

    def test_committed_observation_matches_current_source(self):
        import hashlib
        import json
        observed = json.loads((ROOT / "examples/initialization-study/observation.json").read_text(encoding="utf-8"))
        source = ROOT / observed["source"]["path"]
        actual = hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        self.assertEqual(observed["source"]["sha256"], actual)
