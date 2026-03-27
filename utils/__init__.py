"""Utility exports for parsing/scoring/helper functions."""

from .helpers import (
    clean_name,
    get_available_drives,
    is_network_path,
    make_rip_folder_name,
    make_temp_title,
)
from .parsing import (
    parse_cli_args,
    parse_duration_to_seconds,
    parse_episode_names,
    parse_ordered_titles,
    parse_size_to_bytes,
    safe_int,
)
from .scoring import choose_best_title, format_audio_summary, score_title
from .updater import (
    download_asset,
    fetch_latest_release,
    get_authenticode_signature,
    is_newer_version,
    sha256_file,
    verify_downloaded_update,
)

__all__ = [
    "clean_name",
    "get_available_drives",
    "is_network_path",
    "make_rip_folder_name",
    "make_temp_title",
    "parse_cli_args",
    "parse_duration_to_seconds",
    "parse_episode_names",
    "parse_ordered_titles",
    "parse_size_to_bytes",
    "safe_int",
    "choose_best_title",
    "format_audio_summary",
    "score_title",
    "download_asset",
    "fetch_latest_release",
    "get_authenticode_signature",
    "is_newer_version",
    "sha256_file",
    "verify_downloaded_update",
]
