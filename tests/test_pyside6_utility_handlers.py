"""Phase 3c-ii pass 3 — gui_qt.utility_handlers tests."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QApplication, QFileDialog

from gui_qt.main_window import MainWindow
from gui_qt.utility_handlers import UtilityHandler


# ---------------------------------------------------------------------------
# Settings — defer to 3d, just logs a notice
# ---------------------------------------------------------------------------


def test_util_settings_opens_settings_dialog(qtbot, monkeypatch):
    """Clicking Settings opens the new gui_qt.settings dialog
    (delivered in Phase 3d theme-picker pass).  We monkeypatch
    show_settings to avoid a real modal in the test thread."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    captured: dict = {}

    def fake_show(parent, cfg, **kwargs):
        captured["parent"] = parent
        captured["cfg"] = cfg
        return True  # user pressed OK

    import gui_qt.settings as settings_mod
    monkeypatch.setattr(settings_mod, "show_settings", fake_show)

    window.utility_button_clicked.emit("utilSettings")
    QApplication.instance().processEvents()

    assert captured.get("parent") is window
    log = window.log_pane.get_text()
    assert "Settings saved" in log


def test_util_settings_logs_close_without_save(qtbot, monkeypatch):
    """Cancelling the settings dialog logs "closed without saving"."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    import gui_qt.settings as settings_mod
    monkeypatch.setattr(
        settings_mod, "show_settings",
        lambda parent, cfg, **kwargs: False,  # user cancelled
    )

    window.utility_button_clicked.emit("utilSettings")
    QApplication.instance().processEvents()

    log = window.log_pane.get_text()
    assert "closed without saving" in log


# ---------------------------------------------------------------------------
# Updates — calls into gui.update_ui.check_for_updates
# ---------------------------------------------------------------------------


def test_util_updates_calls_check_for_updates(qtbot, monkeypatch):
    """Clicking Updates invokes the existing ``check_for_updates``
    flow with the window as the gui argument.  We monkeypatch the
    handler method itself because the deferred import inside it
    pulls tkinter (sandbox limitation)."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    captured: list = []

    # Replace the bound method on the instance so the deferred
    # import doesn't fire.
    def fake_handle(self):
        captured.append(("invoked", self._window))

    monkeypatch.setattr(
        UtilityHandler, "handle_utilUpdates", fake_handle,
    )

    window.utility_button_clicked.emit("utilUpdates")
    QApplication.instance().processEvents()

    assert len(captured) == 1
    assert captured[0][0] == "invoked"
    assert captured[0][1] is window


# ---------------------------------------------------------------------------
# Copy Log
# ---------------------------------------------------------------------------


def test_util_copy_log_writes_to_clipboard(qtbot):
    """``utilCopyLog`` copies the log pane's content to the system
    clipboard and confirms via append_log."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    # Seed the log
    window.append_log("disc 1: ripped")
    window.append_log("disc 2: ripped")
    QApplication.instance().processEvents()

    window.utility_button_clicked.emit("utilCopyLog")
    QApplication.instance().processEvents()

    clipboard = QApplication.clipboard()
    assert "disc 1: ripped" in clipboard.text()
    assert "disc 2: ripped" in clipboard.text()
    # Confirmation logged
    log = window.log_pane.get_text()
    assert "copied to clipboard" in log


def test_util_copy_log_empty_log_logs_notice(qtbot):
    """If the log is empty, the chip logs a "nothing to copy" notice
    and doesn't touch the clipboard."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    # Pre-clear clipboard via a known marker
    QApplication.clipboard().setText("__SENTINEL__")

    window.utility_button_clicked.emit("utilCopyLog")
    QApplication.instance().processEvents()

    log = window.log_pane.get_text()
    assert "Log is empty" in log
    # Clipboard untouched
    assert QApplication.clipboard().text() == "__SENTINEL__"


# ---------------------------------------------------------------------------
# Browse Folder
# ---------------------------------------------------------------------------


def test_util_browse_logs_selected_folder(qtbot, monkeypatch):
    """Clicking Browse Folder opens a folder picker; if the user
    chooses a folder, the path is logged."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *args, **kwargs: "/some/folder/the/user/picked",
    )

    window.utility_button_clicked.emit("utilBrowse")
    QApplication.instance().processEvents()

    log = window.log_pane.get_text()
    assert "/some/folder/the/user/picked" in log


def test_util_browse_cancelled_does_not_log(qtbot, monkeypatch):
    """Cancelling the folder picker (empty string) → no log line."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *args, **kwargs: "",
    )

    log_before = window.log_pane.get_text()
    window.utility_button_clicked.emit("utilBrowse")
    QApplication.instance().processEvents()
    log_after = window.log_pane.get_text()
    assert log_before == log_after


# ---------------------------------------------------------------------------
# Unknown chip
# ---------------------------------------------------------------------------


def test_unknown_chip_logs_no_handler(qtbot):
    """A chip name without a matching handler logs a notice rather
    than crashing."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    window.utility_button_clicked.emit("utilNonexistent")
    QApplication.instance().processEvents()

    log = window.log_pane.get_text()
    assert "no handler" in log
    assert "utilNonexistent" in log


# ---------------------------------------------------------------------------
# Connect/disconnect lifecycle
# ---------------------------------------------------------------------------


def test_connect_idempotent(qtbot):
    """Double-connect doesn't double-fire the handler.  Uses the
    Copy Log chip rather than Settings to avoid spinning up a
    real settings dialog modal during the test."""
    window = MainWindow()
    qtbot.addWidget(window)
    # Pre-seed the log so Copy Log has something to copy
    window.append_log("seed line")
    QApplication.instance().processEvents()

    handler = UtilityHandler(window)
    handler.connect_signals()
    handler.connect_signals()  # second call

    window.utility_button_clicked.emit("utilCopyLog")
    QApplication.instance().processEvents()

    log = window.log_pane.get_text()
    # Only one log line about copying — if double-connected, would be 2
    assert log.count("Log copied to clipboard") == 1


def test_disconnect_stops_dispatch(qtbot):
    """After disconnect, signals don't reach handlers."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.append_log("seed line")
    QApplication.instance().processEvents()

    handler = UtilityHandler(window)
    handler.connect_signals()
    handler.disconnect_signals()

    window.utility_button_clicked.emit("utilCopyLog")
    QApplication.instance().processEvents()

    log = window.log_pane.get_text()
    assert "Log copied to clipboard" not in log


def test_handler_exception_is_caught_and_logged(qtbot, monkeypatch):
    """If a handler raises, the dispatcher logs the error rather
    than crashing the app."""
    window = MainWindow()
    qtbot.addWidget(window)
    handler = UtilityHandler(window)
    handler.connect_signals()

    monkeypatch.setattr(
        UtilityHandler, "handle_utilUpdates",
        lambda self: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    window.utility_button_clicked.emit("utilUpdates")
    QApplication.instance().processEvents()

    log = window.log_pane.get_text()
    assert "failed" in log
    assert "boom" in log
