"""Phase 3c-ii — dialog module tests.

Pins the contract for the dialogs in ``gui_qt/dialogs/``:

* ``show_info`` / ``show_error`` — QMessageBox-based; we test the
  message body / title / icon are wired correctly via monkeypatched
  exec.
* ``ask_yesno`` — bool result, default-No on Esc.
* ``ask_input`` — str / None on cancel.
* ``ask_space_override`` — purpose-built dialog; default Cancel.
* ``ask_duplicate_resolution`` — three-way; default Stop on Esc.

Behavior-first.  No real modal exec — we monkeypatch ``exec``
methods (or the static helpers) to return canned values, then
inspect the resulting dialog state.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QInputDialog, QMessageBox, QPushButton

from gui_qt.dialogs import (
    DuplicateResolutionChoice,
    ask_duplicate_resolution,
    ask_input,
    ask_space_override,
    ask_yesno,
    show_error,
    show_info,
)
from gui_qt.dialogs.duplicate_resolution import _DuplicateResolutionDialog
from gui_qt.dialogs.space_override import _SpaceOverrideDialog


# ==========================================================================
# show_info / show_error
# ==========================================================================


def test_show_info_constructs_information_messagebox(qtbot, monkeypatch):
    """``show_info`` constructs a ``QMessageBox`` with Information
    icon, the right title, and the right message."""
    captured: dict = {}

    def fake_exec(self):
        captured["icon"] = self.icon()
        captured["title"] = self.windowTitle()
        captured["text"] = self.text()
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    show_info(None, "Heads up", "Disc 1 ripped successfully.")
    assert captured["icon"] == QMessageBox.Icon.Information
    assert captured["title"] == "Heads up"
    assert captured["text"] == "Disc 1 ripped successfully."


def test_show_error_constructs_critical_messagebox(qtbot, monkeypatch):
    """``show_error`` uses the Critical icon — visually distinct
    from info dialogs so users register the severity."""
    captured: dict = {}

    def fake_exec(self):
        captured["icon"] = self.icon()
        captured["title"] = self.windowTitle()
        captured["text"] = self.text()
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    show_error(None, "Rip Failed", "MakeMKV exited with code 2.")
    assert captured["icon"] == QMessageBox.Icon.Critical
    assert captured["title"] == "Rip Failed"
    assert captured["text"] == "MakeMKV exited with code 2."


def test_show_info_defaults_title_when_empty(qtbot, monkeypatch):
    """Empty title → "Info".  Defensive against callers passing ``""``."""
    captured: dict = {}

    def fake_exec(self):
        captured["title"] = self.windowTitle()
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    show_info(None, "", "body")
    assert captured["title"] == "Info"


def test_show_error_defaults_title_when_empty(qtbot, monkeypatch):
    """Empty title → "Error"."""
    captured: dict = {}

    def fake_exec(self):
        captured["title"] = self.windowTitle()
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    show_error(None, "", "body")
    assert captured["title"] == "Error"


# ==========================================================================
# ask_yesno
# ==========================================================================


def test_ask_yesno_returns_true_on_yes(qtbot, monkeypatch):
    """User clicks Yes → ``True``."""
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    assert ask_yesno(None, "Continue?") is True


def test_ask_yesno_returns_false_on_no(qtbot, monkeypatch):
    """User clicks No → ``False``."""
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.No,
    )
    assert ask_yesno(None, "Continue?") is False


def test_ask_yesno_passes_title(qtbot, monkeypatch):
    """Custom title propagates to the dialog."""
    captured: dict = {}

    def fake_question(parent, title, *args, **kwargs):
        captured["title"] = title
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", fake_question)
    ask_yesno(None, "Body text", title="Confirm Delete")
    assert captured["title"] == "Confirm Delete"


def test_ask_yesno_default_title_is_confirm(qtbot, monkeypatch):
    captured: dict = {}

    def fake_question(parent, title, *args, **kwargs):
        captured["title"] = title
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", fake_question)
    ask_yesno(None, "Body text")
    assert captured["title"] == "Confirm"


# ==========================================================================
# ask_input
# ==========================================================================


def test_ask_input_returns_text_on_ok(qtbot, monkeypatch):
    """User entered text and clicked OK → returns the text."""
    monkeypatch.setattr(
        QInputDialog, "getText",
        lambda *args, **kwargs: ("Breaking Bad S03", True),
    )
    result = ask_input(None, "Title", "Enter show name:")
    assert result == "Breaking Bad S03"


def test_ask_input_returns_none_on_cancel(qtbot, monkeypatch):
    """User clicked Cancel → ``None`` (distinct from empty string).
    The controller distinguishes these — pinned."""
    monkeypatch.setattr(
        QInputDialog, "getText",
        lambda *args, **kwargs: ("", False),
    )
    assert ask_input(None, "Title", "Enter show name:") is None


def test_ask_input_returns_empty_string_on_ok_with_empty_field(qtbot, monkeypatch):
    """User clicked OK with no text → returns ``""``, not ``None``."""
    monkeypatch.setattr(
        QInputDialog, "getText",
        lambda *args, **kwargs: ("", True),
    )
    assert ask_input(None, "Title", "Enter show name:") == ""


def test_ask_input_passes_default_text(qtbot, monkeypatch):
    """Pre-fill is forwarded to ``QInputDialog.getText``."""
    captured: dict = {}

    def fake(parent, label, prompt, *args, **kwargs):
        captured["label"] = label
        captured["prompt"] = prompt
        captured["default"] = kwargs.get("text", "")
        return ("ok-text", True)

    monkeypatch.setattr(QInputDialog, "getText", fake)
    ask_input(None, "WLABEL", "PROMPT", "DEFAULT")
    assert captured["label"] == "WLABEL"
    assert captured["prompt"] == "PROMPT"
    assert captured["default"] == "DEFAULT"


# ==========================================================================
# ask_space_override
# ==========================================================================


def test_space_override_dialog_chrome(qtbot):
    """Constructed dialog has the right title, objectName, default
    Cancel button."""
    d = _SpaceOverrideDialog(50.0, 12.5)
    qtbot.addWidget(d)
    assert d.windowTitle() == "Not Enough Space"
    assert d.objectName() == "spaceOverrideDialog"
    assert d.isModal()
    # Default = Cancel (proceed defaults to False)
    assert d.proceed is False
    # The cancel button is the keyboard default, not Proceed
    assert d._cancel_button.isDefault()
    assert not d._proceed_button.isDefault()


def test_space_override_body_shows_required_and_free_gb(qtbot):
    """Body label includes the required and free GB values formatted
    to one decimal place."""
    d = _SpaceOverrideDialog(123.45, 6.78)
    qtbot.addWidget(d)
    body_labels = [
        l for l in d.findChildren(type(d.findChild(object)))
        if hasattr(l, "text") and "Required:" in (getattr(l, "text", lambda: "")() or "")
    ]
    # Simpler: walk all QLabels.
    from PySide6.QtWidgets import QLabel
    body_text = "\n".join(
        l.text() for l in d.findChildren(QLabel)
    )
    assert "123.5 GB" in body_text  # required (rounded to 1 decimal)
    assert "6.8 GB" in body_text    # free


def test_space_override_proceed_button_sets_flag(qtbot):
    """Clicking Proceed Anyway → proceed=True and accept()."""
    d = _SpaceOverrideDialog(50.0, 12.5)
    qtbot.addWidget(d)
    d._proceed_button.click()
    assert d.proceed is True
    assert d.result() == 1  # QDialog.Accepted


def test_space_override_cancel_button_keeps_flag_false(qtbot):
    d = _SpaceOverrideDialog(50.0, 12.5)
    qtbot.addWidget(d)
    d._cancel_button.click()
    assert d.proceed is False
    assert d.result() == 0  # QDialog.Rejected


def test_space_override_escape_cancels(qtbot):
    d = _SpaceOverrideDialog(50.0, 12.5)
    qtbot.addWidget(d)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert d.proceed is False


def test_ask_space_override_returns_proceed_flag(qtbot, monkeypatch):
    """Public function: monkeypatch the dialog's exec and inject
    proceed=True; verify the function returns True."""
    def fake_exec(self):
        self.proceed = True
        return 1

    monkeypatch.setattr(_SpaceOverrideDialog, "exec", fake_exec)
    assert ask_space_override(None, 50.0, 12.5) is True


def test_ask_space_override_returns_false_on_cancel(qtbot, monkeypatch):
    def fake_exec(self):
        self.proceed = False
        return 0

    monkeypatch.setattr(_SpaceOverrideDialog, "exec", fake_exec)
    assert ask_space_override(None, 50.0, 12.5) is False


# ==========================================================================
# ask_duplicate_resolution
# ==========================================================================


def test_duplicate_resolution_dialog_chrome(qtbot):
    """Three buttons, retry is the keyboard default."""
    d = _DuplicateResolutionDialog(
        prompt="Looks like a duplicate disc.",
        retry_text="Swap and Retry",
        bypass_text="Not a Dup",
        stop_text="Stop",
    )
    qtbot.addWidget(d)
    assert d.windowTitle() == "Duplicate Disc Check"
    assert d.objectName() == "duplicateResolutionDialog"
    # Three buttons, retry is default
    assert d._retry_button.isDefault()
    assert not d._bypass_button.isDefault()
    assert not d._stop_button.isDefault()


def test_duplicate_resolution_default_choice_is_stop(qtbot):
    """Initial state is "stop" so Esc / window close maps to stop."""
    d = _DuplicateResolutionDialog(
        prompt="?", retry_text="A", bypass_text="B", stop_text="C",
    )
    qtbot.addWidget(d)
    assert d.choice == "stop"


def test_duplicate_resolution_buttons_set_choice(qtbot):
    d = _DuplicateResolutionDialog(
        prompt="?", retry_text="A", bypass_text="B", stop_text="C",
    )
    qtbot.addWidget(d)
    d._retry_button.click()
    assert d.choice == "retry"
    assert d.result() == 1  # accepted


def test_duplicate_resolution_bypass_button(qtbot):
    d = _DuplicateResolutionDialog(
        prompt="?", retry_text="A", bypass_text="B", stop_text="C",
    )
    qtbot.addWidget(d)
    d._bypass_button.click()
    assert d.choice == "bypass"
    assert d.result() == 1


def test_duplicate_resolution_stop_button(qtbot):
    d = _DuplicateResolutionDialog(
        prompt="?", retry_text="A", bypass_text="B", stop_text="C",
    )
    qtbot.addWidget(d)
    d._stop_button.click()
    assert d.choice == "stop"
    assert d.result() == 0  # rejected


def test_duplicate_resolution_escape_chooses_stop(qtbot):
    d = _DuplicateResolutionDialog(
        prompt="?", retry_text="A", bypass_text="B", stop_text="C",
    )
    qtbot.addWidget(d)
    event = QKeyEvent(
        QKeyEvent.Type.KeyPress,
        Qt.Key.Key_Escape,
        Qt.KeyboardModifier.NoModifier,
    )
    d.keyPressEvent(event)
    assert d.choice == "stop"


def test_duplicate_resolution_custom_button_labels(qtbot):
    """Custom labels appear on the buttons.  Pinned because the
    controller calls this with workflow-specific labels."""
    d = _DuplicateResolutionDialog(
        prompt="prompt body",
        retry_text="Swap, Then Continue",
        bypass_text="Force Anyway",
        stop_text="Abort Workflow",
    )
    qtbot.addWidget(d)
    assert d._retry_button.text() == "Swap, Then Continue"
    assert d._bypass_button.text() == "Force Anyway"
    assert d._stop_button.text() == "Abort Workflow"


def test_duplicate_resolution_prompt_text_word_wraps(qtbot):
    """Long prompt text doesn't crop — the prompt label has
    wordWrap on so multi-paragraph prompts render."""
    long_prompt = "a really long prompt " * 50
    d = _DuplicateResolutionDialog(
        prompt=long_prompt, retry_text="A", bypass_text="B", stop_text="C",
    )
    qtbot.addWidget(d)
    from PySide6.QtWidgets import QLabel
    prompt_labels = [
        l for l in d.findChildren(QLabel)
        if l.objectName() == "duplicatePrompt"
    ]
    assert len(prompt_labels) == 1
    assert prompt_labels[0].wordWrap()


def test_ask_duplicate_resolution_returns_user_choice(qtbot, monkeypatch):
    """Public function returns whichever choice the user made."""
    def fake_exec(self):
        self.choice = "bypass"
        return 1

    monkeypatch.setattr(_DuplicateResolutionDialog, "exec", fake_exec)
    result = ask_duplicate_resolution(None, "prompt body")
    assert result == "bypass"


def test_ask_duplicate_resolution_default_labels(qtbot, monkeypatch):
    """Without explicit text args, labels match the tkinter defaults."""
    captured: dict = {}

    real_init = _DuplicateResolutionDialog.__init__

    def fake_init(self, prompt, retry_text, bypass_text, stop_text, parent=None):
        captured["retry"] = retry_text
        captured["bypass"] = bypass_text
        captured["stop"] = stop_text
        real_init(self, prompt, retry_text, bypass_text, stop_text, parent)

    monkeypatch.setattr(_DuplicateResolutionDialog, "__init__", fake_init)
    monkeypatch.setattr(_DuplicateResolutionDialog, "exec", lambda self: 0)

    ask_duplicate_resolution(None, "prompt body")
    assert captured["retry"] == "Swap and Retry"
    assert captured["bypass"] == "Not a Dup"
    assert captured["stop"] == "Stop"
