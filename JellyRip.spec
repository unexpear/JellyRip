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
FFMPEG_NOTICE_FILENAMES = ("LICENSE", "README.txt")


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


def _collect_tree(root_dir: Path, dest_root: str) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    if not root_dir.is_dir():
        return entries

    for path in root_dir.rglob("*"):
        if not path.is_file():
            continue
        relative_parent = path.parent.relative_to(root_dir)
        destination = str(Path(dest_root) / relative_parent).replace("\\", "/")
        entries.append((str(path), destination))
    return entries


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


def _add_search_root(roots: list[Path], root: Path) -> None:
    roots.append(root)
    if root.name.lower() == "bin":
        roots.append(root.parent)


def _search_roots() -> list[Path]:
    roots: list[Path] = []
    for env_name in FFMPEG_ENV_VARS:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            _add_search_root(roots, Path(raw).expanduser())

    for root in (
        PROJECT_ROOT / "ffmpeg",
        PROJECT_ROOT / "ffmpeg" / "bin",
        PROJECT_ROOT.parent / "ffmpeg",
        PROJECT_ROOT.parent / "ffmpeg" / "bin",
        PROJECT_ROOT.parent.parent / "ffmpeg",
        PROJECT_ROOT.parent.parent / "ffmpeg" / "bin",
    ):
        _add_search_root(roots, root)
    return roots


def _find_bundle_file(filename: str) -> str:
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
        f"Could not find {filename} from the FFmpeg build required by JellyRip.spec.\n"
        "Set JELLYRIP_FFMPEG_DIR (or FFMPEG_DIR) to the Gyan FFmpeg full build "
        "folder, or place the extracted build under .\\ffmpeg\\ or ..\\ffmpeg\\."
    )
    raise SystemExit(search_hint)


def _collect_gui_qt_qss() -> list[tuple[str, str]]:
    """Bundle the 6 generated QSS files under ``gui_qt/qss/`` so the
    runtime ``gui_qt.theme.load_theme`` can find them post-bundle.

    Phase 3a-themes generates the QSS files via
    ``tools/build_qss.py``; they live alongside the source and need
    to ship in the bundle's ``gui_qt/qss/`` data directory.

    Empty placeholder ``.qss`` files are filtered out by
    ``gui_qt.theme._is_real_theme_file`` at runtime — but we bundle
    them anyway so the directory layout matches dev-time.
    """
    qss_dir = PROJECT_ROOT / "gui_qt" / "qss"
    out: list[tuple[str, str]] = []
    if not qss_dir.is_dir():
        return out
    for path in sorted(qss_dir.glob("*.qss")):
        out.append((str(path), "gui_qt/qss"))
    return out


# Submodules of ``gui_qt`` that the shell + handlers import lazily
# (inside method bodies / via deferred imports).  PyInstaller's
# static analyzer doesn't always pick these up — list them
# explicitly so they always end up in the bundle.
GUI_QT_HIDDEN_IMPORTS: list[str] = [
    "gui_qt",
    "gui_qt.app",
    "gui_qt.theme",
    "gui_qt.themes",
    "gui_qt.main_window",
    "gui_qt.formatters",
    "gui_qt.log_pane",
    "gui_qt.splash",
    "gui_qt.status_bar",
    "gui_qt.thread_safety",
    "gui_qt.tray_icon",
    "gui_qt.workflow_launchers",
    "gui_qt.utility_handlers",
    "gui_qt.drive_handler",
    "gui_qt.preview_widget",
    "gui_qt.setup_wizard",
    "gui_qt.dialogs",
    "gui_qt.dialogs.ask",
    "gui_qt.dialogs.disc_tree",
    "gui_qt.dialogs.duplicate_resolution",
    "gui_qt.dialogs.info",
    "gui_qt.dialogs.list_picker",
    "gui_qt.dialogs.session_setup",
    "gui_qt.dialogs.space_override",
    "gui_qt.dialogs.temp_manager",
    "gui_qt.settings",
    "gui_qt.settings.dialog",
    "gui_qt.settings.tab_appearance",
    "gui_qt.settings.tab_everyday",
    "gui_qt.settings.tab_paths",
    "gui_qt.settings.tab_reliability",
]

# PySide6 modules the migration uses.  PySide6 6.0+ ships its own
# PyInstaller hooks that auto-collect most of QtCore/QtGui/QtWidgets,
# but listing them as hidden imports adds a safety net (especially
# for QtMultimedia, which is opt-in and used only by the preview
# widget — easy for the static analyzer to miss if the import is
# inside ``gui_qt/preview_widget.py`` only).
PYSIDE6_HIDDEN_IMPORTS: list[str] = [
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
]


GUI_QT_DATAS = _collect_gui_qt_qss()


APP_VERSION = _read_app_version()
APP_VERSION_INFO = _build_version_info(APP_VERSION)
FFMPEG_BINARIES = [(_find_bundle_file(name), ".") for name in FFMPEG_FILENAMES]
FFMPEG_NOTICE_DATAS = [
    (_find_bundle_file(name), "licenses/ffmpeg") for name in FFMPEG_NOTICE_FILENAMES
]

a = Analysis(
    ["main.py"],
    pathex=[str(PROJECT_ROOT)],
    binaries=FFMPEG_BINARIES,
    datas=[
        ("LICENSE", "."),
        ("THIRD_PARTY_NOTICES.md", "."),
        *FFMPEG_NOTICE_DATAS,
        # Phase 3a-themes — ship the 6 generated QSS theme files.
        *GUI_QT_DATAS,
    ],
    hiddenimports=[
        # Phase 3h close-out (2026-05-05) — tkinter retired entirely.
        # Qt is the only UI; the gui/ directory and the runtime
        # hook are gone.
        *GUI_QT_HIDDEN_IMPORTS,
        *PYSIDE6_HIDDEN_IMPORTS,
    ],
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
