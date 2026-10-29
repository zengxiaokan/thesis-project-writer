#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render observed initializer file counts; all output paths are explicit."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile


SERIES = (
    ("analysis", "分析记录初始化", "analysis_created_files"),
    ("intake", "访谈记录补建", "intake_created_files"),
    ("software", "软件路径扩展", "upgrade_created_files"),
)


def load_counts(path):
    record = json.loads(path.read_text(encoding="utf-8"))
    values = []
    for profile, label, key in SERIES:
        value = record["observations"][key]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("Expected a non-negative observed integer: " + key)
        values.append((profile, label, key, value))
    return record, values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--png", type=Path, help="Optional local preview; not part of the release example")
    parser.add_argument("--font", help="Installed font family supporting Chinese labels")
    args = parser.parse_args()
    record, values = load_counts(args.observation)
    outputs = [path for path in (args.svg, args.csv, args.png) if path is not None]
    resolved = [path.resolve() for path in outputs]
    if len(set(resolved)) != len(resolved) or args.observation.resolve() in resolved:
        parser.error("Outputs must be distinct and must not replace the observation")
    for path in outputs:
        if not path.parent.is_dir():
            parser.error("Output parent must already exist: " + str(path.parent))

    # The example does not alter the user's Matplotlib settings or permanent cache.
    with tempfile.TemporaryDirectory(prefix="thesis-figure-mpl-") as configuration:
        os.environ.setdefault("MPLCONFIGDIR", configuration)
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import font_manager, pyplot as plt
        from matplotlib.ticker import MaxNLocator

        families = [args.font] if args.font else [
            "Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC",
        ]
        selected = None
        for family in families:
            try:
                font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
            except ValueError:
                continue
            selected = family
            break
        if selected is None:
            parser.error("No requested Chinese font found; supply an installed family with --font")

        plt.rcParams.update({
            "font.family": selected,
            "font.size": 11,
            "axes.unicode_minus": False,
            "svg.fonttype": "path",
            "svg.hashsalt": "thesis-initializer-counts-v1",
        })
        figure, axis = plt.subplots(figsize=(6.8, 3.6), layout="constrained")
        bars = axis.bar([row[1] for row in values], [row[3] for row in values],
                        width=0.54, color=["#dbe2e8", "#aebdca", "#657f95"],
                        edgecolor="#334155", linewidth=0.7)
        axis.set_ylabel("新增文件数（份）")
        axis.set_ylim(0, max(row[3] for row in values) * 1.20 or 1)
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))
        axis.grid(axis="y", color="#e2e8ee", linewidth=0.7)
        axis.set_axisbelow(True)
        axis.spines[["top", "right"]].set_visible(False)
        for bar, row in zip(bars, values):
            axis.annotate(str(row[3]), (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                          xytext=(0, 5), textcoords="offset points", ha="center", va="bottom")
        figure.savefig(args.svg, format="svg", metadata={"Date": None, "Creator": "Thesis Project Writer example"})
        # Matplotlib emits trailing spaces in SVG path data. Normalize the text
        # while retaining newlines as separators, so the checked-in source is clean.
        svg_text = args.svg.read_text(encoding="utf-8")
        with args.svg.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(line.rstrip() for line in svg_text.splitlines()) + "\n")
        if args.png:
            figure.savefig(args.png, format="png", dpi=180)
        plt.close(figure)

    if args.csv:
        with args.csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(("configuration", "label", "observation_key", "created_files"))
            writer.writerows(values)
    print(json.dumps({
        "observation_sha256": hashlib.sha256(args.observation.read_bytes()).hexdigest(),
        "initializer_source_sha256": record["source"]["sha256"],
        "counts": {row[0]: row[3] for row in values},
        "font": selected,
        "svg": str(args.svg),
        "csv": str(args.csv) if args.csv else None,
        "png_preview": str(args.png) if args.png else None,
        "scope": "Observed file additions in one initializer replay; not thesis-stage completion or performance",
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
