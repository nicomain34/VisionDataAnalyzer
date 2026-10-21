"""Persistent analysis session: load a dataset once, reuse it for every module.

The engine process is long-lived (spawned by the Tauri shell), so datasets are
cached here instead of being re-read by each analysis page.
"""

from __future__ import annotations

import hashlib
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

from distribution_engine import FileInfo, _iter_frames, calculate_stats, format_size
from schema_engine import grouping_suitable

DEFAULT_MAX_ROWS = 1_500_000
EMPTY_TOKENS = {"", "nan", "none", "null", "n/a", "na", "-", "#n/a", "#value!", "#ref!"}
UNNAMED_RE = re.compile(r"^unnamed(:|\s)?\s*\d*$", re.IGNORECASE)
METADATA_RE = re.compile(r"(^#)|(https?://)|(^\s*source\s*:)", re.IGNORECASE)
BINARY_ARTIFACT_RE = re.compile(r"^(class|label|col|column|field|var)[\s_\-]?\d+$", re.IGNORECASE)
DATE_LIKE_RE = re.compile(r"\d{1,4}[-/.]\d{1,2}(?:[-/.]\d{1,4})?|\d{1,2}:\d{2}")
# Vision logs write 2026-10-0700-11-52: date and clock glued together, clock separated by '-'.
COMPACT_TS_RE = re.compile(
    r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\s*(\d{2})[-:.](\d{2})[-:.](\d{2})(\.\d+)?$"
)

POSITIVE_TOKENS = {"ok", "pass", "passed", "good", "accept", "accepted", "true", "yes", "1", "p", "g"}
NEGATIVE_TOKENS = {"ng", "nok", "fail", "failed", "bad", "defect", "defective", "reject", "rejected", "false", "no", "0", "f"}

FILE_COL = "__file"
SHEET_COL = "__sheet"
META_COLS = (FILE_COL, SHEET_COL)


@dataclass
class Session:
    key: str
    source_folder: str
    source_files: List[str]
    frame: pd.DataFrame
    profile: Dict[str, Any]
    results: Dict[str, Any] = field(default_factory=dict)


_SESSIONS: Dict[str, Session] = {}
_LOCK = threading.Lock()


def _signature(folder: str, paths: Sequence[str], max_rows: int) -> str:
    h = hashlib.sha1()
    h.update(folder.encode("utf-8", "ignore"))
    h.update(str(max_rows).encode())
    for p in sorted(paths):
        h.update(p.encode("utf-8", "ignore"))
        try:
            st = os.stat(p)
            h.update(str(int(st.st_mtime)).encode())
            h.update(str(st.st_size).encode())
        except OSError:
            pass
    return h.hexdigest()[:16]


def _missing_mask(series: pd.Series) -> pd.Series:
    mask = series.isna()
    if series.dtype == object:
        try:
            lowered = series.where(~mask).map(
                lambda v: str(v).strip().lower() if isinstance(v, str) else v
            )
            mask = mask | lowered.isin(EMPTY_TOKENS)
        except Exception:
            pass
    return mask


def parse_timestamps(series: pd.Series) -> pd.Series:
    """Parse a column to datetimes, including the compact vision timestamp format."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    text = series.astype("string").str.strip()
    normalized = text.str.replace(COMPACT_TS_RE, r"\1-\2-\3 \4:\5:\6\7", regex=True)
    try:
        return pd.to_datetime(normalized, errors="coerce", dayfirst=True, format="mixed")
    except (TypeError, ValueError):
        return pd.to_datetime(normalized, errors="coerce", dayfirst=True)


def _looks_datetime(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    sample = series.dropna().head(200)
    if sample.empty:
        return False
    as_text = sample.astype(str)
    if float(as_text.str.contains(DATE_LIKE_RE, regex=True, na=False).mean()) < 0.6:
        return False
    try:
        parsed = parse_timestamps(sample)
    except Exception:
        return False
    return float(parsed.notna().mean()) >= 0.8


def _bool_hits(series: pd.Series) -> int:
    sample = series.dropna().head(500)
    if sample.empty:
        return 0
    try:
        lowered = sample.astype(str).str.strip().str.lower()
    except Exception:
        return 0
    hits = int(lowered.isin(POSITIVE_TOKENS | NEGATIVE_TOKENS).sum())
    return int(hits * (len(series.dropna()) / max(len(sample), 1)))


def classify(
    dtype_vote: str,
    unique_count: int,
    non_missing: int,
    bool_hits: int,
    integer_like: bool,
) -> str:
    """Column type from value shape. High-cardinality floats stay measurements."""
    if dtype_vote == "date":
        return "datetime"
    if non_missing == 0:
        return "empty"
    unique_ratio = unique_count / max(non_missing, 1)
    if dtype_vote == "numeric":
        if unique_count <= 2 and bool_hits >= max(1, int(0.8 * non_missing)):
            return "boolean"
        # Only discrete integer codes can be identifiers; float measurements are not.
        if integer_like and non_missing >= 20 and unique_ratio > 0.95:
            return "identifier"
        return "numeric"
    if bool_hits >= max(1, int(0.8 * non_missing)) and unique_count <= 2:
        return "boolean"
    if unique_count <= max(2, min(60, int(0.35 * non_missing))):
        return "categorical"
    if non_missing >= 20 and unique_ratio > 0.9:
        return "identifier"
    return "text"


def _column_quality(
    name: str,
    col_type: str,
    valid_ratio: float,
    unique_count: int,
    non_missing: int,
) -> Dict[str, Any]:
    """Decide whether a column is a meaningful engineering analysis candidate."""
    reason = ""
    usable = True
    clean = (name or "").strip()
    if not clean or UNNAMED_RE.match(clean):
        usable, reason = False, "Unnamed / import artifact column"
    elif METADATA_RE.search(clean):
        usable, reason = False, "Source metadata / comment column"
    elif col_type == "empty" or non_missing == 0:
        usable, reason = False, "Column is empty"
    elif valid_ratio < 0.5:
        usable, reason = False, f"Only {valid_ratio * 100:.0f}% of rows contain a value"
    elif col_type == "mixed":
        usable, reason = False, "Mixed data types"
    elif col_type == "identifier":
        usable, reason = False, "Identifier-like column"
    elif BINARY_ARTIFACT_RE.match(clean) and unique_count <= 2:
        usable, reason = False, "Binary encoding artifact"

    if col_type == "numeric" and usable and unique_count <= 2:
        usable, reason = False, "Numeric column with only two distinct values"

    role = "excluded"
    if usable:
        if col_type == "numeric":
            role = "measurement"
        elif col_type == "datetime":
            role = "datetime"
        elif col_type in ("categorical", "boolean"):
            role = "grouping"
        elif col_type == "text":
            role = "grouping" if unique_count <= 40 else "text"
    return {"usable_for_analysis": usable, "reason_excluded": reason, "analysis_role": role}


def _label_info(series: pd.Series, missing: pd.Series) -> Dict[str, Any]:
    """Detect binary OK/NG style label columns without hardcoding column names."""
    values = series[~missing]
    if values.empty:
        return {"is_label_candidate": False}
    try:
        text = values.astype(str).str.strip()
    except Exception:
        return {"is_label_candidate": False}
    counts = text.value_counts()
    if len(counts) != 2:
        return {"is_label_candidate": False}
    a, b = [str(v) for v in counts.index[:2]]
    la, lb = a.lower(), b.lower()
    negative = None
    positive = None
    if la in NEGATIVE_TOKENS and lb in POSITIVE_TOKENS:
        negative, positive = a, b
    elif lb in NEGATIVE_TOKENS and la in POSITIVE_TOKENS:
        negative, positive = b, a
    return {
        "is_label_candidate": True,
        "label_values": [a, b],
        "label_counts": [int(counts.iloc[0]), int(counts.iloc[1])],
        "negative_label": negative,
        "positive_label": positive,
        "labels_recognized": negative is not None and positive is not None,
    }


def build_profile(
    frame: pd.DataFrame,
    file_presence: Dict[str, int],
    files_scanned: int,
    valid_files: int,
    failed: List[str],
    issues: List[Dict[str, Any]],
    truncated: bool,
    total_rows_read: int,
    applicable_rows: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    columns: List[Dict[str, Any]] = []
    type_counts: Dict[str, int] = {}
    missing_cells = 0
    total_cells = 0
    invalid_total = 0

    data_cols = [c for c in frame.columns if c not in META_COLS]
    rows = int(len(frame))

    for col in data_cols:
        series = frame[col]
        missing = _missing_mask(series)
        # A column that only exists in some files must not look "mostly empty":
        # rate it against the rows of the files that actually contain it.
        scope = int((applicable_rows or {}).get(str(col), rows)) or rows
        non_missing = rows - int(missing.sum())
        miss_n = max(0, scope - non_missing)
        missing_cells += miss_n
        total_cells += scope
        values = series[~missing]

        numeric = pd.to_numeric(values, errors="coerce")
        numeric_ok = int(numeric.notna().sum())
        numeric_ratio = (numeric_ok / non_missing) if non_missing else 0.0
        invalid_numeric = 0
        integer_like = False
        if numeric_ratio >= 0.8:
            invalid_numeric = int(non_missing - numeric_ok)
            dtype_vote = "numeric"
            valid_nums = numeric.dropna()
            if not valid_nums.empty:
                integer_like = bool(np.all(np.mod(valid_nums.to_numpy(dtype=np.float64), 1) == 0))
        elif _looks_datetime(values):
            dtype_vote = "date"
        else:
            dtype_vote = "text"
        invalid_total += invalid_numeric

        try:
            unique_count = int(values.nunique(dropna=True))
        except Exception:
            unique_count = 0

        bool_hits = _bool_hits(values) if dtype_vote != "date" else 0
        col_type = classify(dtype_vote, unique_count, non_missing, bool_hits, integer_like)
        if dtype_vote == "numeric" and invalid_numeric and invalid_numeric > 0.2 * max(non_missing, 1):
            col_type = "mixed"

        stats: Dict[str, float] = {}
        if dtype_vote == "numeric" and numeric_ok:
            arr = numeric.dropna().to_numpy(dtype=np.float64)
            stats = calculate_stats(arr)

        valid_ratio = (non_missing / scope) if scope else 0.0
        quality = _column_quality(str(col), col_type, valid_ratio, unique_count, non_missing)
        label = _label_info(series, missing) if col_type in ("categorical", "boolean", "text") else {"is_label_candidate": False}

        item: Dict[str, Any] = {
            "name": str(col),
            "dtype": dtype_vote,
            "col_type": col_type,
            "file_count": int(file_presence.get(str(col), 0)),
            "count": non_missing,
            "unique_approx": unique_count,
            "cardinality": unique_count,
            "sample_rows": rows,
            "rows_applicable": scope,
            "missing": miss_n,
            "missing_pct": (miss_n / scope * 100.0) if scope else 0.0,
            "invalid_numeric": invalid_numeric,
            "valid_ratio": valid_ratio,
            "min": stats.get("min"),
            "max": stats.get("max"),
            "mean": stats.get("mean"),
            "median": stats.get("median"),
            "std": stats.get("std"),
            "grouping_suitable": grouping_suitable(col_type, unique_count, non_missing)
            and quality["usable_for_analysis"],
        }
        item.update(quality)
        item.update(label)
        columns.append(item)
        type_counts[col_type] = type_counts.get(col_type, 0) + 1

        if invalid_numeric:
            issues.append(
                {
                    "severity": "WARNING",
                    "file": "*",
                    "column": str(col),
                    "issue": "Invalid numeric values",
                    "count": invalid_numeric,
                    "details": "Values could not be parsed as numbers",
                }
            )
        if scope and miss_n / scope > 0.2:
            issues.append(
                {
                    "severity": "WARNING",
                    "file": "*",
                    "column": str(col),
                    "issue": "High missing rate",
                    "count": miss_n,
                    "details": f"{item['missing_pct']:.1f}% of rows have no value",
                }
            )
        if col_type == "mixed":
            issues.append(
                {
                    "severity": "WARNING",
                    "file": "*",
                    "column": str(col),
                    "issue": "Mixed data types",
                    "count": invalid_numeric or non_missing,
                    "details": "Column mixes numbers and text",
                }
            )
        if files_scanned > 1 and 0 < item["file_count"] < files_scanned:
            issues.append(
                {
                    "severity": "INFO",
                    "file": "*",
                    "column": str(col),
                    "issue": "Schema inconsistency",
                    "count": files_scanned - item["file_count"],
                    "details": f"Available in {item['file_count']} of {files_scanned} files",
                }
            )

    dup_rows = 0
    if data_cols and rows:
        try:
            dup_rows = int(frame[data_cols].duplicated().sum())
        except Exception:
            dup_rows = 0

    columns.sort(key=lambda c: (-c["file_count"], c["name"].lower()))

    def names(pred) -> List[str]:
        return [c["name"] for c in columns if pred(c)]

    profile = {
        "files_scanned": files_scanned,
        "valid_files": valid_files,
        "failed_files": len(failed),
        "failed_file_names": failed,
        "rows": rows,
        "total_rows_est": total_rows_read,
        "total_columns": len(columns),
        "type_counts": type_counts,
        "missing_pct": (missing_cells / total_cells * 100.0) if total_cells else 0.0,
        "missing_values": missing_cells,
        "duplicate_rows": dup_rows,
        "duplicate_pct": (dup_rows / rows * 100.0) if rows else 0.0,
        "invalid_values": invalid_total,
        "empty_columns": len(names(lambda c: c["col_type"] == "empty")),
        "mixed_columns": len(names(lambda c: c["col_type"] == "mixed")),
        "unnamed_columns": len(names(lambda c: not c["usable_for_analysis"] and "Unnamed" in c["reason_excluded"])),
        "columns": columns,
        "numeric_columns": names(lambda c: c["col_type"] == "numeric" and c["usable_for_analysis"]),
        "all_numeric_columns": names(lambda c: c["col_type"] == "numeric"),
        "grouping_columns": names(lambda c: c["grouping_suitable"]),
        "datetime_columns": names(lambda c: c["col_type"] == "datetime" and c["usable_for_analysis"]),
        "identifier_columns": names(lambda c: c["col_type"] == "identifier"),
        "label_columns": names(lambda c: c.get("is_label_candidate")),
        "excluded_columns": [
            {"name": c["name"], "reason": c["reason_excluded"]}
            for c in columns
            if not c["usable_for_analysis"]
        ],
        "issues": issues[:1000],
        "errors": [i["details"] or i["issue"] for i in issues if i["severity"] == "ERROR"][:200],
        "truncated": truncated,
    }
    profile["insights"] = _dataset_insights(profile, columns)
    return profile


def _dataset_insights(profile: Dict[str, Any], columns: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    rows = profile["rows"]
    if rows == 0:
        return ["No rows could be read from the selected source."]
    out.append(
        f"{rows:,} rows and {profile['total_columns']} columns were loaded from "
        f"{profile['valid_files']} of {profile['files_scanned']} files."
    )
    if profile["failed_files"]:
        out.append(
            f"{profile['failed_files']} file(s) could not be processed; analysis continued "
            f"with the remaining {profile['valid_files']}."
        )
    measurements = [c for c in columns if c["analysis_role"] == "measurement"]
    if measurements:
        best = max(measurements, key=lambda c: c["count"])
        out.append(f"{best['name']} contains {best['count']:,} valid measurements.")
        out.append(f"{len(measurements)} numeric column(s) are available for statistical analysis.")
    else:
        out.append("No usable numeric measurement columns were detected.")
    if profile["missing_pct"] > 0:
        out.append(f"{profile['missing_pct']:.1f}% of all cells are missing.")
    if profile["duplicate_rows"]:
        out.append(
            f"{profile['duplicate_rows']:,} duplicate row(s) detected ({profile['duplicate_pct']:.1f}%)."
        )
    groups = profile["grouping_columns"]
    if groups:
        out.append(f"{groups[0]} is a categorical grouping candidate.")
    else:
        out.append("No suitable grouping columns detected for Comparison.")
    if profile["datetime_columns"]:
        out.append(
            f"{profile['datetime_columns'][0]} was detected as Date/Time — Time Trend analysis is available."
        )
    for c in columns:
        if c.get("is_label_candidate") and c.get("labels_recognized"):
            vals = c.get("label_values") or []
            out.append(
                f"{c['name']} contains two classes: {vals[0]} and {vals[1]} — Limit Finder can use it as a label."
            )
            break
    if profile["excluded_columns"]:
        out.append(
            f"{len(profile['excluded_columns'])} column(s) were excluded from analysis candidates "
            "(unnamed, empty or mixed-type)."
        )
    if profile["truncated"]:
        out.append("Row limit reached — statistics use the loaded subset of the dataset.")
    return out


def open_session(
    files: Sequence[FileInfo],
    folder: str = "",
    max_rows: int = DEFAULT_MAX_ROWS,
    progress: Optional[Callable[[int, int, str], None]] = None,
    stop_event=None,
) -> Dict[str, Any]:
    """Read every file once, concatenate, profile, and cache the result."""
    paths = [f.path for f in files]
    key = _signature(folder, paths, max_rows)
    with _LOCK:
        cached = _SESSIONS.get(key)
    if cached is not None:
        return summary(cached, cached_hit=True)

    frames: List[pd.DataFrame] = []
    issues: List[Dict[str, Any]] = []
    failed: List[str] = []
    file_presence: Dict[str, int] = {}
    col_rows: Dict[str, int] = {}
    valid = 0
    total_rows_read = 0
    truncated = False
    total = len(files)

    for i, fi in enumerate(files, 1):
        if stop_event is not None and stop_event.is_set():
            break
        if progress:
            progress(i - 1, total, fi.name)
        if total_rows_read >= max_rows:
            truncated = True
            break
        try:
            sheets = list(_iter_frames(fi.path))
        except Exception as e:
            failed.append(fi.name)
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
        if not sheets:
            failed.append(fi.name)
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

        used = False
        seen: Dict[str, int] = {}
        for sheet, df in sheets:
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
            df = df.copy()
            df.columns = [str(c) for c in df.columns]
            total_rows_read += int(len(df))
            room = max_rows - sum(len(f) for f in frames)
            if room <= 0:
                truncated = True
                break
            if len(df) > room:
                df = df.head(room)
                truncated = True
            df[FILE_COL] = fi.name
            df[SHEET_COL] = sheet
            frames.append(df)
            used = True
            for c in df.columns:
                if c not in META_COLS:
                    seen[str(c)] = seen.get(str(c), 0) + int(len(df))
        for c, n in seen.items():
            file_presence[c] = file_presence.get(c, 0) + 1
            col_rows[c] = col_rows.get(c, 0) + n
        if used:
            valid += 1
        elif fi.name not in failed:
            failed.append(fi.name)

    if progress:
        progress(total, total, "")

    if frames:
        frame = pd.concat(frames, ignore_index=True, sort=False)
    else:
        frame = pd.DataFrame()

    profile = build_profile(
        frame,
        file_presence=file_presence,
        files_scanned=total,
        valid_files=valid,
        failed=failed,
        issues=issues,
        truncated=truncated,
        total_rows_read=total_rows_read,
        applicable_rows=col_rows,
    )
    profile["total_size"] = format_size(sum(f.size for f in files))

    session = Session(
        key=key,
        source_folder=folder,
        source_files=paths,
        frame=frame,
        profile=profile,
    )
    with _LOCK:
        # Keep memory bounded: only the two most recent datasets stay resident.
        if len(_SESSIONS) >= 2:
            for old in list(_SESSIONS)[:-1]:
                _SESSIONS.pop(old, None)
        _SESSIONS[key] = session
    return summary(session)


def summary(session: Session, cached_hit: bool = False) -> Dict[str, Any]:
    payload = dict(session.profile)
    payload["key"] = session.key
    payload["source_folder"] = session.source_folder
    payload["source_file_count"] = len(session.source_files)
    payload["cached"] = cached_hit
    return payload


def get_session(key: str) -> Session:
    with _LOCK:
        session = _SESSIONS.get(key)
    if session is None:
        raise KeyError("Dataset session expired. Please select the folder or files again.")
    return session


def close_session(key: str) -> Dict[str, Any]:
    with _LOCK:
        _SESSIONS.pop(key, None)
    return {"ok": True}


def column_meta(session: Session, name: str) -> Optional[Dict[str, Any]]:
    for c in session.profile["columns"]:
        if c["name"] == name:
            return c
    return None


def numeric_series(session: Session, column: str) -> pd.Series:
    """Numeric values of a column with invalid entries dropped."""
    if column not in session.frame.columns:
        raise KeyError(f"Column '{column}' does not exist in the loaded dataset.")
    return pd.to_numeric(session.frame[column], errors="coerce")


def column_values(session: Session, name: str, limit: int = 50) -> Dict[str, Any]:
    """Most frequent non-empty values of any column, for label mapping in the UI."""
    if name not in session.frame.columns and name not in (FILE_COL, "__file__"):
        raise KeyError(f"Column '{name}' does not exist in the loaded dataset.")
    series = text_series(session, name).dropna().astype(str).str.strip()
    series = series[series.ne("") & series.str.lower().ne("nan")]
    counts = series.value_counts()
    cap = max(1, min(int(limit or 50), 80))
    top = counts.head(cap)
    return {
        "name": name,
        "values": [{"value": str(value), "count": int(count)} for value, count in top.items()],
        "distinct": int(counts.size),
        "truncated": bool(counts.size > cap),
    }


def text_series(session: Session, column: str) -> pd.Series:
    if column == FILE_COL or column == "__file__":
        return session.frame[FILE_COL].astype(str)
    if column not in session.frame.columns:
        raise KeyError(f"Column '{column}' does not exist in the loaded dataset.")
    series = session.frame[column]
    missing = _missing_mask(series)
    return series.where(~missing).astype(object)
