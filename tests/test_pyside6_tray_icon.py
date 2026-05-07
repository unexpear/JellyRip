"""Phase 3 / 2026-05-04 — gui_qt.tray_icon tests.

Pins the public surface of ``JellyRipTray``:

- Construction succeeds with or without a real system tray
- ``is_available`` reflects ``QSystemTrayIcon.isSystemTrayAvailable``
- All public methods are no-ops when no tray is available — tests
  on headless CI runners must not raise just because the platform
  has no notification surface
- Tooltip formatter combines status text with optional progress

We deliberately don't try to assert on the tray's actual rendered
state — that's OS- and shell-dependent (Windows vs. KDE vs. macOS
"Item-1" vs. an EC2 instance with no tray at all).  The wiring
contract is what these tests pin; visual behavior is covered by
manual smoke.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QSystemTrayIcon, QWidget

from gui_qt.tray_icon import JellyRipTray


def test_tray_construction_does_not_raise(qtbot):
    """Tray must construct cleanly even on systems without a tray
    surface (CI runners, stripped VMs)."""
    win = QWidget()
    qtbot.addWidget(win)
    tray = JellyRipTray(win, app_name="JellyRip")
    # Attribute exists either way.
    assert isinstance(tray.is_available, bool)


def test_tray_unavailable_path_is_a_no_op(qtbot, monkeypatch):
    """When ``isSystemTrayAvailable`` returns False, every public
    method must be a no-op — no AttributeError, no None-deref.
    Pinned because the call sites in MainWindow don't guard."""
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False),
    )
    win = QWidget()
    qtbot.addWidget(win)
    tray = JellyRipTray(win)

    assert tray.is_available is False
    # All of these must just return without raising.
    tray.update_tooltip("Scanning...")
    tray.update_tooltip("Ripping...", progress_pct=42)
    tray.notify_complete()
    tray.notify_complete(title="Custom", body="Body")
    tray.notify_failure()
    tray.notify_failure(title="Err", body="Reason")
    tray.hide()


def test_tooltip_with_progress_pct(qtbot, monkeypatch):
    """When progress is given, the tooltip combines status + percent.
    We verify on the available-tray path so we can read the result
    back from the underlying QSystemTrayIcon."""
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True),
    )
    win = QWidget()
    qtbot.addWidget(win)
    tray = JellyRipTray(win, app_name="JellyRip")
    if not tray.is_available or tray._tray is None:
        pytest.skip("system tray not actually available on this runner")

    tray.update_tooltip("Ripping...", progress_pct=42)
    text = tray._tray.toolTip()
    assert "JellyRip" in text
    assert "Ripping..." in text
    assert "42%" in text


def test_tooltip_truncates_overlong_text(qtbot, monkeypatch):
    """Windows truncates tooltips after ~127 chars.  Pre-truncate
    so long status messages don't get cut off mid-word."""
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True),
    )
    win = QWidget()
    qtbot.addWidget(win)
    tray = JellyRipTray(win, app_name="JellyRip")
    if not tray.is_available or tray._tray is None:
        pytest.skip("system tray not actually available on this runner")

    long_status = "x" * 200
    tray.update_tooltip(long_status)
    assert len(tray._tray.toolTip()) <= 120


def test_progress_pct_out_of_range_is_ignored(qtbot, monkeypatch):
    """Defensive: a controller passing -1 / 200 shouldn't end up in
    the tooltip — fall back to status-only."""
    monkeypatch.setattr(
        QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True),
    )
    win = QWidget()
    qtbot.addWidget(win)
    tray = JellyRipTray(win, app_name="JellyRip")
    if not tray.is_available or tray._tray is None:
        pytest.skip("system tray not actually available on this runner")

    tray.update_tooltip("Ripping...", progress_pct=-5)
    assert "%" not in tray._tray.toolTip()
    tray.update_tooltip("Ripping...", progress_pct=250)
    assert "%" not in tray._tray.toolTip()
