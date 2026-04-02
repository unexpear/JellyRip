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
import tempfile
import threading
import time
import urllib.error
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk


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
    build_fallback_title,
    build_naming_preview_text,
    configure_duration_debug,
    configure_safe_int_debug,
    get_config_dir,
    normalize_naming_mode,
    resolve_naming_mode,
)

from config import (
    load_config,
    save_config,
    should_keep_current_tool_path,
    validate_ffprobe,
    validate_makemkvcon,
)
from controller.controller import RipperController
from engine.ripper_engine import RipperEngine
from utils.helpers import (
    get_available_drives,
    is_network_path,
    make_rip_folder_name,
)
from utils.scoring import choose_best_title, format_audio_summary
from utils.updater import (
    download_asset,
    fetch_latest_release,
    is_newer_version,
    sha256_file,
    verify_downloaded_update,
)


class JellyRipperGUI(tk.Tk):
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
        self.after(100, self.process_queue)
        self._taskbar_progress = None
        self.after(500, self._init_taskbar)

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
        buttons_row1 = [
            ("📀  Rip TV Show Disc",       "t",  "#238636", 20),
            ("🎬  Rip Movie Disc",          "m",  "#238636", 20),
            ("💾  Dump All Titles",         "d",  "#1f6feb", 18),
            ("📁  Organize Existing MKVs", "i",  "#6e40c9", 22),
        ]
        for text, mode, color, width in buttons_row1:
            btn = tk.Button(
                mode_frame, text=text,
                command=lambda m=mode: self.start_task(m),
                bg=color, fg="white",
                font=("Segoe UI", 11),
                width=width, height=2, relief="flat"
            )
            btn.pack(side="left", padx=5)
            self.mode_buttons[mode] = btn

        util_frame = tk.Frame(self, bg=BG)
        util_frame.pack(fill="x", padx=20)
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

        bottom = tk.Frame(self, bg="#161b22")
        bottom.pack(fill="x", pady=8, padx=20)
        self.abort_btn = tk.Button(
            bottom, text="ABORT SESSION",
            bg="#c94b4b", fg="white",
            font=("Segoe UI", 12, "bold"),
            width=20, command=self.request_abort, relief="flat"
        )
        self.abort_btn.pack(side="right")

        # Do not auto-probe optical drives on startup; probing can spin up
        # physical media drives and stall on some systems. Users can refresh
        # explicitly with the Refresh button.

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
        """Launch downloaded update package and close app for file replacement."""
        try:
            self.controller.log(
                "Launching installer — a UAC permission prompt may appear."
            )
            self.show_info(
                "Update Ready",
                "The installer is starting.\n\n"
                "A UAC permission prompt may appear.\n"
                "JellyRip will now close so files can be replaced."
            )
            self.engine.abort()
            self.after(500, self.destroy)
            os.startfile(downloaded_path)
        except Exception as e:
            self.controller.log(f"Could not launch update package: {e}")
            self.show_error(
                "Update Downloaded",
                "Downloaded update package but could not launch it.\n\n"
                f"Run this file manually:\n{downloaded_path}"
            )

    def check_for_updates(self):
        """Check GitHub releases for a newer version and offer download."""
        self.set_status("Checking for updates...")
        self.controller.log("Checking GitHub Releases for updates...")
        if hasattr(self, "update_btn"):
            self.update_btn.config(state="disabled")

        def _finish_ready():
            self.set_status("Ready")
            if hasattr(self, "update_btn"):
                self.update_btn.config(state="normal")

        def worker():
            try:
                release = fetch_latest_release("unexpear/JellyRip")
            except urllib.error.URLError as e:
                self.controller.log(f"Update check failed: {e}")
                self.after(
                    0,
                    lambda: self.show_error(
                        "Update Check Failed",
                        "Could not reach GitHub Releases right now."
                    )
                )
                self.after(0, _finish_ready)
                return
            except Exception as e:
                self.controller.log(f"Update check failed: {e}")
                self.after(
                    0,
                    lambda: self.show_error(
                        "Update Check Failed",
                        f"Unexpected error while checking updates:\n{e}"
                    )
                )
                self.after(0, _finish_ready)
                return

            latest = release.get("version") or ""
            if not latest:
                self.controller.log("Latest release has no usable version tag.")
                self.after(
                    0,
                    lambda: self.show_error(
                        "Update Check Failed",
                        "Latest release metadata did not include a version."
                    )
                )
                self.after(0, _finish_ready)
                return

            if not is_newer_version(__version__, latest):
                self.controller.log(
                    f"Already up to date (current: {__version__}, latest: {latest})."
                )
                self.after(
                    0,
                    lambda: self.show_info(
                        "No Update Available",
                        f"You are already on v{__version__}."
                    )
                )
                self.after(0, _finish_ready)
                return

            self.controller.log(
                f"Update available: v{latest} (current: v{__version__})"
            )
            wants_update = self.ask_yesno(
                f"Update available: v{latest} (current: v{__version__}).\n"
                "Download and install now?"
            )
            if not wants_update:
                self.controller.log("Update deferred by user.")
                self.after(0, _finish_ready)
                return

            asset_url = release.get("asset_url") or ""
            asset_name = release.get("asset_name") or "JellyRip.exe"
            page_url = release.get("html_url") or ""

            if not asset_url:
                self.controller.log("No downloadable asset found in latest release.")
                if page_url:
                    webbrowser.open(page_url)
                self.after(0, _finish_ready)
                return

            # Use a unique per-download temp directory to prevent TOCTOU
            # attacks via the predictable JellyRipUpdate/ fixed path.
            update_dir = tempfile.mkdtemp(prefix="JellyRipUpdate_")
            destination = os.path.join(update_dir, asset_name)

            self.set_status("Downloading update...")
            self.controller.log(f"Downloading update asset: {asset_name}")

            last_logged_mb = {"mb": -1}

            def on_progress(written, total):
                mb = written // (1024 * 1024)
                if mb == last_logged_mb["mb"]:
                    return
                last_logged_mb["mb"] = mb
                if total > 0:
                    pct = int((written / total) * 100)
                    self.controller.log(
                        f"Update download: {pct}% ({mb} MB)"
                    )
                else:
                    self.controller.log(f"Update download: {mb} MB")

            try:
                download_asset(
                    asset_url, destination, on_progress,
                    abort_event=self.engine.abort_event,
                )
            except Exception as e:
                self.controller.log(f"Update download failed: {e}")
                shutil.rmtree(update_dir, ignore_errors=True)
                self.after(
                    0,
                    lambda: self.show_error(
                        "Update Download Failed",
                        f"Could not download update package:\n{e}"
                    )
                )
                self.after(0, _finish_ready)
                return

            try:
                digest = sha256_file(destination)
                self.controller.log(f"Update SHA256: {digest}")
            except Exception as e:
                self.controller.log(f"Could not compute update SHA256: {e}")

            require_sig = bool(
                self.cfg.get("opt_update_require_signature", True)
            )
            pinned_thumbprint = str(
                self.cfg.get("opt_update_signer_thumbprint", "")
            )
            if require_sig and not pinned_thumbprint.strip():
                self.controller.log(
                    "Update blocked: signature pinning is enabled but "
                    "opt_update_signer_thumbprint is empty."
                )
                shutil.rmtree(update_dir, ignore_errors=True)
                self.after(
                    0,
                    lambda: self.show_error(
                        "Update Blocked",
                        "Signature verification is enabled but no signer "
                        "thumbprint is configured.\n\n"
                        "Set opt_update_signer_thumbprint in Settings to "
                        "your release certificate thumbprint before using "
                        "auto-update.",
                    ),
                )
                self.after(0, _finish_ready)
                return
            ok, verify_msg = verify_downloaded_update(
                destination,
                require_signature=require_sig,
                required_thumbprint=pinned_thumbprint,
            )
            self.controller.log(verify_msg)
            if not ok:
                shutil.rmtree(update_dir, ignore_errors=True)
                self.after(
                    0,
                    lambda: self.show_error(
                        "Update Blocked",
                        "Downloaded update failed signature verification.\n\n"
                        "The package will not be launched automatically."
                    )
                )
                self.after(0, _finish_ready)
                return

            self.controller.log(f"Update downloaded to: {destination}")
            self.after(0, _finish_ready)
            self.after(0, lambda: self._launch_downloaded_update(destination))

        threading.Thread(target=worker, daemon=True).start()

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
        self._input_result = val if val else None
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
                    self.after(0, self._hide_input_bar)
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
        timeout_seconds = self._get_user_prompt_timeout_seconds()
        start = time.time()

        def _show():
            ts = datetime.now().strftime("%H:%M:%S")
            self._append_log_text_main(f"[{ts}] {prompt}", "prompt")

            btn_frame = tk.Frame(self.log_text, bg="#161b22")

            def yes():
                if done.is_set() or self.engine.abort_event.is_set():
                    return
                result[0] = True
                try:
                    btn_frame.destroy()
                except Exception:
                    pass
                self._append_log_text_main(
                    f"[{datetime.now().strftime('%H:%M:%S')}] → Yes",
                    "answer",
                )
                done.set()

            def no():
                if done.is_set() or self.engine.abort_event.is_set():
                    return
                result[0] = False
                try:
                    btn_frame.destroy()
                except Exception:
                    pass
                self._append_log_text_main(
                    f"[{datetime.now().strftime('%H:%M:%S')}] → No",
                    "answer",
                )
                done.set()

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
                        def _cleanup():
                            if done.is_set():
                                return
                            try:
                                btn_frame.destroy()
                            except Exception:
                                pass
                            result[0] = False
                            done.set()
                        self.after(0, _cleanup)
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
                return False
        return result[0] if result[0] is not None else False

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
        timeout_seconds = self._get_user_prompt_timeout_seconds()
        start = time.time()

        def _show():
            self.log_text.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.log_text.insert(
                "end", f"[{ts}] {prompt}\n", "prompt"
            )

            btn_frame = tk.Frame(self.log_text, bg="#161b22")

            def choose_retry():
                result[0] = "retry"
                _finish(f"→ {retry_text}")

            def choose_bypass():
                result[0] = "bypass"
                _finish(f"→ {bypass_text}")

            def choose_stop():
                result[0] = "stop"
                _finish(f"→ {stop_text}")

            def _finish(answer_text):
                try:
                    btn_frame.destroy()
                except Exception:
                    pass
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
                        def _cleanup():
                            try:
                                btn_frame.destroy()
                            except Exception:
                                pass
                            result[0] = "stop"
                            done.set()
                        self.after(0, _cleanup)
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
                    id_map[int(iid.split("_")[1])]["size_bytes"]
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

            section(paths_tab, "Apps")
            path_row(paths_tab, "makemkvcon_path", "MakeMKV app")
            path_row(paths_tab, "ffprobe_path",    "ffmpeg / ffprobe folder")
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
                try:
                    tool_validators = {
                        "makemkvcon_path": validate_makemkvcon,
                        "ffprobe_path": validate_ffprobe,
                    }

                    # Stage all changes before touching live config.
                    staged = {}
                    for key, (vtype, var) in vars_map.items():
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
                                pass
                        elif vtype == "float":
                            try:
                                staged[key] = float(var.get())
                            except ValueError:
                                pass
                        elif vtype == "choice":
                            staged[key] = var.get().strip()
                        elif vtype == "naming_mode":
                            selected = var.get().strip()
                            staged[key] = naming_mode_label_to_value.get(
                                selected, "timestamp"
                            )

                    # Apply staged changes atomically.
                    cfg.update(staged)
                    self.engine.cfg = cfg
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
            done.wait()

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
            # Escape for safe PS string interpolation.
            safe_title = title.replace('"', '`"').replace("'", "''")
            safe_msg = message.replace('"', '`"').replace("'", "''")
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager,"
                " Windows.UI.Notifications, ContentType=WindowsRuntime]"
                " | Out-Null;"
                "$t = [Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                "$x = [Windows.UI.Notifications.ToastNotificationManager]"
                "::GetTemplateContent($t);"
                f'$x.GetElementsByTagName("text")[0].AppendChild('
                f'$x.CreateTextNode("{safe_title}")) | Out-Null;'
                f'$x.GetElementsByTagName("text")[1].AppendChild('
                f'$x.CreateTextNode("{safe_msg}")) | Out-Null;'
                "$n = [Windows.UI.Notifications.ToastNotification]::new($x);"
                '[Windows.UI.Notifications.ToastNotificationManager]'
                '::CreateToastNotifier("JellyRip.App.1").Show($n);'
            )
            _ps = (
                shutil.which("powershell")
                or r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            )
            subprocess.Popen(
                [_ps, "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
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

    def enable_buttons(self):
        for btn in self.mode_buttons.values():
            btn.config(state="normal")
        if hasattr(self, "settings_btn"):
            self.settings_btn.config(state="normal")
        if hasattr(self, "update_btn"):
            self.update_btn.config(state="normal")

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
            self.destroy()

    def _pick_movie_mode(self):
        if self.ask_yesno(
            "Use Smart Rip for this movie disc?\n\n"
            "Yes = auto-pick main feature\n"
            "No = manual title selection"
        ):
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
            self.log(f"ffprobe resolved via: {src}")

        temp_folder = os.path.normpath(
            self.cfg.get("temp_folder", DEFAULTS["temp_folder"])
        )
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
        self.abort_btn.config(state="normal")
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
                fn()
                _success = True
            except Exception as e:
                self.controller.log(f"Unhandled error: {e}")
                self.after(0, lambda msg=str(e): self._notify_complete(
                    "JellyRip — Error", f"Rip failed: {msg}"
                ))
            finally:
                self.stop_indeterminate()
                self.after(0, self.enable_buttons)
                self.after(
                    0,
                    lambda: self.abort_btn.config(state="normal")
                )
                self.set_status("Ready")
                if _success and not self.engine.abort_event.is_set():
                    self.after(0, lambda: self._notify_complete(
                        "JellyRip", "Rip complete!"
                    ))

        self.rip_thread = threading.Thread(
            target=task_wrapper, daemon=True
        )
        self.rip_thread.start()


if __name__ == "__main__":
    cfg = load_config()
    app = JellyRipperGUI(cfg)
    app.mainloop()

__all__ = ["JellyRipperGUI"]
