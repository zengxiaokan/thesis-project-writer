"""Observable read-only manuscript audit behavior, using temporary materials."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
MODULE = runpy.run_path(str(SCRIPTS / "check_consistency.py"))
check = MODULE["check"]
InputError = MODULE["InputError"]


class ConsistencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="thesis-consistency-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "chapters").mkdir()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def snapshot(self):
        return {path.relative_to(self.root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
                for path in self.root.rglob("*") if path.is_file()}

    def manifest(self, config):
        self.write("review/consistency.json", json.dumps({"schema_version": 1, **config}, ensure_ascii=False))

    def codes(self, report):
        return {item["code"] for item in report["findings"]}

    def table(self, path, identity, first="10", second="2", total="12"):
        self.write(path, "# Results\n<!-- thesis:id %s -->\n| 状态 | 数量 |\n| --- | ---: |\n| 通过 | %s |\n| 失败 | %s |\n| 合计 | %s |\n" % (identity, first, second, total))

    def table_rule(self, path="chapters/current.md", identity="TAB-1", **updates):
        rule = {"id": identity, "document": path, "anchor": identity,
                "label_column": 0, "value_column": 1, "sum_of": ["通过", "失败"], "total": "合计",
                "value_type": "integer", "unit": "cases", "context": {"version": "v2", "batch": "r1", "object": "functional", "method": "count"},
                "comparison_id": "functional-total", "metrics": [{"metric_id": "total", "row": "合计"}]}
        rule.update(updates)
        return rule

    def test_registered_errors_are_located_and_inputs_are_unchanged(self):
        self.write("chapters/a.md", "# 5.1 实现\n<!-- thesis:id FIG-1 -->\n<!-- thesis:ref FIG-MISSING -->\n![界面](../figures/missing.png)\n【待确认：来源】\n<!-- thesis:id FIG-1 -->\n")
        self.table("chapters/current.md", "TAB-1", total="13")
        self.manifest({"documents": ["chapters/a.md", "chapters/current.md"], "expected_ids": ["FIG-2"],
                       "required_sections": [{"document": "chapters/a.md", "heading": "5.2 测试"}],
                       "table_checks": [self.table_rule()]})
        before = self.snapshot()
        report = check(self.root, "review/consistency.json")
        self.assertTrue({"duplicate_id", "missing_id", "dangling_reference", "image_missing", "unresolved_marker", "section_missing", "table_total_mismatch"}.issubset(self.codes(report)))
        total = next(item for item in report["findings"] if item["code"] == "table_total_mismatch")
        self.assertEqual((total["path"], total["line"]), ("chapters/current.md", 7))
        self.assertEqual(total["details"]["expected"], "12")
        self.assertEqual(self.snapshot(), before)

    def test_code_examples_are_ignored_and_registered_marker_is_not_duplicate(self):
        self.write("chapters/a.md", "# A\n<!-- thesis:id FIG-1 -->\n<!-- thesis:ref FIG-1 -->\n`<!-- thesis:id FIG-1 --> TODO`\n```md\n<!-- thesis:id FIG-1 -->\n<!-- thesis:ref UNKNOWN -->\n【待确认：example】\n![missing](none.png)\n```\n")
        self.manifest({"documents": ["chapters/a.md"], "entities": [{"id": "FIG-1", "document": "chapters/a.md", "line": 2}],
                       "references": [{"id": "FIG-1", "document": "chapters/a.md", "line": 3}]})
        self.assertEqual(check(self.root, "review/consistency.json")["findings"], [])

    def test_local_images_handle_spaces_chinese_encoding_and_remote_scope(self):
        self.write("figures/中文 图.svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.write("chapters/a.md", "![one](<../figures/中文 图.svg#view>)\n![two](../figures/%E4%B8%AD%E6%96%87%20%E5%9B%BE.svg)\n![remote](https://example.invalid/not-downloaded.png)\n")
        before = self.snapshot()
        report = check(self.root)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["coverage"]["images_examined"], 3)
        self.assertTrue(any(item["reason"] == "remote_or_embedded_image_not_verified" for item in report["coverage"]["skipped"]))
        self.assertEqual(self.snapshot(), before)

    def test_balanced_and_escaped_image_parentheses_are_not_truncated(self):
        self.write("figures/chart(1).svg", '<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.write("figures/chart(outer(inner)).svg", "<svg/>")
        self.write("chapters/a.md", '\n'.join([
            '![plain](../figures/chart(1).svg)',
            r'![escaped](../figures/chart\(1\).svg)',
            '![titled](../figures/chart(1).svg "计数图")',
            "![single title](../figures/chart(1).svg '计数图')",
            '![parenthesized title](../figures/chart(1).svg (计数图))',
            '![nested](../figures/chart(outer(inner)).svg)',
            '![angle](<../figures/chart(1).svg> "计数图")',
            '![encoded](../figures/chart%281%29.svg)',
        ]) + '\n')
        before = self.snapshot()
        report = check(self.root)
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["coverage"]["images_examined"], 8)
        self.assertEqual(self.snapshot(), before)

    def test_unbalanced_image_destination_is_uncheckable_not_a_missing_truncated_file(self):
        self.write("figures/chart(1.svg", "<svg/>")
        self.write("chapters/a.md", "![broken](../figures/chart(1.svg)\n")
        report = check(self.root)
        self.assertIn("image_path_uncheckable", self.codes(report))
        self.assertNotIn("image_missing", self.codes(report))

    def test_different_versions_batches_units_objects_and_methods_do_not_conflict(self):
        rules, documents = [], []
        variations = [("version", "v1"), ("batch", "old"), ("object", "destination"), ("method", "manual")]
        for index, variation in enumerate([(None, None), *variations, ("unit", "requests")]):
            name, identity = "chapters/t%s.md" % index, "TAB-%s" % index
            self.table(name, identity, first=str(10 + index), total=str(12 + index))
            rule = self.table_rule(name, identity)
            if variation[0] == "unit":
                rule["unit"] = variation[1]
            elif variation[0]:
                rule["context"][variation[0]] = variation[1]
            rules.append(rule)
            documents.append(name)
        self.manifest({"documents": documents, "table_checks": rules})
        report = check(self.root, "review/consistency.json")
        self.assertEqual(report["findings"], [])
        self.assertEqual(len(report["coverage"]["tables_checked"]), 6)

    def test_only_same_explicit_comparison_identity_can_conflict(self):
        self.table("chapters/a.md", "TAB-A", first="10", total="12")
        self.table("chapters/b.md", "TAB-B", first="11", total="13")
        self.manifest({"documents": ["chapters/a.md", "chapters/b.md"], "table_checks": [self.table_rule("chapters/a.md", "TAB-A"), self.table_rule("chapters/b.md", "TAB-B")]})
        report = check(self.root, "review/consistency.json")
        self.assertEqual(self.codes(report), {"number_conflict"})
        self.assertEqual(len(report["findings"][0]["details"]["observations"]), 2)
        config = json.loads((self.root / "review/consistency.json").read_text(encoding="utf-8"))
        config["table_checks"][1]["comparison_id"] = "another-metric-family"
        self.manifest(config)
        self.assertEqual(check(self.root, "review/consistency.json")["findings"], [])

    def test_context_scalar_types_do_not_silently_collapse(self):
        self.table("chapters/a.md", "TAB-A", first="10", total="12")
        self.table("chapters/b.md", "TAB-B", first="11", total="13")
        rules = [self.table_rule("chapters/a.md", "TAB-A"), self.table_rule("chapters/b.md", "TAB-B")]
        rules[0]["context"]["version"] = 2
        rules[1]["context"]["version"] = "2"
        self.manifest({"documents": ["chapters/a.md", "chapters/b.md"], "table_checks": rules})
        self.assertEqual(check(self.root, "review/consistency.json")["findings"], [])

    def test_missing_mixed_units_and_duplicate_rows_are_not_treated_as_zero(self):
        for bad in ("", "—", "1项", "1.5"):
            with self.subTest(bad=bad):
                self.table("chapters/current.md", "TAB-1", second=bad, total="10")
                self.manifest({"documents": ["chapters/current.md"], "table_checks": [self.table_rule()]})
                report = check(self.root, "review/consistency.json")
                self.assertIn("table_value_uncheckable", self.codes(report))
                self.assertNotIn("table_total_mismatch", self.codes(report))
        self.table("chapters/current.md", "TAB-1")
        text = (self.root / "chapters/current.md").read_text(encoding="utf-8")
        self.write("chapters/current.md", text + "| 失败 | 0 |\n")
        self.assertIn("table_row_missing_or_duplicate", self.codes(check(self.root, "review/consistency.json")))

    def test_decimal_sum_and_declared_rounding_tolerance_are_explicit(self):
        self.table("chapters/current.md", "TAB-1", first="0.10", second="0.20", total="0.3001")
        rule = self.table_rule(value_type="decimal", tolerance="0.001")
        self.manifest({"documents": ["chapters/current.md"], "table_checks": [rule]})
        self.assertEqual(check(self.root, "review/consistency.json")["findings"], [])
        rule["tolerance"] = "0"
        self.manifest({"documents": ["chapters/current.md"], "table_checks": [rule]})
        self.assertIn("table_total_mismatch", self.codes(check(self.root, "review/consistency.json")))

    def test_large_integer_totals_are_not_rounded_by_decimal_context(self):
        self.table("chapters/current.md", "TAB-1", first="123456789012345678901234567890", second="1",
                   total="123456789012345678901234567891")
        self.manifest({"documents": ["chapters/current.md"], "table_checks": [self.table_rule()]})
        self.assertEqual(check(self.root, "review/consistency.json")["findings"], [])

    def test_invalid_image_url_is_a_finding_not_a_traceback(self):
        self.write("chapters/a.md", "![invalid](https://[bad)\n")
        self.assertIn("image_path_uncheckable", self.codes(check(self.root)))
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "check_consistency.py"), "--root", str(self.root)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("image_path_uncheckable", self.codes(json.loads(result.stdout)))

    def test_linked_image_cannot_escape_the_selected_read_root(self):
        outside = tempfile.TemporaryDirectory(prefix="thesis-audit-outside-")
        self.addCleanup(outside.cleanup)
        target = Path(outside.name).resolve()
        (target / "image.svg").write_text("<svg/>", encoding="utf-8")
        link = self.root / "figures-link"
        if sys.platform == "win32":
            import _winapi
            if not hasattr(_winapi, "CreateJunction"):
                self.skipTest("Windows Junction creation is unavailable")
            _winapi.CreateJunction(str(target), str(link))
            self.addCleanup(lambda: link.rmdir() if link.exists() else None)
        else:
            link.symlink_to(target, target_is_directory=True)
        self.write("chapters/a.md", "![outside](../figures-link/image.svg)\n")
        self.assertIn("image_path_unsafe", self.codes(check(self.root)))

    def test_authority_fingerprint_never_selects_or_overwrites_a_draft(self):
        word = self.root / "latest.docx"
        word.write_bytes(b"synthetic document bytes")
        self.write("chapters/old.md", "# Old draft\n")
        authority = {"path": "latest.docx", "version": "author-selected-v2", "hash_mode": "bytes", "sha256": hashlib.sha256(word.read_bytes()).hexdigest()}
        self.manifest({"documents": ["chapters/old.md"], "authority": authority})
        self.assertEqual(check(self.root, "review/consistency.json")["authority"]["status"], "fingerprint_matches")
        word.write_bytes(b"new author content")
        before = self.snapshot()
        report = check(self.root, "review/consistency.json")
        self.assertIn("authority_changed", self.codes(report))
        self.assertEqual(report["authority"]["declared_version"], "author-selected-v2")
        self.assertEqual(self.snapshot(), before)
        del authority["sha256"]
        self.manifest({"documents": ["chapters/old.md"], "authority": authority})
        self.assertIn("authority_baseline_missing", self.codes(check(self.root, "review/consistency.json")))

    def test_legacy_selection_reports_unconfigured_checks_and_empty_scope(self):
        self.write("chapters/a.md", "# Existing paragraph\n")
        report = check(self.root, documents=["chapters/a.md"])
        self.assertEqual(report["findings"], [])
        self.assertIn("typed_table_totals", report["coverage"]["not_configured"])
        self.assertIn("no_documents_checked", self.codes(check(self.root, documents=[])))

    def test_escaping_paths_and_malformed_configuration_are_rejected(self):
        self.write("chapters/a.md", "![escape](../../outside.png)\n")
        self.assertIn("image_path_unsafe", self.codes(check(self.root)))
        with self.assertRaises(InputError):
            check(self.root, documents=["../outside.md"])
        self.write("bad.json", '{"schema_version":1,"documents":[],"documents":[]}')
        with self.assertRaises(InputError):
            check(self.root, "bad.json")
        self.manifest({"documents": ["chapters/a.md"], "typo_table_checks": []})
        with self.assertRaises(InputError):
            check(self.root, "review/consistency.json")

    def test_schema_version_is_an_actual_integer_not_bool_or_float(self):
        self.write("chapters/a.md", "# A\n")
        for value in (True, 1.0, "1", None):
            with self.subTest(value=value):
                self.write("schema.json", json.dumps({"schema_version": value, "documents": ["chapters/a.md"]}))
                with self.assertRaises(InputError):
                    check(self.root, "schema.json")

    def test_cli_exit_codes_and_source_tree_are_read_only(self):
        self.write("chapters/a.md", "# A\n")
        command = [sys.executable, "-B", str(SCRIPTS / "check_consistency.py"), "--root", str(self.root)]
        before = self.snapshot()
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["read_only"])
        self.assertEqual(self.snapshot(), before)
        self.write("chapters/a.md", "# A\nTODO\n")
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        result = subprocess.run(command + ["--document", "../escape.md"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "input_error")

    def test_cli_can_import_its_helpers_in_an_isolated_interpreter(self):
        self.write("chapters/a.md", "# A\n")
        command = [sys.executable, "-I", "-B", str(SCRIPTS / "check_consistency.py"), "--root", str(self.root)]
        before = self.snapshot()
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["findings"], [])
        self.assertEqual(self.snapshot(), before)
