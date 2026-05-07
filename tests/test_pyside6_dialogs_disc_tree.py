"""Phase 3c-iii — gui_qt.dialogs.disc_tree tests.

Pins the MVP disc-tree selector contract:

- Pure helpers (_format_title_label, _is_recommended) — Qt-free
- Multi-column header
- One row per title with the right column values
- Pre-select the recommended title
- Click anywhere on a row toggles its checkbox
- OK returns the list of selected IDs (matches insertion order)
- Cancel / Esc return None
- Empty disc_titles handled gracefully
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHeaderView

from gui_qt.dialogs.disc_tree import (
    _COL_CHAPTERS,
    _COL_DURATION,
    _COL_SIZE,
    _COL_STATUS,
    _COL_TITLE,
    _DiscTreeDialog,
    _classification_text,
    _format_title_label,
    _HEADERS,
    _is_recommended,
    show_disc_tree,
)


def _title(
    *,
    tid: int,
    name: str = "X",
    duration: str = "0:00",
    size: str = "0 GB",
    chapters: int = 0,
    recommended: bool = False,
    classification: str = "",
) -> dict:
    """Build a minimal disc title dict for tests."""
    return {
        "id": tid,
        "name": name,
        "duration": duration,
        "size": size,
        "chapters": chapters,
        "recommended": recommended,
        "classification": classification,
    }


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_format_title_label_zero_indexed_id():
    """``Title 1`` for id=0, etc.  Mirrors tkinter's ``t['id']+1``."""
    assert _format_title_label({"id": 0, "name": "Main"}) == "Title 1: Main"
    assert _format_title_label({"id": 5, "name": "X"}) == "Title 6: X"


def test_format_title_label_empty_name_falls_back():
    """Missing or empty name → ``(no name)`` fallback."""
    assert _format_title_label({"id": 2, "name": ""}) == "Title 3: (no name)"
    assert _format_title_label({"id": 2}) == "Title 3: (no name)"


def test_is_recommended_true_only_when_flag_set():
    assert _is_recommended({"recommended": True}) is True
    assert _is_recommended({"recommended": False}) is False
    assert _is_recommended({}) is False


def test_classification_text_uses_classification_first():
    """``classification`` key wins; fallback to ``status``; else empty."""
    assert _classification_text({"classification": "MAIN"}) == "MAIN"
    assert _classification_text({"status": "Recommended"}) == "Recommended"
    assert _classification_text({"classification": "EXTRA", "status": "Optional"}) == "EXTRA"
    assert _classification_text({}) == ""


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_dialog_chrome(qtbot):
    d = _DiscTreeDialog([_title(tid=0)], is_tv=False)
    qtbot.addWidget(d)
    assert d.objectName() == "discTreeDialog"
    assert "Disc Contents" in d.windowTitle()
    assert d.isModal()


def test_tree_has_expected_headers(qtbot):
    """Multi-column header — Title, Duration, Size, Chapters, Status."""
    d = _DiscTreeDialog([_title(tid=0)], is_tv=False)
    qtbot.addWidget(d)
    actual = [
        d._tree.headerItem().text(i) for i in range(d._tree.columnCount())
    ]
    assert actual == list(_HEADERS)


def test_tree_one_row_per_title(qtbot):
    titles = [_title(tid=i, name=f"T{i}") for i in range(5)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    assert d._tree.topLevelItemCount() == 5


def test_row_columns_populated(qtbot):
    """Each row's columns hold the right values."""
    titles = [_title(
        tid=2, name="Main Feature",
        duration="2:18:00", size="38.2 GB", chapters=28,
        classification="MAIN",
    )]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    item = d._tree.topLevelItem(0)
    assert item.text(_COL_TITLE) == "Title 3: Main Feature"
    assert item.text(_COL_DURATION) == "2:18:00"
    assert item.text(_COL_SIZE) == "38.2 GB"
    assert item.text(_COL_CHAPTERS) == "28"
    assert item.text(_COL_STATUS) == "MAIN"


def test_row_user_data_holds_title_id(qtbot):
    """The title ID is stashed as user-data on the column-0 cell so
    ``_selected_ids`` can retrieve it without re-parsing the label."""
    titles = [_title(tid=7, name="X")]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    item = d._tree.topLevelItem(0)
    assert item.data(_COL_TITLE, Qt.ItemDataRole.UserRole) == "7"


def test_recommended_title_is_pre_checked(qtbot):
    """The row marked ``recommended=True`` starts checked; others
    unchecked.  Pinned because the controller relies on this default."""
    titles = [
        _title(tid=0, name="Extra", recommended=False),
        _title(tid=1, name="Main", recommended=True),
        _title(tid=2, name="Trailer", recommended=False),
    ]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    states = {
        d._tree.topLevelItem(i).data(_COL_TITLE, Qt.ItemDataRole.UserRole):
        d._tree.topLevelItem(i).checkState(_COL_TITLE)
        for i in range(d._tree.topLevelItemCount())
    }
    assert states["1"] == Qt.CheckState.Checked
    assert states["0"] == Qt.CheckState.Unchecked
    assert states["2"] == Qt.CheckState.Unchecked


def test_no_recommended_means_no_pre_check(qtbot):
    """When no title has ``recommended=True``, every row starts
    unchecked.  Pinned because some discs have no clear MAIN."""
    titles = [_title(tid=i) for i in range(3)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    for i in range(3):
        assert d._tree.topLevelItem(i).checkState(_COL_TITLE) == Qt.CheckState.Unchecked


# ---------------------------------------------------------------------------
# Click toggling
# ---------------------------------------------------------------------------


def test_clicking_non_checkbox_column_toggles(qtbot):
    """Clicking on Duration / Size / etc. toggles the row's
    checkbox.  Mirrors the tkinter "click anywhere on the row" UX."""
    titles = [_title(tid=0, name="X", recommended=False)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    item = d._tree.topLevelItem(0)
    assert item.checkState(_COL_TITLE) == Qt.CheckState.Unchecked

    d._on_item_clicked(item, _COL_DURATION)
    assert item.checkState(_COL_TITLE) == Qt.CheckState.Checked

    d._on_item_clicked(item, _COL_SIZE)
    assert item.checkState(_COL_TITLE) == Qt.CheckState.Unchecked


def test_clicking_title_column_does_not_double_toggle(qtbot):
    """Column 0 has the native Qt checkbox; clicking it shouldn't
    double-toggle (Qt's built-in handler fires already)."""
    titles = [_title(tid=0, recommended=False)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    item = d._tree.topLevelItem(0)
    state_before = item.checkState(_COL_TITLE)
    d._on_item_clicked(item, _COL_TITLE)
    # Custom handler returns early; state unchanged by the handler.
    assert item.checkState(_COL_TITLE) == state_before


# ---------------------------------------------------------------------------
# Submit / cancel / Esc
# ---------------------------------------------------------------------------


def test_ok_returns_selected_ids_in_insertion_order(qtbot):
    """OK collects checked rows' IDs in the order the disc_titles
    list defined them — controllers may rely on this for ordering."""
    titles = [
        _title(tid=10, recommended=True),
        _title(tid=20, recommended=False),
        _title(tid=30, recommended=True),
    ]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    # Manually check the middle one too
    d._tree.topLevelItem(1).setCheckState(_COL_TITLE, Qt.CheckState.Checked)
    d._on_ok()
    assert d.result_value == ["10", "20", "30"]


def test_ok_with_no_selection_returns_empty_list(qtbot):
    """All-unchecked OK returns ``[]`` (empty list, not None).
    Pinned because the controller distinguishes "cancelled" (None)
    from "selected nothing" (empty list)."""
    titles = [_title(tid=0, recommended=False)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    d._on_ok()
    assert d.result_value == []


def test_cancel_returns_none(qtbot):
    titles = [_title(tid=0, recommended=True)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    d._on_cancel()
    assert d.result_value is None


def test_escape_cancels(qtbot):
    titles = [_title(tid=0, recommended=True)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert d.result_value is None


# ---------------------------------------------------------------------------
# Empty disc handling
# ---------------------------------------------------------------------------


def test_empty_disc_titles_constructs_cleanly(qtbot):
    """Empty input → dialog opens with no rows.  User can OK
    (returning []) or Cancel."""
    d = _DiscTreeDialog([], is_tv=False)
    qtbot.addWidget(d)
    assert d._tree.topLevelItemCount() == 0
    d._on_ok()
    assert d.result_value == []


def test_titles_without_id_are_skipped(qtbot):
    """Defensive — titles missing 'id' are skipped rather than
    crashing the dialog."""
    titles = [
        _title(tid=0, name="Has ID"),
        {"name": "No ID"},  # no 'id' key
        _title(tid=2, name="Also OK"),
    ]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    # 2 rows (the malformed one is skipped)
    assert d._tree.topLevelItemCount() == 2


# ---------------------------------------------------------------------------
# Public function smoke
# ---------------------------------------------------------------------------


def test_show_disc_tree_returns_value(qtbot, monkeypatch):
    """Public function: simulate user OK by monkeypatching exec."""
    def fake_exec(self):
        # Pre-select the second title
        self._tree.topLevelItem(1).setCheckState(_COL_TITLE, Qt.CheckState.Checked)
        self._on_ok()
        return 1

    monkeypatch.setattr(_DiscTreeDialog, "exec", fake_exec)

    titles = [_title(tid=0), _title(tid=1), _title(tid=2)]
    result = show_disc_tree(None, titles, is_tv=True)
    # Default-recommended is none, but our fake_exec checked id=1
    assert result == ["1"]


def test_show_disc_tree_returns_none_on_cancel(qtbot, monkeypatch):
    def fake_exec(self):
        self._on_cancel()
        return 0

    monkeypatch.setattr(_DiscTreeDialog, "exec", fake_exec)
    assert show_disc_tree(None, [_title(tid=0)], is_tv=False) is None


def test_show_disc_tree_accepts_preview_callback_signature(qtbot, monkeypatch):
    """Signature compatibility: callers pass a preview callback as a
    keyword arg.  Pinned that we don't reject or crash on the
    third positional arg.  (Whether the signal pathway actually
    delivers right-clicks is covered by the regression tests below.)"""
    monkeypatch.setattr(_DiscTreeDialog, "exec", lambda self: 0)
    callback_calls: list = []
    def cb(title_id):
        callback_calls.append(title_id)
    # Should not raise
    show_disc_tree(None, [_title(tid=0)], is_tv=False, preview_callback=cb)
    # exec() is monkeypatched to a no-op, so no right-click can be
    # delivered — callback_calls stays empty.
    assert callback_calls == []


# ---------------------------------------------------------------------------
# Right-click preview — signal-level regression
#
# The smoke bot caught a v1-blocking gap on 2026-05-04: the dialog
# defined ``_on_tree_context_menu`` but never connected it to
# ``customContextMenuRequested`` and never set
# ``ContextMenuPolicy.CustomContextMenu`` on the tree.  Tests passed
# because they all reached into ``trigger_preview_for_test`` (which
# calls the callback directly).  These regression tests exercise the
# live Qt signal pathway so the same gap can't reappear silently.
# ---------------------------------------------------------------------------


def test_tree_uses_custom_context_menu_policy(qtbot):
    """The tree's context-menu policy must be ``CustomContextMenu``;
    Qt's default ``DefaultContextMenu`` swallows right-clicks before
    they reach our handler."""
    d = _DiscTreeDialog([_title(tid=0)], is_tv=False, preview_callback=None)
    qtbot.addWidget(d)
    assert d._tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


def test_right_click_signal_invokes_preview_callback(qtbot):
    """Emitting ``customContextMenuRequested`` at a row's position
    must invoke the preview callback with that row's title ID.
    Mirrors what Qt does on a real right-click — proves the signal
    is connected, not just the handler defined."""
    titles = [_title(tid=42, name="Main Feature"), _title(tid=99, name="Extra")]
    callback_calls: list[int] = []
    d = _DiscTreeDialog(
        titles, is_tv=False, preview_callback=callback_calls.append,
    )
    qtbot.addWidget(d)
    d.show()  # Tree must be laid out for visualItemRect to be meaningful.

    # Right-click position over row 0.
    item = d._tree.topLevelItem(0)
    rect = d._tree.visualItemRect(item)
    pos = rect.center()
    d._tree.customContextMenuRequested.emit(pos)

    assert callback_calls == [42]


def test_right_click_on_empty_space_is_a_no_op(qtbot):
    """Right-click below the last row (where ``itemAt`` returns None)
    must NOT invoke the callback.  Pinned so a careless refactor
    can't make us preview a phantom title."""
    titles = [_title(tid=0)]
    callback_calls: list[int] = []
    d = _DiscTreeDialog(
        titles, is_tv=False, preview_callback=callback_calls.append,
    )
    qtbot.addWidget(d)
    d.show()

    # Far below any row — itemAt() returns None.
    from PySide6.QtCore import QPoint
    d._tree.customContextMenuRequested.emit(QPoint(20, 9999))

    assert callback_calls == []


def test_right_click_with_no_preview_callback_is_a_no_op(qtbot):
    """When the dialog is constructed without a preview callback,
    right-clicks must be swallowed silently.  This was the legacy
    behaviour and we keep it for the bulk-pick paths that don't
    care about preview."""
    d = _DiscTreeDialog(
        [_title(tid=0)], is_tv=False, preview_callback=None,
    )
    qtbot.addWidget(d)
    d.show()

    item = d._tree.topLevelItem(0)
    pos = d._tree.visualItemRect(item).center()
    # Should not raise.
    d._tree.customContextMenuRequested.emit(pos)
