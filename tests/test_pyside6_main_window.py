"""Phase 3c-i shell — gui_qt.main_window tests.

Pins the shell's contract:

- Window construction with chrome (header / drive row / utility row /
  primary + secondary button rows / status bar / stop row / log
  panel header / log pane)
- Leaf widgets (LogPane, StatusBar) are present and accessible
- UIAdapter Protocol methods (handle_event, on_progress, on_log,
  on_error, on_complete) wire to the leaves correctly
- Status / progress / log methods (set_status, set_progress,
  start_indeterminate, stop_indeterminate, append_log) delegate
  to the leaves
- All workflow / utility / stop buttons exist with the right
  objectNames so QSS can target them
- Stub dialog methods raise NotImplementedError with helpful
  messages pointing at 3c-ii
- Click signals fire when buttons are clicked (3c-ii will wire
  these to controller methods)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QLabel,
    QPushButton,
)

from gui_qt.log_pane import LogPane
from gui_qt.main_window import MainWindow
from gui_qt.status_bar import StatusBar


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _FakeEvent:
    """Stand-in for shared.event.Event so tests don't depend on the
    real class (which lives in shared/ and may have its own deps)."""
    type: str
    job_id: str
    data: dict


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_main_window_objectname(qtbot):
    """The window itself gets ``mainWindow`` so QSS can target it."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert mw.objectName() == "mainWindow"


def test_main_window_title_is_app_name(qtbot):
    """Title bar reads "JellyRip" — same brand as tkinter."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert mw.windowTitle() == "JellyRip"


def test_main_window_has_log_pane(qtbot):
    """Shell embeds the LogPane leaf widget."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.log_pane, LogPane)


def test_main_window_has_status_bar(qtbot):
    """Shell embeds the StatusBar leaf widget."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.status_bar, StatusBar)


def test_main_window_has_drive_combo(qtbot):
    """Drive row has a ``QComboBox`` named ``driveCombo``."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert isinstance(mw.drive_combo, QComboBox)
    assert mw.drive_combo.objectName() == "driveCombo"


def test_main_window_has_drive_refresh_button(qtbot):
    """Drive row has the ↻ refresh button."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    refresh_btns = [
        b for b in mw.findChildren(QPushButton)
        if b.objectName() == "driveRefresh"
    ]
    assert len(refresh_btns) == 1


def test_main_window_has_app_header(qtbot):
    """Header band with the accent-colored title + subtitle."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    headers = [f for f in mw.findChildren(QFrame) if f.objectName() == "appHeader"]
    titles = [
        l for l in mw.findChildren(QLabel)
        if l.objectName() == "appHeaderTitle"
    ]
    subs = [
        l for l in mw.findChildren(QLabel)
        if l.objectName() == "appHeaderSubtitle"
    ]
    assert len(headers) == 1
    assert len(titles) == 1 and titles[0].text() == "JellyRip"
    assert len(subs) == 1


def test_main_window_has_log_panel_header(qtbot):
    """Log panel header has the LIVE LOG label and LED indicator."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    log_label = [
        l for l in mw.findChildren(QLabel)
        if l.objectName() == "logLabel"
    ]
    log_led = [
        l for l in mw.findChildren(QLabel)
        if l.objectName() == "logLed"
    ]
    assert len(log_label) == 1
    assert len(log_led) == 1


# ---------------------------------------------------------------------------
# Workflow + utility + stop buttons
# ---------------------------------------------------------------------------


_EXPECTED_WORKFLOW_BUTTONS = (
    "modeGoTv",
    "modeGoMovie",
    "modeInfoDump",
    "modeAltOrganize",
    "modeWarnPrep",
)

_EXPECTED_UTILITY_BUTTONS = (
    "utilSettings",
    "utilUpdates",
    "utilCopyLog",
    "utilBrowse",
)


def test_workflow_buttons_present_with_object_names(qtbot):
    """All 5 workflow buttons exist with the expected objectNames so
    the QSS [objectName^="modeGo"] / modeInfo / modeAlt / modeWarn
    selectors can color them per role."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    actual = set(mw.workflow_buttons.keys())
    expected = set(_EXPECTED_WORKFLOW_BUTTONS)
    assert actual == expected


def test_utility_buttons_present_with_object_names(qtbot):
    """All 4 utility chips exist with the expected objectNames."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    actual = set(mw.utility_buttons.keys())
    expected = set(_EXPECTED_UTILITY_BUTTONS)
    assert actual == expected


def test_stop_button_exists_and_initially_disabled(qtbot):
    """Stop Session button exists with ``stopButton`` objectName.
    Initially disabled — only enabled while a workflow is in flight."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert mw.stop_button.objectName() == "stopButton"
    assert not mw.stop_button.isEnabled()


def test_workflow_buttons_emit_signal_on_click(qtbot):
    """Clicking a workflow button emits ``workflow_button_clicked``
    with the button's objectName.  3c-ii wires this to the
    controller's run methods."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    button = mw.workflow_buttons["modeGoMovie"]
    with qtbot.waitSignal(mw.workflow_button_clicked, timeout=1000) as blocker:
        button.click()
    assert blocker.args == ["modeGoMovie"]


def test_utility_buttons_emit_signal_on_click(qtbot):
    """Triggering a utility action emits ``utility_button_clicked``.

    Pre-2026-05-04 these were ``QPushButton`` chips; they're now
    ``QAction`` items in a ``QToolBar``.  Test API stays
    ``mw.utility_buttons[name]`` but the call is ``.trigger()``
    instead of ``.click()`` since ``QAction`` doesn't implement
    ``click``."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    action = mw.utility_buttons["utilCopyLog"]
    with qtbot.waitSignal(mw.utility_button_clicked, timeout=1000) as blocker:
        action.trigger()
    assert blocker.args == ["utilCopyLog"]


def test_utility_toolbar_is_top_docked(qtbot):
    """The toolbar must dock at the top of the window — pinned so
    a future visual refactor that moves it (e.g., to the side)
    has to consciously update this test rather than silently
    breaking the platform convention."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QToolBar
    mw = MainWindow()
    qtbot.addWidget(mw)
    toolbar = mw.findChild(QToolBar, "utilityToolBar")
    assert toolbar is not None
    assert mw.toolBarArea(toolbar) == Qt.ToolBarArea.TopToolBarArea


def test_utility_toolbar_is_pinned_in_place(qtbot):
    """Movable + floatable disabled — the toolbar is the primary
    navigation surface; users shouldn't be able to drag it loose
    and lose it behind the window."""
    from PySide6.QtWidgets import QToolBar
    mw = MainWindow()
    qtbot.addWidget(mw)
    toolbar = mw.findChild(QToolBar, "utilityToolBar")
    assert toolbar is not None
    assert toolbar.isMovable() is False
    assert toolbar.isFloatable() is False


def test_drive_refresh_emits_signal_on_click(qtbot):
    """Clicking ↻ emits ``drive_refresh_clicked``.  3c-ii wires this
    to the controller's drive-scan path."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    refresh = next(
        b for b in mw.findChildren(QPushButton)
        if b.objectName() == "driveRefresh"
    )
    with qtbot.waitSignal(mw.drive_refresh_clicked, timeout=1000):
        refresh.click()


def test_workflow_button_click_emits_signal_silently(qtbot):
    """Clicking a workflow button emits ``workflow_button_clicked``
    but does NOT append any log line of its own.  The controller's
    own session-start lines fire microseconds later (via the
    ``WorkflowLauncher``) and tell the user what's happening.

    Pre-2026-05-04 this test pinned a "TODO 3c-ii: workflow button
    'modeGoTv' clicked" line — engineering noise that surfaced on
    every click.  Removing the log line was a UX-copy cleanup; this
    test is now the inverted guard against re-introducing it."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    button = mw.workflow_buttons["modeGoTv"]
    received = []
    mw.workflow_button_clicked.connect(received.append)
    button.click()
    # Signal fired with the right object name.
    assert received == ["modeGoTv"]
    # No engineering-shaped TODO line in the log.
    log_text = mw.log_pane.get_text()
    assert "TODO" not in log_text
    assert "modeGoTv" not in log_text


# ---------------------------------------------------------------------------
# Status / progress / log delegation
# ---------------------------------------------------------------------------


def test_set_status_delegates_to_status_bar(qtbot):
    """``set_status`` on the shell forwards to the StatusBar leaf."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.set_status("Ripping title 02")
    assert mw.status_bar.label_text == "Ripping title 02"
    assert mw.status_bar.label_role == "statusBusy"


def test_set_status_falls_back_to_ready_on_empty(qtbot):
    """Empty string normalizes to "Ready" — matches tkinter line 7527."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.set_status("")
    assert mw.status_bar.label_text == "Ready"


def test_set_progress_delegates_to_status_bar(qtbot):
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.set_progress(64)
    assert mw.status_bar.progress_value == 64
    assert mw.status_bar.progress_maximum == 100


def test_set_progress_clamps_negative_to_zero(qtbot):
    """Negative progress clamps to 0 — defensive matching tkinter
    line 7515 behavior."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.set_progress(-5)
    assert mw.status_bar.progress_value == 0


def test_set_progress_with_none_clamps_to_zero(qtbot):
    """``None`` is the tkinter signal for "clear" — treat as 0."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.set_progress(None)
    assert mw.status_bar.progress_value == 0


def test_start_indeterminate_switches_to_busy_mode(qtbot):
    """``start_indeterminate`` switches the progress bar to the
    marquee animation (max=0)."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.start_indeterminate()
    assert mw.status_bar.progress_maximum == 0


def test_stop_indeterminate_returns_to_determinate(qtbot):
    """``stop_indeterminate`` returns the bar to determinate mode at 0."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.start_indeterminate()
    mw.stop_indeterminate()
    assert mw.status_bar.progress_maximum == 100
    assert mw.status_bar.progress_value == 0


def test_append_log_delegates_to_log_pane(qtbot):
    """``append_log`` on the shell forwards to the LogPane leaf."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.append_log("startup banner")
    assert "startup banner" in mw.log_pane.get_text()


# ---------------------------------------------------------------------------
# UIAdapter Protocol
# ---------------------------------------------------------------------------


def test_handle_event_progress_updates_progress(qtbot):
    """Progress event → set_progress."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.handle_event(_FakeEvent(type="progress", job_id="rip-1", data={"percent": 42}))
    assert mw.status_bar.progress_value == 42


def test_handle_event_progress_with_non_numeric_is_ignored(qtbot):
    """Non-numeric percent is silently ignored — pinned because the
    controller can occasionally send malformed events during cleanup."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.handle_event(_FakeEvent(type="progress", job_id="rip-1", data={"percent": "fast"}))
    # Progress untouched (still at 0)
    assert mw.status_bar.progress_value == 0


def test_handle_event_log_appends(qtbot):
    """Log event → append_log."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.handle_event(_FakeEvent(type="log", job_id="rip-1", data={"message": "Decrypting BD"}))
    assert "Decrypting BD" in mw.log_pane.get_text()


def test_handle_event_done_sets_progress_to_100(qtbot):
    """Done event → set_progress(100), matching tkinter on_complete."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.handle_event(_FakeEvent(type="done", job_id="rip-1", data={}))
    assert mw.status_bar.progress_value == 100


def test_handle_event_error_logs_via_log_pane_in_3c_i(qtbot):
    """Error event in 3c-i logs the error inline (no modal dialog —
    that's 3c-ii).  The user still sees the error; just degraded UX
    until the dialog port lands."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    err = ValueError("disk full")
    mw.handle_event(_FakeEvent(type="error", job_id="rip-1", data={"error": err}))
    log_text = mw.log_pane.get_text()
    assert "ERROR" in log_text
    assert "disk full" in log_text
    assert "rip-1" in log_text


def test_handle_event_error_with_string_payload(qtbot):
    """Some controllers send string error payloads instead of
    Exception instances.  Pin that we wrap them rather than crashing."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.handle_event(_FakeEvent(type="error", job_id="rip-1", data={"error": "out of space"}))
    assert "out of space" in mw.log_pane.get_text()


def test_handle_event_unknown_type_is_silent(qtbot):
    """Unknown event types are silently dropped — pinned because the
    controller may send event types this version doesn't recognize
    (forward-compat)."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    # Should not raise.
    mw.handle_event(_FakeEvent(type="future_event_type", job_id="rip-1", data={}))


# ---------------------------------------------------------------------------
# 3c-ii territory — stubbed dialog methods
# ---------------------------------------------------------------------------


def test_no_dialog_methods_remain_stubbed(qtbot):
    """Phase 3c-iii completion guard — every originally-stubbed
    dialog method is now wired.  This test will fail loudly if a
    future regression accidentally re-stubs one of them."""
    mw = MainWindow()
    qtbot.addWidget(mw)
    # Each method name + a plausible call.  None should raise
    # NotImplementedError.  We monkeypatch the dialog modules' real
    # functions in the parametric delegation test below; this guard
    # just verifies nothing here raises NIE.
    import gui_qt.main_window as mw_module
    for attr in ("_show_info", "_show_error", "_ask_yesno", "_ask_input",
                 "_ask_space_override", "_ask_duplicate_resolution",
                 "_ask_tv_setup", "_ask_movie_setup", "_show_disc_tree",
                 "_show_extras_picker", "_show_file_list",
                 "_show_temp_manager"):
        setattr(mw_module, attr, lambda *a, **k: None)

    # Each call below should NOT raise NotImplementedError.
    mw.show_info("t", "m")
    mw.show_error("t", "m")
    mw.ask_yesno("p")
    mw.ask_input("l", "p")
    mw.ask_space_override(50.0, 12.5)
    mw.ask_duplicate_resolution("p")
    mw.ask_tv_setup()
    mw.ask_movie_setup()
    mw.show_disc_tree([], False)
    mw.show_extras_picker("t", "p", [])
    mw.show_file_list("t", "p", [])
    mw.show_temp_manager([], None, lambda m: None)


# ---------------------------------------------------------------------------
# 3c-ii — wired dialog delegation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shell_method,dialog_module_attr,return_value", [
    ("show_info",                ("info",                 "show_info"),                None),
    ("show_error",               ("info",                 "show_error"),               None),
    ("ask_yesno",                ("ask",                  "ask_yesno"),                True),
    ("ask_input",                ("ask",                  "ask_input"),                "user-text"),
    ("ask_space_override",       ("space_override",       "ask_space_override"),       True),
    ("ask_duplicate_resolution", ("duplicate_resolution", "ask_duplicate_resolution"), "retry"),
    ("ask_tv_setup",             ("session_setup",        "ask_tv_setup"),             "TV_OBJ"),
    ("ask_movie_setup",          ("session_setup",        "ask_movie_setup"),          "MOVIE_OBJ"),
    ("show_disc_tree",           ("disc_tree",            "show_disc_tree"),           ["0", "2"]),
    ("show_extras_picker",       ("list_picker",          "show_extras_picker"),       [0, 1]),
    ("show_file_list",           ("list_picker",          "show_file_list"),           ["a"]),
    ("show_temp_manager",        ("temp_manager",         "show_temp_manager"),        None),
])
def test_dialog_methods_delegate_to_dialog_modules(
    qtbot, monkeypatch, shell_method, dialog_module_attr, return_value
):
    """Each wired dialog method on MainWindow delegates to the
    matching function in ``gui_qt.dialogs.*``.  Monkeypatching the
    underlying function and verifying the return value flows back
    pins the wiring without invoking real modal dialogs."""
    import gui_qt.main_window as mw_module

    # The shell imports are aliased with leading underscores
    # (e.g., ``_show_info``).  Map ``show_info`` → ``_show_info``.
    aliased_attr = "_" + dialog_module_attr[1]
    captured: dict = {}

    def fake(*args, **kwargs):
        captured["called"] = True
        captured["args"] = args
        captured["kwargs"] = kwargs
        return return_value

    monkeypatch.setattr(mw_module, aliased_attr, fake)

    mw = MainWindow()
    qtbot.addWidget(mw)

    # Call with minimal args matching each method's signature.
    if shell_method == "show_info":
        mw.show_info("title", "msg")
    elif shell_method == "show_error":
        mw.show_error("title", "msg")
    elif shell_method == "ask_yesno":
        result = mw.ask_yesno("prompt")
        assert result is True
    elif shell_method == "ask_input":
        result = mw.ask_input("label", "prompt")
        assert result == "user-text"
    elif shell_method == "ask_space_override":
        result = mw.ask_space_override(50.0, 12.5)
        assert result is True
    elif shell_method == "ask_duplicate_resolution":
        result = mw.ask_duplicate_resolution("dup prompt")
        assert result == "retry"
    elif shell_method == "ask_tv_setup":
        result = mw.ask_tv_setup(default_title="BB")
        assert result == "TV_OBJ"
    elif shell_method == "ask_movie_setup":
        result = mw.ask_movie_setup(default_title="Inception")
        assert result == "MOVIE_OBJ"
    elif shell_method == "show_disc_tree":
        result = mw.show_disc_tree([{"id": 0}], False)
        assert result == ["0", "2"]
    elif shell_method == "show_extras_picker":
        result = mw.show_extras_picker("T", "P", ["a", "b"])
        assert result == [0, 1]
    elif shell_method == "show_file_list":
        result = mw.show_file_list("T", "P", ["a", "b"])
        assert result == ["a"]
    elif shell_method == "show_temp_manager":
        result = mw.show_temp_manager([("/x", "x", 1, 1)], None, lambda m: None)
        assert result is None

    assert captured.get("called"), (
        f"{shell_method!r} did not delegate to the dialog module"
    )


# ---------------------------------------------------------------------------
# Theme tag colors
# ---------------------------------------------------------------------------


def test_theme_tag_colors_propagate_to_log_pane(qtbot):
    """``theme_tag_colors`` passed at construction time reaches the
    LogPane and overrides the dark_github defaults."""
    mw = MainWindow(
        cfg={},
        theme_tag_colors={"prompt": "#abcdef", "answer": "#fedcba"},
    )
    qtbot.addWidget(mw)
    assert mw.log_pane.tag_colors["prompt"] == "#abcdef"
    assert mw.log_pane.tag_colors["answer"] == "#fedcba"
