"""Distribution analysis engine — schema-agnostic numeric column analysis."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

SUPPORTED_EXTS = (".xlsx", ".xls", ".csv", ".xlsm")
MAX_PREVIEW_ROWS = 5000
MAX_GROUP_KEYS = 40


@dataclass
class FileInfo:
    path: str
    size: int

    @property
    def name(self) -> str:
        return os.path.basename(self.path)


@dataclass
class ColumnInfo:
    name: str
    dtype: str  # numeric | text | date | mixed
    file_count: int
    numeric_hits: int = 0
    unique_approx: int = 0  # approx distinct values seen in schema samples
    sample_rows: int = 0


@dataclass
class AnalysisResult:
    column: str
    values: np.ndarray
    file_ids: np.ndarray
    sheet_ids: np.ndarray
    file_names: List[str]
    sheet_names: List[str]
    stats: Dict[str, float]
    outlier_mask: np.ndarray
    hist_counts: np.ndarray
    hist_edges: np.ndarray
    summary_lines: List[str]
    files_total: int
    files_with_column: int
    files_missing_column: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    group_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    mode: str = "overall"


def format_size(num_bytes: int) -> str:
    mb = num_bytes / (1024 * 1024)
    if mb >= 100:
        return f"{mb:.0f} MB"
    if mb >= 1:
        return f"{mb:.1f} MB"
    kb = num_bytes / 1024
    if kb >= 1:
        return f"{kb:.0f} KB"
    return f"{num_bytes} B"


def scan_files(
    folder: str = "",
    files: Optional[Sequence[str]] = None,
    extensions: Optional[Sequence[str]] = None,
    recursive: bool = True,
) -> List[FileInfo]:
    exts = tuple((extensions or SUPPORTED_EXTS))
    found: List[FileInfo] = []
    if files:
        for path in files:
            if os.path.isfile(path) and path.lower().endswith(exts):
                try:
                    found.append(FileInfo(path=path, size=os.path.getsize(path)))
                except OSError:
                    found.append(FileInfo(path=path, size=0))
        return sorted(found, key=lambda f: f.path.lower())

    if not folder or not os.path.isdir(folder):
        return []

    if recursive:
        walker = os.walk(folder)
    else:
        try:
            names = os.listdir(folder)
        except OSError:
            names = []
        walker = [(folder, [], names)]

    for root, _dirs, names in walker:
        for name in names:
            if not name.lower().endswith(exts):
                continue
            path = os.path.join(root, name)
            try:
                found.append(FileInfo(path=path, size=os.path.getsize(path)))
            except OSError:
                found.append(FileInfo(path=path, size=0))
    return sorted(found, key=lambda f: f.path.lower())


def _infer_series_dtype(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "text"
    # numeric?
    numeric = pd.to_numeric(non_null, errors="coerce")
    num_ok = float(numeric.notna().mean())
    if num_ok >= 0.8:
        return "numeric"
    # datetime? only if strings look date-like (avoid classifying "A"/"Camera1" as dates)
    sample = non_null.astype(str).head(30)
    date_like = sample.str.contains(
        r"\d{1,4}[-/.]\d{1,2}(?:[-/.]\d{1,4})?|\d{1,2}:\d{2}",
        regex=True,
        na=False,
    ).mean()
    if date_like >= 0.5:
        try:
            with pd.option_context("mode.chained_assignment", None):
                parsed = pd.to_datetime(non_null, errors="coerce", dayfirst=True, format="mixed")
            if float(parsed.notna().mean()) >= 0.8:
                return "date"
        except Exception:
            try:
                parsed = pd.to_datetime(non_null, errors="coerce", dayfirst=True)
                if float(parsed.notna().mean()) >= 0.8:
                    return "date"
            except Exception:
                pass
    return "text"


def _iter_frames(path: str) -> Iterable[Tuple[str, pd.DataFrame]]:
    lower = path.lower()
    read_kwargs = {"keep_default_na": False, "na_values": [""]}
    if lower.endswith(".csv"):
        yield "CSV", pd.read_csv(path, **read_kwargs)
        return
    xl = pd.ExcelFile(path)
    for sheet in xl.sheet_names:
        yield sheet, pd.read_excel(path, sheet_name=sheet, **read_kwargs)


def detect_schema(
    files: Sequence[FileInfo],
    progress: Optional[Callable[[int, int, str], None]] = None,
    stop_event=None,
    sample_rows: int = 200,
) -> Tuple[List[ColumnInfo], List[str]]:
    """Inspect columns across files without loading full datasets."""
    col_meta: Dict[str, Dict[str, object]] = {}
    errors: List[str] = []
    total = len(files)

    for i, fi in enumerate(files, 1):
        if stop_event is not None and stop_event.is_set():
            break
        if progress:
            progress(i - 1, total, fi.name)
        try:
            if fi.path.lower().endswith(".csv"):
                df = pd.read_csv(fi.path, nrows=sample_rows, keep_default_na=False, na_values=[""])
                frames = [("CSV", df)]
            else:
                xl = pd.ExcelFile(fi.path)
                frames = []
                for sheet in xl.sheet_names[:3]:
                    frames.append(
                        (
                            sheet,
                            pd.read_excel(
                                fi.path, sheet_name=sheet, nrows=sample_rows,
                                keep_default_na=False, na_values=[""],
                            ),
                        )
                    )
            seen_in_file = set()
            for _sheet, df in frames:
                for col in df.columns:
                    name = str(col)
                    seen_in_file.add(name)
                    meta = col_meta.setdefault(
                        name,
                        {
                            "files": 0,
                            "numeric": 0,
                            "text": 0,
                            "date": 0,
                            "uniques": set(),
                            "rows": 0,
                        },
                    )
                    dtype = _infer_series_dtype(df[col])
                    meta[dtype] = int(meta.get(dtype, 0)) + 1
                    series = df[col].dropna().astype(str).head(sample_rows)
                    uniq: set = meta["uniques"]  # type: ignore[assignment]
                    for v in series.tolist():
                        if len(uniq) < 500:
                            uniq.add(v)
                    meta["rows"] = int(meta["rows"]) + int(len(series))
            for name in seen_in_file:
                col_meta[name]["files"] = int(col_meta[name]["files"]) + 1
        except Exception as e:
            errors.append(f"Could not read {fi.name}: {e}")

    columns: List[ColumnInfo] = []
    for name, meta in col_meta.items():
        votes = {
            "numeric": int(meta.get("numeric", 0)),
            "date": int(meta.get("date", 0)),
            "text": int(meta.get("text", 0)),
        }
        dtype = max(votes, key=votes.get)
        if votes["numeric"] and votes["numeric"] >= max(votes["text"], votes["date"]):
            dtype = "numeric"
        uniq = meta.get("uniques") or set()
        columns.append(
            ColumnInfo(
                name=name,
                dtype=dtype,
                file_count=int(meta["files"]),
                numeric_hits=int(meta.get("numeric", 0)),
                unique_approx=len(uniq) if isinstance(uniq, set) else 0,
                sample_rows=int(meta.get("rows", 0)),
            )
        )

    # Prefer numeric, then by file coverage, then name
    columns.sort(key=lambda c: (-int(c.dtype == "numeric"), -c.file_count, c.name.lower()))
    if progress:
        progress(total, total, "")
    return columns, errors


def _to_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        if pd.isna(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (bool, np.bool_)):
        return None
    if isinstance(val, (int, float, np.integer, np.floating)):
        f = float(val)
        if np.isfinite(f):
            return f
        return None
    text = str(val).strip().replace(",", ".")
    if not text or text.lower() in ("nan", "none", "null", "-", "n/a"):
        return None
    try:
        f = float(text)
        return f if np.isfinite(f) else None
    except ValueError:
        return None


def calculate_stats(values: np.ndarray) -> Dict[str, float]:
    empty = {
        "count": 0, "mean": float("nan"), "median": float("nan"),
        "std": float("nan"), "min": float("nan"), "max": float("nan"),
        "p5": float("nan"), "p25": float("nan"), "p75": float("nan"), "p95": float("nan"),
        "q1": float("nan"), "q3": float("nan"), "iqr": float("nan"),
        "skew": float("nan"), "kurtosis": float("nan"), "variance": float("nan"),
        "excluded": 0,
    }
    if values.size == 0:
        return empty
    finite = values[np.isfinite(values)]
    excluded = int(values.size - finite.size)
    if finite.size == 0:
        empty["excluded"] = excluded
        return empty
    q1, q3 = np.percentile(finite, [25, 75])
    iqr = float(q3 - q1)
    mean = float(np.mean(finite))
    median = float(np.median(finite))
    std = float(np.std(finite, ddof=1)) if finite.size > 1 else 0.0
    var = float(np.var(finite, ddof=1)) if finite.size > 1 else 0.0
    if std > 0:
        z = (finite - mean) / std
        skew = float(np.mean(z ** 3))
        kurtosis = float(np.mean(z ** 4) - 3.0)
    else:
        skew = 0.0
        kurtosis = 0.0
    return {
        "count": float(finite.size),
        "mean": mean,
        "median": median,
        "std": std,
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "p5": float(np.percentile(finite, 5)),
        "p25": float(q1),
        "p75": float(q3),
        "p95": float(np.percentile(finite, 95)),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": iqr,
        "skew": skew,
        "kurtosis": kurtosis,
        "variance": var,
        "excluded": float(excluded),
    }


def outlier_mask_iqr(values: np.ndarray, stats: Optional[Dict[str, float]] = None) -> np.ndarray:
    if values.size == 0:
        return np.array([], dtype=bool)
    st = stats or calculate_stats(values)
    q1, q3, iqr = st["q1"], st["q3"], st["iqr"]
    if not np.isfinite(iqr) or iqr == 0:
        return np.zeros(values.shape, dtype=bool)
    low = q1 - 1.5 * iqr
    high = q3 + 1.5 * iqr
    return (values < low) | (values > high)


def build_histogram(values: np.ndarray, bins: int = 50) -> Tuple[np.ndarray, np.ndarray]:
    if values.size == 0:
        return np.array([]), np.array([])
    bins = max(5, min(int(bins or 50), 200))
    counts, edges = np.histogram(values, bins=bins)
    return counts.astype(float), edges.astype(float)


def generate_summary_from_values(
    column: str,
    values: np.ndarray,
    stats: Dict[str, float],
    outlier_count: int,
    files_with: int,
    files_total: int,
    spec: Optional[Dict[str, Any]] = None,
    group_stats: Optional[Dict[str, Dict[str, float]]] = None,
) -> List[str]:
    lines: List[str] = []
    n = int(stats.get("count") or 0)
    if n == 0:
        return [f"No numeric values found for column '{column}'."]
    if n < 8:
        lines.append("Insufficient data for reliable statistical interpretation.")
        return lines

    lines.append(
        f"Mean value is {stats['mean']:.4g} and median is {stats['median']:.4g}."
    )
    p5, p95 = stats["p5"], stats["p95"]
    lines.append(f"Most values are concentrated between {p5:.3g} and {p95:.3g}.")

    skew = stats.get("skew", 0.0)
    if abs(skew) < 0.2:
        lines.append("The distribution is approximately symmetric.")
    elif skew > 0:
        lines.append("The distribution is slightly right-skewed.")
    else:
        lines.append("The distribution is slightly left-skewed.")

    excluded = int(stats.get("excluded") or 0)
    if excluded:
        lines.append(f"{excluded} non-numeric / invalid value(s) were excluded.")
    lines.append(f"{outlier_count} potential outlier(s) detected (outside 1.5 × IQR).")
    if files_with < files_total:
        lines.append(f"Column '{column}' found in {files_with} of {files_total} files.")
    if spec and spec.get("enabled"):
        lines.append(
            f"{spec['pass_pct']:.1f}% of values are in specification; "
            f"{spec['fail_pct']:.1f}% are outside limits."
        )
    if group_stats:
        ranked = sorted(
            group_stats.items(),
            key=lambda kv: (kv[1].get("mean") is None, -(kv[1].get("mean") or float("-inf"))),
        )
        if ranked and ranked[0][1].get("count", 0) >= 3:
            top = ranked[0]
            lines.append(
                f"Group '{top[0]}' has the highest average ({top[1]['mean']:.4g})."
            )
    return lines


def run_distribution_analysis(
    files: Sequence[FileInfo],
    column: str,
    bins: int = 50,
    group_by: str = "",
    mode: str = "overall",
    progress: Optional[Callable[[int, int, int, str], None]] = None,
    stop_event=None,
    lsl: Optional[float] = None,
    usl: Optional[float] = None,
) -> AnalysisResult:
    """
    Extract numeric values for `column` across files.
    progress(files_done, files_total, values_so_far, current_file)
    """
    values: List[float] = []
    file_ids: List[int] = []
    sheet_ids: List[int] = []
    file_names: List[str] = []
    sheet_names: List[str] = []
    file_index: Dict[str, int] = {}
    sheet_index: Dict[str, int] = {}
    group_values: Dict[str, List[float]] = {}

    errors: List[str] = []
    warnings: List[str] = []
    files_with = 0
    files_missing = 0
    total = len(files)

    for i, fi in enumerate(files, 1):
        if stop_event is not None and stop_event.is_set():
            warnings.append("Analysis cancelled by user.")
            break
        if progress:
            progress(i - 1, total, len(values), fi.name)

        try:
            frames = list(_iter_frames(fi.path))
        except Exception as e:
            errors.append(f"Could not read {fi.name}: {e}")
            files_missing += 1
            continue

        found_col = False
        for sheet, df in frames:
            if stop_event is not None and stop_event.is_set():
                break
            cols = {str(c): c for c in df.columns}
            if column not in cols:
                continue
            found_col = True
            series = df[cols[column]]
            group_series = None
            if group_by and group_by in cols:
                group_series = df[cols[group_by]]

            if fi.path not in file_index:
                file_index[fi.path] = len(file_names)
                file_names.append(fi.name)
            fid = file_index[fi.path]
            if sheet not in sheet_index:
                sheet_index[sheet] = len(sheet_names)
                sheet_names.append(sheet)
            sid = sheet_index[sheet]

            for idx, raw in enumerate(series.tolist()):
                num = _to_float(raw)
                if num is None:
                    continue
                values.append(num)
                file_ids.append(fid)
                sheet_ids.append(sid)
                if group_by == "__file__":
                    gkey = fi.name
                    if len(group_values) < MAX_GROUP_KEYS or gkey in group_values:
                        group_values.setdefault(gkey, []).append(num)
                elif group_series is not None:
                    graw = group_series.iloc[idx] if idx < len(group_series) else ""
                    gkey = str(graw).strip() if graw is not None and str(graw).lower() != "nan" else "(empty)"
                    if len(group_values) < MAX_GROUP_KEYS or gkey in group_values:
                        group_values.setdefault(gkey, []).append(num)

        if found_col:
            files_with += 1
        else:
            files_missing += 1

    if progress:
        progress(total, total, len(values), "")

    arr = np.asarray(values, dtype=np.float64)
    fids = np.asarray(file_ids, dtype=np.int32)
    sids = np.asarray(sheet_ids, dtype=np.int32)
    stats = calculate_stats(arr)
    mask = outlier_mask_iqr(arr, stats)
    counts, edges = build_histogram(arr, bins=bins)
    outlier_count = int(np.sum(mask)) if mask.size else 0
    spec = None
    try:
        from schema_engine import spec_limits_result

        spec = spec_limits_result(stats, arr, lsl, usl)
    except Exception:
        spec = None
    summary = generate_summary_from_values(
        column, arr, stats, outlier_count, files_with, total,
        spec=spec, group_stats=None,
    )

    if files_missing and files_with:
        warnings.append(
            f"{files_missing} file(s) did not contain column '{column}'."
        )
    if group_by:
        # files missing group column — counted as empty groups only
        if not group_values and arr.size:
            warnings.append(
                f"Grouping column '{group_by}' was missing or empty in analyzed rows."
            )
        elif len(group_values) > MAX_GROUP_KEYS:
            # High cardinality — usually means a measurement column was used as group-by
            warnings.append(
                f"Group by '{group_by}' produced {len(group_values)} groups "
                f"(showing top {MAX_GROUP_KEYS}). Prefer categorical / low-cardinality columns."
            )

    gstats: Dict[str, Dict[str, float]] = {}
    # Prefer larger groups first so truncated high-cardinality results stay useful
    ranked = sorted(group_values.items(), key=lambda kv: -len(kv[1]))[:MAX_GROUP_KEYS]
    for key, vals in ranked:
        arr_g = np.asarray(vals, dtype=np.float64)
        gst = calculate_stats(arr_g)
        gmask = outlier_mask_iqr(arr_g, gst)
        gst["outlier_count"] = float(int(np.sum(gmask))) if gmask.size else 0.0
        gstats[key] = gst

    if spec and spec.get("enabled"):
        # already in summary via first pass; refresh with group insight
        pass
    summary = generate_summary_from_values(
        column, arr, stats, outlier_count, files_with, total,
        spec=spec, group_stats=gstats or None,
    )

    return AnalysisResult(
        column=column,
        values=arr,
        file_ids=fids,
        sheet_ids=sids,
        file_names=file_names,
        sheet_names=sheet_names,
        stats=stats,
        outlier_mask=mask,
        hist_counts=counts,
        hist_edges=edges,
        summary_lines=summary,
        files_total=total,
        files_with_column=files_with,
        files_missing_column=files_missing,
        errors=errors,
        warnings=warnings,
        group_stats=gstats,
        mode=mode,
    )


def preview_records(
    result: AnalysisResult,
    outliers_only: bool = False,
    limit: int = MAX_PREVIEW_ROWS,
) -> List[Dict[str, object]]:
    if result.values.size == 0:
        return []
    mask = result.outlier_mask if outliers_only else np.ones(result.values.shape, dtype=bool)
    idxs = np.flatnonzero(mask)
    if idxs.size > limit:
        idxs = idxs[:limit]
    rows = []
    for n, i in enumerate(idxs, 1):
        rows.append({
            "#": n,
            "File name": result.file_names[int(result.file_ids[i])],
            "Sheet name": result.sheet_names[int(result.sheet_ids[i])],
            result.column: float(result.values[i]),
            "Outlier": bool(result.outlier_mask[i]),
        })
    return rows


def export_records_df(
    result: AnalysisResult,
    outliers_only: bool = False,
) -> pd.DataFrame:
    rows = preview_records(result, outliers_only=outliers_only, limit=10_000_000)
    return pd.DataFrame(rows)
