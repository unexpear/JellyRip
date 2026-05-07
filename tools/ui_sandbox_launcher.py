"""RETIRED in Phase 3h (2026-05-04).

This was the tkinter UI sandbox launcher — it built a fake config
and constructed ``JellyRipperGUI`` (the tkinter main window) so a
developer could exercise UI flows without MakeMKV / ffprobe / disc
hardware. After tkinter retirement, both the launcher and its target
no longer exist.

The Qt-side UI is exercised by ``tests/test_pyside6_*.py`` running
under pytest-qt, which covers the same flow-validation surface
without needing a manual launcher. If you want to drive the real Qt
UI manually, run::

    python main.py

with whatever ``%APPDATA%/JellyRip/config.json`` you have.

A Qt-equivalent sandbox (``tools/ui_qt_sandbox_launcher.py``) can
be built later if a manual exercise harness becomes useful — see
``docs/handoffs/phase-3h-tkinter-retirement.md`` Step 3c. For now
it's deferred as overlap with pytest-qt.
"""

raise SystemExit(
    "ui_sandbox_launcher.py was retired in Phase 3h (2026-05-04). "
    "Run `python main.py` for the live Qt UI, or rely on the pytest-qt "
    "test suite under tests/test_pyside6_*.py for flow validation."
)
