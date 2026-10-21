"""Full engineering analysis report built from the state already shown in the UI.

Nothing is recalculated here: every section is rendered from the results stored
in the analysis session.
"""

from __future__ import annotations

import datetime as _dt
import html
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from session_analysis import dataframe_for_export
from session_store import Session

SECTION_ORDER = [
    "dataset",
    "quality",
    "schema",
    "distribution",
    "outliers",
    "comparison",
    "correlation",
    "scatter",
    "trend",
    "batch",
    "limit",
]

SECTION_TITLES = {
    "dataset": "Dataset information",
    "quality": "Data quality",
    "schema": "Detected schema",
    "distribution": "Distribution statistics",
    "outliers": "Outliers",
    "comparison": "Group comparison",
    "correlation": "Correlation",
    "scatter": "Scatter / regression",
    "trend": "Time trend",
    "batch": "Batch / file comparison",
    "limit": "Limit recommendation",
}


def _dataset_table(session: Session) -> pd.DataFrame:
    p = session.profile
    rows = [
        ("Source folder", session.source_folder or "(file selection)"),
        ("Files scanned", p["files_scanned"]),
        ("Valid files", p["valid_files"]),
        ("Failed files", p["failed_files"]),
        ("Rows loaded", p["rows"]),
        ("Rows read", p["total_rows_est"]),
        ("Columns", p["total_columns"]),
        ("Numeric columns", p["type_counts"].get("numeric", 0)),
        ("Categorical columns", p["type_counts"].get("categorical", 0)),
        ("Date/Time columns", p["type_counts"].get("datetime", 0)),
        ("Identifier columns", p["type_counts"].get("identifier", 0)),
        ("Missing values", p["missing_values"]),
        ("Missing %", round(p["missing_pct"], 3)),
        ("Duplicate rows", p["duplicate_rows"]),
        ("Duplicate %", round(p["duplicate_pct"], 3)),
        ("Invalid values", p["invalid_values"]),
        ("Empty columns", p["empty_columns"]),
        ("Mixed-type columns", p["mixed_columns"]),
        ("Row limit reached", "yes" if p.get("truncated") else "no"),
        ("Report generated", _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def _limit_tables(payload: Dict[str, Any]) -> List[tuple]:
    out: List[tuple] = []
    summary_rows = [
        ("Mode", "Supervised (OK/NG labels)" if payload.get("supervised") else "Statistical only"),
        ("Measurement", payload.get("measurement")),
        ("Label column", payload.get("label_col") or "—"),
        ("Limit type", payload.get("limit_type")),
        ("Optimization method", payload.get("optimization_method")),
        ("Recommended lower", payload.get("recommended_lower")),
        ("Recommended upper", payload.get("recommended_upper")),
        ("AUC", payload.get("auc")),
        ("Sample size", payload.get("n")),
    ]
    for k, v in (payload.get("class_counts") or {}).items():
        summary_rows.append((f"Class '{k}'", v))
    out.append(("Limit summary", pd.DataFrame(summary_rows, columns=["metric", "value"])))

    rec = payload.get("recommended") or {}
    cur = payload.get("current") or {}
    if rec:
        metrics = ["tp", "fp", "fn", "tn", "precision", "recall", "specificity", "f1", "yield",
                   "false_accept_rate", "false_reject_rate", "youden", "cost"]
        cmp_rows = [
            {"metric": m, "recommended": rec.get(m), "current": cur.get(m) if cur else None}
            for m in metrics
        ]
        out.append(("Confusion / performance", pd.DataFrame(cmp_rows)))
    if payload.get("thresholds"):
        out.append(("Threshold analysis", pd.DataFrame(payload["thresholds"])))
    if payload.get("roc"):
        out.append(("ROC curve", pd.DataFrame(payload["roc"])))
    boundary = payload.get("boundary") or {}
    if boundary.get("edges"):
        edges = boundary["edges"]
        out.append(
            (
                "Defect boundary",
                pd.DataFrame(
                    {
                        "bin_start": edges[:-1],
                        "bin_end": edges[1:],
                        "ok_count": boundary.get("ok") or [],
                        "ng_count": boundary.get("ng") or [],
                    }
                ),
            )
        )
    stat = payload.get("statistical") or {}
    if stat:
        out.append(
            (
                "Statistical limits",
                pd.DataFrame(
                    [
                        ("Method", stat.get("basis") or stat.get("method")),
                        ("Lower", stat.get("lower")),
                        ("Upper", stat.get("upper")),
                        ("Out of limits", stat.get("out_of_limits")),
                        ("Out of limits %", stat.get("out_of_limits_pct")),
                    ],
                    columns=["metric", "value"],
                ),
            )
        )
    return out


def _section_tables(session: Session, section: str) -> List[tuple]:
    payload = session.results.get(section)
    if section == "dataset":
        return [("Dataset", _dataset_table(session))]
    if section == "quality":
        return [("Issues", pd.DataFrame(session.profile.get("issues") or []))]
    if section == "schema":
        return [("Columns", pd.DataFrame(session.profile.get("columns") or []))]
    if payload is None:
        return []
    if section == "limit":
        return _limit_tables(payload)
    if section == "distribution":
        tables = [("Statistics", dataframe_for_export(session, "statistics", payload))]
        hist = payload.get("hist_counts") or []
        edges = payload.get("hist_edges") or []
        if hist and len(edges) == len(hist) + 1:
            tables.append(
                (
                    "Histogram",
                    pd.DataFrame(
                        {"bin_start": edges[:-1], "bin_end": edges[1:], "count": hist}
                    ),
                )
            )
        spec = payload.get("spec") or {}
        if spec.get("enabled"):
            tables.append(
                (
                    "Specification",
                    pd.DataFrame([{k: v for k, v in spec.items() if k != "enabled"}]),
                )
            )
        return tables
    if section == "outliers":
        return [("Outliers", dataframe_for_export(session, "outliers", session.results.get("distribution") or {}))]
    df = dataframe_for_export(session, section, payload)
    return [(SECTION_TITLES.get(section, section), df)] if not df.empty else []


def _insights(session: Session, sections: Sequence[str]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for line in session.profile.get("insights") or []:
        rows.append({"section": "Dataset", "insight": line})
    for section in sections:
        payload = session.results.get(section)
        if not payload:
            continue
        for line in payload.get("insights") or []:
            rows.append({"section": SECTION_TITLES.get(section, section), "insight": line})
        for line in payload.get("warnings") or []:
            rows.append({"section": SECTION_TITLES.get(section, section), "insight": f"Warning: {line}"})
    if session.profile.get("truncated"):
        rows.append(
            {
                "section": "Limitations",
                "insight": "The configured row limit was reached; results describe the loaded subset.",
            }
        )
    return pd.DataFrame(rows)


def _sheet_name(base: str, used: set) -> str:
    name = base[:28].replace("/", "-").replace("\\", "-").replace(":", "-")
    candidate = name or "Sheet"
    i = 2
    while candidate.lower() in used:
        candidate = f"{name[:25]}_{i}"
        i += 1
    used.add(candidate.lower())
    return candidate


def _cell(value: Any) -> str:
    """Cell text for any payload value, including list-valued schema fields."""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value)


def _html_table(df: pd.DataFrame, limit: int = 400) -> str:
    view = df.head(limit)
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in view.columns)
    body = ""
    for _, row in view.iterrows():
        cells = "".join(f"<td>{html.escape(_cell(v))}</td>" for v in row.tolist())
        body += f"<tr>{cells}</tr>"
    more = (
        f"<p class='note'>Showing first {limit} of {len(df)} rows.</p>" if len(df) > limit else ""
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>{more}"


def write_report(
    session: Session,
    path: str,
    fmt: str = "xlsx",
    sections: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    if not path:
        return {"ok": False, "error": "No output path was provided."}
    wanted = [s for s in (sections or SECTION_ORDER) if s in SECTION_ORDER]
    if not wanted:
        wanted = list(SECTION_ORDER)
    analysis_sections = [s for s in wanted if s not in ("dataset", "quality", "schema")]
    fmt = (fmt or "xlsx").lower()

    collected: List[tuple] = []
    for section in wanted:
        for title, df in _section_tables(session, section):
            if df is not None and not df.empty:
                collected.append((SECTION_TITLES.get(section, section), title, df))
    insights = _insights(session, analysis_sections)

    try:
        if fmt == "html":
            if not path.lower().endswith(".html"):
                path += ".html"
            parts = [
                "<!doctype html><html><head><meta charset='utf-8'>",
                "<title>ExcelMerger analysis report</title>",
                "<style>",
                "body{font-family:Segoe UI,Arial,sans-serif;background:#fff;color:#111;margin:32px;}",
                "h1{font-size:20px;} h2{font-size:15px;margin-top:26px;border-bottom:1px solid #ccc;padding-bottom:4px;}",
                "h3{font-size:13px;color:#333;margin:14px 0 6px;}",
                "table{border-collapse:collapse;font-size:11px;margin-bottom:10px;}",
                "th,td{border:1px solid #d0d0d0;padding:3px 6px;text-align:left;}",
                "th{background:#f1f3f6;} .note{font-size:11px;color:#666;}",
                "li{font-size:12px;margin-bottom:3px;}",
                "@media print{body{margin:12px;}}",
                "</style></head><body>",
                "<h1>ExcelMerger — engineering analysis report</h1>",
                f"<p class='note'>Generated {_dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
                f"{html.escape(session.source_folder or 'file selection')}</p>",
            ]
            last_section = ""
            for section_title, table_title, df in collected:
                if section_title != last_section:
                    parts.append(f"<h2>{html.escape(section_title)}</h2>")
                    last_section = section_title
                parts.append(f"<h3>{html.escape(table_title)}</h3>")
                parts.append(_html_table(df))
            if not insights.empty:
                parts.append("<h2>Engineering insights &amp; limitations</h2><ul>")
                for _, row in insights.iterrows():
                    parts.append(
                        f"<li><b>{html.escape(str(row['section']))}:</b> {html.escape(str(row['insight']))}</li>"
                    )
                parts.append("</ul>")
            parts.append(
                "<p class='note'>Charts are available interactively in the application. "
                "Use the browser/Windows print dialog to save this report as PDF.</p>"
            )
            parts.append("</body></html>")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("".join(parts))
            return {"ok": True, "path": path, "sections": len(collected), "format": "html"}

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        used: set = set()
        with pd.ExcelWriter(path) as writer:
            for section_title, table_title, df in collected:
                sheet = _sheet_name(f"{section_title[:12]}-{table_title}", used)
                df.to_excel(writer, sheet_name=sheet, index=False)
            if not insights.empty:
                insights.to_excel(writer, sheet_name=_sheet_name("Insights", used), index=False)
        return {"ok": True, "path": path, "sections": len(collected), "format": "xlsx"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
