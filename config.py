"""Configuration entrypoint for package-style imports."""

from JellyRip import (  # pyright: ignore[reportMissingImports]
    CONFIG_FILE,
    DEFAULTS,
    get_config_dir,
    load_config,
    resolve_ffprobe,
    save_config,
)

__all__ = [
    "CONFIG_FILE",
    "DEFAULTS",
    "get_config_dir",
    "load_config",
    "resolve_ffprobe",
    "save_config",
]
