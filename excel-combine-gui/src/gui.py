import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
import os
import threading
from datetime import datetime, timedelta

from icons import get_icon


# ---------------------------------------------------------------------------
# VisionOS-inspired theme
# ---------------------------------------------------------------------------

THEME = {
    "bg_deep": "#0B0B12",
    "bg_space": "#12121A",
    "sidebar": "#14141C",
    "glass": "#1C1C24",
    "elevated": "#2A2A34",
    "border": "#3A3A48",
    "text": "#F5F5F7",
    "text_sec": "#A1A1AA",
    "text_mute": "#6E6E76",
    "accent": "#0A84FF",
    "accent_hover": "#409CFF",
    "accent_soft": "#0A84FF33",
    "success": "#30D158",
    "success_hover": "#4CD964",
    "danger": "#FF453A",
    "danger_hover": "#FF6961",
    "lg": "#A50034",
    "disabled_bg": "#2C2C32",
    "disabled_fg": "#6E6E76",
    "entry_bg": "#14141C",
    "font": "Segoe UI",
}


def glass_frame(parent, elevated=False):
    bg = THEME["elevated"] if elevated else THEME["glass"]
    outer = tk.Frame(parent, bg=THEME["border"], bd=0, highlightthickness=0)
    inner = tk.Frame(outer, bg=bg, bd=0, highlightthickness=0)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return outer, inner


def style_entry(entry):
    entry.configure(
        font=(THEME["font"], 10),
        bg=THEME["entry_bg"],
        fg=THEME["text"],
        insertbackground=THEME["text"],
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightcolor=THEME["accent"],
        highlightbackground=THEME["border"],
    )
    return entry


def apply_vision_ttk(style=None):
    style = style or ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Vision.Horizontal.TProgressbar",
        troughcolor=THEME["elevated"],
        bordercolor=THEME["elevated"],
        background=THEME["accent"],
        lightcolor=THEME["accent"],
        darkcolor=THEME["accent"],
        thickness=10,
    )
    style.configure(
        "Vision.TCombobox",
        fieldbackground=THEME["entry_bg"],
        background=THEME["elevated"],
        foreground=THEME["text"],
        arrowcolor=THEME["text"],
        bordercolor=THEME["border"],
        padding=6,
    )
    style.map(
        "Vision.TCombobox",
        fieldbackground=[("readonly", THEME["entry_bg"])],
        foreground=[("readonly", THEME["text"])],
    )
    style.configure(
        "Vision.Treeview",
        background=THEME["glass"],
        foreground=THEME["text"],
        fieldbackground=THEME["glass"],
        rowheight=26,
        font=(THEME["font"], 9),
        borderwidth=0,
    )
    style.configure(
        "Vision.Treeview.Heading",
        background=THEME["elevated"],
        foreground=THEME["text"],
        font=(THEME["font"], 9, "bold"),
        relief="flat",
    )
    style.map(
        "Vision.Treeview",
        background=[("selected", THEME["accent"])],
        foreground=[("selected", THEME["text"])],
    )
    style.configure(
        "Vision.Vertical.TScrollbar",
        background=THEME["elevated"],
        troughcolor=THEME["glass"],
        arrowcolor=THEME["text_sec"],
    )
    return style


def _round_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    points = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class VisionButton(tk.Canvas):
    """Rounded pill button with tk.Button-like config(text/state) API."""

    def __init__(
        self,
        parent,
        text="",
        command=None,
        bg=None,
        fg=None,
        hover_bg=None,
        width=180,
        height=44,
        radius=18,
        font=None,
        state=tk.NORMAL,
        icon=None,
        icon_name=None,
        icon_size=16,
        outline=False,
        **kwargs,
    ):
        self._command = command
        self._text = text
        self._bg = bg or THEME["accent"]
        self._fg = fg or THEME["text"]
        self._hover_bg = hover_bg or THEME["accent_hover"]
        self._radius = radius
        self._font = font or (THEME["font"], 11, "bold")
        self._state = state
        self._width = width
        self._height = height
        self._icon_name = icon_name
        self._icon_size = icon_size
        self._icon = icon or (get_icon(icon_name, icon_size) if icon_name else None)
        self._outline = outline
        parent_bg = kwargs.pop("parent_bg", None)
        if parent_bg is None:
            try:
                parent_bg = parent.cget("bg")
            except Exception:
                parent_bg = THEME["glass"]

        super().__init__(
            parent,
            width=width,
            height=height,
            bg=parent_bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._pill = None
        self.bind("<Configure>", self._redraw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.after_idle(self._redraw)

    def _current_fill(self, hover=False):
        if self._state == tk.DISABLED:
            return THEME["disabled_bg"]
        return self._hover_bg if hover else self._bg

    def _current_fg(self):
        if self._state == tk.DISABLED:
            return THEME["disabled_fg"]
        return self._fg

    def _redraw(self, event=None):
        self.delete("all")
        w = max(self.winfo_width(), self._width)
        h = max(self.winfo_height(), self._height)
        pad = 1
        fill = self._current_fill()
        outline = THEME["border"] if self._outline and self._state != tk.DISABLED else ""
        self._pill = _round_rect(
            self, pad, pad, w - pad, h - pad, self._radius,
            fill=fill, outline=outline,
        )
        if self._icon is not None:
            gap = 8
            # approximate text width
            tw = max(len(self._text) * 7, 20)
            total = self._icon_size + gap + tw
            x0 = (w - total) // 2
            self.create_image(x0 + self._icon_size // 2, h // 2, image=self._icon)
            self.create_text(
                x0 + self._icon_size + gap + tw // 2,
                h // 2,
                text=self._text,
                fill=self._current_fg(),
                font=self._font,
            )
        else:
            self.create_text(
                w // 2, h // 2, text=self._text,
                fill=self._current_fg(), font=self._font,
            )

    def _on_enter(self, _e=None):
        if self._state != tk.DISABLED and self._pill:
            self.itemconfig(self._pill, fill=self._current_fill(hover=True))

    def _on_leave(self, _e=None):
        if self._pill:
            self.itemconfig(self._pill, fill=self._current_fill())

    def _on_click(self, _e=None):
        if self._state != tk.DISABLED and self._command:
            self._command()

    def config(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if "text" in kwargs:
            self._text = kwargs.pop("text")
        if "command" in kwargs:
            self._command = kwargs.pop("command")
        if "state" in kwargs:
            self._state = kwargs.pop("state")
            self.configure(cursor="arrow" if self._state == tk.DISABLED else "hand2")
        if "bg" in kwargs:
            self._bg = kwargs.pop("bg")
        if "fg" in kwargs:
            self._fg = kwargs.pop("fg")
        if "activebackground" in kwargs:
            self._hover_bg = kwargs.pop("activebackground")
        if "width" in kwargs:
            self._width = int(kwargs["width"])
        if "height" in kwargs:
            self._height = int(kwargs["height"])
        if kwargs:
            super().config(**kwargs)
        self._redraw()

    configure = config

    def __getitem__(self, key):
        if key == "state":
            return self._state
        if key == "text":
            return self._text
        return super().__getitem__(key)

    def update(self):
        self._redraw()
        super().update()


def _cell_to_display(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value)
    return "" if text.lower() == "nan" else text


def _read_tabular_file(file_path: str, sheet_contains: str = ""):
    lower_path = file_path.lower()
    read_kwargs = {"keep_default_na": False, "na_values": [""]}
    if lower_path.endswith(".csv"):
        return pd.read_csv(file_path, **read_kwargs)
    needle = (sheet_contains or "").strip().lower()
    if needle:
        xl = pd.ExcelFile(file_path)
        match = next((s for s in xl.sheet_names if needle in s.lower()), None)
        if match is None:
            raise ValueError(f"No sheet matching '{sheet_contains}'")
        return pd.read_excel(file_path, sheet_name=match, **read_kwargs)
    return pd.read_excel(file_path, **read_kwargs)


LANG = {
    "en": {
        "title": "ExcelMerger",
        "subtitle": "Merge and analyze files from folders and subfolders.",
        "language": "Language",
        "nav_merger": "Excel Merger",
        "nav_logs": "Logs",
        "nav_analysis": "Analysis",
        "nav_settings": "Settings",
        "logs_title": "Logs",
        "logs_subtitle": "All actions and errors (English only).",
        "logs_clear": "Clear log",
        "logs_empty": "No log entries yet.",
        "step_folder": "1. Select folder",
        "step_types": "2. File types to search",
        "step_advanced": "Advanced Options",
        "step_merge": "3. Start merge",
        "step_save": "4. Save result",
        "folder_hint": "Select a folder with files to merge",
        "select_folder": "Select folder",
        "change_folder": "Change folder",
        "folder_not_selected": "No folder selected",
        "folder_selected": "{path}",
        "folder_search_hint": "Searches in selected folder and all subfolders.",
        "folder_drop_hint": "The application will search for files in the selected folder and all subfolders.",
        "folder_title_line": "Select a folder with files to merge",
        "file_types": "File types to search",
        "csv": "CSV (.csv)",
        "xlsx": "Excel (.xlsx)",
        "xls_old": "Excel old (.xls)",
        "xlsm": "Excel macros (.xlsm)",
        "advanced_options": "Advanced Options",
        "advanced_title": "Advanced Options",
        "adv_file_filters": "File filters",
        "adv_name_contains": "File name contains",
        "adv_name_excludes": "File name does not contain",
        "adv_name_contains_ph": "e.g. report, vision, camera",
        "adv_name_excludes_ph": "e.g. temp, old, backup",
        "adv_name_contains_tip": "Keep only files whose name contains any of these words (comma-separated).",
        "adv_name_excludes_tip": "Exclude files whose name contains any of these words (comma-separated).",
        "adv_date_filter": "Date filter (file modified date)",
        "adv_date_any": "Any time",
        "adv_date_24h": "Last 24 hours",
        "adv_date_7d": "Last 7 days",
        "adv_date_30d": "Last 30 days",
        "adv_date_custom": "Custom range",
        "adv_date_from": "From",
        "adv_date_to": "To",
        "adv_date_ph": "DD.MM.YYYY",
        "adv_date_tip": "Filter files by last modified date. Use a preset or type dates as DD.MM.YYYY.",
        "adv_size_filter": "File size filter",
        "adv_size_enable": "Enable size filter",
        "adv_size_min": "Min size (MB)",
        "adv_size_max": "Max size (MB)",
        "adv_size_min_ph": "0",
        "adv_size_max_ph": "100",
        "adv_size_tip": "Keep only files within the selected size range in megabytes.",
        "adv_data_filters": "Data filters (optional)",
        "adv_sheet_contains": "Sheet name contains",
        "adv_sheet_contains_ph": "e.g. Summary, Data",
        "adv_sheet_contains_tip": "Read the Excel sheet whose name contains this text. Leave empty to use the first sheet.",
        "adv_col_filter": "Column filter",
        "adv_col_filter_tip": "Keep rows where any cell matches the rule (Contains / Equals / Does not contain).",
        "adv_col_contains": "Contains",
        "adv_col_equals": "Equals",
        "adv_col_not": "Does not contain",
        "adv_col_value_ph": "e.g. Defect, Camera, Time",
        "adv_add_col_filter": "+ Add column filter",
        "adv_other": "Other options",
        "adv_include_hidden": "Include hidden files",
        "adv_subfolders": "Search in subfolders",
        "adv_skip_temp": "Skip temporary files",
        "adv_remove_dupes": "Remove duplicate rows",
        "adv_include_hidden_tip": "Include Windows hidden files and dot-files.",
        "adv_subfolders_tip": "Search recursively in all subfolders of the selected folder.",
        "adv_skip_temp_tip": "Skip temporary Office files (~$...) and .tmp files.",
        "adv_remove_dupes_tip": "After merge, remove fully duplicate rows.",
        "adv_apply_filters": "Apply filters",
        "close": "Close",
        "apply": "Apply",
        "start_merge": "Start Merge",
        "save_merged": "Save merged file",
        "save_hint": "Available after merge completes.",
        "status_ready": "Ready. Please select a folder and click 'Start Merge'.",
        "status_merging": "Searching and merging files...",
        "status_no_files": "No files with selected extensions found.",
        "status_no_checked": "No files selected in the preview list.",
        "status_processing": "Processing files: {current}/{total}...",
        "status_done": "Merge completed — {rows} rows",
        "status_no_data": "No data to merge.",
        "status_scanning": "Scanning files...",
        "status_saving": "Saving file...",
        "status_saved": "File saved successfully.",
        "msg_no_folder_title": "Folder not selected",
        "msg_no_folder_body": "Please select a folder first.",
        "msg_no_types_title": "File types",
        "msg_no_types_body": "Select at least one file type to search.",
        "msg_saved_title": "Saved",
        "msg_saved_body": "Merged file saved as:\n{path}",
        "msg_save_error_title": "Save error",
        "msg_save_error_body": "Could not save file:\n{error}",
        "msg_no_data_title": "No data",
        "msg_no_data_body": "No data to save.",
        "product_name": "Excel Merger",
        "files_preview": "Files found ({count}) — uncheck to exclude",
        "files_select_all": "Select all",
        "files_deselect_all": "Deselect all",
        "summary_title": "Merge summary",
        "summary_text": "Files merged: {files}  ·  Rows: {rows}  ·  Columns: {cols}  ·  Duplicates removed: {dupes}  ·  Errors: {errors}",
        "analysis_soon": "This analysis page is coming soon.",
        "settings_soon": "Settings module — coming soon.",
        "nav_analysis_overview": "Overview",
        "nav_analysis_distribution": "Distribution",
        "nav_analysis_datatable": "Data Table",
        "nav_analysis_comparison": "Comparison",
        "nav_analysis_quality": "Data Quality",
        "dist_title": "Distribution",
        "dist_subtitle": "Analyze the distribution of values across multiple Excel files.",
        "dist_step_files": "1. Select files or folder",
        "dist_step_column": "2. Select column to analyze",
        "dist_step_options": "3. Analysis options",
        "dist_select_folder": "Select folder",
        "dist_select_files": "Select files",
        "dist_change": "Change",
        "dist_files_meta": "{count} Excel files found ({size})",
        "dist_mode_overall": "Overall",
        "dist_mode_compare": "Compare",
        "dist_mode_outliers": "Outliers",
        "dist_group_by": "Group by (optional)",
        "dist_chart_type": "Chart type",
        "dist_show_stats": "Show statistics",
        "dist_bins": "Bins",
        "dist_log_scale": "Log scale (Y-axis)",
        "dist_advanced_filters": "Advanced filters",
        "dist_advanced_hint": "Future filters: file, sheet, value range, date range, exclude nulls/zeros.",
        "dist_analyze": "Analyze Distribution",
        "dist_statistics": "Statistics",
        "dist_summary": "Analysis Summary",
        "dist_preview": "Data Preview (sample)",
        "dist_export": "Export data",
        "dist_outliers_only": "Show outliers only",
        "dist_group_stats": "Group comparison",
        "dist_empty": "Select Excel files or a folder to begin analysis.",
        "dist_chart_placeholder": "Distribution chart",
        "dist_tab_distribution": "Distribution",
        "dist_tab_statistics": "Statistics",
        "dist_tab_insights": "Insights",
        "dist_tab_outliers": "Outliers",
        "dist_tab_outliers_n": "Outliers ({count})",
        "dist_dtype_numeric": "Numeric",
        "dist_dtype_text": "Text",
        "dist_dtype_date": "Date",
        "dist_dtype_mixed": "Mixed",
        "dist_col_coverage": "'{col}' found in {found} of {total} files.",
        "dist_col_not_numeric": "Selected column is not numeric.",
        "dist_need_files": "Please select a folder or files first.",
        "dist_need_column": "Please select a column to analyze.",
        "dist_confirm_non_numeric": "This column does not look numeric. Continue anyway?",
        "dist_scanning_columns": "Scanning columns...",
        "dist_analyzing": "Analyzing distribution...",
        "dist_progress": "Analyzing {done} / {total} files · {values} values · {file}",
        "dist_of": "Distribution of {col}",
        "dist_values_from": "{values} values from {files} files",
        "dist_no_export": "No data to export.",
        "dist_export_ok": "Exported to:\n{path}",
        "save_progress": "Saving... please wait",
        "save_stop": "STOP",
        "save_cancelled_title": "Cancelled",
        "save_cancelled_body": "Saving was stopped by the user.",
        "save_modal_title": "Saving",
        "scan_modal_title": "Loading",
        "scan_progress": "Loading files... please wait",
        "scan_cancelled_title": "Cancelled",
        "scan_cancelled_body": "Loading was stopped by the user.",
        "scan_done": "Found {count} files.",
    },
    "pl": {
        "title": "ExcelMerger",
        "subtitle": "Łącz i analizuj pliki z folderów i podfolderów.",
        "language": "Język",
        "nav_merger": "Excel Merger",
        "nav_logs": "Logs",
        "nav_analysis": "Analiza",
        "nav_settings": "Ustawienia",
        "logs_title": "Logs",
        "logs_subtitle": "All actions and errors (English only).",
        "logs_clear": "Clear log",
        "logs_empty": "No log entries yet.",
        "step_folder": "1. Wybierz folder",
        "step_types": "2. Typy plików",
        "step_advanced": "Opcje zaawansowane",
        "step_merge": "3. Rozpocznij łączenie",
        "step_save": "4. Zapisz wynik",
        "folder_hint": "Wybierz folder z plikami do połączenia",
        "select_folder": "Wybierz folder",
        "change_folder": "Zmień folder",
        "folder_not_selected": "Nie wybrano folderu",
        "folder_selected": "{path}",
        "folder_search_hint": "Przeszukuje wybrany folder i wszystkie podfoldery.",
        "folder_drop_hint": "Aplikacja przeszuka wybrany folder i wszystkie podfoldery.",
        "folder_title_line": "Wybierz folder z plikami do połączenia",
        "file_types": "Typy plików do wyszukania",
        "csv": "CSV (.csv)",
        "xlsx": "Excel (.xlsx)",
        "xls_old": "Excel stary (.xls)",
        "xlsm": "Excel makra (.xlsm)",
        "advanced_options": "Opcje zaawansowane",
        "advanced_title": "Opcje zaawansowane",
        "adv_file_filters": "Filtry plików",
        "adv_name_contains": "Nazwa pliku zawiera",
        "adv_name_excludes": "Nazwa pliku nie zawiera",
        "adv_name_contains_ph": "np. report, vision, camera",
        "adv_name_excludes_ph": "np. temp, old, backup",
        "adv_name_contains_tip": "Zachowaj tylko pliki, których nazwa zawiera któreś z tych słów (oddzielone przecinkami).",
        "adv_name_excludes_tip": "Pomiń pliki, których nazwa zawiera któreś z tych słów (oddzielone przecinkami).",
        "adv_date_filter": "Filtr daty (data modyfikacji)",
        "adv_date_any": "Dowolny czas",
        "adv_date_24h": "Ostatnie 24 godziny",
        "adv_date_7d": "Ostatnie 7 dni",
        "adv_date_30d": "Ostatnie 30 dni",
        "adv_date_custom": "Zakres własny",
        "adv_date_from": "Od",
        "adv_date_to": "Do",
        "adv_date_ph": "DD.MM.YYYY",
        "adv_date_tip": "Filtruj pliki według daty modyfikacji. Wybierz preset lub wpisz daty DD.MM.YYYY.",
        "adv_size_filter": "Filtr rozmiaru pliku",
        "adv_size_enable": "Włącz filtr rozmiaru",
        "adv_size_min": "Min. rozmiar (MB)",
        "adv_size_max": "Maks. rozmiar (MB)",
        "adv_size_min_ph": "0",
        "adv_size_max_ph": "100",
        "adv_size_tip": "Zachowaj tylko pliki w podanym zakresie rozmiaru (MB).",
        "adv_data_filters": "Filtry danych (opcjonalnie)",
        "adv_sheet_contains": "Nazwa arkusza zawiera",
        "adv_sheet_contains_ph": "np. Summary, Data",
        "adv_sheet_contains_tip": "Wczytaj arkusz Excel, którego nazwa zawiera ten tekst. Puste = pierwszy arkusz.",
        "adv_col_filter": "Filtr kolumn",
        "adv_col_filter_tip": "Zachowaj wiersze, w których dowolna komórka spełnia regułę (Zawiera / Równa się / Nie zawiera).",
        "adv_col_contains": "Zawiera",
        "adv_col_equals": "Równa się",
        "adv_col_not": "Nie zawiera",
        "adv_col_value_ph": "np. Defect, Camera, Time",
        "adv_add_col_filter": "+ Dodaj filtr kolumny",
        "adv_other": "Inne opcje",
        "adv_include_hidden": "Uwzględnij ukryte pliki",
        "adv_subfolders": "Szukaj w podfolderach",
        "adv_skip_temp": "Pomiń pliki tymczasowe",
        "adv_remove_dupes": "Usuń zduplikowane wiersze",
        "adv_include_hidden_tip": "Uwzględnij ukryte pliki Windows i pliki zaczynające się od kropki.",
        "adv_subfolders_tip": "Szukaj rekurencyjnie we wszystkich podfolderach.",
        "adv_skip_temp_tip": "Pomiń tymczasowe pliki Office (~$...) oraz .tmp.",
        "adv_remove_dupes_tip": "Po połączeniu usuń w pełni zduplikowane wiersze.",
        "adv_apply_filters": "Zastosuj filtry",
        "close": "Zamknij",
        "apply": "Zastosuj",
        "start_merge": "Rozpocznij łączenie",
        "save_merged": "Zapisz połączony plik",
        "save_hint": "Dostępne po zakończeniu łączenia.",
        "status_ready": "Gotowe. Wybierz folder i kliknij 'Rozpocznij łączenie'.",
        "status_merging": "Wyszukiwanie i łączenie plików...",
        "status_no_files": "Nie znaleziono plików z wybranymi rozszerzeniami.",
        "status_no_checked": "Nie zaznaczono plików na liście.",
        "status_processing": "Przetwarzanie plików: {current}/{total}...",
        "status_done": "Łączenie zakończone — {rows} wierszy",
        "status_no_data": "Brak danych do połączenia.",
        "status_scanning": "Skanowanie plików...",
        "status_saving": "Zapisywanie pliku...",
        "status_saved": "Plik zapisano pomyślnie.",
        "msg_no_folder_title": "Nie wybrano folderu",
        "msg_no_folder_body": "Najpierw wybierz folder.",
        "msg_no_types_title": "Typy plików",
        "msg_no_types_body": "Wybierz co najmniej jeden typ pliku.",
        "msg_saved_title": "Zapisano",
        "msg_saved_body": "Połączony plik zapisano jako:\n{path}",
        "msg_save_error_title": "Błąd zapisu",
        "msg_save_error_body": "Nie można zapisać pliku:\n{error}",
        "msg_no_data_title": "Brak danych",
        "msg_no_data_body": "Brak danych do zapisania.",
        "product_name": "Excel Merger",
        "files_preview": "Znalezione pliki ({count}) — odznacz, aby wykluczyć",
        "files_select_all": "Zaznacz wszystko",
        "files_deselect_all": "Odznacz wszystko",
        "summary_title": "Podsumowanie",
        "summary_text": "Pliki: {files}  ·  Wiersze: {rows}  ·  Kolumny: {cols}  ·  Usunięte duplikaty: {dupes}  ·  Błędy: {errors}",
        "analysis_soon": "Ta strona analizy będzie wkrótce dostępna.",
        "settings_soon": "Moduł Ustawienia — wkrótce.",
        "nav_analysis_overview": "Przegląd",
        "nav_analysis_distribution": "Rozkład",
        "nav_analysis_datatable": "Tabela danych",
        "nav_analysis_comparison": "Porównanie",
        "nav_analysis_quality": "Jakość danych",
        "dist_title": "Rozkład",
        "dist_subtitle": "Analizuj rozkład wartości w wielu plikach Excel.",
        "dist_step_files": "1. Wybierz pliki lub folder",
        "dist_step_column": "2. Wybierz kolumnę do analizy",
        "dist_step_options": "3. Opcje analizy",
        "dist_select_folder": "Wybierz folder",
        "dist_select_files": "Wybierz pliki",
        "dist_change": "Zmień",
        "dist_files_meta": "Znaleziono plików: {count} ({size})",
        "dist_mode_overall": "Ogółem",
        "dist_mode_compare": "Porównaj",
        "dist_mode_outliers": "Odchylenia",
        "dist_group_by": "Grupuj według (opcjonalnie)",
        "dist_chart_type": "Typ wykresu",
        "dist_show_stats": "Pokaż statystyki",
        "dist_bins": "Przedziały",
        "dist_log_scale": "Skala log (oś Y)",
        "dist_advanced_filters": "Filtry zaawansowane",
        "dist_advanced_hint": "Przyszłe filtry: plik, arkusz, zakres wartości, data, null/zero.",
        "dist_analyze": "Analizuj rozkład",
        "dist_statistics": "Statystyki",
        "dist_summary": "Podsumowanie analizy",
        "dist_preview": "Podgląd danych (próbka)",
        "dist_export": "Eksportuj dane",
        "dist_outliers_only": "Tylko odchylenia",
        "dist_group_stats": "Porównanie grup",
        "dist_empty": "Wybierz pliki Excel lub folder, aby rozpocząć analizę.",
        "dist_chart_placeholder": "Wykres rozkładu",
        "dist_tab_distribution": "Rozkład",
        "dist_tab_statistics": "Statystyki",
        "dist_tab_insights": "Wnioski",
        "dist_tab_outliers": "Odchylenia",
        "dist_tab_outliers_n": "Odchylenia ({count})",
        "dist_dtype_numeric": "Numeryczna",
        "dist_dtype_text": "Tekst",
        "dist_dtype_date": "Data",
        "dist_dtype_mixed": "Mieszana",
        "dist_col_coverage": "'{col}' znaleziono w {found} z {total} plików.",
        "dist_col_not_numeric": "Wybrana kolumna nie jest numeryczna.",
        "dist_need_files": "Najpierw wybierz folder lub pliki.",
        "dist_need_column": "Wybierz kolumnę do analizy.",
        "dist_confirm_non_numeric": "Kolumna nie wygląda na numeryczną. Kontynuować?",
        "dist_scanning_columns": "Skanowanie kolumn...",
        "dist_analyzing": "Analiza rozkładu...",
        "dist_progress": "Analiza {done} / {total} plików · {values} wartości · {file}",
        "dist_of": "Rozkład: {col}",
        "dist_values_from": "{values} wartości z {files} plików",
        "dist_no_export": "Brak danych do eksportu.",
        "dist_export_ok": "Wyeksportowano do:\n{path}",
        "save_progress": "Zapisywanie... proszę czekać",
        "save_stop": "STOP",
        "save_cancelled_title": "Anulowano",
        "save_cancelled_body": "Zapisywanie zostało przerwane przez użytkownika.",
        "save_modal_title": "Zapisywanie",
        "scan_modal_title": "Ładowanie",
        "scan_progress": "Ładowanie plików... proszę czekać",
        "scan_cancelled_title": "Anulowano",
        "scan_cancelled_body": "Ładowanie zostało przerwane przez użytkownika.",
        "scan_done": "Znaleziono plików: {count}.",
    },
}


def _app_icon_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "excelmerger.ico")


def _set_window_icon(win):
    try:
        icon = _app_icon_path()
        if os.path.exists(icon):
            win.iconbitmap(icon)
    except Exception:
        pass


class Tooltip:
    """Hover tooltip for info icons / hints."""

    def __init__(self, widget, text_getter):
        self.widget = widget
        self.text_getter = text_getter
        self.tip = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None):
        text = self.text_getter() if callable(self.text_getter) else self.text_getter
        if not text:
            return
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg=THEME["border"])
        tk.Label(
            tw, text=text, justify="left", wraplength=320,
            background=THEME["elevated"], foreground=THEME["text"],
            font=(THEME["font"], 9), padx=10, pady=8,
        ).pack(padx=1, pady=1)

    def _hide(self, _event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class PlaceholderEntry(tk.Entry):
    """Entry with grey placeholder; keeps the real StringVar free of placeholder text."""

    def __init__(self, parent, textvariable=None, placeholder="", **kwargs):
        self._ph = placeholder or ""
        self._real = textvariable or tk.StringVar()
        self._showing_ph = False
        self._updating = False
        kwargs.pop("textvariable", None)
        super().__init__(parent, **kwargs)
        style_entry(self)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<KeyRelease>", self._sync_real)
        self._real.trace_add("write", self._on_real_changed)
        self._refresh_display()

    def set_placeholder(self, text):
        self._ph = text or ""
        self._refresh_display()

    def get_value(self):
        if self._showing_ph:
            return ""
        return self.get().strip()

    def clear(self):
        self._real.set("")
        self._refresh_display()

    def _sync_real(self, _e=None):
        if self._showing_ph or self._updating:
            return
        self._updating = True
        try:
            self._real.set(self.get())
        finally:
            self._updating = False

    def _on_real_changed(self, *_):
        if self._updating:
            return
        if self.focus_get() is self and not self._showing_ph:
            return
        self._refresh_display()

    def _refresh_display(self):
        self._updating = True
        try:
            val = self._real.get()
            self.delete(0, "end")
            if val:
                self._showing_ph = False
                self.insert(0, val)
                self.configure(fg=THEME["text"])
            else:
                self._showing_ph = True
                self.insert(0, self._ph)
                self.configure(fg=THEME["text_mute"])
        finally:
            self._updating = False

    def _on_focus_in(self, _e=None):
        if self._showing_ph:
            self._showing_ph = False
            self.delete(0, "end")
            self.configure(fg=THEME["text"])

    def _on_focus_out(self, _e=None):
        self._sync_real()
        self._refresh_display()


class BlueCheckchip(tk.Frame):
    """File-type chip with a blue checkbox indicator."""

    def __init__(self, parent, text, variable, command=None, **kwargs):
        super().__init__(
            parent,
            bg=THEME["elevated"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
            **kwargs,
        )
        self.variable = variable
        self.command = command
        self._text = text
        self._disabled = False

        self.box = tk.Canvas(
            self, width=18, height=18, bg=THEME["elevated"],
            highlightthickness=0, bd=0, cursor="hand2",
        )
        self.box.pack(side="left", padx=(10, 6), pady=8)
        self.label = tk.Label(
            self, text=text, font=(THEME["font"], 10),
            bg=THEME["elevated"], fg=THEME["text"], cursor="hand2",
        )
        self.label.pack(side="left", padx=(0, 12), pady=8)

        for w in (self, self.box, self.label):
            w.bind("<Button-1>", self._toggle)
        self.variable.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _toggle(self, _e=None):
        if self._disabled:
            return
        self.variable.set(not self.variable.get())
        if self.command:
            self.command()

    def _draw(self):
        self.box.delete("all")
        checked = bool(self.variable.get())
        if checked:
            self.box.create_rectangle(
                1, 1, 17, 17, fill=THEME["accent"], outline=THEME["accent"], width=1
            )
            self.box.create_line(
                4, 9, 8, 13, fill="white", width=2,
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
            )
            self.box.create_line(
                8, 13, 14, 5, fill="white", width=2,
                capstyle=tk.ROUND, joinstyle=tk.ROUND,
            )
        else:
            self.box.create_rectangle(
                1, 1, 17, 17, fill=THEME["glass"], outline=THEME["border"], width=1
            )

    def config(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if "text" in kwargs:
            self._text = kwargs.pop("text")
            self.label.config(text=self._text)
        if "state" in kwargs:
            state = kwargs.pop("state")
            self._disabled = state == tk.DISABLED
            cursor = "arrow" if self._disabled else "hand2"
            self.configure(cursor=cursor)
            self.box.configure(cursor=cursor)
            self.label.configure(cursor=cursor)
        if kwargs:
            super().config(**kwargs)

    configure = config


class ProgressModal(tk.Toplevel):
    """Centered blocking modal with indeterminate progress + red STOP."""

    def __init__(self, parent, gui, title, status_text, cancel_text, stop_event):
        super().__init__(parent)
        self.gui = gui
        self._cancel_text = cancel_text
        self._stop_event = stop_event
        self.title(title)
        self.configure(bg=THEME["bg_deep"])
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.request_stop)
        _set_window_icon(self)
        self.after(10, lambda: _set_window_icon(self))

        w, h = 360, 170
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (w // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

        card_outer, card = glass_frame(self)
        card_outer.pack(fill="both", expand=True, padx=12, pady=12)

        self.status = tk.Label(
            card, text=status_text,
            font=(THEME["font"], 10), bg=THEME["glass"], fg=THEME["text_sec"],
        )
        self.status.pack(pady=(18, 12))

        self.bar = ttk.Progressbar(
            card, orient="horizontal", mode="indeterminate",
            style="Vision.Horizontal.TProgressbar", length=280,
        )
        self.bar.pack(padx=24, fill="x")
        self.bar.start(12)

        self.stop_btn = VisionButton(
            card, text=gui._t("save_stop"), command=self.request_stop,
            bg=THEME["danger"], hover_bg=THEME["danger_hover"],
            width=120, height=40, radius=14,
            font=(THEME["font"], 11, "bold"), parent_bg=THEME["glass"],
        )
        self.stop_btn.pack(pady=(16, 10))

        self.grab_set()
        self.focus_force()

    def request_stop(self):
        self._stop_event.set()
        self.status.config(text=self._cancel_text, fg=THEME["danger"])
        self.stop_btn.config(state=tk.DISABLED)

    def finish(self):
        try:
            self.bar.stop()
        except Exception:
            pass
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()


class ExcelCombineGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("ExcelMerger")
        self.master.geometry("1100x820")
        self.master.minsize(960, 700)
        self.master.configure(bg=THEME["bg_deep"])

        _set_window_icon(self.master)

        self.folder_path = ""
        self.found_files = []
        self.file_vars = {}  # path -> BooleanVar
        self.all_dataframes = []
        self.merged_df = None
        self.activity_log = []  # list of {"ts", "level", "msg"} — English only
        self.merge_error_count = 0
        self.last_summary = {"files": 0, "rows": 0, "cols": 0, "dupes": 0, "errors": 0}
        self.current_lang = "en"
        self.current_page = "merger"
        self.advanced_open = False
        self.files_preview_open = False
        self._busy = False
        self._save_stop = threading.Event()
        self._scan_stop = threading.Event()
        self._progress_modal = None

        self.name_contains_var = tk.StringVar()
        self.name_excludes_var = tk.StringVar()
        self.date_preset_var = tk.StringVar(value="any")
        self.date_from_var = tk.StringVar()
        self.date_to_var = tk.StringVar()
        self.size_enable = tk.BooleanVar(value=False)
        self.size_min_var = tk.StringVar(value="0")
        self.size_max_var = tk.StringVar(value="100")
        self.sheet_contains_var = tk.StringVar()
        self.column_filters = []  # list of {"mode": StringVar, "value": StringVar, "frame": Frame}
        self.include_hidden = tk.BooleanVar(value=False)
        self.search_subfolders = tk.BooleanVar(value=True)
        self.skip_temp = tk.BooleanVar(value=True)
        self.remove_dupes = tk.BooleanVar(value=False)

        self.include_csv = tk.BooleanVar(value=True)
        self.include_xlsx = tk.BooleanVar(value=True)
        self.include_xls = tk.BooleanVar(value=True)
        self.include_xlsm = tk.BooleanVar(value=False)

        for var in (self.include_csv, self.include_xlsx, self.include_xls, self.include_xlsm):
            var.trace_add("write", lambda *_: self._on_types_changed())

        apply_vision_ttk()
        self._build_shell()
        self._apply_language()
        self._show_page("merger")

    # ------------------------------------------------------------------ UI
    def _build_shell(self):
        # Keep PhotoImage refs alive
        self._icons = {
            "logo": get_icon("logo", 32),
            "app": get_icon("app", 28),
            "nav_merger": get_icon("file-spreadsheet", 18),
            "nav_merger_on": get_icon("file-spreadsheet-blue", 18),
            "nav_logs": get_icon("list", 18),
            "nav_analysis": get_icon("bar-chart", 18),
            "nav_settings": get_icon("settings", 18),
            "folder": get_icon("folder", 22),
            "folder_blue": get_icon("folder-blue", 22),
            "filter": get_icon("filter", 16),
            "calendar": get_icon("calendar", 16),
            "file": get_icon("file", 16),
            "table": get_icon("table", 16),
            "settings": get_icon("settings", 16),
            "status": get_icon("status", 14),
            "chevron_down": get_icon("chevron-down", 16),
            "chevron_up": get_icon("chevron-up", 16),
            "info": get_icon("info", 14),
            "x": get_icon("x", 12),
        }
        self._ph_entries = []  # (PlaceholderEntry, ph_lang_key)
        self._tooltips = []

        root = tk.Frame(self.master, bg=THEME["bg_deep"])
        root.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = tk.Frame(root, bg=THEME["sidebar"], width=230)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        brand = tk.Frame(self.sidebar, bg=THEME["sidebar"])
        brand.pack(fill="x", padx=16, pady=(22, 28))
        if self._icons["logo"]:
            tk.Label(brand, image=self._icons["logo"], bg=THEME["sidebar"]).pack(side="left")
        tk.Label(
            brand, text="  ExcelMerger", font=(THEME["font"], 13, "bold"),
            bg=THEME["sidebar"], fg=THEME["text"],
        ).pack(side="left")

        self.nav_frames = {}
        self.nav_icon_labels = {}
        self.nav_text_labels = {}
        self.nav_accent = {}
        self.nav_sub_frames = {}  # child key -> (wrap, inner, txt)
        self.analysis_expanded = True
        self.analysis_children_host = None
        self._analysis_child_keys = [
            "analysis_overview",
            "analysis_distribution",
            "analysis_datatable",
            "analysis_comparison",
            "analysis_quality",
        ]

        def _add_nav(key, icon_key, click):
            wrap = tk.Frame(self.sidebar, bg=THEME["sidebar"], cursor="hand2")
            wrap.pack(fill="x", padx=10, pady=3)
            accent = tk.Frame(wrap, bg=THEME["sidebar"], width=3)
            accent.pack(side="left", fill="y")
            inner = tk.Frame(wrap, bg=THEME["sidebar"], cursor="hand2")
            inner.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=2)
            row = tk.Frame(inner, bg=THEME["sidebar"], cursor="hand2")
            row.pack(fill="x", padx=10, pady=10)
            ic = tk.Label(row, image=self._icons.get(icon_key), bg=THEME["sidebar"], cursor="hand2")
            ic.pack(side="left")
            txt = tk.Label(
                row, text="", font=(THEME["font"], 11),
                bg=THEME["sidebar"], fg=THEME["text_sec"], cursor="hand2",
            )
            txt.pack(side="left", padx=(10, 0))
            for w in (wrap, inner, row, ic, txt, accent):
                w.bind("<Button-1>", click)
            self.nav_frames[key] = (wrap, inner)
            self.nav_icon_labels[key] = ic
            self.nav_text_labels[key] = txt
            self.nav_accent[key] = accent
            return wrap

        _add_nav("merger", "nav_merger", lambda e: self._show_page("merger"))
        _add_nav("analysis", "nav_analysis", lambda e: self._toggle_analysis_nav())

        self.analysis_children_host = tk.Frame(self.sidebar, bg=THEME["sidebar"])
        self.analysis_children_host.pack(fill="x")
        for child in self._analysis_child_keys:
            wrap = tk.Frame(self.analysis_children_host, bg=THEME["sidebar"], cursor="hand2")
            wrap.pack(fill="x", padx=(28, 10), pady=1)
            inner = tk.Frame(wrap, bg=THEME["sidebar"], cursor="hand2")
            inner.pack(fill="x", padx=4, pady=2)
            txt = tk.Label(
                inner, text="", font=(THEME["font"], 10),
                bg=THEME["sidebar"], fg=THEME["text_mute"], cursor="hand2",
                anchor="w",
            )
            txt.pack(fill="x", padx=10, pady=6)
            for w in (wrap, inner, txt):
                w.bind("<Button-1>", lambda e, k=child: self._show_page(k))
            self.nav_sub_frames[child] = (wrap, inner, txt)

        _add_nav("logs", "nav_logs", lambda e: self._show_page("logs"))
        _add_nav("settings", "nav_settings", lambda e: self._show_page("settings"))

        tk.Label(
            self.sidebar,
            text="Technology Dev.",
            font=(THEME["font"], 8),
            bg=THEME["sidebar"],
            fg=THEME["text_mute"],
        ).pack(side="bottom", pady=16)

        # Main
        self.main = tk.Frame(root, bg=THEME["bg_deep"])
        self.main.pack(side="left", fill="both", expand=True)

        self.pages = {
            "merger": tk.Frame(self.main, bg=THEME["bg_deep"]),
            "logs": tk.Frame(self.main, bg=THEME["bg_deep"]),
            "settings": tk.Frame(self.main, bg=THEME["bg_deep"]),
            "analysis_overview": tk.Frame(self.main, bg=THEME["bg_deep"]),
            "analysis_distribution": tk.Frame(self.main, bg=THEME["bg_deep"]),
            "analysis_datatable": tk.Frame(self.main, bg=THEME["bg_deep"]),
            "analysis_comparison": tk.Frame(self.main, bg=THEME["bg_deep"]),
            "analysis_quality": tk.Frame(self.main, bg=THEME["bg_deep"]),
        }
        for p in self.pages.values():
            p.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_merger_page()
        self._build_logs_page()
        self._build_placeholder_page("settings")
        self.placeholder_labels = {}
        for key in (
            "analysis_overview",
            "analysis_datatable",
            "analysis_comparison",
            "analysis_quality",
        ):
            self._build_analysis_placeholder(key)

        from distribution_page import DistributionPage
        self.distribution_page = DistributionPage(self.pages["analysis_distribution"], self)

        self._log("INFO", "Application started.")

    def _build_placeholder_page(self, key):
        page = self.pages[key]
        label = tk.Label(
            page,
            text="",
            font=(THEME["font"], 14),
            bg=THEME["bg_deep"],
            fg=THEME["text_sec"],
        )
        label.place(relx=0.5, rely=0.45, anchor="center")
        self.settings_label = label

    def _build_analysis_placeholder(self, key):
        page = self.pages[key]
        label = tk.Label(
            page,
            text="",
            font=(THEME["font"], 14),
            bg=THEME["bg_deep"],
            fg=THEME["text_sec"],
        )
        label.place(relx=0.5, rely=0.45, anchor="center")
        self.placeholder_labels[key] = label

    def _toggle_analysis_nav(self):
        # Collapse only when already inside Analysis and submenu is open
        if self.current_page in self._analysis_child_keys and self.analysis_expanded:
            self.analysis_expanded = False
            self.analysis_children_host.pack_forget()
            return
        self.analysis_expanded = True
        self.analysis_children_host.pack(fill="x", after=self.nav_frames["analysis"][0])
        target = self.current_page if self.current_page in self._analysis_child_keys else "analysis_overview"
        self._show_page(target)

    def _build_logs_page(self):
        page = self.pages["logs"]
        wrap = tk.Frame(page, bg=THEME["bg_deep"])
        wrap.pack(fill="both", expand=True, padx=28, pady=22)

        head = tk.Frame(wrap, bg=THEME["bg_deep"])
        head.pack(fill="x", pady=(0, 14))
        left = tk.Frame(head, bg=THEME["bg_deep"])
        left.pack(side="left", fill="x", expand=True)
        self.logs_title_label = tk.Label(
            left, text="Logs", font=(THEME["font"], 24, "bold"),
            bg=THEME["bg_deep"], fg=THEME["text"],
        )
        self.logs_title_label.pack(anchor="w")
        self.logs_subtitle_label = tk.Label(
            left, text="All actions and errors (English only).",
            font=(THEME["font"], 10),
            bg=THEME["bg_deep"], fg=THEME["text_sec"],
        )
        self.logs_subtitle_label.pack(anchor="w", pady=(4, 0))

        self.logs_clear_btn = VisionButton(
            head, text="Clear log", command=self._clear_activity_log,
            bg=THEME["elevated"], hover_bg=THEME["border"],
            width=120, height=36, radius=12,
            font=(THEME["font"], 10, "bold"), parent_bg=THEME["bg_deep"],
        )
        self.logs_clear_btn.pack(side="right")

        card = tk.Frame(
            wrap, bg=THEME["glass"],
            highlightbackground=THEME["border"], highlightthickness=1,
        )
        card.pack(fill="both", expand=True)
        inner = tk.Frame(card, bg=THEME["glass"])
        inner.pack(fill="both", expand=True, padx=12, pady=12)

        self.log_text = tk.Text(
            inner, font=(THEME["font"], 9),
            bg=THEME["entry_bg"], fg=THEME["text_sec"],
            insertbackground=THEME["text"], relief="flat", bd=0,
            wrap="word", state=tk.DISABLED,
        )
        sb = ttk.Scrollbar(
            inner, orient="vertical", command=self.log_text.yview,
            style="Vision.Vertical.TScrollbar",
        )
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.log_text.tag_configure("INFO", foreground=THEME["text_sec"])
        self.log_text.tag_configure("OK", foreground=THEME["success"])
        self.log_text.tag_configure("WARN", foreground="#FFD60A")
        self.log_text.tag_configure("ERROR", foreground=THEME["danger"])
        self._refresh_log_view()

    def _step_card(self, parent, title_attr):
        outer, card = glass_frame(parent)
        outer.pack(fill="x", pady=(0, 12))
        title = tk.Label(
            card,
            text="",
            font=(THEME["font"], 12, "bold"),
            bg=THEME["glass"],
            fg=THEME["text"],
            anchor="w",
        )
        title.pack(fill="x", padx=18, pady=(14, 8))
        body = tk.Frame(card, bg=THEME["glass"])
        body.pack(fill="x", padx=18, pady=(0, 16))
        setattr(self, title_attr, title)
        return body

    def _build_merger_page(self):
        page = self.pages["merger"]

        # Scrollable content
        canvas = tk.Canvas(page, bg=THEME["bg_deep"], highlightthickness=0)
        vsb = ttk.Scrollbar(page, orient="vertical", command=canvas.yview, style="Vision.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.scroll_body = tk.Frame(canvas, bg=THEME["bg_deep"])
        self._scroll_window = canvas.create_window((0, 0), window=self.scroll_body, anchor="nw")

        def _on_body_configure(_e=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e):
            canvas.itemconfig(self._scroll_window, width=e.width)

        self.scroll_body.bind("<Configure>", _on_body_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.bind_all(
            "<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )
        self.merge_canvas = canvas

        content = tk.Frame(self.scroll_body, bg=THEME["bg_deep"])
        content.pack(fill="both", expand=True, padx=28, pady=22)

        # Header
        header = tk.Frame(content, bg=THEME["bg_deep"])
        header.pack(fill="x", pady=(0, 18))

        left = tk.Frame(header, bg=THEME["bg_deep"])
        left.pack(side="left", fill="x", expand=True)
        self.product_label = tk.Label(
            left, text="", font=(THEME["font"], 24, "bold"),
            bg=THEME["bg_deep"], fg=THEME["text"],
        )
        self.product_label.pack(anchor="w")
        self.subtitle_label = tk.Label(
            left, text="", font=(THEME["font"], 10),
            bg=THEME["bg_deep"], fg=THEME["text_sec"],
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))

        lang_frame = tk.Frame(header, bg=THEME["bg_deep"])
        lang_frame.pack(side="right")
        self.lang_label = tk.Label(
            lang_frame, text="", font=(THEME["font"], 9),
            bg=THEME["bg_deep"], fg=THEME["text_sec"],
        )
        self.lang_label.pack(side="left", padx=(0, 8))
        self.lang_combo = ttk.Combobox(
            lang_frame, state="readonly", values=["English", "Polski"],
            width=10, style="Vision.TCombobox",
        )
        self.lang_combo.current(0)
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_lang_change)
        self.lang_combo.pack(side="left")

        # 1 Folder — dashed drop zone: text left, button right (target mockup)
        body = self._step_card(content, "step_folder_title")

        self.folder_drop = tk.Frame(body, bg=THEME["elevated"])
        self.folder_drop.pack(fill="x", pady=(0, 8))
        # dashed look via canvas border
        self.folder_dash = tk.Canvas(
            self.folder_drop, height=96, bg=THEME["elevated"],
            highlightthickness=0, bd=0,
        )
        self.folder_dash.pack(fill="x")
        self.folder_dash.bind("<Configure>", self._draw_folder_dash)

        drop_inner = tk.Frame(self.folder_dash, bg=THEME["elevated"])
        self._folder_window = self.folder_dash.create_window(8, 8, window=drop_inner, anchor="nw")

        # Empty state
        self.folder_empty = tk.Frame(drop_inner, bg=THEME["elevated"])
        left_empty = tk.Frame(self.folder_empty, bg=THEME["elevated"])
        left_empty.pack(side="left", fill="both", expand=True, padx=12, pady=14)
        top_e = tk.Frame(left_empty, bg=THEME["elevated"])
        top_e.pack(anchor="w")
        tk.Label(top_e, image=self._icons["folder"], bg=THEME["elevated"]).pack(side="left", padx=(0, 10))
        self.folder_title_line = tk.Label(
            top_e, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["elevated"], fg=THEME["text"],
        )
        self.folder_title_line.pack(side="left")
        self.folder_hint = tk.Label(
            left_empty, text="", font=(THEME["font"], 9),
            bg=THEME["elevated"], fg=THEME["text_sec"],
            wraplength=480, justify="left",
        )
        self.folder_hint.pack(anchor="w", pady=(6, 0), padx=(32, 0))
        self.select_btn = VisionButton(
            self.folder_empty, text="", command=self.select_folder,
            bg=THEME["accent"], hover_bg=THEME["accent_hover"],
            width=180, height=44, radius=16, parent_bg=THEME["elevated"],
            icon_name="folder-open", icon_size=18,
        )
        self.select_btn.pack(side="right", padx=16, pady=20)

        # Selected state
        self.folder_selected_row = tk.Frame(drop_inner, bg=THEME["elevated"])
        left_sel = tk.Frame(self.folder_selected_row, bg=THEME["elevated"])
        left_sel.pack(side="left", fill="x", expand=True, padx=12, pady=14)
        top_sel = tk.Frame(left_sel, bg=THEME["elevated"])
        top_sel.pack(anchor="w", fill="x")
        tk.Label(
            top_sel, image=self._icons["folder_blue"], bg=THEME["elevated"],
        ).pack(side="left", padx=(0, 10))
        self.folder_label = tk.Label(
            top_sel, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["elevated"], fg=THEME["text"],
            wraplength=480, justify="left",
        )
        self.folder_label.pack(side="left", fill="x", expand=True)
        self.folder_search_hint = tk.Label(
            left_sel, text="", font=(THEME["font"], 9),
            bg=THEME["elevated"], fg=THEME["text_mute"],
        )
        self.folder_search_hint.pack(anchor="w", pady=(6, 0), padx=(32, 0))
        self.change_folder_btn = VisionButton(
            self.folder_selected_row, text="", command=self.select_folder,
            bg=THEME["glass"], hover_bg=THEME["border"],
            width=160, height=40, radius=14, parent_bg=THEME["elevated"],
            icon_name="folder", icon_size=16, outline=True,
            font=(THEME["font"], 10, "bold"),
        )
        self.change_folder_btn.pack(side="right", padx=16, pady=20)

        self.folder_status = tk.Label(
            body, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_mute"],
        )
        self.folder_status.pack(anchor="w", pady=(0, 4))

        self.folder_empty.pack(fill="x")
        self._update_folder_card()

        # File preview (collapsed by default)
        files_card = tk.Frame(
            body, bg=THEME["glass"],
            highlightbackground=THEME["border"], highlightthickness=1,
        )
        files_card.pack(fill="x", pady=(10, 0))

        self.files_preview_header = tk.Frame(files_card, bg=THEME["glass"], cursor="hand2")
        self.files_preview_header.pack(fill="x", padx=14, pady=10)
        self.preview_header = tk.Label(
            self.files_preview_header, text="", font=(THEME["font"], 10, "bold"),
            bg=THEME["glass"], fg=THEME["text"], cursor="hand2",
        )
        self.preview_header.pack(side="left")
        self.files_preview_chevron = tk.Label(
            self.files_preview_header, image=self._icons["chevron_down"],
            bg=THEME["glass"], cursor="hand2",
        )
        self.files_preview_chevron.pack(side="right")
        for w in (self.files_preview_header, self.preview_header, self.files_preview_chevron):
            w.bind("<Button-1>", lambda e: self._toggle_files_preview())

        self.files_preview_body = tk.Frame(files_card, bg=THEME["glass"])

        prev_btns = tk.Frame(self.files_preview_body, bg=THEME["glass"])
        prev_btns.pack(anchor="w", pady=(0, 6), padx=14)
        self.files_select_all_btn = VisionButton(
            prev_btns, text="", command=self._select_all_files,
            bg=THEME["elevated"], hover_bg=THEME["border"],
            width=120, height=32, radius=12,
            font=(THEME["font"], 9, "bold"), parent_bg=THEME["glass"],
        )
        self.files_select_all_btn.pack(side="left", padx=(0, 8))
        self.files_deselect_all_btn = VisionButton(
            prev_btns, text="", command=self._deselect_all_files,
            bg=THEME["elevated"], hover_bg=THEME["border"],
            width=130, height=32, radius=12,
            font=(THEME["font"], 9, "bold"), parent_bg=THEME["glass"],
        )
        self.files_deselect_all_btn.pack(side="left")

        tree_wrap = tk.Frame(self.files_preview_body, bg=THEME["border"])
        tree_wrap.pack(fill="x", padx=14, pady=(0, 12))
        tree_inner = tk.Frame(tree_wrap, bg=THEME["glass"])
        tree_inner.pack(fill="both", expand=True, padx=1, pady=1)

        self.files_tree = ttk.Treeview(
            tree_inner, columns=("sel", "name", "path"),
            show="headings", height=7, style="Vision.Treeview",
        )
        self.files_tree.heading("sel", text="✓")
        self.files_tree.heading("name", text="File")
        self.files_tree.heading("path", text="Path")
        self.files_tree.column("sel", width=40, stretch=False, anchor="center")
        self.files_tree.column("name", width=220, stretch=False)
        self.files_tree.column("path", width=420)
        fsb = ttk.Scrollbar(tree_inner, orient="vertical", command=self.files_tree.yview, style="Vision.Vertical.TScrollbar")
        self.files_tree.configure(yscrollcommand=fsb.set)
        self.files_tree.pack(side="left", fill="both", expand=True)
        fsb.pack(side="right", fill="y")
        self.files_tree.bind("<ButtonRelease-1>", self._on_file_click)

        # 2 Types
        body = self._step_card(content, "step_types_title")
        chips = tk.Frame(body, bg=THEME["glass"])
        chips.pack(anchor="w")
        for attr, var in [
            ("check_csv", self.include_csv),
            ("check_xlsx", self.include_xlsx),
            ("check_xls", self.include_xls),
            ("check_xlsm", self.include_xlsm),
        ]:
            chip = BlueCheckchip(chips, text="", variable=var)
            chip.pack(side="left", padx=(0, 10))
            setattr(self, attr, chip)

        # 3 Advanced (collapsible) — accent border like mockup
        adv_outer = tk.Frame(content, bg=THEME["accent"], bd=0)
        adv_outer.pack(fill="x", pady=(0, 12))
        adv_card = tk.Frame(adv_outer, bg=THEME["glass"], bd=0)
        adv_card.pack(fill="both", expand=True, padx=2, pady=2)
        self.advanced_header = tk.Frame(adv_card, bg=THEME["glass"], cursor="hand2")
        self.advanced_header.pack(fill="x", padx=18, pady=12)
        tk.Label(
            self.advanced_header, image=self._icons["settings"],
            bg=THEME["glass"], cursor="hand2",
        ).pack(side="left", padx=(0, 8))
        self.step_advanced_title = tk.Label(
            self.advanced_header, text="", font=(THEME["font"], 12, "bold"),
            bg=THEME["glass"], fg=THEME["text"], cursor="hand2",
        )
        self.step_advanced_title.pack(side="left")
        self.advanced_chevron = tk.Label(
            self.advanced_header, image=self._icons["chevron_down"],
            bg=THEME["glass"], cursor="hand2",
        )
        self.advanced_chevron.pack(side="right")
        self.advanced_header.bind("<Button-1>", lambda e: self._toggle_advanced())
        self.step_advanced_title.bind("<Button-1>", lambda e: self._toggle_advanced())
        self.advanced_chevron.bind("<Button-1>", lambda e: self._toggle_advanced())

        self.advanced_body = tk.Frame(adv_card, bg=THEME["glass"])
        self._build_advanced_body(self.advanced_body)

        # 3 Merge — wide button, progress below (target mockup)
        body = self._step_card(content, "step_merge_title")
        self.merge_btn = VisionButton(
            body, text="", command=self.start_merge_thread,
            bg=THEME["accent"], hover_bg=THEME["accent_hover"],
            width=640, height=48, radius=16,
            font=(THEME["font"], 12, "bold"), parent_bg=THEME["glass"],
            icon_name="play-white", icon_size=16,
        )
        self.merge_btn.pack(fill="x", pady=(0, 12))
        body.bind(
            "<Configure>",
            lambda e: self.merge_btn.config(width=max(e.width, 200)) if e.width > 40 else None,
        )

        self.progress = ttk.Progressbar(
            body, orient="horizontal", mode="determinate",
            style="Vision.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(0, 10))

        status_row = tk.Frame(body, bg=THEME["glass"])
        status_row.pack(anchor="w", fill="x")
        tk.Label(
            status_row, image=self._icons["status"], bg=THEME["glass"],
        ).pack(side="left", padx=(0, 8))
        self.status_label = tk.Label(
            status_row, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_sec"],
            wraplength=700, justify="left",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.summary_label = tk.Label(
            body, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["success"],
            wraplength=720, justify="left",
        )
        self.summary_label.pack(anchor="w", pady=(8, 0))

        # 4 Save — button + hint on one row (target mockup)
        body = self._step_card(content, "step_save_title")
        save_row = tk.Frame(body, bg=THEME["glass"])
        save_row.pack(fill="x")
        self.save_btn = VisionButton(
            save_row, text="", command=self.save_merged_file,
            bg=THEME["elevated"], hover_bg=THEME["success"],
            width=260, height=44, radius=14, state=tk.DISABLED,
            parent_bg=THEME["glass"],
            icon_name="download", icon_size=16,
        )
        self.save_btn.pack(side="left")
        self.save_hint_label = tk.Label(
            save_row, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_mute"],
        )
        self.save_hint_label.pack(side="left", padx=(14, 0))

    def _section_title(self, parent, icon_name):
        row = tk.Frame(parent, bg=THEME["elevated"])
        row.pack(anchor="w", fill="x", pady=(0, 8))
        ic = self._icons.get(icon_name)
        if ic:
            tk.Label(row, image=ic, bg=THEME["elevated"]).pack(side="left", padx=(0, 8))
        lab = tk.Label(
            row, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["elevated"], fg=THEME["text"],
        )
        lab.pack(side="left")
        return lab

    def _draw_folder_dash(self, event=None):
        c = self.folder_dash
        w = max(c.winfo_width(), 40)
        h = max(c.winfo_height(), 96)
        c.delete("dash")
        # dashed rectangle
        dash = (6, 4)
        c.create_rectangle(
            2, 2, w - 2, h - 2,
            outline=THEME["border"], width=1, dash=dash, tags="dash",
        )
        if hasattr(self, "_folder_window"):
            c.itemconfigure(self._folder_window, width=w - 16, height=h - 16)
            c.coords(self._folder_window, 8, 8)

    def _update_folder_card(self):
        if self.folder_path:
            self.folder_empty.pack_forget()
            self.folder_selected_row.pack(fill="x")
            self.folder_label.config(text=self.folder_path)
            self.folder_status.config(text=self.folder_path, fg=THEME["text_sec"])
        else:
            self.folder_selected_row.pack_forget()
            self.folder_empty.pack(fill="x")
            self.folder_status.config(
                text=self._t("folder_not_selected"), fg=THEME["text_mute"]
            )

    def _adv_box(self, parent):
        box = tk.Frame(
            parent, bg=THEME["elevated"],
            highlightbackground=THEME["border"], highlightthickness=1,
        )
        inner = tk.Frame(box, bg=THEME["elevated"])
        inner.pack(fill="both", expand=True, padx=12, pady=10)
        return box, inner

    def _label_with_tip(self, parent, label_attr, tip_key=None):
        row = tk.Frame(parent, bg=THEME["elevated"])
        row.pack(anchor="w", fill="x")
        lab = tk.Label(
            row, text="", font=(THEME["font"], 9),
            bg=THEME["elevated"], fg=THEME["text_sec"],
        )
        lab.pack(side="left")
        setattr(self, label_attr, lab)
        if tip_key:
            tip = tk.Label(
                row, image=self._icons["info"],
                bg=THEME["elevated"], cursor="hand2",
            )
            tip.pack(side="left", padx=(6, 0))
            self._tooltips.append(Tooltip(tip, lambda k=tip_key: self._t(k)))
        return row

    def _labeled_entry(self, parent, label_attr, var, tip_key=None, ph_key=None):
        wrap = tk.Frame(parent, bg=THEME["elevated"])
        wrap.pack(fill="x", pady=(0, 8))
        self._label_with_tip(wrap, label_attr, tip_key)
        entry_row = tk.Frame(wrap, bg=THEME["elevated"])
        entry_row.pack(fill="x", pady=(3, 0))
        entry = PlaceholderEntry(entry_row, textvariable=var, placeholder="")
        entry.pack(side="left", fill="x", expand=True, ipady=5)
        if self._icons.get("x"):
            clear_btn = tk.Label(
                entry_row, image=self._icons["x"],
                bg=THEME["elevated"], cursor="hand2",
            )
            clear_btn.pack(side="left", padx=(6, 0))
            clear_btn.bind("<Button-1>", lambda _e, en=entry: en.clear())
        if ph_key:
            self._ph_entries.append((entry, ph_key))
        return entry

    def _ph_entry_in(self, parent, var, ph_key, pack_side="top"):
        entry_row = tk.Frame(parent, bg=THEME["elevated"])
        if pack_side == "top":
            entry_row.pack(fill="x", pady=(3, 0))
        else:
            entry_row.pack(fill="x", expand=True)
        entry = PlaceholderEntry(entry_row, textvariable=var, placeholder="")
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        if self._icons.get("x"):
            clear_btn = tk.Label(
                entry_row, image=self._icons["x"],
                bg=THEME["elevated"], cursor="hand2",
            )
            clear_btn.pack(side="left", padx=(6, 0))
            clear_btn.bind("<Button-1>", lambda _e, en=entry: en.clear())
        self._ph_entries.append((entry, ph_key))
        return entry

    def _build_advanced_body(self, parent):
        self._ph_entries = []
        grid = tk.Frame(parent, bg=THEME["glass"])
        grid.pack(fill="both", expand=True)
        left = tk.Frame(grid, bg=THEME["glass"])
        right = tk.Frame(grid, bg=THEME["glass"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))

        # --- File filters ---
        box, inner = self._adv_box(left)
        box.pack(fill="x", pady=(0, 10))
        self.adv_file_filters_title = self._section_title(inner, "filter")
        self._labeled_entry(
            inner, "adv_name_contains_lab", self.name_contains_var,
            tip_key="adv_name_contains_tip", ph_key="adv_name_contains_ph",
        )
        self._labeled_entry(
            inner, "adv_name_excludes_lab", self.name_excludes_var,
            tip_key="adv_name_excludes_tip", ph_key="adv_name_excludes_ph",
        )

        # --- Date filter ---
        box, inner = self._adv_box(left)
        box.pack(fill="x", pady=(0, 10))
        title_row = tk.Frame(inner, bg=THEME["elevated"])
        title_row.pack(anchor="w", fill="x", pady=(0, 8))
        if self._icons.get("calendar"):
            tk.Label(title_row, image=self._icons["calendar"], bg=THEME["elevated"]).pack(
                side="left", padx=(0, 8)
            )
        self.adv_date_title = tk.Label(
            title_row, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["elevated"], fg=THEME["text"],
        )
        self.adv_date_title.pack(side="left")
        tip = tk.Label(
            title_row, image=self._icons["info"],
            bg=THEME["elevated"], cursor="hand2",
        )
        tip.pack(side="left", padx=(6, 0))
        self._tooltips.append(Tooltip(tip, lambda: self._t("adv_date_tip")))

        self.date_preset_combo = ttk.Combobox(
            inner, state="readonly", width=22, style="Vision.TCombobox",
        )
        self.date_preset_combo.pack(anchor="w", pady=(0, 8))
        self.date_preset_combo.bind("<<ComboboxSelected>>", self._on_date_preset)

        dates = tk.Frame(inner, bg=THEME["elevated"])
        dates.pack(fill="x")
        from_f = tk.Frame(dates, bg=THEME["elevated"])
        from_f.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.adv_date_from_lab = tk.Label(
            from_f, text="", font=(THEME["font"], 9),
            bg=THEME["elevated"], fg=THEME["text_sec"],
        )
        self.adv_date_from_lab.pack(anchor="w")
        self._ph_entry_in(from_f, self.date_from_var, "adv_date_ph")
        to_f = tk.Frame(dates, bg=THEME["elevated"])
        to_f.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.adv_date_to_lab = tk.Label(
            to_f, text="", font=(THEME["font"], 9),
            bg=THEME["elevated"], fg=THEME["text_sec"],
        )
        self.adv_date_to_lab.pack(anchor="w")
        self._ph_entry_in(to_f, self.date_to_var, "adv_date_ph")

        # --- Size filter ---
        box, inner = self._adv_box(left)
        box.pack(fill="x", pady=(0, 10))
        title_row = tk.Frame(inner, bg=THEME["elevated"])
        title_row.pack(anchor="w", fill="x", pady=(0, 8))
        if self._icons.get("file"):
            tk.Label(title_row, image=self._icons["file"], bg=THEME["elevated"]).pack(
                side="left", padx=(0, 8)
            )
        self.adv_size_title = tk.Label(
            title_row, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["elevated"], fg=THEME["text"],
        )
        self.adv_size_title.pack(side="left")
        tip = tk.Label(
            title_row, image=self._icons["info"],
            bg=THEME["elevated"], cursor="hand2",
        )
        tip.pack(side="left", padx=(6, 0))
        self._tooltips.append(Tooltip(tip, lambda: self._t("adv_size_tip")))

        self.size_enable_chip = BlueCheckchip(inner, text="", variable=self.size_enable)
        self.size_enable_chip.pack(anchor="w", pady=(0, 8))
        size_row = tk.Frame(inner, bg=THEME["elevated"])
        size_row.pack(fill="x")
        min_f = tk.Frame(size_row, bg=THEME["elevated"])
        min_f.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.adv_size_min_lab = tk.Label(
            min_f, text="", font=(THEME["font"], 9),
            bg=THEME["elevated"], fg=THEME["text_sec"],
        )
        self.adv_size_min_lab.pack(anchor="w")
        self._ph_entry_in(min_f, self.size_min_var, "adv_size_min_ph")
        max_f = tk.Frame(size_row, bg=THEME["elevated"])
        max_f.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.adv_size_max_lab = tk.Label(
            max_f, text="", font=(THEME["font"], 9),
            bg=THEME["elevated"], fg=THEME["text_sec"],
        )
        self.adv_size_max_lab.pack(anchor="w")
        self._ph_entry_in(max_f, self.size_max_var, "adv_size_max_ph")

        # --- Data filters ---
        box, inner = self._adv_box(right)
        box.pack(fill="x", pady=(0, 10))
        self.adv_data_title = self._section_title(inner, "table")
        self._labeled_entry(
            inner, "adv_sheet_contains_lab", self.sheet_contains_var,
            tip_key="adv_sheet_contains_tip", ph_key="adv_sheet_contains_ph",
        )

        self._label_with_tip(inner, "adv_col_filter_lab", "adv_col_filter_tip")
        self.col_filters_host = tk.Frame(inner, bg=THEME["elevated"])
        self.col_filters_host.pack(fill="x", pady=(4, 0))
        self._add_column_filter_row()

        self.add_col_filter_btn = VisionButton(
            inner, text="", command=self._add_column_filter_row,
            bg=THEME["glass"], hover_bg=THEME["border"],
            width=180, height=34, radius=12,
            font=(THEME["font"], 9, "bold"), parent_bg=THEME["elevated"],
        )
        self.add_col_filter_btn.pack(anchor="e", pady=(8, 0))

        # --- Other options ---
        box, inner = self._adv_box(right)
        box.pack(fill="x", pady=(0, 10))
        self.adv_other_title = self._section_title(inner, "settings")
        chips = tk.Frame(inner, bg=THEME["elevated"])
        chips.pack(fill="x")
        self.opt_hidden = BlueCheckchip(chips, text="", variable=self.include_hidden)
        self.opt_hidden.pack(anchor="w", pady=2)
        self._tooltips.append(Tooltip(self.opt_hidden, lambda: self._t("adv_include_hidden_tip")))
        self.opt_subfolders = BlueCheckchip(chips, text="", variable=self.search_subfolders)
        self.opt_subfolders.pack(anchor="w", pady=2)
        self._tooltips.append(Tooltip(self.opt_subfolders, lambda: self._t("adv_subfolders_tip")))
        self.opt_skip_temp = BlueCheckchip(chips, text="", variable=self.skip_temp)
        self.opt_skip_temp.pack(anchor="w", pady=2)
        self._tooltips.append(Tooltip(self.opt_skip_temp, lambda: self._t("adv_skip_temp_tip")))
        self.opt_dupes = BlueCheckchip(chips, text="", variable=self.remove_dupes)
        self.opt_dupes.pack(anchor="w", pady=2)
        self._tooltips.append(Tooltip(self.opt_dupes, lambda: self._t("adv_remove_dupes_tip")))

        self.apply_filters_btn = VisionButton(
            parent, text="", command=self._apply_filters_and_rescan,
            bg=THEME["accent"], hover_bg=THEME["accent_hover"],
            width=160, height=40, radius=14, parent_bg=THEME["glass"],
        )
        self.apply_filters_btn.pack(anchor="e", pady=(4, 0))

        self._on_date_preset()

    def _add_column_filter_row(self):
        mode = tk.StringVar(value="contains")
        value = tk.StringVar()
        row = tk.Frame(self.col_filters_host, bg=THEME["elevated"])
        row.pack(fill="x", pady=(0, 6))
        combo = ttk.Combobox(
            row, state="readonly", width=14, style="Vision.TCombobox",
            textvariable=mode,
            values=["contains", "equals", "not_contains"],
        )
        combo.pack(side="left", padx=(0, 8))
        entry = PlaceholderEntry(row, textvariable=value, placeholder="")
        entry.pack(side="left", fill="x", expand=True, ipady=4)
        if self._icons.get("x"):
            clear_btn = tk.Label(
                row, image=self._icons["x"],
                bg=THEME["elevated"], cursor="hand2",
            )
            clear_btn.pack(side="left", padx=(6, 0))
            clear_btn.bind("<Button-1>", lambda _e, en=entry: en.clear())
        self._ph_entries.append((entry, "adv_col_value_ph"))
        entry.set_placeholder(self._t("adv_col_value_ph"))
        self.column_filters.append({
            "mode": mode, "value": value, "combo": combo,
            "frame": row, "entry": entry,
        })
        self._refresh_col_filter_combos()

    def _refresh_col_filter_combos(self):
        labels = {
            "contains": self._t("adv_col_contains"),
            "equals": self._t("adv_col_equals"),
            "not_contains": self._t("adv_col_not"),
        }
        for item in self.column_filters:
            keys = ["contains", "equals", "not_contains"]
            item["combo"]["values"] = [labels[k] for k in keys]
            cur = item["mode"].get()
            if cur in labels:
                item["combo"].set(labels[cur])
            elif cur in labels.values():
                # map display back
                for k, v in labels.items():
                    if v == cur:
                        item["mode"].set(k)
                        item["combo"].set(v)
                        break

            def on_sel(event=None, it=item, labs=labels):
                shown = it["combo"].get()
                for k, v in labs.items():
                    if v == shown:
                        it["mode"].set(k)
                        break

            item["combo"].bind("<<ComboboxSelected>>", on_sel)

    def _on_date_preset(self, event=None):
        # Resolve display label -> key
        shown = self.date_preset_combo.get() if hasattr(self, "date_preset_combo") else ""
        key_map = {
            self._t("adv_date_any"): "any",
            self._t("adv_date_24h"): "24h",
            self._t("adv_date_7d"): "7d",
            self._t("adv_date_30d"): "30d",
            self._t("adv_date_custom"): "custom",
        }
        key = key_map.get(shown, self.date_preset_var.get() or "any")
        if key in ("any", "24h", "7d", "30d", "custom"):
            self.date_preset_var.set(key)

        today = datetime.now().date()
        if key == "any":
            self.date_from_var.set("")
            self.date_to_var.set("")
        elif key == "24h":
            self.date_from_var.set((today - timedelta(days=1)).strftime("%d.%m.%Y"))
            self.date_to_var.set(today.strftime("%d.%m.%Y"))
        elif key == "7d":
            self.date_from_var.set((today - timedelta(days=7)).strftime("%d.%m.%Y"))
            self.date_to_var.set(today.strftime("%d.%m.%Y"))
        elif key == "30d":
            self.date_from_var.set((today - timedelta(days=30)).strftime("%d.%m.%Y"))
            self.date_to_var.set(today.strftime("%d.%m.%Y"))
        # custom: leave user values

    def _apply_filters_and_rescan(self):
        if self.folder_path and not self._busy:
            self._log("INFO", "Advanced filters applied — rescanning folder.")
            self._start_scan_with_modal()
        else:
            self._log("WARN", "Apply filters ignored: no folder selected or busy.")

    def _toggle_advanced(self):
        self.advanced_open = not self.advanced_open
        if self.advanced_open:
            self.advanced_body.pack(fill="x", padx=18, pady=(0, 14))
            self.advanced_chevron.config(image=self._icons["chevron_up"])
        else:
            self.advanced_body.pack_forget()
            self.advanced_chevron.config(image=self._icons["chevron_down"])

    def _toggle_files_preview(self):
        self.files_preview_open = not self.files_preview_open
        if self.files_preview_open:
            self.files_preview_body.pack(fill="x")
            self.files_preview_chevron.config(image=self._icons["chevron_up"])
        else:
            self.files_preview_body.pack_forget()
            self.files_preview_chevron.config(image=self._icons["chevron_down"])

    def _show_page(self, key):
        if key == "analysis":
            key = "analysis_overview"
        if key not in self.pages:
            return
        self.current_page = key
        self.pages[key].tkraise()

        in_analysis = key in self._analysis_child_keys
        if in_analysis and not self.analysis_expanded:
            self.analysis_expanded = True
            self.analysis_children_host.pack(fill="x", after=self.nav_frames["analysis"][0])

        for k, (wrap, inner) in self.nav_frames.items():
            if k == "analysis":
                active = in_analysis
            else:
                active = k == key
            bg = THEME["elevated"] if active else THEME["sidebar"]
            fg = THEME["text"] if active else THEME["text_sec"]
            wrap.configure(bg=THEME["sidebar"])
            inner.configure(bg=bg)
            self.nav_accent[k].configure(bg=THEME["accent"] if active else THEME["sidebar"])
            self.nav_text_labels[k].configure(bg=bg, fg=fg)
            self.nav_icon_labels[k].configure(bg=bg)
            for child in inner.winfo_children():
                child.configure(bg=bg)
                for sub in child.winfo_children():
                    try:
                        sub.configure(bg=bg)
                    except Exception:
                        pass
            if k == "merger":
                ic = self._icons["nav_merger_on"] if active else self._icons["nav_merger"]
                self.nav_icon_labels[k].configure(image=ic)

        for child_key, (wrap, inner, txt) in self.nav_sub_frames.items():
            active = child_key == key
            bg = THEME["elevated"] if active else THEME["sidebar"]
            fg = THEME["text"] if active else THEME["text_mute"]
            wrap.configure(bg=THEME["sidebar"])
            inner.configure(bg=bg)
            txt.configure(bg=bg, fg=fg)

        self._apply_nav_labels()

    def _apply_nav_labels(self):
        labels = {
            "merger": self._t("nav_merger"),
            "logs": self._t("nav_logs"),
            "analysis": self._t("nav_analysis"),
            "settings": self._t("nav_settings"),
        }
        for k, txt in self.nav_text_labels.items():
            txt.configure(text=labels.get(k, k))
        child_labels = {
            "analysis_overview": self._t("nav_analysis_overview"),
            "analysis_distribution": self._t("nav_analysis_distribution"),
            "analysis_datatable": self._t("nav_analysis_datatable"),
            "analysis_comparison": self._t("nav_analysis_comparison"),
            "analysis_quality": self._t("nav_analysis_quality"),
        }
        for k, (_w, _i, txt) in self.nav_sub_frames.items():
            txt.configure(text=child_labels.get(k, k))

    def _log(self, level, message):
        """Append an English-only activity log entry (thread-safe via after)."""
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "level": (level or "INFO").upper(),
            "msg": str(message),
        }
        self.activity_log.append(entry)

        def refresh():
            if hasattr(self, "log_text"):
                self._refresh_log_view()

        try:
            self.master.after(0, refresh)
        except Exception:
            refresh()

    def _clear_activity_log(self):
        self.activity_log = []
        self._refresh_log_view()
        self._log("INFO", "Log cleared.")

    def _refresh_log_view(self):
        if not hasattr(self, "log_text"):
            return
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        if not self.activity_log:
            self.log_text.insert(tk.END, "No log entries yet.\n", "INFO")
        else:
            for e in self.activity_log:
                line = f"[{e['ts']}] {e['level']}: {e['msg']}\n"
                tag = e["level"] if e["level"] in ("INFO", "OK", "WARN", "ERROR") else "INFO"
                self.log_text.insert(tk.END, line, tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    # -------------------------------------------------------------- language
    def _t(self, key: str, **kwargs) -> str:
        text = LANG.get(self.current_lang, LANG["en"]).get(key, "")
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def on_lang_change(self, event=None):
        self.current_lang = "pl" if self.lang_combo.get() == "Polski" else "en"
        self._log("INFO", f"Language changed to: {self.current_lang.upper()}")
        self._apply_language()

    def _apply_language(self):
        self._apply_nav_labels()
        self.product_label.config(text=self._t("product_name"))
        self.subtitle_label.config(text=self._t("subtitle"))
        self.lang_label.config(text=self._t("language"))
        self.step_folder_title.config(text=self._t("step_folder"))
        self.step_types_title.config(text=self._t("step_types"))
        self.step_advanced_title.config(text=self._t("step_advanced"))
        self.step_merge_title.config(text=self._t("step_merge"))
        self.step_save_title.config(text=self._t("step_save"))
        self.folder_title_line.config(text=self._t("folder_title_line"))
        self.folder_hint.config(text=self._t("folder_drop_hint"))
        self.select_btn.config(text=self._t("select_folder"))
        self.change_folder_btn.config(text=self._t("change_folder"))
        self.folder_search_hint.config(text=self._t("folder_search_hint"))
        self._update_folder_card()
        self.check_csv.config(text=self._t("csv"))
        self.check_xlsx.config(text=self._t("xlsx"))
        self.check_xls.config(text=self._t("xls_old"))
        self.check_xlsm.config(text=self._t("xlsm"))
        self.merge_btn.config(text=self._t("start_merge"))
        self.save_btn.config(text=self._t("save_merged"))
        if self.save_btn["state"] == tk.DISABLED:
            self.save_hint_label.config(text=self._t("save_hint"))
            self.status_label.config(text=self._t("status_ready"))
        self.files_select_all_btn.config(text=self._t("files_select_all"))
        self.files_deselect_all_btn.config(text=self._t("files_deselect_all"))
        self.preview_header.config(
            text=self._t("files_preview", count=len(self.found_files))
        )
        self.logs_title_label.config(text=self._t("logs_title"))
        self.logs_subtitle_label.config(text=self._t("logs_subtitle"))
        self.logs_clear_btn.config(text=self._t("logs_clear"))
        self.settings_label.config(text=self._t("settings_soon"))
        for key, lab in getattr(self, "placeholder_labels", {}).items():
            title = self._t(f"nav_{key}") if f"nav_{key}" in LANG["en"] else key
            # nav keys use nav_analysis_*
            map_key = {
                "analysis_overview": "nav_analysis_overview",
                "analysis_datatable": "nav_analysis_datatable",
                "analysis_comparison": "nav_analysis_comparison",
                "analysis_quality": "nav_analysis_quality",
            }.get(key)
            name = self._t(map_key) if map_key else title
            lab.config(text=f"{name} — {self._t('analysis_soon')}")
        if hasattr(self, "distribution_page"):
            self.distribution_page.apply_language()

        # Advanced labels
        self.adv_file_filters_title.config(text=self._t("adv_file_filters"))
        self.adv_name_contains_lab.config(text=self._t("adv_name_contains"))
        self.adv_name_excludes_lab.config(text=self._t("adv_name_excludes"))
        self.adv_date_title.config(text=self._t("adv_date_filter"))
        self.adv_date_from_lab.config(text=self._t("adv_date_from"))
        self.adv_date_to_lab.config(text=self._t("adv_date_to"))
        presets = [
            ("any", self._t("adv_date_any")),
            ("24h", self._t("adv_date_24h")),
            ("7d", self._t("adv_date_7d")),
            ("30d", self._t("adv_date_30d")),
            ("custom", self._t("adv_date_custom")),
        ]
        self.date_preset_combo["values"] = [p[1] for p in presets]
        cur_key = self.date_preset_var.get() if self.date_preset_var.get() in dict(presets) else "any"
        # if current value is a translated label, keep key
        if self.date_preset_var.get() not in dict(presets):
            for k, lab in presets:
                if self.date_preset_var.get() == lab:
                    cur_key = k
                    break
        self.date_preset_var.set(cur_key)
        self.date_preset_combo.set(dict(presets)[cur_key])
        self.adv_size_title.config(text=self._t("adv_size_filter"))
        self.size_enable_chip.config(text=self._t("adv_size_enable"))
        self.adv_size_min_lab.config(text=self._t("adv_size_min"))
        self.adv_size_max_lab.config(text=self._t("adv_size_max"))
        self.adv_data_title.config(text=self._t("adv_data_filters"))
        self.adv_sheet_contains_lab.config(text=self._t("adv_sheet_contains"))
        self.adv_col_filter_lab.config(text=self._t("adv_col_filter"))
        self.add_col_filter_btn.config(text=self._t("adv_add_col_filter"))
        self._refresh_col_filter_combos()
        self.adv_other_title.config(text=self._t("adv_other"))
        self.opt_hidden.config(text=self._t("adv_include_hidden"))
        self.opt_subfolders.config(text=self._t("adv_subfolders"))
        self.opt_skip_temp.config(text=self._t("adv_skip_temp"))
        self.opt_dupes.config(text=self._t("adv_remove_dupes"))
        self.apply_filters_btn.config(text=self._t("adv_apply_filters"))
        for entry, ph_key in self._ph_entries:
            entry.set_placeholder(self._t(ph_key))
        if self.last_summary["rows"]:
            self._show_summary()

    # ----------------------------------------------------------- file preview
    def _get_selected_extensions(self):
        exts = []
        if self.include_csv.get():
            exts.append(".csv")
        if self.include_xlsx.get():
            exts.append(".xlsx")
        if self.include_xls.get():
            exts.append(".xls")
        if self.include_xlsm.get():
            exts.append(".xlsm")
        return exts

    def _on_types_changed(self):
        if self.folder_path and not self._busy:
            self._start_scan_with_modal()

    def select_folder(self):
        if self._busy:
            return
        folder = filedialog.askdirectory()
        if folder:
            self.folder_path = folder
            self._update_folder_card()
            self._log("INFO", f"Folder selected: {folder}")
            self._start_scan_with_modal()

    def _start_scan_with_modal(self):
        if not self.folder_path or self._busy:
            return
        self._scan_stop.clear()
        self._set_busy(True)
        exts = ", ".join(self._get_selected_extensions()) or "(none)"
        self._log("INFO", f"Scan started in '{self.folder_path}' for types: {exts}")
        self.status_label.config(text=self._t("status_scanning"), fg=THEME["text_sec"])
        self._progress_modal = ProgressModal(
            self.master,
            self,
            title=self._t("scan_modal_title"),
            status_text=self._t("scan_progress"),
            cancel_text=self._t("scan_cancelled_body"),
            stop_event=self._scan_stop,
        )
        threading.Thread(target=self._scan_files_worker, daemon=True).start()

    def _parse_date(self, text):
        text = (text or "").strip()
        if not text:
            return None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    def _is_hidden(self, path):
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

    def _is_temp_file(self, name):
        lower = name.lower()
        return (
            name.startswith("~$")
            or lower.endswith(".tmp")
            or lower.endswith(".temp")
            or name.startswith(".~")
        )

    def _file_passes_filters(self, path):
        name = os.path.basename(path)
        name_l = name.lower()

        if self.skip_temp.get() and self._is_temp_file(name):
            return False
        if not self.include_hidden.get() and self._is_hidden(path):
            return False

        contains = self.name_contains_var.get().strip().lower()
        if contains:
            parts = [p.strip() for p in contains.replace(";", ",").split(",") if p.strip()]
            if parts and not any(p in name_l for p in parts):
                return False

        excludes = self.name_excludes_var.get().strip().lower()
        if excludes:
            parts = [p.strip() for p in excludes.replace(";", ",").split(",") if p.strip()]
            if any(p in name_l for p in parts):
                return False

        try:
            if self.size_enable.get():
                size_mb = os.path.getsize(path) / (1024 * 1024)
                try:
                    min_mb = float(self.size_min_var.get() or 0)
                except ValueError:
                    min_mb = 0
                try:
                    max_mb = float(self.size_max_var.get() or 1e12)
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
        d_from = self._parse_date(self.date_from_var.get())
        d_to = self._parse_date(self.date_to_var.get())
        if d_from and mtime < d_from:
            return False
        if d_to and mtime > d_to:
            return False
        return True

    def _scan_files_worker(self):
        found = []
        cancelled = False
        exts = self._get_selected_extensions()
        try:
            if self.folder_path and exts:
                if self.search_subfolders.get():
                    walker = os.walk(self.folder_path)
                else:
                    try:
                        names = os.listdir(self.folder_path)
                    except OSError:
                        names = []
                    walker = [(self.folder_path, [], names)]

                for root, _dirs, files in walker:
                    if self._scan_stop.is_set():
                        cancelled = True
                        break
                    for file in files:
                        if self._scan_stop.is_set():
                            cancelled = True
                            break
                        if not any(file.lower().endswith(ext) for ext in exts):
                            continue
                        path = os.path.join(root, file)
                        if self._file_passes_filters(path):
                            found.append(path)
                    if cancelled:
                        break
        except Exception as e:
            self._log("ERROR", f"Scan failed: {e}")

        def done():
            if self._progress_modal and self._progress_modal.winfo_exists():
                self._progress_modal.finish()
            self._progress_modal = None

            if cancelled or self._scan_stop.is_set():
                self.found_files = []
                self.file_vars = {}
                self._populate_files_tree()
                self.status_label.config(
                    text=self._t("scan_cancelled_body"), fg=THEME["danger"],
                )
                self._set_busy(False)
                self._log("WARN", "Scan cancelled by user.")
                messagebox.showinfo(
                    self._t("scan_cancelled_title"),
                    self._t("scan_cancelled_body"),
                )
                return

            self.found_files = sorted(found)
            self.file_vars = {p: True for p in self.found_files}
            self._populate_files_tree()
            self.status_label.config(
                text=self._t("scan_done", count=len(self.found_files)),
                fg=THEME["success"],
            )
            self._set_busy(False)
            self._log("OK", f"Scan finished. Found {len(self.found_files)} file(s).")

        self.master.after(0, done)

    def _scan_files(self):
        """Synchronous scan (used when modal is not needed)."""
        self._scan_stop.clear()
        found = []
        exts = self._get_selected_extensions()
        if self.folder_path and exts:
            if self.search_subfolders.get():
                walker = os.walk(self.folder_path)
            else:
                try:
                    names = os.listdir(self.folder_path)
                except OSError:
                    names = []
                walker = [(self.folder_path, [], names)]
            for root, _dirs, files in walker:
                for file in files:
                    if not any(file.lower().endswith(ext) for ext in exts):
                        continue
                    path = os.path.join(root, file)
                    if self._file_passes_filters(path):
                        found.append(path)
        self.found_files = sorted(found)
        self.file_vars = {p: True for p in self.found_files}
        self._populate_files_tree()

    def _apply_data_filters(self, df):
        for item in self.column_filters:
            mode = item["mode"].get()
            # mode may still be display label
            labels = {
                self._t("adv_col_contains"): "contains",
                self._t("adv_col_equals"): "equals",
                self._t("adv_col_not"): "not_contains",
            }
            mode = labels.get(mode, mode)
            val = item["value"].get().strip()
            if not val:
                continue
            text_df = df.apply(lambda col: col.map(_cell_to_display))
            if mode == "equals":
                mask = text_df.apply(
                    lambda r: r.str.lower().eq(val.lower()).any(), axis=1
                )
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

    def _populate_files_tree(self):
        self.files_tree.delete(*self.files_tree.get_children())
        for path in self.found_files:
            mark = "☑" if self.file_vars.get(path, True) else "☐"
            self.files_tree.insert(
                "", "end", iid=path,
                values=(mark, os.path.basename(path), path),
            )
        self.preview_header.config(
            text=self._t("files_preview", count=len(self.found_files))
        )

    def _on_file_click(self, event):
        if self._busy:
            return
        col = self.files_tree.identify_column(event.x)
        item = self.files_tree.identify_row(event.y)
        if not item:
            return
        if col in ("#1", "#2", "#3"):
            self.file_vars[item] = not self.file_vars.get(item, True)
            mark = "☑" if self.file_vars[item] else "☐"
            vals = list(self.files_tree.item(item, "values"))
            vals[0] = mark
            self.files_tree.item(item, values=vals)

    def _select_all_files(self):
        for p in self.found_files:
            self.file_vars[p] = True
        self._populate_files_tree()

    def _deselect_all_files(self):
        for p in self.found_files:
            self.file_vars[p] = False
        self._populate_files_tree()

    def _checked_files(self):
        return [p for p in self.found_files if self.file_vars.get(p, False)]

    # -------------------------------------------------------------- busy UI
    def _set_busy(self, busy: bool):
        self._busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.select_btn.config(state=state)
        self.change_folder_btn.config(state=state)
        self.merge_btn.config(state=state)
        self.files_select_all_btn.config(state=state)
        self.files_deselect_all_btn.config(state=state)
        self.apply_filters_btn.config(state=state)
        self.lang_combo.config(state="disabled" if busy else "readonly")
        for cb in (self.check_csv, self.check_xlsx, self.check_xls, self.check_xlsm):
            cb.config(state=state)
        if not busy and self.merged_df is not None:
            self.save_btn.config(
                state=tk.NORMAL, bg=THEME["success"], fg="#0B0B12",
                activebackground=THEME["success_hover"],
            )
        elif busy:
            self.save_btn.config(state=tk.DISABLED, bg=THEME["elevated"], fg=THEME["text"])

    # ---------------------------------------------------------------- merge
    def start_merge_thread(self):
        if self._busy:
            return
        if not self.folder_path:
            self._log("WARN", "Merge blocked: no folder selected.")
            messagebox.showwarning(self._t("msg_no_folder_title"), self._t("msg_no_folder_body"))
            return
        if not self._get_selected_extensions():
            self._log("WARN", "Merge blocked: no file types selected.")
            messagebox.showwarning(self._t("msg_no_types_title"), self._t("msg_no_types_body"))
            return
        if not self.found_files:
            self._scan_files()
        if not self._checked_files():
            self._log("WARN", "Merge blocked: no files checked.")
            self.status_label.config(text=self._t("status_no_checked"), fg=THEME["danger"])
            return

        self._set_busy(True)
        self.save_btn.config(state=tk.DISABLED, bg=THEME["elevated"])
        self.save_hint_label.config(text=self._t("save_hint"))
        self.summary_label.config(text="")
        self.merge_error_count = 0
        checked = len(self._checked_files())
        self._log("INFO", f"Merge started for {checked} selected file(s).")
        threading.Thread(target=self.merge_files, daemon=True).start()

    def merge_files(self):
        self.master.after(0, lambda: self.status_label.config(
            text=self._t("status_merging"), fg=THEME["text"]
        ))
        self.all_dataframes = []
        files = self._checked_files()
        total = len(files)

        sheet_contains = self.sheet_contains_var.get().strip()
        remove_dupes = self.remove_dupes.get()

        def set_progress(i):
            self.progress["maximum"] = total
            self.progress["value"] = i
            self.status_label.config(
                text=self._t("status_processing", current=i, total=total),
                fg=THEME["text_sec"],
            )

        self.master.after(0, lambda: set_progress(0))

        merged_count = 0
        for i, file_path in enumerate(files, 1):
            try:
                df = _read_tabular_file(file_path, sheet_contains=sheet_contains)
                if df.empty:
                    self._log("WARN", f"Skipped empty file: {os.path.basename(file_path)}")
                    self.master.after(0, lambda i=i: set_progress(i))
                    continue
                df = self._apply_data_filters(df)
                if df.empty:
                    self._log("WARN", f"No rows after filters: {os.path.basename(file_path)}")
                    self.master.after(0, lambda i=i: set_progress(i))
                    continue
                df.insert(0, "File name", os.path.basename(file_path))
                self.all_dataframes.append(df)
                merged_count += 1
                self._log("INFO", f"Merged file ({i}/{total}): {os.path.basename(file_path)} — {len(df)} row(s)")
            except Exception as e:
                self.merge_error_count += 1
                self._log("ERROR", f"{os.path.basename(file_path)}: {e}")

            self.master.after(0, lambda i=i: set_progress(i))

        dupes_removed = 0
        if self.all_dataframes:
            self.merged_df = pd.concat(self.all_dataframes, ignore_index=True)
            before = len(self.merged_df)
            if remove_dupes:
                self.merged_df = self.merged_df.drop_duplicates(keep="first").reset_index(drop=True)
                dupes_removed = before - len(self.merged_df)
                if dupes_removed:
                    self._log("INFO", f"Removed {dupes_removed} duplicate row(s).")

            self.last_summary = {
                "files": merged_count,
                "rows": len(self.merged_df),
                "cols": len(self.merged_df.columns),
                "dupes": dupes_removed,
                "errors": self.merge_error_count,
            }

            def done_ok():
                self.status_label.config(
                    text=self._t("status_done", rows=len(self.merged_df)),
                    fg=THEME["success"],
                )
                self._show_summary()
                self.save_hint_label.config(text="")
                self._set_busy(False)
                self._log(
                    "OK",
                    f"Merge completed: {merged_count} file(s), "
                    f"{len(self.merged_df)} row(s), {self.merge_error_count} error(s).",
                )

            self.master.after(0, done_ok)
        else:
            self.merged_df = None
            self.last_summary = {
                "files": 0, "rows": 0, "cols": 0,
                "dupes": 0, "errors": self.merge_error_count,
            }

            def done_empty():
                self.status_label.config(text=self._t("status_no_data"), fg=THEME["danger"])
                self._show_summary()
                self._set_busy(False)
                self.save_btn.config(state=tk.DISABLED, bg=THEME["elevated"])
                self._log("ERROR", f"Merge produced no data. Errors: {self.merge_error_count}.")

            self.master.after(0, done_empty)

    def _show_summary(self):
        s = self.last_summary
        self.summary_label.config(
            text=self._t(
                "summary_text",
                files=s["files"], rows=s["rows"], cols=s["cols"],
                dupes=s["dupes"], errors=s["errors"],
            ),
            fg=THEME["success"] if s["rows"] else THEME["text_sec"],
        )

    # ----------------------------------------------------------------- save
    def _write_csv_cancellable(self, path, df):
        chunk = 2000
        # header
        df.iloc[0:0].to_csv(path, index=False, encoding="utf-8-sig")
        for start in range(0, len(df), chunk):
            if self._save_stop.is_set():
                return False
            df.iloc[start:start + chunk].to_csv(
                path, mode="a", header=False, index=False, encoding="utf-8-sig",
            )
        return True

    def _write_excel_cancellable(self, path, df):
        try:
            from openpyxl import Workbook
        except ImportError:
            if self._save_stop.is_set():
                return False
            df.to_excel(path, index=False)
            return not self._save_stop.is_set()

        wb = Workbook(write_only=True)
        ws = wb.create_sheet(title="Sheet1")
        ws.append(list(df.columns))
        for i, row in enumerate(df.itertuples(index=False, name=None)):
            if self._save_stop.is_set():
                wb.close()
                return False
            ws.append(list(row))
            if i % 1500 == 0:
                # yield a bit so UI can process STOP
                pass
        wb.save(path)
        return True

    def save_merged_file(self):
        if self.merged_df is None:
            self._log("WARN", "Save blocked: no merged data.")
            messagebox.showwarning(self._t("msg_no_data_title"), self._t("msg_no_data_body"))
            return
        if self._busy:
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("CSV files", "*.csv"),
            ],
            title=self._t("save_merged"),
        )
        if not file_path:
            self._log("INFO", "Save cancelled in file dialog.")
            return

        self._log("INFO", f"Saving merged data to: {file_path}")
        self._save_stop.clear()
        self._set_busy(True)
        self.save_btn.config(state=tk.DISABLED)
        self.status_label.config(text=self._t("status_saving"), fg=THEME["text"])
        self._progress_modal = ProgressModal(
            self.master,
            self,
            title=self._t("save_modal_title"),
            status_text=self._t("save_progress"),
            cancel_text=self._t("save_cancelled_body"),
            stop_event=self._save_stop,
        )

        def do_save():
            out_path = file_path
            try:
                lower = file_path.lower()
                if lower.endswith(".csv"):
                    out_path = file_path
                    ok_write = self._write_csv_cancellable(out_path, self.merged_df)
                else:
                    out_path = file_path if lower.endswith(".xlsx") else file_path + ".xlsx"
                    ok_write = self._write_excel_cancellable(out_path, self.merged_df)

                if not ok_write or self._save_stop.is_set():
                    try:
                        if os.path.exists(out_path):
                            os.remove(out_path)
                    except Exception:
                        pass

                    def cancelled():
                        if self._progress_modal and self._progress_modal.winfo_exists():
                            self._progress_modal.finish()
                        self._progress_modal = None
                        self.status_label.config(
                            text=self._t("save_cancelled_body"), fg=THEME["danger"],
                        )
                        self.save_hint_label.config(
                            text="" if self.merged_df is not None else self._t("save_hint")
                        )
                        self._set_busy(False)
                        self._log("WARN", "Save cancelled by user.")
                        messagebox.showinfo(
                            self._t("save_cancelled_title"),
                            self._t("save_cancelled_body"),
                        )

                    self.master.after(0, cancelled)
                    return

                def ok():
                    if self._progress_modal and self._progress_modal.winfo_exists():
                        self._progress_modal.finish()
                    self._progress_modal = None
                    self.status_label.config(text=self._t("status_saved"), fg=THEME["success"])
                    self.save_hint_label.config(text="")
                    self._set_busy(False)
                    self._log("OK", f"File saved: {out_path}")
                    messagebox.showinfo(
                        self._t("msg_saved_title"),
                        self._t("msg_saved_body", path=out_path),
                    )

                self.master.after(0, ok)
            except Exception as e:
                err = str(e)

                def fail():
                    if self._progress_modal and self._progress_modal.winfo_exists():
                        self._progress_modal.finish()
                    self._progress_modal = None
                    self._set_busy(False)
                    self._log("ERROR", f"Save failed: {err}")
                    messagebox.showerror(
                        self._t("msg_save_error_title"),
                        self._t("msg_save_error_body", error=err),
                    )

                self.master.after(0, fail)

        threading.Thread(target=do_save, daemon=True).start()
