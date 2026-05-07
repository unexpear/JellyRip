"""Sub-phase 3b shell tests for ``gui_qt/setup_wizard.py``.

Pins that the public API surface exists and currently raises
``NotImplementedError`` with helpful messages — until each step
is individually ported in 3b's per-step sessions.

Why test the shell at all: makes sure
- the data class re-exports work (``from gui_qt.setup_wizard
  import ContentSelection`` etc.)
- the four step functions exist with the right signatures
- callers get a clear error pointing at the handoff brief, not
  a confusing AttributeError or a silent no-op
- when the actual ports land, these tests get rewritten — they're
  scaffolding pins, not behavior pins

Replace these tests with real per-step tests in 3b's sessions.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_data_classes_reexported_from_gui_qt():
    """The data classes (``ContentSelection``, ``ExtrasAssignment``,
    ``OutputPlan``) re-export from ``gui_qt.setup_wizard``.  Pins
    that callers can import either implementation interchangeably."""
    from gui_qt.setup_wizard import (
        ContentSelection,
        ExtrasAssignment,
        OutputPlan,
        JELLYFIN_EXTRAS_CATEGORIES,
    )
    # Sanity: the dataclasses are real and constructible.
    cs = ContentSelection(main_title_ids=[0, 1])
    assert cs.main_title_ids == [0, 1]
    ea = ExtrasAssignment(assignments={0: "Featurettes"})
    assert ea.assignments[0] == "Featurettes"
    op = OutputPlan(base_folder="/tmp", main_file_label="Movie")
    assert op.base_folder == "/tmp"
    # The Jellyfin categories list is identity-shared with the
    # tkinter module — same constant, same authority.
    assert "Featurettes" in JELLYFIN_EXTRAS_CATEGORIES
    assert "Behind The Scenes" in JELLYFIN_EXTRAS_CATEGORIES


def test_data_classes_are_same_object_as_shared_module():
    """``gui_qt/setup_wizard.py`` re-exports the dataclasses from
    ``shared/wizard_types.py`` — they should be the SAME objects, not
    copies, so controllers and tests can pass instances around without
    type confusion.

    Phase 3h (2026-05-04) — this used to compare ``gui_qt`` against
    ``gui.setup_wizard``; the tkinter side retired so the comparison
    moved to the new neutral home in ``shared/``.
    """
    import shared.wizard_types as shared_types
    import gui_qt.setup_wizard as qt_wizard
    assert qt_wizard.ContentSelection is shared_types.ContentSelection
    assert qt_wizard.ExtrasAssignment is shared_types.ExtrasAssignment
    assert qt_wizard.OutputPlan is shared_types.OutputPlan


# test_show_extras_classification_raises_not_implemented REMOVED
# 2026-05-04.  Step 4 was ported via ``_ExtrasClassificationDialog``
# during 3b's offline session; the shell stub no longer raises
# NotImplementedError.  Real behavior pinned in
# ``test_pyside6_setup_wizard_extras_classification.py`` (20 tests).
# This file is now purely "data classes + helpers re-export
# correctly" — every step has its own dedicated test file.


def test_helpers_reexported():
    """``_format_duration`` and ``_format_size`` are pure helpers —
    re-export so the Qt port can use them without depending on
    tkinter behavior."""
    from gui_qt.setup_wizard import _format_duration, _format_size
    assert _format_duration(3661) == "1h 01m"
    assert _format_size(2 * (1024 ** 3)) == "2.0 GB"
  