"""Phase 3c-iii — gui_qt.dialogs.list_picker tests.

Pins the contract differences between ``show_extras_picker`` and
``show_file_list``:

* Pre-selection: extras pre-checks all, file_list pre-checks first.
* Return value on confirm: extras → ``list[int]``, file_list → ``list[str]``.
* Return value on cancel: extras → ``None``, file_list → ``[]``.

Plus shared behavior: Select All / Deselect All buttons, Esc cancels,
prompt label word-wraps.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QListWidget, QPushButton

from gui_qt.dialogs.list_picker import (
    _ListPickerDialog,
    show_extras_picker,
    show_file_list,
)


# ==========================================================================
# Construction / chrome
# ==========================================================================


def test_dialog_chrome(qtbot):
    d = _ListPickerDialog(
        "Pick One", "Choose:", ["a", "b"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    assert d.windowTitle() == "Pick One"
    assert d.objectName() == "listPickerDialog"
    assert d.isModal()


def test_empty_title_falls_back_to_default(qtbot):
    """Empty title uses the "Select" fallback so the window isn't
    titleless."""
    d = _ListPickerDialog(
        "", "P", ["a"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    assert d.windowTitle() == "Select"


def test_options_populate_list(qtbot):
    d = _ListPickerDialog(
        "T", "P", ["alpha", "beta", "gamma"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    assert d._list.count() == 3
    assert d._list.item(0).text() == "alpha"
    assert d._list.item(2).text() == "gamma"


def test_prompt_label_word_wraps(qtbot):
    """Long prompts must wrap rather than crop."""
    long_prompt = "very long prompt " * 30
    d = _ListPickerDialog(
        "T", long_prompt, ["a"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    from PySide6.QtWidgets import QLabel
    prompt_labels = [
        l for l in d.findChildren(QLabel)
        if l.objectName() == "stepSubtitle"
    ]
    assert len(prompt_labels) == 1
    assert prompt_labels[0].wordWrap()


# ==========================================================================
# Pre-selection — the critical difference between the two pickers
# ==========================================================================


def test_extras_pre_selects_all_items(qtbot):
    """``preselect='all'`` checks every option."""
    d = _ListPickerDialog(
        "T", "P", ["a", "b", "c", "d"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    selected = [d._list.item(i).isSelected() for i in range(d._list.count())]
    assert selected == [True, True, True, True]


def test_file_list_pre_selects_first_only(qtbot):
    """``preselect='first'`` checks only the first option."""
    d = _ListPickerDialog(
        "T", "P", ["a", "b", "c", "d"],
        preselect="first", return_mode="texts",
    )
    qtbot.addWidget(d)
    selected = [d._list.item(i).isSelected() for i in range(d._list.count())]
    assert selected == [True, False, False, False]


def test_pre_selection_with_empty_options(qtbot):
    """Empty options → no pre-selection, no crash."""
    d_extras = _ListPickerDialog(
        "T", "P", [],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d_extras)
    assert d_extras._list.count() == 0

    d_files = _ListPickerDialog(
        "T", "P", [],
        preselect="first", return_mode="texts",
    )
    qtbot.addWidget(d_files)
    assert d_files._list.count() == 0


# ==========================================================================
# Helper buttons — Select All / Deselect All
# ==========================================================================


def test_select_all_button_checks_every_item(qtbot):
    """Even after manual deselection, Select All re-checks every row."""
    d = _ListPickerDialog(
        "T", "P", ["a", "b", "c"],
        preselect="first", return_mode="texts",
    )
    qtbot.addWidget(d)
    # Currently only [0] is selected
    d._select_all_btn.click()
    selected = [d._list.item(i).isSelected() for i in range(d._list.count())]
    assert selected == [True, True, True]


def test_deselect_all_button_clears_selection(qtbot):
    d = _ListPickerDialog(
        "T", "P", ["a", "b", "c"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    d._deselect_all_btn.click()
    selected = [d._list.item(i).isSelected() for i in range(d._list.count())]
    assert selected == [False, False, False]


# ==========================================================================
# Gather selection — internal helper
# ==========================================================================


def test_gather_selection_collects_indices_and_texts(qtbot):
    """Both indices and texts are collected; downstream choosing
    happens in the public functions per ``return_mode``."""
    d = _ListPickerDialog(
        "T", "P", ["alpha", "beta", "gamma"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    # Deselect "beta" (index 1)
    d._list.item(1).setSelected(False)
    d._gather_selection()
    assert d.selection_indices == [0, 2]
    assert d.selection_texts == ["alpha", "gamma"]


# ==========================================================================
# Confirm / Cancel / Esc state
# ==========================================================================


def test_confirm_sets_confirmed_true(qtbot):
    d = _ListPickerDialog(
        "T", "P", ["a"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    d._on_confirm()
    assert d.confirmed is True
    assert d.result() == 1  # accepted


def test_cancel_sets_confirmed_false(qtbot):
    d = _ListPickerDialog(
        "T", "P", ["a"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    d._on_cancel()
    assert d.confirmed is False
    assert d.result() == 0  # rejected


def test_escape_key_cancels(qtbot):
    d = _ListPickerDialog(
        "T", "P", ["a"],
        preselect="all", return_mode="indices",
    )
    qtbot.addWidget(d)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert d.confirmed is False


# ==========================================================================
# show_extras_picker — public function contract
# ==========================================================================


def test_show_extras_picker_returns_indices_on_confirm(qtbot, monkeypatch):
    def fake_exec(self):
        self._on_confirm()
        return 1

    monkeypatch.setattr(_ListPickerDialog, "exec", fake_exec)
    result = show_extras_picker(None, "T", "P", ["a", "b", "c"])
    # All pre-selected → all indices returned
    assert result == [0, 1, 2]


def test_show_extras_picker_returns_user_selection_subset(qtbot, monkeypatch):
    """If the user deselects some, we get the surviving indices."""
    def fake_exec(self):
        # Deselect index 1
        self._list.item(1).setSelected(False)
        self._on_confirm()
        return 1

    monkeypatch.setattr(_ListPickerDialog, "exec", fake_exec)
    result = show_extras_picker(None, "T", "P", ["a", "b", "c"])
    assert result == [0, 2]


def test_show_extras_picker_returns_none_on_cancel(qtbot, monkeypatch):
    """Critical: extras_picker returns None (not []) on cancel —
    controller uses ``if chosen is None`` for cancel detection."""
    def fake_exec(self):
        self._on_cancel()
        return 0

    monkeypatch.setattr(_ListPickerDialog, "exec", fake_exec)
    result = show_extras_picker(None, "T", "P", ["a", "b"])
    assert result is None


def test_show_extras_picker_with_empty_options_confirm(qtbot, monkeypatch):
    """Empty options → confirm returns []; cancel returns None.
    Distinguishable from the cancel case by the controller."""
    def fake_exec(self):
        self._on_confirm()
        return 1

    monkeypatch.setattr(_ListPickerDialog, "exec", fake_exec)
    result = show_extras_picker(None, "T", "P", [])
    assert result == []  # not None


# ==========================================================================
# show_file_list — public function contract
# ==========================================================================


def test_show_file_list_returns_texts_on_confirm(qtbot, monkeypatch):
    """Returns list of selected texts (not indices)."""
    def fake_exec(self):
        # Default: only index 0 ("a.mkv") is pre-selected
        self._on_confirm()
        return 1

    monkeypatch.setattr(_ListPickerDialog, "exec", fake_exec)
    result = show_file_list(None, "T", "P", ["a.mkv", "b.mkv", "c.mkv"])
    assert result == ["a.mkv"]


def test_show_file_list_returns_empty_list_on_cancel(qtbot, monkeypatch):
    """Critical: file_list returns [] (not None) on cancel —
    controller uses ``if not selected`` to detect both empty
    selection and cancel."""
    def fake_exec(self):
        self._on_cancel()
        return 0

    monkeypatch.setattr(_ListPickerDialog, "exec", fake_exec)
    result = show_file_list(None, "T", "P", ["a.mkv", "b.mkv"])
    assert result == []  # NOT None
    assert result is not None


def test_show_file_list_returns_multiple_selections(qtbot, monkeypatch):
    """Despite the name, file_list supports multi-select."""
    def fake_exec(self):
        # Add second item to selection
        self._list.item(2).setSelected(True)
        self._on_confirm()
        return 1

    monkeypatch.setattr(_ListPickerDialog, "exec", fake_exec)
    result = show_file_list(None, "T", "P", ["a", "b", "c"])
    assert result == ["a", "c"]
