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
        tmp = CONFIG_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, CONFIG_FILE)
    except Exception as exc:
        raise RuntimeError(f"Could not save config: {exc}") from exc


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
    """Validate ffprobe. Accepts a direct exe path or a folder containing it."""
    if os.path.isdir(path):
        resolved = _resolve_ffprobe_from_dir(path)
        if not resolved:
            return False, "No ffprobe.exe found in folder"
        return _run_probe(resolved, ["-version"])
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


def _resolve_ffprobe_from_dir(dirpath):
    """Given a directory, look for ffprobe.exe inside it."""
    if not dirpath or not os.path.isdir(dirpath):
        return None
    for subpath in [
        "ffprobe.exe",
        os.path.join("bin", "ffprobe.exe"),
    ]:
        candidate = os.path.join(dirpath, subpath)
        if os.path.isfile(candidate):
            return candidate
    return None


def resolve_ffprobe(configured_path):
    """Resolve ffprobe. Accepts a direct exe path OR a directory (ffmpeg folder).

    Returns (resolved_path, source) where source describes how it was found.
    """
    # If configured path is a direct exe, use it
    if _is_file(configured_path):
        return configured_path, "configured"
    # If configured path is a directory, look for ffprobe inside it
    found = _resolve_ffprobe_from_dir(configured_path)
    if found:
        return found, "configured folder"
    # Try common install directories
    for d in [
        r"C:\Program Files\ffmpeg",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg",
        r"C:\Program Files (x86)\ffmpeg\bin",
        r"C:\ffmpeg",
        r"C:\ffmpeg\bin",
    ]:
        found = _resolve_ffprobe_from_dir(d)
        if found:
            return found, f"common path ({d})"
    # PATH lookup
    found = shutil.which("ffprobe")
    if found:
        return found, f"PATH ({found})"
    return configured_path or "", "not found"


def _locate_makemkvcon_registry():
    """Check Windows registry for a MakeMKV installation directory.

    MakeMKV's Windows installer writes to:
      HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MakeMKV
    with a 'DisplayIcon' value pointing directly to MakeMKVcon.exe and an
    'UninstallString' value pointing to uninst.exe in the same folder.
    There is NO InstallLocation value written by the official installer.
    """
    if platform.system() != "Windows":
        return None
    try:
        import winreg
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\MakeMKV"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\MakeMKV"),
            # Kept as fallbacks for non-standard or future installs
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MakeMKV"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\MakeMKV"),
        ]
        for hive, subkey in reg_paths:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    # DisplayIcon is the value the real installer writes — check it first
                    for value_name in ("DisplayIcon", "InstallLocation", "InstallDir", "Path"):
                        try:
                            val, _ = winreg.QueryValueEx(key, value_name)
                            if not val:
                                continue
                            # Value may point directly to the exe
                            if val.lower().endswith(".exe") and os.path.isfile(val):
                                return val
                            # Or it may be an install directory
                            candidate = os.path.join(val, "makemkvcon.exe")
                            if os.path.isfile(candidate):
                                return candidate
                        except OSError:
                            continue
                    # Last resort: derive install dir from UninstallString
                    try:
                        uninstall, _ = winreg.QueryValueEx(key, "UninstallString")
                        if uninstall:
                            install_dir = os.path.dirname(uninstall)
                            candidate = os.path.join(install_dir, "makemkvcon.exe")
                            if os.path.isfile(candidate):
                                return candidate
                    except OSError:
                        pass
            except OSError:
                continue
    except Exception:
        pass
    return None


def _locate_ffprobe_registry():
    """Check Windows registry and known package-manager paths for ffprobe."""
    if platform.system() != "Windows":
        return None
    try:
        import winreg
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\ffmpeg"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\ffmpeg"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Gyan.FFmpeg"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Gyan.FFmpeg"),
        ]
        for hive, subkey in reg_paths:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    for value_name in ("InstallLocation", "InstallDir"):
                        try:
                            val, _ = winreg.QueryValueEx(key, value_name)
                            if val:
                                found = _resolve_ffprobe_from_dir(val)
                                if found:
                                    return found
                        except OSError:
                            continue
            except OSError:
                continue
    except Exception:
        pass
    # Chocolatey default path
    choco = r"C:\tools\ffmpeg"
    found = _resolve_ffprobe_from_dir(choco)
    if found:
        return found
    return None


def auto_locate_tools():
    """Find MakeMKV and ffprobe using Windows registry, common paths, and PATH.

    Returns:
        (makemkvcon_path, ffprobe_path) — empty string for any tool not found.
    """
    makemkvcon = _locate_makemkvcon_registry() or resolve_makemkvcon("")
    # resolve_makemkvcon returns the configured_path arg when nothing is found,
    # so filter out the empty-string fallback.
    if not makemkvcon or not os.path.isfile(makemkvcon):
        makemkvcon = ""

    ffprobe = _locate_ffprobe_registry()
    if not ffprobe:
        ffprobe, _ = resolve_ffprobe("")
    if not ffprobe or not os.path.isfile(ffprobe):
        ffprobe = ""

    return makemkvcon, ffprobe


__all__ = [
    "CONFIG_FILE",
    "DEFAULTS",
    "get_config_dir",
    "auto_locate_tools",
    "load_config",
    "resolve_makemkvcon",
    "resolve_tool",
    "resolve_ffprobe",
    "save_config",
    "should_keep_current_tool_path",
    "validate_ffprobe",
    "validate_makemkvcon",
]
