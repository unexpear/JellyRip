"""Phase 3c-i — gui_qt.status_bar tests.

Pins the contract for the StatusBar widget:

- Initial state is "Ready" with statusReady objectName
- set_status auto-classifies the role from the message
- set_status with explicit role override
- set_progress determinate / indeterminate
- reset returns to Ready / 0%
- Theming hooks (objectNames per role)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QLabel, QProgressBar

from gui_qt.status_bar import StatusBar, _humanize_bytes


# ---------------------------------------------------------------------------
# Construction + initial state
# ---------------------------------------------------------------------------


def test_status_bar_objectname(qtbot):
    """The widget itself gets ``statusBar`` objectName."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    assert sb.objectName() == "statusBar"


def test_status_bar_initial_text_is_ready(qtbot):
    """Brand-new status bar shows "Ready"."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    assert sb.label_text == "Ready"


def test_status_bar_initial_role_is_ready(qtbot):
    """Initial label objectName is ``statusReady``."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    assert sb.label_role == "statusReady"


def test_status_bar_has_progress_bar(qtbot):
    """A QProgressBar must be embedded — pinned because the
    controller depends on its existence."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    bars = sb.findChildren(QProgressBar)
    assert len(bars) == 1
    assert bars[0].objectName() == "statusProgress"


def test_status_bar_has_status_label(qtbot):
    """A QLabel must be embedded for the status text."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    labels = sb.findChildren(QLabel)
    assert len(labels) == 1


# ---------------------------------------------------------------------------
# set_status — automatic role classification
# ---------------------------------------------------------------------------


def test_set_status_busy_message(qtbot):
    """Active in-progress message classifies as busy."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_status("Ripping title 02")
    assert sb.label_text == "Ripping title 02"
    assert sb.label_role == "statusBusy"


def test_set_status_error_message(qtbot):
    """Error tokens classify as error."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_status("MakeMKV failed to scan")
    assert sb.label_role == "statusError"


def test_set_status_warn_message(qtbot):
    """Warn tokens classify as warn."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_status("Aborting current operation")
    assert sb.label_role == "statusWarn"


def test_set_status_ready_message(qtbot):
    """Idle messages classify as ready."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_status("Idle")
    assert sb.label_role == "statusReady"


# ---------------------------------------------------------------------------
# set_status — explicit role override
# ---------------------------------------------------------------------------


def test_set_status_with_explicit_role_override(qtbot):
    """Caller can force a role regardless of message classification.
    Useful when the controller knows the semantic state better than
    the message text suggests."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    # Message reads "busy" but caller explicitly asks for warn.
    sb.set_status("Ripping title 02", role="warn")
    assert sb.label_role == "statusWarn"


# ---------------------------------------------------------------------------
# set_progress
# ---------------------------------------------------------------------------


def test_set_progress_determinate(qtbot):
    """``total > 0`` → determinate progress."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(64, 100)
    assert sb.progress_value == 64
    assert sb.progress_maximum == 100


def test_set_progress_indeterminate(qtbot):
    """``total == 0`` → indeterminate (busy) mode.  Qt renders this
    as the marquee animation; the maximum is set to 0."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(0, 0)
    assert sb.progress_maximum == 0


def test_set_progress_clamps_negative_current(qtbot):
    """Negative ``current`` clamps to 0 — defensive against an
    off-by-one in the controller's progress reporting."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(-5, 100)
    assert sb.progress_value == 0


def test_set_progress_clamps_overshoot(qtbot):
    """``current > total`` clamps to ``total`` — pinned because some
    callers report 100/100 plus a few extra ticks."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(120, 100)
    assert sb.progress_value == 100


def test_set_progress_negative_total_treated_as_indeterminate(qtbot):
    """``total < 0`` is nonsense — treat like ``0`` (indeterminate)
    rather than crashing."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(50, -10)
    assert sb.progress_maximum == 0


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


def test_reset_clears_progress_and_returns_to_ready(qtbot):
    """``reset()`` after work is done returns the bar to its
    starting state — pinned because the controller calls this
    between workflow runs."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_status("Ripping...")
    sb.set_progress(50, 100)
    sb.reset()
    assert sb.label_text == "Ready"
    assert sb.label_role == "statusReady"
    assert sb.progress_value == 0
    assert sb.progress_maximum == 100  # back to determinate


# ---------------------------------------------------------------------------
# Byte-level format — added 2026-05-04 for the MakeMKV rip view
# ---------------------------------------------------------------------------


def test_humanize_bytes_picks_unit_for_readability():
    """Pure helper — pinned so the format string stays compact even
    as the value scales."""
    assert _humanize_bytes(0) == "0 KB"
    assert _humanize_bytes(512) == "1 KB"
    assert _humanize_bytes(900_000) == "900 KB"
    assert _humanize_bytes(1_500_000) == "1.5 MB"
    assert _humanize_bytes(900_000_000) == "900.0 MB"
    assert _humanize_bytes(3_700_000_000) == "3.7 GB"


def test_progress_format_defaults_to_bare_percent(qtbot):
    """Without byte hints, the bar shows just the percent — the
    legacy contract."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(33, 100)
    assert sb.progress_format == "%p%"


def test_progress_format_switches_to_byte_style_when_hinted(qtbot):
    """Passing both ``current_bytes`` + ``total_bytes`` rewrites the
    format to the GB-aware style.  Pinned so the engine→controller
    plumbing has a stable target."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(
        33, 100,
        current_bytes=1_200_000_000, total_bytes=3_700_000_000,
    )
    fmt = sb.progress_format
    assert "1.2 GB" in fmt
    assert "3.7 GB" in fmt
    assert "%p%" in fmt


def test_progress_format_reverts_to_percent_when_bytes_dropped(qtbot):
    """A second call without byte hints must revert to "%p%" — the
    bar shouldn't get stuck showing stale GB values."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(
        33, 100,
        current_bytes=1_200_000_000, total_bytes=3_700_000_000,
    )
    sb.set_progress(50, 100)
    assert sb.progress_format == "%p%"


def test_indeterminate_clears_byte_format(qtbot):
    """Switching to busy/indeterminate must drop any stale byte
    format — the marquee animation has nothing meaningful to
    pair with byte values."""
    sb = StatusBar()
    qtbot.addWidget(sb)
    sb.set_progress(
        33, 100,
        current_bytes=1_200_000_000, total_bytes=3_700_000_000,
    )
    sb.set_progress(0, 0)  # indeterminate
    assert sb.progress_format == "%p%"
