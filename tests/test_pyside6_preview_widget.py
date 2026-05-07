"""Phase 3e — gui_qt.preview_widget tests.

Pins:
- Pure helpers (format_position_label, _format_ms)
- Dialog construction and chrome
- Play/pause toggle + Space shortcut
- Scrub slider behavior
- Position label updates on positionChanged signal
- Esc closes
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtMultimedia import QMediaPlayer

from gui_qt.preview_widget import (
    PreviewDialog,
    _format_ms,
    format_position_label,
    show_preview,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ms,expected", [
    (0, "0:00"),
    (-100, "0:00"),       # negative → 0:00
    (1000, "0:01"),
    (60_000, "1:00"),
    (61_500, "1:01"),
    (3_600_000, "1:00:00"),
    (3_661_500, "1:01:01"),
    (10_800_000, "3:00:00"),
])
def test_format_ms_known_values(ms, expected):
    assert _format_ms(ms) == expected


def test_format_position_label_basic():
    assert format_position_label(14_000, 30_000) == "0:14 / 0:30"


def test_format_position_label_unknown_duration():
    """Unknown duration (0 or negative) renders as em-dash."""
    assert format_position_label(14_000, 0) == "0:14 / —"
    assert format_position_label(14_000, -1) == "0:14 / —"


def test_format_position_label_zero_position():
    assert format_position_label(0, 30_000) == "0:00 / 0:30"


def test_format_position_label_long_duration():
    """Hours render properly for both pos and dur."""
    assert format_position_label(3_661_000, 7_322_000) == "1:01:01 / 2:02:02"


# ---------------------------------------------------------------------------
# Dialog construction
# ---------------------------------------------------------------------------


def test_dialog_chrome(qtbot):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    assert d.windowTitle() == "MKV Preview"
    assert d.objectName() == "previewDialog"
    assert d.isModal()


def test_dialog_initial_state(qtbot):
    """Brand-new dialog: paused, slider at 0-0, label "0:00 / —"."""
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    assert d.play_button.text() == "▶"
    assert d.scrub_slider.minimum() == 0
    assert d.scrub_slider.maximum() == 0
    assert d.position_label.text() == "0:00 / —"


def test_dialog_has_video_widget(qtbot):
    """The video surface widget must be embedded."""
    from PySide6.QtMultimediaWidgets import QVideoWidget
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    assert d._video_widget.objectName() == "previewVideoWidget"


def test_dialog_has_qmediaplayer(qtbot):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    assert isinstance(d.player, QMediaPlayer)


def test_empty_path_does_not_set_source(qtbot):
    """``mkv_path=""`` leaves the player idle so the dialog can be
    constructed even when no file is ready."""
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    assert d.player.source().isEmpty()


# ---------------------------------------------------------------------------
# Play / pause / state-driven button label
# ---------------------------------------------------------------------------


def test_play_pause_button_label_follows_state(qtbot):
    """Player state changes flip the button glyph."""
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    # Manually fire the slot since we don't actually play media
    d._on_state_changed(QMediaPlayer.PlaybackState.PlayingState)
    assert d.play_button.text() == "⏸"
    d._on_state_changed(QMediaPlayer.PlaybackState.PausedState)
    assert d.play_button.text() == "▶"
    d._on_state_changed(QMediaPlayer.PlaybackState.StoppedState)
    assert d.play_button.text() == "▶"


# ---------------------------------------------------------------------------
# Scrub slider + position label
# ---------------------------------------------------------------------------


def test_duration_changed_updates_slider_range(qtbot):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    d._on_duration_changed(45_000)
    assert d.scrub_slider.maximum() == 45_000


def test_position_changed_updates_slider_when_not_dragging(qtbot):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    d._on_duration_changed(30_000)
    d._on_position_changed(15_000)
    assert d.scrub_slider.value() == 15_000


def test_position_changed_updates_label(qtbot):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    d._on_duration_changed(30_000)
    d._on_position_changed(14_500)
    assert d.position_label.text() == "0:14 / 0:30"


def test_position_changed_does_not_clobber_user_drag(qtbot, monkeypatch):
    """When the user is mid-drag on the slider, position updates from
    the player must NOT yank the slider away from where the user has
    it.  Pinned because that's a confusing UX glitch."""
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    d._on_duration_changed(30_000)
    d.scrub_slider.setValue(20_000)
    # Pretend the user is dragging
    monkeypatch.setattr(d.scrub_slider, "isSliderDown", lambda: True)
    d._on_position_changed(5_000)
    # Slider stays at 20_000 (user's drag wins)
    assert d.scrub_slider.value() == 20_000


def test_scrub_release_seeks_player(qtbot, monkeypatch):
    """Releasing the slider seeks the player to the slider value."""
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    # Slider needs a range before setValue actually takes effect.
    d._on_duration_changed(30_000)
    seeks: list = []
    monkeypatch.setattr(d.player, "setPosition", seeks.append)
    d.scrub_slider.setValue(12_500)
    d._on_scrub_released()
    assert seeks == [12_500]


# ---------------------------------------------------------------------------
# Toggle play/pause via space + button
# ---------------------------------------------------------------------------


def test_space_key_toggles_play_pause(qtbot, monkeypatch):
    """Spacebar fires the toggle just like clicking the play button."""
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    calls: list = []
    monkeypatch.setattr(d.player, "play", lambda: calls.append("play"))
    monkeypatch.setattr(d.player, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(
        d.player, "playbackState",
        lambda: QMediaPlayer.PlaybackState.StoppedState,
    )
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert calls == ["play"]


def test_play_button_triggers_play(qtbot, monkeypatch):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    calls: list = []
    monkeypatch.setattr(d.player, "play", lambda: calls.append("play"))
    monkeypatch.setattr(d.player, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(
        d.player, "playbackState",
        lambda: QMediaPlayer.PlaybackState.PausedState,
    )
    d.play_button.click()
    assert calls == ["play"]


def test_play_button_triggers_pause_when_playing(qtbot, monkeypatch):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    calls: list = []
    monkeypatch.setattr(d.player, "play", lambda: calls.append("play"))
    monkeypatch.setattr(d.player, "pause", lambda: calls.append("pause"))
    monkeypatch.setattr(
        d.player, "playbackState",
        lambda: QMediaPlayer.PlaybackState.PlayingState,
    )
    d.play_button.click()
    assert calls == ["pause"]


# ---------------------------------------------------------------------------
# Close / Esc / cleanup
# ---------------------------------------------------------------------------


def test_close_button_stops_player_and_rejects(qtbot, monkeypatch):
    """Close stops the player + clears the source (releases file
    handle) before rejecting the dialog."""
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    calls: list = []
    monkeypatch.setattr(d.player, "stop", lambda: calls.append("stop"))
    monkeypatch.setattr(
        d.player, "setSource", lambda url: calls.append(("setSource", url.toString())),
    )
    d._close_button.click()
    assert "stop" in calls
    # The setSource call should clear the URL
    set_calls = [c for c in calls if isinstance(c, tuple) and c[0] == "setSource"]
    assert set_calls and set_calls[0][1] == ""
    assert d.result() == 0  # rejected


def test_esc_key_closes(qtbot, monkeypatch):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    monkeypatch.setattr(d.player, "stop", lambda: None)
    monkeypatch.setattr(d.player, "setSource", lambda url: None)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert d.result() == 0


# ---------------------------------------------------------------------------
# Player error path
# ---------------------------------------------------------------------------


def test_error_signal_captured(qtbot):
    d = PreviewDialog(mkv_path="")
    qtbot.addWidget(d)
    # Manually invoke the slot — real signal would come from QMediaPlayer.
    d._on_player_error(QMediaPlayer.Error.ResourceError, "file not found")
    assert d.last_error == "file not found"


# ---------------------------------------------------------------------------
# Public function smoke
# ---------------------------------------------------------------------------


def test_show_preview_constructs_dialog(qtbot, monkeypatch):
    """Public entry constructs a PreviewDialog and calls exec.
    We monkeypatch exec to avoid a real modal."""
    captured: dict = {}

    def fake_exec(self):
        captured["called"] = True
        captured["mkv_path"] = self._mkv_path
        return 0

    monkeypatch.setattr(PreviewDialog, "exec", fake_exec)
    show_preview(None, "/tmp/x.mkv")
    assert captured["called"]
    assert captured["mkv_path"] == "/tmp/x.mkv"


# ---------------------------------------------------------------------------
# disc_tree right-click → preview_callback (cross-module integration)
# ---------------------------------------------------------------------------


def test_disc_tree_right_click_invokes_preview_callback(qtbot):
    """Right-click handler on disc tree dispatches to the
    preview_callback with the title's integer ID."""
    from gui_qt.dialogs.disc_tree import _DiscTreeDialog

    captured_ids: list = []

    def cb(tid: int) -> None:
        captured_ids.append(tid)

    titles = [
        {"id": 0, "name": "A"},
        {"id": 7, "name": "B"},
    ]
    d = _DiscTreeDialog(titles, is_tv=False, preview_callback=cb)
    qtbot.addWidget(d)

    # Simulate a right-click on each title via the test helper
    d.trigger_preview_for_test("0")
    d.trigger_preview_for_test("7")

    assert captured_ids == [0, 7]


def test_disc_tree_right_click_without_callback_is_noop(qtbot):
    """If the caller didn't provide a preview_callback, right-click
    is silently ignored — no exception."""
    from gui_qt.dialogs.disc_tree import _DiscTreeDialog
    d = _DiscTreeDialog(
        [{"id": 0, "name": "A"}],
        is_tv=False,
        preview_callback=None,
    )
    qtbot.addWidget(d)
    # Should not raise
    d.trigger_preview_for_test("0")


def test_disc_tree_right_click_with_invalid_id_silently_skips(qtbot):
    """Defensive — non-numeric user-data won't blow up the handler."""
    from gui_qt.dialogs.disc_tree import _DiscTreeDialog
    captured: list = []
    d = _DiscTreeDialog(
        [{"id": 0, "name": "A"}],
        is_tv=False,
        preview_callback=captured.append,
    )
    qtbot.addWidget(d)
    d.trigger_preview_for_test("not-a-number")
    # Callback never invoked
    assert captured == []


def test_disc_tree_callback_exception_does_not_crash(qtbot):
    """If the callback raises, the dialog stays alive."""
    from gui_qt.dialogs.disc_tree import _DiscTreeDialog
    def bad(tid: int) -> None:
        raise RuntimeError("preview engine crashed")
    d = _DiscTreeDialog(
        [{"id": 0, "name": "A"}],
        is_tv=False,
        preview_callback=bad,
    )
    qtbot.addWidget(d)
    # Should not raise
    d.trigger_preview_for_test("0")
