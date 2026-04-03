"""Helper utilities implementation."""

import os
import platform
import re
import subprocess
import sys as _sys
from datetime import datetime

_POPEN_FLAGS = {"creationflags": 0x08000000} if _sys.platform == "win32" else {}

_WINDOWS_RESERVED = re.compile(
    r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',
    re.IGNORECASE,
)


def clean_name(name):
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', '', name)
    name = name.strip().rstrip(". ")
    if not name:
        return "Title_Unknown"
    # Append underscore to Windows reserved device names.
    stem, _, ext = name.partition(".")
    if _WINDOWS_RESERVED.match(stem):
        name = stem + "_" + ("." + ext if ext else "")
    return name


def make_rip_folder_name():
    return datetime.now().strftime("Disc_%Y-%m-%d_%H-%M-%S")


def make_temp_title():
    return f"TEMP_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"


def is_network_path(path):
    """Best-effort check for UNC or mapped/network drive paths.
    
    On Windows: checks for UNC paths (\\\\server\share) and DRIVE_REMOTE via GetDriveType.
    On Linux/macOS: checks /proc/mounts or mount output for network filesystem types (nfs, cifs, smb).
    Note: /mnt/ on WSL contains local mounts, not network paths; this function checks actual mount types.
    """
    try:
        if not path:
            return False
        p = os.path.normpath(path)
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
                import subprocess
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



def get_available_drives(makemkvcon_path):
    """Query MakeMKV for available optical drives via disc:9999 trick."""
    drives = []
    try:
        proc = subprocess.Popen(
            [makemkvcon_path, "-r", "info", "disc:9999"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **_POPEN_FLAGS
        )
        try:
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
            proc.wait()
    except Exception:
        pass
    if not drives:
        drives = [(0, "Default Drive (disc:0)")]
    return drives

__all__ = ["clean_name", "is_network_path", "make_rip_folder_name", "make_temp_title", "get_available_drives"]
