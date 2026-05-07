"""Sub-phase 3b — Step 4 (``show_extras_classification``) port tests.

Pins the PySide6 implementation of the wizard's extras-classification
step:

- Pure helper ``_build_extras_assignment`` aggregation (no Qt needed)
- Empty-titles passthrough (returns ``ExtrasAssignment()``, no dialog)
- Default category is ``"Extras"`` per row
- Combo box populated from ``JELLYFIN_EXTRAS_CATEGORIES``
- Submit aggregates each row's combo selection into ``ExtrasAssignment``
- Cancel / Esc → returns ``None``
- Theming hooks: ``stepHeader``, ``stepSubtitle``, ``confirmButton``,
  ``cancelButton``, ``extrasCategoryCombo``, ``classifiedTitleRow``
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QComboBox, QPushButton

from gui_qt.setup_wizard import (
    ExtrasAssignment,
    JELLYFIN_EXTRAS_CATEGORIES,
    _build_extras_assignment,
    _ExtrasClassificationDialog,
    show_extras_classification,
)


# --------------------------------------------------------------------------
# Fakes — minimal ClassifiedTitle-like shape for testing
# --------------------------------------------------------------------------


@dataclass
class _FakeTitle:
    title_id: int
    label: str
    title: dict


def _extra(
    tid: int,
    *,
    duration_seconds: int = 720,
    size_bytes: int = 200_000_000,
) -> _FakeTitle:
    """Build a ``ClassifiedTitle``-shaped fake suitable for the dialog."""
    return _FakeTitle(
        title_id=tid,
        label="EXTRA",
        title={
            "duration_seconds": duration_seconds,
            "size_bytes": size_bytes,
            "name": f"Extra {tid + 1}",
        },
    )


# ==========================================================================
# Helper-only tests — no Qt needed, covered by AST + unit logic
# ==========================================================================


def test_build_extras_assignment_with_explicit_choices():
    """Each row's combo selection lands in the assignments map keyed by
    title_id.  This is the primary aggregation contract."""
    extras = [_extra(0), _extra(1), _extra(2)]
    choices = {0: "Behind The Scenes", 1: "Deleted Scenes", 2: "Trailers"}
    result = _build_extras_assignment(extras, choices)
    assert isinstance(result, ExtrasAssignment)
    assert result.assignments == {
        0: "Behind The Scenes",
        1: "Deleted Scenes",
        2: "Trailers",
    }


def test_build_extras_assignment_falls_back_to_default():
    """If a row's choice is missing from ``row_choices``, it gets the
    default category (``"Extras"``).  Defends against widget desync."""
    extras = [_extra(0), _extra(1)]
    choices = {0: "Featurettes"}  # row 1 missing
    result = _build_extras_assignment(extras, choices)
    assert result.assignments == {0: "Featurettes", 1: "Extras"}


def test_build_extras_assignment_empty_choice_falls_back():
    """An explicit empty string also routes to default — pins the
    belt-and-suspenders defense in ``_build_extras_assignment``."""
    extras = [_extra(0)]
    result = _build_extras_assignment(extras, {0: ""})
    assert result.assignments == {0: "Extras"}


def test_build_extras_assignment_empty_titles_returns_empty():
    """Zero titles → empty assignments dict, no errors."""
    result = _build_extras_assignment([], {})
    assert isinstance(result, ExtrasAssignment)
    assert result.assignments == {}


def test_show_extras_classification_with_empty_titles_skips_dialog():
    """Empty extras list → return ``ExtrasAssignment()`` without
    constructing the dialog (matches tkinter shortcut, line 574-575
    of gui/setup_wizard.py)."""
    # Passing parent=None — the function shouldn't even reach the
    # parent-typecheck if it returns early.
    result = show_extras_classification(None, [])
    assert isinstance(result, ExtrasAssignment)
    assert result.assignments == {}


# ==========================================================================
# Dialog construction tests — pytest-qt qtbot fixture
# ==========================================================================


def test_dialog_window_title_and_modal(qtbot):
    """Step 4 dialog must be modal (matches tkinter ``grab_set``) and
    titled so users in screen readers know which step they're on."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Extras Classification"
    assert dialog.isModal()
    assert dialog.objectName() == "wizardDialog"


def test_dialog_step_header_objectname(qtbot):
    """The Step 4 header has ``stepHeader`` / ``stepSubtitle``
    objectNames so QSS can target them.  Same hooks as Steps 1, 3, 5."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    headers = dialog.findChildren(type(dialog.findChild(object)))  # any QObject
    # Find the actual step header label by objectName.
    from PySide6.QtWidgets import QLabel
    labels = dialog.findChildren(QLabel)
    object_names = {lbl.objectName() for lbl in labels}
    assert "stepHeader" in object_names
    assert "stepSubtitle" in object_names


def test_dialog_creates_one_combo_per_extra(qtbot):
    """Each extra title produces exactly one ``QComboBox``.  The combo
    is the per-row category picker; if the count is wrong, rows lost
    their picker or got duplicates."""
    extras = [_extra(0), _extra(1), _extra(2), _extra(3)]
    dialog = _ExtrasClassificationDialog(extras)
    qtbot.addWidget(dialog)
    combos = dialog.findChildren(QComboBox)
    assert len(combos) == len(extras)


def test_dialog_combo_default_is_extras(qtbot):
    """Default category is ``"Extras"`` per row.  Matches tkinter's
    ``StringVar(value="Extras")`` and is the safe non-committal pick."""
    extras = [_extra(0), _extra(1)]
    dialog = _ExtrasClassificationDialog(extras)
    qtbot.addWidget(dialog)
    combos = dialog.findChildren(QComboBox)
    for combo in combos:
        assert combo.currentText() == "Extras"


def test_dialog_combo_items_match_jellyfin_categories(qtbot):
    """Each combo's item list is exactly ``JELLYFIN_EXTRAS_CATEGORIES``,
    in declaration order.  Pins the source-of-truth import."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    combo = dialog.findChildren(QComboBox)[0]
    items = [combo.itemText(i) for i in range(combo.count())]
    assert items == list(JELLYFIN_EXTRAS_CATEGORIES)


def test_dialog_combo_objectname_for_theming(qtbot):
    """Per-row combos get ``extrasCategoryCombo`` objectName so QSS
    can target this specific control if needed."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    combo = dialog.findChildren(QComboBox)[0]
    assert combo.objectName() == "extrasCategoryCombo"


def test_dialog_buttons_have_object_names(qtbot):
    """``confirmButton`` (green Next), ``cancelButton`` (muted Cancel)
    must exist with those exact objectNames so the QSS go/cancel
    coloring applies.  Drift guard for the role-to-objectName
    contract used by ``tools/build_qss.py``."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    buttons = dialog.findChildren(QPushButton)
    object_names = {btn.objectName() for btn in buttons}
    assert "confirmButton" in object_names
    assert "cancelButton" in object_names


def test_dialog_confirm_button_is_default(qtbot):
    """Pressing Enter in the dialog should trigger Next, matching the
    tkinter ``win.bind("<Return>", _submit)``.  The Qt equivalent is
    ``QPushButton.setDefault(True)`` on the confirm button."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    confirm = next(
        b for b in dialog.findChildren(QPushButton)
        if b.objectName() == "confirmButton"
    )
    assert confirm.isDefault()


def test_dialog_row_objectname_for_theming(qtbot):
    """Each row gets ``classifiedTitleRow`` objectName — same as
    Steps 1 / 3 — so the row backgrounds and dividers are themed
    consistently across the wizard."""
    dialog = _ExtrasClassificationDialog([_extra(0), _extra(1)])
    qtbot.addWidget(dialog)
    from PySide6.QtWidgets import QFrame
    rows = [
        f for f in dialog.findChildren(QFrame)
        if f.objectName() == "classifiedTitleRow"
    ]
    assert len(rows) == 2


# ==========================================================================
# Submit / cancel / Esc behavior
# ==========================================================================


def test_submit_aggregates_combo_selections(qtbot):
    """Clicking Next gathers each combo's currentText into the result."""
    extras = [_extra(0), _extra(1), _extra(2)]
    dialog = _ExtrasClassificationDialog(extras)
    qtbot.addWidget(dialog)

    combos = dialog.findChildren(QComboBox)
    # Pick distinctive non-default categories for each row so we can
    # tell whether the submission actually reads them.
    combos[0].setCurrentText("Behind The Scenes")
    combos[1].setCurrentText("Trailers")
    # Leave combos[2] at default "Extras"

    dialog._submit()

    assert isinstance(dialog.result_value, ExtrasAssignment)
    assert dialog.result_value.assignments == {
        0: "Behind The Scenes",
        1: "Trailers",
        2: "Extras",
    }


def test_submit_with_default_selection_uses_extras_for_all(qtbot):
    """If the user clicks Next without changing any combo, every row
    gets ``"Extras"``.  Pins the safe-default behavior — no row
    accidentally goes to ``"Trailers"`` or wherever index 0 happens
    to point if we ever change list order."""
    extras = [_extra(0), _extra(1)]
    dialog = _ExtrasClassificationDialog(extras)
    qtbot.addWidget(dialog)

    dialog._submit()

    assert dialog.result_value is not None
    assert dialog.result_value.assignments == {0: "Extras", 1: "Extras"}


def test_cancel_returns_none(qtbot):
    """Cancel discards user input — assignments are not committed."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    # Even after the user changed the combo, cancel must produce None.
    dialog.findChildren(QComboBox)[0].setCurrentText("Trailers")
    dialog._cancel()
    assert dialog.result_value is None


def test_escape_key_cancels(qtbot):
    """Esc maps to cancel, matching the tkinter
    ``win.bind("<Escape>", _cancel)``.  Pins the keyboard-out UX."""
    dialog = _ExtrasClassificationDialog([_extra(0)])
    qtbot.addWidget(dialog)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    dialog.keyPressEvent(event)
    assert dialog.result_value is None


# ==========================================================================
# Public function smoke
# ==========================================================================


def test_show_extras_classification_constructs_real_dialog(qtbot, monkeypatch):
    """``show_extras_classification`` constructs the dialog and calls
    ``exec()``.  We monkeypatch ``exec`` so the test doesn't actually
    block on a modal loop, then invoke ``_submit`` to simulate the
    user clicking Next."""
    extras = [_extra(0), _extra(1)]

    captured: dict = {}

    def fake_exec(self):
        captured["dialog"] = self
        # Simulate the user picking a category and confirming.
        combos = self.findChildren(QComboBox)
        combos[0].setCurrentText("Featurettes")
        combos[1].setCurrentText("Interviews")
        self._submit()
        return 1  # accepted

    monkeypatch.setattr(_ExtrasClassificationDialog, "exec", fake_exec)

    result = show_extras_classification(None, extras)

    assert isinstance(captured["dialog"], _ExtrasClassificationDialog)
    assert isinstance(result, ExtrasAssignment)
    assert result.assignments == {0: "Featurettes", 1: "Interviews"}


def test_show_extras_classification_returns_none_on_cancel(qtbot, monkeypatch):
    """If the user cancels, ``show_extras_classification`` propagates
    ``None`` upward so the caller can abort the wizard."""
    def fake_exec(self):
        self._cancel()
        return 0  # rejected

    monkeypatch.setattr(_ExtrasClassificationDialog, "exec", fake_exec)

    result = show_extras_classification(None, [_extra(0)])
    assert result is None
