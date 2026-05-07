"""Phase 3g — test surface audit pins.

Per migration plan decision #5 (behavior-first tests survive
unchanged; tkinter-touching tests get rewritten or deleted), Phase
3g confirms the test corpus is uniformly clean.

This file pins the audit findings from
``docs/handoffs/phase-3g-test-audit.md`` so a future change can't
silently introduce a new tkinter-coupled test.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


_REPO_ROOT = Path(__file__).resolve().parent.parent
_TESTS_DIR = _REPO_ROOT / "tests"


# The exhaustive list of tests that legitimately touch tkinter.
# Each entry is justified in
# ``docs/handoffs/phase-3g-test-audit.md`` and gets deleted (or
# its specific tkinter test gets removed) in Phase 3h alongside
# ``gui/``.
_LEGITIMATE_TKINTER_TOUCHING_TESTS: frozenset[str] = frozenset({
    # Imports the tkinter gui module via _FakeTkBase patch — pinned
    # because the tkinter side is still load-bearing until Phase 3h.
    "test_imports.py",
    # Source-text introspection of gui/setup_wizard.py.  Doesn't
    # actually construct tkinter widgets.
    "test_label_color_and_libredrive.py",
    # Tests pure helpers on JellyRipperGUI via _FakeTkBase patch +
    # object.__new__.  Qt path has a parallel
    # tests/test_pyside6_formatters.py covering equivalents.
    "test_main_window_formatters.py",
})


def _all_test_files() -> list[Path]:
    return sorted(p for p in _TESTS_DIR.glob("test_*.py"))


def _file_imports_tkinter(path: Path) -> bool:
    """Return True if the file genuinely couples to tkinter.

    Narrow detector — we only flag tests that:

    - Actually ``import tkinter`` (or ``from tkinter``) at the
      Python statement level.
    - Patch ``tkinter.Tk`` via ``unittest.mock.patch`` (the
      workaround for importing tkinter-touching modules without
      a live display).

    Tests that import from ``gui.theme`` or ``gui.update_ui`` etc.
    are *not* flagged — those modules are tkinter-package siblings
    that don't necessarily exercise widgets.  Per the brief, those
    are "behavior-first" and survive unchanged.
    """
    import re
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    # Real tkinter imports
    if re.search(r"^\s*(?:from\s+tkinter|import\s+tkinter)\b", text, re.MULTILINE):
        return True
    # The display-free workaround: patch tkinter.Tk
    if 'patch("tkinter.Tk"' in text or "patch('tkinter.Tk'" in text:
        return True
    return False


# ---------------------------------------------------------------------------
# Audit pins
# ---------------------------------------------------------------------------


def test_no_unexpected_tkinter_touching_tests():
    """Only the 3 audit-listed files may touch tkinter.  If a new
    test appears that does, it must be added to
    ``_LEGITIMATE_TKINTER_TOUCHING_TESTS`` with a docstring
    justification — or rewritten to not touch tkinter."""
    tkinter_touching: set[str] = set()
    for path in _all_test_files():
        # The audit file itself mentions tkinter in its docstring;
        # skip self-detection.
        if path.name == "test_phase_3g_audit.py":
            continue
        if _file_imports_tkinter(path):
            tkinter_touching.add(path.name)

    unexpected = tkinter_touching - _LEGITIMATE_TKINTER_TOUCHING_TESTS
    assert not unexpected, (
        f"Found unexpected tkinter-touching tests: {sorted(unexpected)}.\n"
        f"Either rewrite them under pytest-qt or, if they legitimately\n"
        f"need to test the tkinter path, add them to\n"
        f"``_LEGITIMATE_TKINTER_TOUCHING_TESTS`` in this file along with\n"
        f"a justification in docs/handoffs/phase-3g-test-audit.md."
    )


def test_legitimate_tkinter_files_still_present():
    """The 3 files we audited as legitimate should still exist —
    they retire in Phase 3h alongside ``gui/``.  If one of them
    disappeared early, update the audit doc."""
    for name in _LEGITIMATE_TKINTER_TOUCHING_TESTS:
        path = _TESTS_DIR / name
        assert path.is_file(), (
            f"Audit-listed file {name} no longer exists.  Update "
            f"_LEGITIMATE_TKINTER_TOUCHING_TESTS and "
            f"docs/handoffs/phase-3g-test-audit.md to reflect early "
            f"deletion."
        )


# ---------------------------------------------------------------------------
# pytest-qt convention pins
# ---------------------------------------------------------------------------


def test_all_pyside6_test_files_use_importorskip():
    """Every ``test_pyside6_*.py`` file should call
    ``pytest.importorskip("pytestqt")`` at module level so it
    skips cleanly on environments without pytest-qt installed.

    Pinned because any test file that imports PySide6 widgets
    directly without the importorskip will break collection on
    a stripped-down environment.
    """
    pyside_files = sorted(_TESTS_DIR.glob("test_pyside6_*.py"))
    assert pyside_files, "expected at least one test_pyside6_*.py file"

    missing: list[str] = []
    for path in pyside_files:
        text = path.read_text(encoding="utf-8")
        # Some pyside files might not need pytest-qt (pure helper
        # tests on themes / formatters).  Allow them if they don't
        # actually construct widgets.
        constructs_widgets = (
            "from PySide6.QtWidgets" in text
            or "from PySide6.QtMultimedia" in text
        )
        has_importorskip = 'importorskip("pytestqt")' in text
        if constructs_widgets and not has_importorskip:
            missing.append(path.name)

    assert not missing, (
        f"PySide6 widget tests missing ``pytest.importorskip("
        f"\"pytestqt\")`` at module level: {missing}.  Add it so "
        f"these files skip cleanly when pytest-qt isn't installed."
    )


def test_requirements_dev_lists_pytest_qt_and_pyside6():
    """``requirements-dev.txt`` is the canonical dev-deps file as
    of Phase 3g.  It should list pytest-qt and PySide6 explicitly."""
    reqs = _REPO_ROOT / "requirements-dev.txt"
    assert reqs.is_file(), "requirements-dev.txt must exist"
    text = reqs.read_text(encoding="utf-8")
    for required in ("pytest-qt", "PySide6", "pytest", "pyinstaller"):
        # Match against the package name (case-insensitive on the
        # package, since pip is case-insensitive).
        assert (
            required.lower() in text.lower()
        ), f"requirements-dev.txt missing {required!r}"
