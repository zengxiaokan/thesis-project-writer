#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Report explicit Markdown thesis inconsistencies without modifying files."""
import sys
sys.dont_write_bytecode = True

import argparse
from collections import defaultdict
from decimal import Decimal, InvalidOperation, localcontext
import json
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_common import InputError, Reader, finding, is_link, print_report


MARKER = re.compile(r"<!--\s*thesis:(id|ref)\s+([A-Za-z][A-Za-z0-9_.:-]*)\s*-->")
IMAGE_START = re.compile(r"!\[[^\]\n]*\]\(")
PENDING = re.compile(r"【待确认[^】\n]*】|(?<!\w)(?:TODO|FIXME)(?!\w)")
CONTEXT_KEYS = ("version", "batch", "object", "method")
TOP_KEYS = {"schema_version", "documents", "entities", "references", "expected_ids",
            "required_sections", "table_checks", "authority"}


def string(value, label):
    if not isinstance(value, str) or not value.strip():
        raise InputError(label + " must be a non-empty string")
    return value


def array(value, label):
    if not isinstance(value, list):
        raise InputError(label + " must be a list")
    return value


def object_value(value, label):
    if not isinstance(value, dict):
        raise InputError(label + " must be an object")
    return value


def positive_line(value, label):
    if type(value) is not int or value < 1:
        raise InputError(label + " must be a positive 1-based line number")
    return value


def visible_lines(text):
    """Preserve line locations while masking fenced and inline code examples."""
    result, fence = [], None
    for raw in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", raw)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            result.append("")
        elif match:
            fence = match[1]
            result.append("")
        else:
            result.append(re.sub(r"(`+).*?\1", lambda item: " " * len(item[0]), raw))
    return result


def image_targets(line):
    """Parse common inline image destinations without truncating nested parens."""
    targets, malformed, consumed = [], 0, 0

    def whitespace(index):
        while index < len(line) and line[index].isspace():
            index += 1
        return index

    def end_of_image(index):
        index = whitespace(index)
        if index < len(line) and line[index] == ")":
            return index + 1
        if index >= len(line) or line[index] not in ("\"", "'", "("):
            return None
        delimiter = ")" if line[index] == "(" else line[index]
        index += 1
        while index < len(line):
            if line[index] == "\\" and index + 1 < len(line):
                index += 2
            elif line[index] == delimiter:
                index = whitespace(index + 1)
                return index + 1 if index < len(line) and line[index] == ")" else None
            else:
                index += 1
        return None

    for opening in IMAGE_START.finditer(line):
        if opening.start() < consumed:
            continue
        start = whitespace(opening.end())
        index, destination_end, valid = start, None, True
        if index < len(line) and line[index] == "<":
            start = index + 1
            index = start
            while index < len(line):
                if line[index] == "\\" and index + 1 < len(line):
                    index += 2
                elif line[index] == ">":
                    destination_end = index
                    index += 1
                    break
                else:
                    index += 1
        else:
            depth = 0
            while index < len(line):
                char = line[index]
                if char == "\\" and index + 1 < len(line):
                    index += 2
                    continue
                if char == "(":
                    depth += 1
                elif char == ")":
                    if not depth:
                        destination_end = index
                        break
                    depth -= 1
                elif char.isspace():
                    valid = not depth
                    destination_end = index
                    break
                index += 1
            if depth:
                valid = False
        end = end_of_image(index) if valid and destination_end is not None else None
        if end is None or destination_end == start:
            malformed += 1
            continue
        target = line[start:destination_end]
        # Markdown backslash escapes are part of syntax, not filename bytes.
        target = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\\\]^_`{|}~])", r"\1", target)
        targets.append(target)
        consumed = end
    return targets, malformed


def discover_documents(reader, skipped):
    chapters = reader.path("chapters")
    if not chapters.is_dir():
        return []
    found = []
    for parent, directories, files in os.walk(str(chapters), followlinks=False):
        kept = []
        for name in directories:
            path = Path(parent) / name
            if is_link(path):
                skipped.append({"check": "document_discovery", "path": reader.name(path), "reason": "linked_directory"})
            else:
                kept.append(name)
        directories[:] = sorted(kept)
        for name in sorted(files):
            path = Path(parent) / name
            if path.suffix.lower() == ".md":
                if is_link(path):
                    skipped.append({"check": "document_discovery", "path": reader.name(path), "reason": "linked_file"})
                else:
                    found.append(reader.name(path))
    return found


def cells(line):
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    return [cell.replace("\\|", "|").strip() for cell in re.split(r"(?<!\\)\|", text)]


def number(value, kind):
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", value):
        raise ValueError("Cell is not a plain numeric value")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid number") from error
    if not result.is_finite() or (kind == "integer" and result != result.to_integral_value()):
        raise ValueError("Cell does not match the declared numeric type")
    return result


def check(root, manifest=None, documents=None):
    reader = Reader(root)
    config = reader.load_json(manifest) if manifest else {}
    object_value(config, "manifest")
    if manifest and (type(config.get("schema_version")) is not int or config.get("schema_version") != 1):
        raise InputError("manifest schema_version must be 1")
    if set(config) - TOP_KEYS:
        raise InputError("Unknown manifest keys: " + ", ".join(sorted(set(config) - TOP_KEYS)))
    findings, skipped, unchecked = [], [], []
    selected = documents if documents is not None else config.get("documents")
    if selected is None:
        selected = discover_documents(reader, skipped)
    selected = array(selected, "documents")
    docs, raw_docs = {}, {}
    for name in selected:
        name = reader.name(reader.path(string(name, "document")))
        if name in docs:
            continue
        if Path(name).suffix.lower() != ".md":
            skipped.append({"check": "document_content", "path": name, "reason": "only_markdown_text_supported"})
            continue
        try:
            raw = reader.read_text(name)
        except FileNotFoundError:
            findings.append(finding("document_missing", "Selected document does not exist", name, severity="error"))
            continue
        raw_docs[name] = raw.splitlines()
        docs[name] = visible_lines(raw)
    if not docs:
        findings.append(finding("no_documents_checked", "No readable Markdown manuscript was checked"))

    def registered_document(value):
        name = reader.name(reader.path(string(value, "document")))
        if name not in docs:
            raise InputError("Registered content must refer to a selected readable document: " + name)
        return name

    definitions, refs = defaultdict(set), []
    image_count = 0
    for name, lines in docs.items():
        for line_no, line in enumerate(lines, 1):
            for marker in MARKER.finditer(line):
                if marker[1] == "id":
                    definitions[marker[2]].add((name, line_no))
                else:
                    refs.append((marker[2], name, line_no))
            for pending in PENDING.finditer(line):
                findings.append(finding("unresolved_marker", "Review this explicit unresolved marker", name,
                                        line_no, marker=pending[0]))
            targets, malformed_images = image_targets(line)
            if line.count("![") > len(targets):
                skipped.append({"check": "image_path", "path": name, "line": line_no, "reason": "unsupported_markdown_image_syntax"})
            for _ in range(malformed_images):
                findings.append(finding("image_path_uncheckable", "Image destination or optional title has unsupported or unbalanced syntax", name, line_no))
            for target in targets:
                image_count += 1
                try:
                    parsed = urlsplit(target)
                except ValueError:
                    findings.append(finding("image_path_uncheckable", "Image target is not a supported URL or local path", name, line_no))
                    continue
                if parsed.scheme.lower() in ("http", "https", "data") or parsed.netloc:
                    skipped.append({"check": "image_path", "path": name, "line": line_no, "reason": "remote_or_embedded_image_not_verified"})
                    continue
                if parsed.scheme:
                    findings.append(finding("image_path_unsafe", "Unsupported local image path scheme", name, line_no))
                    continue
                relative = unquote(parsed.path)
                try:
                    path = reader.path(relative, base=Path(name).parent)
                    if not path.is_file():
                        findings.append(finding("image_missing", "Local image file does not exist", name, line_no,
                                                target=relative))
                except InputError as error:
                    findings.append(finding("image_path_unsafe", str(error), name, line_no, severity="error"))

    for field, target in (("entities", definitions), ("references", None)):
        for item in array(config.get(field, []), field):
            object_value(item, field + " entry")
            identity = string(item.get("id"), field + ".id")
            name = registered_document(item.get("document"))
            line_no = positive_line(item.get("line"), field + ".line")
            if line_no > len(docs[name]):
                raise InputError("Registered line is outside document: " + name)
            if target is not None:
                target[identity].add((name, line_no))
            else:
                refs.append((identity, name, line_no))
    for identity, positions in definitions.items():
        if len(positions) > 1:
            first = sorted(positions)[0]
            findings.append(finding("duplicate_id", "Stable ID has multiple definition positions", *first,
                                    id=identity, locations=[{"path": p, "line": n} for p, n in sorted(positions)]))
    for identity in array(config.get("expected_ids", []), "expected_ids"):
        string(identity, "expected_id")
        if identity not in definitions:
            findings.append(finding("missing_id", "Expected stable ID has no registered definition", id=identity))
    for identity, name, line_no in refs:
        if identity not in definitions:
            findings.append(finding("dangling_reference", "Explicit reference has no stable-ID definition", name,
                                    line_no, id=identity))

    for item in array(config.get("required_sections", []), "required_sections"):
        object_value(item, "required_section")
        name = registered_document(item.get("document"))
        heading = string(item.get("heading"), "required_section.heading").strip()
        headings = [re.sub(r"\s+#+\s*$", "", m[1]).strip() for line in docs[name]
                    for m in [re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)] if m]
        if heading not in headings:
            findings.append(finding("section_missing", "Required exact heading is missing", name, heading=heading))
    if not config.get("required_sections"):
        unchecked.append("required_sections")

    comparisons = defaultdict(list)
    checked_tables, table_ids = [], set()
    for item in array(config.get("table_checks", []), "table_checks"):
        object_value(item, "table_check")
        identity = string(item.get("id"), "table_check.id")
        if identity in table_ids:
            raise InputError("Duplicate table check ID: " + identity)
        table_ids.add(identity)
        name = registered_document(item.get("document"))
        if ("anchor" in item) == ("line" in item):
            raise InputError("Table check requires exactly one of anchor or header line")
        if "anchor" in item:
            anchor = string(item["anchor"], "table_check.anchor")
            positions = definitions.get(anchor, set())
            if len(positions) != 1 or next(iter(positions))[0] != name:
                findings.append(finding("table_anchor_missing_or_ambiguous", "Table anchor is missing, duplicated or in another document", name, id=identity))
                continue
            start = next(iter(positions))[1] - 1
            if "|" not in docs[name][start]:
                start += 1
            while start < len(docs[name]) and not docs[name][start].strip():
                start += 1
        else:
            start = positive_line(item["line"], "table_check.line") - 1
        columns = []
        for field in ("label_column", "value_column"):
            value = item.get(field)
            if type(value) is not int or value < 0:
                raise InputError(field + " must be a zero-based non-negative column index")
            columns.append(value)
        labels = array(item.get("sum_of"), "table_check.sum_of")
        if not labels or any(not isinstance(label, str) or not label for label in labels) or len(set(labels)) != len(labels):
            raise InputError("sum_of requires distinct non-empty row labels")
        total_label = string(item.get("total"), "table_check.total")
        if total_label in labels:
            raise InputError("total row cannot be one of sum_of rows")
        kind = item.get("value_type")
        if kind not in ("integer", "decimal"):
            raise InputError("value_type must be integer or decimal")
        unit = string(item.get("unit"), "table_check.unit")
        if type(item.get("non_negative", False)) is not bool:
            raise InputError("non_negative must be boolean")
        try:
            tolerance = number(str(item.get("tolerance", "0")), "decimal")
            if tolerance < 0:
                raise ValueError("Negative tolerance")
        except ValueError as error:
            raise InputError("tolerance must be a finite non-negative plain number") from error
        context = object_value(item.get("context", {}), "table_check.context")
        if any(not isinstance(key, str) or not isinstance(value, (str, int)) or isinstance(value, bool)
               for key, value in context.items()):
            raise InputError("context keys and values must be scalar strings or integers")
        lines = docs[name]
        if (start + 1 >= len(lines) or "|" not in lines[start]
                or not all(re.fullmatch(r":?-{3,}:?", value) for value in cells(lines[start + 1]))):
            findings.append(finding("table_not_found", "Registered position is not a supported Markdown pipe table", name,
                                    start + 1, id=identity))
            continue
        width = len(cells(lines[start]))
        rows, malformed = defaultdict(list), False
        index = start + 2
        while index < len(lines) and "|" in lines[index] and lines[index].strip():
            row = cells(lines[index])
            if len(row) != width or max(columns) >= width:
                findings.append(finding("table_uncheckable", "Table cells or configured columns are ambiguous", name,
                                        index + 1, id=identity))
                malformed = True
                break
            rows[row[columns[0]]].append((row[columns[1]], index + 1))
            index += 1
        required = labels + [total_label]
        metrics = array(item.get("metrics", []), "table_check.metrics")
        for metric in metrics:
            object_value(metric, "metric")
            string(metric.get("metric_id"), "metric_id")
            required.append(string(metric.get("row"), "metric.row"))
        values = {}
        if not malformed:
            for label in dict.fromkeys(required):
                if len(rows.get(label, [])) != 1:
                    findings.append(finding("table_row_missing_or_duplicate", "Required row is missing or ambiguous", name,
                                            start + 1, id=identity, row=label))
                    malformed = True
                    continue
                raw_value, line_no = rows[label][0]
                try:
                    value = number(raw_value, kind)
                    if item.get("non_negative", False) and value < 0:
                        raise ValueError("Negative value")
                    values[label] = value
                except ValueError:
                    findings.append(finding("table_value_uncheckable", "Cell is missing, mixed-unit or not of the declared numeric type", name,
                                            line_no, id=identity, row=label))
                    malformed = True
        if malformed:
            continue
        checked_tables.append(identity)
        numbers = list(values.values()) + [tolerance]
        scale = max(0, *[-value.as_tuple().exponent for value in numbers])
        integer_digits = max(1, *[len(value.as_tuple().digits) + value.as_tuple().exponent for value in numbers])
        with localcontext() as arithmetic:
            arithmetic.prec = max(28, integer_digits + scale + len(str(len(labels))) + 2)
            expected = sum((values[label] for label in labels), Decimal(0))
            actual = values[total_label]
            mismatched = abs(expected - actual) > tolerance
        if mismatched:
            findings.append(finding("table_total_mismatch", "Declared total does not equal the registered component sum", name,
                                    rows[total_label][0][1], id=identity, expected=str(expected), actual=str(actual), unit=unit,
                                    context=context))
        if metrics:
            comparison_id = item.get("comparison_id")
            if not isinstance(comparison_id, str) or not comparison_id or any(key not in context or context[key] == "" for key in CONTEXT_KEYS):
                skipped.append({"check": "cross_table_numbers", "id": identity, "reason": "comparison_id_or_complete_context_missing"})
                continue
            for metric in metrics:
                key = (comparison_id, metric["metric_id"], unit,
                       json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
                label = metric["row"]
                comparisons[key].append({"path": name, "line": rows[label][0][1], "table_id": identity,
                                         "value": str(values[label])})
    comparison_groups = 0
    for key, observations in comparisons.items():
        if len(observations) > 1:
            comparison_groups += 1
            if len({Decimal(value["value"]) for value in observations}) > 1:
                first = observations[0]
                findings.append(finding("number_conflict", "Explicitly comparable table observations disagree", first["path"], first["line"],
                                        comparison_id=key[0], metric_id=key[1], unit=key[2], context=json.loads(key[3]), observations=observations))
    if not config.get("table_checks"):
        unchecked.append("typed_table_totals")
    if not comparisons:
        unchecked.append("cross_table_numbers")

    authority_status = None
    if "authority" in config:
        authority = object_value(config["authority"], "authority")
        path = string(authority.get("path"), "authority.path")
        version = string(authority.get("version"), "authority.version")
        mode = authority.get("hash_mode", "bytes")
        if mode not in ("bytes", "text-lf"):
            raise InputError("Unknown authority hash_mode")
        expected = authority.get("sha256")
        if expected is not None and (not isinstance(expected, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected)):
            raise InputError("authority.sha256 must contain 64 hexadecimal characters")
        safe = reader.path(path)
        authority_status = {"path": reader.name(safe), "declared_version": version, "hash_mode": mode}
        if not safe.is_file():
            authority_status["status"] = "missing"
            findings.append(finding("authority_missing", "Declared authoritative manuscript is missing", reader.name(safe)))
        elif expected is None:
            authority_status["status"] = "no_fingerprint_baseline"
            findings.append(finding("authority_baseline_missing", "Authority is declared but its fingerprint baseline is not registered", reader.name(safe)))
        else:
            actual = reader.fingerprint(path, mode)
            authority_status["status"] = "fingerprint_matches" if actual.lower() == expected.lower() else "needs_review"
            if actual.lower() != expected.lower():
                findings.append(finding("authority_changed", "Authoritative file fingerprint changed; review its declared version and synchronization direction", reader.name(safe),
                                        declared_version=version, expected_sha256=expected.lower(), actual_sha256=actual))
    else:
        unchecked.append("authoritative_manuscript_fingerprint")

    return {"tool": "thesis_consistency", "read_only": True, "root": str(reader.root),
            "status": "findings" if findings else "no_findings_in_checked_scope", "findings": findings,
            "authority": authority_status,
            "coverage": {"documents": sorted(docs), "read_files": sorted(reader.accessed),
                         "definition_ids": sorted(definitions), "explicit_references": len(refs),
                         "images_examined": image_count, "tables_checked": checked_tables,
                         "comparison_groups_checked": comparison_groups,
                         "not_configured": unchecked, "skipped": skipped,
                         "limits": ["Only explicit stable IDs and registrations are checked; natural-language figure numbers and ordinary numeric citations are not inferred.",
                                    "Pipe-table checks require declared rows, types, units and comparison identity; no free-prose number comparison.",
                                    "Existing image files are not visual or page validation. Word/PDF content and rendering are not inspected.",
                                    "Fingerprints do not identify the newest manuscript or prove a claim wrong; no document is corrected."]}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--manifest", help="Optional JSON path relative to root; not loaded automatically")
    parser.add_argument("--document", action="append", help="Selected Markdown path relative to root; may be repeated")
    args = parser.parse_args(argv)
    try:
        report = check(args.root, args.manifest, args.document)
    except (InputError, OSError) as error:
        print_report({"tool": "thesis_consistency", "read_only": True, "status": "input_error", "error": str(error)})
        return 2
    print_report(report)
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
