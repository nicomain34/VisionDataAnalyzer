"""Schema detection, quality, correlation, scatter, spec limits.

Dynamically classifies columns from heterogeneous Excel/CSV files.
Does not assume fixed column names.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from distribution_engine import (
    FileInfo,
    _infer_series_dtype,
    _iter_frames,
    _to_float,
    calculate_stats,
    outlier_mask_iqr,
)

MAX_CORR_COLS = 24
MAX_SCATTER_POINTS = 4000
MAX_TABLE_ROWS = 2000
BOOL_TRUE = {"true", "yes", "y", "1", "ok", "pass", "on"}
BOOL_FALSE = {"false", "no", "n", "0", "ng", "fail", "off"}


def _cell_empty(val) -> bool:
    if val is None:
        return True
    try:
        if pd.isna(val):
            return True
    except (TypeError, ValueError):
        pass
    text = str(val).strip()
    return text == "" or text.lower() in ("nan", "none", "null", "n/a")


def _is_bool_like(val) -> bool:
    if isinstance(val, (bool, np.bool_)):
        return True
    s = str(val).strip().lower()
    return s in BOOL_TRUE or s in BOOL_FALSE


def classify_column(
    dtype_vote: str,
    unique_count: int,
    non_empty: int,
    bool_hits: int,
) -> str:
    """Map raw dtype + cardinality to a user-facing column type."""
    if dtype_vote == "date":
        return "datetime"
    if dtype_vote == "numeric":
        if non_empty >= 8 and unique_count <= 2 and bool_hits >= max(1, int(0.8 * non_empty)):
            return "boolean"
        if non_empty >= 20 and unique_count / max(non_empty, 1) > 0.92:
            return "identifier"
        return "numeric"
    # text / mixed
    if non_empty == 0:
        return "empty"
    if non_empty >= 8 and bool_hits >= max(1, int(0.8 * non_empty)):
        return "boolean"
    if unique_count <= max(2, min(50, int(0.35 * non_empty))):
        return "categorical"
    if non_empty >= 20 and unique_count / max(non_empty, 1) > 0.92:
        return "identifier"
    return "text"


def grouping_suitable(col_type: str, unique_count: int, non_empty: int) -> bool:
    if col_type in ("categorical", "boolean"):
        return unique_count >= 1 and unique_count <= 80
    if col_type == "text":
        return 2 <= unique_count <= 40 and unique_count < 0.5 * max(non_empty, 1)
    return False


def collect_dataset_profile(
    files: Sequence[FileInfo],
    progress: Optional[Callable[[int, int, str], None]] = None,
    stop_event=None,
    sample_rows: int = 400,
) -> Dict[str, Any]:
    """Scan files; return schema, quality issues, and light aggregates."""
    total = len(files)
    col_meta: Dict[str, Dict[str, Any]] = {}
    issues: List[Dict[str, Any]] = []
    failed_files: List[str] = []
    valid = 0
    total_rows = 0
    missing_cells = 0
    total_cells = 0
    invalid_numeric = 0
    dup_rows = 0
    sampled_rows_for_dup = 0

    for i, fi in enumerate(files, 1):
        if stop_event is not None and stop_event.is_set():
            break
        if progress:
            progress(i - 1, total, fi.name)
        try:
            frames = list(_iter_frames(fi.path))
        except Exception as e:
            failed_files.append(fi.name)
            issues.append(
                {
                    "severity": "ERROR",
                    "file": fi.name,
                    "column": "",
                    "issue": "Could not read file",
                    "count": 1,
                    "details": str(e),
                }
            )
            continue

        if not frames:
            failed_files.append(fi.name)
            issues.append(
                {
                    "severity": "ERROR",
                    "file": fi.name,
                    "column": "",
                    "issue": "Empty file / no sheets",
                    "count": 1,
                    "details": "",
                }
            )
            continue

        valid += 1
        seen_in_file = set()
        for sheet, df in frames:
            if df is None or df.empty:
                issues.append(
                    {
                        "severity": "WARNING",
                        "file": fi.name,
                        "column": "",
                        "issue": "Empty sheet",
                        "count": 1,
                        "details": f"Sheet: {sheet}",
                    }
                )
                continue
            n = min(len(df), sample_rows)
            sample = df.head(sample_rows)
            total_rows += int(len(df))
            sampled_rows_for_dup += n
            try:
                dup_rows += int(sample.duplicated().sum())
            except Exception:
                pass
            for col in sample.columns:
                name = str(col)
                seen_in_file.add(name)
                series = sample[col]
                meta = col_meta.setdefault(
                    name,
                    {
                        "files": 0,
                        "numeric": 0,
                        "text": 0,
                        "date": 0,
                        "uniques": set(),
                        "rows": 0,
                        "missing": 0,
                        "bool_hits": 0,
                        "invalid_numeric": 0,
                        "nums": [],
                    },
                )
                vote = _infer_series_dtype(series)
                meta[vote] = int(meta.get(vote, 0)) + 1
                for raw in series.tolist():
                    meta["rows"] += 1
                    total_cells += 1
                    if _cell_empty(raw):
                        meta["missing"] += 1
                        missing_cells += 1
                        continue
                    if _is_bool_like(raw):
                        meta["bool_hits"] += 1
                    num = _to_float(raw)
                    if vote == "numeric" or (isinstance(raw, (int, float, np.integer, np.floating))):
                        if num is None:
                            # looked numeric-ish but failed parse
                            s = str(raw).strip()
                            if s and not _is_bool_like(raw):
                                meta["invalid_numeric"] += 1
                                invalid_numeric += 1
                        else:
                            if len(meta["nums"]) < 8000:
                                meta["nums"].append(num)
                    u = meta["uniques"]
                    if len(u) < 400:
                        u.add(str(raw).strip()[:80])
            for col in sample.columns:
                name = str(col)
                if meta_empty_col(sample[col]):
                    issues.append(
                        {
                            "severity": "WARNING",
                            "file": fi.name,
                            "column": name,
                            "issue": "Empty column",
                            "count": int(len(sample)),
                            "details": f"Sheet: {sheet}",
                        }
                    )

        for name in seen_in_file:
            col_meta[name]["files"] = int(col_meta[name]["files"]) + 1

    if progress:
        progress(total, total, "")

    columns: List[Dict[str, Any]] = []
    type_counts = {
        "numeric": 0,
        "categorical": 0,
        "datetime": 0,
        "identifier": 0,
        "text": 0,
        "boolean": 0,
        "empty": 0,
        "mixed": 0,
    }
    grouping: List[str] = []
    numeric_names: List[str] = []
    datetime_names: List[str] = []

    for name, meta in col_meta.items():
        votes = {
            "numeric": int(meta.get("numeric", 0)),
            "date": int(meta.get("date", 0)),
            "text": int(meta.get("text", 0)),
        }
        dtype_vote = max(votes, key=votes.get)
        mixed = sum(1 for v in votes.values() if v > 0) > 1 and votes["numeric"] and votes["text"]
        uniq = meta.get("uniques") or set()
        unique_count = len(uniq) if isinstance(uniq, set) else 0
        rows = int(meta.get("rows", 0))
        missing = int(meta.get("missing", 0))
        non_empty = max(0, rows - missing)
        bool_hits = int(meta.get("bool_hits", 0))
        col_type = "mixed" if mixed and votes["numeric"] < votes["text"] * 0.5 else classify_column(
            dtype_vote, unique_count, non_empty, bool_hits
        )
        if mixed and dtype_vote == "numeric" and votes["text"] > 0:
            col_type = "mixed"
        type_counts[col_type] = type_counts.get(col_type, 0) + 1
        nums = np.asarray(meta.get("nums") or [], dtype=np.float64)
        st = calculate_stats(nums) if nums.size else {}
        item = {
            "name": name,
            "dtype": dtype_vote,
            "col_type": col_type,
            "file_count": int(meta["files"]),
            "unique_approx": unique_count,
            "sample_rows": rows,
            "missing": missing,
            "missing_pct": (missing / rows * 100.0) if rows else 0.0,
            "invalid_numeric": int(meta.get("invalid_numeric", 0)),
            "min": st.get("min"),
            "max": st.get("max"),
            "mean": st.get("mean"),
            "median": st.get("median"),
            "grouping_suitable": grouping_suitable(col_type, unique_count, non_empty),
        }
        columns.append(item)
        if item["grouping_suitable"]:
            grouping.append(name)
        if col_type == "numeric":
            numeric_names.append(name)
        if col_type == "datetime":
            datetime_names.append(name)
        inv = int(meta.get("invalid_numeric", 0))
        if inv:
            issues.append(
                {
                    "severity": "WARNING",
                    "file": "*",
                    "column": name,
                    "issue": "Invalid numeric values",
                    "count": inv,
                    "details": "Could not parse as number in sampled rows",
                }
            )
        if missing and missing / max(rows, 1) > 0.2:
            issues.append(
                {
                    "severity": "WARNING",
                    "file": "*",
                    "column": name,
                    "issue": "High missing rate",
                    "count": missing,
                    "details": f"{item['missing_pct']:.1f}% missing in sample",
                }
            )

    columns.sort(key=lambda c: (-c["file_count"], c["name"].lower()))
    grouping.sort(key=lambda n: n.lower())
    missing_pct = (missing_cells / total_cells * 100.0) if total_cells else 0.0
    dup_pct = (dup_rows / sampled_rows_for_dup * 100.0) if sampled_rows_for_dup else 0.0

    return {
        "files_scanned": total,
        "valid_files": valid,
        "failed_files": len(failed_files),
        "failed_file_names": failed_files,
        "total_rows_est": total_rows,
        "total_columns": len(columns),
        "type_counts": type_counts,
        "missing_pct": missing_pct,
        "duplicate_pct": dup_pct,
        "invalid_values": invalid_numeric,
        "columns": columns,
        "grouping_columns": grouping,
        "numeric_columns": numeric_names,
        "datetime_columns": datetime_names,
        "issues": issues[:500],
        "errors": [i["details"] or i["issue"] for i in issues if i["severity"] == "ERROR"][:200],
    }


def meta_empty_col(series: pd.Series) -> bool:
    if series.empty:
        return True
    return all(_cell_empty(v) for v in series.head(50).tolist())


def _load_numeric_matrix(
    files: Sequence[FileInfo],
    columns: Sequence[str],
    max_rows: int = 8000,
    stop_event=None,
) -> Tuple[pd.DataFrame, List[str]]:
    wanted = [str(c) for c in columns][:MAX_CORR_COLS]
    acc: Dict[str, List[float]] = {c: [] for c in wanted}
    errors: List[str] = []
    for fi in files:
        if stop_event is not None and stop_event.is_set():
            break
        if acc and min(len(v) for v in acc.values()) >= max_rows:
            break
        try:
            frames = list(_iter_frames(fi.path))
        except Exception as e:
            errors.append(f"{fi.name}: {e}")
            continue
        for _sheet, df in frames:
            cols = {str(c): c for c in df.columns}
            present = [c for c in wanted if c in cols]
            if len(present) < 2:
                continue
            sub = df[[cols[c] for c in present]].head(max_rows)
            for c in present:
                for raw in sub[cols[c]].tolist():
                    num = _to_float(raw)
                    if num is None:
                        continue
                    if len(acc[c]) < max_rows:
                        acc[c].append(num)
    # Align by truncating to shortest common length (pairwise later uses independent series)
    data = {c: acc[c] for c in wanted if acc[c]}
    if not data:
        return pd.DataFrame(), errors
    maxlen = max(len(v) for v in data.values())
    padded = {c: v + [np.nan] * (maxlen - len(v)) for c, v in data.items()}
    return pd.DataFrame(padded), errors


def correlation_matrix(
    files: Sequence[FileInfo],
    columns: Optional[Sequence[str]] = None,
    stop_event=None,
) -> Dict[str, Any]:
    if not columns:
        profile = collect_dataset_profile(files, stop_event=stop_event, sample_rows=80)
        columns = profile.get("numeric_columns") or []
    cols = list(columns)[:MAX_CORR_COLS]
    if len(cols) < 2:
        return {"columns": cols, "matrix": [], "pairs": [], "errors": [], "message": "Need at least two numeric columns."}
    df, errors = _load_numeric_matrix(files, cols, stop_event=stop_event)
    present = [c for c in cols if c in df.columns]
    matrix: List[List[Optional[float]]] = []
    pairs: List[Dict[str, Any]] = []
    for a in present:
        row = []
        sa = pd.to_numeric(df[a], errors="coerce")
        for b in present:
            if a == b:
                row.append(1.0)
                continue
            sb = pd.to_numeric(df[b], errors="coerce")
            joined = pd.concat([sa, sb], axis=1).dropna()
            if len(joined) < 5:
                row.append(None)
                continue
            r = float(joined.iloc[:, 0].corr(joined.iloc[:, 1], method="pearson"))
            if not math.isfinite(r):
                r = None
            row.append(r)
            if a < b and r is not None:
                pairs.append({"x": a, "y": b, "r": r, "n": int(len(joined))})
        matrix.append(row)
    pairs.sort(key=lambda p: -abs(p["r"]))
    return {"columns": present, "matrix": matrix, "pairs": pairs[:40], "errors": errors}


def scatter_analysis(
    files: Sequence[FileInfo],
    x_col: str,
    y_col: str,
    stop_event=None,
) -> Dict[str, Any]:
    xs: List[float] = []
    ys: List[float] = []
    errors: List[str] = []
    for fi in files:
        if stop_event is not None and stop_event.is_set():
            break
        if len(xs) >= MAX_SCATTER_POINTS * 3:
            break
        try:
            frames = list(_iter_frames(fi.path))
        except Exception as e:
            errors.append(f"{fi.name}: {e}")
            continue
        for _sheet, df in frames:
            cols = {str(c): c for c in df.columns}
            if x_col not in cols or y_col not in cols:
                continue
            for xv, yv in zip(df[cols[x_col]].tolist(), df[cols[y_col]].tolist()):
                xf, yf = _to_float(xv), _to_float(yv)
                if xf is None or yf is None:
                    continue
                xs.append(xf)
                ys.append(yf)
    n = min(len(xs), len(ys))
    xa = np.asarray(xs[:n], dtype=np.float64)
    ya = np.asarray(ys[:n], dtype=np.float64)
    if n < 3:
        return {
            "x": x_col,
            "y": y_col,
            "n": n,
            "r": None,
            "r2": None,
            "slope": None,
            "intercept": None,
            "points": [],
            "sampled": False,
            "errors": errors,
            "insight": "Insufficient data for scatter / correlation.",
        }
    r = float(np.corrcoef(xa, ya)[0, 1]) if n > 1 else float("nan")
    if not math.isfinite(r):
        r = 0.0
    # OLS y = a + b x
    b, a = np.polyfit(xa, ya, 1)
    r2 = float(r * r)
    sampled = n > MAX_SCATTER_POINTS
    if sampled:
        rng = np.random.default_rng(42)
        idx = rng.choice(n, size=MAX_SCATTER_POINTS, replace=False)
        idx.sort()
        px, py = xa[idx], ya[idx]
    else:
        px, py = xa, ya
    points = [{"x": float(px[i]), "y": float(py[i])} for i in range(len(px))]
    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
    direction = "positive" if r >= 0 else "negative"
    insight = (
        f"{x_col} and {y_col} show a {strength} {direction} correlation (r = {r:.2f}, n = {n})."
    )
    return {
        "x": x_col,
        "y": y_col,
        "n": n,
        "r": r,
        "r2": r2,
        "slope": float(b),
        "intercept": float(a),
        "points": points,
        "sampled": sampled,
        "errors": errors,
        "insight": insight,
    }


def spec_limits_result(stats: Dict[str, float], values: np.ndarray, lsl: Optional[float], usl: Optional[float]) -> Dict[str, Any]:
    if values.size == 0:
        return {"enabled": False}
    finite = values[np.isfinite(values)]
    n = int(finite.size)
    if n == 0 or (lsl is None and usl is None):
        return {"enabled": False, "n": n}
    below = int(np.sum(finite < lsl)) if lsl is not None else 0
    above = int(np.sum(finite > usl)) if usl is not None else 0
    fail = below + above
    pass_n = n - fail
    return {
        "enabled": True,
        "n": n,
        "lsl": lsl,
        "usl": usl,
        "in_spec": pass_n,
        "out_spec": fail,
        "below_lsl": below,
        "above_usl": above,
        "pass_pct": pass_n / n * 100.0,
        "fail_pct": fail / n * 100.0,
        "below_pct": below / n * 100.0,
        "above_pct": above / n * 100.0,
    }


def table_preview(
    files: Sequence[FileInfo],
    limit: int = 400,
    stop_event=None,
) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    headers: List[str] = []
    errors: List[str] = []
    seen = set()
    for fi in files:
        if stop_event is not None and stop_event.is_set():
            break
        if len(rows) >= limit:
            break
        try:
            frames = list(_iter_frames(fi.path))
        except Exception as e:
            errors.append(f"{fi.name}: {e}")
            continue
        for sheet, df in frames:
            if df is None or df.empty:
                continue
            for c in df.columns:
                name = str(c)
                if name not in seen:
                    seen.add(name)
                    headers.append(name)
            take = min(len(df), max(1, limit - len(rows)))
            chunk = df.head(take)
            for rec in chunk.to_dict(orient="records"):
                out = {"__file": fi.name, "__sheet": sheet}
                for k, v in rec.items():
                    if _cell_empty(v):
                        out[str(k)] = ""
                    else:
                        out[str(k)] = str(v)
                rows.append(out)
                if len(rows) >= limit:
                    break
            if len(rows) >= limit:
                break
    return {"columns": ["__file", "__sheet"] + headers, "rows": rows, "errors": errors, "truncated": len(rows) >= limit}


MAX_TREND_POINTS = 2500


def _shift_label(ts: pd.Timestamp) -> str:
    h = int(ts.hour)
    if 6 <= h < 14:
        return "Shift 1 (06-14)"
    if 14 <= h < 22:
        return "Shift 2 (14-22)"
    return "Shift 3 (22-06)"


def time_trend(
    files: Sequence[FileInfo],
    time_col: str,
    value_col: str,
    aggregation: str = "raw",
    stop_event=None,
) -> Dict[str, Any]:
    """Time series for a numeric column against a detected datetime column."""
    records: List[Tuple[pd.Timestamp, float]] = []
    errors: List[str] = []
    files_with = 0
    for fi in files:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            frames = list(_iter_frames(fi.path))
        except Exception as e:
            errors.append(f"{fi.name}: {e}")
            continue
        found = False
        for _sheet, df in frames:
            cols = {str(c): c for c in df.columns}
            if time_col not in cols or value_col not in cols:
                continue
            found = True
            try:
                ts = pd.to_datetime(df[cols[time_col]], errors="coerce", dayfirst=True, format="mixed")
            except TypeError:
                ts = pd.to_datetime(df[cols[time_col]], errors="coerce", dayfirst=True)
            for t, raw in zip(ts.tolist(), df[cols[value_col]].tolist()):
                if t is None or (isinstance(t, float) and math.isnan(t)):
                    continue
                try:
                    if pd.isna(t):
                        continue
                except (TypeError, ValueError):
                    continue
                num = _to_float(raw)
                if num is None:
                    continue
                records.append((pd.Timestamp(t), num))
        if found:
            files_with += 1

    if len(records) < 3:
        return {
            "time_col": time_col,
            "value_col": value_col,
            "aggregation": aggregation,
            "n": len(records),
            "points": [],
            "stats": calculate_stats(np.array([])),
            "errors": errors,
            "files_with_column": files_with,
            "insight": "Insufficient data for reliable statistical interpretation.",
        }

    frame = pd.DataFrame(records, columns=["t", "v"]).sort_values("t")
    agg = (aggregation or "raw").lower()
    if agg == "hourly":
        series = frame.set_index("t")["v"].resample("h").mean().dropna()
        out = pd.DataFrame({"t": series.index, "v": series.values})
    elif agg == "daily":
        series = frame.set_index("t")["v"].resample("D").mean().dropna()
        out = pd.DataFrame({"t": series.index, "v": series.values})
    elif agg == "shift":
        grouped = frame.groupby(frame["t"].map(_shift_label), sort=False)["v"].mean()
        out = pd.DataFrame({"t": grouped.index.astype(str), "v": grouped.values})
    else:
        out = frame

    values = out["v"].to_numpy(dtype=np.float64)
    st = calculate_stats(values)
    mask = outlier_mask_iqr(values, st)
    window = max(3, min(25, int(len(out) // 15) or 3))
    roll = pd.Series(values).rolling(window, min_periods=1).mean().to_numpy()

    sampled = len(out) > MAX_TREND_POINTS
    if sampled:
        step = int(math.ceil(len(out) / MAX_TREND_POINTS))
        idxs = list(range(0, len(out), step))
    else:
        idxs = list(range(len(out)))

    points = []
    for i in idxs:
        tval = out["t"].iloc[i]
        label = tval.isoformat() if hasattr(tval, "isoformat") else str(tval)
        points.append(
            {
                "t": label,
                "v": float(values[i]),
                "roll": float(roll[i]),
                "outlier": bool(mask[i]) if i < len(mask) else False,
            }
        )

    n = int(st.get("count") or 0)
    if n < 8:
        insight = "Insufficient data for reliable statistical interpretation."
    else:
        insight = (
            f"{value_col} over time ({agg}): mean {st['mean']:.4g}, "
            f"min {st['min']:.4g}, max {st['max']:.4g}; "
            f"{int(np.sum(mask))} outlier(s) by IQR."
        )
    return {
        "time_col": time_col,
        "value_col": value_col,
        "aggregation": agg,
        "n": n,
        "points": points,
        "stats": st,
        "outlier_count": int(np.sum(mask)) if mask.size else 0,
        "sampled": sampled,
        "errors": errors,
        "files_with_column": files_with,
        "insight": insight,
        "min": st.get("min"),
        "max": st.get("max"),
        "mean": st.get("mean"),
    }
