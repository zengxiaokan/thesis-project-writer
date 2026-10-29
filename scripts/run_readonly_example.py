#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Replay audit findings in temporary synthetic manuscripts; never edit the base fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/readonly-checks/base"


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in folder.rglob("*") if p.is_file()}


def run_check(folder, script, manifest):
    before = snapshot(folder)
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts" / script),
         "--root", str(folder), "--manifest", manifest],
        cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
        env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("Audit failed: " + result.stdout + result.stderr)
    report = json.loads(result.stdout)
    unchanged = snapshot(folder) == before
    assert unchanged, "An audit modified its input contents, mtimes or file list"
    return result.returncode, report, unchanged


def observe():
    base_before = snapshot(FIXTURE)
    with tempfile.TemporaryDirectory(prefix="thesis-readonly-example-") as temporary:
        parent = Path(temporary).resolve()
        parent.relative_to(Path(tempfile.gettempdir()).resolve())
        good = parent / "good"
        shutil.copytree(FIXTURE, good)
        good_code, good_report, good_unchanged = run_check(good, "check_consistency.py", "review/consistency.json")
        evidence_code, evidence_report, evidence_unchanged = run_check(good, "check_evidence_changes.py", "evidence/claims.json")
        assert good_code == 0 and good_report["findings"] == []
        assert evidence_code == 0 and evidence_report["findings"] == []

        broken = parent / "inconsistent"
        shutil.copytree(FIXTURE, broken)
        chapter = broken / "chapters/chapter-5.md"
        text = chapter.read_text(encoding="utf-8")
        text = text.replace("状态 图.svg", "missing.png").replace("## 5.3 异常与事务", "## 5.X 临时节")
        text += "\n<!-- thesis:id FIG-501 -->\n<!-- thesis:ref FIG-599 -->\n【待确认：补充该关系的来源】\n"
        chapter.write_text(text, encoding="utf-8")
        chapter = broken / "chapters/chapter-6.md"
        chapter.write_text(chapter.read_text(encoding="utf-8").replace("| 合计 | 12 |", "| 合计 | 13 |"), encoding="utf-8")
        authority = broken / "chapters/abstract.md"
        authority.write_text(authority.read_text(encoding="utf-8") + "\n作者新增的版本内容。\n", encoding="utf-8")
        manifest_path = broken / "review/consistency.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["expected_ids"].append("FIG-777")
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        bad_code, bad_report, bad_unchanged = run_check(broken, "check_consistency.py", "review/consistency.json")
        found_codes = {item["code"] for item in bad_report["findings"]}
        expected = {"duplicate_id", "missing_id", "dangling_reference", "image_missing",
                    "unresolved_marker", "section_missing", "table_total_mismatch",
                    "number_conflict", "authority_changed"}
        assert bad_code == 1 and expected.issubset(found_codes), sorted(found_codes)

        changed = parent / "changed-source"
        shutil.copytree(FIXTURE, changed)
        source = changed / "source/service.py"
        source.write_text(source.read_text(encoding="utf-8").replace('state == "available"', 'state == "reserved"'), encoding="utf-8")
        changed_code, changed_report, changed_unchanged = run_check(changed, "check_evidence_changes.py", "evidence/claims.json")
        assert changed_code == 1 and changed_report["needs_review_claim_ids"] == ["C-STATE"]
        assert changed_report["unaffected_claim_ids"] == ["C-CATALOG"]
        affected = changed_report["affected_targets"]
        assert {item["kind"] for item in affected} == {"chapter", "figure", "test"}

        moved = parent / "renamed-source"
        shutil.copytree(FIXTURE, moved)
        old_path, new_path = moved / "source/catalog.py", moved / "source/catalog-renamed.py"
        old_path.resolve().relative_to(parent)
        new_path.resolve().relative_to(parent)
        old_path.rename(new_path)
        path = moved / "evidence/claims.json"
        claims = json.loads(path.read_text(encoding="utf-8"))
        claims["rename_candidates"] = ["source/catalog-renamed.py"]
        path.write_text(json.dumps(claims, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        moved_code, moved_report, moved_unchanged = run_check(moved, "check_evidence_changes.py", "evidence/claims.json")
        assert moved_code == 1 and moved_report["needs_review_claim_ids"] == ["C-CATALOG"]
        assert moved_report["unaffected_claim_ids"] == ["C-STATE"]
    assert snapshot(FIXTURE) == base_before, "Base fixture changed"
    return {
        "scope": "Actual read-only audit CLI calls on temporary copies of synthetic text; not a real thesis acceptance",
        "runtime": {"python": platform.python_version(), "system": platform.system()},
        "sources": {name: hashlib.sha256((ROOT / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                    for name in ("scripts/audit_common.py", "scripts/check_consistency.py",
                                 "scripts/check_evidence_changes.py", "scripts/run_readonly_example.py")},
        "observations": {
            "configured_consistency_control_findings": good_report["findings"],
            "evidence_control_findings": evidence_report["findings"],
            "different_historical_context_not_flagged": not any(item["code"] == "number_conflict" for item in good_report["findings"]),
            "injected_consistency_findings": bad_report["findings"],
            "changed_source_claims": changed_report["needs_review_claim_ids"],
            "unaffected_claims_after_state_change": changed_report["unaffected_claim_ids"],
            "changed_source_targets": affected,
            "renamed_source_findings": moved_report["findings"],
            "all_audit_input_bytes_mtimes_and_file_lists_unchanged": all((good_unchanged, evidence_unchanged, bad_unchanged, changed_unchanged, moved_unchanged)),
            "base_fixture_unchanged": True,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Explicit observation output, outside base fixtures; default only prints JSON")
    args = parser.parse_args()
    if args.output:
        output = args.output.resolve()
        if output == FIXTURE.resolve() or FIXTURE.resolve() in output.parents:
            parser.error("Observation output must be outside base fixtures")
    result = json.dumps(observe(), ensure_ascii=True, indent=2) + "\n"
    if args.output:
        with args.output.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(result)
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
