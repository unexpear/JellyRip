"""Phase 3 / 2026-05-04 — gui_qt.splash tests.

Pins the API surface of the startup splash:

- ``_build_pixmap`` returns a non-null pixmap of the expected size
- ``JellyRipSplash`` constructs without raising
- ``set_status`` / ``close`` / ``finish_for`` don't blow up
- ``finish_for(None)`` is a safe path — falls back to ``close``

The splash is pure UX nicety: ``main.py`` falls back to
``_NullStartupWindow`` if construction raises, so we don't need to
test "what happens on a broken Qt".  We DO need to test that the
happy paths work and that ``finish_for(None)`` doesn't crash —
that's the controller-bailed-early defensive case.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QWidget

from gui_qt.splash import (
    JellyRipSplash,
    _SPLASH_HEIGHT,
    _SPLASH_WIDTH,
    _build_pixmap,
)


def test_build_pixmap_has_expected_size(qtbot):
    pm = _build_pixmap()
    assert not pm.isNull()
    assert pm.width() == _SPLASH_WIDTH
    assert pm.height() == _SPLASH_HEIGHT


def test_build_pixmap_with_version_does_not_raise(qtbot):
    """Version string is rendered into the bottom-left corner —
    must not crash even with a long / weird version string."""
    pm = _build_pixmap(version="1.0.21-rc.2")
    assert not pm.isNull()


def test_splash_construction_and_close(qtbot):
    """Happy path — construct splash, close it, no exceptions."""
    splash = JellyRipSplash()
    splash.close()


def test_splash_set_status_does_not_raise(qtbot):
    splash = JellyRipSplash()
    try:
        splash.set_status("Loading settings...")
        splash.set_status("Loading interface...")
    finally:
        splash.close()


def test_splash_finish_for_window(qtbot):
    """``finish_for(window)`` is the Qt-native handoff — must not
    raise when given a real ``QWidget``."""
    splash = JellyRipSplash()
    try:
        win = QWidget()
        qtbot.addWidget(win)
        win.show()
        splash.finish_for(win)
    finally:
        win.close()


def test_splash_finish_for_none_falls_back_to_close(qtbot):
    """Defensive: ``main.py``'s flow could in theory hand
    ``finish_for(None)`` if the controller bails before MainWindow
    exists.  The splash must close cleanly without crashing."""
    splash = JellyRipSplash()
    splash.finish_for(None)
    # Calling close again must also be safe (idempotent).
    splash.close()


def test_close_is_idempotent(qtbot):
    """Two close() calls in sequence — the second one is a no-op,
    not a crash.  Pinned because main.py's ``finally:`` calls
    close() after run_qt_app already did it via finish_for."""
    splash = JellyRipSplash()
    splash.close()
    splash.close()
