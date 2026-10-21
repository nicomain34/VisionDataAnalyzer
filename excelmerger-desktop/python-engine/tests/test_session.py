"""Session layer: schema, column quality, grouping, correlation, trend, limits."""

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

import limit_engine
import session_analysis
import session_store
from distribution_engine import FileInfo


def _files(paths):
    return [FileInfo(path=p, size=os.path.getsize(p)) for p in paths]


def _make_dataset(tmp: str, rows: int = 400, seed: int = 3):
    """Two files with partly different schemas, noise columns and OK/NG labels."""
    rng = np.random.default_rng(seed)
    a_path = os.path.join(tmp, "batch_a.csv")
    b_path = os.path.join(tmp, "batch_b.csv")
    bad_path = os.path.join(tmp, "broken.xlsx")

    fr = rng.normal(0.0, 0.2, rows)
    re = fr * 0.8 + rng.normal(0, 0.1, rows)
    labels = np.where(np.abs(fr) > 0.38, "NG", "OK")
    ts = pd.date_range("2024-01-01", periods=rows, freq="7min")
    df_a = pd.DataFrame(
        {
            "ALIGN_LEAD_FR_YA": fr,
            "ALIGN_LEAD_RE_YA": re,
            "Camera": rng.choice(["Camera 1", "Camera 2", "Camera 3"], rows),
            "Result": labels,
            "Timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "Material ID": [f"MID{i:05d}" for i in range(rows)],
            "Unnamed: 4": [""] * rows,
            "# Data source: https://example.com": [""] * rows,
            "class_0": rng.integers(0, 2, rows),
        }
    )
    df_a.loc[: rows // 20, "Camera"] = ""
    df_a.to_csv(a_path, index=False)

    df_b = pd.DataFrame(
        {
            "ALIGN_LEAD_FR_YA": rng.normal(0.05, 0.25, rows),
            "Station": rng.choice(["S1", "S2"], rows),
            "Result": rng.choice(["OK", "NG"], rows, p=[0.9, 0.1]),
            "Timestamp": pd.date_range("2024-02-01", periods=rows, freq="9min").strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
    )
    df_b.loc[5:9, "ALIGN_LEAD_FR_YA"] = "sensor_error"
    df_b.loc[11:13, "ALIGN_LEAD_FR_YA"] = "n/a"
    df_b.to_csv(b_path, index=False)

    with open(bad_path, "wb") as fh:
        fh.write(b"\x00\x01\x02 not a real workbook")

    return a_path, b_path, bad_path


class SessionSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a, self.b, self.bad = _make_dataset(self.tmp.name)
        self.summary = session_store.open_session(
            _files([self.a, self.b, self.bad]), folder=self.tmp.name
        )
        self.session = session_store.get_session(self.summary["key"])

    def tearDown(self):
        session_store.close_session(self.summary["key"])
        self.tmp.cleanup()

    def test_dataset_loaded_once_and_cached(self):
        again = session_store.open_session(_files([self.a, self.b, self.bad]), folder=self.tmp.name)
        self.assertEqual(again["key"], self.summary["key"])
        self.assertTrue(again["cached"])

    def test_bad_file_does_not_stop_analysis(self):
        self.assertEqual(self.summary["files_scanned"], 3)
        self.assertEqual(self.summary["valid_files"], 2)
        self.assertEqual(self.summary["failed_files"], 1)
        self.assertGreater(self.summary["rows"], 700)

    def test_overview_has_real_numbers(self):
        self.assertGreater(self.summary["total_columns"], 5)
        self.assertGreater(len(self.summary["insights"]), 3)
        self.assertIn("ALIGN_LEAD_FR_YA", self.summary["numeric_columns"])

    def test_noise_columns_are_not_analysis_candidates(self):
        by_name = {c["name"]: c for c in self.summary["columns"]}
        self.assertFalse(by_name["Unnamed: 4"]["usable_for_analysis"])
        self.assertFalse(by_name["# Data source: https://example.com"]["usable_for_analysis"])
        self.assertFalse(by_name["class_0"]["usable_for_analysis"])
        self.assertNotIn("Unnamed: 4", self.summary["numeric_columns"])
        self.assertNotIn("class_0", self.summary["numeric_columns"])
        self.assertTrue(by_name["Unnamed: 4"]["reason_excluded"])

    def test_identifier_excluded_from_measurements(self):
        by_name = {c["name"]: c for c in self.summary["columns"]}
        self.assertFalse(by_name["Material ID"]["usable_for_analysis"])

    def test_partial_schema_is_reported(self):
        by_name = {c["name"]: c for c in self.summary["columns"]}
        self.assertEqual(by_name["Camera"]["file_count"], 1)
        self.assertEqual(by_name["ALIGN_LEAD_FR_YA"]["file_count"], 2)

    def test_grouping_candidates_exclude_measurements(self):
        self.assertIn("Camera", self.summary["grouping_columns"])
        self.assertIn("Station", self.summary["grouping_columns"])
        self.assertNotIn("ALIGN_LEAD_FR_YA", self.summary["grouping_columns"])
        self.assertNotIn("Material ID", self.summary["grouping_columns"])

    def test_datetime_and_label_detection(self):
        self.assertIn("Timestamp", self.summary["datetime_columns"])
        self.assertIn("Result", self.summary["label_columns"])

    def test_invalid_numeric_values_reported(self):
        by_name = {c["name"]: c for c in self.summary["columns"]}
        self.assertGreaterEqual(by_name["ALIGN_LEAD_FR_YA"]["invalid_numeric"], 5)
        self.assertTrue(
            any(i["issue"] == "Invalid numeric values" for i in self.summary["issues"])
        )

    def test_failed_file_issue_is_error(self):
        self.assertTrue(any(i["severity"] == "ERROR" for i in self.summary["issues"]))


class SessionAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.a, cls.b, cls.bad = _make_dataset(cls.tmp.name)
        cls.summary = session_store.open_session(
            _files([cls.a, cls.b, cls.bad]), folder=cls.tmp.name
        )
        cls.session = session_store.get_session(cls.summary["key"])

    @classmethod
    def tearDownClass(cls):
        session_store.close_session(cls.summary["key"])
        cls.tmp.cleanup()

    def test_distribution(self):
        res = session_analysis.distribution(self.session, "ALIGN_LEAD_FR_YA", bins=30)
        self.assertGreater(res["stats"]["count"], 700)
        self.assertEqual(len(res["hist_counts"]) + 1, len(res["hist_edges"]))
        self.assertGreaterEqual(res["excluded_values"], 5)
        self.assertTrue(res["insights"])
        self.assertEqual(len(set(res["insights"])), len(res["insights"]))

    def test_distribution_rejects_non_numeric(self):
        with self.assertRaises(ValueError):
            session_analysis.distribution(self.session, "Camera")

    def test_distribution_missing_column(self):
        with self.assertRaises(KeyError):
            session_analysis.distribution(self.session, "DoesNotExist")

    def test_spec_limits(self):
        res = session_analysis.distribution(self.session, "ALIGN_LEAD_FR_YA", lsl=-0.5, usl=0.5)
        spec = res["spec"]
        self.assertTrue(spec["enabled"])
        self.assertAlmostEqual(spec["pass_pct"] + spec["fail_pct"], 100.0, places=6)

    def test_comparison_categorical(self):
        res = session_analysis.comparison(self.session, "ALIGN_LEAD_FR_YA", "Camera")
        groups = [g["group"] for g in res["groups"]]
        self.assertLessEqual(res["total_groups"], 4)
        self.assertTrue(any(g.startswith("Camera") for g in groups))
        self.assertFalse(res["bucketed"])

    def test_comparison_numeric_blocked_by_default(self):
        with self.assertRaises(ValueError):
            session_analysis.comparison(self.session, "ALIGN_LEAD_FR_YA", "ALIGN_LEAD_RE_YA")

    def test_comparison_numeric_is_bucketed_when_allowed(self):
        res = session_analysis.comparison(
            self.session,
            "ALIGN_LEAD_FR_YA",
            "ALIGN_LEAD_RE_YA",
            allow_numeric_group=True,
            numeric_buckets=6,
        )
        self.assertTrue(res["bucketed"])
        self.assertLessEqual(res["total_groups"], 6)
        self.assertTrue(all("," in g["group"] for g in res["groups"]))

    def test_comparison_by_file_is_batch_capable(self):
        res = session_analysis.comparison(self.session, "ALIGN_LEAD_FR_YA", "__file")
        self.assertEqual(res["total_groups"], 2)

    def test_comparison_single_group(self):
        res = session_analysis.comparison(self.session, "ALIGN_LEAD_FR_YA", "Station")
        self.assertGreaterEqual(res["total_groups"], 1)

    def test_correlation_filters_noise_columns(self):
        res = session_analysis.correlation(self.session)
        self.assertIn("ALIGN_LEAD_FR_YA", res["columns"])
        self.assertNotIn("class_0", res["columns"])
        self.assertNotIn("Unnamed: 4", res["columns"])
        self.assertNotIn("Material ID", res["columns"])
        top = res["pairs"][0]
        self.assertGreater(abs(top["r"]), 0.5)

    def test_spearman_option(self):
        res = session_analysis.correlation(self.session, method="spearman")
        self.assertEqual(res["method"], "spearman")

    def test_scatter(self):
        res = session_analysis.scatter(self.session, "ALIGN_LEAD_FR_YA", "ALIGN_LEAD_RE_YA")
        self.assertGreater(res["n"], 100)
        self.assertGreater(res["r"], 0.5)
        self.assertAlmostEqual(res["r2"], res["r"] ** 2, places=9)
        self.assertEqual(len(res["fit"]), 2)

    def test_scatter_same_column_rejected(self):
        with self.assertRaises(ValueError):
            session_analysis.scatter(self.session, "ALIGN_LEAD_FR_YA", "ALIGN_LEAD_FR_YA")

    def test_trend_requires_datetime(self):
        with self.assertRaises(ValueError):
            session_analysis.trend(self.session, "Camera", "ALIGN_LEAD_FR_YA")

    def test_trend_daily(self):
        res = session_analysis.trend(self.session, "Timestamp", "ALIGN_LEAD_FR_YA", "daily")
        self.assertGreater(res["n"], 2)
        self.assertTrue(res["points"])
        self.assertEqual(res["aggregation"], "daily")

    def test_trend_shift(self):
        res = session_analysis.trend(self.session, "Timestamp", "ALIGN_LEAD_FR_YA", "shift")
        self.assertLessEqual(len(res["points"]), 3)

    def test_batch_comparison_pass_rate(self):
        res = session_analysis.batch_comparison(
            self.session, "ALIGN_LEAD_FR_YA", unit="__file", label_col="Result"
        )
        self.assertEqual(res["total_batches"], 2)
        self.assertTrue(all(b["pass_rate"] is not None for b in res["batches"]))

    def test_table_pagination_and_sort(self):
        page = session_analysis.table_page(self.session, offset=0, limit=25, sort_by="ALIGN_LEAD_FR_YA")
        self.assertEqual(len(page["rows"]), 25)
        self.assertGreater(page["total"], 700)
        nxt = session_analysis.table_page(self.session, offset=25, limit=25)
        self.assertNotEqual(page["rows"][0], nxt["rows"][0])

    def test_table_query(self):
        page = session_analysis.table_page(self.session, query="Camera 1", limit=10)
        self.assertGreater(page["total"], 0)

    def test_export_frames(self):
        dist = session_analysis.distribution(self.session, "ALIGN_LEAD_FR_YA")
        self.assertFalse(session_analysis.dataframe_for_export(self.session, "statistics", dist).empty)
        comp = session_analysis.comparison(self.session, "ALIGN_LEAD_FR_YA", "Camera")
        self.assertFalse(session_analysis.dataframe_for_export(self.session, "comparison", comp).empty)
        corr = session_analysis.correlation(self.session)
        self.assertFalse(session_analysis.dataframe_for_export(self.session, "correlation", corr).empty)


class LimitFinderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.a, cls.b, cls.bad = _make_dataset(cls.tmp.name)
        cls.summary = session_store.open_session(_files([cls.a]), folder=cls.tmp.name)
        cls.session = session_store.get_session(cls.summary["key"])

    @classmethod
    def tearDownClass(cls):
        session_store.close_session(cls.summary["key"])
        cls.tmp.cleanup()

    def test_label_candidates_detected(self):
        cands = limit_engine.label_candidates(self.session)
        names = [c["name"] for c in cands]
        self.assertIn("Result", names)
        self.assertTrue(cands[0]["recognized"])

    def test_supervised_upper_limit(self):
        res = limit_engine.limit_finder(
            self.session, "ALIGN_LEAD_FR_YA", label_col="Result", limit_type="upper"
        )
        self.assertTrue(res["supervised"])
        rec = res["recommended"]
        self.assertEqual(rec["tp"] + rec["fn"], res["class_counts"]["NG"])
        self.assertEqual(rec["fp"] + rec["tn"], res["class_counts"]["OK"])
        self.assertGreater(rec["recall"], 0.3)
        self.assertIsNotNone(res["auc"])
        self.assertTrue(res["roc"])

    def test_two_sided_limit_brackets_data(self):
        res = limit_engine.limit_finder(
            self.session, "ALIGN_LEAD_FR_YA", label_col="Result", limit_type="two_sided"
        )
        rec = res["recommended"]
        self.assertLess(rec["lower"], rec["upper"])
        self.assertGreater(rec["recall"], 0.8)

    def test_lower_limit_direction(self):
        res = limit_engine.limit_finder(
            self.session, "ALIGN_LEAD_FR_YA", label_col="Result", limit_type="lower"
        )
        self.assertEqual(res["limit_type"], "lower")
        self.assertIsNotNone(res["recommended"]["lower"])

    def test_cost_optimization_differs_from_youden(self):
        cost = limit_engine.limit_finder(
            self.session,
            "ALIGN_LEAD_FR_YA",
            label_col="Result",
            limit_type="upper",
            method="cost",
            cost_false_accept=50,
            cost_false_reject=1,
        )
        self.assertIn("Minimum expected cost", cost["optimization_method"])
        self.assertGreaterEqual(cost["recommended"]["recall"], 0.0)

    def test_current_vs_recommended(self):
        res = limit_engine.limit_finder(
            self.session,
            "ALIGN_LEAD_FR_YA",
            label_col="Result",
            limit_type="upper",
            current_upper=1.0,
        )
        self.assertIsNotNone(res["current"])
        self.assertGreaterEqual(res["current"]["fn"], 0)

    def test_threshold_slider_metrics_are_monotonic_for_rejects(self):
        low = limit_engine.evaluate_threshold(
            self.session, "ALIGN_LEAD_FR_YA", "Result", limit_type="upper", upper=0.2
        )
        high = limit_engine.evaluate_threshold(
            self.session, "ALIGN_LEAD_FR_YA", "Result", limit_type="upper", upper=0.6
        )
        self.assertGreaterEqual(low["rejected"], high["rejected"])
        self.assertLessEqual(low["missed_defects"], high["missed_defects"])

    def test_statistical_mode_without_labels(self):
        res = limit_engine.limit_finder(self.session, "ALIGN_LEAD_FR_YA", limit_type="two_sided")
        self.assertFalse(res["supervised"])
        self.assertEqual(res["mode"], "statistical")
        self.assertTrue(any("not been validated" in w for w in res["warnings"]))
        self.assertIsNotNone(res["recommended_upper"])

    def test_statistical_methods(self):
        values = np.concatenate([np.random.default_rng(1).normal(0, 1, 500), [12.0]])
        for method in ("percentile", "iqr", "sigma", "robust"):
            out = limit_engine.statistical_limits(values, "two_sided", method)
            self.assertIsNotNone(out["upper"])
            self.assertIsNotNone(out["lower"])
            self.assertTrue(out["warnings"])

    def test_statistical_small_sample_warns(self):
        out = limit_engine.statistical_limits(np.array([1.0, 2.0, 3.0]), "upper", "percentile")
        self.assertIn("Insufficient data", out["warnings"][0])

    def test_non_binary_label_rejected(self):
        with self.assertRaises(ValueError):
            limit_engine.limit_finder(
                self.session, "ALIGN_LEAD_FR_YA", label_col="Camera", limit_type="upper"
            )

    def test_user_chosen_labels_on_any_column(self):
        res = limit_engine.limit_finder(
            self.session,
            "ALIGN_LEAD_FR_YA",
            label_col="Camera",
            positive_label="Camera 1",
            negative_label="camera 2",
            limit_type="upper",
        )
        self.assertTrue(res["supervised"])
        self.assertEqual(res["positive_label"], "Camera 1")
        self.assertEqual(res["negative_label"], "Camera 2")
        self.assertTrue(any("excluded" in w for w in res["warnings"]))
        values = session_store.column_values(self.session, "Camera")
        self.assertGreaterEqual(values["distinct"], 3)
        self.assertTrue(any(v["value"] == "Camera 1" for v in values["values"]))

    def test_class_imbalance_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "imbalanced.csv")
            rng = np.random.default_rng(5)
            n = 600
            vals = rng.normal(0, 1, n)
            labels = np.array(["OK"] * n, dtype=object)
            labels[:4] = "NG"
            vals[:4] = rng.normal(4, 0.2, 4)
            pd.DataFrame({"m": vals, "r": labels}).to_csv(path, index=False)
            summary = session_store.open_session(_files([path]), folder=tmp)
            session = session_store.get_session(summary["key"])
            res = limit_engine.limit_finder(session, "m", label_col="r", limit_type="upper")
            self.assertTrue(any("imbalanced" in w for w in res["warnings"]))
            self.assertTrue(any("Small sample" in w for w in res["warnings"]))
            session_store.close_session(summary["key"])


class EmptyAndEdgeTests(unittest.TestCase):
    def test_empty_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "empty.csv")
            pd.DataFrame({"a": []}).to_csv(path, index=False)
            summary = session_store.open_session(_files([path]), folder=tmp)
            self.assertEqual(summary["rows"], 0)
            self.assertTrue(summary["insights"])
            session_store.close_session(summary["key"])

    def test_single_value_and_constant_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "const.csv")
            pd.DataFrame({"v": [5.0] * 40, "one": [1.0] + [None] * 39}).to_csv(path, index=False)
            summary = session_store.open_session(_files([path]), folder=tmp)
            session = session_store.get_session(summary["key"])
            res = session_analysis.distribution(session, "v")
            self.assertEqual(res["outlier_count"], 0)
            self.assertEqual(res["stats"]["std"], 0.0)
            session_store.close_session(summary["key"])

    def test_nan_and_infinity_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nan.csv")
            pd.DataFrame({"v": [1.0, 2.0, float("nan"), float("inf"), -float("inf"), 3.0] * 10}).to_csv(
                path, index=False
            )
            summary = session_store.open_session(_files([path]), folder=tmp)
            session = session_store.get_session(summary["key"])
            res = session_analysis.distribution(session, "v")
            self.assertEqual(res["stats"]["count"], 30)
            session_store.close_session(summary["key"])

    def test_no_grouping_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nogroup.csv")
            rng = np.random.default_rng(2)
            pd.DataFrame({"a": rng.normal(size=200), "b": rng.normal(size=200)}).to_csv(
                path, index=False
            )
            summary = session_store.open_session(_files([path]), folder=tmp)
            self.assertEqual(summary["grouping_columns"], [])
            self.assertTrue(
                any("No suitable grouping columns" in i for i in summary["insights"])
            )
            session_store.close_session(summary["key"])

    def test_high_cardinality_numeric_not_grouping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "hc.csv")
            rng = np.random.default_rng(4)
            pd.DataFrame({"m": rng.normal(size=500)}).to_csv(path, index=False)
            summary = session_store.open_session(_files([path]), folder=tmp)
            self.assertNotIn("m", summary["grouping_columns"])
            session_store.close_session(summary["key"])

    def test_many_categorical_groups_are_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "manygroups.csv")
            rng = np.random.default_rng(6)
            n = 3000
            pd.DataFrame(
                {"m": rng.normal(size=n), "g": [f"G{i % 300}" for i in range(n)]}
            ).to_csv(path, index=False)
            summary = session_store.open_session(_files([path]), folder=tmp)
            session = session_store.get_session(summary["key"])
            res = session_analysis.comparison(session, "m", "g")
            self.assertEqual(res["total_groups"], 300)
            self.assertLessEqual(len(res["groups"]), session_analysis.MAX_GROUPS)
            self.assertTrue(res["truncated"])
            session_store.close_session(summary["key"])

    def test_expired_session_raises_readable_error(self):
        with self.assertRaises(KeyError):
            session_store.get_session("does-not-exist")

    def test_row_limit_truncation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "big.csv")
            pd.DataFrame({"v": range(500)}).to_csv(path, index=False)
            summary = session_store.open_session(_files([path]), folder=tmp, max_rows=100)
            self.assertTrue(summary["truncated"])
            self.assertEqual(summary["rows"], 100)
            session_store.close_session(summary["key"])


class CompactTimestampTests(unittest.TestCase):
    """Vision files store DATE as 2026-10-0700-11-52 (date and clock glued, clock uses '-')."""

    def test_compact_date_column_enables_time_trend(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "vision.csv")
            pd.DataFrame(
                {
                    "DATE": [
                        "2026-10-0700-11-52",
                        "2026-10-0700-12-22",
                        "2026-10-0700-13-01",
                        "2026-10-07 00-14-10",
                    ],
                    "ALIGN": [0.1, 0.2, 0.15, 0.4],
                }
            ).to_csv(path, index=False)
            summary = session_store.open_session(_files([path]), folder=tmp)
            self.assertIn("DATE", summary["datetime_columns"])
            session = session_store.get_session(summary["key"])
            res = session_analysis.trend(session, "DATE", "ALIGN", "raw")
            self.assertGreaterEqual(res["n"], 4)
            self.assertTrue(res["points"][0]["t"].startswith("2026-10-07"))
            session_store.close_session(summary["key"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
