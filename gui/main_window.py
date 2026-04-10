"""GUI layer implementation."""


import glob
import json
import os
import platform
import queue as queue_module
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from shared.event import Event
from ui.adapters import UIAdapter


if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    class _TaskbarProgress:
        """ITaskbarList3 taskbar progress overlay — Windows only."""
        TBPF_NOPROGRESS = 0
        TBPF_NORMAL     = 2
        TBPF_ERROR      = 4

        def __init__(self, hwnd):
            self._hwnd = hwnd
            self._com  = None
            try:
                clsid = ctypes.c_buffer(
                    b'\x55\xb9\xfb\x56\x37\x13\x43\x42'
                    b'\x9a\xdc\x9c\xc6\x04\x2e\x63\x33', 16)
                iid = ctypes.c_buffer(
                    b'\x91\xfb\x1a\xea\x28\x9e\x86\x4b'
                    b'\x90\xe9\x9e\x9f\x8a\x5e\xef\xaf', 16)
                obj = ctypes.c_void_p()
                hr = ctypes.windll.ole32.CoCreateInstance(
                    clsid, None, 1, iid, ctypes.byref(obj))
                if hr == 0:
                    self._com = obj
                    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.c_void_p))
                    ctypes.CFUNCTYPE(
                        ctypes.HRESULT, ctypes.c_void_p
                    )(vtbl[0][3])(obj)
            except Exception:
                pass

        def set_value(self, current, total):
            if not self._com or total <= 0:
                return
            try:
                vtbl = ctypes.cast(self._com, ctypes.POINTER(ctypes.c_void_p))
                fn = ctypes.CFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.wintypes.HWND,
                    ctypes.c_ulonglong, ctypes.c_ulonglong
                )(vtbl[0][9])
                fn(self._com, self._hwnd, current, total)
            except Exception:
                pass

        def set_state(self, state):
            if not self._com:
                return
            try:
                vtbl = ctypes.cast(self._com, ctypes.POINTER(ctypes.c_void_p))
                fn = ctypes.CFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.wintypes.HWND, ctypes.c_int
                )(vtbl[0][10])
                fn(self._com, self._hwnd, state)
            except Exception:
                pass

        def clear(self):
            self.set_state(self.TBPF_NOPROGRESS)

else:
    class _TaskbarProgress:
        TBPF_NOPROGRESS = 0
        TBPF_NORMAL     = 2
        TBPF_ERROR      = 4
        def __init__(self, hwnd): pass
        def set_value(self, c, t): pass
        def set_state(self, s):   pass
        def clear(self):          pass

from shared.runtime import (
    CONFIG_FILE,
    DEFAULTS,
    RIP_ATTEMPT_FLAGS,
    __version__,
    _duration_debug_warn,
    _safe_int_debug_warn,
    configure_duration_debug,
    configure_safe_int_debug,
    get_config_dir,
)

from config import (
    auto_locate_ffmpeg,
    auto_locate_handbrake,
    auto_locate_tools,
    load_config,
    resolve_ffprobe,
    save_config,
    should_keep_current_tool_path,
    validate_ffmpeg,
    validate_ffprobe,
    validate_handbrake,
    validate_makemkvcon,
)
from controller.controller import RipperController
from controller.naming import (
    build_fallback_title,
    build_naming_preview_text,
    normalize_naming_mode,
    resolve_naming_mode,
)
from engine.ripper_engine import RipperEngine
from transcode.engine import (
    FFMPEG_SOURCE_MODE_SAFE_COPY,
    describe_ffmpeg_source_mode,
    normalize_ffmpeg_source_mode,
)
from transcode.planner import (
    FFMPEG_SOURCE_MODE_LABEL_TO_VALUE,
    build_transcode_plan,
    ffmpeg_source_mode_label,
    suggest_transcode_output_root,
    transcode_backend_label,
)
from transcode.profiles import ProfileLoader
from transcode.queue_builder import (
    build_queue_jobs,
    build_recommendation_job,
    build_transcode_queue,
    required_output_directories,
)
from transcode.recommendations import (
    build_ffmpeg_recommendations,
    format_analysis_summary,
    probe_media_for_recommendation,
)
from utils.helpers import (
    get_available_drives,
    is_network_path,
    make_rip_folder_name,
)
from utils.scoring import choose_best_title, format_audio_summary

from gui.update_ui import check_for_updates, launch_downloaded_update


HANDBRAKE_PRESETS = [
    "Fast 1080p30",
    "HQ 1080p30 Surround",
    "Fast 2160p60 4K HEVC",
    "HQ 2160p60 4K HEVC Surround",
    "Super HQ 1080p30 Surround",
]
TRANSCODE_PROFILE_FILENAME = "transcode_profiles.json"


def _ffmpeg_source_mode_label(value: str) -> str:
    return ffmpeg_source_mode_label(value)


def _transcode_backend_label(backend: str) -> str:
    return transcode_backend_label(backend)


def _suggest_transcode_output_root(scan_root: str, backend: str) -> str:
    return suggest_transcode_output_root(scan_root, backend)


def _build_transcode_plan(
    scan_root: str,
    selected_paths: list[str],
    output_root: str,
) -> list[dict[str, str]]:
    return build_transcode_plan(scan_root, selected_paths, output_root)


class JellyRipperGUI(tk.Tk, UIAdapter):
    def auto_detect_existing_folder_mode(self, folder_path):
        """
        Auto-detect mode for an existing folder:
        - If folder is under tv_folder, default to 'no' for order prompt.
        - If folder is under movies_folder, default to 'main'.
        """
        tv_folder = self.cfg.get('tv_folder', '').lower()
        movies_folder = self.cfg.get('movies_folder', '').lower()
        folder_path_l = folder_path.lower()
        if tv_folder and folder_path_l.startswith(tv_folder):
            return 'tv_no_order'  # TV: quick no for order
        if movies_folder and folder_path_l.startswith(movies_folder):
            return 'movie_main'   # Movie: main
        return None


    # --- UIAdapter interface ---
    def handle_event(self, event: Event) -> None:
        if event.type == "progress":
            percent = event.data.get("percent")
            if isinstance(percent, (int, float)):
                self.on_progress(event.job_id, float(percent))
            return

        if event.type == "log":
            self.on_log(event.job_id, str(event.data.get("message", "")))
            return

        if event.type == "done":
            self.on_complete(event.job_id)
            return

        if event.type == "error":
            raw_error = event.data.get("error", "Unknown error")
            error = raw_error if isinstance(raw_error, Exception) else Exception(str(raw_error))
            self.on_error(event.job_id, error)

    def on_progress(self, _job_id: str, value: float) -> None:
        self.set_progress(value)

    def on_log(self, _job_id: str, message: str) -> None:
        self.append_log(message)

    def on_error(self, job_id: str, error: Exception) -> None:
        title = f"Job {job_id}" if job_id else "Rip Error"
        self.show_error(title, str(error))

    def on_complete(self, _job_id: str) -> None:
        self.set_progress(100)

    def __init__(self, cfg):
        """
        LAYER 3 — GUI

        Display and input layer. All tkinter lives here and only here.

        Owns all widgets, user prompts, progress indicators, and the inline
        yes/no and text input UI. Makes no content decisions.

        Threading model: all GUI updates must happen on the main thread via
        self.after(). Worker threads communicate through:
          - message_queue → process_queue() polls every 100ms for log lines
          - threading.Event for ask_input() and ask_yesno() blocking calls
          - _run_on_main() for one-off calls that need a return value

        Never call engine or controller methods directly from widget
        callbacks. Always go through start_task() which runs the target
        in a daemon thread.
        """
        super().__init__()
        self.cfg   = cfg
        self.title(f"Jellyfin Raw Ripper v{__version__}")
        self.geometry("1200x900")
        self.minsize(1000, 750)
        self.configure(bg="#0d1117")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.message_queue = queue_module.Queue()
        self.engine        = RipperEngine(cfg)
        self.controller    = RipperController(self.engine, self)
        self.rip_thread    = None
        self._settings_window = None
        self._input_result = None
        self._input_event  = threading.Event()
        self._input_active = False
        self._input_lock   = threading.Lock()
        self._log_widget_lock = threading.Lock()

        configure_safe_int_debug(
            cfg.get("opt_debug_safe_int", False),
            self.controller.log
        )
        configure_duration_debug(
            cfg.get("opt_debug_duration", False),
            self.controller.log
        )

        self.build_interface()
        self.controller.log(f"Jellyfin Raw Ripper v{__version__} started")
        self.controller.log("Choose a mode to begin")
        self._taskbar_progress = None
        self.after(500, self._init_taskbar)
        # Schedule process_queue last to guarantee all widgets are initialized
        self.after(100, self.process_queue)

    def _append_log_text_main(self, msg, tag=None):
        """Append one line to the log widget from the Tk main thread only."""
        with self._log_widget_lock:
            self.log_text.config(state="normal")
            text = msg if msg.endswith("\n") else f"{msg}\n"
            if tag:
                self.log_text.insert("end", text, tag)
            else:
                self.log_text.insert("end", text)
            # Trim widget to prevent unbounded memory growth in long sessions.
            line_count = int(self.log_text.index("end").split(".")[0]) - 1
            cap = int(self.cfg.get("opt_log_cap_lines", 300000))
            if line_count > cap:
                trim = int(self.cfg.get("opt_log_trim_lines", 200000))
                self.log_text.delete("1.0", f"{line_count - trim}.0")
            # Only auto-scroll if user is already near the bottom.
            visible_end = self.log_text.yview()[1]
            if visible_end > 0.95:
                self.log_text.see("end")
            self.log_text.config(state="disabled")

    def build_interface(self):
        BG = "#0d1117"
        self.configure(bg=BG)

        header = tk.Frame(self, bg="#161b22")
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"JELLYFIN RAW RIPPER",
            font=("Segoe UI", 24, "bold"),
            bg="#161b22", fg="#58a6ff"
        ).pack(pady=12)

        drive_frame = tk.Frame(self, bg=BG)
        drive_frame.pack(fill="x", padx=20, pady=(8, 0))
        tk.Label(
            drive_frame, text="Drive:",
            bg=BG, fg="#8b949e",
            font=("Segoe UI", 10)
        ).pack(side="left", padx=(0, 8))
        self.drive_var     = tk.StringVar(value="Loading drives...")
        self.drive_options = [(0, "Default Drive (disc:0)")]
        self.drive_menu    = ttk.Combobox(
            drive_frame, textvariable=self.drive_var,
            values=["Loading drives..."],
            state="readonly", width=38
        )
        self.drive_menu.bind(
            "<<ComboboxSelected>>", self._on_drive_select
        )
        self.drive_menu.pack(side="left")
        tk.Button(
            drive_frame, text="↻ Refresh",
            command=self._refresh_drives,
            bg="#21262d", fg="#c9d1d9",
            font=("Segoe UI", 10), relief="flat"
        ).pack(side="left", padx=8)

        mode_frame = tk.Frame(self, bg=BG)
        mode_frame.pack(pady=(12, 4))
        self.mode_buttons = {}

        primary_row = tk.Frame(mode_frame, bg=BG)
        primary_row.pack()
        secondary_row = tk.Frame(mode_frame, bg=BG)
        secondary_row.pack(pady=(8, 0))

        buttons_row1 = [
            (primary_row, "📀  Rip TV Show Disc", "t", "#238636", 20, lambda: self.start_task("t")),
            (primary_row, "🎬  Rip Movie Disc", "m", "#238636", 20, lambda: self.start_task("m")),
            (primary_row, "💾  Dump All Titles", "d", "#1f6feb", 18, lambda: self.start_task("d")),
        ]
        buttons_row2 = [
            (secondary_row, "📁  Organize Existing MKVs", "i", "#6e40c9", 22, lambda: self.start_task("i")),
            (
                secondary_row,
                "🧰  Prep MKVs For FFmpeg / HandBrake",
                "scan",
                "#9a6700",
                30,
                self._open_folder_scanner,
            ),
        ]

        for parent, text, mode, color, width, command in buttons_row1 + buttons_row2:
            btn = tk.Button(
                parent,
                text=text,
                command=command,
                bg=color, fg="white",
                font=("Segoe UI", 11),
                width=width, height=2, relief="flat"
            )
            btn.pack(side="left", padx=5)
            self.mode_buttons[mode] = btn

        util_frame = tk.Frame(self, bg=BG)
        util_frame.pack(fill="x", padx=20)
        tk.Button(
            util_frame, text="📂  Browse Folder",
            command=self._browse_folder_in_explorer,
            bg="#21262d", fg="#8b949e",
            font=("Segoe UI", 10), relief="flat"
        ).pack(side="right", padx=4)
        tk.Button(
            util_frame, text="📋  Copy Log",
            command=self.copy_log_to_clipboard,
            bg="#21262d", fg="#8b949e",
            font=("Segoe UI", 10), relief="flat"
        ).pack(side="right", padx=4)
        self.update_btn = tk.Button(
            util_frame, text="⬆  Check Updates",
            command=self.check_for_updates,
            bg="#21262d", fg="#8b949e",
            font=("Segoe UI", 10), relief="flat"
        )
        self.update_btn.pack(side="right", padx=4)
        self.settings_btn = tk.Button(
            util_frame, text="⚙  Settings",
            command=self._open_settings_safe,
            bg="#21262d", fg="#8b949e",
            font=("Segoe UI", 10), relief="flat"
        )
        self.settings_btn.pack(side="right", padx=4)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self, variable=self.progress_var,
            maximum=100, mode="determinate"
        )
        self.progress_bar.pack(fill="x", padx=20, pady=(8, 2))

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(
            self, textvariable=self.status_var,
            bg=BG, fg="#58a6ff",
            font=("Segoe UI", 10, "italic")
        ).pack(anchor="w", padx=22)

        tk.Label(
            self, text="Live Log",
            bg=BG, fg="#8b949e",
            font=("Segoe UI", 10)
        ).pack(anchor="w", padx=20)

        self.log_text = scrolledtext.ScrolledText(
            self, height=18, bg="#161b22", fg="#c9d1d9",
            font=("Consolas", 10), insertbackground="white",
            state="disabled"
        )
        self.log_text.pack(
            fill="both", expand=True, padx=20, pady=(0, 0)
        )
        self.log_text.tag_configure("prompt", foreground="#f0e68c")
        self.log_text.tag_configure("answer", foreground="#90ee90")

        self.input_bar = tk.Frame(self, bg="#21262d")
        self.input_bar.pack(fill="x", padx=20, pady=4)
        self.input_bar.pack_forget()

        self.input_label_var = tk.StringVar(value="")
        tk.Label(
            self.input_bar, textvariable=self.input_label_var,
            bg="#21262d", fg="#c9d1d9",
            font=("Segoe UI", 10), anchor="w"
        ).pack(side="left", padx=(10, 6), pady=8)

        self.input_var   = tk.StringVar()
        self.input_field = tk.Entry(
            self.input_bar, textvariable=self.input_var,
            bg="#0d1117", fg="#c9d1d9",
            font=("Segoe UI", 11),
            insertbackground="white",
            relief="flat", bd=4, width=40
        )
        self.input_field.pack(side="left", padx=4, pady=8)
        self.input_field.bind(
            "<Return>", lambda e: self._confirm_input()
        )

        tk.Button(
            self.input_bar, text="Confirm",
            bg="#238636", fg="white",
            font=("Segoe UI", 10, "bold"),
            command=self._confirm_input, relief="flat"
        ).pack(side="left", padx=4, pady=8)

        tk.Button(
            self.input_bar, text="Skip",
            bg="#30363d", fg="#8b949e",
            font=("Segoe UI", 10),
            command=self._skip_input, relief="flat"
        ).pack(side="left", padx=4, pady=8)

        # Keep abort visible when the inline prompt bar is open.
        self.abort_btn = tk.Button(
            self.input_bar, text="ABORT SESSION",
            bg="#c94b4b", fg="white",
            font=("Segoe UI", 12, "bold"),
            width=20, command=self.request_abort, relief="flat"
        )
        self.abort_btn.pack(side="right", padx=(10, 0), pady=8)

        # Keep bottom interaction controls clear of the Windows taskbar area
        # on machines where the app window can overlap shell-reserved space.
        safe_margin_px = int(self.cfg.get("opt_bottom_safe_margin_px", 72))
        self._bottom_safe_spacer = tk.Frame(self, bg=BG, height=safe_margin_px)
        self._bottom_safe_spacer.pack(fill="x")
        self._bottom_safe_spacer.pack_propagate(False)

        # Do not auto-probe optical drives on startup; probing can spin up
        # physical media drives and stall on some systems. Users can refresh
        # explicitly with the Refresh button.

    def _browse_folder_in_explorer(self):
        folder = self.ask_directory("Browse Folder", "Choose a folder to open")
        if not folder:
            return
        self._open_path_in_explorer(folder)

    def _open_folder_scanner(self):
        from tools.folder_scanner import scan_folder

        folder = self.ask_directory("Folder Scanner", "Choose a folder to scan")
        if not folder:
            self.show_info("Folder Scanner", "No folder selected.")
            return

        scan_options = self._ask_folder_scan_options()
        if scan_options is None:
            self.show_info("Folder Scanner", "Scan cancelled.")
            return

        main_log = self.cfg.get("log_file", "")
        log_dir = os.path.dirname(main_log) if main_log else os.path.expanduser("~")
        scan_log_path = os.path.join(log_dir, "folder_scan_log.txt")
        ffprobe_exe = None
        if str(scan_options.get("mode")) in {"duration_desc", "duration_asc"}:
            ffprobe_exe = resolve_ffprobe(
                os.path.normpath(self.cfg.get("ffprobe_path", ""))
            )[0] or None

        progress_win = tk.Toplevel(self)
        progress_win.title("Scanning MKVs...")
        progress_win.geometry("400x120")
        progress_win.configure(bg="#161b22")
        progress_win.grab_set()
        tk.Label(
            progress_win,
            text=f"Scanning: {folder}",
            bg="#161b22",
            fg="#58a6ff",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(18, 8))
        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(
            progress_win,
            variable=progress_var,
            maximum=100,
            mode="determinate",
        )
        progress_bar.pack(fill="x", padx=30, pady=(0, 12))
        status_var = tk.StringVar(value="Starting scan...")
        tk.Label(
            progress_win,
            textvariable=status_var,
            bg="#161b22",
            fg="#8b949e",
            font=("Segoe UI", 10, "italic"),
        ).pack()

        results = []

        def do_scan():
            nonlocal results
            import traceback

            try:
                def progress_cb(current, total):
                    def _update_progress() -> None:
                        pct = (current / total) * 100 if total else 0
                        progress_var.set(pct)
                        if total:
                            status_var.set(f"Scanning {current} of {total} items...")
                        else:
                            status_var.set(f"Scanning {current} item(s)...")

                    self.after(0, _update_progress)

                results = scan_folder(
                    folder,
                    mode=scan_options["mode"],
                    progress_cb=progress_cb,
                    log_path=scan_log_path,
                    recursive=bool(scan_options.get("recursive", True)),
                    include_dirs=False,
                    ffprobe_exe=ffprobe_exe,
                )
            except Exception as e:
                print("[ERROR] Exception in folder scan thread:", e)
                traceback.print_exc()
                results.append(e)
            self.after(0, on_done)

        def on_done():
            try:
                progress_win.destroy()
            except Exception as destroy_exc:
                print("[ERROR] Exception destroying progress_win:", destroy_exc)
            if results and isinstance(results[0], Exception):
                import traceback

                tb = traceback.format_exc()
                print(f"[ERROR] Folder Scanner error: {results[0]}\nTraceback:\n{tb}")
                self.show_error(
                    "Folder Scanner",
                    f"Error scanning folder:\n{results[0]}\n\nSee terminal for traceback.",
                )
                return
            try:
                self._show_folder_scan_results(folder, results, scan_options)
            except Exception as show_exc:
                print("[ERROR] Exception showing scan results:", show_exc)
                import traceback

                traceback.print_exc()
                self.show_error(
                    "Folder Scanner",
                    f"Error displaying scan results:\n{show_exc}\n\nSee terminal for traceback.",
                )

        threading.Thread(target=do_scan, daemon=True).start()

    def _ask_folder_scan_options(self):
        from tools.folder_scanner import SORT_MODE_LABELS

        win = tk.Toplevel(self)
        win.title("MKV Scanner — Sort Options")
        win.configure(bg="#161b22")
        win.grab_set()
        win.resizable(False, False)
        sort_var = tk.StringVar(value="size_desc")
        recursive_var = tk.BooleanVar(value=True)
        tk.Label(
            win,
            text="Scan MKV files for ffmpeg / HandBrake prep",
            bg="#161b22",
            fg="#58a6ff",
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=18, pady=(18, 6))
        tk.Label(
            win,
            text="Only .mkv files are shown. Subfolders are scanned by default.",
            bg="#161b22",
            fg="#8b949e",
            font=("Segoe UI", 10),
            wraplength=420,
            justify="left",
        ).pack(padx=18, pady=(0, 10), anchor="w")
        for mode, label in SORT_MODE_LABELS.items():
            tk.Radiobutton(
                win,
                text=label,
                variable=sort_var,
                value=mode,
                bg="#161b22",
                fg="#c9d1d9",
                selectcolor="#21262d",
                font=("Segoe UI", 11),
                anchor="w",
            ).pack(anchor="w", padx=24)
        tk.Checkbutton(
            win,
            text="Scan subfolders recursively",
            variable=recursive_var,
            bg="#161b22",
            fg="#c9d1d9",
            selectcolor="#21262d",
            activebackground="#161b22",
            activeforeground="#c9d1d9",
            font=("Segoe UI", 10),
        ).pack(anchor="w", padx=24, pady=(8, 0))
        btn_row = tk.Frame(win, bg="#161b22")
        btn_row.pack(pady=16)
        result = [None]

        def ok():
            result[0] = {
                "mode": sort_var.get(),
                "recursive": bool(recursive_var.get()),
            }
            win.destroy()

        def cancel():
            result[0] = None
            win.destroy()

        tk.Button(
            btn_row,
            text="Scan",
            command=ok,
            bg="#238636",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            width=10,
            relief="flat",
        ).pack(side="left", padx=8)
        tk.Button(
            btn_row,
            text="Cancel",
            command=cancel,
            bg="#30363d",
            fg="#8b949e",
            font=("Segoe UI", 10),
            width=10,
            relief="flat",
        ).pack(side="left", padx=8)
        win.wait_window()
        return result[0]

    def _show_folder_scan_results(self, folder, results, scan_options):
        from tools.folder_scanner import get_sort_mode_label

        BG = "#0d1117"
        win = tk.Toplevel(self)
        win.title(f"MKV Scanner Results — {os.path.basename(folder)}")
        win.configure(bg=BG)
        win.geometry("1100x650")
        win.grab_set()
        win.lift()
        win.focus_force()
        tk.Label(
            win,
            text=f"MKV Scan Results for:\n{folder}",
            bg=BG,
            fg="#58a6ff",
            font=("Segoe UI", 12, "bold"),
        ).pack(pady=(16, 4))
        mode_text = get_sort_mode_label(scan_options["mode"])
        recursive_text = (
            "Recursive"
            if scan_options.get("recursive", True)
            else "Current folder only"
        )
        tk.Label(
            win,
            text=f"Sort: {mode_text} | Scope: {recursive_text} | MKV files only",
            bg=BG,
            fg="#8b949e",
            font=("Segoe UI", 10, "italic"),
        ).pack(pady=(0, 10))
        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=16, pady=8)
        tree = ttk.Treeview(
            frame,
            columns=("name", "folder", "size", "duration", "modified", "status"),
            show="headings",
            style="Disc.Treeview",
            selectmode="extended",
        )
        tree.heading("name", text="Name")
        tree.heading("folder", text="Folder")
        tree.heading("size", text="Size")
        tree.heading("duration", text="Runtime")
        tree.heading("modified", text="Modified")
        tree.heading("status", text="Status")
        tree.column("name", width=280, anchor="w")
        tree.column("folder", width=320, anchor="w")
        tree.column("size", width=110, anchor="e")
        tree.column("duration", width=90, anchor="e")
        tree.column("modified", width=140, anchor="center")
        tree.column("status", width=110, anchor="center")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        entry_by_iid = {}
        for index, entry in enumerate(results):
            iid = f"scan_{index}"
            entry_by_iid[iid] = entry
            relative_folder = os.path.dirname(entry["relative_path"]) or "."
            tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    entry["name"],
                    relative_folder,
                    entry["size_str"],
                    entry["duration_str"],
                    entry["modified_str"],
                    entry["status"],
                ),
            )

        footer = tk.Frame(win, bg=BG)
        footer.pack(fill="x", padx=16, pady=(0, 12))
        status_var = tk.StringVar(
            value=(
                f"{len(results)} MKV file(s) found"
                if results else
                "No MKV files found"
            )
        )
        tk.Label(
            footer,
            textvariable=status_var,
            bg=BG,
            fg="#58a6ff",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        def _selected_entries():
            selected_iids = set(tree.selection())
            return [
                entry_by_iid[iid]
                for iid in tree.get_children("")
                if iid in selected_iids and iid in entry_by_iid
            ]

        def _selected_paths():
            return [entry["path"] for entry in _selected_entries()]

        def _reveal_selected(_event=None):
            selected_paths = _selected_paths()
            if not selected_paths:
                status_var.set("Select at least one MKV file first.")
                return
            self._reveal_path_in_explorer(selected_paths[0])
            status_var.set(f"Revealed: {os.path.basename(selected_paths[0])}")

        def _copy_selected():
            selected_paths = _selected_paths()
            if not selected_paths:
                status_var.set("Select at least one MKV file first.")
                return
            self.clipboard_clear()
            self.clipboard_append("\n".join(selected_paths))
            status_var.set(f"Copied {len(selected_paths)} path(s) to the clipboard.")

        def _select_all(_event=None):
            children = tree.get_children("")
            if not children:
                status_var.set("No MKV files are available to select.")
                return "break"
            tree.selection_set(children)
            status_var.set(f"Selected {len(children)} MKV file(s).")
            return "break"

        def _queue_selected():
            selected_entries = _selected_entries()
            if not selected_entries:
                status_var.set("Select at least one MKV file first.")
                return
            self._open_transcode_queue_builder(
                folder,
                [entry["path"] for entry in selected_entries],
                selected_entries=selected_entries,
            )

        def _recommend_selected():
            selected_paths = _selected_paths()
            if not selected_paths:
                status_var.set("Select one MKV file first.")
                return
            if len(selected_paths) != 1:
                status_var.set("Select exactly one MKV file for recommendations.")
                return
            self._open_ffmpeg_recommendation_scan(folder, selected_paths[0])

        tree.bind("<Double-1>", _reveal_selected)
        tree.bind("<Control-a>", _select_all)
        tree.bind("<Control-A>", _select_all)
        tree.focus_set()

        button_row = tk.Frame(win, bg=BG)
        button_row.pack(fill="x", padx=16, pady=(0, 12))
        tk.Button(
            button_row,
            text="Copy Selected Paths",
            command=_copy_selected,
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left", padx=4)
        tk.Button(
            button_row,
            text="Build Queue",
            command=_queue_selected,
            bg="#1f6feb",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        ).pack(side="left", padx=4)
        tk.Button(
            button_row,
            text="Recommend For Selected",
            command=_recommend_selected,
            bg="#9a6700",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        ).pack(side="left", padx=4)
        tk.Button(
            button_row,
            text="Reveal Selected",
            command=_reveal_selected,
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left", padx=4)
        tk.Button(
            button_row,
            text="Close",
            command=win.destroy,
            bg="#21262d",
            fg="#8b949e",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="right", padx=4)

    def _open_ffmpeg_recommendation_scan(self, scan_root, input_path):
        ffprobe_exe = resolve_ffprobe(
            os.path.normpath(self.cfg.get("ffprobe_path", ""))
        )[0] or ""
        if not ffprobe_exe or not os.path.isfile(ffprobe_exe):
            self.show_error(
                "FFmpeg Recommendation",
                "ffprobe is required for recommendations and was not found.\n\n"
                "Open Settings > Paths and confirm the ffmpeg / ffprobe folder.",
            )
            return

        progress_win = tk.Toplevel(self)
        progress_win.title("Analyzing MKV...")
        progress_win.geometry("420x130")
        progress_win.configure(bg="#161b22")
        progress_win.grab_set()
        tk.Label(
            progress_win,
            text=f"Analyzing:\n{os.path.basename(input_path)}",
            bg="#161b22",
            fg="#58a6ff",
            font=("Segoe UI", 11, "bold"),
        ).pack(pady=(18, 8))
        tk.Label(
            progress_win,
            text="Running a second pass with ffprobe to recommend safer FFmpeg settings.",
            bg="#161b22",
            fg="#8b949e",
            font=("Segoe UI", 10),
            wraplength=360,
            justify="center",
        ).pack(pady=(0, 12))
        status_var = tk.StringVar(value="Starting analysis...")
        tk.Label(
            progress_win,
            textvariable=status_var,
            bg="#161b22",
            fg="#c9d1d9",
            font=("Segoe UI", 10, "italic"),
        ).pack()

        result_holder = {
            "analysis": None,
            "recommendation_result": None,
            "error": None,
        }

        def _worker():
            try:
                result_holder["analysis"] = probe_media_for_recommendation(
                    input_path,
                    ffprobe_exe,
                )
                result_holder["recommendation_result"] = build_ffmpeg_recommendations(
                    result_holder["analysis"]
                )
            except Exception as exc:
                result_holder["error"] = exc
            self.after(0, _on_done)

        def _on_done():
            try:
                progress_win.destroy()
            except Exception:
                pass

            error = result_holder["error"]
            if error is not None:
                self.show_error(
                    "FFmpeg Recommendation",
                    f"Could not analyze the selected MKV:\n{error}",
                )
                return

            self._show_ffmpeg_recommendations(
                scan_root,
                result_holder["analysis"],
                result_holder["recommendation_result"],
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _start_ffmpeg_recommendation_queue(
        self,
        scan_root,
        analysis,
        recommendation,
        output_root,
    ):
        ffmpeg_exe, ffmpeg_status = self._resolve_transcode_backend_path("ffmpeg")
        if not ffmpeg_exe:
            self.show_error(
                "FFmpeg Recommendation",
                f"{ffmpeg_status}\n\nSet the FFmpeg executable in Settings > Paths.",
            )
            return False

        if not output_root:
            self.show_error(
                "FFmpeg Recommendation",
                "Choose an output folder before queuing the recommendation.",
            )
            return False

        try:
            os.makedirs(output_root, exist_ok=True)
        except Exception as exc:
            self.show_error(
                "FFmpeg Recommendation",
                f"Could not create the output folder:\n{exc}",
            )
            return False

        plans = _build_transcode_plan(scan_root, [analysis["path"]], output_root)
        if not plans:
            self.show_error(
                "FFmpeg Recommendation",
                "The selected file could not be added to the queue.",
            )
            return False

        ffmpeg_source_mode = normalize_ffmpeg_source_mode(
            self.cfg.get("opt_ffmpeg_source_mode", FFMPEG_SOURCE_MODE_SAFE_COPY)
        )
        build_result = build_recommendation_job(
            plan=plans[0],
            analysis=analysis,
            recommendation=recommendation,
            ffmpeg_source_mode=ffmpeg_source_mode,
        )

        log_dir = os.path.join(get_config_dir(), "transcode_logs")
        transcode_queue = build_transcode_queue(
            jobs=build_result.jobs,
            log_dir=log_dir,
            ffmpeg_exe=ffmpeg_exe,
            ffprobe_exe=resolve_ffprobe(
                os.path.normpath(self.cfg.get("ffprobe_path", ""))
            )[0],
            handbrake_exe=self._resolve_transcode_backend_path("handbrake")[0],
            ffmpeg_source_mode=ffmpeg_source_mode,
            temp_root=os.path.normpath(
                self.cfg.get("temp_folder", DEFAULTS["temp_folder"])
            ),
        )
        self.controller.log(
            f"FFmpeg recommendation queued for {analysis['name']}: "
            f"{recommendation['label']} (CRF {recommendation['crf']}, preset {recommendation['preset']}, "
            f"source {_ffmpeg_source_mode_label(ffmpeg_source_mode)})"
        )
        self._run_transcode_queue(
            transcode_queue,
            "FFmpeg",
            os.path.normpath(output_root),
            queue_detail=build_result.queue_detail,
        )
        return True

    def _show_ffmpeg_recommendations(self, scan_root, analysis, recommendation_result):
        BG = "#0d1117"
        win = tk.Toplevel(self)
        win.title(f"FFmpeg Recommendation - {analysis['name']}")
        win.configure(bg=BG)
        win.geometry("960x700")
        win.grab_set()
        win.lift()
        win.focus_force()

        tk.Label(
            win,
            text=f"FFmpeg recommendations for {analysis['name']}",
            bg=BG,
            fg="#58a6ff",
            font=("Segoe UI", 13, "bold"),
        ).pack(padx=18, pady=(18, 6), anchor="w")
        tk.Label(
            win,
            text=(
                "This second pass looks at the actual file and gives you three safer starting points "
                "for making it smaller with FFmpeg."
            ),
            bg=BG,
            fg="#8b949e",
            font=("Segoe UI", 10),
            wraplength=900,
            justify="left",
        ).pack(padx=18, pady=(0, 12), anchor="w")

        summary_frame = tk.Frame(win, bg="#161b22")
        summary_frame.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(
            summary_frame,
            text="File summary",
            bg="#161b22",
            fg="#58a6ff",
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 4))
        for line in format_analysis_summary(analysis):
            tk.Label(
                summary_frame,
                text=line,
                bg="#161b22",
                fg="#c9d1d9",
                font=("Segoe UI", 10),
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=12)

        recommended_id = recommendation_result["recommended_id"]
        selected_var = tk.StringVar(value=recommended_id)
        recommendation_map = {
            rec["id"]: rec
            for rec in recommendation_result["recommendations"]
        }
        status_var = tk.StringVar(
            value=f"We recommend {recommendation_map[recommended_id]['label']}. "
            f"{recommendation_result['recommendation_reason']}"
        )

        if recommendation_result["advisory"]:
            advisory_frame = tk.Frame(win, bg="#2d1f04")
            advisory_frame.pack(fill="x", padx=18, pady=(0, 10))
            tk.Label(
                advisory_frame,
                text=recommendation_result["advisory"],
                bg="#2d1f04",
                fg="#ffd866",
                font=("Segoe UI", 10, "bold"),
                wraplength=900,
                justify="left",
            ).pack(fill="x", padx=12, pady=10)

        tk.Label(
            win,
            textvariable=status_var,
            bg=BG,
            fg="#58a6ff",
            font=("Segoe UI", 10, "bold"),
            wraplength=900,
            justify="left",
        ).pack(padx=18, pady=(0, 10), anchor="w")

        options_frame = tk.Frame(win, bg=BG)
        options_frame.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        for recommendation in recommendation_result["recommendations"]:
            is_recommended = recommendation["id"] == recommended_id
            card = tk.Frame(
                options_frame,
                bg="#161b22" if is_recommended else "#0f141a",
                highlightthickness=1,
                highlightbackground="#58a6ff" if is_recommended else "#30363d",
            )
            card.pack(fill="x", pady=6)
            tk.Radiobutton(
                card,
                text=(
                    f"{recommendation['label']}"
                    f"{' (Recommended)' if is_recommended else ''}"
                ),
                variable=selected_var,
                value=recommendation["id"],
                bg=card.cget("bg"),
                fg="#c9d1d9",
                selectcolor="#21262d",
                activebackground=card.cget("bg"),
                activeforeground="#c9d1d9",
                font=("Segoe UI", 11, "bold"),
                anchor="w",
                command=lambda rec=recommendation: status_var.set(
                    f"{rec['label']}: {rec['why']}"
                ),
            ).pack(anchor="w", padx=12, pady=(10, 2))
            tk.Label(
                card,
                text=recommendation["summary"],
                bg=card.cget("bg"),
                fg="#58a6ff",
                font=("Segoe UI", 10, "bold"),
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=34)
            tk.Label(
                card,
                text=recommendation["details"],
                bg=card.cget("bg"),
                fg="#c9d1d9",
                font=("Segoe UI", 10),
                anchor="w",
                justify="left",
                wraplength=860,
            ).pack(fill="x", padx=34, pady=(2, 2))
            tk.Label(
                card,
                text=recommendation["why"],
                bg=card.cget("bg"),
                fg="#8b949e",
                font=("Segoe UI", 10, "italic"),
                anchor="w",
                justify="left",
                wraplength=860,
            ).pack(fill="x", padx=34, pady=(0, 10))

        output_root_var = tk.StringVar(
            value=_suggest_transcode_output_root(scan_root, "ffmpeg")
        )
        output_row = tk.Frame(win, bg=BG)
        output_row.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(
            output_row,
            text="Output root:",
            bg=BG,
            fg="#c9d1d9",
            font=("Segoe UI", 10, "bold"),
            width=12,
            anchor="w",
        ).pack(side="left")
        tk.Entry(
            output_row,
            textvariable=output_root_var,
            bg="#161b22",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
            bd=3,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        def _browse_output_root():
            current_output = output_root_var.get().strip()
            initial_dir = current_output or os.path.dirname(scan_root) or scan_root
            chosen = self.ask_directory(
                "FFmpeg Recommendation",
                "Choose an output folder",
                initialdir=initial_dir,
            )
            if chosen:
                output_root_var.set(os.path.normpath(chosen))

        tk.Button(
            output_row,
            text="Browse",
            command=_browse_output_root,
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left")

        button_row = tk.Frame(win, bg=BG)
        button_row.pack(fill="x", padx=18, pady=(0, 18))

        def _queue_recommendation():
            selected_recommendation = recommendation_map.get(selected_var.get())
            if not selected_recommendation:
                self.show_error(
                    "FFmpeg Recommendation",
                    "Choose a recommendation first.",
                )
                return
            if self._start_ffmpeg_recommendation_queue(
                scan_root,
                analysis,
                selected_recommendation,
                output_root_var.get().strip(),
            ):
                win.destroy()

        tk.Button(
            button_row,
            text="Queue Chosen Recommendation",
            command=_queue_recommendation,
            bg="#238636",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            button_row,
            text="Open Regular Queue",
            command=lambda: self._open_transcode_queue_builder(
                scan_root,
                [analysis["path"]],
                backend="ffmpeg",
            ),
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left")
        tk.Button(
            button_row,
            text="Close",
            command=win.destroy,
            bg="#21262d",
            fg="#8b949e",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="right")

    def _resolve_transcode_backend_path(self, backend):
        backend_key = str(backend or "").strip().lower()
        if backend_key == "handbrake":
            cfg_key = "handbrake_path"
            auto_locator = auto_locate_handbrake
            validator = validate_handbrake
        else:
            backend_key = "ffmpeg"
            cfg_key = "ffmpeg_path"
            auto_locator = auto_locate_ffmpeg
            validator = validate_ffmpeg

        backend_label = _transcode_backend_label(backend_key)
        configured_path = str(self.cfg.get(cfg_key, "") or "").strip()
        if configured_path:
            configured_path = os.path.normpath(configured_path)
            ok, reason = validator(configured_path)
            if ok:
                return configured_path, f"Using configured {backend_label}: {configured_path}"

            auto_path = auto_locator()
            if auto_path:
                auto_path = os.path.normpath(auto_path)
                auto_ok, _auto_reason = validator(auto_path)
                if auto_ok:
                    reason_text = reason or "validation failed"
                    return (
                        auto_path,
                        f"Configured {backend_label} path failed ({reason_text}). "
                        f"Using auto-detected {backend_label}: {auto_path}",
                    )

            reason_text = reason or "validation failed"
            return "", f"{backend_label} is not ready: {reason_text}"

        auto_path = auto_locator()
        if auto_path:
            auto_path = os.path.normpath(auto_path)
            ok, reason = validator(auto_path)
            if ok:
                return auto_path, f"Using auto-detected {backend_label}: {auto_path}"
            if reason:
                return "", f"Auto-detected {backend_label} failed validation: {reason}"

        return "", f"{backend_label} executable not found. Set it in Settings > Paths."

    def _get_transcode_profile_loader(self):
        profile_path = os.path.join(get_config_dir(), TRANSCODE_PROFILE_FILENAME)
        return ProfileLoader(profile_path)

    def _open_transcode_queue_builder(
        self,
        scan_root,
        selected_paths,
        backend="ffmpeg",
        selected_entries=None,
    ):
        backend_key = str(backend or "").strip().lower()
        if backend_key not in {"ffmpeg", "handbrake"}:
            backend_key = "ffmpeg"

        normalized_paths = [
            os.path.normpath(path)
            for path in selected_paths
            if str(path or "").strip()
        ]
        if not normalized_paths:
            self.show_info(
                "Build Queue",
                "Select at least one MKV file before building a queue.",
            )
            return

        try:
            profile_loader = self._get_transcode_profile_loader()
        except Exception as exc:
            self.show_error(
                "Build Queue",
                f"Could not load transcode profiles:\n{exc}",
            )
            return

        backend_choices = {
            "FFmpeg": "ffmpeg",
            "HandBrake": "handbrake",
        }
        backend_key_to_label = {value: key for key, value in backend_choices.items()}
        backend_var = tk.StringVar(
            value=backend_key_to_label.get(backend_key, "FFmpeg")
        )
        output_root_var = tk.StringVar(
            value=_suggest_transcode_output_root(scan_root, backend_key)
        )
        executable_var = tk.StringVar()
        option_label_var = tk.StringVar()
        option_var = tk.StringVar()
        source_mode_help_var = tk.StringVar()
        start_button_var = tk.StringVar()
        status_var = tk.StringVar(
            value=f"Ready to queue {len(normalized_paths)} MKV file(s)."
        )
        suggested_output_state = {"value": output_root_var.get()}

        profile_names = list(profile_loader.profiles)
        default_profile_name = profile_loader.default or (
            profile_names[0] if profile_names else ""
        )

        win = tk.Toplevel(self)
        win.title("Transcode Queue Builder")
        win.configure(bg="#0d1117")
        win.geometry("980x620")
        win.grab_set()
        win.lift()
        win.focus_force()

        tk.Label(
            win,
            text=f"Queue {len(normalized_paths)} MKV file(s) for FFmpeg or HandBrake",
            bg="#0d1117",
            fg="#58a6ff",
            font=("Segoe UI", 13, "bold"),
        ).pack(padx=18, pady=(18, 6), anchor="w")
        tk.Label(
            win,
            text="Choose a backend, review the output layout, and keep the selected MKVs organized before sending them to the encoder.",
            bg="#0d1117",
            fg="#8b949e",
            font=("Segoe UI", 10),
            wraplength=920,
            justify="left",
        ).pack(padx=18, pady=(0, 10), anchor="w")

        backend_row = tk.Frame(win, bg="#0d1117")
        backend_row.pack(fill="x", padx=18, pady=(0, 8))
        tk.Label(
            backend_row,
            text="Backend:",
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Segoe UI", 10, "bold"),
            width=14,
            anchor="w",
        ).pack(side="left")
        ttk.Combobox(
            backend_row,
            textvariable=backend_var,
            values=list(backend_choices),
            state="readonly",
            width=20,
        ).pack(side="left", padx=(0, 8))

        executable_row = tk.Frame(win, bg="#0d1117")
        executable_row.pack(fill="x", padx=18, pady=(0, 8))
        tk.Label(
            executable_row,
            text="Executable:",
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Segoe UI", 10, "bold"),
            width=14,
            anchor="w",
        ).pack(side="left")
        tk.Label(
            executable_row,
            textvariable=executable_var,
            bg="#0d1117",
            fg="#8b949e",
            font=("Segoe UI", 10),
            wraplength=760,
            justify="left",
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        output_row = tk.Frame(win, bg="#0d1117")
        output_row.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(
            output_row,
            text="Output root:",
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Segoe UI", 10, "bold"),
            width=14,
            anchor="w",
        ).pack(side="left")
        tk.Entry(
            output_row,
            textvariable=output_root_var,
            bg="#161b22",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
            bd=3,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        def _selected_backend_key():
            return backend_choices.get(backend_var.get(), "ffmpeg")

        def _browse_output_root():
            current_output = output_root_var.get().strip()
            initial_dir = current_output or os.path.dirname(scan_root) or scan_root
            chosen = self.ask_directory(
                "Build Queue",
                "Choose an output folder",
                initialdir=initial_dir,
            )
            if chosen:
                output_root_var.set(os.path.normpath(chosen))

        def _reveal_output_root():
            current_output = output_root_var.get().strip()
            if not current_output:
                status_var.set("Choose an output folder first.")
                return
            normalized_output = os.path.normpath(current_output)
            if not os.path.isdir(normalized_output):
                status_var.set("Output folder will be created when the queue starts.")
                return
            self._open_path_in_explorer(normalized_output)

        tk.Button(
            output_row,
            text="Browse",
            command=_browse_output_root,
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            output_row,
            text="Reveal",
            command=_reveal_output_root,
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left")

        option_row = tk.Frame(win, bg="#0d1117")
        option_row.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(
            option_row,
            textvariable=option_label_var,
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Segoe UI", 10, "bold"),
            width=14,
            anchor="w",
        ).pack(side="left")
        option_menu = ttk.Combobox(
            option_row,
            textvariable=option_var,
            state="readonly",
            width=36,
        )
        option_menu.pack(side="left", padx=(0, 8))
        tk.Label(
            win,
            textvariable=source_mode_help_var,
            bg="#0d1117",
            fg="#8b949e",
            font=("Segoe UI", 9),
            wraplength=920,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=18, pady=(0, 10))

        tk.Label(
            win,
            text="Queue preview",
            bg="#0d1117",
            fg="#58a6ff",
            font=("Segoe UI", 11, "bold"),
        ).pack(padx=18, pady=(4, 4), anchor="w")

        preview_frame = tk.Frame(win, bg="#0d1117")
        preview_frame.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        preview_tree = ttk.Treeview(
            preview_frame,
            columns=("source", "output"),
            show="headings",
            style="Disc.Treeview",
        )
        preview_tree.heading("source", text="Source (relative)")
        preview_tree.heading("output", text="Output (relative)")
        preview_tree.column("source", width=360, anchor="w")
        preview_tree.column("output", width=520, anchor="w")
        preview_scroll = ttk.Scrollbar(
            preview_frame, orient="vertical", command=preview_tree.yview
        )
        preview_tree.configure(yscrollcommand=preview_scroll.set)
        preview_tree.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")

        def _refresh_preview(*_args):
            current_output = output_root_var.get().strip()
            plans = _build_transcode_plan(scan_root, normalized_paths, current_output)
            preview_tree.delete(*preview_tree.get_children(""))
            for idx, plan in enumerate(plans):
                preview_tree.insert(
                    "",
                    "end",
                    iid=f"plan_{idx}",
                    values=(
                        plan["relative_path"],
                        plan["output_relative_path"],
                    ),
                )
            if plans:
                status_var.set(
                    f"Queue preview ready: {len(plans)} MKV file(s) preserving subfolders."
                )
            else:
                status_var.set("Choose an output folder to build the queue preview.")

        def _refresh_backend_state(*_args):
            current_backend = _selected_backend_key()
            backend_label = _transcode_backend_label(current_backend)
            suggested_output = _suggest_transcode_output_root(scan_root, current_backend)
            current_output = output_root_var.get().strip()
            previous_suggested = suggested_output_state["value"]
            if (
                not current_output or
                os.path.normcase(os.path.normpath(current_output)) ==
                os.path.normcase(os.path.normpath(previous_suggested))
            ):
                output_root_var.set(suggested_output)
            suggested_output_state["value"] = suggested_output

            _chosen_executable, executable_status = self._resolve_transcode_backend_path(
                current_backend
            )
            executable_var.set(executable_status)

            if current_backend == "ffmpeg":
                option_label_var.set("FFmpeg profile:")
                option_menu.configure(values=profile_names)
                selected_value = option_var.get().strip()
                if selected_value not in profile_names:
                    option_var.set(default_profile_name)
                current_source_mode = normalize_ffmpeg_source_mode(
                    self.cfg.get("opt_ffmpeg_source_mode", FFMPEG_SOURCE_MODE_SAFE_COPY)
                )
                source_mode_help_var.set(
                    f"FFmpeg source handling: {_ffmpeg_source_mode_label(current_source_mode)}. "
                    f"{describe_ffmpeg_source_mode(current_source_mode)} "
                    "Change this in Settings > Advanced."
                )
            else:
                option_label_var.set("HandBrake preset:")
                option_menu.configure(values=HANDBRAKE_PRESETS)
                selected_value = option_var.get().strip()
                if selected_value not in HANDBRAKE_PRESETS:
                    option_var.set(HANDBRAKE_PRESETS[0])
                source_mode_help_var.set(
                    "HandBrake reads the selected source file directly and writes a separate output file."
                )

            start_button_var.set(f"Start {backend_label} Queue")

        output_root_var.trace_add("write", _refresh_preview)
        backend_var.trace_add("write", _refresh_backend_state)
        _refresh_backend_state()
        _refresh_preview()

        footer = tk.Frame(win, bg="#0d1117")
        footer.pack(fill="x", padx=18, pady=(0, 10))
        tk.Label(
            footer,
            textvariable=status_var,
            bg="#0d1117",
            fg="#58a6ff",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        button_row = tk.Frame(win, bg="#0d1117")
        button_row.pack(fill="x", padx=18, pady=(0, 18))

        def _start_queue():
            current_backend = _selected_backend_key()
            backend_label = _transcode_backend_label(current_backend)
            output_root = output_root_var.get().strip()
            if not output_root:
                status_var.set("Choose an output folder first.")
                return
            if os.path.isfile(output_root):
                status_var.set("The output root points to a file. Choose a folder instead.")
                return

            chosen_executable, chosen_status = self._resolve_transcode_backend_path(
                current_backend
            )
            executable_var.set(chosen_status)
            if not chosen_executable:
                self.show_error(
                    "Build Queue",
                    f"{chosen_status}\n\nSet the executable in Settings > Paths.",
                )
                return

            plans = _build_transcode_plan(scan_root, normalized_paths, output_root)
            if not plans:
                status_var.set("Nothing to queue. Select at least one MKV file.")
                return

            try:
                os.makedirs(output_root, exist_ok=True)
            except Exception as exc:
                self.show_error(
                    "Build Queue",
                    f"Could not create the output folder:\n{exc}",
                )
                return

            ffmpeg_source_mode = normalize_ffmpeg_source_mode(
                self.cfg.get("opt_ffmpeg_source_mode", FFMPEG_SOURCE_MODE_SAFE_COPY)
            )

            try:
                build_result = build_queue_jobs(
                    plans=plans,
                    profile_loader=profile_loader,
                    backend=current_backend,
                    option_value=option_var.get().strip(),
                    ffmpeg_source_mode=ffmpeg_source_mode,
                    selected_entries=selected_entries,
                    default_handbrake_preset=HANDBRAKE_PRESETS[0],
                )
            except Exception as exc:
                self.show_error(
                    "Build Queue",
                    f"Could not build the queue:\n{exc}",
                )
                return

            jobs = build_result.jobs
            if not jobs:
                status_var.set("No transcode jobs were added to the queue.")
                return

            try:
                for directory in required_output_directories(jobs, output_root):
                    os.makedirs(directory, exist_ok=True)
            except Exception as exc:
                self.show_error(
                    "Build Queue",
                    f"Could not prepare the output folders:\n{exc}",
                )
                return

            log_dir = os.path.join(get_config_dir(), "transcode_logs")
            ffmpeg_path = (
                chosen_executable if current_backend == "ffmpeg"
                else self._resolve_transcode_backend_path("ffmpeg")[0]
            )
            handbrake_path = (
                chosen_executable if current_backend == "handbrake"
                else self._resolve_transcode_backend_path("handbrake")[0]
            )
            transcode_queue = build_transcode_queue(
                jobs=jobs,
                log_dir=log_dir,
                ffmpeg_exe=ffmpeg_path,
                ffprobe_exe=resolve_ffprobe(
                    os.path.normpath(self.cfg.get("ffprobe_path", ""))
                )[0],
                handbrake_exe=handbrake_path,
                ffmpeg_source_mode=ffmpeg_source_mode,
                temp_root=os.path.normpath(
                    self.cfg.get("temp_folder", DEFAULTS["temp_folder"])
                ),
            )

            self.controller.log(
                f"{backend_label} queue created with {len(jobs)} job(s). "
                f"Output root: {os.path.normpath(output_root)}. {build_result.queue_detail}"
            )
            win.destroy()
            self._run_transcode_queue(
                transcode_queue,
                backend_label,
                os.path.normpath(output_root),
                queue_detail=build_result.queue_detail,
            )

        tk.Button(
            button_row,
            textvariable=start_button_var,
            command=_start_queue,
            bg="#238636",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            button_row,
            text="Reveal Output Root",
            command=_reveal_output_root,
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left")
        tk.Button(
            button_row,
            text="Cancel",
            command=win.destroy,
            bg="#21262d",
            fg="#8b949e",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="right")

    def _run_transcode_queue(
        self,
        transcode_queue,
        backend_label,
        output_root,
        queue_detail="",
    ):
        total_jobs = len(transcode_queue.jobs)
        if total_jobs <= 0:
            self.show_info(
                f"{backend_label} Queue",
                "No jobs were available to run.",
            )
            return

        BG = "#0d1117"
        win = tk.Toplevel(self)
        win.title(f"{backend_label} Queue Progress")
        win.configure(bg=BG)
        win.geometry("760x460")
        win.lift()
        win.focus_force()

        tk.Label(
            win,
            text=f"{backend_label} queue is running",
            bg=BG,
            fg="#58a6ff",
            font=("Segoe UI", 12, "bold"),
        ).pack(padx=18, pady=(18, 6), anchor="w")
        tk.Label(
            win,
            text=f"Output root: {output_root}",
            bg=BG,
            fg="#8b949e",
            font=("Segoe UI", 10),
            wraplength=700,
            justify="left",
        ).pack(padx=18, pady=(0, 2), anchor="w")
        if queue_detail:
            tk.Label(
                win,
                text=queue_detail,
                bg=BG,
                fg="#8b949e",
                font=("Segoe UI", 10),
            ).pack(padx=18, pady=(0, 8), anchor="w")

        progress_var = tk.DoubleVar(value=0)
        progress_bar = ttk.Progressbar(
            win,
            variable=progress_var,
            maximum=100,
            mode="determinate",
        )
        progress_bar.pack(fill="x", padx=18, pady=(0, 8))

        status_var = tk.StringVar(
            value=f"Queued {total_jobs} job(s). Processing will continue in the background thread."
        )
        tk.Label(
            win,
            textvariable=status_var,
            bg=BG,
            fg="#58a6ff",
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=18, pady=(0, 8), anchor="w")

        log_text = scrolledtext.ScrolledText(
            win,
            bg="#161b22",
            fg="#c9d1d9",
            insertbackground="white",
            font=("Consolas", 10),
            relief="flat",
            height=16,
            state="disabled",
        )
        log_text.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        def _append_log_line(message):
            try:
                if not win.winfo_exists():
                    return
                log_text.config(state="normal")
                log_text.insert("end", f"{message}\n")
                log_text.see("end")
            except tk.TclError:
                return
            finally:
                try:
                    log_text.config(state="disabled")
                except tk.TclError:
                    return

        _append_log_line(f"Output root: {output_root}")
        _append_log_line(f"Log folder: {transcode_queue.engine.log_dir}")
        if queue_detail:
            _append_log_line(queue_detail)

        button_row = tk.Frame(win, bg=BG)
        button_row.pack(fill="x", padx=18, pady=(0, 18))
        tk.Button(
            button_row,
            text="Open Output Folder",
            command=lambda: self._open_path_in_explorer(output_root),
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            button_row,
            text="Open Log Folder",
            command=lambda: self._open_path_in_explorer(transcode_queue.engine.log_dir),
            bg="#21262d",
            fg="#c9d1d9",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="left")
        tk.Button(
            button_row,
            text="Close",
            command=win.destroy,
            bg="#21262d",
            fg="#8b949e",
            font=("Segoe UI", 10),
            relief="flat",
        ).pack(side="right")

        def _feedback(message):
            self.controller.log(f"[{backend_label}] {message}")

            def _update_ui():
                try:
                    if not win.winfo_exists():
                        return
                    status_var.set(message)
                    _append_log_line(message)
                except tk.TclError:
                    return

            self.after(0, _update_ui)

        def _progress(event):
            if not isinstance(event, dict):
                return

            overall_percent = event.get("overall_percent")
            message = str(event.get("message", "") or "").strip()

            def _update_ui():
                try:
                    if not win.winfo_exists():
                        return
                    if isinstance(overall_percent, (int, float)):
                        progress_var.set(
                            max(0.0, min(100.0, float(overall_percent)))
                        )
                    if message:
                        status_var.set(message)
                except tk.TclError:
                    return

            self.after(0, _update_ui)

        def _mark_progress():
            finished = len(transcode_queue.completed) + len(transcode_queue.failed)
            pct = (finished / total_jobs) * 100 if total_jobs else 0
            summary = (
                f"{backend_label} progress: {finished}/{total_jobs} complete "
                f"(success: {len(transcode_queue.completed)}, failed: {len(transcode_queue.failed)})"
            )
            try:
                if not win.winfo_exists():
                    return
                progress_var.set(pct)
                status_var.set(summary)
                _append_log_line(summary)
            except tk.TclError:
                return

        def _finish(message):
            try:
                if not win.winfo_exists():
                    return
                progress_var.set(100)
                status_var.set(message)
                _append_log_line(message)
            except tk.TclError:
                return

        def _worker():
            try:
                while transcode_queue.jobs:
                    transcode_queue.run_next(
                        feedback_cb=_feedback,
                        progress_cb=_progress,
                    )
                    self.after(0, _mark_progress)
            except Exception as exc:
                error_message = f"{backend_label} queue stopped with an unexpected error: {exc}"
                self.controller.log(error_message)
                self.after(0, lambda: _finish(error_message))
                return

            summary = (
                f"{backend_label} queue complete. Success: {len(transcode_queue.completed)}, "
                f"Failed: {len(transcode_queue.failed)}"
            )
            self.controller.log(summary)
            self.after(0, lambda: _finish(summary))

        threading.Thread(target=_worker, daemon=True).start()

    def _refresh_drives(self):
        def _load():
            makemkvcon = os.path.normpath(
                self.cfg.get("makemkvcon_path", "")
            )
            drives = get_available_drives(makemkvcon)
            self.after(0, lambda: self._update_drive_menu(drives))
        threading.Thread(target=_load, daemon=True).start()

    def _update_drive_menu(self, drives):
        self.drive_options = drives
        labels = [f"Drive {idx}: {name}" for idx, name in drives]
        self.drive_menu["values"] = labels
        current_idx = self.cfg.get("opt_drive_index", 0)
        for i, (idx, name) in enumerate(drives):
            if idx == current_idx:
                self.drive_var.set(labels[i])
                break
        else:
            if labels:
                self.drive_var.set(labels[0])

    def _on_drive_select(self, *args):
        selected = self.drive_var.get()
        for idx, name in self.drive_options:
            if f"Drive {idx}: {name}" == selected:
                self.cfg["opt_drive_index"] = idx
                self.engine.cfg["opt_drive_index"] = idx
                save_config(self.cfg)
                self.controller.log(f"Drive selected: {name}")
                break

    def copy_log_to_clipboard(self):
        try:
            content = self.log_text.get("1.0", "end-1c")
            if not content.strip():
                self.controller.log("Log is empty — nothing to copy.")
                return
            self.clipboard_clear()
            self.clipboard_append(content)
            # Ensure clipboard ownership is committed on Windows.
            self.update_idletasks()
            self.controller.log("Log copied to clipboard.")
        except Exception as e:
            self.controller.log(f"Could not copy log: {e}")

    def _launch_downloaded_update(self, downloaded_path):
        """Delegate to update_ui.launch_downloaded_update."""
        launch_downloaded_update(self, downloaded_path)

    def check_for_updates(self):
        """Delegate to update_ui.check_for_updates."""
        check_for_updates(self)

    def _show_input_bar(self, label, initial_value=""):
        self.input_label_var.set(label)
        self.input_var.set(initial_value or "")
        self._input_active = True
        self.input_bar.pack(fill="x", padx=20, pady=4)
        if initial_value:
            self.input_field.selection_range(0, "end")
        self.input_field.focus_set()

    def _hide_input_bar(self):
        self._input_active = False
        self.input_bar.pack_forget()
        self.input_var.set("")

    def _confirm_input(self):
        if not self._input_active:
            return
        val = self.input_var.get().strip()
        self._input_result = val
        self._input_event.set()

    def _skip_input(self):
        if not self._input_active:
            return
        self._input_result = ""
        self._input_event.set()

    def ask_input(self, label, prompt,
                  default_value=""):
        """Show non-modal input bar and wait from caller thread for user input.

        Serialised by _input_lock — only one prompt can be active at a time,
        preventing concurrent calls from clobbering _input_result/_input_event.
        """
        with self._input_lock:
            result = [None]
            done   = threading.Event()
            timeout_seconds = self._get_user_prompt_timeout_seconds()
            start = time.time()

            def _show():
                self._input_event.clear()
                self._input_result = None
                self._show_input_bar(
                    f"{label}: {prompt}", default_value
                )

                def _wait():
                    while not self._input_event.wait(timeout=0.1):
                        if self.engine.abort_event.is_set():
                            self.after(0, self._hide_input_bar)
                            result[0] = None
                            done.set()
                            return
                    val = self._input_result
                    self.after(0, self._hide_input_bar)
                    if val:
                        self.append_log(
                            f"[{datetime.now().strftime('%H:%M:%S')}] "
                            f"{label}: {val}"
                        )
                    elif val == "":
                        self.append_log(
                            f"[{datetime.now().strftime('%H:%M:%S')}] "
                            f"{label}: (skipped)"
                        )
                    result[0] = val
                    done.set()

                threading.Thread(target=_wait, daemon=True).start()

            self.after(0, _show)
            # Caller may be a worker thread; this loop must not touch tkinter.
            while not done.wait(timeout=0.1):
                if self.engine.abort_event.is_set():
                    return None
                if (timeout_seconds is not None and
                    time.time() - start >= timeout_seconds):
                    def _timeout_cleanup():
                        self._input_result = None
                        self._hide_input_bar()
                        self._input_event.set()

                    self.after(0, _timeout_cleanup)
                    done.wait(timeout=1.0)
                    return None
            return result[0]

    def ask_yesno(self, prompt):
        """Render an inline Yes/No prompt in the log pane and wait for answer."""
        if threading.current_thread() is threading.main_thread():
            return bool(
                messagebox.askyesno(
                    "Confirm",
                    prompt,
                    parent=self,
                )
            )

        result = [None]
        done   = threading.Event()
        finish_holder = {"fn": None}
        timeout_seconds = self._get_user_prompt_timeout_seconds()
        start = time.time()

        def _show():
            ts = datetime.now().strftime("%H:%M:%S")
            self._append_log_text_main(f"[{ts}] {prompt}", "prompt")

            btn_frame = tk.Frame(self.log_text, bg="#161b22")

            def finish(answer, answer_text=None):
                if done.is_set():
                    return
                result[0] = answer
                try:
                    btn_frame.destroy()
                except Exception:
                    pass
                if answer_text:
                    self._append_log_text_main(
                        f"[{datetime.now().strftime('%H:%M:%S')}] {answer_text}",
                        "answer",
                    )
                done.set()

            finish_holder["fn"] = finish

            def yes():
                if done.is_set() or self.engine.abort_event.is_set():
                    return
                finish(True, "→ Yes")

            def no():
                if done.is_set() or self.engine.abort_event.is_set():
                    return
                finish(False, "→ No")

            tk.Button(
                btn_frame, text="  Yes  ",
                bg="#238636", fg="white",
                font=("Segoe UI", 10, "bold"),
                command=yes, relief="flat"
            ).pack(side="left", padx=6, pady=4)
            tk.Button(
                btn_frame, text="  No  ",
                bg="#c94b4b", fg="white",
                font=("Segoe UI", 10, "bold"),
                command=no, relief="flat"
            ).pack(side="left", padx=6, pady=4)

            # Re-enable widget for embedded button insertion
            # (_append_log_text_main leaves it disabled).
            self.log_text.config(state="normal")
            self.log_text.window_create("end", window=btn_frame)
            self.log_text.insert("end", "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

            # Abort watcher — unblocks immediately if abort fires
            def _abort_watch():
                while not done.is_set():
                    if self.engine.abort_event.is_set():
                        self.after(0, lambda: finish(False))
                        return
                    time.sleep(0.1)

            threading.Thread(
                target=_abort_watch, daemon=True
            ).start()

        self.after(0, _show)
        # Wait by event polling so worker threads can call this safely
        # while tkinter widgets are still managed on the main thread.
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return False
            if (timeout_seconds is not None and
                    time.time() - start >= timeout_seconds):
                if finish_holder["fn"] is not None:
                    self.after(0, lambda: finish_holder["fn"](False))
                    done.wait(timeout=1.0)
                return False
        return result[0] if result[0] is not None else False

    def ask_directory(self, title, prompt, initialdir=""):
        """Open a native folder picker and return selected path or None."""
        def _pick():
            # Bring the app window to the foreground first so the native dialog
            # is less likely to appear behind other windows.
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
                self.update_idletasks()
            except Exception:
                pass

            chosen = filedialog.askdirectory(
                title=f"{title}: {prompt}",
                initialdir=initialdir or os.path.expanduser("~"),
                mustexist=False,
                parent=self,
            )

            try:
                self.lift()
                self.focus_force()
            except Exception:
                pass

            return chosen if chosen else None

        return self._run_on_main(_pick)

    def ask_open_file(
        self,
        title,
        prompt,
        initialdir="",
        initialfile="",
        filetypes=(("All files", "*.*"),),
    ):
        """Open a native file picker and return selected path or None."""
        def _pick():
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
                self.update_idletasks()
            except Exception:
                pass

            chosen = filedialog.askopenfilename(
                title=f"{title}: {prompt}",
                initialdir=initialdir or os.path.expanduser("~"),
                initialfile=initialfile or "",
                filetypes=filetypes,
                parent=self,
            )

            try:
                self.lift()
                self.focus_force()
            except Exception:
                pass

            return chosen if chosen else None

        return self._run_on_main(_pick)

    def ask_save_file(
        self,
        title,
        prompt,
        initialdir="",
        initialfile="",
        defaultextension="",
        filetypes=(("All files", "*.*"),),
    ):
        """Open a native save dialog and return selected path or None."""
        def _pick():
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
                self.update_idletasks()
            except Exception:
                pass

            chosen = filedialog.asksaveasfilename(
                title=f"{title}: {prompt}",
                initialdir=initialdir or os.path.expanduser("~"),
                initialfile=initialfile or "",
                defaultextension=defaultextension,
                filetypes=filetypes,
                parent=self,
            )

            try:
                self.lift()
                self.focus_force()
            except Exception:
                pass

            return chosen if chosen else None

        return self._run_on_main(_pick)

    def ask_duplicate_resolution(self, prompt,
                                 retry_text="Swap and Retry",
                                 bypass_text="Not a Dup",
                                 stop_text="Stop"):
        """
        Three-way decision prompt for duplicate-disc handling.
        Returns one of: 'retry', 'bypass', 'stop'.
        """
        if threading.current_thread() is threading.main_thread():
            return self._ask_duplicate_resolution_modal(
                prompt,
                retry_text=retry_text,
                bypass_text=bypass_text,
                stop_text=stop_text,
            )

        result = ["stop"]
        done   = threading.Event()
        finish_holder = {"fn": None}
        timeout_seconds = self._get_user_prompt_timeout_seconds()
        start = time.time()

        def _show():
            self.log_text.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(
                "end", f"[{ts}] {prompt}\n", "prompt"
            )

            btn_frame = tk.Frame(self.log_text, bg="#161b22")

            def finish(value, answer_text=None):
                if done.is_set():
                    return
                result[0] = value
                try:
                    btn_frame.destroy()
                except Exception:
                    pass
                if answer_text:
                    self.log_text.config(state="normal")
                    self.log_text.insert(
                        "end",
                        f"[{datetime.now().strftime('%H:%M:%S')}] "
                        f"{answer_text}\n",
                        "answer"
                    )
                    self.log_text.see("end")
                    self.log_text.config(state="disabled")
                done.set()

            finish_holder["fn"] = finish

            def choose_retry():
                if done.is_set() or self.engine.abort_event.is_set():
                    return
                finish("retry", f"→ {retry_text}")

            def choose_bypass():
                if done.is_set() or self.engine.abort_event.is_set():
                    return
                finish("bypass", f"→ {bypass_text}")

            def choose_stop():
                if done.is_set() or self.engine.abort_event.is_set():
                    return
                finish("stop", f"→ {stop_text}")

            tk.Button(
                btn_frame, text=f"  {retry_text}  ",
                bg="#238636", fg="white",
                font=("Segoe UI", 10, "bold"),
                command=choose_retry, relief="flat"
            ).pack(side="left", padx=4, pady=4)

            tk.Button(
                btn_frame, text=f"  {bypass_text}  ",
                bg="#1f6feb", fg="white",
                font=("Segoe UI", 10, "bold"),
                command=choose_bypass, relief="flat"
            ).pack(side="left", padx=4, pady=4)

            tk.Button(
                btn_frame, text=f"  {stop_text}  ",
                bg="#c94b4b", fg="white",
                font=("Segoe UI", 10, "bold"),
                command=choose_stop, relief="flat"
            ).pack(side="left", padx=4, pady=4)

            self.log_text.window_create("end", window=btn_frame)
            self.log_text.insert("end", "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")

            def _abort_watch():
                while not done.is_set():
                    if self.engine.abort_event.is_set():
                        self.after(0, lambda: finish("stop"))
                        return
                    time.sleep(0.1)

            threading.Thread(
                target=_abort_watch, daemon=True
            ).start()

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return "stop"
            if (timeout_seconds is not None and
                    time.time() - start >= timeout_seconds):
                if finish_holder["fn"] is not None:
                    self.after(0, lambda: finish_holder["fn"]("stop"))
                    done.wait(timeout=1.0)
                return "stop"
        return result[0]

    def _get_user_prompt_timeout_seconds(self):
        if not self.cfg.get("opt_user_prompt_timeout_enabled", False):
            return None
        try:
            return max(
                1,
                int(self.cfg.get("opt_user_prompt_timeout_seconds", 300))
            )
        except Exception:
            return 300

    def _ask_duplicate_resolution_modal(self, prompt,
                                        retry_text="Swap and Retry",
                                        bypass_text="Not a Dup",
                                        stop_text="Stop"):
        """Main-thread-safe modal duplicate prompt using a nested Tk event loop."""
        result = ["stop"]
        win = tk.Toplevel(self)
        win.title("Duplicate Disc Check")
        win.configure(bg="#161b22")
        win.grab_set()
        win.lift()
        win.focus_force()
        win.resizable(False, False)

        tk.Label(
            win,
            text=prompt,
            bg="#161b22",
            fg="#c9d1d9",
            justify="left",
            wraplength=520,
            font=("Segoe UI", 10),
        ).pack(padx=18, pady=(18, 10))

        btn_row = tk.Frame(win, bg="#161b22")
        btn_row.pack(padx=18, pady=(0, 18))

        def finish(value):
            result[0] = value
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", lambda: finish("stop"))

        tk.Button(
            btn_row,
            text=retry_text,
            bg="#238636",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=lambda: finish("retry"),
            relief="flat",
            width=16,
        ).pack(side="left", padx=4)
        tk.Button(
            btn_row,
            text=bypass_text,
            bg="#1f6feb",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=lambda: finish("bypass"),
            relief="flat",
            width=14,
        ).pack(side="left", padx=4)
        tk.Button(
            btn_row,
            text=stop_text,
            bg="#c94b4b",
            fg="white",
            font=("Segoe UI", 10, "bold"),
            command=lambda: finish("stop"),
            relief="flat",
            width=12,
        ).pack(side="left", padx=4)

        win.wait_window()
        return result[0]

    def _run_on_main(self, fn):
        """Execute callable on tkinter main loop and return its result."""
        if threading.current_thread() is threading.main_thread():
            return fn()

        result = [None]
        done   = threading.Event()

        def wrapper():
            try:
                result[0] = fn()
            finally:
                done.set()

        self.after(0, wrapper)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return None
        return result[0]

    def show_info(self, title, msg):
        self._run_on_main(
            lambda: messagebox.showinfo(title, msg, parent=self)
        )

    def show_error(self, title, msg):
        self._run_on_main(
            lambda: messagebox.showerror(title, msg, parent=self)
        )

    def _open_path_in_explorer(self, path):
        normalized = os.path.normpath(str(path))
        if not os.path.exists(normalized):
            self.show_error("Open in Explorer", f"Path not found:\n{normalized}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(normalized)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", normalized])
            else:
                subprocess.Popen(["xdg-open", normalized])
        except Exception as e:
            self.show_error("Open in Explorer", f"Could not open path:\n{normalized}\n\n{e}")

    def _reveal_path_in_explorer(self, path):
        normalized = os.path.normpath(str(path))
        if not os.path.exists(normalized):
            self.show_error("Reveal in Explorer", f"Path not found:\n{normalized}")
            return

        try:
            if sys.platform == "win32":
                target = normalized
                if os.path.isdir(normalized):
                    self._open_path_in_explorer(normalized)
                    return
                subprocess.Popen(["explorer", f"/select,{target}"])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", normalized])
            else:
                self._open_path_in_explorer(os.path.dirname(normalized) or normalized)
        except Exception as e:
            self.show_error("Reveal in Explorer", f"Could not reveal path:\n{normalized}\n\n{e}")

    def _browse_settings_path(self, key, label, current_path=""):
        normalized = os.path.normpath(current_path) if current_path else ""
        current_dir = ""
        if normalized:
            current_dir = normalized if os.path.isdir(normalized) else os.path.dirname(normalized)

        folder_keys = {"ffprobe_path", "temp_folder", "tv_folder", "movies_folder"}
        if key in folder_keys:
            return self.ask_directory("Browse", f"Choose {label.lower()}", initialdir=current_dir)

        if key == "log_file":
            default_name = os.path.basename(normalized) if normalized else "jellyrip.log"
            return self.ask_save_file(
                "Log File",
                f"Choose {label.lower()}",
                initialdir=current_dir,
                initialfile=default_name,
                defaultextension=".log",
                filetypes=(("Log files", "*.log *.txt"), ("All files", "*.*")),
            )

        default_name = os.path.basename(normalized) if normalized else ""
        return self.ask_open_file(
            "Tool Path",
            f"Choose {label.lower()}",
            initialdir=current_dir,
            initialfile=default_name,
            filetypes=(("Executable files", "*.exe"), ("All files", "*.*")),
        )

    def _open_settings_path(self, key, label, raw_path):
        normalized = os.path.normpath(raw_path.strip()) if raw_path else ""
        if not normalized:
            self.show_info("Open in Explorer", f"No path set for {label.lower()} yet.")
            return

        folder_keys = {"ffprobe_path", "temp_folder", "tv_folder", "movies_folder"}
        if key in folder_keys:
            self._open_path_in_explorer(normalized)
            return

        if os.path.exists(normalized):
            self._reveal_path_in_explorer(normalized)
            return

        parent = os.path.dirname(normalized)
        if parent and os.path.isdir(parent):
            self._open_path_in_explorer(parent)
            return

        self.show_error("Open in Explorer", f"Path not found:\n{normalized}")

    def ask_space_override(self, required_gb, free_gb):
        if threading.current_thread() is threading.main_thread():
            return self._ask_space_override_modal(required_gb, free_gb)

        result = [False]
        done   = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title("Not Enough Space")
            win.configure(bg="#1a0000")
            win.grab_set()
            win.lift()
            win.focus_force()
            win.resizable(False, False)

            tk.Label(
                win, text="⚠  NOT ENOUGH DISK SPACE",
                font=("Segoe UI", 16, "bold"),
                bg="#1a0000", fg="#ff4444"
            ).pack(pady=(20, 10), padx=20)
            tk.Label(
                win,
                text=f"Required:  {required_gb:.1f} GB\n"
                     f"Free:         {free_gb:.1f} GB\n\n"
                     f"This may cause the rip to fail\n"
                     f"or produce incomplete files.",
                font=("Segoe UI", 12),
                bg="#1a0000", fg="#ffcccc",
                justify="center"
            ).pack(pady=10, padx=30)

            bf = tk.Frame(win, bg="#1a0000")
            bf.pack(pady=20)

            def proceed():
                result[0] = True
                win.destroy()
                done.set()

            def cancel():
                result[0] = False
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", cancel)

            tk.Button(
                bf, text="I understand, continue anyway",
                bg="#c94b4b", fg="white",
                font=("Segoe UI", 11, "bold"),
                width=28, command=proceed, relief="flat"
            ).pack(side="left", padx=8)
            tk.Button(
                bf, text="Cancel",
                bg="#21262d", fg="white",
                font=("Segoe UI", 11),
                width=12, command=cancel, relief="flat"
            ).pack(side="left", padx=8)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return False
        return result[0]

    def _ask_space_override_modal(self, required_gb, free_gb):
        """Main-thread-safe modal version of the low-space override prompt."""
        result = [False]
        win = tk.Toplevel(self)
        win.title("Not Enough Space")
        win.configure(bg="#1a0000")
        win.grab_set()
        win.lift()
        win.focus_force()
        win.resizable(False, False)

        tk.Label(
            win, text="⚠  NOT ENOUGH DISK SPACE",
            font=("Segoe UI", 16, "bold"),
            bg="#1a0000", fg="#ff4444"
        ).pack(pady=(20, 10), padx=20)
        tk.Label(
            win,
            text=f"Required:  {required_gb:.1f} GB\n"
                 f"Free:         {free_gb:.1f} GB\n\n"
                 f"This may cause the rip to fail\n"
                 f"or produce incomplete files.",
            font=("Segoe UI", 12),
            bg="#1a0000", fg="#ffcccc",
            justify="center"
        ).pack(pady=10, padx=30)

        bf = tk.Frame(win, bg="#1a0000")
        bf.pack(pady=20)

        def finish(value):
            result[0] = bool(value)
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", lambda: finish(False))

        tk.Button(
            bf, text="I understand, continue anyway",
            bg="#c94b4b", fg="white",
            font=("Segoe UI", 11, "bold"),
            width=28, command=lambda: finish(True), relief="flat"
        ).pack(side="left", padx=8)
        tk.Button(
            bf, text="Cancel",
            bg="#21262d", fg="white",
            font=("Segoe UI", 11),
            width=12, command=lambda: finish(False), relief="flat"
        ).pack(side="left", padx=8)

        win.wait_window()
        return result[0]

    def show_disc_tree(self, disc_titles, is_tv, preview_callback=None):
        result = [None]
        done   = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title("Disc Contents — Select Titles to Rip")
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()
            win.geometry("1060x660")

            tk.Label(
                win,
                text="Select titles to rip. "
                     "Click anywhere on a row to toggle. "
                     "Best title candidate highlighted in blue.",
                bg="#0d1117", fg="#8b949e",
                font=("Segoe UI", 10)
            ).pack(pady=(10, 4), padx=15)

            tree_frame = tk.Frame(win, bg="#0d1117")
            tree_frame.pack(
                fill="both", expand=True, padx=15, pady=5
            )

            style = ttk.Style()
            style.theme_use("default")
            style.configure(
                "Disc.Treeview",
                background="#161b22", foreground="#c9d1d9",
                fieldbackground="#161b22", rowheight=24,
                font=("Consolas", 10)
            )
            style.configure(
                "Disc.Treeview.Heading",
                background="#21262d", foreground="#58a6ff",
                font=("Segoe UI", 10, "bold")
            )
            style.map(
                "Disc.Treeview",
                background=[("selected", "#1f6feb")]
            )

            tree = ttk.Treeview(
                tree_frame, style="Disc.Treeview",
                columns=("duration", "size", "chapters", "audio", "preview"),
                show="tree headings"
            )
            tree.heading("#0",       text="Title / Track")
            tree.heading("duration", text="Duration")
            tree.heading("size",     text="Size")
            tree.heading("chapters", text="Chapters")
            tree.heading("audio",    text="Audio")
            tree.heading("preview",  text="Preview")
            tree.column("#0",       width=220)
            tree.column("duration", width=80,  anchor="center")
            tree.column("size",     width=80,  anchor="center")
            tree.column("chapters", width=70,  anchor="center")
            tree.column("audio",    width=320, anchor="w")
            tree.column("preview",  width=90,  anchor="center")

            vsb = ttk.Scrollbar(
                tree_frame, orient="vertical", command=tree.yview
            )
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            check_vars  = {}
            base_labels = {}

            # Compute best candidate directly from score.
            best_title, _best_score = choose_best_title(disc_titles)
            best_id = best_title["id"] if best_title else None
            id_map  = {t["id"]: t for t in disc_titles}

            for t in disc_titles:
                audio_summary = format_audio_summary(
                    t.get("audio_tracks", [])
                )
                iid          = f"title_{t['id']}"
                pre_selected = (t["id"] == best_id)
                check_vars[iid]  = pre_selected
                base_labels[iid] = f"Title {t['id']+1}: {t['name']}"
                check_char       = "☑" if pre_selected else "☐"

                tags = ["title"]
                if t["id"] == best_id:
                    tags.append("main")

                tree.insert(
                    "", "end", iid=iid,
                    text=f"{check_char}  {base_labels[iid]}",
                    values=(
                        t.get("duration", ""),
                        t.get("size", ""),
                        t.get("chapters", ""),
                        audio_summary,
                        "Preview",
                    ),
                    tags=tuple(tags)
                )

                for s in t.get("subtitle_tracks", []):
                    lang = (s.get("lang_name") or
                            s.get("lang") or "Unknown")
                    tree.insert(
                        iid, "end",
                        text=f"    💬 Subtitle: {lang}",
                        values=("", "", "", "", ""),
                        tags=("track",)
                    )

            tree.tag_configure("title", foreground="#c9d1d9")
            tree.tag_configure("main",  foreground="#58a6ff")
            tree.tag_configure("track", foreground="#6e7681")

            def toggle(event):
                item = tree.identify_row(event.y)
                if not item or not item.startswith("title_"):
                    return
                col = tree.identify_column(event.x)
                if col == "#5" and preview_callback:
                    try:
                        tid = int(item.split("_")[1])
                        preview_callback(tid)
                    except Exception:
                        pass
                    return
                check_vars[item] = not check_vars[item]
                prefix = "☑" if check_vars[item] else "☐"
                tree.item(
                    item, text=f"{prefix}  {base_labels[item]}"
                )
                _update_size_label()

            tree.bind("<Button-1>", toggle)

            def _update_size_label():
                total = sum(
                    id_map[int(iid.split("_")[1])].get("size_bytes", 0)
                    for iid, checked in check_vars.items()
                    if checked
                )
                size_label_var.set(
                    f"Selected: ~{total / (1024**3):.1f} GB"
                )

            def select_all():
                for iid in check_vars:
                    check_vars[iid] = True
                    tree.item(iid, text=f"☑  {base_labels[iid]}")
                _update_size_label()

            def deselect_all():
                for iid in check_vars:
                    check_vars[iid] = False
                    tree.item(iid, text=f"☐  {base_labels[iid]}")
                _update_size_label()

            def select_best():
                for iid in check_vars:
                    check_vars[iid] = False
                    tree.item(iid, text=f"☐  {base_labels[iid]}")
                if best_id is not None:
                    iid = f"title_{best_id}"
                    check_vars[iid] = True
                    tree.item(iid, text=f"☑  {base_labels[iid]}")
                _update_size_label()

            def select_top3():
                for iid in check_vars:
                    check_vars[iid] = False
                    tree.item(iid, text=f"☐  {base_labels[iid]}")
                for t in disc_titles[:3]:
                    iid = f"title_{t['id']}"
                    check_vars[iid] = True
                    tree.item(iid, text=f"☑  {base_labels[iid]}")
                _update_size_label()

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(fill="x", padx=15, pady=8)

            size_label_var = tk.StringVar(value="")
            _update_size_label()

            tk.Label(
                btn_row, textvariable=size_label_var,
                bg="#0d1117", fg="#58a6ff",
                font=("Segoe UI", 10, "bold")
            ).pack(side="left", padx=8)

            for text, cmd in [
                ("Select All",   select_all),
                ("Deselect All", deselect_all),
                ("Best Only",    select_best),
                ("Top 3",        select_top3),
            ]:
                tk.Button(
                    btn_row, text=text, command=cmd,
                    bg="#21262d", fg="#c9d1d9",
                    font=("Segoe UI", 10), relief="flat"
                ).pack(side="left", padx=4)

            def confirm():
                selected = [
                    int(iid.split("_")[1])
                    for iid, checked in check_vars.items()
                    if checked
                ]
                result[0] = selected
                win.destroy()
                done.set()

            def cancel():
                result[0] = None
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", cancel)

            tk.Button(
                btn_row, text="Rip Selected",
                bg="#238636", fg="white",
                font=("Segoe UI", 11, "bold"),
                command=confirm, relief="flat"
            ).pack(side="right", padx=4)
            tk.Button(
                btn_row, text="Cancel",
                bg="#21262d", fg="white",
                command=cancel, relief="flat"
            ).pack(side="right", padx=4)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return None
        return result[0]

    def show_file_list(self, title, prompt, options):
        result = [None]
        done   = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title(title)
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()

            tk.Label(
                win, text=prompt,
                bg="#0d1117", fg="#c9d1d9",
                font=("Segoe UI", 11), wraplength=500
            ).pack(pady=10, padx=15)

            listbox = tk.Listbox(
                win, bg="#161b22", fg="#c9d1d9",
                font=("Consolas", 10), width=70,
                height=min(len(options), 15),
                selectmode="extended", relief="flat"
            )
            listbox.pack(padx=15, pady=5)
            for opt in options:
                listbox.insert("end", opt)
            listbox.select_set(0)

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(pady=4)
            tk.Button(
                btn_row, text="Select All",
                bg="#21262d", fg="#c9d1d9",
                command=lambda: listbox.select_set(0, "end"),
                relief="flat"
            ).pack(side="left", padx=6)
            tk.Button(
                btn_row, text="Deselect All",
                bg="#21262d", fg="#c9d1d9",
                command=lambda: listbox.selection_clear(0, "end"),
                relief="flat"
            ).pack(side="left", padx=6)

            def confirm():
                result[0] = [
                    listbox.get(i) for i in listbox.curselection()
                ]
                win.destroy()
                done.set()

            def on_close():
                result[0] = []
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", on_close)
            tk.Button(
                win, text="Confirm",
                bg="#238636", fg="white",
                font=("Segoe UI", 11),
                command=confirm, relief="flat"
            ).pack(pady=10)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return []
        return result[0]

    def show_extras_picker(self, title, prompt, options):
        """Multi-select dialog with all items pre-selected.
        Returns list of selected 0-based indices, or None if cancelled.
        """
        result = [None]
        done   = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            win.title(title)
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()

            tk.Label(
                win, text=prompt,
                bg="#0d1117", fg="#c9d1d9",
                font=("Segoe UI", 11), wraplength=500
            ).pack(pady=10, padx=15)

            listbox = tk.Listbox(
                win, bg="#161b22", fg="#c9d1d9",
                font=("Consolas", 10), width=70,
                height=min(len(options), 15),
                selectmode="extended", relief="flat"
            )
            listbox.pack(padx=15, pady=5)
            for opt in options:
                listbox.insert("end", opt)
            listbox.select_set(0, "end")  # pre-select all

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(pady=4)
            tk.Button(
                btn_row, text="Select All",
                bg="#21262d", fg="#c9d1d9",
                command=lambda: listbox.select_set(0, "end"),
                relief="flat"
            ).pack(side="left", padx=6)
            tk.Button(
                btn_row, text="Deselect All",
                bg="#21262d", fg="#c9d1d9",
                command=lambda: listbox.selection_clear(0, "end"),
                relief="flat"
            ).pack(side="left", padx=6)

            def confirm():
                result[0] = list(listbox.curselection())
                win.destroy()
                done.set()

            def on_close():
                result[0] = None
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", on_close)
            tk.Button(
                win, text="Confirm",
                bg="#238636", fg="white",
                font=("Segoe UI", 11),
                command=confirm, relief="flat"
            ).pack(pady=10)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return None
        return result[0]

    def show_temp_manager(self, old_folders, engine, log_fn):
        if not old_folders:
            return
        done = threading.Event()

        STATUS_COLORS = {
            "ripped":     "#238636",
            "organizing": "#f0a500",
            "ripping":    "#f0a500",
            "organized":  "#1f6feb",
        }
        DEFAULT_COLOR = "#c94b4b"

        def _show():
            win = tk.Toplevel(self)
            win.title("Temp Session Manager")
            win.configure(bg="#0d1117")
            win.grab_set()
            win.lift()
            win.focus_force()
            win.geometry("740x540")

            tk.Label(
                win, text="Temp Sessions",
                font=("Segoe UI", 14, "bold"),
                bg="#0d1117", fg="#58a6ff"
            ).pack(pady=(15, 5))
            tk.Label(
                win,
                text="Leftover disc folders in your temp directory.\n"
                     "Check the ones you want to delete.",
                font=("Segoe UI", 10),
                bg="#0d1117", fg="#8b949e"
            ).pack(pady=(0, 10))

            frame = tk.Frame(win, bg="#0d1117")
            frame.pack(fill="both", expand=True, padx=15, pady=5)

            canvas = tk.Canvas(
                frame, bg="#0d1117", highlightthickness=0
            )
            scrollbar = ttk.Scrollbar(
                frame, orient="vertical", command=canvas.yview
            )
            scroll_frame = tk.Frame(canvas, bg="#0d1117")

            scroll_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(
                    scrollregion=canvas.bbox("all")
                )
            )
            canvas.create_window(
                (0, 0), window=scroll_frame, anchor="nw"
            )
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            check_vars = []

            for full_path, name, file_count, size in old_folders:
                meta = engine.read_temp_metadata(full_path)
                var  = tk.BooleanVar(value=False)
                check_vars.append((var, full_path, name))

                status_text = (
                    meta.get("status", "unknown")
                    if meta else "unknown"
                )
                color = STATUS_COLORS.get(status_text, DEFAULT_COLOR)

                row = tk.Frame(scroll_frame, bg="#161b22")
                row.pack(fill="x", pady=3, padx=5)

                tk.Checkbutton(
                    row, variable=var,
                    bg="#161b22", activebackground="#161b22",
                    selectcolor="#238636"
                ).pack(side="left", padx=8, pady=8)

                tk.Label(
                    row, text="●", fg=color, bg="#161b22",
                    font=("Segoe UI", 14)
                ).pack(side="left", padx=(0, 6))

                info = tk.Frame(row, bg="#161b22")
                info.pack(
                    side="left", fill="x", expand=True, pady=6
                )

                title_text = (
                    meta.get("title", "Unknown")
                    if meta else "Unknown"
                )
                ts_text = (
                    meta.get("timestamp", name) if meta else name
                )

                tk.Label(
                    info, text=title_text,
                    font=("Segoe UI", 11, "bold"),
                    bg="#161b22", fg="#c9d1d9", anchor="w"
                ).pack(fill="x")
                tk.Label(
                    info,
                    text=f"Ripped: {ts_text}   "
                         f"Files: {file_count}   "
                         f"Size: {size / (1024**3):.1f} GB   "
                         f"Status: {status_text}",
                    font=("Segoe UI", 9),
                    bg="#161b22", fg="#8b949e", anchor="w"
                ).pack(fill="x")

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(fill="x", padx=15, pady=12)

            def select_all():
                for var, _, _ in check_vars:
                    var.set(True)

            def deselect_all():
                for var, _, _ in check_vars:
                    var.set(False)

            def delete_selected():
                selected = [
                    (full_path, name)
                    for var, full_path, name in check_vars
                    if var.get()
                ]

                # Close first to keep UI responsive; delete on background
                # thread so large folder trees do not block tkinter.
                win.destroy()

                def _delete_worker():
                    for full_path, name in selected:
                        try:
                            shutil.rmtree(full_path)
                            log_fn(f"Deleted temp folder: {name}")
                        except Exception as e:
                            log_fn(f"Could not delete {name}: {e}")
                    done.set()

                threading.Thread(
                    target=_delete_worker,
                    daemon=True
                ).start()

            def close():
                win.destroy()
                done.set()

            win.protocol("WM_DELETE_WINDOW", close)

            tk.Button(
                btn_row, text="Select All",
                bg="#21262d", fg="#c9d1d9",
                command=select_all, relief="flat"
            ).pack(side="left", padx=4)
            tk.Button(
                btn_row, text="Deselect All",
                bg="#21262d", fg="#c9d1d9",
                command=deselect_all, relief="flat"
            ).pack(side="left", padx=4)
            tk.Button(
                btn_row, text="Delete Selected",
                bg="#c94b4b", fg="white",
                font=("Segoe UI", 11, "bold"),
                command=delete_selected, relief="flat"
            ).pack(side="right", padx=4)
            tk.Button(
                btn_row, text="Close",
                bg="#21262d", fg="white",
                command=close, relief="flat"
            ).pack(side="right", padx=4)

        self.after(0, _show)
        while not done.wait(timeout=0.1):
            if self.engine.abort_event.is_set():
                return

    def _open_settings_safe(self):
        """Prevent callback exceptions from tearing down the main window."""
        try:
            self.open_settings()
        except Exception as e:
            self._settings_window = None
            import traceback
            tb = traceback.format_exc()
            try:
                self.controller.log(f"Fatal settings callback error: {e}\n{tb}")
            except Exception:
                pass
            try:
                self.show_error("Settings Error", f"Could not open Settings:\n{e}")
            except Exception:
                messagebox.showerror(
                    "Settings Error",
                    f"Could not open Settings:\n{e}",
                    parent=self,
                )


    def open_settings(self):
        cfg = self.cfg
        # Expert Mode toggle (persistent in config)
        expert_mode_var = tk.BooleanVar(value=cfg.get('opt_expert_mode', False))
        if self.rip_thread and self.rip_thread.is_alive():
            messagebox.showwarning(
                "Rip in Progress",
                "Settings cannot be opened during an active rip.\n"
                "Abort the current session first, or wait for it to finish.",
                parent=self,
            )
            return

        if (
            self._settings_window is not None
            and self._settings_window.winfo_exists()
        ):
            try:
                self._settings_window.lift()
                self._settings_window.focus_force()
            except Exception:
                pass
            return

        done = threading.Event()

        def _show():
            win = tk.Toplevel(self)
            self._settings_window = win
            win.title("JellyRip Settings")
            expert_toggle_row = tk.Frame(win, bg="#0d1117")
            expert_toggle_row.pack(fill="x", padx=16, pady=(8, 0))
            tk.Checkbutton(
                expert_toggle_row, variable=expert_mode_var,
                bg="#0d1117", activebackground="#0d1117",
                selectcolor="#238636",
                fg="#c9d1d9", font=("Segoe UI", 11, "bold"),
                text="Enable Expert Mode (show all advanced profile options)", anchor="w"
            ).pack(side="left")
            win.configure(bg="#0d1117")
            try:
                win.grab_set()
            except tk.TclError:
                # Avoid crashing if another dialog currently owns grab.
                pass
            win.lift()
            win.focus_force()
            win.geometry("700x800")
            win.resizable(False, True)

            style = ttk.Style(win)
            style.configure("JellyRip.TNotebook", background="#0d1117")
            style.configure(
                "JellyRip.TNotebook.Tab",
                padding=(12, 8),
                background="#21262d",
                foreground="#c9d1d9"
            )
            style.map(
                "JellyRip.TNotebook.Tab",
                background=[("selected", "#161b22")],
                foreground=[("selected", "#58a6ff")]
            )

            notebook = ttk.Notebook(win, style="JellyRip.TNotebook")
            notebook.pack(fill="both", expand=True, padx=8, pady=(8, 0))

            def make_scroll_tab(title):
                tab = tk.Frame(notebook, bg="#0d1117")
                canvas = tk.Canvas(
                    tab, bg="#0d1117", highlightthickness=0
                )
                scrollbar = ttk.Scrollbar(
                    tab, orient="vertical", command=canvas.yview
                )
                scroll_frame = tk.Frame(canvas, bg="#0d1117")

                scroll_frame.bind(
                    "<Configure>",
                    lambda e, c=canvas: c.configure(
                        scrollregion=c.bbox("all")
                    )
                )
                canvas.create_window(
                    (0, 0), window=scroll_frame, anchor="nw"
                )
                canvas.configure(yscrollcommand=scrollbar.set)
                canvas.pack(side="left", fill="both", expand=True)
                scrollbar.pack(side="right", fill="y")
                notebook.add(tab, text=title)
                return scroll_frame

            paths_tab = make_scroll_tab("Paths")
            everyday_tab = make_scroll_tab("Everyday")
            validation_tab = make_scroll_tab("Validation")
            advanced_tab = make_scroll_tab("Advanced")
            logs_tab = make_scroll_tab("Logs & Debug")
            expert_tab = None
            if expert_mode_var.get():
                expert_tab = make_scroll_tab("Expert")
            # --- Expert Tab (if enabled) ---
            if expert_tab is not None:
                section(expert_tab, "Transcode Profile (Expert)")
                # Show all profile parameters for direct editing
                from transcode.profiles import PROFILE_SCHEMA
                expert_vars = {}
                for section_name, keys in PROFILE_SCHEMA.items():
                    section(expert_tab, section_name.capitalize())
                    for key in keys:
                        row = tk.Frame(expert_tab, bg="#0d1117")
                        row.pack(fill="x", padx=24, pady=2)
                        tk.Label(
                            row, text=key, bg="#0d1117", fg="#c9d1d9",
                            font=("Segoe UI", 10), width=18, anchor="w"
                        ).pack(side="left")
                        var = tk.StringVar()
                        tk.Entry(
                            row, textvariable=var,
                            bg="#161b22", fg="#c9d1d9",
                            font=("Segoe UI", 10), relief="flat", bd=3, width=24
                        ).pack(side="left")
                        expert_vars[f"{section_name}.{key}"] = var
                # Optionally: add a button to apply expert profile changes
                def apply_expert_profile():
                    # This is a placeholder for applying expert profile changes
                    # You would parse and validate the values, then update the profile
                    self.controller.log("Expert profile changes applied (not yet implemented)")
                tk.Button(
                    expert_tab, text="Apply Expert Profile Changes",
                    bg="#238636", fg="white", font=("Segoe UI", 10, "bold"),
                    command=apply_expert_profile
                ).pack(pady=12)

            cfg      = self.cfg
            vars_map = {}
            naming_mode_label_to_value = {
                "Timestamp (default)": "timestamp",
                "Auto title": "auto-title",
                "Auto title + timestamp (safe)": "auto-title+timestamp",
            }
            naming_mode_value_to_label = {
                value: label
                for label, value in naming_mode_label_to_value.items()
            }

            def section(parent, text):
                tk.Label(
                    parent, text=text,
                    bg="#0d1117", fg="#58a6ff",
                    font=("Segoe UI", 11, "bold"), anchor="w"
                ).pack(fill="x", padx=16, pady=(14, 2))
                tk.Frame(
                    parent, bg="#21262d", height=1
                ).pack(fill="x", padx=16, pady=(0, 6))

            def path_row(parent, key, label):
                row = tk.Frame(parent, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=3)
                tk.Label(
                    row, text=label, bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), width=28, anchor="w"
                ).pack(side="left")
                var = tk.StringVar(
                    value=cfg.get(key, DEFAULTS.get(key, ""))
                )
                tk.Entry(
                    row, textvariable=var,
                    bg="#161b22", fg="#c9d1d9",
                    font=("Segoe UI", 10),
                    insertbackground="white",
                    relief="flat", bd=3, width=28
                ).pack(side="left", padx=4)

                def browse_path():
                    chosen = self._browse_settings_path(
                        key,
                        label,
                        var.get().strip(),
                    )
                    if chosen:
                        var.set(os.path.normpath(chosen))

                tk.Button(
                    row, text="Browse",
                    bg="#21262d", fg="#c9d1d9",
                    font=("Segoe UI", 9),
                    relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2",
                    command=browse_path,
                ).pack(side="left", padx=(4, 2))
                tk.Button(
                    row, text="Open",
                    bg="#21262d", fg="#8b949e",
                    font=("Segoe UI", 9),
                    relief="flat", bd=0, padx=8, pady=2,
                    cursor="hand2",
                    command=lambda: self._open_settings_path(
                        key,
                        label,
                        var.get(),
                    ),
                ).pack(side="left", padx=(2, 0))

                vars_map[key] = ("str", var)

            def toggle_row(parent, key, label):
                """Create a toggle row without dependent number field.
                Number fields are now created separately for full independence."""
                row = tk.Frame(parent, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                bool_var = tk.BooleanVar(value=cfg.get(key, True))
                tk.Checkbutton(
                    row, variable=bool_var,
                    bg="#0d1117", activebackground="#0d1117",
                    selectcolor="#238636",
                    fg="#c9d1d9", font=("Segoe UI", 10),
                    text=label, anchor="w"
                ).pack(side="left")
                vars_map[key] = ("bool", bool_var)

            def number_row(parent, key, label, default=0):
                row = tk.Frame(parent, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                tk.Label(
                    row, text=label,
                    bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), anchor="w", width=36
                ).pack(side="left")
                num_var = tk.StringVar(
                    value=str(cfg.get(key, default))
                )
                tk.Entry(
                    row, textvariable=num_var,
                    bg="#161b22", fg="#c9d1d9",
                    font=("Segoe UI", 10),
                    relief="flat", bd=3, width=10
                ).pack(side="left")
                vars_map[key] = ("int", num_var)

            def float_row(parent, key, label, default=0.0):
                row = tk.Frame(parent, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                tk.Label(
                    row, text=label,
                    bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), anchor="w", width=36
                ).pack(side="left")
                num_var = tk.StringVar(
                    value=str(cfg.get(key, default))
                )
                tk.Entry(
                    row, textvariable=num_var,
                    bg="#161b22", fg="#c9d1d9",
                    font=("Segoe UI", 10),
                    relief="flat", bd=3, width=10
                ).pack(side="left")
                vars_map[key] = ("float", num_var)

            def text_row(parent, key, label, width=38):
                row = tk.Frame(parent, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                tk.Label(
                    row, text=label,
                    bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), anchor="w", width=36
                ).pack(side="left")
                txt_var = tk.StringVar(
                    value=cfg.get(key, DEFAULTS.get(key, ""))
                )
                tk.Entry(
                    row, textvariable=txt_var,
                    bg="#161b22", fg="#c9d1d9",
                    font=("Segoe UI", 10),
                    relief="flat", bd=3, width=width
                ).pack(side="left")
                vars_map[key] = ("text", txt_var)

            def choice_row(parent, key, label, choices):
                row = tk.Frame(parent, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                tk.Label(
                    row, text=label,
                    bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), anchor="w", width=36
                ).pack(side="left")
                selected = tk.StringVar(
                    value=cfg.get(key, DEFAULTS.get(key, choices[0]))
                )
                combo = ttk.Combobox(
                    row, textvariable=selected,
                    values=choices, state="readonly", width=24
                )
                combo.pack(side="left")
                vars_map[key] = ("choice", selected)
                return selected

            def choice_map_row(parent, key, label, label_to_value):
                row = tk.Frame(parent, bg="#0d1117")
                row.pack(fill="x", padx=16, pady=2)
                tk.Label(
                    row, text=label,
                    bg="#0d1117", fg="#c9d1d9",
                    font=("Segoe UI", 10), anchor="w", width=36
                ).pack(side="left")
                current_value = str(
                    cfg.get(key, DEFAULTS.get(key, ""))
                ).strip()
                normalized_value = normalize_ffmpeg_source_mode(current_value)
                selected = tk.StringVar(
                    value=_ffmpeg_source_mode_label(normalized_value)
                )
                combo = ttk.Combobox(
                    row,
                    textvariable=selected,
                    values=list(label_to_value.keys()),
                    state="readonly",
                    width=24,
                )
                combo.pack(side="left")
                vars_map[key] = ("choice_map", selected, label_to_value)
                return selected

            section(paths_tab, "Apps")
            path_row(paths_tab, "makemkvcon_path", "MakeMKV app")
            path_row(paths_tab, "ffprobe_path",    "ffmpeg / ffprobe folder")
            path_row(paths_tab, "ffmpeg_path",     "FFmpeg executable")
            path_row(paths_tab, "handbrake_path",  "HandBrakeCLI executable")

            # Auto Locate button
            _auto_status_var = tk.StringVar()

            def _do_auto_locate():
                mkv, ffp = auto_locate_tools()
                ffmpeg = auto_locate_ffmpeg()
                handbrake = auto_locate_handbrake()
                results = []
                if mkv:
                    vars_map["makemkvcon_path"][1].set(mkv)
                    results.append("MakeMKV")
                if ffp:
                    vars_map["ffprobe_path"][1].set(ffp)
                    results.append("FFprobe")
                if ffmpeg:
                    vars_map["ffmpeg_path"][1].set(ffmpeg)
                    results.append("FFmpeg")
                if handbrake:
                    vars_map["handbrake_path"][1].set(handbrake)
                    results.append("HandBrakeCLI")
                if results:
                    _auto_status_var.set(f"  Found: {', '.join(results)}")
                else:
                    _auto_status_var.set("  Neither tool found automatically.")
                win.after(5000, lambda: _auto_status_var.set(""))

            auto_btn_row = tk.Frame(paths_tab, bg="#0d1117")
            auto_btn_row.pack(fill="x", padx=16, pady=(0, 6))
            tk.Button(
                auto_btn_row, text="Auto Locate",
                bg="#21262d", fg="#c9d1d9",
                font=("Segoe UI", 10),
                relief="flat", bd=0, padx=8, pady=2,
                cursor="hand2",
                command=_do_auto_locate,
            ).pack(side="left")
            tk.Label(
                auto_btn_row, textvariable=_auto_status_var,
                bg="#0d1117", fg="#3fb950",
                font=("Segoe UI", 9),
            ).pack(side="left", padx=8)

            section(paths_tab, "Folders")
            path_row(paths_tab, "temp_folder",     "Temp folder")
            path_row(paths_tab, "tv_folder",       "TV shows library folder")
            path_row(paths_tab, "movies_folder",   "Movies folder")

            row = tk.Frame(paths_tab, bg="#0d1117")
            row.pack(fill="x", padx=16, pady=2)
            tk.Label(
                row, text="Naming mode:",
                bg="#0d1117", fg="#c9d1d9",
                font=("Segoe UI", 10), anchor="w", width=36
            ).pack(side="left")

            mode_value = resolve_naming_mode(cfg)
            if mode_value == "disc-title":
                mode_value = "auto-title"
            elif mode_value == "disc-title+timestamp":
                mode_value = "auto-title+timestamp"

            naming_mode_var = tk.StringVar(
                value=naming_mode_value_to_label.get(
                    mode_value, "Timestamp (default)"
                )
            )
            naming_dropdown = ttk.Combobox(
                row,
                textvariable=naming_mode_var,
                state="readonly",
                values=list(naming_mode_label_to_value.keys()),
                width=30,
            )
            naming_dropdown.pack(side="left")
            vars_map["opt_naming_mode"] = ("naming_mode", naming_mode_var)

            naming_preview_var = tk.StringVar()
            tk.Label(
                paths_tab,
                textvariable=naming_preview_var,
                bg="#0d1117",
                fg="#8b949e",
                font=("Segoe UI", 9),
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 4))

            def update_naming_preview(*_args):
                selected = naming_mode_var.get().strip()
                mode = normalize_naming_mode(
                    naming_mode_label_to_value.get(selected, "timestamp")
                )
                sample_title = "Inception"
                sample_rip = make_rip_folder_name()
                naming_preview_var.set(
                    build_naming_preview_text(
                        mode, sample_title, sample_rip
                    )
                )

            naming_mode_var.trace_add("write", update_naming_preview)
            update_naming_preview()

            path_row(paths_tab, "log_file",        "Log file")

            section(everyday_tab, "Common Options")
            toggle_row(everyday_tab, "opt_safe_mode",
                       "Safe Mode (recommended)")
            toggle_row(everyday_tab, "opt_confirm_before_rip",
                       "Ask before ripping")
            toggle_row(everyday_tab, "opt_confirm_before_move",
                       "Ask before moving files")
            toggle_row(everyday_tab, "opt_smart_rip_mode",
                       "Smart Rip (auto-pick best title)")
            number_row(everyday_tab, "opt_smart_min_minutes",
                       "Shortest movie length for Smart Rip (minutes):", 20)
            float_row(everyday_tab, "opt_smart_low_confidence_threshold",
                      "Smart Rip low-confidence warning threshold:", 0.45)
            toggle_row(everyday_tab, "opt_show_temp_manager",
                       "Show temp folders at startup")
            toggle_row(everyday_tab, "opt_auto_delete_temp",
                       "Delete temp files after successful organize")
            toggle_row(everyday_tab, "opt_clean_partials_startup",
                       "Remove unfinished files at startup")
            toggle_row(everyday_tab, "opt_warn_out_of_order_episodes",
                       "Warn if episode numbers look out of order")
            toggle_row(everyday_tab, "opt_session_failure_report",
                       "Show a failure report at the end")

            section(everyday_tab, "Extras")
            choice_row(everyday_tab, "opt_extras_folder_mode",
                       "Extras folder layout:",
                       ["single", "split"])
            choice_row(everyday_tab, "opt_bonus_folder_name",
                       "Bonus folder name (Jellyfin):",
                       ["behind the scenes", "deleted scenes",
                        "featurettes", "interviews", "scenes",
                        "shorts", "clips", "other", "trailers"])

            section(validation_tab, "Rip Validation")
            toggle_row(validation_tab, "opt_scan_disc_size",
                       "Check disc size before ripping")
            toggle_row(validation_tab, "opt_file_stabilization",
                       "Wait for files to finish writing")
            toggle_row(validation_tab, "opt_check_dest_space",
                       "Check free space before moving files")
            toggle_row(validation_tab, "opt_warn_low_space",
                       "Warn when free space is low")
            number_row(validation_tab, "opt_min_rip_size_gb",
                       "Minimum accepted file size (GB):", 1)
            number_row(validation_tab, "opt_expected_size_ratio_pct",
                       "Preferred size match vs expected (%):", 70)
            number_row(validation_tab, "opt_hard_fail_ratio_pct",
                       "Hard fail below expected size (%):", 40)
            number_row(validation_tab, "opt_stabilize_timeout_seconds",
                       "File-write wait timeout in seconds:", 60)
            number_row(validation_tab, "opt_stabilize_required_polls",
                       "How many stable checks are required:", 4)
            number_row(validation_tab, "opt_move_verify_retries",
                       "Move size check retries:", 5)

            section(advanced_tab, "MakeMKV")
            number_row(advanced_tab, "opt_drive_index",
                       "Drive number for MakeMKV:", 0)
            number_row(advanced_tab, "opt_minlength_seconds",
                       "Min title length in seconds (0=off):", 0)
            toggle_row(advanced_tab, "opt_stall_detection",
                       "Warn when MakeMKV goes quiet")
            number_row(advanced_tab, "opt_stall_timeout_seconds",
                       "Quiet-time warning in seconds:", 120)
            section(advanced_tab, "Interactive Timeouts")
            toggle_row(advanced_tab, "opt_user_prompt_timeout_enabled",
                       "Let prompts auto-timeout")
            number_row(advanced_tab, "opt_user_prompt_timeout_seconds",
                       "Prompt timeout in seconds:", 300)
            toggle_row(advanced_tab, "opt_disc_swap_timeout_enabled",
                       "Let multi-disc swap wait timeout")
            number_row(advanced_tab, "opt_disc_swap_timeout_seconds",
                       "Disc swap timeout in seconds:", 300)
            toggle_row(advanced_tab, "opt_auto_retry",
                       "Retry failed titles automatically")
            number_row(advanced_tab, "opt_retry_attempts",
                       "Retry attempts per title:", 3)
            toggle_row(advanced_tab, "opt_clean_mkv_before_retry",
                       "Delete new MKV files before retry")
            section(advanced_tab, "Moving")
            toggle_row(advanced_tab, "opt_atomic_move",
                       "Use safer move method (slower)")
            toggle_row(advanced_tab, "opt_fsync",
                       "Force file sync to disk during copy")
            number_row(advanced_tab, "opt_hard_block_gb",
                       "Stop when free space is below (GB):", 20)
            section(advanced_tab, "FFmpeg")
            ffmpeg_source_mode_var = choice_map_row(
                advanced_tab,
                "opt_ffmpeg_source_mode",
                "FFmpeg source handling:",
                FFMPEG_SOURCE_MODE_LABEL_TO_VALUE,
            )
            ffmpeg_source_help_var = tk.StringVar()
            tk.Label(
                advanced_tab,
                textvariable=ffmpeg_source_help_var,
                bg="#0d1117",
                fg="#8b949e",
                font=("Segoe UI", 9),
                wraplength=760,
                justify="left",
                anchor="w",
            ).pack(fill="x", padx=16, pady=(0, 4))

            def update_ffmpeg_source_help(*_args):
                selected_label = ffmpeg_source_mode_var.get().strip()
                selected_mode = FFMPEG_SOURCE_MODE_LABEL_TO_VALUE.get(
                    selected_label,
                    FFMPEG_SOURCE_MODE_SAFE_COPY,
                )
                ffmpeg_source_help_var.set(
                    describe_ffmpeg_source_mode(selected_mode)
                )

            ffmpeg_source_mode_var.trace_add("write", update_ffmpeg_source_help)
            update_ffmpeg_source_help()
            section(advanced_tab, "Extra MakeMKV Arguments")
            text_row(
                advanced_tab,
                "opt_makemkv_global_args",
                "Extra MakeMKV args (all commands):"
            )
            text_row(
                advanced_tab,
                "opt_makemkv_info_args",
                "Extra MakeMKV args (scan commands):"
            )
            text_row(
                advanced_tab,
                "opt_makemkv_rip_args",
                "Extra MakeMKV args (rip commands):"
            )
            section(logs_tab, "Log Storage")
            number_row(
                logs_tab,
                "opt_log_cap_lines", "Max log lines kept in memory:", 300000
            )
            number_row(
                logs_tab,
                "opt_log_trim_lines", "Trim log down to this many lines:", 200000
            )
            section(logs_tab, "Debugging")
            toggle_row(logs_tab, "opt_debug_safe_int",
                       "Debug: log bad integer values")
            toggle_row(logs_tab, "opt_debug_duration",
                       "Debug: log bad duration values")

            btn_row = tk.Frame(win, bg="#0d1117")
            btn_row.pack(fill="x", padx=16, pady=12)

            def save():
                # Save expert mode toggle
                cfg['opt_expert_mode'] = expert_mode_var.get()
                try:
                    tool_validators = {
                        "makemkvcon_path": validate_makemkvcon,
                        "ffprobe_path": validate_ffprobe,
                        "ffmpeg_path": validate_ffmpeg,
                        "handbrake_path": validate_handbrake,
                    }

                    # Stage all changes before touching live config.
                    staged = {}
                    rejected_fields = []
                    for key, entry in vars_map.items():
                        vtype = entry[0]
                        var = entry[1]
                        if vtype == "str":
                            v = var.get().strip()
                            candidate = os.path.normpath(v) if v else ""
                            if key in tool_validators:
                                current = os.path.normpath(
                                    str(cfg.get(key, "")).strip()
                                )
                                if should_keep_current_tool_path(
                                    current,
                                    candidate,
                                    tool_validators[key],
                                ):
                                    _new_ok, new_err = tool_validators[key](candidate)
                                    self.controller.log(
                                        f"Settings: kept working {key}; "
                                        f"new path failed validation ({new_err})."
                                    )
                                    continue
                            staged[key] = candidate
                        elif vtype == "text":
                            staged[key] = var.get().strip()
                        elif vtype == "bool":
                            staged[key] = var.get()
                        elif vtype == "int":
                            try:
                                staged[key] = int(var.get())
                            except ValueError:
                                rejected_fields.append(key)
                        elif vtype == "float":
                            try:
                                staged[key] = float(var.get())
                            except ValueError:
                                rejected_fields.append(key)
                        elif vtype == "choice":
                            staged[key] = var.get().strip()
                        elif vtype == "choice_map":
                            selected = var.get().strip()
                            label_to_value = entry[2]
                            staged[key] = label_to_value.get(
                                selected,
                                DEFAULTS.get(key, ""),
                            )
                        elif vtype == "naming_mode":
                            selected = var.get().strip()
                            staged[key] = naming_mode_label_to_value.get(
                                selected, "timestamp"
                            )

                    # Apply staged changes atomically.
                    cfg.update(staged)
                    self.engine.cfg = cfg
                    if rejected_fields:
                        names = ", ".join(rejected_fields)
                        self.controller.log(
                            f"Settings: invalid numeric input ignored for: {names}"
                        )
                    configure_safe_int_debug(
                        cfg.get("opt_debug_safe_int", False),
                        self.controller.log
                    )
                    configure_duration_debug(
                        cfg.get("opt_debug_duration", False),
                        self.controller.log
                    )
                    save_config(cfg)
                    self.controller.log("Settings saved.")
                except Exception as e:
                    self.controller.log(f"Error saving settings: {e}")
                    messagebox.showerror(
                        "Save Failed",
                        f"Settings could not be saved:\n{e}",
                        parent=win,
                    )
                finally:
                    try:
                        win.destroy()
                    except Exception:
                        pass
                    self._settings_window = None
                    done.set()

            def cancel():
                try:
                    win.destroy()
                except Exception:
                    pass
                finally:
                    self._settings_window = None
                    done.set()

            win.protocol("WM_DELETE_WINDOW", cancel)

            tk.Button(
                btn_row, text="Save",
                bg="#238636", fg="white",
                font=("Segoe UI", 11, "bold"),
                width=12, command=save, relief="flat"
            ).pack(side="left", padx=4)
            tk.Button(
                btn_row, text="Cancel",
                bg="#21262d", fg="white",
                font=("Segoe UI", 11),
                width=12, command=cancel, relief="flat"
            ).pack(side="left", padx=4)

        def _safe_show():
            try:
                _show()
            except Exception as e:
                self._settings_window = None
                self.controller.log(f"Error opening settings: {e}")
                self.show_error("Settings Error", f"Could not open Settings:\n{e}")
                done.set()

        if threading.current_thread() is threading.main_thread():
            _safe_show()
        else:
            self.after(0, _safe_show)
            while not done.wait(timeout=0.1):
                if self.engine.abort_event.is_set():
                    return

    def start_indeterminate(self):
        def _start():
            if self.progress_bar["mode"] != "indeterminate":
                self.progress_bar.config(mode="indeterminate")
            self.progress_bar.start(12)
        self.after(0, _start)

    def stop_indeterminate(self):
        def _stop():
            self.progress_bar.stop()
            if self.progress_bar["mode"] != "determinate":
                self.progress_bar.config(mode="determinate")
            self.progress_var.set(0)
        self.after(0, _stop)

    def _init_taskbar(self):
        try:
            self._taskbar_progress = _TaskbarProgress(self.winfo_id())
        except Exception:
            self._taskbar_progress = None

    def _notify_complete(self, title="JellyRip", message="Rip complete."):
        """Send a Windows toast notification and play a completion beep."""
        if sys.platform != "win32":
            return
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        try:
            # Pass title and message as process arguments ($args[0], $args[1])
            # so no string escaping is needed and disc metadata cannot inject PS code.
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager,"
                " Windows.UI.Notifications, ContentType=WindowsRuntime]"
                " | Out-Null;"
                "$tpl = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                "$x = [Windows.UI.Notifications.ToastNotificationManager]"
                "::GetTemplateContent($tpl);"
                "$x.GetElementsByTagName('text')[0].AppendChild("
                "$x.CreateTextNode($args[0])) | Out-Null;"
                "$x.GetElementsByTagName('text')[1].AppendChild("
                "$x.CreateTextNode($args[1])) | Out-Null;"
                "$n = [Windows.UI.Notifications.ToastNotification]::new($x);"
                "[Windows.UI.Notifications.ToastNotificationManager]"
                "::CreateToastNotifier('JellyRip.App.1').Show($n);"
            )
            _ps = (
                shutil.which("powershell")
                or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            )
            subprocess.Popen(
                [_ps, "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps,
                 title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                **({"creationflags": 0x08000000} if sys.platform == "win32" else {}),
            )
        except Exception:
            pass

    def set_progress(self, value):
        def _update():
            self.progress_var.set(value if value is not None and value >= 0 else 0)
            if self._taskbar_progress:
                if value is None or value < 0:
                    self._taskbar_progress.clear()
                else:
                    self._taskbar_progress.set_value(int(value), 100)
        self.after(0, _update)

    def set_status(self, msg):
        self.after(0, lambda: self.status_var.set(msg))

    def append_log(self, msg):
        self.message_queue.put(msg)

    def process_queue(self):
        # Defensive: skip if log_text is not yet initialized
        if not hasattr(self, "log_text"):
            self.after(100, self.process_queue)
            return
        # Batch process log messages for better performance.
        # Collect up to 100 messages, then insert all at once
        # instead of state on/off 100 times.
        messages = []
        for _ in range(100):
            if self.message_queue.empty():
                break
            try:
                messages.append(self.message_queue.get_nowait())
            except queue_module.Empty:
                break
        if messages:
            with self._log_widget_lock:
                self.log_text.config(state="normal")
                batch_text = "\n".join(messages) + "\n"
                self.log_text.insert("end", batch_text)
                # Trim widget (same cap/trim as _append_log_text_main).
                line_count = int(self.log_text.index("end").split(".")[0]) - 1
                cap = int(self.cfg.get("opt_log_cap_lines", 300000))
                if line_count > cap:
                    trim = int(self.cfg.get("opt_log_trim_lines", 200000))
                    self.log_text.delete("1.0", f"{line_count - trim}.0")
                # Only auto-scroll if user is already near the bottom.
                visible_end = self.log_text.yview()[1]
                if visible_end > 0.95:
                    self.log_text.see("end")
                self.log_text.config(state="disabled")
        self.after(100, self.process_queue)

    def disable_buttons(self):
        for btn in self.mode_buttons.values():
            btn.config(state="disabled")
        if hasattr(self, "settings_btn"):
            self.settings_btn.config(state="disabled")
        if hasattr(self, "update_btn"):
            self.update_btn.config(state="disabled")
        if hasattr(self, "abort_btn"):
            self.abort_btn.config(state="normal")  # Keep abort enabled during tasks

    def enable_buttons(self):
        for btn in self.mode_buttons.values():
            btn.config(state="normal")
        if hasattr(self, "settings_btn"):
            self.settings_btn.config(state="normal")
        if hasattr(self, "update_btn"):
            self.update_btn.config(state="normal")
        if hasattr(self, "abort_btn"):
            self.abort_btn.config(state="disabled")  # Disable abort when idle

    def request_abort(self):
        """Abort immediately — no confirmation dialog required."""
        self.controller.log("ABORT REQUESTED BY USER")
        self.set_status("Aborting...")
        self.abort_btn.config(state="disabled")
        self.engine.abort()

    def on_close(self):
        if messagebox.askokcancel(
            "Exit", "Close Jellyfin Raw Ripper?", parent=self
        ):
            self.engine.abort()
            # Attempt to join any running rip thread
            if self.rip_thread and self.rip_thread.is_alive():
                try:
                    self.rip_thread.join(timeout=3)
                except Exception:
                    pass
            self.destroy()
            # As a last resort, force kill the process (kills all threads/subprocesses)
            import os
            os._exit(0)

    def _pick_movie_mode(self):
        choice = self._run_on_main(
            lambda: messagebox.askyesnocancel(
                "Movie Mode",
                "Use Smart Rip for this movie disc?\n\n"
                "Yes = auto-pick main feature\n"
                "No = manual title selection\n"
                "Cancel = manual title selection",
                parent=self,
            )
        )
        if choice is None:
            self.controller.log(
                "Movie mode prompt closed — defaulting to manual selection."
            )
            return self.controller.run_movie_disc
        if choice:
            return self.controller.run_smart_rip
        return self.controller.run_movie_disc

    def start_task(self, mode):
        if self.rip_thread and self.rip_thread.is_alive():
            messagebox.showwarning(
                "Busy",
                "Wait for current operation to finish.",
                parent=self
            )
            return

        ok, msg = self.engine.validate_tools()
        if not ok:
            messagebox.showerror(
                "Configuration Error", msg, parent=self
            )
            return

        src = getattr(self.engine, "_ffprobe_source", "")
        if src:
            self.controller.log(f"ffprobe resolved via: {src}")

        temp_folder = os.path.normpath(
            self.cfg.get("temp_folder", DEFAULTS["temp_folder"])
        )
        _safe_mode_keys = (
            "opt_file_stabilization",
            "opt_stabilize_required_polls",
            "opt_stabilize_timeout_seconds",
            "opt_move_verify_retries",
            "opt_expected_size_ratio_pct",
        )
        _safe_mode_snapshot = {k: self.cfg.get(k) for k in _safe_mode_keys}
        if self.cfg.get("opt_safe_mode", True):
            self.cfg["opt_file_stabilization"] = True
            self.cfg["opt_stabilize_required_polls"] = max(
                4, int(self.cfg.get("opt_stabilize_required_polls", 4))
            )
            self.cfg["opt_stabilize_timeout_seconds"] = max(
                90, int(self.cfg.get("opt_stabilize_timeout_seconds", 60))
            )
            self.cfg["opt_move_verify_retries"] = max(
                5, int(self.cfg.get("opt_move_verify_retries", 5))
            )
            self.cfg["opt_expected_size_ratio_pct"] = max(
                50, int(self.cfg.get("opt_expected_size_ratio_pct", 70))
            )

        if (not self.cfg.get("opt_first_run_done", False) and
                is_network_path(temp_folder)):
            messagebox.showwarning(
                "Network Temp Folder",
                "Your temp folder appears to be on a network/mapped "
                "drive. Network storage is slower and may cause "
                "incomplete rips. Local temp storage is recommended.\n\n"
                f"Current temp folder:\n{temp_folder}",
                parent=self
            )

        if not self.cfg.get("opt_first_run_done", False):
            self.cfg["opt_first_run_done"] = True
            self.engine.cfg["opt_first_run_done"] = True
            save_config(self.cfg)

        self.engine.reset_abort()
        self.controller.session_log          = []
        self.controller.session_report       = []
        self.controller.start_time           = datetime.now()
        self.controller.global_extra_counter = 1
        self.disable_buttons()
        self.set_progress(0)

        targets = {
            "t":  self.controller.run_tv_disc,
            "m":  self._pick_movie_mode,
            "sr": self.controller.run_smart_rip,
            "d":  self.controller.run_dump_all,
            "i":  self.controller.run_organize,
        }
        target = targets.get(mode, self.controller.run_organize)
        needs_pick = mode == "m"

        def task_wrapper():
            _success = False
            try:
                # Important: mode pickers use ask_yesno(), which schedules UI
                # work on the main thread and waits from the caller thread.
                # Resolve picker targets here (background thread), not in
                # start_task() on the main thread, to avoid UI deadlocks.
                fn = target() if needs_pick else target
                # If abort was requested during the mode picker prompt,
                # don't start the rip — just bail out cleanly.
                if self.engine.abort_event.is_set():
                    return
                if fn is None:
                    self.set_status("Ready")
                    return
                fn()
                _success = True
            except Exception as e:
                self.controller.log(f"Unhandled error: {e}")
                self.after(0, lambda msg=str(e): self._notify_complete(
                    "JellyRip — Error", f"Rip failed: {msg}"
                ))
            finally:
                # Restore safe-mode-overridden config keys so Settings shows
                # the user's actual values, not the enforced minimums.
                for k, v in _safe_mode_snapshot.items():
                    if v is None:
                        self.cfg.pop(k, None)
                    else:
                        self.cfg[k] = v
                self.stop_indeterminate()
                self.after(0, self.enable_buttons)
                self.set_status("Ready")
                if not self.engine.abort_event.is_set():
                    # Determine session result
                    from utils.session_result import normalize_session_result
                    abort = self.engine.abort_event.is_set()
                    failed_titles = getattr(self.controller, "failed_titles", [])
                    files = getattr(self.controller, "session_files", [])
                    valid_files = getattr(self.controller, "valid_files", files)
                    is_full_success = normalize_session_result(abort, failed_titles, files, valid_files)
                    is_partial = (not is_full_success) and bool(files)
                    if is_full_success:
                        self.after(0, lambda: self._notify_complete(
                            "JellyRip", "Rip complete!"
                        ))
                    elif is_partial:
                        def handle_partial():
                            accept = self.ask_accept_partial()
                            if accept:
                                self._notify_complete(
                                    "JellyRip", "Partial rip accepted. Files and metadata kept."
                                )
                            else:
                                # Delete session folder and metadata
                                session_dir = getattr(self.controller, "session_dir", None)
                                if session_dir and os.path.exists(session_dir):
                                    import shutil
                                    try:
                                        shutil.rmtree(session_dir)
                                        self._notify_complete(
                                            "JellyRip", "Partial rip deleted. Session and files removed."
                                        )
                                    except Exception as e:
                                        self._notify_complete(
                                            "JellyRip", f"Error deleting session: {e}"
                                        )
                                else:
                                    self._notify_complete(
                                        "JellyRip", "Session directory not found. Nothing deleted."
                                    )
                        self.after(0, handle_partial)
                    else:
                        self.after(0, lambda: self._notify_complete(
                            "JellyRip", "Rip failed. No files kept."
                        ))

        self.rip_thread = threading.Thread(
            target=task_wrapper, daemon=True
        )
        self.rip_thread.start()


if __name__ == "__main__":
    # Example: direct AppConfig construction for testing or alternate entry
    # config = AppConfig(source="/path/to/makemkvcon", output="/path/to/ffprobe", quality="high")
    config = load_config()
    app = JellyRipperGUI(config)
    app.mainloop()

__all__ = ["JellyRipperGUI"]
