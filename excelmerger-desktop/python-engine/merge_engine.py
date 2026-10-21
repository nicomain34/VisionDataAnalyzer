"""Headless merge/scan/save engine extracted from ExcelMerger Tkinter app."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np
import pandas as pd

SUPPORTED_EXTS = (".csv", ".xlsx", ".xls", ".xlsm")

# The merged table stays in this process. Save reads it from here, so a failed
# pickle (full temp disk, a read-only engine folder) does not disable Save.
_MERGED: Optional[pd.DataFrame] = None
_MERGED_META: Dict[str, Any] = {}


def _cache_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return os.path.join(base, "ExcelMerger", "last_merge.pkl")


def merge_status() -> Dict[str, Any]:
    if _MERGED is None:
        return {"ready": False, "rows": 0, "cols": 0, "files": 0, "dupes": 0}
    return {
        "ready": True,
        "rows": int(len(_MERGED)),
        "cols": int(_MERGED.shape[1]),
        "files": int(_MERGED_META.get("files") or 0),
        "dupes": int(_MERGED_META.get("dupes") or 0),
    }


def cell_to_display(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    return "" if text.lower() == "nan" else text


def read_tabular_file(file_path: str, sheet_contains: str = ""):
    """Read a CSV, or the Excel sheet that actually holds the rows.

    Vision workbooks often put a cover or summary on the first sheet and the
    measurements on the next one. Reading only the first sheet then looks like
    an empty file.
    """
    lower_path = file_path.lower()
    read_kwargs = {"keep_default_na": False, "na_values": [""]}
    if lower_path.endswith(".csv"):
        return pd.read_csv(file_path, **read_kwargs)
    needle = (sheet_contains or "").strip().lower()
    xl = pd.ExcelFile(file_path)
    try:
        names = list(xl.sheet_names)
        if needle:
            names = [s for s in names if needle in s.lower()]
            if not names:
                raise ValueError(f"No sheet matching '{sheet_contains}'")
        loaded = []
        for sheet in names:
            df = pd.read_excel(xl, sheet_name=sheet, **read_kwargs)
            if df is None or df.empty:
                continue
            loaded.append((sheet, df))
        if not loaded:
            return pd.DataFrame()
        if not needle and len(loaded) > 1:
            biggest = max(len(df) for _, df in loaded)
            # A short cover sheet must not be stacked onto the measurement sheet.
            cutoff = biggest if biggest < 50 else max(50, int(biggest * 0.05))
            loaded = [(sheet, df) for sheet, df in loaded if len(df) >= cutoff]
        if len(loaded) == 1:
            return loaded[0][1]
        frames = []
        for sheet, df in loaded:
            df = df.copy()
            if "Sheet" in df.columns:
                df = df.rename(columns={"Sheet": "Sheet (from file)"})
            df.insert(0, "Sheet", sheet)
            frames.append(df)
        return pd.concat(frames, ignore_index=True, sort=False)
    finally:
        xl.close()


def parse_date(text: str):
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def is_hidden(path: str) -> bool:
    name = os.path.basename(path)
    if name.startswith("."):
        return True
    try:
        import ctypes

        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        if attrs != -1 and (attrs & 2):
            return True
    except Exception:
        pass
    return False


def is_temp_file(name: str) -> bool:
    lower = name.lower()
    return (
        name.startswith("~$")
        or lower.endswith(".tmp")
        or lower.endswith(".temp")
        or name.startswith(".~")
    )


def file_passes_filters(path: str, filters: Dict[str, Any]) -> bool:
    name = os.path.basename(path)
    name_l = name.lower()

    if filters.get("skip_temp", True) and is_temp_file(name):
        return False
    if not filters.get("include_hidden", False) and is_hidden(path):
        return False

    contains = (filters.get("name_contains") or "").strip().lower()
    if contains:
        parts = [p.strip() for p in contains.replace(";", ",").split(",") if p.strip()]
        if parts and not any(p in name_l for p in parts):
            return False

    excludes = (filters.get("name_excludes") or "").strip().lower()
    if excludes:
        parts = [p.strip() for p in excludes.replace(";", ",").split(",") if p.strip()]
        if any(p in name_l for p in parts):
            return False

    try:
        if filters.get("size_enable"):
            size_mb = os.path.getsize(path) / (1024 * 1024)
            try:
                min_mb = float(filters.get("size_min") or 0)
            except ValueError:
                min_mb = 0
            try:
                max_mb = float(filters.get("size_max") or 1e12)
            except ValueError:
                max_mb = 1e12
            if size_mb < min_mb or size_mb > max_mb:
                return False
    except OSError:
        return False

    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(path)).date()
    except OSError:
        return False

    preset = filters.get("date_preset") or "any"
    d_from = parse_date(filters.get("date_from") or "")
    d_to = parse_date(filters.get("date_to") or "")
    today = datetime.now().date()
    if preset == "24h":
        d_from, d_to = today - timedelta(days=1), today
    elif preset == "7d":
        d_from, d_to = today - timedelta(days=7), today
    elif preset == "30d":
        d_from, d_to = today - timedelta(days=30), today

    if d_from and mtime < d_from:
        return False
    if d_to and mtime > d_to:
        return False
    return True


def scan_folder(
    folder: str,
    extensions: Sequence[str],
    filters: Optional[Dict[str, Any]] = None,
    progress: Optional[Callable[[int, str], None]] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    filters = filters or {}
    recursive = filters.get("search_subfolders", True)
    found: List[Dict[str, Any]] = []
    exts = tuple(e if e.startswith(".") else f".{e}" for e in extensions)
    errors: List[str] = []

    if not folder or not os.path.isdir(folder):
        return {"files": [], "errors": ["Folder not found"], "cancelled": False}

    if recursive:
        walker = os.walk(folder)
    else:
        try:
            names = os.listdir(folder)
        except OSError as e:
            return {"files": [], "errors": [str(e)], "cancelled": False}
        walker = [(folder, [], names)]

    count = 0
    for root, _dirs, files in walker:
        if cancel and cancel():
            return {"files": [], "errors": errors, "cancelled": True}
        for file in files:
            if cancel and cancel():
                return {"files": [], "errors": errors, "cancelled": True}
            if not any(file.lower().endswith(ext) for ext in exts):
                continue
            path = os.path.join(root, file)
            count += 1
            if progress and count % 25 == 0:
                progress(count, file)
            if file_passes_filters(path, filters):
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                found.append(
                    {
                        "path": path,
                        "name": file,
                        "size": size,
                        "selected": True,
                    }
                )

    found.sort(key=lambda f: f["path"].lower())
    return {"files": found, "errors": errors, "cancelled": False, "count": len(found)}


def apply_data_filters(df: pd.DataFrame, column_filters: List[Dict[str, str]]) -> pd.DataFrame:
    for item in column_filters or []:
        mode = item.get("mode") or "contains"
        val = (item.get("value") or "").strip()
        if not val:
            continue
        text_df = df.apply(lambda col: col.map(cell_to_display))
        if mode == "equals":
            mask = text_df.apply(lambda r: r.str.lower().eq(val.lower()).any(), axis=1)
        elif mode == "not_contains":
            mask = ~text_df.apply(
                lambda r: r.astype(str).str.contains(val, case=False, na=False).any(),
                axis=1,
            )
        else:
            mask = text_df.apply(
                lambda r: r.astype(str).str.contains(val, case=False, na=False).any(),
                axis=1,
            )
        df = df[mask]
        if df.empty:
            break
    return df


def merge_files(
    file_paths: Sequence[str],
    sheet_contains: str = "",
    column_filters: Optional[List[Dict[str, str]]] = None,
    remove_dupes: bool = False,
    progress: Optional[Callable[[int, int, str], None]] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    global _MERGED, _MERGED_META
    _MERGED = None
    _MERGED_META = {}
    frames: List[pd.DataFrame] = []
    errors: List[Dict[str, str]] = []
    total = len(file_paths)
    merged_count = 0

    for i, path in enumerate(file_paths, 1):
        if cancel and cancel():
            return {"cancelled": True, "errors": errors}
        if progress:
            progress(i - 1, total, os.path.basename(path))
        try:
            df = read_tabular_file(path, sheet_contains=sheet_contains)
            if df.empty:
                errors.append({"file": os.path.basename(path), "error": "No rows found in this file."})
                continue
            df = apply_data_filters(df, column_filters or [])
            if df.empty:
                errors.append(
                    {"file": os.path.basename(path), "error": "Every row was removed by the column filters."}
                )
                continue
            if "File name" in df.columns:
                df = df.rename(columns={"File name": "File name (from file)"})
            df.insert(0, "File name", os.path.basename(path))
            frames.append(df)
            merged_count += 1
        except Exception as e:
            errors.append({"file": os.path.basename(path), "error": str(e)})

    if not frames:
        if progress:
            progress(total, total, "")
        return {
            "cancelled": False,
            "ok": False,
            "rows": 0,
            "cols": 0,
            "files": 0,
            "dupes": 0,
            "errors": errors,
            "columns": [],
        }

    if progress:
        progress(total, total, "Combining rows")

    merged = pd.concat(frames, ignore_index=True)
    before = len(merged)
    dupes = 0
    if remove_dupes:
        merged = merged.drop_duplicates(keep="first").reset_index(drop=True)
        dupes = before - len(merged)

    _MERGED = merged
    _MERGED_META = {"files": merged_count, "dupes": int(dupes)}
    cache_path = ""
    try:
        cache_path = _cache_path()
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        merged.to_pickle(cache_path)
    except Exception:
        cache_path = ""

    if progress:
        progress(total, total, "")

    return {
        "cancelled": False,
        "ok": True,
        "rows": int(len(merged)),
        "cols": int(len(merged.columns)),
        "files": merged_count,
        "dupes": int(dupes),
        "errors": errors,
        "columns": [str(c) for c in merged.columns],
        "cache_path": cache_path,
    }


def _excel_value(value: Any) -> Any:
    """Value openpyxl can write. Missing cells become empty."""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        return None if number != number else number
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.to_pydatetime()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _write_table(df: pd.DataFrame, path: str, progress: Optional[Callable[[int, int], None]]) -> None:
    """Write beside the destination, then replace it so a partial file is never opened."""
    total = int(len(df))
    tmp = path + ".partial"
    step = max(1, min(4000, total // 40 or 1))
    if progress:
        progress(0, total)
    try:
        if path.lower().endswith(".csv"):
            if total == 0:
                df.to_csv(tmp, index=False, encoding="utf-8-sig")
            else:
                for start in range(0, total, step):
                    chunk = df.iloc[start : start + step]
                    chunk.to_csv(
                        tmp,
                        index=False,
                        mode="w" if start == 0 else "a",
                        header=start == 0,
                        encoding="utf-8-sig",
                    )
                    if progress:
                        progress(min(start + step, total), total)
        else:
            from openpyxl import Workbook

            book = Workbook(write_only=True)
            sheet = book.create_sheet("Merged")
            sheet.append([str(c) for c in df.columns])
            written = 0
            for row in df.itertuples(index=False, name=None):
                sheet.append([_excel_value(v) for v in row])
                written += 1
                if progress and (written % step == 0 or written == total):
                    progress(written, total)
            book.save(tmp)
        os.replace(tmp, path)
        if progress:
            progress(total, total)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def save_merged(
    path: str,
    cache_path: Optional[str] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    df = _MERGED
    if df is None:
        cache = cache_path or _cache_path()
        if not os.path.exists(cache):
            return {"ok": False, "error": "No merged data available. Run merge first."}
        df = pd.read_pickle(cache)
    lower = path.lower()
    if not lower.endswith(".csv") and not lower.endswith(".xlsx"):
        path = path + ".xlsx"
    try:
        _write_table(df, path, progress)
        return {"ok": True, "path": path, "rows": int(len(df))}
    except Exception as e:
        return {"ok": False, "error": str(e)}
