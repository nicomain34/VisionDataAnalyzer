"""Schema, statistics, grouping, correlation, spec limits."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

from distribution_engine import (
    FileInfo,
    calculate_stats,
    outlier_mask_iqr,
)
from schema_engine import (
    classify_column,
    collect_dataset_profile,
    correlation_matrix,
    grouping_suitable,
    spec_limits_result,
)


class ClassifyTests(unittest.TestCase):
    def test_numeric(self):
        self.assertEqual(classify_column("numeric", 40, 100, 0), "numeric")

    def test_categorical(self):
        self.assertEqual(classify_column("text", 4, 100, 0), "categorical")

    def test_identifier(self):
        self.assertEqual(classify_column("text", 95, 100, 0), "identifier")

    def test_empty(self):
        self.assertEqual(classify_column("text", 0, 0, 0), "empty")

    def test_boolean_text(self):
        self.assertEqual(classify_column("text", 2, 20, 18), "boolean")

    def test_datetime(self):
        self.assertEqual(classify_column("date", 10, 10, 0), "datetime")


class GroupingTests(unittest.TestCase):
    def test_categorical_ok(self):
        self.assertTrue(grouping_suitable("categorical", 4, 100))

    def test_numeric_rejected(self):
        self.assertFalse(grouping_suitable("numeric", 4, 100))

    def test_hundreds_of_groups(self):
        self.assertFalse(grouping_suitable("categorical", 200, 1000))

    def test_one_group_still_ok(self):
        self.assertTrue(grouping_suitable("categorical", 1, 50))


class StatsTests(unittest.TestCase):
    def test_empty(self):
        st = calculate_stats(np.array([]))
        self.assertEqual(st["count"], 0)

    def test_one_value(self):
        st = calculate_stats(np.array([3.0]))
        self.assertEqual(st["count"], 1)
        self.assertEqual(st["mean"], 3.0)
        self.assertEqual(st["std"], 0.0)

    def test_all_equal(self):
        st = calculate_stats(np.array([2.0, 2.0, 2.0, 2.0]))
        self.assertEqual(st["iqr"], 0.0)
        self.assertEqual(st["skew"], 0.0)

    def test_nan_inf_excluded(self):
        st = calculate_stats(np.array([1.0, np.nan, np.inf, -np.inf, 3.0]))
        self.assertEqual(st["count"], 2)
        self.assertEqual(st["excluded"], 3)

    def test_iqr_outliers(self):
        vals = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100], dtype=float)
        mask = outlier_mask_iqr(vals)
        self.assertTrue(mask[-1])
        self.assertEqual(int(mask.sum()), 1)

    def test_all_equal_no_outliers(self):
        mask = outlier_mask_iqr(np.array([1.0, 1.0, 1.0, 1.0]))
        self.assertFalse(mask.any())


class SpecTests(unittest.TestCase):
    def test_disabled_when_no_limits(self):
        vals = np.array([0.1, 0.2, 0.3])
        st = calculate_stats(vals)
        self.assertFalse(spec_limits_result(st, vals, None, None).get("enabled"))

    def test_pass_fail(self):
        vals = np.array([-2.0, 0.0, 0.5, 2.0])
        st = calculate_stats(vals)
        r = spec_limits_result(st, vals, -1.0, 1.0)
        self.assertTrue(r["enabled"])
        self.assertEqual(r["below_lsl"], 1)
        self.assertEqual(r["above_usl"], 1)
        self.assertEqual(r["out_spec"], 2)


class DatasetTests(unittest.TestCase):
    def test_mixed_schemas_and_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.csv")
            b = os.path.join(tmp, "b.csv")
            bad = os.path.join(tmp, "bad.csv")
            pd.DataFrame(
                {
                    "Camera": ["C1", "C2", "C1"],
                    "ALIGN_LEAD_FR_YA": [0.1, 0.2, 0.3],
                    "ALIGN_LEAD_RE_YA": [0.2, 0.1, 0.4],
                }
            ).to_csv(a, index=False)
            pd.DataFrame(
                {
                    "Station": ["S1", "S1", "S2"],
                    "ALIGN_LEAD_FR_YA": [0.4, 0.5, "x"],
                    "Timestamp": ["2024-01-01 10:00", "2024-01-01 11:00", "2024-01-01 12:00"],
                }
            ).to_csv(b, index=False)
            with open(bad, "wb") as f:
                f.write(b"\x00\x01not,a,csv")
            files = [
                FileInfo(path=a, size=os.path.getsize(a)),
                FileInfo(path=b, size=os.path.getsize(b)),
                FileInfo(path=bad, size=os.path.getsize(bad)),
            ]
            profile = collect_dataset_profile(files)
            self.assertGreaterEqual(profile["files_scanned"], 3)
            names = {c["name"] for c in profile["columns"]}
            self.assertIn("ALIGN_LEAD_FR_YA", names)
            self.assertIn("Camera", names)
            cam = next(c for c in profile["columns"] if c["name"] == "Camera")
            self.assertLess(cam["file_count"], profile["files_scanned"])
            self.assertTrue(grouping_suitable(cam["col_type"], cam["unique_approx"], cam["sample_rows"] - cam["missing"]))
            fr = next(c for c in profile["columns"] if c["name"] == "ALIGN_LEAD_FR_YA")
            self.assertFalse(fr["grouping_suitable"])
            corr = correlation_matrix(files, columns=["ALIGN_LEAD_FR_YA", "ALIGN_LEAD_RE_YA"])
            self.assertIn("columns", corr)


if __name__ == "__main__":
    unittest.main()
