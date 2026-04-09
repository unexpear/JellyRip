# -*- mode: python ; coding: utf-8 -*-

import os
import re
import sys
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VSVersionInfo,
    VarFileInfo,
    VarStruct,
)


# PyInstaller executes the spec without defining __file__, so resolve
# project-relative paths from the working directory used to launch it.
PROJECT_ROOT = Path.cwd()
FFMPEG_ENV_VARS = ("JELLYRIP_FFMPEG_DIR", "FFMPEG_DIR")
FFMPEG_FILENAMES = ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")


def _configure_tcl_tk_environment() -> None:
    base_prefix = Path(getattr(sys, "base_prefix", "") or "")
    if not base_prefix:
        return

    tcl_root = base_prefix / "tcl"
    tcl_library = tcl_root / "tcl8.6"
    tk_library = tcl_root / "tk8.6"

    if not os.environ.get("TCL_LIBRARY") and tcl_library.is_dir():
        os.environ["TCL_LIBRARY"] = str(tcl_library)
    if not os.environ.get("TK_LIBRARY") and tk_library.is_dir():
        os.environ["TK_LIBRARY"] = str(tk_library)


_configure_tcl_tk_environment()


def _read_app_version() -> str:
    runtime_path = PROJECT_ROOT / "shared" / "runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', runtime_text)
    if not match:
        raise SystemExit("Could not read __version__ from shared/runtime.py")
    return match.group(1)


def _version_quad(version: str) -> tuple[int, int, int, int]:
    parts: list[int] = []
    for piece in version.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def _build_version_info(version: str) -> VSVersionInfo:
    version_quad = _version_quad(version)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=version_quad,
            prodvers=version_quad,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "unexpear"),
                            StringStruct("FileDescription", "JellyRip"),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", "JellyRip"),
                            StringStruct("OriginalFilename", "JellyRip.exe"),
                            StringStruct("ProductName", "JellyRip"),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )

def _search_roots() -> list[Path]:
    roots: list[Path] = []
    for env_name in FFMPEG_ENV_VARS:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            roots.append(Path(raw).expanduser())

    roots.extend(
        [
            PROJECT_ROOT / "ffmpeg",
            PROJECT_ROOT / "ffmpeg" / "bin",
            PROJECT_ROOT.parent / "ffmpeg",
            PROJECT_ROOT.parent / "ffmpeg" / "bin",
        ]
    )
    return roots


def _find_bundle_binary(filename: str) -> str:
    seen: set[str] = set()
    for root in _search_roots():
        try:
            normalized_root = root.resolve()
        except OSError:
            normalized_root = root

        root_key = os.path.normcase(str(normalized_root))
        if root_key in seen or not normalized_root.exists():
            continue
        seen.add(root_key)

        direct_candidates = [
            normalized_root / filename,
            normalized_root / "bin" / filename,
        ]
        for candidate in direct_candidates:
            if candidate.is_file():
                return str(candidate)

        for candidate in normalized_root.rglob(filename):
            if candidate.is_file():
                return str(candidate)

    search_hint = (
        "Could not find the bundled FFmpeg tools required by JellyRip.spec.\n"
        "Set JELLYRIP_FFMPEG_DIR (or FFMPEG_DIR) to a folder containing "
        "ffmpeg.exe, ffprobe.exe, and ffplay.exe, or place an extracted "
        "FFmpeg build under .\\ffmpeg\\ or ..\\ffmpeg\\."
    )
    raise SystemExit(search_hint)


APP_VERSION = _read_app_version()
APP_VERSION_INFO = _build_version_info(APP_VERSION)
FFMPEG_BINARIES = [(_find_bundle_binary(name), ".") for name in FFMPEG_FILENAMES]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=FFMPEG_BINARIES,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="JellyRip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=APP_VERSION_INFO,
)
