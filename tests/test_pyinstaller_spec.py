"""Phase 3f — JellyRip.spec content pin.

The PyInstaller spec lives at the repo root and is the source of
truth for the production bundle.  Phase 3a-3e shipped a lot of new
Python modules + assets; the spec was extended in Phase 3f to
ensure they end up in the bundle.

This file pins the additions via text introspection (no PyInstaller
import, no actual build).  Catches accidental regressions like:

* Removing ``gui_qt`` from hidden imports → bundle launches but
  immediately fails ``import gui_qt.app``.
* Forgetting to ship the QSS files → launches but every theme
  load raises ``FileNotFoundError`` and falls back to unstyled.
* Dropping ``PySide6.QtMultimedia`` from hidden imports → preview
  widget crashes on first invocation in the bundle.

The test reads ``JellyRip.spec`` as text (not as a Python module)
because importing it would try to run the PyInstaller-only
``Analysis``, ``PYZ``, ``EXE`` constructors.  Spec syntax is
verified separately via ``ast.parse``.
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = _REPO_ROOT / "JellyRip.spec"


def _spec_text() -> str:
    return _SPEC.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Sanity
# ---------------------------------------------------------------------------


def test_spec_file_exists():
    assert _SPEC.is_file(), f"JellyRip.spec must exist at {_SPEC}"


def test_spec_is_syntactically_valid_python():
    """The spec must AST-parse — PyInstaller runs it as Python."""
    ast.parse(_spec_text())


# ---------------------------------------------------------------------------
# tkinter path still load-bearing
# ---------------------------------------------------------------------------


def test_tkinter_hidden_imports_still_present():
    """Phase 3 keeps the tkinter path runnable until Phase 3h, so
    the spec must still bundle tkinter.  Pinned because losing this
    silently breaks every user who hasn't opted into PySide6."""
    src = _spec_text()
    for tk_mod in ("tkinter", "tkinter.ttk", "_tkinter"):
        assert f'"{tk_mod}"' in src, (
            f"{tk_mod} dropped from hidden imports — would break "
            f"the tkinter path during the migration"
        )


# ---------------------------------------------------------------------------
# Phase 3a-3e additions
# ---------------------------------------------------------------------------


def test_gui_qt_qss_collector_present():
    """``_collect_gui_qt_qss`` helper bundles the 6 QSS theme files
    under gui_qt/qss/.  Without this, themes don't render in the
    bundle."""
    src = _spec_text()
    assert "_collect_gui_qt_qss" in src
    assert "gui_qt/qss" in src


def test_gui_qt_hidden_imports_list_present():
    """``GUI_QT_HIDDEN_IMPORTS`` ensures lazy-imported gui_qt
    submodules are bundled.  Static analysis misses these."""
    src = _spec_text()
    assert "GUI_QT_HIDDEN_IMPORTS" in src


def test_critical_gui_qt_modules_in_hidden_imports():
    """Each module that's imported lazily (inside method bodies or
    via deferred imports) must appear by name."""
    src = _spec_text()
    critical = [
        # Top-level shell + handlers
        "gui_qt.main_window",
        "gui_qt.app",
        # Theming infrastructure (3a-themes)
        "gui_qt.theme",
        "gui_qt.themes",
        # 3c-i leaves
        "gui_qt.formatters",
        "gui_qt.log_pane",
        "gui_qt.status_bar",
        # 3c-ii infrastructure
        "gui_qt.thread_safety",
        "gui_qt.workflow_launchers",
        "gui_qt.utility_handlers",
        # 3c-iii — drive scan + Prep MVP
        "gui_qt.drive_handler",
        # 3e — preview (lazy QtMultimedia import)
        "gui_qt.preview_widget",
        # Wizard (3b)
        "gui_qt.setup_wizard",
        # Dialogs (3c-ii / 3c-iii)
        "gui_qt.dialogs.ask",
        "gui_qt.dialogs.info",
        "gui_qt.dialogs.session_setup",
        "gui_qt.dialogs.disc_tree",
        "gui_qt.dialogs.duplicate_resolution",
        "gui_qt.dialogs.list_picker",
        "gui_qt.dialogs.space_override",
        "gui_qt.dialogs.temp_manager",
        # Settings (3d, renamed 2026-05-04)
        "gui_qt.settings",
        "gui_qt.settings.dialog",
        "gui_qt.settings.tab_appearance",
    ]
    for mod in critical:
        assert f'"{mod}"' in src, (
            f"{mod} dropped from hidden imports — bundle would fail "
            f"to import it lazily at runtime"
        )


def test_pyside6_hidden_imports_present():
    """PySide6 modules should be listed as a safety net for
    PyInstaller's static analysis."""
    src = _spec_text()
    for mod in (
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
    ):
        assert f'"{mod}"' in src, (
            f"{mod} dropped from hidden imports"
        )


def test_qtmultimedia_hidden_import_present():
    """``QtMultimedia`` is critical for Phase 3e (MKV preview).
    PyInstaller's hook for PySide6 may or may not collect it
    depending on hook version — listing here is the belt-and-
    suspenders fix."""
    src = _spec_text()
    assert '"PySide6.QtMultimedia"' in src
    assert '"PySide6.QtMultimediaWidgets"' in src


def test_gui_qt_datas_threaded_into_analysis():
    """The collected QSS data files must be spread into the
    Analysis ``datas`` list."""
    src = _spec_text()
    assert "GUI_QT_DATAS" in src
    # Verify it's actually consumed in the Analysis call (the
    # ``*GUI_QT_DATAS`` spread).
    assert "*GUI_QT_DATAS" in src


def test_hidden_imports_threaded_into_analysis():
    """Both hidden-imports lists must be spread into the Analysis
    ``hiddenimports`` list."""
    src = _spec_text()
    assert "*GUI_QT_HIDDEN_IMPORTS" in src
    assert "*PYSIDE6_HIDDEN_IMPORTS" in src


# ---------------------------------------------------------------------------
# QSS files actually exist on disk
# ---------------------------------------------------------------------------


def test_qss_files_exist_for_collector():
    """The collector globs ``gui_qt/qss/*.qss``; if those files
    don't exist on disk, the bundle ships zero themes.  This pin
    ensures Phase 3a-themes' generated QSS files are present."""
    qss_dir = _REPO_ROOT / "gui_qt" / "qss"
    assert qss_dir.is_dir(), "gui_qt/qss/ must exist"
    qss_files = sorted(qss_dir.glob("*.qss"))
    # Filter to non-empty (the deprecated warm.qss placeholder may
    # still be present at 0 bytes — the loader filters it).
    real = [p for p in qss_files if p.stat().st_size > 0]
    assert len(real) >= 6, (
        f"Expected at least 6 themes in gui_qt/qss/, got "
        f"{[p.name for p in real]}"
    )


# ---------------------------------------------------------------------------
# Build script content pin
# ---------------------------------------------------------------------------


def test_build_bat_invokes_pyinstaller():
    """Sanity — the build batch file should still run PyInstaller
    on the spec.  Pinned against accidental regression of the
    build pipeline."""
    build_bat = _REPO_ROOT / "build.bat"
    if not build_bat.is_file():
        # Build script may live elsewhere on some setups.
        return
    text = build_bat.read_text(encoding="utf-8", errors="replace")
    assert "PyInstaller" in text or "pyinstaller" in text.lower()
    assert "JellyRip.spec" in text
