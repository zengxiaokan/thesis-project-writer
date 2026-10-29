#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List an explicit local material scope without interpreting business modules."""
import sys
sys.dont_write_bytecode = True

import argparse
import hashlib
import os
from pathlib import Path
import stat

_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPT_DIRECTORY)
from audit_common import InputError, Reader, finding, is_link, print_report


DEFAULT_EXCLUDED_NAMES = (
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".tox",
)


class ReportArgumentParser(argparse.ArgumentParser):
    """Keep help and option failures machine-readable like normal reports."""

    def error(self, message):
        raise InputError(message)

    def print_help(self, file=None):
        print_report({"tool": "inventory_sources", "schema_version": 1,
                      "status": "usage", "usage": self.format_help()})


def inventory_sources(root, excludes=None, hash_files=False, hash_mode="bytes",
                      use_default_excludes=True):
    """Return file metadata and optional hashes; never write a snapshot or cache."""
    if type(hash_files) is not bool or type(use_default_excludes) is not bool:
        raise InputError("Hash and default-exclusion options must be booleans")
    if hash_mode not in ("bytes", "text-lf"):
        raise InputError("hash_mode must be bytes or text-lf")
    if excludes is None:
        excludes = []
    if not isinstance(excludes, (list, tuple)):
        raise InputError("excludes must be a list of relative directories")
    reader = Reader(root)
    excluded, skipped, findings = [], [], []
    explicit = set()
    for name in excludes:
        if not isinstance(name, str) or not name.strip() or any(char in name for char in "\r\n\x00"):
            raise InputError("Each exclusion must be a non-empty relative directory")
        selected = reader.path(name)
        if selected == reader.root:
            raise InputError("The selected read root cannot exclude itself")
        relative = reader.name(selected)
        if selected.exists() and not selected.is_dir():
            raise InputError("Exclusion must name a directory: " + relative)
        explicit.add(relative)
        if not selected.exists():
            findings.append(finding("exclude_directory_missing", "Configured exclusion directory does not exist", path=relative))
    defaults = set(DEFAULT_EXCLUDED_NAMES) if use_default_excludes else set()
    explicit_matches = {os.path.normcase(name) for name in explicit}
    default_matches = {os.path.normcase(name) for name in defaults}
    files = []
    hash_attempts, hash_bytes = 0, 0

    def skip(path, code, message):
        relative = reader.name(path)
        skipped.append({"path": relative, "reason": code})
        findings.append(finding(code, message, path=relative))

    def walk_error(error):
        path = Path(error.filename) if error.filename else reader.root
        try:
            relative = reader.name(path)
        except ValueError:
            relative = "."
        skipped.append({"path": relative, "reason": "directory_unreadable"})
        findings.append(finding("directory_unreadable", "Directory could not be enumerated", path=relative,
                                error_type=type(error).__name__))

    for parent, directories, names in os.walk(str(reader.root), topdown=True,
                                               onerror=walk_error, followlinks=False):
        parent = Path(parent)
        retained = []
        for name in sorted(directories):
            path = parent / name
            relative = reader.name(path)
            if os.path.normcase(relative) in explicit_matches:
                excluded.append({"path": relative, "reason": "explicit_directory"})
                continue
            if os.path.normcase(name) in default_matches:
                excluded.append({"path": relative, "reason": "default_directory_name", "name": name})
                continue
            try:
                if is_link(path):
                    skip(path, "linked_directory_skipped", "Linked or reparse-point directory was not followed")
                    continue
                reader.path(relative)
                retained.append(name)
            except (InputError, OSError) as error:
                skip(path, "directory_scope_uncheckable", "Directory scope could not be safely checked")
        directories[:] = retained
        for name in sorted(names):
            path = parent / name
            relative = reader.name(path)
            try:
                if is_link(path):
                    skip(path, "linked_file_skipped", "Linked or reparse-point file was not read")
                    continue
                selected = reader.path(relative)
                before = selected.lstat()
                if not stat.S_ISREG(before.st_mode):
                    skip(path, "unsupported_file_type", "Only regular files are inventoried")
                    continue
                entry = {"path": relative, "bytes": before.st_size, "mtime_ns": before.st_mtime_ns}
                if hash_files:
                    hash_attempts += 1
                    try:
                        raw = reader.read_bytes(relative)
                        payload = raw.replace(b"\r\n", b"\n") if hash_mode == "text-lf" else raw
                        entry["sha256"] = hashlib.sha256(payload).hexdigest()
                        entry["hash_mode"] = hash_mode
                        hash_bytes += len(raw)
                    except (InputError, OSError) as error:
                        entry["hash_status"] = "unreadable"
                        findings.append(finding("hash_unreadable", "File bytes could not be fingerprinted", path=relative,
                                                error_type=type(error).__name__))
                    after = selected.lstat()
                    if (after.st_size, after.st_mtime_ns) != (before.st_size, before.st_mtime_ns):
                        findings.append(finding("file_changed_during_inventory", "File metadata changed during inventory; recheck its baseline", path=relative))
                files.append(entry)
            except (InputError, OSError) as error:
                skip(path, "file_scope_uncheckable", "File scope or metadata could not be checked")

    return {
        "schema_version": 1,
        "tool": "inventory_sources",
        "root": str(reader.root),
        "status": "partial" if findings else "listed",
        "files": sorted(files, key=lambda entry: entry["path"]),
        "excluded": sorted(excluded, key=lambda entry: entry["path"]),
        "skipped": sorted(skipped, key=lambda entry: entry["path"]),
        "findings": findings,
        "coverage": {
            "files_listed": len(files),
            "metadata_only": not hash_files,
            "hash_mode": hash_mode if hash_files else None,
            "content_hash_attempts": hash_attempts,
            "content_hash_reads": len(reader.accessed),
            "content_hash_bytes": hash_bytes,
            "default_excluded_names": sorted(defaults),
            "explicit_excluded_directories": sorted(explicit),
            "business_modules_assessed": False,
            "model_content_reads_measured": False,
            "limits": [
                "Paths, metadata and hashes do not establish business coverage or understanding.",
                "Hashing reads file bytes; metadata listing and model content reads are different activities.",
                "Default directory names are configurable exclusion hints, not verified third-party classifications.",
                "Read-only checks do not guarantee unchanged access times or atomic isolation against concurrent replacements.",
            ],
        },
    }


def main(argv=None):
    parser = ReportArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Explicit read boundary; no whole-device default")
    parser.add_argument("--exclude", action="append", default=[], help="Additional root-relative directory, repeatable")
    parser.add_argument("--no-default-excludes", action="store_true", help="List directories normally excluded by name")
    parser.add_argument("--hash", action="store_true", dest="hash_files", help="Read file bytes and add SHA-256 fingerprints")
    parser.add_argument("--hash-mode", choices=("bytes", "text-lf"), default="bytes")
    try:
        args = parser.parse_args(argv)
        report = inventory_sources(args.root, args.exclude, args.hash_files, args.hash_mode,
                                   use_default_excludes=not args.no_default_excludes)
    except (InputError, OSError) as error:
        print_report({"tool": "inventory_sources", "schema_version": 1, "status": "input_error",
                      "findings": [finding("input_error", str(error))]})
        return 2
    print_report(report)
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
