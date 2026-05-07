"""Phase 3c-iii final — Prep MKVs MVP tests.

Pins the modeWarnPrep handler's behavior:

- Pure helper ``find_mkv_files`` walks recursively, case-
  insensitive on the .mkv extension, sorted output.
- Click → folder picker → MKV scan → summary via show_info.
- Cancel folder picker → log "cancelled", no further calls.
- Empty folder → show_info with "no MKVs" message.
- Found MKVs → show_info with count + brief pointer.
- Scan error → show_error.

The handler runs on a worker thread (via WorkflowLauncher.start_task),
so each ``window.*`` method is thread-safe; the test thread acts as
the worker for simplicity.
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from gui_qt.main_window import MainWindow
from gui_qt.workflow_launchers import (
    _BUTTON_TO_CONTROLLER_METHOD,
    WorkflowLauncher,
    find_mkv_files,
)


# ---------------------------------------------------------------------------
# Pure helper: find_mkv_files
# ---------------------------------------------------------------------------


def test_find_mkv_files_empty_folder():
    """Empty folder → empty list, no error."""
    with tempfile.TemporaryDirectory() as td:
        assert find_mkv_files(td) == []


def test_find_mkv_files_finds_top_level_mkv(tmp_path):
    (tmp_path / "movie.mkv").write_text("x")
    found = find_mkv_files(str(tmp_path))
    assert len(found) == 1
    assert found[0].endswith("movie.mkv")


def test_find_mkv_files_recurses_subdirs(tmp_path):
    """``find_mkv_files`` walks recursively — pinned because the
    real prep workflow needs to find MKVs in season folders, etc."""
    (tmp_path / "top.mkv").write_text("x")
    sub = tmp_path / "season1"
    sub.mkdir()
    (sub / "ep01.mkv").write_text("x")
    (sub / "ep02.mkv").write_text("x")

    found = find_mkv_files(str(tmp_path))
    assert len(found) == 3


def test_find_mkv_files_case_insensitive_extension(tmp_path):
    """Both ``.mkv`` and ``.MKV`` are recognized."""
    (tmp_path / "lower.mkv").write_text("x")
    (tmp_path / "UPPER.MKV").write_text("x")
    (tmp_path / "Mixed.Mkv").write_text("x")
    found = find_mkv_files(str(tmp_path))
    assert len(found) == 3


def test_find_mkv_files_skips_other_extensions(tmp_path):
    """Non-mkv files are ignored."""
    (tmp_path / "movie.mkv").write_text("x")
    (tmp_path / "info.txt").write_text("x")
    (tmp_path / "thumbnail.jpg").write_text("x")
    (tmp_path / "subtitle.srt").write_text("x")
    found = find_mkv_files(str(tmp_path))
    assert len(found) == 1


def test_find_mkv_files_sorted_output(tmp_path):
    """Output is sorted — pinned for stable display in the log."""
    for name in ["zebra.mkv", "alpha.mkv", "mango.mkv"]:
        (tmp_path / name).write_text("x")
    found = find_mkv_files(str(tmp_path))
    names = [os.path.basename(p) for p in found]
    assert names == sorted(names)


def test_find_mkv_files_empty_folder_arg():
    """Empty string folder → empty list, no crash."""
    assert find_mkv_files("") == []


# ---------------------------------------------------------------------------
# modeWarnPrep mapping & dispatch
# ---------------------------------------------------------------------------


def test_modewarnprep_not_in_controller_mapping():
    """``modeWarnPrep`` is deliberately NOT in the controller
    method mapping — it routes through ``_run_prep_mvp`` instead.
    Pinned so a future refactor doesn't accidentally add it back."""
    assert "modeWarnPrep" not in _BUTTON_TO_CONTROLLER_METHOD


# ---------------------------------------------------------------------------
# Prep MVP — happy path
# ---------------------------------------------------------------------------


class _StubController:
    """Minimal controller stub — Prep doesn't call any controller
    methods, but the launcher needs one to construct."""
    session_log: list = []
    session_report: list = []
    start_time = None
    global_extra_counter = 0


class _StubEngine:
    def __init__(self):
        import threading
        self.abort_event = threading.Event()
    def reset_abort(self):
        self.abort_event.clear()


def _wired(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    launcher = WorkflowLauncher(window, _StubController(), _StubEngine())
    return window, launcher


def test_prep_mvp_logs_summary_when_mkvs_found(qtbot, tmp_path, monkeypatch):
    """Folder with MKVs → log lists each file + summary message."""
    (tmp_path / "movie.mkv").write_text("x")
    (tmp_path / "extra.mkv").write_text("x")

    window, launcher = _wired(qtbot)

    # Stub ask_directory → return our tmp_path
    monkeypatch.setattr(window, "ask_directory", lambda *a, **k: str(tmp_path))
    # Stub show_info → capture the message
    captured: dict = {}
    monkeypatch.setattr(
        window, "show_info",
        lambda title, msg: captured.setdefault("info", (title, msg)),
    )

    launcher._run_prep_mvp()

    log = window.log_pane.get_text()
    assert "Scanning" in log
    assert "movie.mkv" in log
    assert "extra.mkv" in log
    assert "Prep: scanned 2 MKVs" in log
    assert captured["info"][0] == "Prep MKVs"
    assert "Found 2 MKV file(s)" in captured["info"][1]
    assert "phase-3c-iii-prep-workflow.md" in captured["info"][1]


def test_prep_mvp_handles_empty_folder(qtbot, tmp_path, monkeypatch):
    """Folder with no MKVs → "no MKVs found" message, no per-file
    log lines."""
    window, launcher = _wired(qtbot)
    monkeypatch.setattr(window, "ask_directory", lambda *a, **k: str(tmp_path))
    captured: dict = {}
    monkeypatch.setattr(
        window, "show_info",
        lambda title, msg: captured.setdefault("info", (title, msg)),
    )

    launcher._run_prep_mvp()

    assert captured["info"][0] == "Prep MKVs"
    assert "No .mkv files found" in captured["info"][1]
    assert "Prep: no MKVs found" in window.log_pane.get_text()


def test_prep_mvp_handles_cancelled_folder_pick(qtbot, monkeypatch):
    """User cancels folder picker → log "cancelled", no show_info."""
    window, launcher = _wired(qtbot)
    monkeypatch.setattr(window, "ask_directory", lambda *a, **k: None)
    show_info_calls: list = []
    monkeypatch.setattr(
        window, "show_info",
        lambda title, msg: show_info_calls.append((title, msg)),
    )

    launcher._run_prep_mvp()

    assert "Prep cancelled" in window.log_pane.get_text()
    assert show_info_calls == []


def test_prep_mvp_handles_scan_error(qtbot, monkeypatch):
    """If find_mkv_files raises, show_error with the message."""
    window, launcher = _wired(qtbot)
    monkeypatch.setattr(window, "ask_directory", lambda *a, **k: "/some/folder")
    # Force find_mkv_files to raise by patching it on the launcher's module
    import gui_qt.workflow_launchers as wl_module
    monkeypatch.setattr(
        wl_module, "find_mkv_files",
        lambda folder: (_ for _ in ()).throw(OSError("permission denied")),
    )
    error_calls: list = []
    monkeypatch.setattr(
        window, "show_error",
        lambda title, msg: error_calls.append((title, msg)),
    )

    launcher._run_prep_mvp()

    assert error_calls
    assert error_calls[0][0] == "Prep MKVs"
    assert "permission denied" in error_calls[0][1]


# ---------------------------------------------------------------------------
# Click signal dispatch
# ---------------------------------------------------------------------------


def test_prep_button_click_dispatches_through_prep_handler(qtbot, monkeypatch):
    """Clicking the Prep button (signal payload ``modeWarnPrep``)
    routes through ``_run_prep_mvp``, not through any controller
    method.  Pinned for the special-case dispatch logic."""
    window, launcher = _wired(qtbot)
    launcher.connect_signals()

    captured: dict = {"prep_called": False}
    monkeypatch.setattr(
        launcher, "_run_prep_mvp",
        lambda: captured.update(prep_called=True),
    )

    # Stub ask_directory just in case (shouldn't be reached)
    monkeypatch.setattr(window, "ask_directory", lambda *a, **k: None)

    window.workflow_button_clicked.emit("modeWarnPrep")

    # Wait briefly for the worker thread to fire
    from PySide6.QtCore import QCoreApplication
    import time
    deadline = time.time() + 2.0
    while time.time() < deadline and not captured["prep_called"]:
        QCoreApplication.instance().processEvents()
        time.sleep(0.005)

    assert captured["prep_called"]
