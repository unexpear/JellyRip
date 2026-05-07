"""Phase 3c-iii — controller-facing method audit pins.

After the cleanup-sweep audit, the following methods were added to
MainWindow to close gaps with what the controller calls.  This file
pins their presence and rough delegation behavior.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from gui_qt.main_window import MainWindow


# ---------------------------------------------------------------------------
# Wizard step wrappers — wired in 3c-iii cleanup sweep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,wizard_func", [
    ("show_scan_results_step",          "show_scan_results"),
    ("show_content_mapping_step",       "show_content_mapping"),
    ("show_extras_classification_step", "show_extras_classification"),
    ("show_output_plan_step",           "show_output_plan"),
])
def test_wizard_step_wrappers_delegate_to_setup_wizard(
    qtbot, monkeypatch, method, wizard_func,
):
    """Each ``show_*_step`` method delegates to the matching
    ``gui_qt.setup_wizard.show_*`` function.  Pinned because the
    controller is structured around these step calls.

    Implementation note: the wrapper does a lazy import of
    ``gui_qt.setup_wizard`` inside the method body so MainWindow's
    own import chain stays tkinter-free.  In the test sandbox we
    pre-install a stand-in module in ``sys.modules`` so the lazy
    import resolves to our stub instead of pulling the real wizard
    (which transitively imports ``gui/__init__.py`` and tkinter)."""
    import sys
    import types

    fake_module = types.ModuleType("gui_qt.setup_wizard")
    captured: dict = {}

    def fake(*args, **kwargs):
        captured["called"] = True
        captured["wizard_func"] = wizard_func
        return f"RESULT_{wizard_func}"

    setattr(fake_module, wizard_func, fake)
    monkeypatch.setitem(sys.modules, "gui_qt.setup_wizard", fake_module)

    mw = MainWindow()
    qtbot.addWidget(mw)

    if method == "show_scan_results_step":
        result = mw.show_scan_results_step(classified=[], drive_info=None)
    elif method == "show_content_mapping_step":
        result = mw.show_content_mapping_step(classified=[])
    elif method == "show_extras_classification_step":
        result = mw.show_extras_classification_step(extra_titles=[])
    elif method == "show_output_plan_step":
        result = mw.show_output_plan_step(
            base_folder="/x", main_label="Y", extras_map={},
        )

    assert captured.get("called"), f"{method} did not delegate"
    assert result == f"RESULT_{wizard_func}"


# ---------------------------------------------------------------------------
# ask_directory — folder picker
# ---------------------------------------------------------------------------


def test_ask_directory_returns_chosen_path(qtbot, monkeypatch):
    """``ask_directory`` opens a QFileDialog folder picker and
    returns the chosen path."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *args, **kwargs: "/the/chosen/folder",
    )
    mw = MainWindow()
    qtbot.addWidget(mw)
    result = mw.ask_directory("Title", "Pick a folder")
    assert result == "/the/chosen/folder"


def test_ask_directory_returns_none_on_cancel(qtbot, monkeypatch):
    """Cancelled picker → None (matches tkinter contract)."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        lambda *args, **kwargs: "",
    )
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert mw.ask_directory("Title", "Pick") is None


def test_ask_directory_uses_initialdir(qtbot, monkeypatch):
    """The initialdir argument is forwarded to QFileDialog so the
    picker opens at the right starting location."""
    from PySide6.QtWidgets import QFileDialog

    captured: dict = {}

    def fake(parent, title, start, *args, **kwargs):
        captured["start"] = start
        return ""

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", fake)
    mw = MainWindow()
    qtbot.addWidget(mw)
    mw.ask_directory("Title", "Pick", initialdir="/desired/start")
    assert captured["start"] == "/desired/start"


# ---------------------------------------------------------------------------
# Still-stubbed pickers — pinned so future sessions see the gap
# ---------------------------------------------------------------------------


def test_show_extras_picker_now_wired(qtbot, monkeypatch):
    """``show_extras_picker`` no longer raises NotImplementedError —
    delegation pinned in test_pyside6_dialogs_list_picker.py.  This
    is just a regression guard: the method exists and is callable."""
    import gui_qt.main_window as mw_module
    monkeypatch.setattr(mw_module, "_show_extras_picker", lambda *a, **k: [0])
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert mw.show_extras_picker("T", "P", ["a", "b"]) == [0]


def test_show_file_list_now_wired(qtbot, monkeypatch):
    """``show_file_list`` no longer raises NotImplementedError."""
    import gui_qt.main_window as mw_module
    monkeypatch.setattr(mw_module, "_show_file_list", lambda *a, **k: ["a"])
    mw = MainWindow()
    qtbot.addWidget(mw)
    assert mw.show_file_list("T", "P", ["a", "b"]) == ["a"]
