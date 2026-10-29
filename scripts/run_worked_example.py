#!/usr/bin/env python3
"""Replay real initializer behavior for the public single-section writing example."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import runpy
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def observe():
    source = ROOT / "scripts/init_workspace.py"
    initialize = runpy.run_path(str(source))["initialize"]
    with tempfile.TemporaryDirectory(prefix="thesis-worked-example-") as temporary:
        parent = Path(temporary).resolve()
        parent.relative_to(Path(tempfile.gettempdir()).resolve())
        project = parent / "project"
        project.mkdir()
        initialize(project, dry_run=True)
        preview_empty = list(project.iterdir()) == []
        analyzed = initialize(project)
        workspace = Path(analyzed["workspace"])
        entry = workspace / "README.md"
        entry.write_text("Existing entry used only as test input.\n", encoding="utf-8")
        analysis_records = {p.relative_to(workspace).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                            for p in workspace.rglob("*") if p.is_file()}
        intake = initialize(workspace=workspace, profile="intake")
        analysis_preserved = all((workspace / name).read_bytes() == value[0]
                                 and (workspace / name).stat().st_mtime_ns == value[1]
                                 for name, value in analysis_records.items())
        initial = {p.relative_to(workspace).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                   for p in workspace.rglob("*") if p.is_file()}
        expanded = initialize(project, profile="software")
        preserved = all((workspace / name).read_bytes() == value[0] for name, value in initial.items())
        times = all((workspace / name).stat().st_mtime_ns == value[1] for name, value in initial.items())
        before_repeat = {p.relative_to(workspace).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                         for p in workspace.rglob("*") if p.is_file()}
        repeated = initialize(project, profile="software")
        after_repeat = {p.relative_to(workspace).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
                        for p in workspace.rglob("*") if p.is_file()}
        observations = {
            "preview_wrote_nothing": preview_empty,
            "analysis_created_files": len(analyzed["created_files"]),
            "intake_created_files": len(intake["created_files"]),
            "analysis_records_preserved_on_intake": analysis_preserved,
            "intake_continuation_paths": sorted(item["path"] for item in intake["continuation_required"]),
            "upgrade_created_files": len(expanded["created_files"]),
            "existing_file_bytes_preserved": preserved,
            "existing_file_mtimes_preserved": times,
            "continuation_paths": sorted(item["path"] for item in expanded["continuation_required"]),
            "repeat_created_files": len(repeated["created_files"]),
            "repeat_all_bytes_and_mtimes_preserved": before_repeat == after_repeat,
        }
        assert preview_empty and analysis_preserved and preserved and times and before_repeat == after_repeat
        assert observations["analysis_created_files"] == 4
        assert observations["intake_created_files"] == 2
        assert observations["upgrade_created_files"] == 15
        assert len(observations["intake_continuation_paths"]) == 3
        assert observations["repeat_created_files"] == 0
        assert len(observations["continuation_paths"]) == 6
    return {
        "scope": "Real initializer execution in temporary directories; one writing-section example, not a full thesis",
        "input_kind": "Scripted test data; no real author interview or private manuscript",
        "source": {"path": "scripts/init_workspace.py", "sha256": hashlib.sha256(source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()},
        "runtime": {"python": platform.python_version(), "system": platform.system()},
        "observations": observations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Explicit output path; default prints JSON without changing repository files")
    args = parser.parse_args()
    output = json.dumps(observe(), ensure_ascii=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
