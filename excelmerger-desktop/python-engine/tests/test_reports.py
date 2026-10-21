"""Report writing and JSON-RPC dispatch over a live analysis session."""

from __future__ import annotations

import os
import sys
import shutil
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd

import main as engine_main
import session_store
from report_builder import write_report
from test_session import _make_dataset


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.a, self.b, self.bad = _make_dataset(self.tmp.name, rows=200)
        self.key = engine_main.handle(
            "session_open", {"files": [self.a, self.b, self.bad], "folder": self.tmp.name}
        )["key"]

    def tearDown(self):
        session_store.close_session(self.key)
        self.tmp.cleanup()

    def _out(self, name: str) -> str:
        return os.path.join(self.tmp.name, name)

    @staticmethod
    def _sheets(path: str):
        with pd.ExcelFile(path) as xl:
            return list(xl.sheet_names)

    def test_report_without_analyses_has_dataset_sections(self):
        session = session_store.get_session(self.key)
        path = self._out("report-min.xlsx")
        res = write_report(session, path=path, fmt="xlsx")
        self.assertTrue(res["ok"], res)
        self.assertTrue(os.path.exists(path))
        sheets = self._sheets(path)
        self.assertTrue(any("Dataset" in s for s in sheets), sheets)

    def test_report_uses_stored_results_without_recalculating(self):
        engine_main.handle(
            "session_distribution", {"key": self.key, "column": "ALIGN_LEAD_FR_YA"}
        )
        session = session_store.get_session(self.key)
        # Corrupt the stored mean: the report must echo state, not recompute it.
        session.results["distribution"]["stats"]["mean"] = 12345.6789
        path = self._out("report-state.xlsx")
        self.assertTrue(write_report(session, path=path, fmt="xlsx")["ok"])
        frames = pd.read_excel(path, sheet_name=None)
        text = "".join(f.to_string() for f in frames.values())
        self.assertIn("12345.6789", text)

    def test_html_report_is_self_contained(self):
        engine_main.handle("session_correlation", {"key": self.key})
        session = session_store.get_session(self.key)
        path = self._out("report.html")
        res = write_report(session, path=path, fmt="html")
        self.assertTrue(res["ok"], res)
        html = open(path, encoding="utf-8").read()
        self.assertIn("<html", html.lower())
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("http://", html.replace("https://", ""))

    def test_section_selection_is_respected(self):
        session = session_store.get_session(self.key)
        path = self._out("report-sections.xlsx")
        write_report(session, path=path, fmt="xlsx", sections=["quality"])
        sheets = self._sheets(path)
        self.assertTrue(all("Distribution" not in s for s in sheets), sheets)


class DispatchTests(unittest.TestCase):
    """Every analysis reachable from the UI goes through handle()."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        cls.a, cls.b, cls.bad = _make_dataset(cls.dir, rows=240)
        cls.key = engine_main.handle(
            "session_open", {"files": [cls.a, cls.b, cls.bad], "folder": cls.dir}
        )["key"]

    @classmethod
    def tearDownClass(cls):
        session_store.close_session(cls.key)
        shutil.rmtree(cls.dir, ignore_errors=True)

    def call(self, _method, **params):
        return engine_main.handle(_method, {"key": self.key, **params})

    def test_profile_and_results_tracking(self):
        """A fresh session starts with no results and records each module run."""
        with tempfile.TemporaryDirectory() as tmp:
            a, b, bad = _make_dataset(tmp, rows=120, seed=11)
            key = engine_main.handle("session_open", {"files": [a, b, bad], "folder": tmp})["key"]
            try:
                profile = engine_main.handle("session_profile", {"key": key})
                self.assertGreater(profile["rows"], 0)
                self.assertEqual(engine_main.handle("session_results", {"key": key})["available"], [])
                engine_main.handle(
                    "session_distribution", {"key": key, "column": "ALIGN_LEAD_FR_YA"}
                )
                self.assertEqual(
                    engine_main.handle("session_results", {"key": key})["available"],
                    ["distribution"],
                )
            finally:
                session_store.close_session(key)

    def test_each_module_dispatches(self):
        self.call("session_distribution", column="ALIGN_LEAD_FR_YA")
        self.call("session_comparison", column="ALIGN_LEAD_FR_YA", group_by="Camera")
        self.call("session_correlation", method="spearman")
        self.call("session_scatter", x="ALIGN_LEAD_FR_YA", y="ALIGN_LEAD_RE_YA")
        self.call(
            "session_trend",
            time_col="Timestamp",
            value_col="ALIGN_LEAD_FR_YA",
            aggregation="daily",
        )
        self.call("session_batch", column="ALIGN_LEAD_FR_YA", unit="__file")
        self.call("session_table", offset=0, limit=10)
        limit = self.call(
            "session_limit_finder",
            measurement="ALIGN_LEAD_FR_YA",
            label_col="Result",
            limit_type="upper",
            optimization="youden",
        )
        self.assertTrue(limit["supervised"])
        available = self.call("session_results")["available"]
        for kind in (
            "distribution",
            "comparison",
            "correlation",
            "scatter",
            "trend",
            "batch",
            "table",
            "limit",
        ):
            self.assertIn(kind, available)

    def test_export_requires_a_previous_run(self):
        key = engine_main.handle(
            "session_open", {"files": [self.a], "folder": self.dir}
        )["key"]
        try:
            res = engine_main.handle(
                "session_export",
                {"key": key, "kind": "comparison", "path": os.path.join(self.dir, "x.csv")},
            )
            self.assertFalse(res["ok"])
            self.assertIn("Run the analysis", res["error"])
        finally:
            session_store.close_session(key)

    def test_export_csv_and_xlsx_for_every_module(self):
        self.call("session_distribution", column="ALIGN_LEAD_FR_YA")
        self.call("session_comparison", column="ALIGN_LEAD_FR_YA", group_by="Camera")
        self.call("session_batch", column="ALIGN_LEAD_FR_YA", unit="__file")
        for kind, name in [
            ("statistics", "stats.csv"),
            ("outliers", "out.csv"),
            ("comparison", "cmp.xlsx"),
            ("batch", "batch.xlsx"),
            ("schema", "schema.xlsx"),
            ("quality", "quality.csv"),
        ]:
            path = os.path.join(self.dir, name)
            res = engine_main.handle("session_export", {"key": self.key, "kind": kind, "path": path})
            self.assertTrue(res["ok"], f"{kind}: {res}")
            self.assertTrue(os.path.exists(path), kind)

    def test_expired_session_reports_clear_error(self):
        with self.assertRaises(KeyError):
            engine_main.handle("session_profile", {"key": "does-not-exist"})

    def test_unknown_method_raises(self):
        with self.assertRaises(ValueError):
            engine_main.handle("session_unknown", {"key": self.key})


if __name__ == "__main__":
    unittest.main()
