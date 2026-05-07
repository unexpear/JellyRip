"""Sub-phase 3b — Step 3 (``show_content_mapping``) port tests.

Pins the PySide6 implementation of the wizard's content-mapping
step:

- Default check states (MAIN pre-checked, DUPLICATE unchecked,
  EXTRA pre-checked iff valid)
- Submit aggregation (checked → main / extras / skip per label)
- Submit refusal when nothing is checked (matches tkinter)
- Theming hooks per row + per category
- Cancel / Esc → returns None
- Row-click anywhere toggles the checkbox (preserved UX)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QCheckBox, QPushButton, QWidget

from gui_qt.setup_wizard import (
    ContentSelection,
    _build_content_selection,
    _ContentMappingDialog,
    _default_check_state_for,
    show_content_mapping,
)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


@dataclass
class _FakeTitle:
    title_id: int
    label: str
    confidence: float
    status_text: str
    why_text: str
    recommended: bool
    valid: bool
    title: dict


def _ct(
    tid: int,
    label: str,
    *,
    confidence: float = 0.95,
    recommended: bool = False,
    valid: bool = True,
    duration_seconds: int = 7200,
    size_bytes: int = 4_000_000_000,
) -> _FakeTitle:
    return _FakeTitle(
        title_id=tid,
        label=label,
        confidence=confidence,
        status_text="Recommended" if recommended else "Optional",
        why_text="reason",
        recommended=recommended,
        valid=valid,
        title={
            "duration_seconds": duration_seconds,
            "size_bytes": size_bytes,
        },
    )


# --------------------------------------------------------------------------
# Pure helpers (no Qt)
# --------------------------------------------------------------------------


def test_default_check_state_pre_checks_recommended_main():
    """MAIN titles marked recommended are pre-checked."""
    assert _default_check_state_for(
        _ct(0, "MAIN", recommended=True)
    ) is True


def test_default_check_state_pre_checks_valid_extras():
    """Valid EXTRA titles are pre-checked even when not recommended."""
    assert _default_check_state_for(
        _ct(0, "EXTRA", recommended=False, valid=True)
    ) is True


def test_default_check_state_does_not_pre_check_invalid_extras():
    """EXTRA titles marked invalid are NOT pre-checked."""
    assert _default_check_state_for(
        _ct(0, "EXTRA", recommended=False, valid=False)
    ) is False


def test_default_check_state_does_not_pre_check_duplicates():
    """DUPLICATE titles are not pre-checked — the user has to opt
    in if they actually want them."""
    assert _default_check_state_for(
        _ct(0, "DUPLICATE", recommended=False)
    ) is False


def test_default_check_state_does_not_pre_check_unknown():
    """UNKNOWN labels are not pre-checked."""
    assert _default_check_state_for(
        _ct(0, "UNKNOWN", recommended=False)
    ) is False


def test_build_content_selection_groups_main_extras_skip():
    """Pure aggregation logic — groups checked titles by label,
    routes everything unchecked to skip."""
    classified = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "DUPLICATE"),
        _ct(3, "EXTRA"),
        _ct(4, "UNKNOWN"),
    ]
    # User checks 0 (MAIN), 1 (EXTRA), 2 (DUPLICATE), unchecks 3, 4.
    sel = _build_content_selection(classified, checked_ids=[0, 1, 2])

    assert sel.main_title_ids == [0]
    assert sel.extra_title_ids == [1, 2], (
        "DUPLICATE explicitly checked goes to extras_title_ids"
    )
    assert sel.skip_title_ids == [3, 4]


def test_build_content_selection_routes_unknown_to_extras_when_checked():
    """Checked UNKNOWN titles land in extras_title_ids (matches
    tkinter)."""
    classified = [_ct(0, "UNKNOWN")]
    sel = _build_content_selection(classified, checked_ids=[0])
    assert sel.main_title_ids == []
    assert sel.extra_title_ids == [0]
    assert sel.skip_title_ids == []


def test_build_content_selection_with_no_checks_skips_everything():
    """When nothing is checked, every title goes to skip.  Pure
    function pin — the dialog's _submit guard separately refuses
    to accept this state, but the aggregation itself works."""
    classified = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
    ]
    sel = _build_content_selection(classified, checked_ids=[])
    assert sel.main_title_ids == []
    assert sel.extra_title_ids == []
    assert sel.skip_title_ids == [0, 1]


# --------------------------------------------------------------------------
# Dialog construction + theming hooks
# --------------------------------------------------------------------------


def test_dialog_chrome(qtbot):
    """Standard wizard-dialog objectName, title, modality."""
    dialog = _ContentMappingDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        parent=None,
    )
    qtbot.addWidget(dialog)
    assert dialog.objectName() == "wizardDialog"
    assert dialog.windowTitle() == "Content Mapping"
    assert dialog.isModal()


def test_dialog_renders_one_checkbox_per_title(qtbot):
    """Each ClassifiedTitle gets its own checkbox row."""
    classified = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "DUPLICATE"),
    ]
    dialog = _ContentMappingDialog(classified=classified, parent=None)
    qtbot.addWidget(dialog)

    checkboxes = [
        cb for cb in dialog.findChildren(QCheckBox)
        if cb.objectName() == "contentMappingCheckbox"
    ]
    assert len(checkboxes) == 3


def test_default_check_states_match_label_rules(qtbot):
    """Pinned visually: MAIN+recommended → checked; EXTRA+valid →
    checked; DUPLICATE → unchecked; UNKNOWN → unchecked."""
    classified = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "DUPLICATE"),
        _ct(3, "UNKNOWN"),
    ]
    dialog = _ContentMappingDialog(classified=classified, parent=None)
    qtbot.addWidget(dialog)

    states = {
        tid: dialog._check_boxes[tid].isChecked()
        for tid in (0, 1, 2, 3)
    }
    assert states == {0: True, 1: True, 2: False, 3: False}


def test_classification_label_object_name_carries_category(qtbot):
    """Same convention as Step 1 — QSS targets per-category names."""
    classified = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "DUPLICATE"),
        _ct(3, "UNKNOWN"),
    ]
    dialog = _ContentMappingDialog(classified=classified, parent=None)
    qtbot.addWidget(dialog)

    from PySide6.QtWidgets import QLabel
    expected = [
        "classificationLabel_MAIN",
        "classificationLabel_EXTRA",
        "classificationLabel_DUPLICATE",
        "classificationLabel_UNKNOWN",
    ]
    found = [
        w.objectName() for w in dialog.findChildren(QLabel)
        if w.objectName().startswith("classificationLabel_")
    ]
    assert found == expected


def test_every_button_has_object_name(qtbot):
    """Drift guard: every button needs an objectName for theming."""
    dialog = _ContentMappingDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        parent=None,
    )
    qtbot.addWidget(dialog)
    unnamed = [
        b for b in dialog.findChildren(QPushButton)
        if not b.objectName()
    ]
    assert unnamed == []


# --------------------------------------------------------------------------
# Submit / cancel / Esc behavior
# --------------------------------------------------------------------------


def test_next_button_submits_with_default_selection(qtbot):
    """Clicking Next with default check states produces a
    ContentSelection that includes the pre-checked titles."""
    classified = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "DUPLICATE"),
    ]
    dialog = _ContentMappingDialog(classified=classified, parent=None)
    qtbot.addWidget(dialog)

    next_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if "Next" in b.text()
    )
    qtbot.mouseClick(next_btn, Qt.MouseButton.LeftButton)

    assert isinstance(dialog.result_value, ContentSelection)
    assert dialog.result_value.main_title_ids == [0]
    assert dialog.result_value.extra_title_ids == [1]
    assert dialog.result_value.skip_title_ids == [2]


def test_next_button_refuses_when_nothing_checked(qtbot):
    """Submit silently refuses when no checkboxes are on.  Pins
    the tkinter behavior — prevents accidental zero-title rip."""
    classified = [
        _ct(0, "DUPLICATE"),
        _ct(1, "UNKNOWN"),
    ]
    dialog = _ContentMappingDialog(classified=classified, parent=None)
    qtbot.addWidget(dialog)

    # Both default to unchecked. Clicking Next should NOT close.
    next_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if "Next" in b.text()
    )
    qtbot.mouseClick(next_btn, Qt.MouseButton.LeftButton)

    # Dialog stays unrejected and result_value stays None.
    assert dialog.result_value is None


def test_next_button_is_default(qtbot):
    """Enter triggers Next (matches tkinter's <Return> binding)."""
    dialog = _ContentMappingDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        parent=None,
    )
    qtbot.addWidget(dialog)
    next_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if b.objectName() == "confirmButton"
    )
    assert next_btn.isDefault()


def test_cancel_returns_none(qtbot):
    """Cancel sets result_value to None and rejects."""
    dialog = _ContentMappingDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        parent=None,
    )
    qtbot.addWidget(dialog)
    cancel_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if b.text() == "Cancel"
    )
    qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)
    assert dialog.result_value is None


def test_escape_key_cancels(qtbot):
    """Esc cancels — matches tkinter."""
    dialog = _ContentMappingDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        parent=None,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result_value is None


def test_unchecking_main_routes_it_to_skip(qtbot):
    """If the user explicitly unchecks the MAIN title, it goes to
    skip — not main_title_ids.  Pins respect for the user's
    override over the classifier's recommendation."""
    classified = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
    ]
    dialog = _ContentMappingDialog(classified=classified, parent=None)
    qtbot.addWidget(dialog)

    # Uncheck the MAIN title.
    dialog._check_boxes[0].setChecked(False)

    next_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if "Next" in b.text()
    )
    qtbot.mouseClick(next_btn, Qt.MouseButton.LeftButton)

    sel = dialog.result_value
    assert sel is not None
    assert sel.main_title_ids == []
    assert sel.skip_title_ids == [0]
    assert sel.extra_title_ids == [1]


def test_row_click_toggles_checkbox(qtbot):
    """Clicking the row anywhere toggles the embedded checkbox.
    Pins the row-click UX from the tkinter version (every label
    in the row had a click binding)."""
    classified = [_ct(0, "EXTRA")]
    dialog = _ContentMappingDialog(classified=classified, parent=None)
    qtbot.addWidget(dialog)

    cb = dialog._check_boxes[0]
    initially_checked = cb.isChecked()

    # Find the row widget (contentMappingRow object name).
    row = next(
        w for w in dialog.findChildren(QWidget)
        if w.objectName() == "contentMappingRow"
    )

    # Synthesize a left-mouse click at the row's center.  Going
    # through the public mousePressEvent handler that the dialog
    # set up.
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPoint(5, 5),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    row.mousePressEvent(event)

    assert cb.isChecked() != initially_checked, (
        "row-click should toggle the embedded checkbox"
    )
