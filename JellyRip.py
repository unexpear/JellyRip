"""Compatibility shim exposing the split JellyRip modules through the legacy import path.

⚠️  DEPRECATED: This module is maintained only for backward compatibility.
    Direct imports from the subpackages (config, controller, engine, utils, shared) are preferred.
    New code should use main.py as the entry point, not this shim.
    This module will be removed in a future version.
"""

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
from controller.naming import (
    build_fallback_title,
    build_naming_preview_text,
    normalize_naming_mode,
    resolve_naming_mode,
)

from utils.helpers import (
    clean_name,
    get_available_drives,
    is_network_path,
    make_rip_folder_name,
    make_temp_title,
)
from utils.parsing import (
    parse_cli_args,
    parse_duration_to_seconds,
    parse_episode_names,
    parse_ordered_titles,
    parse_size_to_bytes,
    safe_int,
)
from utils.scoring import (
    choose_best_title,
    format_audio_summary,
    score_title,
)
from utils.media import select_largest_file
from config import (
    load_config,
    resolve_ffprobe,
    save_config,
)


# ==========================================
# LAYER 1 — ENGINE
# ==========================================

from engine.ripper_engine import RipperEngine

from controller.controller import RipperController

# JellyRipperGUI (the tkinter main-window class) was retired in
# Phase 3h (2026-05-04). The PySide6 UI lives in ``gui_qt/``. New code
# should import directly from ``gui_qt.app`` (e.g. ``run_qt_app``)
# rather than going through this compatibility shim.
#
# The legacy attribute name is no longer re-exported.  If any
# consumer outside this repo still referenced ``JellyRip.JellyRipperGUI``
# they need to migrate to the Qt path.

__all__ = [
    "CONFIG_FILE",
    "DEFAULTS",
    "RIP_ATTEMPT_FLAGS",
    "RipperController",
    "RipperEngine",
    "__version__",
    "_duration_debug_warn",
    "_safe_int_debug_warn",
    "build_fallback_title",
    "build_naming_preview_text",
    "choose_best_title",
    "clean_name",
    "configure_duration_debug",
    "configure_safe_int_debug",
    "format_audio_summary",
    "get_available_drives",
    "get_config_dir",
    "is_network_path",
    "load_config",
    "make_rip_folder_name",
    "make_temp_title",
    "normalize_naming_mode",
    "parse_cli_args",
    "parse_duration_to_seconds",
    "parse_episode_names",
    "parse_ordered_titles",
    "parse_size_to_bytes",
    "resolve_ffprobe",
    "resolve_naming_mode",
    "safe_int",
    "save_config",
    "score_title",
    "select_largest_file",
]


# -----------------------------------------------------------------------------
# Project file map (quick navigation when chat history is unavailable)
# -----------------------------------------------------------------------------
# Main entrypoint: main.py
# Legacy compatibility entrypoint: JellyRip.py
# Main GUI entrypoint: gui_qt/main_window.py (Qt) — retired tkinter
# implementation lived at gui/main_window.py until Phase 3h, 2026-05-04
# Workflow/controller logic: controller/controller.py
# Disc + file operations engine: engine/ripper_engine.py
# Config load/save and defaults bridge: config.py
# Shared defaults/runtime primitives: shared/runtime.py
# Utility exports: utils/__init__.py
# Session state machine: utils/state_machine.py
# Fallback policy gateway: utils/fallback.py
# File selection helpers: utils/media.py
# Behavioral tests: tests/test_behavior_guards.py
