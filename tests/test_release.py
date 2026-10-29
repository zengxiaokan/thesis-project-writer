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
                             "examples/figures/counts.svg"):
                self.assertIn("thesis-project-writer/" + required, names)
            self.assertFalse(any("workspace/" in name or ".github/" in name or "__pycache__" in name for name in names))
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
