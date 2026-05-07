"""Sub-phase 3b — Step 5 (``show_output_plan``) port tests.

Pins the PySide6 implementation of the wizard's output-plan review
step:

- Dialog shape (header, summary, tree view, destination, buttons)
- Theming hooks (every styled widget has the expected ``objectName``)
- Behavior (Confirm returns True; Cancel and Esc return False)
- Default button is Confirm so Enter triggers Start Rip
- ``build_output_tree`` re-exports correctly from ``gui_qt``
- The optional ``detail_lines`` argument renders a session-summary
  section when present and omits it when not
- Custom ``header_text`` / ``subtitle_text`` / ``confirm_text`` are
  honored (controllers customize these per workflow)

Per migration plan decision #4: sub-phase 3e adds the MKV preview
button into this dialog.  These tests pin the **structural** review
only and will need extending when 3e lands.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QTreeWidget

from gui_qt.setup_wizard import (
    _OutputPlanDialog,
    build_output_tree,
    show_output_plan,
)


# --------------------------------------------------------------------------
# build_output_tree (pure function — re-exported from gui.setup_wizard)
# --------------------------------------------------------------------------


def test_build_output_tree_renders_basic_movie():
    """Smoke test that the re-exported helper works and produces
    the expected shape."""
    lines = build_output_tree(
        base_folder="/library/Movies/Inception (2010)",
        main_label="Inception (2010).mkv",
        extras_map={"Behind The Scenes": ["Making Of.mkv"]},
    )
    text = "\n".join(lines)
    assert "Movies/" in text
    assert "Inception (2010)/" in text
    assert "Inception (2010).mkv" in text
    assert "Behind The Scenes/" in text
    assert "Making Of.mkv" in text


def test_build_output_tree_omits_empty_extras_categories():
    """Empty extras categories don't appear in the tree."""
    lines = build_output_tree(
        base_folder="/library/Movies/Inception (2010)",
        main_label="Inception (2010).mkv",
        extras_map={"Behind The Scenes": [], "Featurettes": ["x.mkv"]},
    )
    text = "\n".join(lines)
    assert "Behind The Scenes" not in text, (
        "categories with no files should be hidden"
    )
    assert "Featurettes" in text


# --------------------------------------------------------------------------
# Dialog shape + theming hooks
# --------------------------------------------------------------------------


def _make_dialog(qtbot, **overrides) -> _OutputPlanDialog:
    """Build a dialog with sensible defaults; tests override what
    they need."""
    defaults = dict(
        base_folder="/library/Movies/Test (2024)",
        main_label="Test (2024).mkv",
        extras_map={"Featurettes": ["Behind The Scenes.mkv"]},
        detail_lines=None,
        header_text="Step 5: Output Plan",
        subtitle_text=(
            "This is exactly what JellyRip will create. "
            "No guessing, no surprises."
        ),
        confirm_text="Start Rip",
        parent=None,
    )
    defaults.update(overrides)
    dialog = _OutputPlanDialog(**defaults)
    qtbot.addWidget(dialog)
    return dialog


def test_dialog_has_wizard_object_name(qtbot):
    """Same dialog chrome objectName as Step 1 — themes target one
    name for all wizard dialogs."""
    dialog = _make_dialog(qtbot)
    assert dialog.objectName() == "wizardDialog"
    assert dialog.windowTitle() == "Output Plan"
    assert dialog.isModal()


def test_dialog_renders_step_header_with_custom_text(qtbot):
    """The ``header_text`` argument lets controllers customize the
    step label per workflow (e.g., 'Step 3' for some flows).  Pins
    that the customization actually reaches the rendered label."""
    dialog = _make_dialog(qtbot, header_text="Step 3: Review Output Plan")
    headers = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == "stepHeader"
    ]
    assert len(headers) == 1
    assert "Step 3" in headers[0].text()


def test_dialog_renders_subtitle_and_confirm_text(qtbot):
    """Custom subtitle and confirm-button text propagate."""
    dialog = _make_dialog(
        qtbot,
        subtitle_text="Custom subtitle",
        confirm_text="Confirm Plan",
    )
    subtitles = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == "stepSubtitle"
    ]
    assert len(subtitles) == 1
    assert subtitles[0].text() == "Custom subtitle"

    confirm_btns = [
        b for b in dialog.findChildren(QPushButton)
        if b.objectName() == "confirmButton"
    ]
    assert len(confirm_btns) == 1
    assert confirm_btns[0].text() == "Confirm Plan"


def test_tree_view_is_a_tree_widget(qtbot):
    """The folder-structure tree is rendered as a real
    ``QTreeWidget`` (was a ``QPlainTextEdit`` placeholder
    pre-2026-05-04).  Pinned because the placeholder rendered
    a tree as plain text — easy to mistake for the new shape
    if a future refactor ever reverts."""
    dialog = _make_dialog(qtbot)
    tree_views = [
        w for w in dialog.findChildren(QTreeWidget)
        if w.objectName() == "outputTreeView"
    ]
    assert len(tree_views) == 1


def test_tree_view_items_not_editable(qtbot):
    """The tree is informational — items must not be user-editable.
    ``QTreeWidgetItem``'s default flags exclude
    ``ItemIsEditable``; pinned so a careless ``setFlags`` later
    can't make titles editable in the live dialog."""
    dialog = _make_dialog(qtbot)
    tree = next(
        w for w in dialog.findChildren(QTreeWidget)
        if w.objectName() == "outputTreeView"
    )
    # Walk the top-level items and at least the immediate children;
    # the tree is shallow (3 levels) so this is exhaustive.
    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        assert not (top.flags() & Qt.ItemFlag.ItemIsEditable)
        for j in range(top.childCount()):
            child = top.child(j)
            assert not (child.flags() & Qt.ItemFlag.ItemIsEditable)


def test_tree_view_renders_expected_hierarchy(qtbot):
    """Tree contains the expected three-level hierarchy:
    library-parent → movie folder → main file + extras subfolders.
    Pins the structural contract independent of how the items
    are styled."""
    dialog = _make_dialog(
        qtbot,
        base_folder="/library/Movies/Test (2024)",
        main_label="Test (2024).mkv",
        extras_map={"Featurettes": ["Behind The Scenes.mkv"]},
    )
    tree = next(
        w for w in dialog.findChildren(QTreeWidget)
        if w.objectName() == "outputTreeView"
    )
    # Top level: parent folder ("Movies/")
    assert tree.topLevelItemCount() == 1
    parent = tree.topLevelItem(0)
    assert parent.text(0) == "Movies/"

    # Mid level: movie folder
    assert parent.childCount() == 1
    folder = parent.child(0)
    assert folder.text(0) == "Test (2024)/"

    # Leaf level: main file + featurettes folder (one of each)
    leaf_texts = [folder.child(i).text(0) for i in range(folder.childCount())]
    assert "Test (2024).mkv" in leaf_texts
    assert "Featurettes/" in leaf_texts

    # Featurettes folder has the extra file
    featurettes = next(
        folder.child(i) for i in range(folder.childCount())
        if folder.child(i).text(0) == "Featurettes/"
    )
    assert featurettes.childCount() == 1
    assert featurettes.child(0).text(0) == "Behind The Scenes.mkv"


def test_tree_view_expanded_by_default(qtbot):
    """The dialog is informational — users want to see the full
    structure at a glance without expanding every node manually.
    Pins ``expandAll`` so a future change can't quietly collapse
    everything."""
    dialog = _make_dialog(
        qtbot,
        extras_map={"Featurettes": ["Reel.mkv"]},
    )
    tree = next(
        w for w in dialog.findChildren(QTreeWidget)
        if w.objectName() == "outputTreeView"
    )
    parent = tree.topLevelItem(0)
    assert parent.isExpanded()
    folder = parent.child(0)
    assert folder.isExpanded()


def test_tree_view_omits_empty_extras_categories(qtbot):
    """Empty categories from ``extras_map`` must not become tree
    nodes — same rule the flat-text builder enforces, pinned by
    ``test_build_output_tree_omits_empty_extras_categories``."""
    dialog = _make_dialog(
        qtbot,
        base_folder="/library/Movies/Test (2024)",
        main_label="Test (2024).mkv",
        extras_map={
            "Featurettes": ["Real.mkv"],
            "Behind The Scenes": [],  # empty — must be skipped
        },
    )
    tree = next(
        w for w in dialog.findChildren(QTreeWidget)
        if w.objectName() == "outputTreeView"
    )
    folder = tree.topLevelItem(0).child(0)
    leaf_texts = [folder.child(i).text(0) for i in range(folder.childCount())]
    assert "Featurettes/" in leaf_texts
    assert "Behind The Scenes/" not in leaf_texts


def test_destination_path_label_uses_objectName(qtbot):
    """Destination label has a stable objectName so QSS can style
    it (typically dim / smaller than body text)."""
    dialog = _make_dialog(
        qtbot, base_folder="/library/Movies/Test (2024)"
    )
    dest_labels = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == "destinationPath"
    ]
    assert len(dest_labels) == 1
    assert "/library/Movies/Test (2024)" in dest_labels[0].text()


# --------------------------------------------------------------------------
# Optional detail_lines section
# --------------------------------------------------------------------------


def test_no_detail_lines_means_no_summary_section(qtbot):
    """Without ``detail_lines``, no SESSION SUMMARY section
    renders.  Pins the conditional rendering."""
    dialog = _make_dialog(qtbot, detail_lines=None)
    detail_labels = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == "sessionDetailLine"
    ]
    assert detail_labels == []


def test_detail_lines_render_one_label_each(qtbot):
    """Every line in ``detail_lines`` renders as its own
    sessionDetailLine label."""
    lines = [
        "Title: Inception (2010)",
        "Metadata: TMDB 27205",
        "Replace existing: Yes",
    ]
    dialog = _make_dialog(qtbot, detail_lines=lines)
    detail_labels = [
        w for w in dialog.findChildren(QLabel)
        if w.objectName() == "sessionDetailLine"
    ]
    assert len(detail_labels) == 3
    rendered_texts = [w.text() for w in detail_labels]
    for line in lines:
        assert any(line in t for t in rendered_texts), (
            f"detail line {line!r} should appear in rendered labels; "
            f"got {rendered_texts}"
        )


# --------------------------------------------------------------------------
# Buttons + keyboard
# --------------------------------------------------------------------------


def test_confirm_button_returns_true(qtbot):
    """Clicking Start Rip sets ``result_value = True`` and accepts."""
    dialog = _make_dialog(qtbot)
    confirm_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if b.text() == "Start Rip"
    )
    qtbot.mouseClick(confirm_btn, Qt.MouseButton.LeftButton)
    assert dialog.result_value is True


def test_confirm_button_is_default(qtbot):
    """The confirm button is the default — Enter triggers it.  Pins
    the keyboard-friendly contract from the tkinter version's
    ``win.bind('<Return>', lambda _e: _confirm())``."""
    dialog = _make_dialog(qtbot)
    confirm_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if b.objectName() == "confirmButton"
    )
    assert confirm_btn.isDefault()


def test_cancel_button_returns_false(qtbot):
    """Cancel sets result_value to False and rejects the dialog."""
    dialog = _make_dialog(qtbot)
    cancel_btn = next(
        b for b in dialog.findChildren(QPushButton)
        if b.text() == "Cancel"
    )
    qtbot.mouseClick(cancel_btn, Qt.MouseButton.LeftButton)
    assert dialog.result_value is False


def test_escape_key_cancels(qtbot):
    """Esc cancels — matches tkinter's ``win.bind('<Escape>', ...)``"""
    dialog = _make_dialog(qtbot)
    dialog.show()
    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    assert dialog.result_value is False


# --------------------------------------------------------------------------
# Theming-hook drift guard + 3e reservation
# --------------------------------------------------------------------------


def test_every_button_has_object_name(qtbot):
    """Drift guard: every button needs an objectName so QSS can
    target it.  Catches refactors that lose theming hooks."""
    dialog = _make_dialog(
        qtbot,
        detail_lines=["one", "two"],
    )
    unnamed = [
        b for b in dialog.findChildren(QPushButton)
        if not b.objectName()
    ]
    assert unnamed == [], (
        f"every button needs an objectName for theming; missing on: "
        f"{[b.text() for b in unnamed]}"
    )


def test_no_preview_widget_yet(qtbot):
    """Per migration plan decision #4, the MKV preview button lives
    in this dialog but is added in sub-phase 3e, not 3b.  Pin
    'no preview yet' so a future contributor doesn't accidentally
    add it during 3b scope.

    When 3e ships, this test gets DELETED (replaced with positive
    pins for the preview button)."""
    dialog = _make_dialog(qtbot)
    preview_widgets = [
        w for w in dialog.findChildren(QPushButton)
        if "preview" in w.objectName().lower()
        or "preview" in w.text().lower()
    ]
    assert preview_widgets == [], (
        "MKV preview button should NOT exist yet — it's sub-phase 3e. "
        "If you're seeing this fail, you're either implementing 3e "
        "(in which case delete this test) or accidentally added "
        "preview UI to 3b (in which case revert)."
    )
