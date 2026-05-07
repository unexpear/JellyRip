"""Sub-phase 3b — Step 1 (``show_scan_results``) port tests.

Pins the PySide6 implementation of the wizard's scan-results step:

- Dialog shape (header, sections, button row)
- Theming hooks (every styled widget has the expected ``objectName``)
- Behavior (Movie/TV/Standard buttons return the right value;
  Cancel and Esc return None)
- Drive-info conditional rendering (LibreDrive states pinned by
  state-specific objectName so QSS can color them differently)
- Summary line content (matches the tkinter helper exactly)

Uses ``pytest-qt``'s ``qtbot`` fixture for QApplication management
and event simulation.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# Skip the whole module if pytest-qt isn't available — keeps the
# rest of the suite running on machines without it.  Removed once
# pytest-qt is a hard dependency (likely Phase 3g).
pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton

from gui_qt.setup_wizard import (
    _ScanResultsDialog,
    _summary_text_for,
    show_scan_results,
)


# --------------------------------------------------------------------------
# Test fixtures: synthetic ClassifiedTitle stand-ins
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
        why_text="longest duration",
        recommended=recommended,
        valid=valid,
        title={
            "duration_seconds": duration_seconds,
            "size_bytes": size_bytes,
        },
    )


# --------------------------------------------------------------------------
# _summary_text_for (pure function — no Qt)
# --------------------------------------------------------------------------


def test_summary_text_counts_each_label():
    """Summary string includes counts for each category present."""
    titles = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "EXTRA"),
        _ct(3, "DUPLICATE"),
        _ct(4, "UNKNOWN"),
    ]
    text = _summary_text_for(titles)
    assert "5 titles" in text
    assert "1 main" in text
    assert "2 extras" in text
    assert "1 duplicates" in text
    assert "1 unknown" in text


def test_summary_text_omits_zero_categories():
    """Categories with zero count don't appear (matches tkinter)."""
    titles = [_ct(0, "MAIN", recommended=True)]
    text = _summary_text_for(titles)
    assert "1 titles" in text
    assert "1 main" in text
    assert "extras" not in text
    assert "duplicates" not in text
    assert "unknown" not in text


# --------------------------------------------------------------------------
# Dialog shape + theming hooks
# --------------------------------------------------------------------------


def test_dialog_has_wizard_object_name(qtbot):
    """The dialog itself carries ``objectName="wizardDialog"`` so
    QSS can target the wizard chrome without targeting all
    QDialogs."""
    dialog = _ScanResultsDialog(classified=[], drive_info=None, parent=None)
    qtbot.addWidget(dialog)
    assert dialog.objectName() == "wizardDialog"
    assert dialog.windowTitle() == "Scan Results"
    assert dialog.isModal()


def test_dialog_has_step_header_and_subtitle(qtbot):
    """Step header and subtitle have stable object names so QSS
    typography rules can target them."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info=None,
        parent=None,
    )
    qtbot.addWidget(dialog)
    headers = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == "stepHeader"
    ]
    subtitles = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == "stepSubtitle"
    ]
    assert len(headers) == 1
    assert "Step 1" in headers[0].text()
    assert len(subtitles) == 1


def test_dialog_renders_one_row_per_classified_title(qtbot):
    """Each ClassifiedTitle gets its own row.  Row count matches
    input length — important for keyboard navigation later."""
    titles = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "DUPLICATE"),
    ]
    dialog = _ScanResultsDialog(
        classified=titles, drive_info=None, parent=None
    )
    qtbot.addWidget(dialog)

    # Find rows by object name.
    rows = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName().startswith("classificationLabel_")
    ]
    assert len(rows) == 3, (
        f"expected 3 classification labels, got {len(rows)}"
    )


def test_classification_label_object_name_carries_category(qtbot):
    """Object name encodes the classification category so QSS can
    color each category differently without Python knowing colors."""
    titles = [
        _ct(0, "MAIN", recommended=True),
        _ct(1, "EXTRA"),
        _ct(2, "DUPLICATE"),
        _ct(3, "UNKNOWN"),
    ]
    dialog = _ScanResultsDialog(
        classified=titles, drive_info=None, parent=None
    )
    qtbot.addWidget(dialog)

    labels = [
        w.objectName() for w in dialog.findChildren(QLabel)
        if w.objectName().startswith("classificationLabel_")
    ]
    # Order matches input order
    assert labels == [
        "classificationLabel_MAIN",
        "classificationLabel_EXTRA",
        "classificationLabel_DUPLICATE",
        "classificationLabel_UNKNOWN",
    ]


# --------------------------------------------------------------------------
# Drive info conditional rendering
# --------------------------------------------------------------------------


def test_no_drive_info_means_no_drive_section(qtbot):
    """When ``drive_info`` is None or empty, no drive widgets render."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info=None,
        parent=None,
    )
    qtbot.addWidget(dialog)

    libre_widgets = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() in {
            "libreEnabled", "librePossible", "libreUnavailable",
            "driveDiscType",
        }
    ]
    assert libre_widgets == []


@pytest.mark.parametrize("state,expected_object_name", [
    ("enabled", "libreEnabled"),
    ("possible", "librePossible"),
    ("unavailable", "libreUnavailable"),
])
def test_libre_drive_state_uses_state_specific_object_name(
    qtbot, state, expected_object_name,
):
    """Each LibreDrive state has its own objectName so QSS can color
    them differently (green / amber / red).  Pins the same
    structure the tkinter version had via inline color, but moved
    to objectName so themes can override."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info={"libre_drive": state},
        parent=None,
    )
    qtbot.addWidget(dialog)

    matches = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == expected_object_name
    ]
    assert len(matches) == 1, (
        f"expected exactly one {expected_object_name} label"
    )


def test_libre_drive_unknown_state_renders_nothing(qtbot):
    """Unknown LibreDrive state values don't render a label.
    Pins defensive behavior — better to hide than show garbage."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info={"libre_drive": "weird_unexpected_value"},
        parent=None,
    )
    qtbot.addWidget(dialog)

    libre_widgets = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() in {
            "libreEnabled", "librePossible", "libreUnavailable",
        }
    ]
    assert libre_widgets == []


# --------------------------------------------------------------------------
# Button row + keyboard
# --------------------------------------------------------------------------


def test_movie_button_returns_movie(qtbot):
    """Clicking Movie sets ``result_value = 'movie'`` and accepts."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info=None,
        parent=None,
    )
    qtbot.addWidget(dialog)

    movie_btn = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == "Movie"
    )
    qtbot.mouseClick(movie_btn, Qt.MouseButton.LeftButton)

    assert dialog.result_value == "movie"


def test_tv_button_returns_tv(qtbot):
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info=None,
        parent=None,
    )
    qtbot.addWidget(dialog)

    tv_btn = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == "TV Show"
    )
    qtbot.mouseClick(tv_btn, Qt.MouseButton.LeftButton)

    assert dialog.result_value == "tv"


def test_standard_button_returns_standard(qtbot):
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info=None,
        parent=None,
    )
    qtbot.addWidget(dialog)

    std_btn = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == "Standard"
    )
    qtbot.mouseClick(std_btn, Qt.MouseButton.LeftButton)

    assert dialog.result_value == "standard"


def test_cancel_button_returns_none(qtbot):
    """Cancel sets result_value to None and rejects the dialog."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info=None,
        parent=None,
    )
    qtbot.addWidget(dialog)

    cancel_btn = next(
        b for b in dialog.findChildren(QPushButton) if b.text() == "Cancel"
    )
    qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)

    assert dialog.result_value is None


def test_escape_key_cancels(qtbot):
    """Esc cancels — matches the tkinter behavior."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info=None,
        parent=None,
    )
    qtbot.addWidget(dialog)
    dialog.show()  # needs to be visible for keypress to dispatch
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    assert dialog.result_value is None


# --------------------------------------------------------------------------
# Theming hook coverage — make sure every styled widget has an
# objectName (catches accidental missing hooks during future edits)
# --------------------------------------------------------------------------


def test_every_button_has_an_object_name(qtbot):
    """Drift guard: every button in the dialog must have an
    objectName so QSS can target it.  Catches refactors that lose
    theming hooks."""
    dialog = _ScanResultsDialog(
        classified=[_ct(0, "MAIN", recommended=True)],
        drive_info={"libre_drive": "enabled"},
        parent=None,
    )
    qtbot.addWidget(dialog)

    unnamed = [
        b for b in dialog.findChildren(QPushButton)
        if not b.objectName()
    ]
    assert unnamed == [], (
        f"every button needs an objectName for theming; missing on: "
        f"{[b.text() for b in unnamed]}"
    )
