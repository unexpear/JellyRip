"""Phase 3a scaffolding tests — PySide6 directory + theme loader + cfg.

Pins the contracts for sub-phase 3a per
[docs/handoffs/phase-3a-pyside6-scaffolding.md](../docs/handoffs/phase-3a-pyside6-scaffolding.md):

- ``gui_qt/`` directory exists with the expected layout.
- The 6 themes (``dark_github``, ``light_inverted``, ``dracula_light``,
  ``hc_dark``, ``slate``, ``frost``) all have non-empty QSS files.
  **Updated 2026-05-03** when the user delivered design mockups for
  6 themes (superseding the original 3-theme placeholder set).
  Empty placeholder files like the deprecated ``warm.qss`` are
  filtered out by ``list_themes()`` and don't need to count.
- ``gui_qt.theme.list_themes()`` returns the 6 real names.
- ``gui_qt.theme.load_theme()`` raises ``FileNotFoundError`` on
  unknown names AND on empty placeholders, with a helpful message.
- ``gui_qt.theme.load_theme()`` calls ``app.setStyleSheet`` with the
  QSS file contents.
- ``DEFAULTS`` in ``shared/runtime.py`` has ``opt_use_pyside6`` and
  ``opt_pyside6_theme`` with the documented defaults.

WCAG contrast pins for the 6 themes live in ``test_pyside6_themes.py``.

Behavior-first.  Does NOT instantiate ``QApplication`` (that needs a
display or the offscreen platform plugin — sub-phase 3g territory
under pytest-qt).  Tests use a tiny fake-app stand-in that captures
the ``setStyleSheet`` call so we can assert what was loaded.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from gui_qt import theme as theme_module
from shared.runtime import DEFAULTS


_REPO_ROOT = Path(__file__).resolve().parent.parent
_QSS_DIR = _REPO_ROOT / "gui_qt" / "qss"

_EXPECTED_THEMES = (
    "dark_github",
    "light_inverted",
    "dracula_light",
    "hc_dark",
    "slate",
    "frost",
)


# --------------------------------------------------------------------------
# Directory layout
# --------------------------------------------------------------------------


def test_gui_qt_directory_exists():
    """``gui_qt/`` is a package next to ``gui/``, not a child of it.
    Pins the parallel-tree layout that lets tkinter and Qt coexist
    during the migration."""
    gui_qt = _REPO_ROOT / "gui_qt"
    gui = _REPO_ROOT / "gui"
    assert gui_qt.is_dir(), "gui_qt/ must exist"
    assert gui.is_dir(), "gui/ must still exist (tkinter not yet retired)"
    assert (gui_qt / "__init__.py").is_file(), "gui_qt/__init__.py present"


def test_gui_qt_qss_directory_has_expected_themes():
    """All 6 themes from sub-phase 3a-themes (delivered 2026-05-03)
    must exist as non-empty QSS files.  The deprecated ``warm.qss``
    placeholder may still be present on disk pending user deletion;
    we ignore empty files here since ``_is_real_theme_file`` filters
    them out at the loader level."""
    assert _QSS_DIR.is_dir(), "gui_qt/qss/ must exist"
    real_qss = [p for p in _QSS_DIR.glob("*.qss") if p.stat().st_size > 0]
    present = sorted(p.stem for p in real_qss)
    expected = sorted(_EXPECTED_THEMES)
    assert present == expected, (
        f"expected exactly {expected} (non-empty), got {present}"
    )


# --------------------------------------------------------------------------
# Theme loader contract
# --------------------------------------------------------------------------


def test_list_themes_returns_expected_names_sorted():
    """``list_themes()`` returns the theme names without the .qss
    extension, sorted for stable picker order."""
    names = theme_module.list_themes()
    assert names == sorted(_EXPECTED_THEMES)


class _FakeApp:
    """Minimal stand-in for ``QApplication`` that captures the QSS
    loaded via ``setStyleSheet``.  Lets us test the loader without
    spinning up a real QApplication (which needs a display)."""

    def __init__(self):
        self.last_stylesheet: str | None = None

    def setStyleSheet(self, qss: str) -> None:
        self.last_stylesheet = qss


def test_load_theme_applies_qss_to_app(tmp_path, monkeypatch):
    """``load_theme()`` reads the QSS file and applies it via
    ``app.setStyleSheet``.  Pins the loader's primary contract."""
    fake_qss_dir = tmp_path / "qss"
    fake_qss_dir.mkdir()
    (fake_qss_dir / "test_theme.qss").write_text(
        "QPushButton { color: #58a6ff; }",
        encoding="utf-8",
    )
    monkeypatch.setattr(theme_module, "THEME_DIR", fake_qss_dir)

    app = _FakeApp()
    theme_module.load_theme(app, "test_theme")

    assert app.last_stylesheet == "QPushButton { color: #58a6ff; }"


def test_load_theme_raises_on_unknown_theme(tmp_path, monkeypatch):
    """Unknown theme name raises ``FileNotFoundError`` so callers
    can show a clear error rather than silently rendering an
    unstyled window."""
    fake_qss_dir = tmp_path / "qss"
    fake_qss_dir.mkdir()
    (fake_qss_dir / "real_theme.qss").write_text("/* real */")
    monkeypatch.setattr(theme_module, "THEME_DIR", fake_qss_dir)

    app = _FakeApp()
    with pytest.raises(FileNotFoundError) as excinfo:
        theme_module.load_theme(app, "doesnt_exist")

    msg = str(excinfo.value)
    assert "doesnt_exist" in msg, "error message names the missing theme"
    assert "real_theme" in msg, (
        "error message lists available themes so the user can fix "
        "the typo without going to the docs"
    )
    assert app.last_stylesheet is None, (
        "no stylesheet should be applied on failure"
    )


def test_load_theme_with_real_qss_files_does_not_raise():
    """Each of the 6 real QSS files in ``gui_qt/qss/`` must load
    without error and produce a non-empty stylesheet.  Pins that the
    loader can read every documented theme and that
    ``tools/build_qss.py`` produced real content for each."""
    app = _FakeApp()
    for theme_name in _EXPECTED_THEMES:
        # Must not raise.
        theme_module.load_theme(app, theme_name)
        # And must have real content (not just empty/whitespace).
        assert app.last_stylesheet, (
            f"theme {theme_name!r} loaded but produced empty stylesheet — "
            f"did tools/build_qss.py run?"
        )
        assert "QPushButton" in app.last_stylesheet, (
            f"theme {theme_name!r} doesn't style QPushButton — "
            f"template regression?"
        )


def test_load_theme_rejects_empty_placeholder(tmp_path, monkeypatch):
    """Empty .qss files (like the deprecated ``warm.qss`` pending
    deletion) must be rejected by ``load_theme`` — they would
    otherwise silently produce an unstyled window, which is
    indistinguishable from "no theme loaded" and very confusing to
    debug.  Pinned as a regression guard for the
    ``_is_real_theme_file`` filter."""
    fake_qss_dir = tmp_path / "qss"
    fake_qss_dir.mkdir()
    (fake_qss_dir / "placeholder.qss").write_text("")  # 0 bytes
    monkeypatch.setattr(theme_module, "THEME_DIR", fake_qss_dir)

    with pytest.raises(FileNotFoundError):
        theme_module.load_theme(_FakeApp(), "placeholder")

