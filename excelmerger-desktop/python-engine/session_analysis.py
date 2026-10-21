"""Analysis services operating on a cached dataset session.

Every function takes an already loaded session, so switching pages in the UI
never re-reads the source files.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from distribution_engine import build_histogram, calculate_stats, outlier_mask_iqr
from session_store import (
    FILE_COL,
    META_COLS,
    SHEET_COL,
    Session,
    column_meta,
    numeric_series,
    parse_timestamps,
    text_series,
)

MAX_GROUPS = 60
MAX_SCATTER_POINTS = 6000
MAX_TREND_POINTS = 3000
MAX_KDE_SAMPLE = 20000
DEFAULT_NUMERIC_BUCKETS = 8


def _clean(arr: np.ndarray) -> np.ndarray:
    return arr[np.isfinite(arr)]


def _f(value) -> Optional[float]:
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def kde_curve(values: np.ndarray, points: int = 160) -> List[Dict[str, float]]:
    v = _clean(values)
    if v.size < 5:
        return []
    if v.size > MAX_KDE_SAMPLE:
        rng = np.random.default_rng(7)
        v = rng.choice(v, MAX_KDE_SAMPLE, replace=False)
    std = float(np.std(v))
    if std <= 0:
        return []
    bw = 1.06 * std * v.size ** (-1 / 5)
    grid = np.linspace(float(v.min()), float(v.max()), points)
    dens = np.exp(-0.5 * ((grid[:, None] - v[None, :]) / bw) ** 2).sum(axis=1)
    dens = dens / (v.size * bw * math.sqrt(2 * math.pi))
    return [{"x": float(grid[i]), "d": float(dens[i])} for i in range(points)]


def _group_keys(
    session: Session,
    group_by: str,
    allow_numeric: bool,
    numeric_buckets: int,
) -> pd.Series:
    """Build group labels. Numeric columns are bucketed, never one group per value."""
    if group_by in ("__file", "__file__", FILE_COL):
        return session.frame[FILE_COL].astype(str)
    if group_by == SHEET_COL:
        return session.frame[SHEET_COL].astype(str)

    meta = column_meta(session, group_by)
    if meta is None:
        raise KeyError(f"Grouping column '{group_by}' does not exist in the loaded dataset.")

    if meta["col_type"] == "numeric":
        if not allow_numeric:
            raise ValueError(
                f"'{group_by}' is a numeric measurement column. Enable advanced numeric grouping "
                "to compare it as value ranges."
            )
        values = numeric_series(session, group_by)
        buckets = max(2, min(int(numeric_buckets or DEFAULT_NUMERIC_BUCKETS), 20))
        try:
            binned = pd.qcut(values, q=buckets, duplicates="drop")
        except (ValueError, IndexError):
            binned = pd.cut(values, bins=buckets)
        return binned.astype(str).where(values.notna())

    return text_series(session, group_by).astype(str).where(
        text_series(session, group_by).notna()
    )


def _group_stat_row(values: np.ndarray) -> Dict[str, Any]:
    arr = _clean(values)
    st = calculate_stats(arr)
    mask = outlier_mask_iqr(arr, st)
    return {
        "count": int(st["count"]),
        "mean": _f(st["mean"]),
        "median": _f(st["median"]),
        "std": _f(st["std"]),
        "min": _f(st["min"]),
        "max": _f(st["max"]),
        "p5": _f(st["p5"]),
        "p25": _f(st["q1"]),
        "p75": _f(st["q3"]),
        "p95": _f(st["p95"]),
        "iqr": _f(st["iqr"]),
        "outlier_count": int(mask.sum()) if mask.size else 0,
    }


def spec_result(values: np.ndarray, lsl: Optional[float], usl: Optional[float]) -> Dict[str, Any]:
    arr = _clean(values)
    if arr.size == 0 or (lsl is None and usl is None):
        return {"enabled": False, "n": int(arr.size)}
    below = int(np.sum(arr < lsl)) if lsl is not None else 0
    above = int(np.sum(arr > usl)) if usl is not None else 0
    fail = below + above
    n = int(arr.size)
    return {
        "enabled": True,
        "n": n,
        "lsl": lsl,
        "usl": usl,
        "in_spec": n - fail,
        "out_spec": fail,
        "below_lsl": below,
        "above_usl": above,
        "pass_pct": (n - fail) / n * 100.0,
        "fail_pct": fail / n * 100.0,
        "below_pct": below / n * 100.0,
        "above_pct": above / n * 100.0,
    }


def distribution(
    session: Session,
    column: str,
    bins: int = 50,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    preview_limit: int = 500,
    outliers_only: bool = False,
) -> Dict[str, Any]:
    meta = column_meta(session, column)
    if meta is None:
        raise KeyError(f"Column '{column}' does not exist in the loaded dataset.")
    if meta["col_type"] not in ("numeric", "mixed"):
        raise ValueError(
            f"Distribution requires a numeric column. '{column}' was detected as {meta['col_type']}."
        )

    series = numeric_series(session, column)
    present = int(meta["count"])
    arr = series.to_numpy(dtype=np.float64)
    valid = _clean(arr)
    excluded = present - int(valid.size)

    st = calculate_stats(valid)
    mask = outlier_mask_iqr(valid, st)
    counts, edges = build_histogram(valid, bins=bins)
    outlier_count = int(mask.sum()) if mask.size else 0
    spec = spec_result(valid, lsl, usl)

    finite_idx = np.flatnonzero(np.isfinite(arr))
    sel = finite_idx[mask] if outliers_only and mask.size else finite_idx
    sel = sel[:preview_limit]
    files = session.frame[FILE_COL].to_numpy()
    sheets = session.frame[SHEET_COL].to_numpy()
    outlier_lookup = dict(zip(finite_idx.tolist(), mask.tolist())) if mask.size else {}
    preview = [
        {
            "#": i + 1,
            "File name": str(files[idx]),
            "Sheet name": str(sheets[idx]),
            column: float(arr[idx]),
            "Outlier": bool(outlier_lookup.get(int(idx), False)),
        }
        for i, idx in enumerate(sel.tolist())
    ]

    lower = _f(st["q1"] - 1.5 * st["iqr"]) if st["count"] else None
    upper = _f(st["q3"] + 1.5 * st["iqr"]) if st["count"] else None

    return {
        "column": column,
        "stats": {k: _f(v) for k, v in st.items()},
        "hist_counts": counts.tolist(),
        "hist_edges": edges.tolist(),
        "kde": kde_curve(valid),
        "outlier_count": outlier_count,
        "outlier_pct": (outlier_count / st["count"] * 100.0) if st["count"] else 0.0,
        "bounds": {"lower": lower, "upper": upper},
        "excluded_values": excluded,
        "missing_values": int(meta["missing"]),
        "files_with_column": int(meta["file_count"]),
        "files_total": int(session.profile["files_scanned"]),
        "spec": spec,
        "preview": preview,
        "insights": _distribution_insights(column, st, outlier_count, excluded, spec, meta, session),
    }


def _distribution_insights(
    column: str,
    st: Dict[str, float],
    outlier_count: int,
    excluded: int,
    spec: Dict[str, Any],
    meta: Dict[str, Any],
    session: Session,
) -> List[str]:
    n = int(st.get("count") or 0)
    if n == 0:
        return [f"No valid numeric values found in '{column}'."]
    if n < 8:
        return [
            f"Only {n} valid value(s) in '{column}'.",
            "Insufficient data for reliable statistical interpretation.",
        ]
    out = [f"{column} contains {n:,} valid measurements."]
    out.append(f"Mean is {st['mean']:.4g} and median is {st['median']:.4g}.")
    iqr_share = None
    if math.isfinite(st["iqr"]) and st["iqr"] > 0:
        iqr_share = 50.0
        out.append(
            f"The middle 50% of values lie between {st['p25']:.4g} and {st['p75']:.4g} "
            f"(IQR {st['iqr']:.4g})."
        )
    skew = st.get("skew") or 0.0
    if abs(skew) >= 0.5:
        out.append(
            f"The distribution is {'right' if skew > 0 else 'left'}-skewed (skewness {skew:.2f})."
        )
    elif abs(skew) < 0.2:
        out.append(f"The distribution is approximately symmetric (skewness {skew:.2f}).")
    if outlier_count:
        out.append(
            f"{outlier_count:,} value(s) fall outside the 1.5 × IQR bounds "
            f"({st['q1'] - 1.5 * st['iqr']:.4g} … {st['q3'] + 1.5 * st['iqr']:.4g})."
        )
    else:
        out.append("No values fall outside the 1.5 × IQR bounds.")
    if excluded:
        out.append(f"{excluded:,} non-numeric value(s) were excluded from the calculation.")
    if meta["file_count"] < session.profile["files_scanned"]:
        out.append(
            f"'{column}' is available in {meta['file_count']} of "
            f"{session.profile['files_scanned']} files."
        )
    if spec.get("enabled"):
        out.append(
            f"{spec['pass_pct']:.1f}% of values are within the specification limits; "
            f"{spec['fail_pct']:.1f}% are outside."
        )
    if iqr_share is None and n:
        out.append("All values are identical, so dispersion statistics are zero.")
    return out


def comparison(
    session: Session,
    value_col: str,
    group_by: str,
    allow_numeric_group: bool = False,
    numeric_buckets: int = DEFAULT_NUMERIC_BUCKETS,
    top_n: int = MAX_GROUPS,
    sort_by: str = "count",
) -> Dict[str, Any]:
    meta = column_meta(session, value_col)
    if meta is None:
        raise KeyError(f"Column '{value_col}' does not exist in the loaded dataset.")
    if meta["col_type"] not in ("numeric", "mixed"):
        raise ValueError(f"Comparison requires a numeric measure column, got {meta['col_type']}.")
    if not group_by:
        raise ValueError("Select a grouping column.")

    keys = _group_keys(session, group_by, allow_numeric_group, numeric_buckets)
    values = numeric_series(session, value_col)
    frame = pd.DataFrame({"g": keys, "v": values}).dropna()
    if frame.empty:
        return {
            "value_col": value_col,
            "group_by": group_by,
            "groups": [],
            "total_groups": 0,
            "truncated": False,
            "insights": ["No rows contain both the measure and the grouping value."],
        }

    rows: List[Dict[str, Any]] = []
    for key, sub in frame.groupby("g", sort=False):
        row = _group_stat_row(sub["v"].to_numpy(dtype=np.float64))
        row["group"] = str(key)
        rows.append(row)

    group_meta = (
        None if group_by in ("__file", "__file__", FILE_COL, SHEET_COL) else column_meta(session, group_by)
    )
    bucketed = bool(group_meta and group_meta["col_type"] == "numeric")
    total_groups = len(rows)
    reverse = sort_by != "group"
    rows.sort(key=lambda r: (r.get(sort_by) if sort_by != "group" else r["group"]) or 0, reverse=reverse)
    shown = rows[: max(1, min(int(top_n or MAX_GROUPS), MAX_GROUPS))]

    overall = _group_stat_row(frame["v"].to_numpy(dtype=np.float64))
    insights: List[str] = [
        f"{total_groups} group(s) were formed from '{group_by}' over {overall['count']:,} values."
    ]
    sized = [r for r in shown if r["count"] >= 3 and r["mean"] is not None]
    if len(sized) >= 2:
        best = max(sized, key=lambda r: r["mean"])
        worst = min(sized, key=lambda r: r["mean"])
        insights.append(
            f"'{best['group']}' has the highest average ({best['mean']:.4g}) and "
            f"'{worst['group']}' the lowest ({worst['mean']:.4g})."
        )
        spread = [r for r in sized if r["std"] is not None]
        if spread:
            noisy = max(spread, key=lambda r: r["std"])
            insights.append(
                f"'{noisy['group']}' shows the largest spread (std {noisy['std']:.4g})."
            )
    else:
        insights.append("Insufficient data for reliable statistical interpretation per group.")
    if total_groups > len(shown):
        insights.append(f"Showing the top {len(shown)} of {total_groups} groups.")
    return {
        "value_col": value_col,
        "group_by": group_by,
        "groups": shown,
        "total_groups": total_groups,
        "truncated": total_groups > len(shown),
        "overall": overall,
        "bucketed": bucketed,
        "insights": insights,
    }


def _candidate_numeric(session: Session, columns: Optional[Sequence[str]]) -> List[str]:
    if columns:
        return [c for c in columns if c in session.frame.columns]
    return list(session.profile["numeric_columns"])


def correlation(
    session: Session,
    columns: Optional[Sequence[str]] = None,
    method: str = "pearson",
    max_columns: int = 30,
) -> Dict[str, Any]:
    cols = _candidate_numeric(session, columns)[:max_columns]
    if len(cols) < 2:
        return {
            "columns": cols,
            "matrix": [],
            "pairs": [],
            "method": method,
            "excluded": session.profile["excluded_columns"],
            "message": "Correlation requires at least two usable numeric columns.",
        }
    method = "spearman" if str(method).lower().startswith("s") else "pearson"
    numeric = session.frame[cols].apply(pd.to_numeric, errors="coerce")
    matrix_df = numeric.corr(method=method, min_periods=5)
    counts = numeric.notna().astype(int)
    pair_counts = counts.T.dot(counts)

    matrix: List[List[Optional[float]]] = []
    pairs: List[Dict[str, Any]] = []
    for a in cols:
        row: List[Optional[float]] = []
        for b in cols:
            r = _f(matrix_df.loc[a, b]) if a in matrix_df.index and b in matrix_df.columns else None
            row.append(r)
            if a < b and r is not None:
                pairs.append({"x": a, "y": b, "r": r, "n": int(pair_counts.loc[a, b])})
        matrix.append(row)
    pairs.sort(key=lambda p: -abs(p["r"]))

    insights: List[str] = []
    for p in pairs[:3]:
        if abs(p["r"]) >= 0.7:
            insights.append(
                f"{p['x']} and {p['y']} show a strong {'positive' if p['r'] > 0 else 'negative'} "
                f"correlation (r = {p['r']:.2f}, n = {p['n']:,}). Correlation does not imply causation."
            )
    if not insights:
        insights.append("No strong linear relationships (|r| ≥ 0.7) were found between numeric columns.")
    return {
        "columns": cols,
        "matrix": matrix,
        "pairs": pairs[:80],
        "method": method,
        "excluded": session.profile["excluded_columns"],
        "insights": insights,
    }


def scatter(
    session: Session,
    x_col: str,
    y_col: str,
    group_by: str = "",
    max_points: int = MAX_SCATTER_POINTS,
) -> Dict[str, Any]:
    for c in (x_col, y_col):
        meta = column_meta(session, c)
        if meta is None:
            raise KeyError(f"Column '{c}' does not exist in the loaded dataset.")
        if meta["col_type"] not in ("numeric", "mixed"):
            raise ValueError(f"Scatter plot requires numeric columns; '{c}' is {meta['col_type']}.")
    if x_col == y_col:
        raise ValueError("Select two different columns for X and Y.")

    data = pd.DataFrame(
        {"x": numeric_series(session, x_col), "y": numeric_series(session, y_col)}
    )
    if group_by:
        data["g"] = _group_keys(session, group_by, allow_numeric=True, numeric_buckets=6)
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=["x", "y"])
    n = int(len(data))
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
            "series": [],
            "total_points": n,
            "sampled": False,
            "outlier_count": 0,
            "insights": ["Insufficient data for reliable statistical interpretation."],
        }

    xs = data["x"].to_numpy(dtype=np.float64)
    ys = data["y"].to_numpy(dtype=np.float64)
    r = _f(np.corrcoef(xs, ys)[0, 1]) or 0.0
    slope, intercept = (float(v) for v in np.polyfit(xs, ys, 1))
    resid = ys - (intercept + slope * xs)
    resid_mask = outlier_mask_iqr(resid)
    outlier_count = int(resid_mask.sum()) if resid_mask.size else 0

    sampled = n > max_points
    if sampled:
        rng = np.random.default_rng(11)
        idx = np.sort(rng.choice(n, size=max_points, replace=False))
    else:
        idx = np.arange(n)

    points = [
        {"x": float(xs[i]), "y": float(ys[i]), "o": bool(resid_mask[i]) if resid_mask.size else False}
        for i in idx.tolist()
    ]
    series: List[Dict[str, Any]] = []
    if group_by and "g" in data.columns:
        groups = data["g"].astype(str).to_numpy()
        per_group: Dict[str, List[Dict[str, float]]] = {}
        for i in idx.tolist():
            per_group.setdefault(groups[i], []).append({"x": float(xs[i]), "y": float(ys[i])})
        series = [
            {"name": name, "points": pts}
            for name, pts in sorted(per_group.items(), key=lambda kv: -len(kv[1]))[:12]
        ]

    strength = "strong" if abs(r) >= 0.7 else "moderate" if abs(r) >= 0.4 else "weak"
    direction = "positive" if r >= 0 else "negative"
    insights = [
        f"{x_col} and {y_col} show a {strength} {direction} linear relationship "
        f"(r = {r:.2f}, R² = {r * r:.2f}, n = {n:,}).",
        "Correlation describes association only, not causation.",
    ]
    if outlier_count:
        insights.append(f"{outlier_count:,} point(s) deviate strongly from the fitted line.")
    if sampled:
        insights.append(f"Visualization sampled: {len(points):,} / {n:,} points.")
    return {
        "x": x_col,
        "y": y_col,
        "group_by": group_by,
        "n": n,
        "r": r,
        "r2": r * r,
        "slope": slope,
        "intercept": intercept,
        "fit": [
            {"x": float(xs.min()), "y": float(intercept + slope * xs.min())},
            {"x": float(xs.max()), "y": float(intercept + slope * xs.max())},
        ],
        "points": points,
        "series": series,
        "total_points": n,
        "sampled": sampled,
        "outlier_count": outlier_count,
        "insights": insights,
    }


def _shift_label(ts: pd.Timestamp) -> str:
    h = int(ts.hour)
    if 6 <= h < 14:
        return "Shift 1 (06-14)"
    if 14 <= h < 22:
        return "Shift 2 (14-22)"
    return "Shift 3 (22-06)"


def trend(
    session: Session,
    time_col: str,
    value_col: str,
    aggregation: str = "raw",
    date_from: str = "",
    date_to: str = "",
) -> Dict[str, Any]:
    tmeta = column_meta(session, time_col)
    vmeta = column_meta(session, value_col)
    if tmeta is None or vmeta is None:
        raise KeyError("Selected column does not exist in the loaded dataset.")
    if tmeta["col_type"] != "datetime":
        raise ValueError(f"'{time_col}' was not detected as a Date/Time column.")
    if vmeta["col_type"] not in ("numeric", "mixed"):
        raise ValueError(f"Time Trend requires a numeric value column; '{value_col}' is {vmeta['col_type']}.")

    ts = parse_timestamps(session.frame[time_col])
    data = pd.DataFrame({"t": ts, "v": numeric_series(session, value_col)}).dropna()
    if date_from:
        data = data[data["t"] >= pd.to_datetime(date_from)]
    if date_to:
        data = data[data["t"] <= pd.to_datetime(date_to)]
    data = data.sort_values("t")
    if len(data) < 3:
        return {
            "time_col": time_col,
            "value_col": value_col,
            "aggregation": aggregation,
            "n": int(len(data)),
            "points": [],
            "insights": ["Insufficient data for reliable statistical interpretation."],
        }

    agg = (aggregation or "raw").lower()
    rule = {"hourly": "h", "daily": "D", "weekly": "W"}.get(agg)
    if rule:
        grouped = data.set_index("t")["v"].resample(rule)
        series = grouped.mean().dropna()
        out = pd.DataFrame({"t": series.index, "v": series.to_numpy()})
    elif agg == "shift":
        labels = data["t"].map(_shift_label)
        grouped = data.groupby(labels, sort=True)["v"].mean()
        out = pd.DataFrame({"t": grouped.index.astype(str), "v": grouped.to_numpy()})
    else:
        out = data.reset_index(drop=True)

    values = out["v"].to_numpy(dtype=np.float64)
    st = calculate_stats(values)
    mask = outlier_mask_iqr(values, st)
    window = max(3, min(50, int(len(out) // 15) or 3))
    roll = pd.Series(values).rolling(window, min_periods=1).mean().to_numpy()

    sampled = len(out) > MAX_TREND_POINTS
    idxs = (
        list(range(0, len(out), int(math.ceil(len(out) / MAX_TREND_POINTS))))
        if sampled
        else list(range(len(out)))
    )
    points = []
    for i in idxs:
        tval = out["t"].iloc[i]
        points.append(
            {
                "t": tval.isoformat() if hasattr(tval, "isoformat") else str(tval),
                "v": float(values[i]),
                "roll": float(roll[i]),
                "outlier": bool(mask[i]) if mask.size else False,
            }
        )

    insights: List[str] = []
    n = int(st["count"])
    if n >= 8:
        half = n // 2
        first, second = float(np.mean(values[:half])), float(np.mean(values[half:]))
        delta = second - first
        scale = abs(first) if first else 1.0
        if abs(delta) > 0.05 * scale:
            insights.append(
                f"The mean {'increased' if delta > 0 else 'decreased'} from {first:.4g} to "
                f"{second:.4g} between the first and second half of the period."
            )
        else:
            insights.append("No material trend between the first and second half of the period.")
        insights.append(
            f"{value_col}: mean {st['mean']:.4g}, min {st['min']:.4g}, max {st['max']:.4g} over {n:,} points."
        )
        if int(mask.sum()):
            insights.append(f"{int(mask.sum()):,} point(s) are IQR outliers.")
    else:
        insights.append("Insufficient data for reliable statistical interpretation.")
    if sampled:
        insights.append(f"Visualization sampled: {len(points):,} / {len(out):,} points.")

    return {
        "time_col": time_col,
        "value_col": value_col,
        "aggregation": agg,
        "n": n,
        "points": points,
        "stats": {k: _f(v) for k, v in st.items()},
        "outlier_count": int(mask.sum()) if mask.size else 0,
        "sampled": sampled,
        "total_points": int(len(out)),
        "range": {
            "from": str(data["t"].min()),
            "to": str(data["t"].max()),
        },
        "insights": insights,
    }


def batch_comparison(
    session: Session,
    value_col: str,
    unit: str = FILE_COL,
    label_col: str = "",
    positive_label: str = "",
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
    top_n: int = MAX_GROUPS,
) -> Dict[str, Any]:
    meta = column_meta(session, value_col)
    if meta is None:
        raise KeyError(f"Column '{value_col}' does not exist in the loaded dataset.")
    if meta["col_type"] not in ("numeric", "mixed"):
        raise ValueError(f"Batch comparison requires a numeric measure; '{value_col}' is {meta['col_type']}.")

    keys = _group_keys(session, unit or FILE_COL, allow_numeric=True, numeric_buckets=6)
    frame = pd.DataFrame({"g": keys, "v": numeric_series(session, value_col)})
    if label_col:
        frame["label"] = text_series(session, label_col).astype(str)
    frame = frame.dropna(subset=["g", "v"])
    if frame.empty:
        return {
            "value_col": value_col,
            "unit": unit,
            "batches": [],
            "insights": ["No rows contain both the measure and the batch identifier."],
        }

    pos = positive_label
    if label_col and not pos:
        meta_label = column_meta(session, label_col)
        if meta_label:
            pos = meta_label.get("positive_label") or ""

    rows: List[Dict[str, Any]] = []
    for key, sub in frame.groupby("g", sort=False):
        arr = sub["v"].to_numpy(dtype=np.float64)
        row = _group_stat_row(arr)
        row["batch"] = str(key)
        spec = spec_result(arr, lsl, usl)
        row["in_spec_pct"] = _f(spec.get("pass_pct")) if spec.get("enabled") else None
        if label_col and pos:
            labels = sub["label"].astype(str)
            total = int(labels.notna().sum())
            good = int((labels.str.strip().str.lower() == str(pos).strip().lower()).sum())
            row["pass_rate"] = (good / total * 100.0) if total else None
        else:
            row["pass_rate"] = None
        rows.append(row)

    rows.sort(key=lambda r: r["batch"])
    shown = rows[: max(1, min(int(top_n or MAX_GROUPS), MAX_GROUPS))]

    insights: List[str] = [f"{len(rows)} batch unit(s) compared on '{value_col}'."]
    sized = [r for r in shown if r["count"] >= 3 and r["mean"] is not None]
    if len(sized) >= 2:
        best = max(sized, key=lambda r: r["mean"])
        worst = min(sized, key=lambda r: r["mean"])
        insights.append(
            f"Highest average: '{best['group'] if 'group' in best else best['batch']}' "
            f"({best['mean']:.4g}); lowest: '{worst['batch']}' ({worst['mean']:.4g})."
        )
        first, last = sized[0], sized[-1]
        if first["mean"] is not None and last["mean"] is not None:
            delta = last["mean"] - first["mean"]
            insights.append(
                f"From '{first['batch']}' to '{last['batch']}' the mean changed by {delta:+.4g}."
            )
        rates = [r for r in sized if r.get("pass_rate") is not None]
        if len(rates) >= 2:
            bestr = max(rates, key=lambda r: r["pass_rate"])
            worstr = min(rates, key=lambda r: r["pass_rate"])
            insights.append(
                f"Pass rate ranges from {worstr['pass_rate']:.1f}% ('{worstr['batch']}') to "
                f"{bestr['pass_rate']:.1f}% ('{bestr['batch']}')."
            )
    else:
        insights.append("Insufficient data for reliable statistical interpretation per batch.")
    return {
        "value_col": value_col,
        "unit": unit,
        "label_col": label_col,
        "positive_label": pos,
        "batches": shown,
        "total_batches": len(rows),
        "truncated": len(rows) > len(shown),
        "insights": insights,
    }


def table_page(
    session: Session,
    offset: int = 0,
    limit: int = 100,
    columns: Optional[Sequence[str]] = None,
    query: str = "",
    sort_by: str = "",
    sort_dir: str = "asc",
    include_meta: bool = True,
) -> Dict[str, Any]:
    frame = session.frame
    if frame.empty:
        return {"columns": [], "rows": [], "total": 0, "offset": 0, "limit": limit}

    cols = [c for c in (columns or []) if c in frame.columns]
    if not cols:
        cols = [c for c in frame.columns if c not in META_COLS]
    view_cols = ([FILE_COL, SHEET_COL] if include_meta else []) + cols
    view = frame[view_cols]

    if query:
        q = str(query).strip().lower()
        if q:
            mask = np.zeros(len(view), dtype=bool)
            for c in view_cols:
                try:
                    mask |= view[c].astype(str).str.lower().str.contains(q, regex=False, na=False).to_numpy()
                except Exception:
                    continue
            view = view[mask]
    if sort_by and sort_by in view.columns:
        ascending = sort_dir != "desc"
        if sort_by in set(session.profile["all_numeric_columns"]):
            # Mixed columns cannot be compared directly; sort on the numeric reading.
            order = pd.to_numeric(view[sort_by], errors="coerce").sort_values(
                ascending=ascending, kind="mergesort", na_position="last"
            )
            view = view.loc[order.index]
        else:
            view = view.sort_values(
                sort_by, ascending=ascending, kind="mergesort", key=lambda s: s.astype(str)
            )

    total = int(len(view))
    offset = max(0, int(offset))
    limit = max(1, min(int(limit or 100), 500))
    page = view.iloc[offset : offset + limit]

    numeric_cols = set(session.profile["all_numeric_columns"])
    rows: List[Dict[str, Any]] = []
    for _, rec in page.iterrows():
        row: Dict[str, Any] = {}
        for c in view_cols:
            val = rec[c]
            if pd.isna(val):
                row[c] = None
            elif c in numeric_cols:
                num = pd.to_numeric(val, errors="coerce")
                row[c] = None if pd.isna(num) else float(num)
            else:
                row[c] = str(val)
        rows.append(row)
    return {
        "columns": view_cols,
        "rows": rows,
        "total": total,
        "offset": offset,
        "limit": limit,
        "numeric_columns": [c for c in view_cols if c in numeric_cols],
    }


def dataframe_for_export(session: Session, kind: str, payload: Dict[str, Any]) -> pd.DataFrame:
    """Turn a stored analysis result into a flat table for CSV/XLSX export."""
    if kind == "statistics":
        stats = payload.get("stats") or {}
        return pd.DataFrame([{"metric": k, "value": v} for k, v in stats.items()])
    if kind == "outliers":
        rows = [r for r in (payload.get("preview") or []) if r.get("Outlier")]
        return pd.DataFrame(rows)
    if kind == "data":
        return pd.DataFrame(payload.get("preview") or [])
    if kind == "comparison":
        return pd.DataFrame(payload.get("groups") or [])
    if kind == "batch":
        return pd.DataFrame(payload.get("batches") or [])
    if kind == "correlation":
        cols = payload.get("columns") or []
        matrix = payload.get("matrix") or []
        return pd.DataFrame(matrix, index=cols, columns=cols).reset_index(names="column")
    if kind == "scatter":
        return pd.DataFrame(payload.get("points") or [])
    if kind == "trend":
        return pd.DataFrame(payload.get("points") or [])
    if kind == "thresholds":
        return pd.DataFrame(payload.get("thresholds") or [])
    if kind == "quality":
        return pd.DataFrame(payload.get("issues") or [])
    if kind == "schema":
        return pd.DataFrame(payload.get("columns") or [])
    return pd.DataFrame()
