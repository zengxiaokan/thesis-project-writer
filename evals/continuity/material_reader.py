#!/usr/bin/env python3
"""Read synthetic project materials with an explicit external evaluation log."""
import sys
sys.dont_write_bytecode = True

import argparse
import hashlib
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from audit_common import InputError, Reader, is_link, print_report
from inventory_sources import inventory_sources


def read_material(project, log, paths=None, inventory=False):
    reader = Reader(project)
    log = Path(log).absolute()
    # The instrumentation writes only outside the audited project, never to it.
    resolved_log = log.resolve()
    if resolved_log == reader.root or reader.root in resolved_log.parents:
        raise InputError("Evaluation read log must be outside project materials")
    if not log.parent.is_dir():
        raise InputError("Evaluation log parent must already exist")
    if is_link(log):
        raise InputError("Evaluation log must not be a link or reparse point")
    if log.exists() and (not log.is_file() or log.stat().st_nlink != 1):
        raise InputError("Existing evaluation log must be a regular file with one link")
    if inventory:
        result = inventory_sources(reader.root, hash_files=True, hash_mode="text-lf")
        event = {"action": "inventory", "report": result,
                 "note": "Hashes read file bytes; this is not a model content-reading event."}
    else:
        if not paths:
            raise InputError("At least one relative file is required")
        selected = []
        for name in paths:
            data = reader.read_bytes(name)
            try:
                text = data.decode("utf-8-sig")
            except UnicodeError as error:
                raise InputError("Evaluation content reads require UTF-8 text: " + name) from error
            selected.append({"path": reader.name(reader.path(name)), "text": text,
                             "sha256_text_lf": hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
                             "bytes": len(data)})
        result = {"files": selected}
        event = {"action": "content_read", "files": [{k: v for k, v in item.items() if k != "text"}
                                                       for item in selected]}
    with log.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inventory", action="store_true")
    group.add_argument("--read", nargs="+")
    args = parser.parse_args()
    try:
        print_report(read_material(args.project, args.log, args.read, args.inventory))
    except (InputError, OSError) as error:
        print_report({"error": str(error)})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
