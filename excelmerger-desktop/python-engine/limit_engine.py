"""Limit Finder: threshold optimization against OK/NG labels, plus statistical limits.

Supervised mode requires real pass/fail ground truth. Without labels the module
only produces explicitly-labelled statistical recommendations.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from distribution_engine import calculate_stats
from session_store import NEGATIVE_TOKENS, POSITIVE_TOKENS, Session, column_meta, numeric_series, text_series

MAX_THRESHOLDS = 240
MAX_GRID = 48
MIN_CLASS_SAMPLES = 30
IMBALANCE_WARN = 0.05


def _f(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def label_candidates(session: Session) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in session.profile["columns"]:
        if not c.get("is_label_candidate"):
            continue
        out.append(
            {
                "name": c["name"],
                "values": c.get("label_values") or [],
                "counts": c.get("label_counts") or [],
                "negative_label": c.get("negative_label"),
                "positive_label": c.get("positive_label"),
                "recognized": bool(c.get("labels_recognized")),
            }
        )
    out.sort(key=lambda c: (not c["recognized"], c["name"].lower()))
    return out


def _resolve_classes(
    labels: pd.Series,
    negative_label: str,
    positive_label: str,
) -> Tuple[str, str, List[str]]:
    """Return (negative/NG label, positive/OK label, warnings)."""
    warnings: List[str] = []
    cleaned = labels.astype(str).str.strip()
    cleaned = cleaned[cleaned.ne("") & cleaned.str.lower().ne("nan")]
    counts = cleaned.value_counts()
    if len(counts) < 2:
        raise ValueError("The selected label column contains only one class; supervised analysis is impossible.")
    neg = str(negative_label or "").strip()
    pos = str(positive_label or "").strip()
    # The user names the two classes. Other values in the column are left out.
    if neg and pos:
        if neg.lower() == pos.lower():
            raise ValueError("PASS and FAIL must be different values.")
        lowered = {str(v).lower(): str(v) for v in counts.index}
        if pos.lower() not in lowered:
            raise ValueError(f"PASS value '{pos}' was not found in the selected column.")
        if neg.lower() not in lowered:
            raise ValueError(f"FAIL value '{neg}' was not found in the selected column.")
        pos = lowered[pos.lower()]
        neg = lowered[neg.lower()]
        low = cleaned.str.lower()
        other = int(len(cleaned) - int((low == pos.lower()).sum()) - int((low == neg.lower()).sum()))
        if other:
            warnings.append(
                f"{other:,} row(s) were excluded because their label is neither '{pos}' (PASS) nor '{neg}' (FAIL)."
            )
        return neg, pos, warnings
    if len(counts) > 2:
        raise ValueError(
            f"The selected label column contains {len(counts)} distinct values. "
            "Choose which value is PASS and which is FAIL."
        )
    values = [str(v) for v in counts.index[:2]]
    lowered = {v.lower(): v for v in values}
    auto_neg = next((orig for low, orig in lowered.items() if low in NEGATIVE_TOKENS), "")
    auto_pos = next((orig for low, orig in lowered.items() if low in POSITIVE_TOKENS), "")
    if auto_neg and auto_pos:
        return auto_neg, auto_pos, warnings
    minority = str(counts.index[-1])
    majority = str(counts.index[0])
    warnings.append(
        f"Pass/fail values were not recognized automatically. '{minority}' was assumed to be the "
        f"defect class and '{majority}' the good class — verify this before using the result."
    )
    return minority, majority, warnings


def _candidates(values: np.ndarray, limit: int = MAX_THRESHOLDS) -> np.ndarray:
    uniq = np.unique(values)
    if uniq.size <= 1:
        return uniq
    mids = (uniq[:-1] + uniq[1:]) / 2.0
    pts = np.concatenate(([uniq[0] - abs(uniq[0]) * 1e-6 - 1e-9], mids, [uniq[-1] + abs(uniq[-1]) * 1e-6 + 1e-9]))
    if pts.size > limit:
        qs = np.linspace(0, 100, limit)
        pts = np.unique(np.percentile(pts, qs))
    return pts


def _metrics(tp: np.ndarray, fp: np.ndarray, fn: np.ndarray, tn: np.ndarray, cost_fa: float, cost_fr: float):
    total = tp + fp + fn + tn
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(tp + fp > 0, tp / (tp + fp), 0.0)
        recall = np.where(tp + fn > 0, tp / (tp + fn), 0.0)
        specificity = np.where(tn + fp > 0, tn / (tn + fp), 0.0)
        f1 = np.where(precision + recall > 0, 2 * precision * recall / (precision + recall), 0.0)
        accuracy = np.where(total > 0, (tp + tn) / total, 0.0)
        far_total = np.where(total > 0, fn / total, 0.0)
        frr_total = np.where(total > 0, fp / total, 0.0)
        far_ng = np.where(tp + fn > 0, fn / (tp + fn), 0.0)
        frr_ok = np.where(tn + fp > 0, fp / (tn + fp), 0.0)
        yield_rate = np.where(total > 0, (tn + fn) / total, 0.0)
    youden = recall + specificity - 1.0
    cost = fp * cost_fr + fn * cost_fa
    return {
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "accuracy": accuracy,
        "false_accept_rate": far_total,
        "false_reject_rate": frr_total,
        "false_accept_rate_ng": far_ng,
        "false_reject_rate_ok": frr_ok,
        "yield": yield_rate,
        "youden": youden,
        "cost": cost,
    }


def _confusion_single(
    ng: np.ndarray,
    ok: np.ndarray,
    limit_type: str,
    lower: Optional[float],
    upper: Optional[float],
):
    """Confusion counts for one concrete limit configuration (NG = rejected)."""
    def below(arr, t):
        return int(np.searchsorted(arr, t, side="left"))

    def at_or_below(arr, t):
        return int(np.searchsorted(arr, t, side="right"))

    n_ng, n_ok = int(ng.size), int(ok.size)
    if limit_type == "lower":
        tp = below(ng, lower)
        fp = below(ok, lower)
    elif limit_type == "upper":
        tp = n_ng - at_or_below(ng, upper)
        fp = n_ok - at_or_below(ok, upper)
    else:
        tp = below(ng, lower) + (n_ng - at_or_below(ng, upper))
        fp = below(ok, lower) + (n_ok - at_or_below(ok, upper))
    fn = n_ng - tp
    tn = n_ok - fp
    return tp, fp, fn, tn


def _sweep(
    ng: np.ndarray,
    ok: np.ndarray,
    all_values: np.ndarray,
    limit_type: str,
    cost_fa: float,
    cost_fr: float,
) -> List[Dict[str, Any]]:
    pts = _candidates(all_values)
    if pts.size == 0:
        return []
    if limit_type == "two_sided":
        low_pts = _candidates(all_values[all_values <= np.median(all_values)], MAX_GRID)
        high_pts = _candidates(all_values[all_values >= np.median(all_values)], MAX_GRID)
        rows: List[Dict[str, Any]] = []
        for lo in low_pts:
            ng_lt = np.searchsorted(ng, lo, side="left")
            ok_lt = np.searchsorted(ok, lo, side="left")
            hi_valid = high_pts[high_pts > lo]
            if hi_valid.size == 0:
                continue
            ng_le_hi = np.searchsorted(ng, hi_valid, side="right")
            ok_le_hi = np.searchsorted(ok, hi_valid, side="right")
            tp = ng_lt + (ng.size - ng_le_hi)
            fp = ok_lt + (ok.size - ok_le_hi)
            fn = ng.size - tp
            tn = ok.size - fp
            m = _metrics(tp.astype(float), fp.astype(float), fn.astype(float), tn.astype(float), cost_fa, cost_fr)
            for i, hi in enumerate(hi_valid.tolist()):
                rows.append(
                    {
                        "lower": float(lo),
                        "upper": float(hi),
                        "threshold": float(hi),
                        "tp": int(tp[i]),
                        "fp": int(fp[i]),
                        "fn": int(fn[i]),
                        "tn": int(tn[i]),
                        **{k: float(v[i]) for k, v in m.items()},
                    }
                )
        return rows

    if limit_type == "lower":
        ng_c = np.searchsorted(ng, pts, side="left")
        ok_c = np.searchsorted(ok, pts, side="left")
        tp = ng_c.astype(float)
        fp = ok_c.astype(float)
    else:
        ng_c = np.searchsorted(ng, pts, side="right")
        ok_c = np.searchsorted(ok, pts, side="right")
        tp = (ng.size - ng_c).astype(float)
        fp = (ok.size - ok_c).astype(float)
    fn = ng.size - tp
    tn = ok.size - fp
    m = _metrics(tp, fp, fn, tn, cost_fa, cost_fr)
    rows = []
    for i, t in enumerate(pts.tolist()):
        rows.append(
            {
                "threshold": float(t),
                "lower": float(t) if limit_type == "lower" else None,
                "upper": float(t) if limit_type == "upper" else None,
                "tp": int(tp[i]),
                "fp": int(fp[i]),
                "fn": int(fn[i]),
                "tn": int(tn[i]),
                **{k: float(v[i]) for k, v in m.items()},
            }
        )
    return rows


def _auc(ng: np.ndarray, ok: np.ndarray, limit_type: str) -> Optional[float]:
    if limit_type == "two_sided" or ng.size == 0 or ok.size == 0:
        return None
    scores_ng = ng if limit_type == "upper" else -ng
    scores_ok = ok if limit_type == "upper" else -ok
    scores = np.concatenate([scores_ng, scores_ok])
    ranks = pd.Series(scores).rank().to_numpy()
    r_ng = float(ranks[: scores_ng.size].sum())
    n1, n0 = float(scores_ng.size), float(scores_ok.size)
    auc = (r_ng - n1 * (n1 + 1) / 2.0) / (n1 * n0)
    return _f(auc)


def _roc(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, float]]:
    pts = [
        {"fpr": 1.0 - float(r["specificity"]), "tpr": float(r["recall"]), "threshold": float(r["threshold"])}
        for r in rows
    ]
    pts.sort(key=lambda p: (p["fpr"], p["tpr"]))
    return [{"fpr": 0.0, "tpr": 0.0, "threshold": float("nan")}] + pts + [{"fpr": 1.0, "tpr": 1.0, "threshold": float("nan")}]


def _class_histograms(ng: np.ndarray, ok: np.ndarray, bins: int = 40) -> Dict[str, Any]:
    allv = np.concatenate([ng, ok])
    if allv.size == 0:
        return {"edges": [], "ok": [], "ng": [], "overlap_pct": None}
    edges = np.histogram_bin_edges(allv, bins=bins)
    ok_h, _ = np.histogram(ok, bins=edges)
    ng_h, _ = np.histogram(ng, bins=edges)
    ok_d = ok_h / max(ok.size, 1)
    ng_d = ng_h / max(ng.size, 1)
    overlap = float(np.minimum(ok_d, ng_d).sum() * 100.0)
    return {
        "edges": edges.tolist(),
        "ok": ok_h.tolist(),
        "ng": ng_h.tolist(),
        "ok_density": ok_d.tolist(),
        "ng_density": ng_d.tolist(),
        "overlap_pct": overlap,
    }


def statistical_limits(
    values: np.ndarray,
    limit_type: str = "two_sided",
    method: str = "percentile",
    percentile: float = 0.135,
    sigma: float = 3.0,
    iqr_k: float = 1.5,
) -> Dict[str, Any]:
    arr = values[np.isfinite(values)]
    st = calculate_stats(arr)
    if arr.size < 8:
        return {
            "method": method,
            "limit_type": limit_type,
            "lower": None,
            "upper": None,
            "n": int(arr.size),
            "warnings": ["Insufficient data for reliable statistical interpretation."],
            "stats": {k: _f(v) for k, v in st.items()},
        }
    method = (method or "percentile").lower()
    if method == "sigma":
        lower = st["mean"] - sigma * st["std"]
        upper = st["mean"] + sigma * st["std"]
        basis = f"mean ± {sigma:g}σ"
    elif method == "iqr":
        lower = st["q1"] - iqr_k * st["iqr"]
        upper = st["q3"] + iqr_k * st["iqr"]
        basis = f"Q1/Q3 ± {iqr_k:g} × IQR"
    elif method == "robust":
        median = st["median"]
        mad = float(np.median(np.abs(arr - median)))
        scaled = 1.4826 * mad
        lower = median - sigma * scaled
        upper = median + sigma * scaled
        basis = f"median ± {sigma:g} × 1.4826 × MAD"
    else:
        lower = float(np.percentile(arr, percentile))
        upper = float(np.percentile(arr, 100.0 - percentile))
        basis = f"{percentile:g}th / {100.0 - percentile:g}th percentile"
        method = "percentile"

    if limit_type == "upper":
        lower = None
    elif limit_type == "lower":
        upper = None

    out_low = int(np.sum(arr < lower)) if lower is not None else 0
    out_high = int(np.sum(arr > upper)) if upper is not None else 0
    n = int(arr.size)
    return {
        "method": method,
        "basis": basis,
        "limit_type": limit_type,
        "lower": _f(lower),
        "upper": _f(upper),
        "n": n,
        "below_lower": out_low,
        "above_upper": out_high,
        "out_of_limits": out_low + out_high,
        "out_of_limits_pct": (out_low + out_high) / n * 100.0,
        "stats": {k: _f(v) for k, v in st.items()},
        "warnings": [
            "No defect labels were provided. This is a statistical recommendation based on the "
            "distribution of the selected measurement. It has not been validated against actual "
            "defect results."
        ],
    }


def limit_finder(
    session: Session,
    measurement: str,
    label_col: str = "",
    negative_label: str = "",
    positive_label: str = "",
    limit_type: str = "upper",
    method: str = "youden",
    cost_false_accept: float = 10.0,
    cost_false_reject: float = 1.0,
    current_lower: Optional[float] = None,
    current_upper: Optional[float] = None,
    stat_method: str = "percentile",
) -> Dict[str, Any]:
    meta = column_meta(session, measurement)
    if meta is None:
        raise KeyError(f"Column '{measurement}' does not exist in the loaded dataset.")
    if meta["col_type"] not in ("numeric", "mixed"):
        raise ValueError(f"Limit Finder requires a numeric measurement; '{measurement}' is {meta['col_type']}.")
    limit_type = limit_type if limit_type in ("upper", "lower", "two_sided") else "upper"

    values = numeric_series(session, measurement)

    if not label_col:
        arr = values.to_numpy(dtype=np.float64)
        stat = statistical_limits(arr, limit_type=limit_type, method=stat_method)
        return {
            "mode": "statistical",
            "supervised": False,
            "measurement": measurement,
            "limit_type": limit_type,
            "statistical": stat,
            "recommended_lower": stat["lower"],
            "recommended_upper": stat["upper"],
            "optimization_method": f"Statistical ({stat.get('basis', stat['method'])})",
            "warnings": stat["warnings"],
            "insights": [
                "No pass/fail label column was selected, so the limit is derived from the "
                "measurement distribution only and is not a validated defect boundary.",
            ],
        }

    labels_raw = text_series(session, label_col)
    frame = pd.DataFrame({"v": values, "l": labels_raw}).dropna()
    if frame.empty:
        raise ValueError("No rows contain both the measurement and the label value.")
    frame["l"] = frame["l"].astype(str).str.strip()

    neg, pos, warnings = _resolve_classes(frame["l"], negative_label, positive_label)
    ng_vals = np.sort(frame.loc[frame["l"].str.lower() == neg.lower(), "v"].to_numpy(dtype=np.float64))
    ok_vals = np.sort(frame.loc[frame["l"].str.lower() == pos.lower(), "v"].to_numpy(dtype=np.float64))
    ng_vals = ng_vals[np.isfinite(ng_vals)]
    ok_vals = ok_vals[np.isfinite(ok_vals)]
    if ng_vals.size == 0 or ok_vals.size == 0:
        raise ValueError(
            f"Both classes must contain numeric measurements ('{neg}': {ng_vals.size}, '{pos}': {ok_vals.size})."
        )

    all_vals = np.sort(np.concatenate([ng_vals, ok_vals]))
    total = int(all_vals.size)
    minority_share = min(ng_vals.size, ok_vals.size) / total
    if min(ng_vals.size, ok_vals.size) < MIN_CLASS_SAMPLES:
        warnings.append(
            f"Small sample size: the smaller class has only {min(ng_vals.size, ok_vals.size)} "
            f"measurements. Treat the recommendation as indicative."
        )
    if minority_share < IMBALANCE_WARN:
        warnings.append(
            f"Classes are strongly imbalanced ({minority_share * 100:.1f}% minority). "
            "Accuracy is misleading; cost or Youden J optimization is preferred."
        )

    rows = _sweep(ng_vals, ok_vals, all_vals, limit_type, cost_false_accept, cost_false_reject)
    if not rows:
        raise ValueError("Could not evaluate thresholds for the selected measurement.")

    method = (method or "youden").lower()
    if method == "f1":
        best = max(rows, key=lambda r: (r["f1"], -r["cost"]))
        method_label = "Maximum F1 score"
    elif method == "cost":
        best = min(rows, key=lambda r: (r["cost"], -r["youden"]))
        method_label = (
            f"Minimum expected cost (false accept = {cost_false_accept:g}, "
            f"false reject = {cost_false_reject:g})"
        )
    elif method == "accuracy":
        best = max(rows, key=lambda r: (r["accuracy"], -r["cost"]))
        method_label = "Maximum accuracy"
    else:
        best = max(rows, key=lambda r: (r["youden"], -r["cost"]))
        method_label = "Youden J (sensitivity + specificity − 1)"
        method = "youden"

    current = None
    if current_lower is not None or current_upper is not None:
        tp, fp, fn, tn = _confusion_single(ng_vals, ok_vals, limit_type, current_lower, current_upper)
        m = _metrics(
            np.array([tp], dtype=float),
            np.array([fp], dtype=float),
            np.array([fn], dtype=float),
            np.array([tn], dtype=float),
            cost_false_accept,
            cost_false_reject,
        )
        current = {
            "lower": current_lower,
            "upper": current_upper,
            "threshold": current_upper if limit_type != "lower" else current_lower,
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            **{k: float(v[0]) for k, v in m.items()},
        }

    auc = _auc(ng_vals, ok_vals, limit_type)
    roc = _roc(rows) if limit_type != "two_sided" else []
    hist = _class_histograms(ng_vals, ok_vals)
    stat = statistical_limits(all_vals, limit_type=limit_type, method=stat_method)

    insights: List[str] = [
        f"{total:,} labelled measurements: {ok_vals.size:,} '{pos}' and {ng_vals.size:,} '{neg}'.",
    ]
    if limit_type == "two_sided":
        insights.append(
            f"Recommended limits: {best['lower']:.4g} … {best['upper']:.4g} ({method_label})."
        )
    else:
        insights.append(f"Recommended limit: {best['threshold']:.4g} ({method_label}).")
    insights.append(
        f"At this limit {best['recall'] * 100:.1f}% of '{neg}' units are detected and "
        f"{best['specificity'] * 100:.1f}% of '{pos}' units are accepted."
    )
    insights.append(
        f"False accept {best['fn']:,} unit(s) ({best['false_accept_rate'] * 100:.2f}% of all units); "
        f"false reject {best['fp']:,} unit(s) ({best['false_reject_rate'] * 100:.2f}%)."
    )
    if auc is not None:
        insights.append(
            f"Separation quality AUC = {auc:.3f}"
            + (" (weak separation between classes)." if auc < 0.7 else ".")
        )
    if hist.get("overlap_pct") is not None:
        insights.append(f"Class distributions overlap by about {hist['overlap_pct']:.0f}%.")
    if current is not None:
        delta_fa = current["fn"] - best["fn"]
        delta_fr = current["fp"] - best["fp"]
        insights.append(
            f"Compared to the current limit: {-delta_fa:+,} false accepts and {-delta_fr:+,} false rejects."
        )

    # Keep the payload small enough for the UI while staying representative.
    table = rows
    if len(table) > MAX_THRESHOLDS:
        step = int(math.ceil(len(table) / MAX_THRESHOLDS))
        table = table[::step]

    return {
        "mode": "supervised",
        "supervised": True,
        "measurement": measurement,
        "label_col": label_col,
        "negative_label": neg,
        "positive_label": pos,
        "limit_type": limit_type,
        "optimization_method": method_label,
        "method": method,
        "costs": {"false_accept": cost_false_accept, "false_reject": cost_false_reject},
        "class_counts": {pos: int(ok_vals.size), neg: int(ng_vals.size)},
        "n": total,
        "recommended": best,
        "recommended_lower": best.get("lower"),
        "recommended_upper": best.get("upper"),
        "current": current,
        "thresholds": table,
        "roc": roc,
        "auc": auc,
        "boundary": hist,
        "statistical": stat,
        "warnings": warnings,
        "insights": insights,
        "value_range": {"min": _f(all_vals.min()), "max": _f(all_vals.max())},
    }


def evaluate_threshold(
    session: Session,
    measurement: str,
    label_col: str,
    limit_type: str = "upper",
    lower: Optional[float] = None,
    upper: Optional[float] = None,
    negative_label: str = "",
    positive_label: str = "",
    cost_false_accept: float = 10.0,
    cost_false_reject: float = 1.0,
) -> Dict[str, Any]:
    """Metrics for one user-chosen threshold (slider interaction)."""
    values = numeric_series(session, measurement)
    labels = text_series(session, label_col)
    frame = pd.DataFrame({"v": values, "l": labels}).dropna()
    frame["l"] = frame["l"].astype(str).str.strip()
    neg, pos, warnings = _resolve_classes(frame["l"], negative_label, positive_label)
    ng = np.sort(frame.loc[frame["l"].str.lower() == neg.lower(), "v"].to_numpy(dtype=np.float64))
    ok = np.sort(frame.loc[frame["l"].str.lower() == pos.lower(), "v"].to_numpy(dtype=np.float64))
    tp, fp, fn, tn = _confusion_single(ng, ok, limit_type, lower, upper)
    m = _metrics(
        np.array([tp], dtype=float),
        np.array([fp], dtype=float),
        np.array([fn], dtype=float),
        np.array([tn], dtype=float),
        cost_false_accept,
        cost_false_reject,
    )
    return {
        "lower": lower,
        "upper": upper,
        "limit_type": limit_type,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "rejected": tp + fp,
        "missed_defects": fn,
        **{k: float(v[0]) for k, v in m.items()},
        "warnings": warnings,
    }
