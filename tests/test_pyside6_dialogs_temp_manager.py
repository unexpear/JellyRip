"""Phase 3c-iii final — gui_qt.dialogs.temp_manager tests."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from gui_qt.dialogs.temp_manager import (
    _NormalizedFolder,
    _TempManagerDialog,
    format_folder_summary,
    normalize_folders,
    show_temp_manager,
    status_object_name,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_normalize_folders_4_tuple():
    """4-tuple inputs pass straight through (with type coercion)."""
    out = normalize_folders([("/tmp/a", "a-name", 5, 4 * 1024**3)])
    assert len(out) == 1
    f = out[0]
    assert f.full_path == "/tmp/a"
    assert f.name == "a-name"
    assert f.file_count == 5
    assert f.size_bytes == 4 * 1024**3


def test_normalize_folders_4_list_also_accepted():
    """Lists with 4 entries are also accepted."""
    out = normalize_folders([["/tmp/a", "a", 1, 100]])
    assert out[0].name == "a"


def test_normalize_folders_string_path_uses_basename():
    """Bare path strings → name from basename, counts default 0."""
    out = normalize_folders(["/some/dir/Session_X"])
    assert out[0].name == "Session_X"
    assert out[0].file_count == 0
    assert out[0].size_bytes == 0


def test_normalize_folders_handles_trailing_slash():
    """``/foo/bar/`` → name should still be ``bar``, not empty."""
    out = normalize_folders(["/foo/bar/"])
    assert out[0].name == "bar"


def test_normalize_folders_coerces_count_strings():
    """Numeric strings in count/size fields coerce to ints."""
    out = normalize_folders([("/x", "x", "7", "9999")])
    assert out[0].file_count == 7
    assert out[0].size_bytes == 9999


def test_normalize_folders_handles_none_counts():
    """None counts coerce to 0 — pinned for resilience against stale data."""
    out = normalize_folders([("/x", "x", None, None)])
    assert out[0].file_count == 0
    assert out[0].size_bytes == 0


def test_normalize_folders_empty_returns_empty():
    assert normalize_folders([]) == []


@pytest.mark.parametrize("status,expected", [
    ("ripped",     "tempStatusRipped"),
    ("ripping",    "tempStatusBusy"),
    ("organizing", "tempStatusBusy"),
    ("organized",  "tempStatusOrganized"),
    ("unknown",    "tempStatusUnknown"),
    ("",           "tempStatusUnknown"),
    ("abandoned",  "tempStatusUnknown"),
])
def test_status_object_name_buckets(status, expected):
    """Each status string maps to the right QSS-targetable
    objectName.  Pinned because QSS rules use these names."""
    assert status_object_name(status) == expected


def test_format_folder_summary_shape():
    """Summary text matches the tkinter pattern exactly."""
    folder = _NormalizedFolder(
        full_path="/x", name="X", file_count=5, size_bytes=2 * 1024**3,
    )
    summary = format_folder_summary(folder, "2026-04-01", "ripped")
    assert "Ripped: 2026-04-01" in summary
    assert "Files: 5" in summary
    assert "Size: 2.0 GB" in summary
    assert "Status: ripped" in summary


def test_format_folder_summary_size_one_decimal():
    """Size is formatted to 1 decimal place — pinned because some
    folder sizes are well under 1 GB and we don't want truncation
    to show `0`."""
    folder = _NormalizedFolder("/x", "x", 1, 500_000_000)  # ~0.5 GB
    summary = format_folder_summary(folder, "ts", "s")
    assert "Size: 0.5 GB" in summary


# ---------------------------------------------------------------------------
# Dialog construction
# ---------------------------------------------------------------------------


class _StubEngine:
    """Returns canned metadata for read_temp_metadata."""
    def __init__(self, metadata=None):
        self._metadata = metadata or {}

    def read_temp_metadata(self, path):
        return self._metadata.get(path, {})


def test_dialog_chrome(qtbot):
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=_StubEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    assert d.windowTitle() == "Temp Session Manager"
    assert d.objectName() == "tempManagerDialog"
    assert d.isModal()


def test_dialog_one_row_per_folder(qtbot):
    d = _TempManagerDialog(
        old_folders=[
            ("/tmp/a", "a", 1, 1),
            ("/tmp/b", "b", 2, 2),
            ("/tmp/c", "c", 3, 3),
        ],
        engine=_StubEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    assert len(d.normalized_folders) == 3
    assert len(d.check_boxes) == 3


def test_dialog_uses_engine_metadata_for_status_color(qtbot):
    """A folder with status=ripped gets the ripped objectName on
    its status indicator label.  Pinned for theming-drift guard."""
    d = _TempManagerDialog(
        old_folders=[("/tmp/done", "done", 5, 1024)],
        engine=_StubEngine({"/tmp/done": {"status": "ripped", "title": "X"}}),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    from PySide6.QtWidgets import QLabel
    status_dots = [
        l for l in d.findChildren(QLabel)
        if l.text() == "*" and l.objectName().startswith("tempStatus")
    ]
    assert len(status_dots) == 1
    assert status_dots[0].objectName() == "tempStatusRipped"


def test_dialog_status_falls_back_when_metadata_missing(qtbot):
    """Engine returning empty dict → status defaults to "unknown",
    indicator gets the "unknown" objectName (red in QSS)."""
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=_StubEngine(),  # returns {} for everything
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    from PySide6.QtWidgets import QLabel
    status_dots = [
        l for l in d.findChildren(QLabel)
        if l.text() == "*" and l.objectName().startswith("tempStatus")
    ]
    assert status_dots[0].objectName() == "tempStatusUnknown"


def test_dialog_handles_engine_without_read_temp_metadata(qtbot):
    """If the engine doesn't implement read_temp_metadata, the
    dialog still constructs without crashing."""
    class BareEngine:
        pass
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=BareEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    assert len(d.check_boxes) == 1


def test_dialog_handles_engine_metadata_exception(qtbot):
    """If read_temp_metadata raises, the dialog still constructs
    and falls back to "unknown" status."""
    class BadEngine:
        def read_temp_metadata(self, path):
            raise RuntimeError("disk error")
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=BadEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    assert len(d.check_boxes) == 1


# ---------------------------------------------------------------------------
# Select All / Deselect All
# ---------------------------------------------------------------------------


def test_select_all_checks_every_row(qtbot):
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1), ("/tmp/b", "b", 2, 2)],
        engine=_StubEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    d._select_all_btn.click()
    assert all(cb.isChecked() for cb in d.check_boxes)


def test_deselect_all_unchecks_every_row(qtbot):
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1), ("/tmp/b", "b", 2, 2)],
        engine=_StubEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    d._select_all_btn.click()
    d._deselect_all_btn.click()
    assert all(not cb.isChecked() for cb in d.check_boxes)


# ---------------------------------------------------------------------------
# Selected folders accessor
# ---------------------------------------------------------------------------


def test_selected_folders_reflects_check_state(qtbot):
    d = _TempManagerDialog(
        old_folders=[
            ("/tmp/a", "a", 1, 1),
            ("/tmp/b", "b", 2, 2),
            ("/tmp/c", "c", 3, 3),
        ],
        engine=_StubEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    d.check_boxes[0].setChecked(True)
    d.check_boxes[2].setChecked(True)
    selected_names = [f.name for f in d.selected_folders]
    assert selected_names == ["a", "c"]


# ---------------------------------------------------------------------------
# Delete flow
# ---------------------------------------------------------------------------


def test_delete_selected_calls_deleter_for_each_checked_folder(qtbot):
    """Delete Selected runs the deleter on each checked folder via
    the thread runner.  Tests inject a synchronous runner so the
    thread doesn't outlive the test."""
    deleted: list[str] = []
    logs: list[str] = []

    def fake_deleter(path):
        deleted.append(path)

    def sync_runner(fn):
        fn()  # run inline for testability

    d = _TempManagerDialog(
        old_folders=[
            ("/tmp/a", "a", 1, 1),
            ("/tmp/b", "b", 2, 2),
            ("/tmp/c", "c", 3, 3),
        ],
        engine=_StubEngine(),
        log_fn=logs.append,
        deleter=fake_deleter,
        thread_runner=sync_runner,
    )
    qtbot.addWidget(d)
    d.check_boxes[0].setChecked(True)
    d.check_boxes[2].setChecked(True)
    d._delete_selected()

    assert deleted == ["/tmp/a", "/tmp/c"]
    assert any("Deleted temp folder: a" in m for m in logs)
    assert any("Deleted temp folder: c" in m for m in logs)


def test_delete_with_no_selection_does_not_call_deleter(qtbot):
    """If the user clicks Delete with nothing checked, no deletes
    happen — and we don't crash."""
    deleted: list[str] = []

    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=_StubEngine(),
        log_fn=lambda m: None,
        deleter=lambda p: deleted.append(p),
        thread_runner=lambda fn: fn(),
    )
    qtbot.addWidget(d)
    d._delete_selected()
    assert deleted == []


def test_delete_logs_failure_per_folder(qtbot):
    """If deleter raises for one folder, the error is logged but
    other deletions still proceed."""
    logs: list[str] = []

    def fake_deleter(path):
        if path == "/tmp/b":
            raise OSError("permission denied")

    d = _TempManagerDialog(
        old_folders=[
            ("/tmp/a", "a", 1, 1),
            ("/tmp/b", "b", 2, 2),
            ("/tmp/c", "c", 3, 3),
        ],
        engine=_StubEngine(),
        log_fn=logs.append,
        deleter=fake_deleter,
        thread_runner=lambda fn: fn(),
    )
    qtbot.addWidget(d)
    for cb in d.check_boxes:
        cb.setChecked(True)
    d._delete_selected()

    # b's failure logged
    assert any("Could not delete b" in m and "permission denied" in m for m in logs)
    # a and c still successful
    assert any("Deleted temp folder: a" in m for m in logs)
    assert any("Deleted temp folder: c" in m for m in logs)


def test_delete_closes_dialog_before_starting_worker(qtbot):
    """The dialog accepts (closes) BEFORE the worker thread runs.
    Pinned because tkinter version does this for UI responsiveness
    during slow deletions."""
    state = {"dialog_closed_at": None, "worker_started_at": None}
    timeline: list[str] = []

    def slow_runner(fn):
        timeline.append("worker_started")
        state["worker_started_at"] = len(timeline)
        fn()

    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=_StubEngine(),
        log_fn=lambda m: None,
        deleter=lambda p: None,
        thread_runner=slow_runner,
    )
    qtbot.addWidget(d)
    d.check_boxes[0].setChecked(True)
    # Override accept to track ordering
    real_accept = d.accept
    def tracked_accept():
        timeline.append("dialog_accepted")
        real_accept()
    d.accept = tracked_accept

    d._delete_selected()
    # dialog_accepted came before worker_started in the timeline
    assert timeline.index("dialog_accepted") < timeline.index("worker_started")


# ---------------------------------------------------------------------------
# Close / Esc
# ---------------------------------------------------------------------------


def test_close_button_accepts(qtbot):
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=_StubEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    d._close_btn.click()
    assert d.result() == 1  # accepted


def test_escape_closes(qtbot):
    d = _TempManagerDialog(
        old_folders=[("/tmp/a", "a", 1, 1)],
        engine=_StubEngine(),
        log_fn=lambda m: None,
    )
    qtbot.addWidget(d)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert d.result() == 1


# ---------------------------------------------------------------------------
# Public function — empty-folders short-circuit
# ---------------------------------------------------------------------------


def test_show_temp_manager_with_empty_folders_returns_immediately(qtbot, monkeypatch):
    """Empty input → returns None without opening the dialog.
    Mirrors tkinter's early return at gui/main_window.py:5930."""
    constructed: list = []

    real_init = _TempManagerDialog.__init__

    def fake_init(self, *args, **kwargs):
        constructed.append(True)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(_TempManagerDialog, "__init__", fake_init)
    result = show_temp_manager(None, [], None, lambda m: None)
    assert result is None
    assert constructed == []  # dialog NOT constructed


def test_show_temp_manager_returns_none(qtbot, monkeypatch):
    """Public function always returns None — side-effect-only."""
    monkeypatch.setattr(_TempManagerDialog, "exec", lambda self: 1)
    result = show_temp_manager(
        None, [("/tmp/a", "a", 1, 1)], _StubEngine(), lambda m: None,
    )
    assert result is None
