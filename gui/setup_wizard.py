"""Setup wizard dialogs for the new 5-step rip flow.

Step 1: Scan Results — show classified titles (MAIN / DUPLICATE / EXTRA)
Step 2: Library Identity — handled by session_setup_dialog.py
Step 3: Content Mapping — pre-checked MAIN, unchecked DUPLICATE, selectable EXTRA
Step 4: Extras Classification — assign Jellyfin categories to extras
Step 5: Output Plan Preview — show exact folder structure before rip

All dialogs are Toplevel windows called from the main thread via
gui dispatch wrappers. They block until the user confirms or cancels.
"""
from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk
from typing import Sequence

from utils.classifier import ClassifiedTitle

# ---------------------------------------------------------------------------
# Style constants (match session_setup_dialog.py)
# ---------------------------------------------------------------------------

_BG        = "#0d1117"
_BG2       = "#161b22"
_BG3       = "#21262d"
_FG        = "#c9d1d9"
_FG_DIM    = "#8b949e"
_ACCENT    = "#58a6ff"
_GREEN     = "#238636"
_CANCEL_BG = "#30363d"

_LABEL_COLORS = {
    "MAIN":      "#58a6ff",
    "DUPLICATE": "#d29922",
    "EXTRA":     "#8b949e",
    "UNKNOWN":   "#f0883e",
}

# Jellyfin extras folder names per
# https://jellyfin.org/docs/general/server/media/movies/#extras
JELLYFIN_EXTRAS_CATEGORIES = [
    "Behind The Scenes",
    "Deleted Scenes",
    "Featurettes",
    "Interviews",
    "Trailers",
    "Other",
]

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ContentSelection:
    """Result of Step 3 — which titles to rip and their roles."""
    main_title_ids: list[int] = field(default_factory=list)
    extra_title_ids: list[int] = field(default_factory=list)
    skip_title_ids: list[int] = field(default_factory=list)


@dataclass
class ExtrasAssignment:
    """Result of Step 4 — maps title IDs to Jellyfin extras categories."""
    assignments: dict[int, str] = field(default_factory=dict)


@dataclass
class OutputPlan:
    """Result of Step 5 — the planned folder structure."""
    base_folder: str = ""
    main_file_label: str = ""
    extras: dict[str, list[str]] = field(default_factory=dict)
    confirmed: bool = False


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _center_over(win: tk.Toplevel, parent: tk.Misc) -> None:
    win.update_idletasks()
    px = parent.winfo_x() + (parent.winfo_width()  - win.winfo_width())  // 2
    py = parent.winfo_y() + (parent.winfo_height() - win.winfo_height()) // 2
    win.geometry(f"+{max(0, px)}+{max(0, py)}")


def _section_header(parent: tk.Misc, text: str) -> None:
    tk.Frame(parent, bg=_BG3, height=1).pack(fill="x", padx=16, pady=(14, 0))
    tk.Label(
        parent, text=f"  {text}",
        bg=_BG2, fg=_FG_DIM,
        font=("Segoe UI", 9, "bold"),
        anchor="w",
    ).pack(fill="x", padx=0)


def _format_duration(seconds: float) -> str:
    if seconds <= 0:
        return "?"
    h = int(seconds) // 3600
    m = (int(seconds) % 3600) // 60
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


def _format_size(size_bytes: float) -> str:
    if size_bytes <= 0:
        return "?"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1.0:
        return f"{gb:.1f} GB"
    return f"{size_bytes / (1024 ** 2):.0f} MB"


# ---------------------------------------------------------------------------
# Step 1: Scan Results
# ---------------------------------------------------------------------------

def show_scan_results(
    parent: tk.Misc,
    classified: list[ClassifiedTitle],
    drive_info: dict | None = None,
) -> str | None:
    """Show scan + classification results. Returns 'movie' or 'tv', or None if cancelled."""

    result: list[str | None] = [None]

    win = tk.Toplevel(parent)
    win.title("Scan Results")
    win.configure(bg=_BG2)
    win.resizable(False, False)
    win.grab_set()
    win.focus_force()

    # Header
    tk.Label(
        win, text="Step 1: Scan Results",
        bg=_BG2, fg=_ACCENT,
        font=("Segoe UI", 14, "bold"),
    ).pack(pady=(18, 4), padx=20, anchor="w")
    tk.Label(
        win, text="JellyRip has scanned and classified the disc titles.",
        bg=_BG2, fg=_FG_DIM,
        font=("Segoe UI", 10),
    ).pack(padx=20, anchor="w")

    # Drive info (if available)
    if drive_info:
        disc_type = drive_info.get("disc_type")
        libre = drive_info.get("libre_drive")
        if disc_type or libre:
            _section_header(win, "DRIVE STATUS")
            info_frame = tk.Frame(win, bg=_BG2)
            info_frame.pack(fill="x", padx=24, pady=(4, 0))
            if disc_type:
                tk.Label(
                    info_frame, text=f"Disc type: {disc_type}",
                    bg=_BG2, fg=_FG, font=("Segoe UI", 10), anchor="w",
                ).pack(fill="x")
            if libre == "enabled":
                tk.Label(
                    info_frame, text="LibreDrive: enabled",
                    bg=_BG2, fg="#3fb950", font=("Segoe UI", 10), anchor="w",
                ).pack(fill="x")
            elif libre == "possible":
                tk.Label(
                    info_frame, text="LibreDrive: possible (firmware patch may help)",
                    bg=_BG2, fg="#d29922", font=("Segoe UI", 10), anchor="w",
                ).pack(fill="x")
            elif libre == "unavailable":
                tk.Label(
                    info_frame, text="LibreDrive: not available",
                    bg=_BG2, fg="#f85149", font=("Segoe UI", 10), anchor="w",
                ).pack(fill="x")

    # Classification list
    _section_header(win, "CLASSIFIED TITLES")

    list_frame = tk.Frame(win, bg=_BG)
    list_frame.pack(fill="both", expand=True, padx=20, pady=(6, 0))

    canvas = tk.Canvas(list_frame, bg=_BG, highlightthickness=0, width=520, height=min(300, len(classified) * 36 + 10))
    scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    items_frame = tk.Frame(canvas, bg=_BG)

    items_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    canvas.create_window((0, 0), window=items_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    for ct in classified:
        row = tk.Frame(items_frame, bg=_BG)
        row.pack(fill="x", padx=4, pady=2)

        pct = int(ct.confidence * 100)
        color = _LABEL_COLORS.get(ct.label, _FG)
        dur = _format_duration(float(ct.title.get("duration_seconds", 0) or 0))
        size = _format_size(float(ct.title.get("size_bytes", 0) or 0))

        tk.Label(
            row, text=f"  {ct.label}",
            bg=_BG, fg=color,
            font=("Segoe UI", 10, "bold"),
            width=12, anchor="w",
        ).pack(side="left")
        tk.Label(
            row, text=f"{pct}%",
            bg=_BG, fg=_FG_DIM,
            font=("Segoe UI", 10),
            width=5, anchor="e",
        ).pack(side="left")
        tk.Label(
            row, text=f"  Title {ct.title_id + 1}",
            bg=_BG, fg=_FG,
            font=("Segoe UI", 10),
            width=10, anchor="w",
        ).pack(side="left")
        tk.Label(
            row, text=f"{dur}  {size}",
            bg=_BG, fg=_FG_DIM,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(side="left", padx=(8, 0))

    canvas.pack(side="left", fill="both", expand=True)
    if len(classified) > 8:
        scrollbar.pack(side="right", fill="y")

    # Summary
    main_count = sum(1 for ct in classified if ct.label == "MAIN")
    extra_count = sum(1 for ct in classified if ct.label == "EXTRA")
    dup_count = sum(1 for ct in classified if ct.label == "DUPLICATE")
    unknown_count = sum(1 for ct in classified if ct.label == "UNKNOWN")

    summary_parts = [f"{len(classified)} titles"]
    if main_count:
        summary_parts.append(f"{main_count} main")
    if extra_count:
        summary_parts.append(f"{extra_count} extras")
    if dup_count:
        summary_parts.append(f"{dup_count} duplicates")
    if unknown_count:
        summary_parts.append(f"{unknown_count} unknown")

    tk.Label(
        win, text="  ".join(summary_parts),
        bg=_BG2, fg=_FG_DIM,
        font=("Segoe UI", 9),
    ).pack(padx=20, pady=(6, 0), anchor="w")

    # Media type selection
    _section_header(win, "WHAT IS THIS DISC?")

    type_frame = tk.Frame(win, bg=_BG2)
    type_frame.pack(fill="x", padx=24, pady=(8, 0))

    def _select(media_type: str) -> None:
        result[0] = media_type
        win.destroy()

    def _cancel() -> None:
        result[0] = None
        win.destroy()

    tk.Button(
        type_frame, text="Movie",
        command=lambda: _select("movie"),
        bg=_ACCENT, fg="white",
        font=("Segoe UI", 12, "bold"),
        width=14, relief="flat",
    ).pack(side="left", padx=(0, 12))
    tk.Button(
        type_frame, text="TV Show",
        command=lambda: _select("tv"),
        bg=_ACCENT, fg="white",
        font=("Segoe UI", 12, "bold"),
        width=14, relief="flat",
    ).pack(side="left")

    # Cancel
    tk.Frame(win, bg=_BG3, height=1).pack(fill="x", padx=0, pady=(16, 0))
    btn_row = tk.Frame(win, bg=_BG2)
    btn_row.pack(pady=14, padx=20)
    tk.Button(
        btn_row, text="Cancel",
        command=_cancel,
        bg=_CANCEL_BG, fg=_FG_DIM,
        font=("Segoe UI", 10),
        width=10, relief="flat",
    ).pack()

    win.bind("<Escape>", lambda _e: _cancel())
    win.protocol("WM_DELETE_WINDOW", _cancel)
    _center_over(win, parent)
    win.wait_window()
    return result[0]


# ---------------------------------------------------------------------------
# Step 3: Content Mapping
# ---------------------------------------------------------------------------

def show_content_mapping(
    parent: tk.Misc,
    classified: list[ClassifiedTitle],
) -> ContentSelection | None:
    """Let user confirm which titles to rip based on classification.

    MAIN titles are pre-checked, DUPLICATES unchecked, EXTRAS selectable.
    Returns ContentSelection or None if cancelled.
    """
    result: list[ContentSelection | None] = [None]

    win = tk.Toplevel(parent)
    win.title("Content Mapping")
    win.configure(bg=_BG2)
    win.resizable(False, False)
    win.grab_set()
    win.focus_force()

    # Header
    tk.Label(
        win, text="Step 3: Content Mapping",
        bg=_BG2, fg=_ACCENT,
        font=("Segoe UI", 14, "bold"),
    ).pack(pady=(18, 4), padx=20, anchor="w")
    tk.Label(
        win, text="Select which titles to rip. MAIN is pre-selected; duplicates are unchecked.",
        bg=_BG2, fg=_FG_DIM,
        font=("Segoe UI", 10),
    ).pack(padx=20, anchor="w")

    _section_header(win, "TITLES")

    # Scrollable list with checkboxes
    list_frame = tk.Frame(win, bg=_BG)
    list_frame.pack(fill="both", expand=True, padx=20, pady=(6, 0))

    canvas = tk.Canvas(list_frame, bg=_BG, highlightthickness=0, width=560, height=min(350, len(classified) * 36 + 10))
    scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
    items_frame = tk.Frame(canvas, bg=_BG)

    items_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
    )
    canvas.create_window((0, 0), window=items_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    check_vars: dict[int, tk.BooleanVar] = {}

    for ct in classified:
        tid = ct.title_id
        # Pre-check MAIN and EXTRA, uncheck DUPLICATE and UNKNOWN
        default_on = ct.label in ("MAIN", "EXTRA")
        var = tk.BooleanVar(value=default_on)
        check_vars[tid] = var

        row = tk.Frame(items_frame, bg=_BG)
        row.pack(fill="x", padx=4, pady=2)

        pct = int(ct.confidence * 100)
        color = _LABEL_COLORS.get(ct.label, _FG)
        dur = _format_duration(float(ct.title.get("duration_seconds", 0) or 0))
        size = _format_size(float(ct.title.get("size_bytes", 0) or 0))

        cb = tk.Checkbutton(
            row, variable=var,
            bg=_BG, fg=_FG,
            selectcolor=_BG3,
            activebackground=_BG,
            activeforeground=_FG,
        )
        cb.pack(side="left")

        tk.Label(
            row, text=f"Title {tid + 1}",
            bg=_BG, fg=_FG,
            font=("Segoe UI", 10),
            width=9, anchor="w",
        ).pack(side="left")
        tk.Label(
            row, text=f"{ct.label}",
            bg=_BG, fg=color,
            font=("Segoe UI", 10, "bold"),
            width=12, anchor="w",
        ).pack(side="left")
        tk.Label(
            row, text=f"({pct}%)",
            bg=_BG, fg=_FG_DIM,
            font=("Segoe UI", 10),
            width=6, anchor="w",
        ).pack(side="left")
        tk.Label(
            row, text=f"{dur}  {size}",
            bg=_BG, fg=_FG_DIM,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(side="left", padx=(8, 0))

    canvas.pack(side="left", fill="both", expand=True)
    if len(classified) > 9:
        scrollbar.pack(side="right", fill="y")

    # Buttons
    tk.Frame(win, bg=_BG3, height=1).pack(fill="x", padx=0, pady=(16, 0))
    btn_row = tk.Frame(win, bg=_BG2)
    btn_row.pack(pady=14, padx=20)

    def _submit() -> None:
        main_ids: list[int] = []
        extra_ids: list[int] = []
        skip_ids: list[int] = []

        for ct in classified:
            tid = ct.title_id
            checked = check_vars[tid].get()
            if not checked:
                skip_ids.append(tid)
            elif ct.label == "MAIN":
                main_ids.append(tid)
            elif ct.label in ("EXTRA", "UNKNOWN"):
                extra_ids.append(tid)
            else:
                # DUPLICATE that user explicitly checked
                extra_ids.append(tid)

        if not main_ids and not extra_ids:
            return  # nothing selected

        result[0] = ContentSelection(
            main_title_ids=main_ids,
            extra_title_ids=extra_ids,
            skip_title_ids=skip_ids,
        )
        win.destroy()

    def _cancel() -> None:
        result[0] = None
        win.destroy()

    tk.Button(
        btn_row, text="Cancel",
        command=_cancel,
        bg=_CANCEL_BG, fg=_FG_DIM,
        font=("Segoe UI", 10),
        width=10, relief="flat",
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_row, text="Next  \u2192",
        command=_submit,
        bg=_GREEN, fg="white",
        font=("Segoe UI", 11, "bold"),
        width=14, relief="flat",
    ).pack(side="left")

    win.bind("<Return>", lambda _e: _submit())
    win.bind("<Escape>", lambda _e: _cancel())
    win.protocol("WM_DELETE_WINDOW", _cancel)
    _center_over(win, parent)
    win.wait_window()
    return result[0]


# ---------------------------------------------------------------------------
# Step 4: Extras Classification
# ---------------------------------------------------------------------------

def show_extras_classification(
    parent: tk.Misc,
    extra_titles: list[ClassifiedTitle],
) -> ExtrasAssignment | None:
    """Let user assign Jellyfin extras categories to selected extra titles.

    Returns ExtrasAssignment or None if cancelled.
    Skipped (returns empty assignment) if no extra titles.
    """
    if not extra_titles:
        return ExtrasAssignment()

    result: list[ExtrasAssignment | None] = [None]

    win = tk.Toplevel(parent)
    win.title("Extras Classification")
    win.configure(bg=_BG2)
    win.resizable(False, False)
    win.grab_set()
    win.focus_force()

    # Header
    tk.Label(
        win, text="Step 4: Classify Extras",
        bg=_BG2, fg=_ACCENT,
        font=("Segoe UI", 14, "bold"),
    ).pack(pady=(18, 4), padx=20, anchor="w")
    tk.Label(
        win, text="Assign each extra to a Jellyfin category for correct folder placement.",
        bg=_BG2, fg=_FG_DIM,
        font=("Segoe UI", 10),
    ).pack(padx=20, anchor="w")

    _section_header(win, "EXTRAS")

    items_frame = tk.Frame(win, bg=_BG)
    items_frame.pack(fill="both", expand=True, padx=20, pady=(6, 0))

    combo_vars: dict[int, tk.StringVar] = {}

    for ct in extra_titles:
        tid = ct.title_id
        dur = _format_duration(float(ct.title.get("duration_seconds", 0) or 0))
        size = _format_size(float(ct.title.get("size_bytes", 0) or 0))
        name = ct.title.get("name", "") or f"Title {tid + 1}"

        row = tk.Frame(items_frame, bg=_BG)
        row.pack(fill="x", padx=4, pady=3)

        tk.Label(
            row, text=f"Title {tid + 1}",
            bg=_BG, fg=_FG,
            font=("Segoe UI", 10),
            width=9, anchor="w",
        ).pack(side="left")
        tk.Label(
            row, text=f"{dur}  {size}",
            bg=_BG, fg=_FG_DIM,
            font=("Segoe UI", 10),
            width=16, anchor="w",
        ).pack(side="left")
        tk.Label(
            row, text="\u2192",
            bg=_BG, fg=_FG_DIM,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=(4, 4))

        var = tk.StringVar(value="Featurettes")
        combo_vars[tid] = var
        combo = ttk.Combobox(
            row, textvariable=var,
            values=JELLYFIN_EXTRAS_CATEGORIES,
            state="readonly", width=20,
        )
        combo.pack(side="left")

    # Buttons
    tk.Frame(win, bg=_BG3, height=1).pack(fill="x", padx=0, pady=(16, 0))
    btn_row = tk.Frame(win, bg=_BG2)
    btn_row.pack(pady=14, padx=20)

    def _submit() -> None:
        assignments = {tid: var.get() for tid, var in combo_vars.items()}
        result[0] = ExtrasAssignment(assignments=assignments)
        win.destroy()

    def _cancel() -> None:
        result[0] = None
        win.destroy()

    tk.Button(
        btn_row, text="Cancel",
        command=_cancel,
        bg=_CANCEL_BG, fg=_FG_DIM,
        font=("Segoe UI", 10),
        width=10, relief="flat",
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_row, text="Next  \u2192",
        command=_submit,
        bg=_GREEN, fg="white",
        font=("Segoe UI", 11, "bold"),
        width=14, relief="flat",
    ).pack(side="left")

    win.bind("<Return>", lambda _e: _submit())
    win.bind("<Escape>", lambda _e: _cancel())
    win.protocol("WM_DELETE_WINDOW", _cancel)
    _center_over(win, parent)
    win.wait_window()
    return result[0]


# ---------------------------------------------------------------------------
# Step 5: Output Plan Preview
# ---------------------------------------------------------------------------

def build_output_tree(
    base_folder: str,
    main_label: str,
    extras_map: dict[str, list[str]],
) -> list[str]:
    """Build a flat list of lines representing the output folder tree.

    Example output:
        Movies/
          Inception (2010)/
            Inception (2010).mkv
            Behind The Scenes/
              Making Of.mkv
            Featurettes/
              Dream Explained.mkv
    """
    root_name = os.path.basename(base_folder)
    parent_name = os.path.basename(os.path.dirname(base_folder))
    lines: list[str] = []
    lines.append(f"{parent_name}/")
    lines.append(f"  {root_name}/")
    lines.append(f"    {main_label}")

    for category in sorted(extras_map.keys()):
        files = extras_map[category]
        if not files:
            continue
        lines.append(f"    {category}/")
        for f in files:
            lines.append(f"      {f}")

    return lines


def show_output_plan(
    parent: tk.Misc,
    base_folder: str,
    main_label: str,
    extras_map: dict[str, list[str]],
) -> bool:
    """Show the planned output folder structure. Returns True to confirm, False to cancel."""

    result: list[bool] = [False]

    win = tk.Toplevel(parent)
    win.title("Output Plan")
    win.configure(bg=_BG2)
    win.resizable(False, False)
    win.grab_set()
    win.focus_force()

    # Header
    tk.Label(
        win, text="Step 5: Output Plan",
        bg=_BG2, fg=_ACCENT,
        font=("Segoe UI", 14, "bold"),
    ).pack(pady=(18, 4), padx=20, anchor="w")
    tk.Label(
        win, text="This is exactly what JellyRip will create. No guessing, no surprises.",
        bg=_BG2, fg=_FG_DIM,
        font=("Segoe UI", 10),
    ).pack(padx=20, anchor="w")

    _section_header(win, "FOLDER STRUCTURE")

    tree_lines = build_output_tree(base_folder, main_label, extras_map)

    tree_frame = tk.Frame(win, bg=_BG)
    tree_frame.pack(fill="both", expand=True, padx=20, pady=(6, 4))

    tree_text = tk.Text(
        tree_frame,
        bg=_BG, fg="#3fb950",
        font=("Consolas", 11),
        relief="flat",
        height=min(20, len(tree_lines) + 1),
        width=60,
        state="normal",
        wrap="none",
    )
    tree_text.insert("1.0", "\n".join(tree_lines))
    tree_text.configure(state="disabled")
    tree_text.pack(fill="both", expand=True)

    # Destination path
    tk.Label(
        win, text=f"Destination: {base_folder}",
        bg=_BG2, fg=_FG_DIM,
        font=("Segoe UI", 9),
    ).pack(padx=20, pady=(4, 0), anchor="w")

    # Buttons
    tk.Frame(win, bg=_BG3, height=1).pack(fill="x", padx=0, pady=(16, 0))
    btn_row = tk.Frame(win, bg=_BG2)
    btn_row.pack(pady=14, padx=20)

    def _confirm() -> None:
        result[0] = True
        win.destroy()

    def _cancel() -> None:
        result[0] = False
        win.destroy()

    tk.Button(
        btn_row, text="Cancel",
        command=_cancel,
        bg=_CANCEL_BG, fg=_FG_DIM,
        font=("Segoe UI", 10),
        width=10, relief="flat",
    ).pack(side="left", padx=(0, 8))
    tk.Button(
        btn_row, text="Start Rip",
        command=_confirm,
        bg=_GREEN, fg="white",
        font=("Segoe UI", 12, "bold"),
        width=14, relief="flat",
    ).pack(side="left")

    win.bind("<Return>", lambda _e: _confirm())
    win.bind("<Escape>", lambda _e: _cancel())
    win.protocol("WM_DELETE_WINDOW", _cancel)
    _center_over(win, parent)
    win.wait_window()
    return result[0]
