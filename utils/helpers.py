"""Helper utilities implementation."""

import os
import platform
import re
import subprocess
import sys as _sys
from datetime import datetime
from os import PathLike

_WINDOWS_RESERVED = re.compile(
    r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',
    re.IGNORECASE,
)


def clean_name(name: object) -> str:
    cleaned = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '', str(name))
    cleaned = cleaned.strip().rstrip(". ")
    if not cleaned:
        return "Title_Unknown"
    # Append underscore to Windows reserved device names.
    stem, _, ext = cleaned.partition(".")
    if _WINDOWS_RESERVED.match(stem):
        cleaned = stem + "_" + ("." + ext if ext else "")
    return cleaned


def make_rip_folder_name() -> str:
    return datetime.now().strftime("Disc_%Y-%m-%d_%H-%M-%S")


def make_temp_title() -> str:
    return f"TEMP_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"


def is_network_path(path: str | PathLike[str] | None) -> bool:
    """Best-effort check for UNC or mapped/network drive paths.

    On Windows: checks for UNC paths (\\\\server\\share) and DRIVE_REMOTE via GetDriveType.
    On Linux/macOS: checks /proc/mounts or mount output for network filesystem types (nfs, cifs, smb).
    Note: /mnt/ on WSL contains local mounts, not network paths; this function checks actual mount types.
    """
    try:
        if not path:
            return False
        p: str = os.path.normpath(os.fspath(path))
        if p.startswith("\\\\"):
            return True
        if platform.system() == "Windows":
            drive, _ = os.path.splitdrive(p)
            if drive:
                root = drive + "\\"
                try:
                    import ctypes
                    drive_type = ctypes.windll.kernel32.GetDriveTypeW(root)
                    # DRIVE_REMOTE = 4
                    return int(drive_type) == 4
                except Exception:
                    return False
        else:
            # Non-Windows: check /proc/mounts or mount output for network filesystem types.
            # This properly handles WSL where /mnt/* are local mounts, not network paths.
            try:
                # Try /proc/mounts first (Linux)
                if os.path.exists("/proc/mounts"):
                    with open("/proc/mounts", "r") as f:
                        for line in f:
                            parts = line.split()
                            if len(parts) >= 3:
                                mount_point = parts[1]
                                fs_type = parts[2]
                                # Check if path starts with this mount point and fs_type is network
                                if p.startswith(mount_point) and fs_type in ("nfs", "nfs4", "cifs", "smb", "smbfs"):
                                    return True
            except Exception:
                pass
            # Fallback: if /proc/mounts is unavailable, try 'mount' command
            try:
                result = subprocess.run(["mount"], capture_output=True, text=True, timeout=2)
                for line in result.stdout.split("\n"):
                    if any(fs in line.lower() for fs in ("nfs", "cifs", "smb")):
                        # Try to extract mount point and see if path is under it
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "on" and i + 1 < len(parts):
                                mount_point = parts[i + 1]
                                if p.startswith(mount_point):
                                    return True
            except Exception:
                pass
        return False
    except Exception:
        return False


def get_available_drives(makemkvcon_path: str) -> list[tuple[int, str]]:
    """Query MakeMKV for available optical drives via disc:9999 trick."""
    drives: list[tuple[int, str]] = []
    try:
        if _sys.platform == "win32":
            proc = subprocess.Popen(
                [makemkvcon_path, "-r", "info", "disc:9999"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=0x08000000,
            )
        else:
            proc = subprocess.Popen(
                [makemkvcon_path, "-r", "info", "disc:9999"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        try:
            if proc.stdout is None:
                return [(0, "Default Drive (disc:0)")]
            for line in iter(proc.stdout.readline, ""):
                line = line.strip()
                if line.startswith("DRV:"):
                    parts = line[4:].split(",")
                    if len(parts) >= 6:
                        try:
                            idx  = int(parts[0])
                            name = parts[5].strip().strip('"')
                            if name:
                                drives.append((idx, name))
                        except (ValueError, IndexError):
                            pass
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
    except Exception:
        pass
    if not drives:
        drives = [(0, "Default Drive (disc:0)")]
    return drives

__all__ = ["clean_name", "is_network_path", "make_rip_folder_name", "make_temp_title", "get_available_drives"]
