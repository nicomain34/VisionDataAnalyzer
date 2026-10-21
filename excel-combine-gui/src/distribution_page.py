"""Distribution analysis page UI for ExcelMerger."""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import numpy as np

from distribution_engine import (
    AnalysisResult,
    FileInfo,
    detect_schema,
    export_records_df,
    format_size,
    preview_records,
    run_distribution_analysis,
    scan_files,
)
from gui import (
    THEME,
    BlueCheckchip,
    VisionButton,
    glass_frame,
)


class HistogramCanvas(tk.Canvas):
    """Dark-theme histogram with mean/median markers."""

    def __init__(self, parent, **kwargs):
        kwargs.setdefault("bg", THEME["elevated"])
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("height", 260)
        super().__init__(parent, **kwargs)
        self.counts = np.array([])
        self.edges = np.array([])
        self.mean = None
        self.median = None
        self.log_y = False
        self.column = ""
        self._bars = []
        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda e: self.delete("tip"))

    def set_data(self, counts, edges, mean=None, median=None, log_y=False, column=""):
        self.counts = np.asarray(counts, dtype=float) if counts is not None else np.array([])
        self.edges = np.asarray(edges, dtype=float) if edges is not None else np.array([])
        self.mean = mean
        self.median = median
        self.log_y = log_y
        self.column = column or ""
        self.redraw()

    def clear(self):
        self.counts = np.array([])
        self.edges = np.array([])
        self.mean = self.median = None
        self.delete("all")

    def redraw(self):
        self.delete("all")
        self._bars = []
        w = max(self.winfo_width(), 40)
        h = max(self.winfo_height(), 40)
        pad_l, pad_r, pad_t, pad_b = 48, 16, 28, 36
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b
        if plot_w < 20 or plot_h < 20:
            return

        # axes
        self.create_line(pad_l, pad_t, pad_l, pad_t + plot_h, fill=THEME["border"], width=1)
        self.create_line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, fill=THEME["border"], width=1)

        if self.counts.size == 0 or self.edges.size < 2:
            self.create_text(
                w // 2, h // 2,
                text="Select files and click Analyze Distribution",
                fill=THEME["text_mute"], font=(THEME["font"], 10),
            )
            return

        counts = self.counts.astype(float)
        if self.log_y:
            display = np.log10(np.maximum(counts, 1e-9))
            display = np.where(counts > 0, display, 0)
        else:
            display = counts
        ymax = float(np.max(display)) if display.size else 1.0
        if ymax <= 0:
            ymax = 1.0

        n = len(counts)
        bar_w = plot_w / n
        for i, c in enumerate(display):
            bh = (c / ymax) * plot_h if ymax else 0
            x0 = pad_l + i * bar_w + 1
            x1 = pad_l + (i + 1) * bar_w - 1
            y0 = pad_t + plot_h - bh
            y1 = pad_t + plot_h
            bar_id = self.create_rectangle(
                x0, y0, x1, y1,
                fill=THEME["accent"], outline="", tags=("bar",),
            )
            self._bars.append((bar_id, i, float(counts[i]), float(self.edges[i]), float(self.edges[i + 1])))

        # mean / median markers
        xmin, xmax = float(self.edges[0]), float(self.edges[-1])
        span = xmax - xmin if xmax != xmin else 1.0

        def x_of(val):
            return pad_l + ((val - xmin) / span) * plot_w

        if self.mean is not None and np.isfinite(self.mean):
            xm = x_of(self.mean)
            self.create_line(xm, pad_t, xm, pad_t + plot_h, fill=THEME["success"], dash=(4, 3), width=2)
            self.create_text(
                xm, pad_t - 10, text=f"Mean {self.mean:.3g}",
                fill=THEME["success"], font=(THEME["font"], 8, "bold"),
            )
        if self.median is not None and np.isfinite(self.median):
            xd = x_of(self.median)
            self.create_line(xd, pad_t, xd, pad_t + plot_h, fill="#FFD60A", dash=(4, 3), width=2)
            self.create_text(
                min(xd + 40, pad_l + plot_w), pad_t + 12,
                text=f"Median {self.median:.3g}",
                fill="#FFD60A", font=(THEME["font"], 8, "bold"),
            )

        # axis labels
        self.create_text(
            pad_l + plot_w / 2, h - 10,
            text=self.column or "Value", fill=THEME["text_sec"], font=(THEME["font"], 8),
        )
        self.create_text(
            14, pad_t + plot_h / 2, text="Count", angle=90,
            fill=THEME["text_sec"], font=(THEME["font"], 8),
        )
        self.create_text(
            pad_l, pad_t + plot_h + 14, text=f"{xmin:.3g}",
            fill=THEME["text_mute"], font=(THEME["font"], 7), anchor="w",
        )
        self.create_text(
            pad_l + plot_w, pad_t + plot_h + 14, text=f"{xmax:.3g}",
            fill=THEME["text_mute"], font=(THEME["font"], 7), anchor="e",
        )

    def _on_motion(self, event):
        self.delete("tip")
        for bar_id, _i, count, lo, hi in self._bars:
            x0, y0, x1, y1 = self.coords(bar_id)
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                text = f"[{lo:.3g}, {hi:.3g})  count={int(count)}"
                self.create_rectangle(
                    event.x + 12, event.y - 22, event.x + 12 + 8 * len(text), event.y + 2,
                    fill=THEME["glass"], outline=THEME["border"], tags="tip",
                )
                self.create_text(
                    event.x + 16, event.y - 10, text=text, anchor="w",
                    fill=THEME["text"], font=(THEME["font"], 8), tags="tip",
                )
                break


class DistributionPage:
    """Full Distribution analysis workspace."""

    def __init__(self, parent, app):
        self.app = app
        self.parent = parent
        self.files: list = []
        self.columns = []
        self.result: AnalysisResult | None = None
        self._busy = False
        self._stop = threading.Event()
        self._adv_open = False
        self.mode = tk.StringVar(value="overall")
        self.chart_type = tk.StringVar(value="Histogram")
        self.group_by = tk.StringVar(value="")
        self.bins_var = tk.IntVar(value=50)
        self.log_y = tk.BooleanVar(value=False)
        self.show_stats = tk.BooleanVar(value=True)
        self.outliers_only = tk.BooleanVar(value=False)
        self.column_var = tk.StringVar(value="")
        self.source_path = ""
        self.source_is_folder = True

        self._build()

    # ------------------------------------------------------------------ build
    def _t(self, key, **kwargs):
        return self.app._t(key, **kwargs)

    def _log(self, level, msg):
        self.app._log(level, msg)

    def _card(self, parent, title_key):
        outer, inner = glass_frame(parent)
        outer.pack(fill="x", pady=(0, 10))
        title = tk.Label(
            inner, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["glass"], fg=THEME["text"], anchor="w",
        )
        title.pack(fill="x", padx=12, pady=(10, 6))
        body = tk.Frame(inner, bg=THEME["glass"])
        body.pack(fill="x", padx=12, pady=(0, 12))
        return body, title

    def _build(self):
        root = tk.Frame(self.parent, bg=THEME["bg_deep"])
        root.pack(fill="both", expand=True)

        # Header
        header = tk.Frame(root, bg=THEME["bg_deep"])
        header.pack(fill="x", padx=22, pady=(18, 10))
        left = tk.Frame(header, bg=THEME["bg_deep"])
        left.pack(side="left", fill="x", expand=True)
        self.title_lab = tk.Label(
            left, text="", font=(THEME["font"], 22, "bold"),
            bg=THEME["bg_deep"], fg=THEME["text"],
        )
        self.title_lab.pack(anchor="w")
        self.subtitle_lab = tk.Label(
            left, text="", font=(THEME["font"], 10),
            bg=THEME["bg_deep"], fg=THEME["text_sec"],
        )
        self.subtitle_lab.pack(anchor="w", pady=(2, 0))

        # Body split
        body = tk.Frame(root, bg=THEME["bg_deep"])
        body.pack(fill="both", expand=True, padx=22, pady=(0, 16))

        # LEFT config (scrollable)
        left_wrap = tk.Frame(body, bg=THEME["bg_deep"], width=320)
        left_wrap.pack(side="left", fill="y")
        left_wrap.pack_propagate(False)
        self._build_config(left_wrap)

        # RIGHT results
        right = tk.Frame(body, bg=THEME["bg_deep"])
        right.pack(side="left", fill="both", expand=True, padx=(14, 0))
        self._build_results(right)

        self.apply_language()
        self._show_empty_state()

    def _build_config(self, parent):
        canvas = tk.Canvas(parent, bg=THEME["bg_deep"], highlightthickness=0, width=320)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview, style="Vision.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        cfg = tk.Frame(canvas, bg=THEME["bg_deep"])
        win = canvas.create_window((0, 0), window=cfg, anchor="nw", width=300)
        cfg.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        # 1 Files
        body, self.card1_title = self._card(cfg, "dist_step_files")
        self.files_empty = tk.Frame(body, bg=THEME["glass"])
        self.files_empty.pack(fill="x")
        btns = tk.Frame(self.files_empty, bg=THEME["glass"])
        btns.pack(fill="x")
        self.btn_folder = VisionButton(
            btns, text="", command=self._select_folder,
            bg=THEME["accent"], hover_bg=THEME["accent_hover"],
            width=140, height=36, radius=12, parent_bg=THEME["glass"],
            icon_name="folder-open", icon_size=14,
        )
        self.btn_folder.pack(side="left", padx=(0, 8))
        self.btn_files = VisionButton(
            btns, text="", command=self._select_files,
            bg=THEME["elevated"], hover_bg=THEME["border"],
            width=120, height=36, radius=12, parent_bg=THEME["glass"],
            outline=True,
        )
        self.btn_files.pack(side="left")

        self.files_selected = tk.Frame(body, bg=THEME["glass"])
        top = tk.Frame(self.files_selected, bg=THEME["glass"])
        top.pack(fill="x")
        if self.app._icons.get("folder_blue"):
            tk.Label(top, image=self.app._icons["folder_blue"], bg=THEME["glass"]).pack(side="left", padx=(0, 8))
        self.path_lab = tk.Label(
            top, text="", font=(THEME["font"], 9, "bold"),
            bg=THEME["glass"], fg=THEME["text"], wraplength=200, justify="left",
        )
        self.path_lab.pack(side="left", fill="x", expand=True)
        self.meta_lab = tk.Label(
            self.files_selected, text="", font=(THEME["font"], 8),
            bg=THEME["glass"], fg=THEME["text_mute"],
        )
        self.meta_lab.pack(anchor="w", pady=(4, 6))
        self.btn_change = VisionButton(
            self.files_selected, text="", command=self._change_source,
            bg=THEME["elevated"], hover_bg=THEME["border"],
            width=90, height=30, radius=10, parent_bg=THEME["glass"],
            font=(THEME["font"], 9, "bold"),
        )
        self.btn_change.pack(anchor="w")

        # 2 Column
        body, self.card2_title = self._card(cfg, "dist_step_column")
        row = tk.Frame(body, bg=THEME["glass"])
        row.pack(fill="x")
        self.column_combo = ttk.Combobox(
            row, textvariable=self.column_var, state="readonly",
            style="Vision.TCombobox", width=18,
        )
        self.column_combo.pack(side="left", fill="x", expand=True)
        self.column_combo.bind("<<ComboboxSelected>>", self._on_column_selected)
        self.dtype_lab = tk.Label(
            row, text="", font=(THEME["font"], 8, "bold"),
            bg=THEME["accent"], fg=THEME["text"], padx=6, pady=2,
        )
        self.dtype_lab.pack(side="left", padx=(6, 4))
        self.btn_rescan = VisionButton(
            row, text="↻", command=self._rescan_schema,
            bg=THEME["elevated"], hover_bg=THEME["border"],
            width=34, height=30, radius=8, parent_bg=THEME["glass"],
            font=(THEME["font"], 11, "bold"),
        )
        self.btn_rescan.pack(side="left")
        self.col_hint = tk.Label(
            body, text="", font=(THEME["font"], 8),
            bg=THEME["glass"], fg=THEME["text_mute"], wraplength=270, justify="left",
        )
        self.col_hint.pack(anchor="w", pady=(6, 0))

        # 3 Options
        body, self.card3_title = self._card(cfg, "dist_step_options")
        modes = tk.Frame(body, bg=THEME["glass"])
        modes.pack(fill="x", pady=(0, 8))
        self.mode_btns = {}
        for key, label_key in [
            ("overall", "dist_mode_overall"),
            ("compare", "dist_mode_compare"),
            ("outliers", "dist_mode_outliers"),
        ]:
            b = VisionButton(
                modes, text="", command=lambda k=key: self._set_mode(k),
                bg=THEME["accent"] if key == "overall" else THEME["elevated"],
                hover_bg=THEME["accent_hover"],
                width=90, height=30, radius=10, parent_bg=THEME["glass"],
                font=(THEME["font"], 9, "bold"),
            )
            b.pack(side="left", padx=(0, 6))
            self.mode_btns[key] = b

        self.group_frame = tk.Frame(body, bg=THEME["glass"])
        self.group_lab = tk.Label(
            self.group_frame, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_sec"],
        )
        self.group_lab.pack(anchor="w")
        self.group_combo = ttk.Combobox(
            self.group_frame, textvariable=self.group_by, state="readonly",
            style="Vision.TCombobox",
        )
        self.group_combo.pack(fill="x", pady=(3, 0))

        self.chart_lab = tk.Label(
            body, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_sec"],
        )
        self.chart_lab.pack(anchor="w", pady=(8, 0))
        self.chart_combo = ttk.Combobox(
            body, textvariable=self.chart_type, state="readonly",
            values=["Histogram", "KDE", "Box Plot"],
            style="Vision.TCombobox",
        )
        self.chart_combo.pack(fill="x", pady=(3, 0))
        self.chart_combo.current(0)

        self.stats_chip = BlueCheckchip(body, text="", variable=self.show_stats)
        self.stats_chip.pack(anchor="w", pady=(8, 4))

        bins_row = tk.Frame(body, bg=THEME["glass"])
        bins_row.pack(fill="x", pady=(4, 0))
        self.bins_lab = tk.Label(
            bins_row, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_sec"],
        )
        self.bins_lab.pack(side="left")
        self.bins_val_lab = tk.Label(
            bins_row, text="50", font=(THEME["font"], 9, "bold"),
            bg=THEME["glass"], fg=THEME["text"],
        )
        self.bins_val_lab.pack(side="right")
        self.bins_scale = ttk.Scale(
            body, from_=10, to=100, orient="horizontal",
            command=self._on_bins,
        )
        self.bins_scale.set(50)
        self.bins_scale.pack(fill="x", pady=(2, 4))

        self.log_chip = BlueCheckchip(body, text="", variable=self.log_y)
        self.log_chip.pack(anchor="w", pady=(4, 4))

        # Advanced filters (collapsed)
        adv_head = tk.Frame(body, bg=THEME["glass"], cursor="hand2")
        adv_head.pack(fill="x", pady=(8, 0))
        self.adv_lab = tk.Label(
            adv_head, text="", font=(THEME["font"], 9, "bold"),
            bg=THEME["glass"], fg=THEME["text_sec"], cursor="hand2",
        )
        self.adv_lab.pack(side="left")
        self.adv_chev = tk.Label(
            adv_head, image=self.app._icons.get("chevron_down"),
            bg=THEME["glass"], cursor="hand2",
        )
        self.adv_chev.pack(side="right")
        for w in (adv_head, self.adv_lab, self.adv_chev):
            w.bind("<Button-1>", lambda e: self._toggle_adv())
        self.adv_body = tk.Frame(body, bg=THEME["glass"])
        self.adv_hint = tk.Label(
            self.adv_body, text="", font=(THEME["font"], 8),
            bg=THEME["glass"], fg=THEME["text_mute"], wraplength=270, justify="left",
        )
        self.adv_hint.pack(anchor="w", pady=6)

        self.analyze_btn = VisionButton(
            cfg, text="", command=self._start_analyze,
            bg=THEME["accent"], hover_bg=THEME["accent_hover"],
            width=280, height=44, radius=14, parent_bg=THEME["bg_deep"],
            icon_name="play-white", icon_size=14,
        )
        self.analyze_btn.pack(fill="x", pady=(4, 8))

        self.progress = ttk.Progressbar(
            cfg, orient="horizontal", mode="determinate",
            style="Vision.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(0, 4))
        self.progress_lab = tk.Label(
            cfg, text="", font=(THEME["font"], 8),
            bg=THEME["bg_deep"], fg=THEME["text_mute"], wraplength=280, justify="left",
        )
        self.progress_lab.pack(anchor="w")
        self.cancel_btn = VisionButton(
            cfg, text="STOP", command=self._cancel_analyze,
            bg=THEME["danger"], hover_bg=THEME["danger_hover"],
            width=80, height=28, radius=10, parent_bg=THEME["bg_deep"],
            font=(THEME["font"], 9, "bold"),
        )
        # packed only while busy

        self.warn_lab = tk.Label(
            cfg, text="", font=(THEME["font"], 8),
            bg=THEME["bg_deep"], fg="#FFD60A", wraplength=280, justify="left",
        )
        self.warn_lab.pack(anchor="w", pady=(6, 0))

    def _build_results(self, parent):
        # result tabs
        tabs = tk.Frame(parent, bg=THEME["bg_deep"])
        tabs.pack(fill="x", pady=(0, 8))
        self.result_tab = tk.StringVar(value="distribution")
        self.result_tab_btns = {}
        for key, lkey in [
            ("distribution", "dist_tab_distribution"),
            ("statistics", "dist_tab_statistics"),
            ("insights", "dist_tab_insights"),
            ("outliers", "dist_tab_outliers"),
        ]:
            b = tk.Label(
                tabs, text="", font=(THEME["font"], 10, "bold"),
                bg=THEME["bg_deep"], fg=THEME["text_sec"], cursor="hand2", padx=10, pady=4,
            )
            b.pack(side="left", padx=(0, 8))
            b.bind("<Button-1>", lambda e, k=key: self._set_result_tab(k))
            self.result_tab_btns[key] = b

        # scrollable results
        canvas = tk.Canvas(parent, bg=THEME["bg_deep"], highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview, style="Vision.Vertical.TScrollbar")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self.results_frame = tk.Frame(canvas, bg=THEME["bg_deep"])
        win = canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        self.results_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))

        # Chart card
        outer, card = glass_frame(self.results_frame)
        outer.pack(fill="x", pady=(0, 10))
        head = tk.Frame(card, bg=THEME["glass"])
        head.pack(fill="x", padx=14, pady=(12, 4))
        self.chart_title = tk.Label(
            head, text="", font=(THEME["font"], 12, "bold"),
            bg=THEME["glass"], fg=THEME["text"],
        )
        self.chart_title.pack(anchor="w")
        self.chart_sub = tk.Label(
            head, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_mute"],
        )
        self.chart_sub.pack(anchor="w")
        self.histogram = HistogramCanvas(card, height=280)
        self.histogram.pack(fill="x", padx=14, pady=(8, 14))

        # Stats + summary row
        row = tk.Frame(self.results_frame, bg=THEME["bg_deep"])
        row.pack(fill="x", pady=(0, 10))

        outer, card = glass_frame(row)
        outer.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.stats_title = tk.Label(
            card, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["glass"], fg=THEME["text"],
        )
        self.stats_title.pack(anchor="w", padx=12, pady=(10, 6))
        self.stats_grid = tk.Frame(card, bg=THEME["glass"])
        self.stats_grid.pack(fill="x", padx=12, pady=(0, 12))
        self.stat_labels = {}
        for i, key in enumerate(
            ["count", "mean", "median", "std", "min", "max", "p5", "p25", "p75", "p95"]
        ):
            r, c = divmod(i, 2)
            cell = tk.Frame(self.stats_grid, bg=THEME["elevated"])
            cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
            self.stats_grid.columnconfigure(c, weight=1)
            name = tk.Label(
                cell, text=key.upper(), font=(THEME["font"], 8),
                bg=THEME["elevated"], fg=THEME["text_mute"],
            )
            name.pack(anchor="w", padx=8, pady=(6, 0))
            val = tk.Label(
                cell, text="—", font=(THEME["font"], 11, "bold"),
                bg=THEME["elevated"], fg=THEME["text"],
            )
            val.pack(anchor="w", padx=8, pady=(0, 6))
            self.stat_labels[key] = (name, val)

        outer, card = glass_frame(row)
        outer.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self.summary_title = tk.Label(
            card, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["glass"], fg=THEME["text"],
        )
        self.summary_title.pack(anchor="w", padx=12, pady=(10, 6))
        self.summary_text = tk.Label(
            card, text="", font=(THEME["font"], 9),
            bg=THEME["glass"], fg=THEME["text_sec"],
            wraplength=280, justify="left",
        )
        self.summary_text.pack(anchor="w", padx=12, pady=(0, 12))

        # Compare groups
        outer, card = glass_frame(self.results_frame)
        self.group_card_outer = outer
        self.group_title = tk.Label(
            card, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["glass"], fg=THEME["text"],
        )
        self.group_title.pack(anchor="w", padx=12, pady=(10, 6))
        self.group_tree = ttk.Treeview(
            card, columns=("group", "count", "mean", "median", "std"),
            show="headings", height=5, style="Vision.Treeview",
        )
        for col, w in [("group", 120), ("count", 70), ("mean", 70), ("median", 70), ("std", 70)]:
            self.group_tree.heading(col, text=col.title())
            self.group_tree.column(col, width=w, stretch=True)
        self.group_tree.pack(fill="x", padx=12, pady=(0, 12))

        # Preview
        outer, card = glass_frame(self.results_frame)
        self.preview_outer = outer
        outer.pack(fill="x", pady=(0, 10))
        head = tk.Frame(card, bg=THEME["glass"])
        head.pack(fill="x", padx=12, pady=(10, 6))
        self.preview_title = tk.Label(
            head, text="", font=(THEME["font"], 11, "bold"),
            bg=THEME["glass"], fg=THEME["text"],
        )
        self.preview_title.pack(side="left")
        self.export_btn = VisionButton(
            head, text="", command=self._export,
            bg=THEME["elevated"], hover_bg=THEME["border"],
            width=120, height=30, radius=10, parent_bg=THEME["glass"],
            font=(THEME["font"], 9, "bold"), icon_name="download", icon_size=12,
        )
        self.export_btn.pack(side="right")
        self.outlier_chip = BlueCheckchip(
            head, text="", variable=self.outliers_only,
            command=self._refresh_preview,
        )
        self.outlier_chip.pack(side="right", padx=(0, 8))

        tree_wrap = tk.Frame(card, bg=THEME["border"])
        tree_wrap.pack(fill="x", padx=12, pady=(0, 12))
        inner = tk.Frame(tree_wrap, bg=THEME["glass"])
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.preview_tree = ttk.Treeview(
            inner, columns=("n", "file", "sheet", "value"),
            show="headings", height=8, style="Vision.Treeview",
        )
        self.preview_tree.heading("n", text="#")
        self.preview_tree.heading("file", text="File name")
        self.preview_tree.heading("sheet", text="Sheet name")
        self.preview_tree.heading("value", text="Value")
        self.preview_tree.column("n", width=40, stretch=False)
        self.preview_tree.column("file", width=180)
        self.preview_tree.column("sheet", width=100)
        self.preview_tree.column("value", width=90)
        psb = ttk.Scrollbar(inner, orient="vertical", command=self.preview_tree.yview, style="Vision.Vertical.TScrollbar")
        self.preview_tree.configure(yscrollcommand=psb.set)
        self.preview_tree.pack(side="left", fill="both", expand=True)
        psb.pack(side="right", fill="y")

        self.empty_lab = tk.Label(
            self.results_frame, text="", font=(THEME["font"], 12),
            bg=THEME["bg_deep"], fg=THEME["text_mute"],
        )

    # -------------------------------------------------------------- language
    def apply_language(self):
        self.title_lab.config(text=self._t("dist_title"))
        self.subtitle_lab.config(text=self._t("dist_subtitle"))
        self.card1_title.config(text=self._t("dist_step_files"))
        self.card2_title.config(text=self._t("dist_step_column"))
        self.card3_title.config(text=self._t("dist_step_options"))
        self.btn_folder.config(text=self._t("dist_select_folder"))
        self.btn_files.config(text=self._t("dist_select_files"))
        self.btn_change.config(text=self._t("dist_change"))
        self.mode_btns["overall"].config(text=self._t("dist_mode_overall"))
        self.mode_btns["compare"].config(text=self._t("dist_mode_compare"))
        self.mode_btns["outliers"].config(text=self._t("dist_mode_outliers"))
        self.group_lab.config(text=self._t("dist_group_by"))
        self.chart_lab.config(text=self._t("dist_chart_type"))
        self.stats_chip.config(text=self._t("dist_show_stats"))
        self.bins_lab.config(text=self._t("dist_bins"))
        self.log_chip.config(text=self._t("dist_log_scale"))
        self.adv_lab.config(text=self._t("dist_advanced_filters"))
        self.adv_hint.config(text=self._t("dist_advanced_hint"))
        self.analyze_btn.config(text=self._t("dist_analyze"))
        self.stats_title.config(text=self._t("dist_statistics"))
        self.summary_title.config(text=self._t("dist_summary"))
        self.preview_title.config(text=self._t("dist_preview"))
        self.export_btn.config(text=self._t("dist_export"))
        self.outlier_chip.config(text=self._t("dist_outliers_only"))
        self.group_title.config(text=self._t("dist_group_stats"))
        self.empty_lab.config(text=self._t("dist_empty"))
        for key, btn in self.result_tab_btns.items():
            if key == "outliers" and self.result is not None:
                n = int(np.sum(self.result.outlier_mask)) if self.result.outlier_mask.size else 0
                btn.config(text=self._t("dist_tab_outliers_n", count=n))
            else:
                btn.config(text=self._t(f"dist_tab_{key}"))
        labels = {
            "count": "Count", "mean": "Mean", "median": "Median", "std": "Std Dev",
            "min": "Min", "max": "Max", "p5": "P5", "p25": "P25", "p75": "P75", "p95": "P95",
        }
        for k, (name, _val) in self.stat_labels.items():
            name.config(text=labels.get(k, k))
        self._update_files_card()
        self._on_column_selected()

    # -------------------------------------------------------------- source
    def _show_empty_state(self):
        self.histogram.clear()
        self.chart_title.config(text=self._t("dist_chart_placeholder"))
        self.chart_sub.config(text="")
        self.summary_text.config(text=self._t("dist_empty"))
        for _n, val in self.stat_labels.values():
            val.config(text="—")
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.group_card_outer.pack_forget()

    def _update_files_card(self):
        if not self.files:
            self.files_selected.pack_forget()
            self.files_empty.pack(fill="x")
            return
        self.files_empty.pack_forget()
        self.files_selected.pack(fill="x")
        self.path_lab.config(text=self.source_path or self.files[0].path)
        total = sum(f.size for f in self.files)
        self.meta_lab.config(
            text=self._t("dist_files_meta", count=len(self.files), size=format_size(total))
        )

    def _select_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        self.source_path = folder
        self.source_is_folder = True
        self.files = scan_files(folder=folder, recursive=True)
        self._log("INFO", f"Distribution: folder selected ({len(self.files)} files): {folder}")
        self._update_files_card()
        self._rescan_schema()

    def _select_files(self):
        paths = filedialog.askopenfilenames(
            filetypes=[
                ("Excel/CSV", "*.xlsx *.xls *.xlsm *.csv"),
                ("All files", "*.*"),
            ]
        )
        if not paths:
            return
        self.source_path = os.path.dirname(paths[0]) if paths else ""
        self.source_is_folder = False
        self.files = scan_files(files=list(paths))
        self._log("INFO", f"Distribution: {len(self.files)} file(s) selected.")
        self._update_files_card()
        self._rescan_schema()

    def _change_source(self):
        if self.source_is_folder:
            self._select_folder()
        else:
            self._select_files()

    def _rescan_schema(self):
        if not self.files:
            return
        if self._busy:
            return
        self._busy = True
        self.progress_lab.config(text=self._t("dist_scanning_columns"))
        self.progress["maximum"] = len(self.files)
        self.progress["value"] = 0

        def work():
            def prog(done, total, name):
                self.app.master.after(
                    0,
                    lambda: (
                        self.progress.configure(value=done, maximum=max(total, 1)),
                        self.progress_lab.config(text=f"{self._t('dist_scanning_columns')} {name}"),
                    ),
                )

            cols, errors = detect_schema(self.files, progress=prog)
            def done():
                self._busy = False
                self.columns = cols
                self.progress_lab.config(text="")
                self.progress["value"] = 0
                names = [c.name for c in cols]
                self.column_combo["values"] = names
                if names:
                    # prefer first numeric
                    pick = next((c.name for c in cols if c.dtype == "numeric"), names[0])
                    self.column_var.set(pick)
                group_names = ["(None)"] + names
                self.group_combo["values"] = group_names
                self.group_by.set("(None)")
                self._on_column_selected()
                for err in errors:
                    self._log("ERROR", f"Distribution schema: {err}")
                if errors:
                    self.warn_lab.config(text=errors[0])
                else:
                    self.warn_lab.config(text="")
                self._log("OK", f"Distribution: detected {len(cols)} column(s).")
            self.app.master.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _on_column_selected(self, _e=None):
        name = self.column_var.get()
        info = next((c for c in self.columns if c.name == name), None)
        if not info:
            self.dtype_lab.config(text="")
            self.col_hint.config(text="")
            return
        dtype_map = {
            "numeric": self._t("dist_dtype_numeric"),
            "text": self._t("dist_dtype_text"),
            "date": self._t("dist_dtype_date"),
            "mixed": self._t("dist_dtype_mixed"),
        }
        self.dtype_lab.config(text=dtype_map.get(info.dtype, info.dtype))
        bg = THEME["accent"] if info.dtype == "numeric" else THEME["elevated"]
        self.dtype_lab.config(bg=bg)
        self.col_hint.config(
            text=self._t(
                "dist_col_coverage",
                col=info.name, found=info.file_count, total=len(self.files),
            )
        )
        if info.dtype != "numeric":
            self.col_hint.config(
                text=self._t("dist_col_not_numeric") + "  " + self.col_hint.cget("text")
            )
        # update preview heading
        self.preview_tree.heading("value", text=name or "Value")

    def _set_mode(self, key):
        self.mode.set(key)
        for k, b in self.mode_btns.items():
            b.config(bg=THEME["accent"] if k == key else THEME["elevated"])
        if key == "compare":
            self.group_frame.pack(fill="x", pady=(0, 6), before=self.chart_lab)
        else:
            self.group_frame.pack_forget()
        if key == "outliers":
            self._set_result_tab("outliers")

    def _on_bins(self, val):
        try:
            v = int(float(val))
        except ValueError:
            v = 50
        self.bins_var.set(v)
        self.bins_val_lab.config(text=str(v))

    def _toggle_adv(self):
        self._adv_open = not self._adv_open
        if self._adv_open:
            self.adv_body.pack(fill="x")
            self.adv_chev.config(image=self.app._icons.get("chevron_up"))
        else:
            self.adv_body.pack_forget()
            self.adv_chev.config(image=self.app._icons.get("chevron_down"))

    def _set_result_tab(self, key):
        self.result_tab.set(key)
        for k, b in self.result_tab_btns.items():
            active = k == key
            b.config(fg=THEME["accent"] if active else THEME["text_sec"])
        if key == "outliers":
            self.outliers_only.set(True)
            self._refresh_preview()
        elif key == "distribution":
            pass

    # -------------------------------------------------------------- analyze
    def _cancel_analyze(self):
        self._stop.set()
        self._log("WARN", "Distribution analysis cancel requested.")

    def _start_analyze(self):
        if self._busy:
            return
        if not self.files:
            messagebox.showwarning(self._t("dist_title"), self._t("dist_need_files"))
            return
        col = self.column_var.get().strip()
        if not col:
            messagebox.showwarning(self._t("dist_title"), self._t("dist_need_column"))
            return
        info = next((c for c in self.columns if c.name == col), None)
        if info and info.dtype != "numeric":
            if not messagebox.askyesno(self._t("dist_title"), self._t("dist_confirm_non_numeric")):
                return

        self._busy = True
        self._stop.clear()
        self.analyze_btn.config(state=tk.DISABLED)
        self.cancel_btn.pack(anchor="e", pady=(4, 0))
        self.progress["value"] = 0
        self.progress["maximum"] = len(self.files)
        self.progress_lab.config(text=self._t("dist_analyzing"))
        self.warn_lab.config(text="")
        group = self.group_by.get()
        if group in ("", "(None)"):
            group = ""
        mode = self.mode.get()
        bins = self.bins_var.get()
        self._log("INFO", f"Distribution analysis started: column='{col}', mode={mode}, files={len(self.files)}")

        def work():
            def prog(done, total, values, name):
                self.app.master.after(0, lambda: self._update_progress(done, total, values, name))

            try:
                result = run_distribution_analysis(
                    self.files,
                    column=col,
                    bins=bins,
                    group_by=group if mode == "compare" else "",
                    mode=mode,
                    progress=prog,
                    stop_event=self._stop,
                )
            except Exception as e:
                result = None
                err = str(e)
                self.app.master.after(0, lambda: self._analyze_failed(err))
                return
            self.app.master.after(0, lambda: self._analyze_done(result))

        threading.Thread(target=work, daemon=True).start()

    def _update_progress(self, done, total, values, name):
        self.progress["maximum"] = max(total, 1)
        self.progress["value"] = done
        self.progress_lab.config(
            text=self._t("dist_progress", done=done, total=total, values=f"{values:,}", file=name or "…")
        )

    def _analyze_failed(self, err):
        self._busy = False
        self.analyze_btn.config(state=tk.NORMAL)
        self.cancel_btn.pack_forget()
        self.progress_lab.config(text="")
        self._log("ERROR", f"Distribution analysis failed: {err}")
        messagebox.showerror(self._t("dist_title"), err)

    def _analyze_done(self, result: AnalysisResult):
        self._busy = False
        self.analyze_btn.config(state=tk.NORMAL)
        self.cancel_btn.pack_forget()
        self.progress_lab.config(text="")
        self.progress["value"] = self.progress["maximum"]
        if result is None:
            return
        self.result = result
        for err in result.errors:
            self._log("ERROR", f"Distribution: {err}")
        for w in result.warnings:
            self._log("WARN", f"Distribution: {w}")
        self.warn_lab.config(text="  |  ".join(result.warnings[:2]))

        n = int(result.stats.get("count") or 0)
        self.chart_title.config(text=self._t("dist_of", col=result.column))
        self.chart_sub.config(
            text=self._t(
                "dist_values_from",
                values=f"{n:,}",
                files=result.files_with_column,
            )
        )

        chart = self.chart_type.get()
        if chart != "Histogram":
            # KDE / Box Plot: fall back to histogram with note
            self.chart_sub.config(
                text=self.chart_sub.cget("text") + f"  ·  {chart} preview uses histogram rendering"
            )
        self.histogram.set_data(
            result.hist_counts,
            result.hist_edges,
            mean=result.stats.get("mean"),
            median=result.stats.get("median"),
            log_y=self.log_y.get(),
            column=result.column,
        )

        if self.show_stats.get():
            self._fill_stats(result.stats)
        self.summary_text.config(text="\n".join(result.summary_lines))

        oc = int(np.sum(result.outlier_mask)) if result.outlier_mask.size else 0
        self.result_tab_btns["outliers"].config(text=self._t("dist_tab_outliers_n", count=oc))

        if result.group_stats:
            self.group_card_outer.pack(fill="x", pady=(0, 10), before=self.preview_outer)
            self.group_tree.delete(*self.group_tree.get_children())
            for g, st in sorted(result.group_stats.items(), key=lambda x: -x[1].get("count", 0)):
                self.group_tree.insert(
                    "", "end",
                    values=(
                        g,
                        int(st["count"]),
                        f"{st['mean']:.4g}" if np.isfinite(st["mean"]) else "—",
                        f"{st['median']:.4g}" if np.isfinite(st["median"]) else "—",
                        f"{st['std']:.4g}" if np.isfinite(st["std"]) else "—",
                    ),
                )
        else:
            self.group_card_outer.pack_forget()

        if self.mode.get() == "outliers":
            self.outliers_only.set(True)
            self._set_result_tab("outliers")
        self._refresh_preview()
        self._log(
            "OK",
            f"Distribution done: {n} values from {result.files_with_column}/{result.files_total} files, "
            f"{oc} outliers, {len(result.errors)} file error(s).",
        )

    def _fill_stats(self, stats):
        order = ["count", "mean", "median", "std", "min", "max", "p5", "p25", "p75", "p95"]
        for key in order:
            _name, val = self.stat_labels[key]
            v = stats.get(key, float("nan"))
            if key == "count":
                val.config(text=f"{int(v):,}" if np.isfinite(v) else "—")
            else:
                val.config(text=f"{v:.4g}" if np.isfinite(v) else "—")

    def _refresh_preview(self):
        self.preview_tree.delete(*self.preview_tree.get_children())
        if not self.result:
            return
        rows = preview_records(self.result, outliers_only=self.outliers_only.get())
        col = self.result.column
        for r in rows:
            tags = ("outlier",) if r.get("Outlier") else ()
            self.preview_tree.insert(
                "", "end",
                values=(r["#"], r["File name"], r["Sheet name"], f"{r[col]:.6g}"),
                tags=tags,
            )
        self.preview_tree.tag_configure("outlier", foreground=THEME["danger"])

    def _export(self):
        if not self.result or self.result.values.size == 0:
            messagebox.showwarning(self._t("dist_title"), self._t("dist_no_export"))
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx"), ("CSV", "*.csv")],
            title=self._t("dist_export"),
        )
        if not path:
            return
        try:
            df = export_records_df(self.result, outliers_only=self.outliers_only.get())
            if path.lower().endswith(".csv"):
                df.to_csv(path, index=False, encoding="utf-8-sig")
            else:
                df.to_excel(path, index=False)
            self._log("OK", f"Distribution export saved: {path}")
            messagebox.showinfo(self._t("dist_title"), self._t("dist_export_ok", path=path))
        except Exception as e:
            self._log("ERROR", f"Distribution export failed: {e}")
            messagebox.showerror(self._t("dist_title"), str(e))
