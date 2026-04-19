"""Helper utilities implementation."""

import csv
import os
import platform
import re
import subprocess
import sys as _sys
from dataclasses import dataclass
from datetime import datetime
from os import PathLike

_WINDOWS_RESERVED = re.compile(
    r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\.|$)',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MakeMKVDriveInfo:
    index: int
    state_code: int
    flags_code: int
    disc_type_code: int
    drive_name: str
    disc_name: str
    device_path: str
    raw_line: str = ""

    @property
    def usability_state(self) -> str:
        if self.state_code == 2:
            return "ready"
        if self.state_code == 0:
            return "empty"
        if self.state_code == 256:
            return "unavailable"
        return f"state {self.state_code}"

    @property
    def has_identity(self) -> bool:
        return bool(self.drive_name or self.disc_name or self.device_path)

    @property
    def target(self) -> str:
        return self.device_path or f"disc:{self.index}"

    def __iter__(self):
        yield self.index
        yield self.drive_name or self.disc_name or self.target


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


def parse_makemkv_drive_row(line: str) -> MakeMKVDriveInfo | None:
    raw_line = (line or "").strip()
    if not raw_line.startswith("DRV:"):
        return None
    try:
        parts = next(csv.reader([raw_line[4:]]))
    except Exception:
        return None
    if len(parts) < 7:
        return None
    try:
        return MakeMKVDriveInfo(
            index=int(parts[0]),
            state_code=int(parts[1]),
            flags_code=int(parts[2]),
            disc_type_code=int(parts[3]),
            drive_name=parts[4].strip(),
            disc_name=parts[5].strip(),
            device_path=parts[6].strip(),
            raw_line=raw_line,
        )
    except ValueError:
        return None


def get_available_drives(makemkvcon_path: str) -> list[MakeMKVDriveInfo]:
    """Query MakeMKV for available optical drives via disc:9999 trick."""
    drives: list[MakeMKVDriveInfo] = []
    try:
        if _sys.platform == "win32":
            proc = subprocess.Popen(
                [makemkvcon_path, "-r", "--cache=1", "info", "disc:9999"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=0x08000000,
            )
        else:
            proc = subprocess.Popen(
                [makemkvcon_path, "-r", "--cache=1", "info", "disc:9999"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        try:
            if proc.stdout is None:
                return [
                    MakeMKVDriveInfo(
                        index=0,
                        state_code=0,
                        flags_code=999,
                        disc_type_code=0,
                        drive_name="Default Drive",
                        disc_name="",
                        device_path="disc:0",
                    )
                ]
            for line in iter(proc.stdout.readline, ""):
                drive = parse_makemkv_drive_row(line)
                if drive is not None and drive.has_identity:
                    drives.append(drive)
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
        drives = [
            MakeMKVDriveInfo(
                index=0,
                state_code=0,
                flags_code=999,
                disc_type_code=0,
                drive_name="Default Drive",
                disc_name="",
                device_path="disc:0",
            )
        ]
    return drives

__all__ = [
    "MakeMKVDriveInfo",
    "clean_name",
    "get_available_drives",
    "is_network_path",
    "make_rip_folder_name",
    "make_temp_title",
    "parse_makemkv_drive_row",
]
