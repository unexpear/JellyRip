"""Phase A Appearance-tab tests — 5 checkbox toggles.

Pins the click-to-apply contract for each new toggle:

- Initial state matches cfg
- Toggle writes cfg AND fires the live-apply hook on the window
- ``apply()`` (OK button) persists the cfg dict via ``save_cfg``
- ``cancel()`` walks the snapshot and reverts both cfg AND the
  live-apply hook so the runtime widget follows

Tests use a fake ``Window`` stub instead of a real ``MainWindow``
so we don't pay the construction cost; the contract we're pinning
is method-name-based, not full-window integration.

See ``docs/handoffs/appearance-tab-spec.md`` for the design.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt

from gui_qt.settings.tab_appearance import AppearanceTab


# ---------------------------------------------------------------------------
# Fake window stub — captures live-apply calls so tests can assert
# the right hook fired with the right value.
# ---------------------------------------------------------------------------


class _FakeLogPane:
    def __init__(self) -> None:
        self.color_calls: list[bool] = []
        self.glyph_calls: list[bool] = []

    def set_color_levels_enabled(self, v: bool) -> None:
        self.color_calls.append(v)

    def set_glyph_prefix_enabled(self, v: bool) -> None:
        self.glyph_calls.append(v)


class _FakeDriveHandler:
    def __init__(self) -> None:
        self.refresh_calls = 0

    def refresh_labels(self) -> None:
        self.refresh_calls += 1


class _FakeWindow:
    def __init__(self) -> None:
        self.log_pane = _FakeLogPane()
        self._drive_handler = _FakeDriveHandler()
        self.tray_calls: list[bool] = []

    def set_tray_enabled(self, v: bool) -> None:
        self.tray_calls.append(v)


def _make_tab(qtbot, cfg=None, window=None, save_cfg=None) -> AppearanceTab:
    if cfg is None:
        cfg = {
            "opt_pyside6_theme": "dark_github",
            "opt_log_color_levels": True,
            "opt_log_glyph_prefix": True,
            "opt_drive_state_glyph": True,
            "opt_tray_icon_enabled": True,
            "opt_show_splash": True,
        }
    tab = AppearanceTab(
        cfg=cfg,
        list_themes=lambda: ["dark_github"],
        load_theme=lambda name: None,
        save_cfg=save_cfg,
        window=window,
    )
    qtbot.addWidget(tab)
    return tab


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


def test_checkbox_initial_state_matches_cfg(qtbot):
    """Each checkbox's initial state must reflect the cfg value."""
    cfg = {
        "opt_pyside6_theme": "dark_github",
        "opt_log_color_levels": False,
        "opt_log_glyph_prefix": True,
        "opt_drive_state_glyph": False,
        "opt_tray_icon_enabled": True,
        "opt_show_splash": False,
    }
    tab = _make_tab(qtbot, cfg=cfg)
    assert tab._cb_color_levels.isChecked() is False
    assert tab._cb_glyph_prefix.isChecked() is True
    assert tab._cb_drive_glyph.isChecked() is False
    assert tab._cb_tray.isChecked() is True
    assert tab._cb_splash.isChecked() is False


def test_checkbox_initial_state_defaults_to_true(qtbot):
    """When a cfg key is missing entirely, the checkbox defaults
    to checked.  Pinned because the spec promises "defaults match
    current behavior" — every new toggle is True by default."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    tab = _make_tab(qtbot, cfg=cfg)
    assert tab._cb_color_levels.isChecked() is True
    assert tab._cb_glyph_prefix.isChecked() is True
    assert tab._cb_drive_glyph.isChecked() is True
    assert tab._cb_tray.isChecked() is True
    assert tab._cb_splash.isChecked() is True


# ---------------------------------------------------------------------------
# Live preview — toggling fires runtime hooks but does NOT touch cfg.
# Pure preview semantics: cfg is reserved for OK.
# ---------------------------------------------------------------------------


def test_color_levels_toggle_off_fires_log_pane_hook_but_skips_cfg(qtbot):
    win = _FakeWindow()
    cfg = {"opt_log_color_levels": True}
    tab = _make_tab(qtbot, cfg=cfg, window=win)
    tab._cb_color_levels.setChecked(False)
    # Runtime hook fired with the new value...
    assert win.log_pane.color_calls == [False]
    # ...but cfg is untouched (only OK writes cfg).
    assert cfg["opt_log_color_levels"] is True


def test_color_levels_toggle_on_again_fires_hook(qtbot):
    cfg = {"opt_log_color_levels": False}
    win = _FakeWindow()
    tab = _make_tab(qtbot, cfg=cfg, window=win)
    tab._cb_color_levels.setChecked(True)
    assert win.log_pane.color_calls == [True]
    assert cfg["opt_log_color_levels"] is False  # untouched


def test_glyph_prefix_toggle_off_fires_log_pane_hook_but_skips_cfg(qtbot):
    win = _FakeWindow()
    cfg = {"opt_log_glyph_prefix": True}
    tab = _make_tab(qtbot, cfg=cfg, window=win)
    tab._cb_glyph_prefix.setChecked(False)
    assert win.log_pane.glyph_calls == [False]
    assert cfg["opt_log_glyph_prefix"] is True  # untouched


def test_drive_glyph_toggle_calls_refresh_labels_but_skips_cfg(qtbot):
    win = _FakeWindow()
    cfg = {"opt_drive_state_glyph": True}
    tab = _make_tab(qtbot, cfg=cfg, window=win)
    tab._cb_drive_glyph.setChecked(False)
    assert win._drive_handler.refresh_calls == 1
    assert cfg["opt_drive_state_glyph"] is True  # untouched


def test_tray_toggle_calls_window_but_skips_cfg(qtbot):
    win = _FakeWindow()
    cfg = {"opt_tray_icon_enabled": True}
    tab = _make_tab(qtbot, cfg=cfg, window=win)
    tab._cb_tray.setChecked(False)
    assert win.tray_calls == [False]
    assert cfg["opt_tray_icon_enabled"] is True  # untouched
    tab._cb_tray.setChecked(True)
    assert win.tray_calls == [False, True]


def test_splash_toggle_does_nothing_at_runtime(qtbot):
    """Splash has no runtime hook (next-launch only) AND doesn't
    touch cfg until OK.  Toggling is purely a UI state change
    until the user commits."""
    win = _FakeWindow()
    cfg = {"opt_show_splash": True}
    tab = _make_tab(qtbot, cfg=cfg, window=win)
    tab._cb_splash.setChecked(False)
    assert cfg["opt_show_splash"] is True  # untouched
    # No window methods called.
    assert win.tray_calls == []
    assert win.log_pane.color_calls == []
    assert win.log_pane.glyph_calls == []
    assert win._drive_handler.refresh_calls == 0


# ---------------------------------------------------------------------------
# OK — apply() reads every widget and commits to cfg + disk
# ---------------------------------------------------------------------------


def test_apply_writes_every_widget_value_to_cfg(qtbot):
    """``apply()`` is the single mutation point — reads each
    widget's current state and writes it to cfg."""
    cfg = {
        "opt_pyside6_theme": "dark_github",
        "opt_log_color_levels": True,
        "opt_log_glyph_prefix": True,
        "opt_drive_state_glyph": True,
        "opt_tray_icon_enabled": True,
        "opt_show_splash": True,
    }
    win = _FakeWindow()
    tab = _make_tab(qtbot, cfg=cfg, window=win)
    tab._cb_color_levels.setChecked(False)
    tab._cb_glyph_prefix.setChecked(False)
    tab._cb_drive_glyph.setChecked(False)
    tab._cb_tray.setChecked(False)
    tab._cb_splash.setChecked(False)

    # Pre-apply: cfg still pristine.
    assert cfg["opt_log_color_levels"] is True

    tab.apply()
    assert cfg["opt_log_color_levels"] is False
    assert cfg["opt_log_glyph_prefix"] is False
    assert cfg["opt_drive_state_glyph"] is False
    assert cfg["opt_tray_icon_enabled"] is False
    assert cfg["opt_show_splash"] is False


def test_apply_saves_to_disk(qtbot):
    saved: list[dict] = []
    win = _FakeWindow()
    tab = _make_tab(
        qtbot, window=win,
        save_cfg=lambda c: saved.append(dict(c)),
    )
    tab._cb_color_levels.setChecked(False)
    tab.apply()
    assert saved and saved[-1]["opt_log_color_levels"] is False


# ---------------------------------------------------------------------------
# Cancel — reverts runtime via the snapshot.  cfg is untouched.
# ---------------------------------------------------------------------------


def test_cancel_reverts_runtime_via_live_hooks_without_touching_cfg(qtbot):
    """Cancel must re-fire each live-apply hook with the snapshotted
    value so the runtime widget follows.  cfg was never written
    during preview, so there's nothing to revert on the cfg side."""
    cfg = {
        "opt_pyside6_theme": "dark_github",
        "opt_log_color_levels": True,
        "opt_log_glyph_prefix": True,
        "opt_drive_state_glyph": True,
        "opt_tray_icon_enabled": True,
        "opt_show_splash": True,
    }
    win = _FakeWindow()
    tab = _make_tab(qtbot, cfg=cfg, window=win)

    # Toggle every checkbox OFF (preview).
    tab._cb_color_levels.setChecked(False)
    tab._cb_glyph_prefix.setChecked(False)
    tab._cb_drive_glyph.setChecked(False)
    tab._cb_tray.setChecked(False)
    tab._cb_splash.setChecked(False)

    # Cancel — runtime should revert; cfg was never written.
    tab.cancel()

    # cfg untouched throughout.
    assert cfg["opt_log_color_levels"] is True
    assert cfg["opt_log_glyph_prefix"] is True
    assert cfg["opt_drive_state_glyph"] is True
    assert cfg["opt_tray_icon_enabled"] is True
    assert cfg["opt_show_splash"] is True

    # Each live hook fired twice: once on toggle-off, once on
    # cancel-revert.  Final runtime state: True (restored).
    assert win.log_pane.color_calls == [False, True]
    assert win.log_pane.glyph_calls == [False, True]
    assert win._drive_handler.refresh_calls == 2
    assert win.tray_calls == [False, True]


def test_cancel_skips_unchanged_widgets(qtbot):
    """If the user opened the dialog and didn't change anything,
    cancel() must not fire any live-apply hook."""
    win = _FakeWindow()
    tab = _make_tab(qtbot, window=win)
    tab.cancel()
    assert win.log_pane.color_calls == []
    assert win.log_pane.glyph_calls == []
    assert win._drive_handler.refresh_calls == 0
    assert win.tray_calls == []


def test_no_window_degrades_gracefully(qtbot):
    """Without a ``window``, live-preview hooks no-op.  Toggling
    still updates the widget's checked state, and ``apply()``
    still writes to cfg + disk."""
    cfg = {"opt_tray_icon_enabled": True}
    tab = _make_tab(qtbot, cfg=cfg, window=None)
    tab._cb_tray.setChecked(False)
    # No live hook fired (no window), but the widget's state
    # tracked the user's intent.
    assert tab._cb_tray.isChecked() is False
    # cfg only changes on apply().
    assert cfg["opt_tray_icon_enabled"] is True
    tab.apply()
    assert cfg["opt_tray_icon_enabled"] is False
