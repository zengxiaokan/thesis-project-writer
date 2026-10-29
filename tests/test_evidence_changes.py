"""Registered evidence change detection, scope and immutable-input checks."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
MODULE = runpy.run_path(str(SCRIPTS / "check_evidence_changes.py"))
check = MODULE["check_evidence_changes"]
InputError = MODULE["InputError"]


def digest(data, mode="bytes"):
    if mode == "text-lf":
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


class EvidenceChangeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="thesis-evidence-check-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.write("source/service.py", b'if state == "ready":\n    save()\n')
        self.write("source/catalog.py", b"CATALOG = ('one', 'two')\n")
        for name in ("chapters/ch5.md", "figures/source/state.dot", "tests/state.md", "chapters/ch2.md"):
            self.write(name, "已有材料\n")
        self.manifest = {
            "schema_version": 1,
            "claims": [
                self.claim("C-STATE", "source/service.py", [
                    {"kind": "chapter", "path": "chapters/ch5.md", "locator": "5.2/P3"},
                    {"kind": "figure", "path": "figures/source/state.dot", "locator": "FIG-501"},
                    {"kind": "test", "path": "tests/state.md", "locator": "CASE-STATE"},
                ]),
                self.claim("C-CATALOG", "source/catalog.py", [{"kind": "chapter", "path": "chapters/ch2.md"}]),
            ],
        }
        self.save_manifest()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode("utf-8") if isinstance(value, str) else value)
        return path

    def claim(self, identity, source, targets, mode="bytes"):
        return {"claim_id": identity, "sources": [{"path": source, "hash_mode": mode,
                "sha256": digest((self.root / source).read_bytes(), mode), "locator": "registered source location"}],
                "targets": targets}

    def save_manifest(self):
        return self.write("evidence/claims.json", json.dumps(self.manifest, ensure_ascii=False, indent=2) + "\n")

    def snapshot(self):
        return ({p.relative_to(self.root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                 for p in self.root.rglob("*") if p.is_file()},
                {p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_dir()})

    def test_unchanged_sources_are_reported_without_semantic_certification_or_writes(self):
        before = self.snapshot()
        report = check(self.root, "evidence/claims.json")
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["unaffected_claim_ids"], ["C-STATE", "C-CATALOG"])
        self.assertEqual(report["needs_review_claim_ids"], [])
        self.assertEqual(report["affected_targets"], [])
        self.assertEqual(report["coverage"]["source_fingerprints_checked"], 2)
        self.assertEqual(self.snapshot(), before)

    def test_one_changed_state_source_locates_only_its_chapter_figure_and_test(self):
        self.write("source/service.py", b'if state == "closed":\n    save()\n')
        before = self.snapshot()
        report = check(self.root, "evidence/claims.json")
        self.assertEqual(report["needs_review_claim_ids"], ["C-STATE"])
        self.assertEqual(report["unaffected_claim_ids"], ["C-CATALOG"])
        self.assertEqual({item["path"] for item in report["affected_targets"]},
                         {"chapters/ch5.md", "figures/source/state.dot", "tests/state.md"})
        self.assertEqual(report["claims"][0]["status"], "needs_review")
        changed = [item for item in report["findings"] if item["code"] == "source_changed"]
        self.assertEqual([item["path"] for item in changed], ["source/service.py"])
        self.assertEqual(changed[0]["details"]["record"], "claims[0].sources[0]")
        self.assertEqual(self.snapshot(), before)

    def test_comment_only_change_also_requires_review_without_guessing_business_difference(self):
        original = (self.root / "source/service.py").read_bytes()
        self.write("source/service.py", b"# comment only\n" + original)
        report = check(self.root, "evidence/claims.json")
        self.assertEqual(report["claims"][0]["sources"][0]["status"], "changed")
        self.assertEqual(report["needs_review_claim_ids"], ["C-STATE"])

    def test_unique_rename_candidate_is_suggested_but_registration_is_not_rewritten(self):
        old = self.root / "source/catalog.py"
        old.rename(self.root / "source/catalog-renamed.py")
        self.manifest["rename_candidates"] = ["source/catalog-renamed.py"]
        self.save_manifest()
        before = self.snapshot()
        report = check(self.root, "evidence/claims.json")
        source = report["claims"][1]["sources"][0]
        self.assertEqual(source["status"], "missing")
        self.assertEqual(source["rename_status"], "unique_candidate")
        self.assertEqual(source["rename_candidates"], ["source/catalog-renamed.py"])
        self.assertEqual(report["needs_review_claim_ids"], ["C-CATALOG"])
        self.assertEqual(self.snapshot(), before)

    def test_multiple_copies_in_explicit_rename_root_remain_ambiguous(self):
        old = self.root / "source/catalog.py"
        raw = old.read_bytes()
        old.unlink()
        self.write("candidates/a.py", raw)
        self.write("candidates/b.py", raw)
        self.manifest["rename_roots"] = ["candidates"]
        self.save_manifest()
        report = check(self.root, "evidence/claims.json")
        source = report["claims"][1]["sources"][0]
        self.assertEqual(source["rename_status"], "ambiguous_candidates")
        self.assertEqual(source["rename_candidates"], ["candidates/a.py", "candidates/b.py"])

    def test_no_undeclared_rename_search_occurs(self):
        old = self.root / "source/catalog.py"
        self.write("unlisted/copy.py", old.read_bytes())
        old.unlink()
        report = check(self.root, "evidence/claims.json")
        self.assertEqual(report["claims"][1]["sources"][0]["rename_candidates"], [])
        self.assertFalse(report["coverage"]["rename_search"]["enabled"])
        self.assertNotIn("unlisted/copy.py", report["coverage"]["files_read"])

    def test_text_lf_ignores_crlf_while_bytes_detects_the_same_change(self):
        raw = b"alpha\r\nbeta\r\n"
        self.write("source/newlines.txt", raw)
        targets = [{"kind": "chapter", "path": "chapters/ch2.md"}]
        self.manifest["claims"] = [self.claim("C-BYTES", "source/newlines.txt", targets),
                                   self.claim("C-LF", "source/newlines.txt", targets, "text-lf")]
        self.save_manifest()
        self.write("source/newlines.txt", raw.replace(b"\r\n", b"\n"))
        report = check(self.root, "evidence/claims.json")
        self.assertEqual(report["needs_review_claim_ids"], ["C-BYTES"])
        self.assertEqual(report["unaffected_claim_ids"], ["C-LF"])

    def test_missing_baseline_and_empty_registration_are_visible(self):
        self.manifest["claims"][0]["sources"][0]["sha256"] = ""
        self.manifest["claims"][1]["sources"] = []
        self.manifest["claims"][1]["targets"] = []
        self.save_manifest()
        before = self.snapshot()
        report = check(self.root, "evidence/claims.json")
        self.assertEqual({item["code"] for item in report["findings"]},
                         {"baseline_missing", "sources_unregistered", "targets_unregistered"})
        self.assertEqual(report["unaffected_claim_ids"], [])
        self.assertEqual(self.snapshot(), before)
        self.manifest["claims"] = []
        self.save_manifest()
        self.assertEqual(check(self.root, "evidence/claims.json")["findings"][0]["code"], "no_claims")

    def test_missing_target_is_not_a_source_change(self):
        self.manifest["claims"][0]["targets"][0]["path"] = "chapters/not-there.md"
        self.save_manifest()
        report = check(self.root, "evidence/claims.json")
        self.assertEqual([item["code"] for item in report["findings"]], ["target_missing"])
        self.assertEqual(report["claims"][0]["sources"][0]["status"], "unchanged")
        self.assertEqual(report["needs_review_claim_ids"], ["C-STATE"])

    def test_invalid_registration_is_rejected_before_source_content_reads(self):
        mutations = [
            lambda m: m["claims"].append(dict(m["claims"][0])),
            lambda m: m["claims"][0]["sources"][0].update(sha256="not-a-fingerprint"),
            lambda m: m["claims"][0]["sources"][0].update(hash_mode="semantic"),
            lambda m: m["claims"][0]["sources"][0].update(path="../outside.py"),
            lambda m: m.update(rename_candidates=["../outside.py"]),
            lambda m: m.update(schema_version=True),
        ]
        original = json.loads(json.dumps(self.manifest))
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.manifest = json.loads(json.dumps(original))
                mutate(self.manifest)
                self.save_manifest()
                before = self.snapshot()
                with self.assertRaises(InputError):
                    check(self.root, "evidence/claims.json")
                self.assertEqual(self.snapshot(), before)

    def test_absolute_manifest_inside_root_is_supported_but_outside_is_rejected(self):
        self.assertEqual(check(self.root, self.root / "evidence/claims.json")["findings"], [])
        with self.assertRaises(InputError):
            check(self.root, self.root.parent / "outside.json")

    @unittest.skipUnless(sys.platform == "win32", "Windows junctions only")
    def test_junction_inside_root_is_not_followed_for_sources_or_rename_search(self):
        import _winapi
        if not hasattr(_winapi, "CreateJunction"):
            self.skipTest("This Python build does not provide CreateJunction")
        link = self.root / "alias"
        _winapi.CreateJunction(str(self.root / "source"), str(link))
        self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        original = json.loads(json.dumps(self.manifest))
        self.manifest["claims"][0]["sources"][0]["path"] = "alias/service.py"
        self.save_manifest()
        with self.assertRaises(InputError):
            check(self.root, "evidence/claims.json")
        self.manifest = original
        self.manifest["rename_roots"] = ["alias"]
        self.save_manifest()
        with self.assertRaises(InputError):
            check(self.root, "evidence/claims.json")

    def test_cli_returns_ascii_json_and_exit_statuses_without_writing(self):
        self.manifest["claims"][0]["statement"] = "这是已登记的中文主张"
        self.save_manifest()
        command = [sys.executable, "-B", str(SCRIPTS / "check_evidence_changes.py"),
                   "--root", str(self.root), "--manifest", "evidence/claims.json"]
        environment = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="ascii")
        for expected, modification in ((0, None), (1, "change"), (2, "invalid")):
            if modification == "change":
                self.write("source/service.py", "状态判断已改变\n")
            elif modification == "invalid":
                self.manifest["claims"][0]["sources"][0]["sha256"] = "invalid"
                self.save_manifest()
            before = self.snapshot()
            result = subprocess.run(command, env=environment, capture_output=True, text=True, encoding="ascii")
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertEqual(json.loads(result.stdout)["tool"], "check_evidence_changes")
            self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
