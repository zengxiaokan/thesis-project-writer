"""Check published chart data against the actual observation, without a plotting dependency."""
import csv
import json
from pathlib import Path
import runpy
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = runpy.run_path(str(ROOT / "examples/figures/render_chart.py"))


class FigureDataTests(unittest.TestCase):
    def test_published_chart_data_matches_observed_counts(self):
        observation = ROOT / "examples/initialization-study/observation.json"
        _, expected = EXAMPLE["load_counts"](observation)
        with (ROOT / "examples/figures/source_data.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        actual = [(row["configuration"], row["label"], row["observation_key"], int(row["created_files"]))
                  for row in rows]
        self.assertEqual(actual, expected)

    def test_invalid_observed_numbers_are_rejected_instead_of_plotted(self):
        original = json.loads((ROOT / "examples/initialization-study/observation.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="thesis-chart-input-") as temporary:
            path = Path(temporary).resolve() / "observation.json"
            for value in (True, -1, 1.5, "10", None):
                with self.subTest(value=value):
                    original["observations"]["analysis_created_files"] = value
                    path.write_text(json.dumps(original), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        EXAMPLE["load_counts"](path)
