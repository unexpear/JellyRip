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
    _COL_NAME,
    _COL_NUM,
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


def test_format_title_label_zero_indexed_id_with_file_token():
    """``Title 1`` for id=0, plus the ``_tNN.mkv`` token that matches
    the rip file (id is the MakeMKV index, not the 1-based number)."""
    assert _format_title_label({"id": 0, "name": "Main"}) == "Title 1: Main  ·  _t00.mkv"
    assert _format_title_label({"id": 5, "name": "X"}) == "Title 6: X  ·  _t05.mkv"


def test_format_title_label_generic_name_not_duplicated():
    """Unlabeled discs name every title "Title {n+1}"; don't echo it as
    "Title 5: Title 5" — just show the head + the file token.  This is
    the user-reported "scan names don't match rip names" case."""
    assert _format_title_label({"id": 4, "name": "Title 5"}) == "Title 5  ·  _t04.mkv"
    assert _format_title_label({"id": 2, "name": ""}) == "Title 3  ·  _t02.mkv"
    assert _format_title_label({"id": 2}) == "Title 3  ·  _t02.mkv"


def test_format_title_label_real_name_kept_with_token():
    """A genuine disc-supplied name is shown, with the file token."""
    assert (
        _format_title_label({"id": 10, "name": "Play All"})
        == "Title 11: Play All  ·  _t10.mkv"
    )


def test_tv_picker_rows_sorted_by_title_number(qtbot):
    """TV discs list titles in number order (1, 2, 3 …) even when the
    scan hands them in longest-first order — so the picker reads
    naturally and lines up with the rip filenames (2026-06-13)."""
    # Scan order: a long extra first, then episodes out of order.
    titles = [
        _title(tid=10, duration="0:53:50"),  # play-all / extra
        _title(tid=2),
        _title(tid=0),
        _title(tid=5),
    ]
    d = _DiscTreeDialog(titles, is_tv=True)
    qtbot.addWidget(d)
    order = [
        d._tree.topLevelItem(i).data(_COL_TITLE, Qt.ItemDataRole.UserRole)
        for i in range(d._tree.topLevelItemCount())
    ]
    assert order == ["0", "2", "5", "10"]  # ascending by title id


def test_movie_picker_keeps_scan_order(qtbot):
    """Movies keep the scan's longest-first order (main feature on top,
    pre-checked) — only TV is re-sorted by number."""
    titles = [_title(tid=10), _title(tid=2), _title(tid=0)]
    d = _DiscTreeDialog(titles, is_tv=False)
    qtbot.addWidget(d)
    order = [
        d._tree.topLevelItem(i).data(_COL_TITLE, Qt.ItemDataRole.UserRole)
        for i in range(d._tree.topLevelItemCount())
    ]
    assert order == ["10", "2", "0"]  # unchanged from input


def test_format_title_label_prefers_real_output_name():
    """When the scan captured MakeMKV's real output filename
    (``output_name``, e.g. "B1_t10.mkv"), show THAT instead of the
    predicted ``_tNN.mkv`` — the A1_/B1_ prefix isn't predictable, so
    the real name is what lines the picker up with the ripped files
    (2026-06-13 user request: show both Title N and the disc name)."""
    assert (
        _format_title_label({"id": 10, "name": "Title 11", "output_name": "B1_t10.mkv"})
        == "Title 11  ·  B1_t10.mkv"
    )
    # No output_name → fall back to the predicted token.
    assert (
        _format_title_label({"id": 10, "name": "Title 11"})
        == "Title 11  ·  _t10.mkv"
    )


def test_is_recommended_true_only_when_flag_set():
    assert _is_recommended({"recommended": True}) is True
    assert _is_recommended({"recommended": False}) is False
    assert _is_recommended({}) is False


# ---------------------------------------------------------------------------
# Per-title episode naming (2026-06-13) — name each title in the picker;
# the name becomes the saved file's episode name.
# ---------------------------------------------------------------------------


def test_name_column_shown_for_tv_hidden_for_movie(qtbot):
    """The editable "Episode name" column is for TV episodes only; a
    movie disc names by title/year, so the column is hidden there."""
    tv = _DiscTreeDialog([_title(tid=0)], is_tv=True)
    qtbot.addWidget(tv)
    assert not tv._tree.isColumnHidden(_COL_NAME)

    movie = _DiscTreeDialog([_title(tid=0)], is_tv=False)
    qtbot.addWidget(movie)
    assert movie._tree.isColumnHidden(_COL_NAME)


def test_episode_names_collects_typed_names_by_int_id(qtbot):
    """What the user types in the name cell is returned keyed by the
    integer title id — that's what the move step maps to each file."""
    d = _DiscTreeDialog([_title(tid=2), _title(tid=5)], is_tv=True)
    qtbot.addWidget(d)
    # Simulate the inline editor committing text into the name cells.
    d._items_by_id["2"].setText(_COL_NAME, "Pilot")
    d._items_by_id["5"].setText(_COL_NAME, "  The Big One  ")  # trimmed
    names = d.episode_names()
    assert names == {2: "Pilot", 5: "The Big One"}


def test_episode_names_skips_blank_rows(qtbot):
    d = _DiscTreeDialog([_title(tid=0), _title(tid=1)], is_tv=True)
    qtbot.addWidget(d)
    d._items_by_id["0"].setText(_COL_NAME, "Named")
    # tid 1 left blank → omitted entirely.
    assert d.episode_names() == {0: "Named"}


def test_episode_names_empty_for_movie(qtbot):
    """The name column is hidden for movies, so no names come back even
    if a cell somehow holds text."""
    d = _DiscTreeDialog([_title(tid=0)], is_tv=False)
    qtbot.addWidget(d)
    d._items_by_id["0"].setText(_COL_NAME, "ignored")
    assert d.episode_names() == {}


def test_on_ok_captures_ids_and_names(qtbot):
    """Hitting OK snapshots both the checked ids and the typed names so
    the caller (run_disc_tree) can read them after the dialog closes."""
    d = _DiscTreeDialog([_title(tid=3), _title(tid=7)], is_tv=True)
    qtbot.addWidget(d)
    d._items_by_id["3"].setCheckState(_COL_TITLE, Qt.CheckState.Checked)
    d._items_by_id["3"].setText(_COL_NAME, "Episode A")
    d._on_ok()
    assert d.result_value == ["3"]
    assert d.episode_names_value == {3: "Episode A"}


# ---------------------------------------------------------------------------
# Per-title episode numbering (2026-06-13) — set each title's episode
# number in the picker (next to its duration/size); blank = an extra.
# ---------------------------------------------------------------------------


def test_number_column_shown_for_tv_hidden_for_movie(qtbot):
    """The editable "Ep #" column is for TV only — movies number by
    title/year, so it's hidden there."""
    tv = _DiscTreeDialog([_title(tid=0)], is_tv=True)
    qtbot.addWidget(tv)
    assert not tv._tree.isColumnHidden(_COL_NUM)

    movie = _DiscTreeDialog([_title(tid=0)], is_tv=False)
    qtbot.addWidget(movie)
    assert movie._tree.isColumnHidden(_COL_NUM)


def test_tv_episode_numbers_blank_until_typed(qtbot):
    """No auto-fill (2026-06-13): TV rows start with an empty Ep # — you
    type each number yourself, and a row left blank stays an extra."""
    d = _DiscTreeDialog(
        [_title(tid=2), _title(tid=0), _title(tid=5)], is_tv=True,
    )
    qtbot.addWidget(d)
    assert d.episode_numbers() == {}


def test_episode_numbers_reads_edited_cells(qtbot):
    """Editing the Ep # cell changes what's reported; a cleared cell
    drops out (that title is treated as an extra)."""
    d = _DiscTreeDialog(
        [_title(tid=0), _title(tid=1), _title(tid=2)], is_tv=True,
    )
    qtbot.addWidget(d)
    d._items_by_id["0"].setText(_COL_NUM, "4")
    d._items_by_id["1"].setText(_COL_NUM, "3")
    d._items_by_id["2"].setText(_COL_NUM, "")  # extra → omitted
    assert d.episode_numbers() == {0: 4, 1: 3}


def test_episode_numbers_empty_for_movie(qtbot):
    """The Ep # column is hidden for movies, so no numbers come back."""
    d = _DiscTreeDialog([_title(tid=0)], is_tv=False)
    qtbot.addWidget(d)
    assert d.episode_numbers() == {}


def test_on_ok_captures_numbers(qtbot):
    """OK snapshots the typed numbers too, so run_disc_tree can read
    them after the dialog closes (alongside ids and names)."""
    d = _DiscTreeDialog([_title(tid=3)], is_tv=True)
    qtbot.addWidget(d)
    d._items_by_id["3"].setText(_COL_NUM, "9")
    d._on_ok()
    assert d.episode_numbers_value == {3: 9}


def test_picker_cell_clipboard_helpers(qtbot):
    """Right-click Cut/Copy/Paste on an editable cell moves text via the
    clipboard (whole-cell), collapsing any pasted newlines to spaces."""
    from PySide6.QtWidgets import QApplication

    d = _DiscTreeDialog([_title(tid=0), _title(tid=1)], is_tv=True)
    qtbot.addWidget(d)
    a = d._items_by_id["0"]
    b = d._items_by_id["1"]
    a.setText(_COL_NAME, "Pilot")

    d._cell_copy(a, _COL_NAME)
    assert QApplication.clipboard().text() == "Pilot"

    d._cell_paste(b, _COL_NAME)
    assert b.text(_COL_NAME) == "Pilot"

    d._cell_cut(a, _COL_NAME)
    assert a.text(_COL_NAME) == ""
    assert QApplication.clipboard().text() == "Pilot"

    # Multi-line clipboard collapses to a single-line cell value.
    QApplication.clipboard().setText("Line1\nLine2")
    d._cell_paste(b, _COL_NAME)
    assert b.text(_COL_NAME) == "Line1 Line2"


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
    assert item.text(_COL_TITLE) == "Title 3: Main Feature  ·  _t02.mkv"
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
