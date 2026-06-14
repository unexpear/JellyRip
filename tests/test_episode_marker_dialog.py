"""Tests for the episode-marking player dialog (gui_qt.dialogs.episode_marker).

Real video playback can't run headless, so these drive the marker
bookkeeping directly (``add_marker_at`` / ``markers`` / ``remove_selected``)
— the same way the preview-dialog tests avoid real decoding.  Pure
label helpers are tested without Qt.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from engine.episode_split import EpisodeMarker
from gui_qt.dialogs.episode_marker import format_seconds, marker_row_label


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_format_seconds_minutes_and_hours():
    assert format_seconds(0) == "0:00"
    assert format_seconds(90) == "1:30"
    assert format_seconds(3661) == "1:01:01"
    assert format_seconds(-5) == "0:00"


def test_marker_row_label_named_and_unnamed():
    assert marker_row_label(1290, "Pilot") == "21:30  —  Pilot"
    assert "(unnamed)" in marker_row_label(60, "")


# ---------------------------------------------------------------------------
# Dialog marker bookkeeping (qtbot, no real playback)
# ---------------------------------------------------------------------------

pytest.importorskip("pytestqt")


@pytest.fixture
def dialog(qtbot):
    from gui_qt.dialogs.episode_marker import EpisodeMarkerDialog
    # Empty path -> player stays idle; we drive markers directly.
    d = EpisodeMarkerDialog("", title_label="Test Disc")
    qtbot.addWidget(d)
    return d


def test_add_markers_sorted_and_exported_as_seconds(dialog):
    dialog.add_marker_at(132_0000 // 100, "B")  # 13200 ms -> 13.2 s
    dialog.add_marker_at(0, "A")
    markers = dialog.markers()
    assert [m.name for m in markers] == ["A", "B"]            # sorted by time
    assert markers[0].start_seconds == 0.0
    assert all(isinstance(m, EpisodeMarker) for m in markers)


def test_same_second_marker_deduped(dialog):
    dialog.add_marker_at(5000, "first")
    dialog.add_marker_at(5400, "dupe within same second")
    assert len(dialog.markers()) == 1                          # 5s already taken
    assert dialog.marker_list.count() == 1


def test_split_button_disabled_until_a_marker_exists(dialog):
    assert not dialog.split_button.isEnabled()                 # no markers yet
    dialog.add_marker_at(1000, "Ep1")
    assert dialog.split_button.isEnabled()


def test_remove_selected_marker(dialog):
    dialog.add_marker_at(0, "A")
    dialog.add_marker_at(10_000, "B")
    dialog.marker_list.setCurrentRow(0)
    dialog.remove_selected()
    remaining = [m.name for m in dialog.markers()]
    assert remaining == ["B"]
    assert dialog.marker_list.count() == 1


def test_split_accepts_dialog_and_keeps_markers(qtbot, dialog):
    dialog.add_marker_at(0, "Pilot")
    dialog.add_marker_at(20_000, "Episode 2")
    dialog._on_split()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert [m.name for m in dialog.markers()] == ["Pilot", "Episode 2"]
