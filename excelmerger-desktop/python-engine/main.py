"""
ExcelMerger headless engine — JSON lines over stdio.

Request:  {"id":1,"method":"scan_folder","params":{...}}
Response: {"id":1,"result":{...}} or {"id":1,"error":"..."}
Events:   {"event":"progress","method":"scan_folder","done":1,"total":10,"file":"..."}
"""

from __future__ import annotations

import json
import sys
import threading
import traceback
from typing import Any, Dict, Optional

import pandas as pd

from distribution_engine import (
    AnalysisResult,
    detect_schema,
    export_records_df,
    preview_records,
    run_distribution_analysis,
    scan_files,
    format_size,
)
from merge_engine import merge_files, merge_status, save_merged, scan_folder
from schema_engine import (
    classify_column,
    collect_dataset_profile,
    correlation_matrix,
    grouping_suitable,
    scatter_analysis,
    spec_limits_result,
    table_preview,
    time_trend,
)
import limit_engine
import session_analysis
import session_store
from report_builder import write_report

_cancel = threading.Event()
_last_analysis: Optional[AnalysisResult] = None


def _opt_float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        f = float(v)
        return f if f == f else None  # NaN check
    except (TypeError, ValueError):
        return None


def _emit(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, default=_json_default) + "\n")
    sys.stdout.flush()


def _json_default(o):
    try:
        import numpy as np

        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    except Exception:
        pass
    return str(o)


def _progress_event(method: str, **kwargs):
    _emit({"event": "progress", "method": method, **kwargs})


_SESSION_ANALYSES = {
    "session_distribution": lambda s, p: session_analysis.distribution(
        s,
        column=p.get("column") or "",
        bins=int(p.get("bins") or 50),
        lsl=_opt_float(p.get("lsl")),
        usl=_opt_float(p.get("usl")),
        preview_limit=int(p.get("preview_limit") or 500),
        outliers_only=bool(p.get("outliers_only")),
    ),
    "session_comparison": lambda s, p: session_analysis.comparison(
        s,
        value_col=p.get("column") or "",
        group_by=p.get("group_by") or "",
        allow_numeric_group=bool(p.get("allow_numeric_group")),
        numeric_buckets=int(p.get("numeric_buckets") or session_analysis.DEFAULT_NUMERIC_BUCKETS),
        top_n=int(p.get("top_n") or session_analysis.MAX_GROUPS),
        sort_by=p.get("sort_by") or "count",
    ),
    "session_correlation": lambda s, p: session_analysis.correlation(
        s,
        columns=p.get("columns"),
        method=p.get("method") or "pearson",
    ),
    "session_scatter": lambda s, p: session_analysis.scatter(
        s,
        x_col=p.get("x") or "",
        y_col=p.get("y") or "",
        group_by=p.get("group_by") or "",
    ),
    "session_trend": lambda s, p: session_analysis.trend(
        s,
        time_col=p.get("time_col") or "",
        value_col=p.get("value_col") or "",
        aggregation=p.get("aggregation") or "raw",
        date_from=p.get("date_from") or "",
        date_to=p.get("date_to") or "",
    ),
    "session_batch": lambda s, p: session_analysis.batch_comparison(
        s,
        value_col=p.get("column") or "",
        unit=p.get("unit") or session_store.FILE_COL,
        label_col=p.get("label_col") or "",
        positive_label=p.get("positive_label") or "",
        lsl=_opt_float(p.get("lsl")),
        usl=_opt_float(p.get("usl")),
    ),
    "session_table": lambda s, p: session_analysis.table_page(
        s,
        offset=int(p.get("offset") or 0),
        limit=int(p.get("limit") or 100),
        columns=p.get("columns"),
        query=p.get("query") or "",
        sort_by=p.get("sort_by") or "",
        sort_dir=p.get("sort_dir") or "asc",
    ),
    "session_limit_finder": lambda s, p: limit_engine.limit_finder(
        s,
        measurement=p.get("measurement") or "",
        label_col=p.get("label_col") or "",
        negative_label=p.get("negative_label") or "",
        positive_label=p.get("positive_label") or "",
        limit_type=p.get("limit_type") or "upper",
        method=p.get("optimization") or "youden",
        cost_false_accept=float(p.get("cost_false_accept") or 10.0),
        cost_false_reject=float(p.get("cost_false_reject") or 1.0),
        current_lower=_opt_float(p.get("current_lower")),
        current_upper=_opt_float(p.get("current_upper")),
        stat_method=p.get("stat_method") or "percentile",
    ),
    "session_threshold_eval": lambda s, p: limit_engine.evaluate_threshold(
        s,
        measurement=p.get("measurement") or "",
        label_col=p.get("label_col") or "",
        limit_type=p.get("limit_type") or "upper",
        lower=_opt_float(p.get("lower")),
        upper=_opt_float(p.get("upper")),
        negative_label=p.get("negative_label") or "",
        positive_label=p.get("positive_label") or "",
        cost_false_accept=float(p.get("cost_false_accept") or 10.0),
        cost_false_reject=float(p.get("cost_false_reject") or 1.0),
    ),
}

_RESULT_KIND = {
    "session_distribution": "distribution",
    "session_comparison": "comparison",
    "session_correlation": "correlation",
    "session_scatter": "scatter",
    "session_trend": "trend",
    "session_batch": "batch",
    "session_table": "table",
    "session_limit_finder": "limit",
    "session_threshold_eval": "threshold",
}

# Export kinds that read from another module's stored result.
_PAYLOAD_SOURCE = {
    "statistics": "distribution",
    "outliers": "distribution",
    "data": "distribution",
    "thresholds": "limit",
}


def handle(method: str, params: Dict[str, Any]) -> Any:
    global _last_analysis

    if method == "ping":
        return {"ok": True, "engine": "excelmerger-engine"}

    if method == "cancel":
        _cancel.set()
        return {"ok": True}

    if method == "scan_folder":
        _cancel.clear()
        folder = params.get("folder") or ""
        extensions = params.get("extensions") or [".xlsx", ".xls", ".csv", ".xlsm"]
        filters = params.get("filters") or {}

        def prog(done, name):
            _progress_event("scan_folder", done=done, file=name)

        return scan_folder(
            folder,
            extensions,
            filters=filters,
            progress=prog,
            cancel=_cancel.is_set,
        )

    if method == "scan_files":
        paths = params.get("files") or []
        files = scan_files(files=paths)
        return {
            "files": [
                {"path": f.path, "name": f.name, "size": f.size, "selected": True}
                for f in files
            ],
            "count": len(files),
            "total_size": format_size(sum(f.size for f in files)),
        }

    if method == "merge":
        _cancel.clear()
        paths = params.get("files") or []

        def prog(done, total, name):
            _progress_event("merge", done=done, total=total, file=name)

        return merge_files(
            paths,
            sheet_contains=params.get("sheet_contains") or "",
            column_filters=params.get("column_filters") or [],
            remove_dupes=bool(params.get("remove_dupes")),
            progress=prog,
            cancel=_cancel.is_set,
        )

    if method == "merge_status":
        return merge_status()

    if method == "save_merged":
        def prog(done, total):
            _progress_event("save_merged", done=done, total=total, file="")

        return save_merged(params.get("path") or "", params.get("cache_path"), progress=prog)

    if method == "detect_schema":
        _cancel.clear()
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        if folder:
            files = scan_files(folder=folder, recursive=True)
        else:
            files = scan_files(files=paths)

        def prog(done, total, name):
            _progress_event("detect_schema", done=done, total=total, file=name)

        cols, errors = detect_schema(files, progress=prog, stop_event=_cancel)
        payload = []
        for c in cols:
            non_empty = max(0, c.sample_rows)
            col_type = classify_column(c.dtype, c.unique_approx, non_empty, 0)
            payload.append(
                {
                    "name": c.name,
                    "dtype": c.dtype,
                    "col_type": col_type,
                    "file_count": c.file_count,
                    "numeric_hits": c.numeric_hits,
                    "unique_approx": c.unique_approx,
                    "sample_rows": c.sample_rows,
                    "grouping_suitable": grouping_suitable(
                        col_type, c.unique_approx, non_empty
                    ),
                }
            )
        return {
            "files": [{"path": f.path, "name": f.name, "size": f.size} for f in files],
            "columns": payload,
            "errors": errors,
            "file_count": len(files),
            "total_size": format_size(sum(f.size for f in files)),
            "grouping_columns": [c["name"] for c in payload if c["grouping_suitable"]],
        }

    if method == "analyze_distribution":
        _cancel.clear()
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        if folder:
            files = scan_files(folder=folder, recursive=True)
        else:
            files = scan_files(files=paths)

        def prog(done, total, values, name):
            _progress_event(
                "analyze_distribution",
                done=done,
                total=total,
                values=values,
                file=name,
            )

        result = run_distribution_analysis(
            files,
            column=params.get("column") or "",
            bins=int(params.get("bins") or 50),
            group_by=params.get("group_by") or "",
            mode=params.get("mode") or "overall",
            progress=prog,
            stop_event=_cancel,
            lsl=_opt_float(params.get("lsl")),
            usl=_opt_float(params.get("usl")),
        )
        _last_analysis = result
        outliers = int(result.outlier_mask.sum()) if result.outlier_mask.size else 0
        preview = preview_records(
            result,
            outliers_only=bool(params.get("outliers_only")),
            limit=int(params.get("preview_limit") or 500),
        )
        spec = spec_limits_result(
            result.stats,
            result.values,
            _opt_float(params.get("lsl")),
            _opt_float(params.get("usl")),
        )
        return {
            "column": result.column,
            "stats": result.stats,
            "hist_counts": result.hist_counts.tolist(),
            "hist_edges": result.hist_edges.tolist(),
            "summary_lines": result.summary_lines,
            "files_total": result.files_total,
            "files_with_column": result.files_with_column,
            "files_missing_column": result.files_missing_column,
            "errors": result.errors,
            "warnings": result.warnings,
            "group_stats": result.group_stats,
            "outlier_count": outliers,
            "outlier_pct": (outliers / result.stats["count"] * 100)
            if result.stats.get("count")
            else 0,
            "bounds": {
                "lower": result.stats.get("q1", 0) - 1.5 * result.stats.get("iqr", 0),
                "upper": result.stats.get("q3", 0) + 1.5 * result.stats.get("iqr", 0),
            },
            "preview": preview,
            "mode": result.mode,
            "spec": spec,
        }

    if method == "export_analysis":
        if _last_analysis is None:
            return {"ok": False, "error": "No analysis result to export."}
        path = params.get("path") or ""
        df = export_records_df(
            _last_analysis, outliers_only=bool(params.get("outliers_only"))
        )
        try:
            if path.lower().endswith(".csv"):
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                df.to_excel(path, index=False)
            return {"ok": True, "path": path, "rows": int(len(df))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if method == "overview":
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        if folder:
            files = scan_files(folder=folder, recursive=True)
        else:
            files = scan_files(files=paths)

        def prog(done, total, name):
            _progress_event("overview", done=done, total=total, file=name)

        profile = collect_dataset_profile(files, progress=prog, stop_event=_cancel)
        profile["total_size"] = format_size(sum(f.size for f in files))
        # backward-compatible aliases for older UI
        profile["files"] = profile["files_scanned"]
        profile["columns"] = profile["total_columns"]
        profile["numeric"] = profile["type_counts"].get("numeric", 0)
        profile["text"] = profile["type_counts"].get("text", 0) + profile["type_counts"].get(
            "categorical", 0
        )
        profile["date"] = profile["type_counts"].get("datetime", 0)
        profile["column_list"] = [
            {
                "name": c["name"],
                "dtype": c["col_type"],
                "file_count": c["file_count"],
                "unique_approx": c["unique_approx"],
                "missing": c["missing"],
                "missing_pct": c["missing_pct"],
                "col_type": c["col_type"],
                "grouping_suitable": c["grouping_suitable"],
            }
            for c in profile["columns"]
        ]
        return profile

    if method == "data_quality":
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        files = scan_files(folder=folder, recursive=True) if folder else scan_files(files=paths)
        return collect_dataset_profile(files, stop_event=_cancel)

    if method == "correlation":
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        files = scan_files(folder=folder, recursive=True) if folder else scan_files(files=paths)
        return correlation_matrix(files, columns=params.get("columns"), stop_event=_cancel)

    if method == "scatter":
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        files = scan_files(folder=folder, recursive=True) if folder else scan_files(files=paths)
        return scatter_analysis(
            files,
            x_col=params.get("x") or "",
            y_col=params.get("y") or "",
            stop_event=_cancel,
        )

    if method == "table_preview":
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        files = scan_files(folder=folder, recursive=True) if folder else scan_files(files=paths)
        return table_preview(files, limit=int(params.get("limit") or 400), stop_event=_cancel)

    if method == "time_trend":
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        files = scan_files(folder=folder, recursive=True) if folder else scan_files(files=paths)
        return time_trend(
            files,
            time_col=params.get("time_col") or params.get("timestamp") or "",
            value_col=params.get("value_col") or params.get("column") or "",
            aggregation=params.get("aggregation") or "raw",
            stop_event=_cancel,
        )

    if method == "export_table":
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        files = scan_files(folder=folder, recursive=True) if folder else scan_files(files=paths)
        preview = table_preview(files, limit=int(params.get("limit") or 5000), stop_event=_cancel)
        path = params.get("path") or ""
        df = pd.DataFrame(preview.get("rows") or [])
        try:
            if path.lower().endswith(".csv"):
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                df.to_excel(path, index=False)
            return {"ok": True, "path": path, "rows": int(len(df)), "errors": preview.get("errors") or []}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if method == "export_analysis_report":
        if _last_analysis is None:
            return {"ok": False, "error": "No analysis result to export."}
        path = params.get("path") or ""
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            stats_df = pd.DataFrame(
                [{"metric": k, "value": v} for k, v in _last_analysis.stats.items()]
            )
            groups = _last_analysis.group_stats or {}
            group_rows = [{"group": g, **st} for g, st in groups.items()]
            group_df = pd.DataFrame(group_rows) if group_rows else pd.DataFrame([{"group": ""}])
            insights_df = pd.DataFrame({"insight": _last_analysis.summary_lines})
            preview_df = export_records_df(_last_analysis, outliers_only=bool(params.get("outliers_only")))
            with pd.ExcelWriter(path) as writer:
                stats_df.to_excel(writer, sheet_name="Statistics", index=False)
                group_df.to_excel(writer, sheet_name="Groups", index=False)
                insights_df.to_excel(writer, sheet_name="Insights", index=False)
                preview_df.head(20000).to_excel(writer, sheet_name="Data", index=False)
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------------------------------------------------------------- session
    # One dataset load per source; every analysis module reuses the cache.
    if method == "session_open":
        _cancel.clear()
        folder = params.get("folder") or ""
        paths = params.get("files") or []
        files = scan_files(folder=folder, recursive=True) if folder else scan_files(files=paths)
        if not files:
            raise ValueError("No supported Excel/CSV files were found in the selection.")

        def prog(done, total, name):
            _progress_event("session_open", done=done, total=total, file=name)

        return session_store.open_session(
            files,
            folder=folder,
            max_rows=int(params.get("max_rows") or session_store.DEFAULT_MAX_ROWS),
            progress=prog,
            stop_event=_cancel,
        )

    if method == "session_profile":
        return session_store.summary(session_store.get_session(params.get("key") or ""))

    if method == "session_close":
        return session_store.close_session(params.get("key") or "")

    if method == "session_results":
        session = session_store.get_session(params.get("key") or "")
        return {"available": sorted(session.results.keys())}

    if method == "session_column_values":
        return session_store.column_values(
            session_store.get_session(params.get("key") or ""),
            params.get("column") or "",
            limit=int(params.get("limit") or 50),
        )

    if method == "session_label_candidates":
        return {"candidates": limit_engine.label_candidates(session_store.get_session(params.get("key") or ""))}

    if method in _SESSION_ANALYSES:
        session = session_store.get_session(params.get("key") or "")
        result = _SESSION_ANALYSES[method](session, params)
        session.results[_RESULT_KIND[method]] = result
        return result

    if method == "session_export":
        session = session_store.get_session(params.get("key") or "")
        kind = params.get("kind") or "data"
        path = params.get("path") or ""
        payload = session.results.get(_PAYLOAD_SOURCE.get(kind, kind))
        if kind == "quality" or kind == "schema":
            payload = session.profile
        if payload is None:
            return {"ok": False, "error": "Run the analysis before exporting it."}
        df = session_analysis.dataframe_for_export(session, kind, payload)
        if df.empty:
            return {"ok": False, "error": "There is no data to export for this analysis."}
        try:
            if path.lower().endswith(".csv"):
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                if not path.lower().endswith(".xlsx"):
                    path += ".xlsx"
                df.to_excel(path, index=False)
            return {"ok": True, "path": path, "rows": int(len(df))}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    if method == "session_report":
        session = session_store.get_session(params.get("key") or "")
        return write_report(
            session,
            path=params.get("path") or "",
            fmt=params.get("format") or "xlsx",
            sections=params.get("sections") or [],
        )

    raise ValueError(f"Unknown method: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req_id = None
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method") or ""
            params = req.get("params") or {}
            result = handle(method, params)
            _emit({"id": req_id, "result": result})
        except Exception as e:
            _emit(
                {
                    "id": req_id,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                }
            )


if __name__ == "__main__":
    main()
