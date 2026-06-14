"""Episode-marking player — watch a multi-episode title, mark episodes.

The app's OWN player (QtMultimedia, like ``gui_qt.preview_widget``) so
it can read the exact timeline position — external VLC can't report
where you paused.  You scrub/play the kept full-title rip, and at the
start of each episode you click "Mark episode here" with a name.  On
"Split into episodes" the dialog returns the markers; the controller
hands them to ``engine.episode_split`` for a lossless cut.

Title-to-title boundaries on a multi-title disc are already separate
files, so this is only for the within-one-title case.

Pure, Qt-free helpers (testable) at module level:
* ``format_seconds(s)`` — "M:SS" / "H:MM:SS".
* ``marker_row_label(seconds, name)`` — the list-row text.

The marker bookkeeping (``add_marker_at`` / ``markers`` /
``remove_selected``) is plain list logic so it's testable without real
video playback (QtMultimedia can't decode in a headless test).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from engine.episode_split import EpisodeMarker

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


# ---------------------------------------------------------------------------
# Pure helpers (Qt-free)
# ---------------------------------------------------------------------------


def format_seconds(seconds: float) -> str:
    """Render seconds as M:SS (or H:MM:SS for >= 1h).  Negative -> 0:00."""
    total = int(max(0.0, seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def marker_row_label(seconds: float, name: str) -> str:
    """The text for one row in the marker list: "0:21:30  —  Ep name"."""
    label = format_seconds(seconds)
    name = str(name or "").strip()
    return f"{label}  —  {name}" if name else f"{label}  —  (unnamed)"


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------


class EpisodeMarkerDialog(QDialog):
    """Player + marker list for splitting one title into episodes.

    Accept (``Split into episodes``) keeps the dialog's markers, which
    the caller reads via :meth:`markers`.  Cancel returns nothing.
    """

    def __init__(
        self,
        mkv_path: str,
        *,
        title_label: str = "",
        parent: "QWidget | None" = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("episodeMarkerDialog")
        self.setWindowTitle("Mark Episodes")
        self.setModal(True)
        self.resize(760, 620)

        self._mkv_path = mkv_path
        self._duration_ms: int = 0
        # Internal marker store: list of (milliseconds, name).  Kept
        # sorted by time on every add so the list + export are ordered.
        self._markers: list[tuple[int, str]] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 8)
        outer.setSpacing(6)

        if title_label:
            header = QLabel(
                f"Watching: {title_label}\n"
                "Play to the start of each episode, type its name, and "
                "click “Mark episode here.”  Then Split into "
                "episodes — the title is cut losslessly into one file "
                "per marker (anything before the first marker is skipped)."
            )
            header.setObjectName("episodeMarkerHeader")
            header.setWordWrap(True)
            header.setContentsMargins(12, 8, 12, 0)
            outer.addWidget(header)

        # Video surface.
        self._video_widget = QVideoWidget()
        self._video_widget.setObjectName("episodeMarkerVideo")
        outer.addWidget(self._video_widget, stretch=1)

        # Transport row: play/pause | scrub | position.
        transport = QHBoxLayout()
        transport.setContentsMargins(12, 4, 12, 4)
        transport.setSpacing(8)

        self._play_button = QPushButton("▶")
        self._play_button.setObjectName("episodeMarkerPlayButton")
        self._play_button.setFixedWidth(36)
        self._play_button.clicked.connect(self._toggle_play_pause)
        transport.addWidget(self._play_button)

        self._scrub = QSlider(Qt.Orientation.Horizontal)
        self._scrub.setObjectName("episodeMarkerScrub")
        self._scrub.setRange(0, 0)
        self._scrub.sliderReleased.connect(self._on_scrub_released)
        transport.addWidget(self._scrub, stretch=1)

        self._position_label = QLabel("0:00 / —")
        self._position_label.setObjectName("episodeMarkerPosition")
        self._position_label.setFixedWidth(110)
        self._position_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        transport.addWidget(self._position_label)
        outer.addLayout(transport)

        # Mark row: name field + "Mark episode here".
        mark_row = QHBoxLayout()
        mark_row.setContentsMargins(12, 0, 12, 4)
        mark_row.setSpacing(8)
        self._name_edit = QLineEdit()
        self._name_edit.setObjectName("episodeMarkerNameEdit")
        self._name_edit.setPlaceholderText("Episode name (optional)")
        self._name_edit.returnPressed.connect(self._on_mark_clicked)
        mark_row.addWidget(self._name_edit, stretch=1)
        self._mark_button = QPushButton("⭐  Mark episode here")
        self._mark_button.setObjectName("episodeMarkerMarkButton")
        self._mark_button.clicked.connect(self._on_mark_clicked)
        mark_row.addWidget(self._mark_button)
        outer.addLayout(mark_row)

        # Marker list + remove.
        self._list = QListWidget()
        self._list.setObjectName("episodeMarkerList")
        self._list.setFixedHeight(140)
        outer.addWidget(self._list)

        list_buttons = QHBoxLayout()
        list_buttons.setContentsMargins(12, 0, 12, 4)
        self._remove_button = QPushButton("Remove selected")
        self._remove_button.setObjectName("episodeMarkerRemoveButton")
        self._remove_button.clicked.connect(self.remove_selected)
        list_buttons.addWidget(self._remove_button)
        list_buttons.addStretch(1)
        outer.addLayout(list_buttons)

        # Bottom: Cancel | Split into episodes.
        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 0, 12, 4)
        bottom.addStretch(1)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("cancelButton")
        self._cancel_button.clicked.connect(self._on_close)
        bottom.addWidget(self._cancel_button)
        self._split_button = QPushButton("Split into episodes")
        self._split_button.setObjectName("confirmButton")
        self._split_button.clicked.connect(self._on_split)
        bottom.addWidget(self._split_button)
        outer.addLayout(bottom)

        # Player.
        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.setVideoOutput(self._video_widget)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.errorOccurred.connect(self._on_player_error)
        if mkv_path:
            self._player.setSource(QUrl.fromLocalFile(mkv_path))

        self.last_error: str = ""
        self._refresh_split_enabled()

    # ------------------------------------------------------------------
    # Public API / test hooks
    # ------------------------------------------------------------------

    @property
    def player(self) -> QMediaPlayer:
        return self._player

    @property
    def mark_button(self) -> QPushButton:
        return self._mark_button

    @property
    def split_button(self) -> QPushButton:
        return self._split_button

    @property
    def marker_list(self) -> QListWidget:
        return self._list

    def add_marker_at(self, position_ms: int, name: str = "") -> None:
        """Add an episode-start marker at ``position_ms`` (kept sorted,
        de-duplicated to the second so a double-click doesn't add two)."""
        ms = max(0, int(position_ms))
        sec = ms // 1000
        if any((m // 1000) == sec for m, _ in self._markers):
            return
        self._markers.append((ms, str(name or "").strip()))
        self._markers.sort(key=lambda m: m[0])
        self._rebuild_list()
        self._refresh_split_enabled()

    def markers(self) -> list[EpisodeMarker]:
        """Export markers as ``EpisodeMarker`` (seconds), time-ordered."""
        return [
            EpisodeMarker(start_seconds=ms / 1000.0, name=name)
            for ms, name in self._markers
        ]

    def remove_selected(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._markers):
            self._markers.pop(row)
            self._rebuild_list()
            self._refresh_split_enabled()

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_mark_clicked(self) -> None:
        self.add_marker_at(self._player.position(), self._name_edit.text())
        self._name_edit.clear()

    def _rebuild_list(self) -> None:
        self._list.clear()
        for ms, name in self._markers:
            self._list.addItem(QListWidgetItem(marker_row_label(ms / 1000.0, name)))

    def _refresh_split_enabled(self) -> None:
        # Need at least one marker to split into a named episode.
        self._split_button.setEnabled(bool(self._markers))

    def _toggle_play_pause(self) -> None:
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _on_scrub_released(self) -> None:
        self._player.setPosition(self._scrub.value())

    def _on_position_changed(self, position_ms: int) -> None:
        if not self._scrub.isSliderDown():
            self._scrub.setValue(position_ms)
        self._refresh_position_label(position_ms)

    def _on_duration_changed(self, duration_ms: int) -> None:
        self._duration_ms = max(0, duration_ms)
        self._scrub.setRange(0, self._duration_ms)
        self._refresh_position_label(self._player.position())

    def _on_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._play_button.setText("⏸" if playing else "▶")

    def _on_player_error(self, error, error_string: str) -> None:
        self.last_error = error_string or str(error)

    def _refresh_position_label(self, position_ms: int) -> None:
        pos = format_seconds(position_ms / 1000.0)
        if self._duration_ms <= 0:
            self._position_label.setText(f"{pos} / —")
        else:
            self._position_label.setText(
                f"{pos} / {format_seconds(self._duration_ms / 1000.0)}"
            )

    def _release_player(self) -> None:
        try:
            self._player.stop()
            self._player.setSource(QUrl())  # release the file handle
        except Exception:
            pass

    def _on_split(self) -> None:
        self._release_player()
        self.accept()

    def _on_close(self) -> None:
        self._release_player()
        self.reject()

    def reject(self) -> None:  # noqa: N802 (Qt convention)
        # The title-bar X routes here too — always release the handle so
        # the kept temp file can be deleted on Windows.
        self._release_player()
        super().reject()

    def keyPressEvent(self, event):  # noqa: N802 (Qt convention)
        if event.key() == Qt.Key.Key_Escape:
            self._on_close()
            return
        if event.key() == Qt.Key.Key_Space:
            self._toggle_play_pause()
            return
        super().keyPressEvent(event)
