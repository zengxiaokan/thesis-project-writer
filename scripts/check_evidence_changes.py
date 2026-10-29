#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report registered evidence changes and affected targets without modifying files."""
import sys
sys.dont_write_bytecode = True

import argparse
import os
from pathlib import Path
import re

_SCRIPT_DIRECTORY = str(Path(__file__).resolve().parent)
if _SCRIPT_DIRECTORY not in sys.path:
    # Embeddable Python can omit the script directory from its isolated path.
    sys.path.insert(0, _SCRIPT_DIRECTORY)
from audit_common import InputError, Reader, finding, print_report


HASH_MODES = ("bytes", "text-lf")


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in "\r\n\x00"):
        raise InputError(label + " must be a non-empty single-line string")
    return value


def _list(value, label):
    if not isinstance(value, list):
        raise InputError(label + " must be an array")
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise InputError(label + " must be an object")
    return value


def _manifest_name(reader, manifest):
    selected = Path(manifest).expanduser()
    if selected.is_absolute():
        try:
            return selected.absolute().relative_to(reader.root).as_posix()
        except ValueError:
            raise InputError("Manifest must be inside the selected read root")
    return str(manifest)


def _validate(reader, manifest):
    _object(manifest, "Manifest")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise InputError("schema_version must be 1")
    claims = _list(manifest.get("claims"), "claims")
    seen = set()
    for index, value in enumerate(claims):
        claim = _object(value, "claims[%d]" % index)
        identity = _text(claim.get("claim_id"), "claim_id")
        if identity in seen:
            raise InputError("Duplicate claim_id: " + identity)
        seen.add(identity)
        if "statement" in claim and not isinstance(claim["statement"], str):
            raise InputError("statement must be a string")
        for source_index, source in enumerate(_list(claim.get("sources", []), "sources")):
            _object(source, "source")
            reader.path(_text(source.get("path"), "source.path"))
            mode = source.get("hash_mode", "bytes")
            if mode not in HASH_MODES:
                raise InputError("Unknown hash_mode for %s sources[%d]" % (identity, source_index))
            expected = source.get("sha256")
            if expected not in (None, "") and (not isinstance(expected, str)
                                               or not re.fullmatch(r"[0-9a-fA-F]{64}", expected)):
                raise InputError("sha256 must be 64 hexadecimal characters or an unregistered empty value")
            if "locator" in source:
                _text(source["locator"], "source.locator")
        for target in _list(claim.get("targets", []), "targets"):
            _object(target, "target")
            _text(target.get("kind"), "target.kind")
            reader.path(_text(target.get("path"), "target.path"))
            if "locator" in target:
                _text(target["locator"], "target.locator")
    for key in ("rename_candidates", "rename_roots"):
        for name in _list(manifest.get(key, []), key):
            reader.path(_text(name, key + " entry"))
    return claims


def _rename_files(reader, manifest, findings):
    paths = set()
    for name in manifest.get("rename_candidates", []):
        path = reader.path(name)
        if path.is_file():
            paths.add(reader.name(path))
        else:
            findings.append(finding("rename_candidate_missing", "Registered rename candidate is not an existing file", name))
    for name in manifest.get("rename_roots", []):
        root = reader.path(name)
        if not root.is_dir():
            findings.append(finding("rename_root_missing", "Registered rename search root is not an existing directory", name))
            continue
        for folder, directories, files in os.walk(str(root), followlinks=False):
            # Validate directory entries before descending; never follow a junction.
            for child in sorted(directories):
                reader.path(reader.name(Path(folder) / child))
            for child in sorted(files):
                path = reader.path(reader.name(Path(folder) / child))
                if path.is_file():
                    paths.add(reader.name(path))
    return sorted(paths)


def check_evidence_changes(root, manifest):
    reader = Reader(root)
    manifest_name = _manifest_name(reader, manifest)
    data = reader.load_json(manifest_name)
    claims = _validate(reader, data)
    findings = []
    candidates = _rename_files(reader, data, findings)
    candidate_hashes = {}
    claims_report = []
    affected = {}
    needs_review = []
    unaffected = []
    source_checks = 0
    target_paths = set()
    candidate_reads = set()
    if not claims:
        findings.append(finding("no_claims", "No claims were registered; no evidence baseline was checked", manifest_name))

    def possible_renames(expected, mode):
        matches = []
        for name in candidates:
            key = (name, mode)
            if key not in candidate_hashes:
                candidate_hashes[key] = reader.fingerprint(name, mode)
                candidate_reads.add(name)
            if candidate_hashes[key] == expected:
                matches.append(name)
        return matches

    for claim_index, claim in enumerate(claims):
        identity = claim["claim_id"]
        reasons = []
        sources_report = []
        sources = claim.get("sources", [])
        if not sources:
            reasons.append("sources_unregistered")
            findings.append(finding("sources_unregistered", "No source is registered for this claim", manifest_name,
                                    claim_id=identity, record="claims[%d].sources" % claim_index))
        for source_index, source in enumerate(sources):
            name = source["path"]
            mode = source.get("hash_mode", "bytes")
            expected = source.get("sha256") or None
            if expected:
                expected = expected.lower()
            item = {"path": name, "hash_mode": mode, "expected_sha256": expected}
            if "locator" in source:
                item["locator"] = source["locator"]
            location = {"claim_id": identity, "manifest": manifest_name,
                        "record": "claims[%d].sources[%d]" % (claim_index, source_index)}
            if "locator" in source:
                location["registered_locator"] = source["locator"]
            path = reader.path(name)
            if not path.is_file():
                item["status"] = "missing"
                item["rename_candidates"] = possible_renames(expected, mode) if expected else []
                count = len(item["rename_candidates"])
                item["rename_status"] = "unique_candidate" if count == 1 else ("ambiguous_candidates" if count else "no_candidate")
                reasons.append("source_missing")
                findings.append(finding("source_missing", "Registered source is missing; candidate paths are not adopted automatically",
                                        name, rename_candidates=item["rename_candidates"], rename_status=item["rename_status"], **location))
                if not expected:
                    reasons.append("baseline_missing")
                    findings.append(finding("baseline_missing", "No fingerprint is registered; rename or change comparison cannot be established",
                                            name, **location))
            else:
                actual = reader.fingerprint(name, mode)
                item["actual_sha256"] = actual
                source_checks += 1
                if expected is None:
                    item["status"] = "baseline_missing"
                    reasons.append("baseline_missing")
                    findings.append(finding("baseline_missing", "Source can be read, but no registered fingerprint is available for comparison",
                                            name, **location))
                elif actual != expected:
                    item["status"] = "changed"
                    reasons.append("source_changed")
                    findings.append(finding("source_changed", "Source fingerprint changed; review the claim and its linked targets, not an automatic factual error",
                                            name, expected_sha256=expected, actual_sha256=actual, hash_mode=mode, **location))
                else:
                    item["status"] = "unchanged"
            sources_report.append(item)
        targets_report = []
        targets = claim.get("targets", [])
        if not targets:
            reasons.append("targets_unregistered")
            findings.append(finding("targets_unregistered", "No chapter, figure or test target is registered; the impact cannot be located",
                                    manifest_name, claim_id=identity, record="claims[%d].targets" % claim_index))
        for target_index, target in enumerate(targets):
            name = target["path"]
            target_paths.add(reader.name(reader.path(name)))
            item = {"kind": target["kind"], "path": name, "exists": reader.path(name).is_file()}
            if "locator" in target:
                item["locator"] = target["locator"]
            if not item["exists"]:
                reasons.append("target_missing")
                findings.append(finding("target_missing", "Registered impact target is missing", name, claim_id=identity,
                                        manifest=manifest_name, record="claims[%d].targets[%d]" % (claim_index, target_index),
                                        registered_locator=target.get("locator")))
            targets_report.append(item)
        reasons = list(dict.fromkeys(reasons))
        status = "needs_review" if reasons else "no_registered_source_change"
        if reasons:
            needs_review.append(identity)
            for target in targets_report:
                key = (target["kind"], target["path"], target.get("locator"))
                if key not in affected:
                    affected[key] = {**target, "claim_ids": []}
                affected[key]["claim_ids"].append(identity)
        else:
            unaffected.append(identity)
        item = {"claim_id": identity, "status": status, "review_reasons": reasons,
                "sources": sources_report, "targets": targets_report}
        if "statement" in claim:
            item["statement"] = claim["statement"]
        claims_report.append(item)
    return {
        "tool": "check_evidence_changes", "schema_version": 1, "root": str(reader.root),
        "manifest": manifest_name, "status": "needs_review" if findings else "no_registered_changes_detected",
        "findings": findings, "claims": claims_report,
        "needs_review_claim_ids": needs_review, "unaffected_claim_ids": unaffected,
        "affected_targets": list(affected.values()),
        "coverage": {
            "registered_claims": len(claims), "registered_sources": sum(len(c.get("sources", [])) for c in claims),
            "source_fingerprints_checked": source_checks, "files_read": sorted(reader.accessed),
            "target_paths_checked": sorted(target_paths),
            "rename_search": {"enabled": bool(data.get("rename_candidates") or data.get("rename_roots")),
                              "explicit_files": data.get("rename_candidates", []), "roots": data.get("rename_roots", []),
                              "candidate_files_in_scope": len(candidates), "candidate_files_hashed": len(candidate_reads)},
            "not_checked": ["Meaning of source changes", "Unregistered claims and sources", "Target text or diagram semantics", "Document page layout"],
        },
        "limitations": [
            "Changed bytes do not establish that a claim is false; comments and formatting can also change fingerprints.",
            "Unchanged registered fingerprints do not establish continuing factual correctness or complete source coverage.",
            "Matching rename candidates can be copies; even one candidate is not automatically adopted.",
            "The tool never writes baselines, sources, targets, logs or caches and does not execute project code.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Explicit allowed read root")
    parser.add_argument("--manifest", required=True, help="Registered claims JSON inside the read root")
    args = parser.parse_args(argv)
    try:
        report = check_evidence_changes(args.root, args.manifest)
    except (InputError, OSError, ValueError) as error:
        print_report({"tool": "check_evidence_changes", "schema_version": 1, "status": "input_error",
                      "error": str(error), "findings": [], "coverage": {"complete": False}})
        return 2
    print_report(report)
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
