"""Phase 3c-iii — gui_qt.drive_handler tests."""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import QCoreApplication

from gui_qt.drive_handler import DriveHandler, _coerce_drive_info, _default_drive_info
from gui_qt.main_window import MainWindow
from utils.helpers import MakeMKVDriveInfo


def _drain_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    app = QCoreApplication.instance()
    while time.time() < deadline:
        if predicate():
            return True
        if app is not None:
            app.processEvents()
        time.sleep(0.005)
    return predicate()


def _drive(idx, name="BD-RE", disc="Disc"):
    return MakeMKVDriveInfo(
        index=idx, state_code=2, flags_code=999, disc_type_code=0,
        drive_name=name, disc_name=disc, device_path=f"disc:{idx}",
    )


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_coerce_passes_through_makemkv_drive_info():
    d = _drive(0)
    assert _coerce_drive_info(d) is d


def test_coerce_tuple_form():
    """``(idx, name)`` tuples become MakeMKVDriveInfo with sensible
    defaults — matches tkinter at gui/main_window.py:233."""
    d = _coerce_drive_info((3, "TestDrive"))
    assert d.index == 3
    assert d.drive_name == "TestDrive"
    assert d.device_path == "disc:3"


def test_coerce_garbage_falls_back_to_default():
    """Malformed input → default sentinel, no exception."""
    d = _coerce_drive_info("garbage")
    assert d.drive_name == "(no drives detected)"
    assert d.index == 0


def test_default_drive_info_is_sentinel():
    d = _default_drive_info()
    assert "no drives" in d.drive_name.lower()


# ---------------------------------------------------------------------------
# populate_combo
# ---------------------------------------------------------------------------


def test_populate_combo_with_drives(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    h = DriveHandler(mw, cfg={"opt_drive_index": 0})
    h.connect_signals()
    h.populate_combo([_drive(0, "A"), _drive(1, "B")])
    assert mw.drive_combo.count() == 2
    assert mw.drive_combo.isEnabled()
    assert "Drive 0" in mw.drive_combo.itemText(0)
    assert "Drive 1" in mw.drive_combo.itemText(1)


def test_populate_combo_restores_prior_selection(qtbot):
    """If cfg has ``opt_drive_index=1``, combo restores to that drive."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    h = DriveHandler(mw, cfg={"opt_drive_index": 1})
    h.connect_signals()
    h.populate_combo([_drive(0, "A"), _drive(1, "B"), _drive(2, "C")])
    assert mw.drive_combo.currentIndex() == 1


def test_populate_combo_empty_falls_back_to_placeholder(qtbot):
    """Empty input → single placeholder row, combo still enabled."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    h = DriveHandler(mw, cfg={})
    h.connect_signals()
    h.populate_combo([])
    assert mw.drive_combo.count() == 1
    assert "no drives" in mw.drive_combo.itemText(0).lower()


def test_populate_combo_when_index_not_present(qtbot):
    """If cfg's ``opt_drive_index`` doesn't match any drive, fall
    back to index 0."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    h = DriveHandler(mw, cfg={"opt_drive_index": 99})
    h.connect_signals()
    h.populate_combo([_drive(0), _drive(1)])
    assert mw.drive_combo.currentIndex() == 0


def test_populate_blocks_signals_during_repopulate(qtbot):
    """The combo's currentIndexChanged signal must not fire during
    populate_combo — otherwise the user's prior selection would
    accidentally trigger a "user picked a drive" save."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    cfg = {"opt_drive_index": 1}
    saves: list = []
    h = DriveHandler(mw, cfg=cfg, save_cfg=lambda c: saves.append(dict(c)))
    h.connect_signals()
    # First populate
    h.populate_combo([_drive(0), _drive(1)])
    initial_save_count = len(saves)
    # Repopulate with same drives — should not fire save
    h.populate_combo([_drive(0), _drive(1)])
    assert len(saves) == initial_save_count


# ---------------------------------------------------------------------------
# Refresh button → worker thread → populate
# ---------------------------------------------------------------------------


def test_refresh_async_calls_scanner_in_worker_thread(qtbot):
    """refresh_async spawns a daemon thread that calls the scanner."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    captured: dict = {}

    def fake_scanner():
        captured["thread_name"] = threading.current_thread().name
        return [_drive(0)]

    h = DriveHandler(mw, cfg={}, scanner=fake_scanner)
    h.connect_signals()
    t = h.refresh_async()
    t.join(timeout=2.0)

    # Drain events so populate_combo runs
    _drain_until(lambda: mw.drive_combo.count() > 0, timeout=2.0)
    assert captured.get("thread_name") == "drive-scan"
    assert mw.drive_combo.count() == 1


def test_refresh_button_triggers_scan(qtbot):
    """Clicking ↻ emits drive_refresh_clicked → handler scans."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    captured: dict = {"calls": 0}

    def fake_scanner():
        captured["calls"] += 1
        return [_drive(0, "X")]

    h = DriveHandler(mw, cfg={}, scanner=fake_scanner)
    h.connect_signals()

    mw.drive_refresh_clicked.emit()
    # Give the worker a moment, then drain events
    assert _drain_until(lambda: captured["calls"] >= 1, timeout=2.0)
    assert _drain_until(lambda: "Drive 0: X" in mw.drive_combo.itemText(0), timeout=2.0)


def test_scanner_exception_logged_and_combo_falls_back(qtbot):
    """If the scanner raises, the error is logged and the combo
    falls back to the placeholder rather than leaving stale state."""
    mw = MainWindow()
    qtbot.addWidget(mw)

    def boom():
        raise RuntimeError("makemkv missing")

    h = DriveHandler(mw, cfg={}, scanner=boom)
    h.connect_signals()
    t = h.refresh_async()
    t.join(timeout=2.0)
    _drain_until(lambda: "makemkv missing" in mw.log_pane.get_text(), timeout=2.0)
    _drain_until(lambda: mw.drive_combo.count() == 1, timeout=2.0)
    log = mw.log_pane.get_text()
    assert "Drive scan failed" in log
    assert "makemkv missing" in log
    assert "no drives" in mw.drive_combo.itemText(0).lower()


# ---------------------------------------------------------------------------
# User combo change → cfg persistence
# ---------------------------------------------------------------------------


def test_user_combo_change_persists_drive_index(qtbot):
    """When the user picks a different drive in the combo, the
    handler writes opt_drive_index to cfg and calls save_cfg."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    cfg = {"opt_drive_index": 0}
    saves: list = []

    h = DriveHandler(mw, cfg=cfg, save_cfg=lambda c: saves.append(dict(c)))
    h.connect_signals()
    h.populate_combo([_drive(0), _drive(2), _drive(5)])

    # Now simulate the user picking the third option (drive index 5)
    mw.drive_combo.setCurrentIndex(2)
    QCoreApplication.instance().processEvents()

    assert cfg["opt_drive_index"] == 5
    assert saves and saves[-1]["opt_drive_index"] == 5


def test_user_combo_change_logs_selection(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    h = DriveHandler(mw, cfg={"opt_drive_index": 0})
    h.connect_signals()
    h.populate_combo([_drive(0, "AlphaDrive"), _drive(1, "BetaDrive")])

    mw.drive_combo.setCurrentIndex(1)
    QCoreApplication.instance().processEvents()

    log = mw.log_pane.get_text()
    assert "Drive selected" in log
    assert "BetaDrive" in log


def test_save_cfg_failure_does_not_crash(qtbot):
    """If save_cfg throws, the handler logs but keeps going."""
    mw = MainWindow()
    qtbot.addWidget(mw)

    def bad_save(c):
        raise OSError("disk full")

    h = DriveHandler(mw, cfg={"opt_drive_index": 0}, save_cfg=bad_save)
    h.connect_signals()
    h.populate_combo([_drive(0), _drive(1)])

    # Trigger a change — should log the error but not raise
    mw.drive_combo.setCurrentIndex(1)
    QCoreApplication.instance().processEvents()
    log = mw.log_pane.get_text()
    assert "disk full" in log


# ---------------------------------------------------------------------------
# Connect/disconnect lifecycle
# ---------------------------------------------------------------------------


def test_connect_idempotent(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    captured: dict = {"calls": 0}
    h = DriveHandler(mw, cfg={}, scanner=lambda: (captured.__setitem__("calls", captured["calls"] + 1) or [_drive(0)]))
    h.connect_signals()
    h.connect_signals()  # second call no-op

    mw.drive_refresh_clicked.emit()
    _drain_until(lambda: captured["calls"] >= 1, timeout=2.0)
    # If double-connected, we'd see 2 calls.  Ensure exactly 1.
    time.sleep(0.05)  # give the second handler a chance if it would fire
    QCoreApplication.instance().processEvents()
    assert captured["calls"] == 1


def test_disconnect_stops_routing(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    captured: dict = {"calls": 0}
    h = DriveHandler(mw, cfg={}, scanner=lambda: (captured.__setitem__("calls", captured["calls"] + 1) or [_drive(0)]))
    h.connect_signals()
    h.disconnect_signals()
    mw.drive_refresh_clicked.emit()
    QCoreApplication.instance().processEvents()
    time.sleep(0.05)
    assert captured["calls"] == 0


# ---------------------------------------------------------------------------
# Disc-state glyph cfg plumbing — Appearance tab Phase A (2026-05-04)
# ---------------------------------------------------------------------------


def test_populate_combo_with_glyph_enabled(qtbot):
    """Default cfg → labels include the disc-state glyph."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    cfg = {"opt_drive_state_glyph": True}
    h = DriveHandler(mw, cfg=cfg, scanner=lambda: [_drive(0)])
    h.populate_combo([_drive(0)])
    assert "◉" in mw.drive_combo.itemText(0)


def test_populate_combo_with_glyph_disabled(qtbot):
    """``opt_drive_state_glyph=False`` strips the glyph from the
    rendered combo labels."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    cfg = {"opt_drive_state_glyph": False}
    h = DriveHandler(mw, cfg=cfg, scanner=lambda: [_drive(0)])
    h.populate_combo([_drive(0)])
    label = mw.drive_combo.itemText(0)
    assert "◉" not in label
    assert "⊚" not in label
    assert "◌" not in label


def test_refresh_labels_re_renders_after_toggle(qtbot):
    """``refresh_labels`` re-formats the combo using current cfg —
    the Appearance tab calls this after toggling
    ``opt_drive_state_glyph``."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    cfg = {"opt_drive_state_glyph": True}
    h = DriveHandler(mw, cfg=cfg, scanner=lambda: [_drive(0)])
    h.populate_combo([_drive(0)])
    assert "◉" in mw.drive_combo.itemText(0)

    cfg["opt_drive_state_glyph"] = False
    h.refresh_labels()
    assert "◉" not in mw.drive_combo.itemText(0)
    assert "⊚" not in mw.drive_combo.itemText(0)


def test_refresh_labels_preserves_selection(qtbot):
    """Re-rendering must not jump the user's selection.  Pinned
    because re-populating a combo without preserving index is a
    classic regression."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    cfg = {"opt_drive_state_glyph": True}
    h = DriveHandler(mw, cfg=cfg, scanner=lambda: [_drive(0), _drive(1)])
    h.populate_combo([_drive(0), _drive(1)])
    mw.drive_combo.setCurrentIndex(1)

    cfg["opt_drive_state_glyph"] = False
    h.refresh_labels()
    assert mw.drive_combo.currentIndex() == 1


def test_refresh_labels_with_no_drives_is_noop(qtbot):
    """Calling refresh_labels before any drives are populated must
    not raise — the toggle could fire at any time."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    h = DriveHandler(mw, cfg={"opt_drive_state_glyph": True}, scanner=lambda: [])
    h.refresh_labels()  # should not raise
