"""Compatibility shim exposing the split JellyRip modules through the legacy import path."""

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

from utils.helpers import (  # pyright: ignore[reportMissingImports]
    clean_name,
    get_available_drives,
    is_network_path,
    make_rip_folder_name,
    make_temp_title,
)
from utils.parsing import (  # pyright: ignore[reportMissingImports]
    parse_cli_args,
    parse_duration_to_seconds,
    parse_episode_names,
    parse_ordered_titles,
    parse_size_to_bytes,
    safe_int,
)
from utils.scoring import (  # pyright: ignore[reportMissingImports]
    choose_best_title,
    format_audio_summary,
    score_title,
)
from utils.media import select_largest_file  # pyright: ignore[reportMissingImports]
from config import (  # pyright: ignore[reportMissingImports]
    load_config,
    resolve_ffprobe,
    save_config,
)


# ==========================================
# LAYER 1 — ENGINE
# ==========================================

from engine.ripper_engine import RipperEngine  # pyright: ignore[reportMissingImports]

from controller.controller import RipperController  # pyright: ignore[reportMissingImports]

from gui.main_window import JellyRipperGUI  # pyright: ignore[reportMissingImports]

__all__ = [
    "CONFIG_FILE",
    "DEFAULTS",
    "JellyRipperGUI",
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
