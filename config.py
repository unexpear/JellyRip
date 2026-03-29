"""Configuration implementation for package-style imports."""

import json
import os
import shutil

from shared.runtime import CONFIG_FILE, DEFAULTS, get_config_dir


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Warning: config file is corrupt, resetting to defaults: {exc}")
        cfg = {}
    except Exception as exc:
        print(f"Warning: could not read config, using defaults: {exc}")
        cfg = {}
    for key, value in DEFAULTS.items():
        if key not in cfg:
            cfg[key] = value

    if "opt_naming_mode" not in cfg and "opt_fallback_title_mode" in cfg:
        cfg["opt_naming_mode"] = cfg.get("opt_fallback_title_mode")

    if "opt_fallback_title_mode" in cfg:
        cfg.pop("opt_fallback_title_mode", None)

    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as exc:
        print(f"Warning: could not save config: {exc}")


def resolve_ffprobe(configured_path):
    if os.path.exists(configured_path):
        return configured_path
    found = shutil.which("ffprobe")
    if found:
        return found
    fallbacks = [
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
    ]
    for path in fallbacks:
        if os.path.exists(path):
            return path
    return configured_path

__all__ = [
    "CONFIG_FILE",
    "DEFAULTS",
    "get_config_dir",
    "load_config",
    "resolve_ffprobe",
    "save_config",
]
