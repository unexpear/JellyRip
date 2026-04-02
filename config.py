"""Configuration implementation for package-style imports."""

import json
import os
import platform
import shutil
import subprocess

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


def _is_file(path):
    return bool(path) and os.path.isfile(path)


def _run_probe(executable, args):
    if not _is_file(executable):
        return False, "Path does not exist"
    try:
        if platform.system() == "Windows":
            proc = subprocess.run(
                [executable] + list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                creationflags=0x08000000,
            )
        else:
            proc = subprocess.run(
                [executable] + list(args),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
    except Exception as exc:
        return False, str(exc)
    if proc.returncode != 0:
        return False, f"Exited with code {proc.returncode}"
    return True, ""


def validate_makemkvcon(path):
    return _run_probe(path, ["-r", "--version"])


def validate_ffprobe(path):
    return _run_probe(path, ["-version"])


def should_keep_current_tool_path(current_path, candidate_path, validator):
    """Return True when current working path should be preserved.

    Rule: never overwrite a working configured path unless the new path is
    validated first.
    """
    current = os.path.normpath(str(current_path or "").strip())
    candidate = os.path.normpath(str(candidate_path or "").strip())

    if not current or candidate == current:
        return False

    current_ok, _ = validator(current)
    if not current_ok:
        return False

    candidate_ok, _ = validator(candidate)
    return not candidate_ok


def resolve_tool(configured_path, common_paths, env_tool_name):
    """Resolve an executable path in order: config, common paths, then PATH."""
    if _is_file(configured_path):
        return configured_path
    for path in common_paths:
        if _is_file(path):
            return path
    found = shutil.which(env_tool_name)
    if found:
        return found
    return configured_path


def resolve_makemkvcon(configured_path):
    fallbacks = [
        r"C:\Program Files (x86)\MakeMKV\makemkvcon.exe",
        r"C:\Program Files\MakeMKV\makemkvcon.exe",
    ]
    return resolve_tool(configured_path, fallbacks, "makemkvcon")


def resolve_ffprobe(configured_path):
    fallbacks = [
        r"C:\Program Files\HandBrake\ffprobe.exe",
        r"C:\Program Files (x86)\HandBrake\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffprobe.exe",
        r"C:\ffmpeg\bin\ffprobe.exe",
    ]
    return resolve_tool(configured_path, fallbacks, "ffprobe")

__all__ = [
    "CONFIG_FILE",
    "DEFAULTS",
    "get_config_dir",
    "load_config",
    "resolve_makemkvcon",
    "resolve_tool",
    "resolve_ffprobe",
    "save_config",
    "should_keep_current_tool_path",
    "validate_ffprobe",
    "validate_makemkvcon",
]
