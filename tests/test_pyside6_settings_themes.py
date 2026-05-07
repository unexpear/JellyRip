"""Phase 3d — gui_qt.settings.tab_appearance tests.

Pins (post 2026-05-04 Appearance-tab consolidation):
- Pure helpers (normalize_theme_choice, format_theme_label).
- Tab construction + initial selection from cfg.
- Click-to-apply: selection swaps QSS instantly (no Apply button).
- OK: persists every cfg key.
- Cancel: walks the snapshot and reverts every change.
- Disk-only themes (no Python metadata) still surface.
- SettingsDialog has only OK + Cancel (no Apply button as of
  2026-05-04 — every control is click-to-apply).

Tests for the new Appearance-tab checkboxes (color, glyph, drive,
tray, splash) live in
``test_pyside6_settings_appearance_checkboxes.py``.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt

from gui_qt.settings import AppearanceTab, SettingsDialog, ThemesTab
from gui_qt.settings.tab_appearance import (
    format_theme_label,
    normalize_theme_choice,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_normalize_passes_through_known_choice():
    assert normalize_theme_choice("frost", ["dark_github", "frost"]) == "frost"


def test_normalize_falls_back_to_dark_github():
    """Missing/unknown choice → dark_github when available."""
    assert normalize_theme_choice("nonexistent", ["dark_github", "frost"]) == "dark_github"
    assert normalize_theme_choice(None, ["dark_github", "frost"]) == "dark_github"
    assert normalize_theme_choice("", ["dark_github", "frost"]) == "dark_github"


def test_normalize_falls_back_to_first_when_no_dark_github():
    """If dark_github isn't on disk, pick the first available."""
    assert normalize_theme_choice("nonexistent", ["frost", "slate"]) == "frost"


def test_normalize_returns_empty_when_no_themes():
    """Defensive — no themes available → empty string."""
    assert normalize_theme_choice("dark_github", []) == ""


def test_format_label_known_theme():
    """Known themes show "Name — family"."""
    label = format_theme_label("dark_github")
    assert "Dark GitHub" in label
    assert "dark" in label


def test_format_label_unknown_theme_falls_back_to_id():
    """Unknown themes (e.g., custom QSS on disk) show their ID."""
    assert format_theme_label("custom_user_theme") == "custom_user_theme"


# ---------------------------------------------------------------------------
# Tab construction
# ---------------------------------------------------------------------------


def test_tab_lists_known_themes(qtbot):
    """The picker shows one row per theme available on disk."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    available = ["dark_github", "light_inverted", "frost"]
    tab = ThemesTab(cfg, lambda: available, lambda n: None)
    qtbot.addWidget(tab)
    assert tab._list.count() == 3


def test_tab_initial_selection_matches_cfg(qtbot):
    """Cfg's current theme drives the initial selection."""
    cfg = {"opt_pyside6_theme": "frost"}
    tab = ThemesTab(
        cfg, lambda: ["dark_github", "frost", "slate"], lambda n: None,
    )
    qtbot.addWidget(tab)
    assert tab.selected_theme_id() == "frost"


def test_tab_initial_selection_falls_back_when_cfg_unknown(qtbot):
    """Unknown cfg theme → falls back to dark_github."""
    cfg = {"opt_pyside6_theme": "nonexistent"}
    tab = ThemesTab(
        cfg, lambda: ["dark_github", "frost"], lambda n: None,
    )
    qtbot.addWidget(tab)
    assert tab.selected_theme_id() == "dark_github"


def test_tab_disk_only_theme_still_listed(qtbot):
    """A QSS file on disk that isn't in Python THEMES still shows
    up in the picker so users can select it."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    available = ["dark_github", "user_custom"]  # user_custom not in THEMES
    tab = ThemesTab(cfg, lambda: available, lambda n: None)
    qtbot.addWidget(tab)
    # 2 rows — both themes
    assert tab._list.count() == 2


def test_tab_notes_label_shows_subtitle_for_known_theme(qtbot):
    """The notes label below the list shows the highlighted theme's
    subtitle + notes (helps users understand each option)."""
    cfg = {"opt_pyside6_theme": "frost"}
    tab = ThemesTab(
        cfg, lambda: ["dark_github", "frost"], lambda n: None,
    )
    qtbot.addWidget(tab)
    notes = tab._notes_label.text()
    # Frost's subtitle is "Muted Nordic dark"
    assert "Muted Nordic dark" in notes


# ---------------------------------------------------------------------------
# Click-to-apply (theme) + OK/Cancel
#
# Updated 2026-05-04 for the Appearance-tab consolidation.  Previous
# behavior: ``apply()`` did runtime swap + cfg write, and the dialog
# had an Apply button.  New behavior: selecting a theme row in the
# list IS the apply (live preview); ``apply()`` just persists to
# disk, the Apply button is gone, and Cancel walks the snapshot.
# ---------------------------------------------------------------------------


def _select_theme(tab, theme_id):
    for i in range(tab._list.count()):
        if tab._list.item(i).data(Qt.ItemDataRole.UserRole) == theme_id:
            tab._list.setCurrentRow(i)
            return
    raise AssertionError(f"theme {theme_id!r} not in list")


def test_clicking_a_theme_swaps_qss_live(qtbot):
    """Selecting a row swaps the QSS at runtime via ``load_theme``.
    Pure preview — ``cfg`` is **not** modified.  cfg only changes
    when the user clicks OK (which calls ``apply()``)."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    loaded: list[str] = []
    tab = AppearanceTab(
        cfg,
        list_themes=lambda: ["dark_github", "frost"],
        load_theme=loaded.append,
    )
    qtbot.addWidget(tab)

    _select_theme(tab, "frost")

    assert loaded == ["frost"]            # runtime swapped
    assert cfg["opt_pyside6_theme"] == "dark_github"  # cfg untouched


def test_clicking_a_theme_does_not_save_until_ok(qtbot):
    """Selection only swaps runtime; neither cfg nor disk are
    written until ``apply()`` (the OK path)."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    saved: list[dict] = []
    tab = AppearanceTab(
        cfg,
        list_themes=lambda: ["dark_github", "frost"],
        load_theme=lambda n: None,
        save_cfg=lambda c: saved.append(dict(c)),
    )
    qtbot.addWidget(tab)

    _select_theme(tab, "frost")
    assert saved == []                                # no disk write
    assert cfg["opt_pyside6_theme"] == "dark_github"  # cfg untouched

    tab.apply()
    assert cfg["opt_pyside6_theme"] == "frost"        # cfg now updated
    assert saved and saved[-1]["opt_pyside6_theme"] == "frost"


def test_select_with_empty_list_is_noop(qtbot):
    """Empty theme list → nothing to select, no load_theme call."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    loaded: list[str] = []
    tab = AppearanceTab(cfg, lambda: [], loaded.append)
    qtbot.addWidget(tab)
    assert loaded == []
    assert cfg["opt_pyside6_theme"] == "dark_github"


def test_load_theme_failure_during_preview_leaves_cfg_alone(qtbot):
    """If load_theme raises during preview, cfg is unchanged
    (it's never written during preview anyway)."""
    cfg = {"opt_pyside6_theme": "dark_github"}

    def boom(name: str) -> None:
        raise RuntimeError("qss broken")

    tab = AppearanceTab(
        cfg, lambda: ["dark_github", "frost"], boom,
    )
    qtbot.addWidget(tab)
    _select_theme(tab, "frost")
    assert cfg["opt_pyside6_theme"] == "dark_github"


def test_cancel_reloads_original_theme(qtbot):
    """If the user previewed a theme and then cancels, cancel()
    reloads the original via ``load_theme``.  cfg was never
    written during preview, so no cfg revert is needed."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    loaded: list[str] = []
    tab = AppearanceTab(
        cfg, lambda: ["dark_github", "frost"], loaded.append,
    )
    qtbot.addWidget(tab)
    _select_theme(tab, "frost")
    assert cfg["opt_pyside6_theme"] == "dark_github"  # untouched

    tab.cancel()
    # load sequence: ["frost"] from the preview, then
    # ["dark_github"] from cancel reverting.
    assert loaded == ["frost", "dark_github"]
    assert cfg["opt_pyside6_theme"] == "dark_github"


def test_cancel_without_preview_is_noop(qtbot):
    """Cancel after no preview-changes does nothing — neither
    runtime nor cfg are touched."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    loaded: list[str] = []
    tab = AppearanceTab(
        cfg, lambda: ["dark_github", "frost"], loaded.append,
    )
    qtbot.addWidget(tab)
    tab.cancel()
    assert loaded == []
    assert cfg["opt_pyside6_theme"] == "dark_github"


# ---------------------------------------------------------------------------
# SettingsDialog buttons
# ---------------------------------------------------------------------------


def test_dialog_has_no_apply_button(qtbot):
    """Apply button removed 2026-05-04 — every control on the
    Appearance tab applies live, so Apply was redundant.  Pinned
    so a future refactor can't quietly add it back."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    d = SettingsDialog(
        cfg, lambda: ["dark_github"], lambda n: None,
    )
    qtbot.addWidget(d)
    assert not hasattr(d, "_apply_btn")
    # Defensive: also make sure no QPushButton in the dialog has
    # the text "Apply".
    from PySide6.QtWidgets import QPushButton
    for btn in d.findChildren(QPushButton):
        assert btn.text() != "Apply"


def test_dialog_ok_commits_and_accepts(qtbot):
    """OK reads every widget, writes to cfg, persists, accepts.
    The runtime QSS swap already happened on selection click."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    loaded: list[str] = []
    saved: list[dict] = []
    d = SettingsDialog(
        cfg,
        lambda: ["dark_github", "frost"],
        loaded.append,
        save_cfg=lambda c: saved.append(dict(c)),
    )
    qtbot.addWidget(d)
    _select_theme(d.appearance_tab, "frost")
    assert cfg["opt_pyside6_theme"] == "dark_github"  # not yet written

    d._ok_btn.click()
    assert cfg["opt_pyside6_theme"] == "frost"        # OK wrote cfg
    assert loaded == ["frost"]                        # from the click
    assert saved and saved[-1]["opt_pyside6_theme"] == "frost"
    assert d.result() == 1  # accepted


def test_dialog_cancel_reverts_runtime_and_rejects(qtbot):
    """Cancel reverts any previewed theme via ``load_theme(original)``
    and rejects the dialog.  cfg was never written during preview,
    so there's nothing to roll back on the cfg side."""
    cfg = {"opt_pyside6_theme": "dark_github"}
    loaded: list[str] = []
    d = SettingsDialog(
        cfg, lambda: ["dark_github", "frost"], loaded.append,
    )
    qtbot.addWidget(d)
    _select_theme(d.appearance_tab, "frost")
    assert cfg["opt_pyside6_theme"] == "dark_github"  # untouched

    d._cancel_btn.click()
    assert cfg["opt_pyside6_theme"] == "dark_github"  # still untouched
    assert d.result() == 0  # rejected
    assert loaded == ["frost", "dark_github"]


def test_dialog_escape_cancels(qtbot):
    cfg = {"opt_pyside6_theme": "dark_github"}
    d = SettingsDialog(
        cfg, lambda: ["dark_github"], lambda n: None,
    )
    qtbot.addWidget(d)
    from PySide6.QtGui import QKeyEvent
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert d.result() == 0
