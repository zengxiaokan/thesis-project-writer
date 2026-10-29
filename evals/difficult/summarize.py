#!/usr/bin/env python3
"""Validate quoted evidence in pilot ratings, then aggregate the supplied ratings."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def exact_quote(quote, output, label):
    if not quote or quote not in output:
        raise ValueError("Rating quote is absent from output: " + label)


def summarize(root):
    root = Path(root)
    mapping = json.loads((root / "mapping.json").read_text(encoding="utf-8"))
    identities = {entry["anonymous_id"]: entry for entry in mapping}
    if len(identities) != len(mapping):
        raise ValueError("Duplicate anonymous identity")
    rows = []
    seen = set()
    # Original reviewer responses are retained as *.raw.json; only the named
    # case files feed the final aggregate, so raw copies are never double-counted.
    for case in sorted({entry["case"] for entry in mapping}):
        file = root / "grades" / (case + ".json")
        record = json.loads(file.read_text(encoding="utf-8"))
        for grade in record["outputs"]:
            identity = grade["anonymous_id"]
            if identity in seen or identity not in identities:
                raise ValueError("Duplicate or unknown graded output: " + identity)
            seen.add(identity)
            entry = identities[identity]
            if record["case_id"] != entry["case"]:
                raise ValueError("Case identity mismatch: " + identity)
            path = root / "outputs" / (identity + ".md")
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["output_sha256"]:
                raise ValueError("Raw output changed: " + identity)
            output = path.read_text(encoding="utf-8")
            depth = grade["depth"]
            if len(depth) != 6 or {item["id"] for item in depth} != {"D" + str(i) for i in range(1, 7)}:
                raise ValueError("Pilot requires six distinct applicable dimensions: " + identity)
            for item in depth:
                score = item["score"]
                if type(score) is not int or score not in (0, 1, 2):
                    raise ValueError("Invalid depth rating: " + identity)
                if score or item.get("quote"):
                    exact_quote(item.get("quote"), output, identity + "/" + item["id"])
                if not item.get("location"):
                    raise ValueError("Missing output location: " + identity)
            for error in grade["critical_errors"]:
                exact_quote(error.get("quote"), output, identity + "/" + error["id"])
                if not error.get("source"):
                    raise ValueError("Missing conflicting input source: " + identity)
            for issue in grade.get("other_issues", []):
                if isinstance(issue, dict) and issue.get("quote"):
                    exact_quote(issue["quote"], output, identity + "/other_issue")
            rows.append({"anonymous_id": identity, "case": entry["case"],
                         "condition": entry["condition"], "repetition": entry["repetition"],
                         "depth_total": sum(item["score"] for item in depth),
                         "critical_errors": len(grade["critical_errors"]),
                         "other_issues": len(grade.get("other_issues", [])),
                         "complete_chapter": grade["complete_chapter"]})
    if seen != set(identities):
        raise ValueError("Not all raw outputs have been graded")
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["case"], row["condition"])].append(row)
    groups = []
    for (case, condition), values in sorted(grouped.items()):
        scores = [value["depth_total"] for value in values]
        groups.append({"case": case, "condition": condition, "runs": len(values),
                       "depth_mean": statistics.mean(scores), "depth_min": min(scores),
                       "depth_max": max(scores),
                       "runs_with_critical_errors": sum(value["critical_errors"] > 0 for value in values),
                       "other_issues": sum(value["other_issues"] for value in values),
                       "complete_chapters": sum(value["complete_chapter"] for value in values)})
    return {"runs": sorted(rows, key=lambda item: item["anonymous_id"]), "groups": groups,
            "scope": "Aggregates supplied anonymous-agent judgments; quote checks are not semantic or human validation."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.results), ensure_ascii=True, indent=2))
