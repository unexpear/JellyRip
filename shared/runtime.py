"""Shared runtime primitives used by split modules and the compatibility shim."""

import glob
import json
import os
import platform
import queue as queue_module
import re
import shlex
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from controller.naming import (
    build_fallback_title,
    build_naming_preview_text,
    normalize_naming_mode,
    resolve_naming_mode,
)

__version__ = "1.0.6"


def get_config_dir():
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif system == "Darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get(
            "XDG_CONFIG_HOME", os.path.expanduser("~/.config")
        )
    config_dir = os.path.join(base, "JellyRip")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


CONFIG_FILE = os.path.join(get_config_dir(), "config.json")

DEFAULTS = {
    "makemkvcon_path": r"C:\Program Files (x86)\MakeMKV\makemkvcon.exe",
    "ffprobe_path": r"C:\Program Files\HandBrake\ffprobe.exe",
    "temp_folder": r"C:\Temp",
    "tv_folder": r"C:\Media\TV Shows",
    "movies_folder": r"C:\Media\Movies",
    "log_file": os.path.expanduser("~/Downloads/rip_log.txt"),
    "opt_drive_index": 0,
    "opt_safe_mode": True,
    "opt_first_run_done": False,
    "opt_scan_disc_size": True,
    "opt_confirm_before_rip": True,
    "opt_clean_mkv_before_retry": True,
    "opt_stall_detection": True,
    "opt_stall_timeout_seconds": 120,
    "opt_file_stabilization": True,
    "opt_stabilize_timeout_seconds": 60,
    "opt_stabilize_required_polls": 4,
    "opt_min_rip_size_gb": 1,
    "opt_expected_size_ratio_pct": 70,
    "opt_hard_fail_ratio_pct": 40,
    "opt_smart_low_confidence_threshold": 0.45,
    "opt_move_verify_retries": 5,
    "opt_auto_retry": True,
    "opt_retry_attempts": 3,
    "opt_check_dest_space": True,
    "opt_confirm_before_move": True,
    "opt_atomic_move": True,
    "opt_fsync": True,
    "opt_show_temp_manager": True,
    "opt_auto_delete_temp": True,
    "opt_clean_partials_startup": True,
    "opt_warn_low_space": True,
    "opt_hard_block_gb": 20,
    "opt_warn_out_of_order_episodes": True,
    "opt_debug_safe_int": False,
    "opt_debug_duration": False,
    "opt_debug_state": False,
    "opt_debug_state_json": False,
    "opt_strict_mode": False,
    "opt_session_failure_report": True,
    "opt_log_cap_lines": 300000,
    "opt_log_trim_lines": 200000,
    "opt_smart_rip_mode": False,
    "opt_smart_min_minutes": 20,
    "opt_naming_mode": "timestamp",
    "opt_makemkv_global_args": "",
    "opt_makemkv_info_args": "",
    "opt_makemkv_rip_args": "",
    "opt_update_require_signature": True,
    "opt_update_signer_thumbprint": "",
}

RIP_ATTEMPT_FLAGS = [
    ["--cache=1024"],
    ["--noscan", "--cache=1024"],
    ["--noscan", "--directio=true", "--cache=512"],
]


_SAFE_INT_DEBUG_ENABLED = False
_SAFE_INT_DEBUG_LOG_FN = None
_SAFE_INT_WARNED_VALUES = set()
_SAFE_INT_WARNED_LIMIT_REACHED = False
_SAFE_INT_WARN_MAX_UNIQUE = 50

_DURATION_DEBUG_ENABLED = False
_DURATION_DEBUG_LOG_FN = None
_DURATION_WARNED_VALUES = set()
_DURATION_WARNED_LIMIT_REACHED = False
_DURATION_WARN_MAX_UNIQUE = 50


def configure_safe_int_debug(enabled=False, log_fn=None):
    global _SAFE_INT_DEBUG_ENABLED
    global _SAFE_INT_DEBUG_LOG_FN
    _SAFE_INT_DEBUG_ENABLED = bool(enabled)
    _SAFE_INT_DEBUG_LOG_FN = log_fn


def configure_duration_debug(enabled=False, log_fn=None):
    global _DURATION_DEBUG_ENABLED
    global _DURATION_DEBUG_LOG_FN
    _DURATION_DEBUG_ENABLED = bool(enabled)
    _DURATION_DEBUG_LOG_FN = log_fn


def _safe_int_debug_warn(val):
    global _SAFE_INT_WARNED_LIMIT_REACHED

    if not _SAFE_INT_DEBUG_ENABLED:
        return

    token = str(val).strip()
    if len(token) > 80:
        token = token[:77] + "..."
    key = token or "<empty>"

    if key in _SAFE_INT_WARNED_VALUES:
        return

    if len(_SAFE_INT_WARNED_VALUES) >= _SAFE_INT_WARN_MAX_UNIQUE:
        if not _SAFE_INT_WARNED_LIMIT_REACHED:
            _SAFE_INT_WARNED_LIMIT_REACHED = True
            msg = (
                "DEBUG safe_int: warning limit reached; "
                "suppressing additional unique parse warnings."
            )
            if _SAFE_INT_DEBUG_LOG_FN:
                _SAFE_INT_DEBUG_LOG_FN(msg)
            else:
                print(msg)
        return

    _SAFE_INT_WARNED_VALUES.add(key)
    msg = f"DEBUG safe_int: could not parse {key!r}; defaulting to 0"
    if _SAFE_INT_DEBUG_LOG_FN:
        _SAFE_INT_DEBUG_LOG_FN(msg)
    else:
        print(msg)


def _duration_debug_warn(val):
    global _DURATION_WARNED_LIMIT_REACHED

    if not _DURATION_DEBUG_ENABLED:
        return

    token = str(val).strip()
    if len(token) > 80:
        token = token[:77] + "..."
    key = token or "<empty>"

    if key in _DURATION_WARNED_VALUES:
        return

    if len(_DURATION_WARNED_VALUES) >= _DURATION_WARN_MAX_UNIQUE:
        if not _DURATION_WARNED_LIMIT_REACHED:
            _DURATION_WARNED_LIMIT_REACHED = True
            msg = (
                "DEBUG duration: warning limit reached; "
                "suppressing additional unique parse warnings."
            )
            if _DURATION_DEBUG_LOG_FN:
                _DURATION_DEBUG_LOG_FN(msg)
            else:
                print(msg)
        return

    _DURATION_WARNED_VALUES.add(key)
    msg = f"DEBUG duration: could not parse {key!r}; defaulting to 0"
    if _DURATION_DEBUG_LOG_FN:
        _DURATION_DEBUG_LOG_FN(msg)
    else:
        print(msg)


__all__ = [
    "CONFIG_FILE",
    "DEFAULTS",
    "RIP_ATTEMPT_FLAGS",
    "ThreadPoolExecutor",
    "__version__",
    "_duration_debug_warn",
    "_safe_int_debug_warn",
    "as_completed",
    "build_fallback_title",
    "build_naming_preview_text",
    "configure_duration_debug",
    "configure_safe_int_debug",
    "datetime",
    "filedialog",
    "get_config_dir",
    "glob",
    "json",
    "messagebox",
    "normalize_naming_mode",
    "os",
    "platform",
    "queue_module",
    "re",
    "resolve_naming_mode",
    "scrolledtext",
    "shlex",
    "shutil",
    "subprocess",
    "threading",
    "time",
    "tk",
    "ttk",
]