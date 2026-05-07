# Patch — `main.py`

Drop the `opt_use_pyside6` feature-flag branch.  Qt becomes the
unconditional code path.

## Find (around line 199-212)

```python
        # PySide6 migration scaffolding (Phase 3a) — feature-flagged
        # path.  When opt_use_pyside6 is True, take the Qt path.
        # Default is False so the existing tkinter UI is unchanged.
        # See docs/migration-roadmap.md.
        if startup.config.get("opt_use_pyside6", False):
            startup_window.set_status("Loading PySide6 interface...")
            from gui_qt.app import run_qt_app
            startup_window.close()
            startup_window = _NullStartupWindow()
            raise SystemExit(run_qt_app(startup.config))

        startup_window.set_status("Loading interface...")
        gui_class = _resolve_gui_class()
        startup_window.set_status("Opening app...")
        startup_window.close()
        startup_window = _NullStartupWindow()
        app = gui_class(
            startup.config,
            startup_context={
                "issues": [issue.message for issue in startup.issues],
                "open_settings": startup.open_settings,
            },
        )
```

## Replace with

```python
        startup_window.set_status("Loading PySide6 interface...")
        from gui_qt.app import run_qt_app
        startup_window.close()
        startup_window = _NullStartupWindow()
        raise SystemExit(run_qt_app(startup.config))
```

## Also drop (top of file)

The startup splash that imports `tkinter` to render the
"Loading…" window can be simplified or removed entirely.
Specifically:

* The `try: import tkinter as tk` block (~line 25-30) and the
  `_StartupWindow`/`_NullStartupWindow` machinery exist only to
  cover the brief moment before either UI starts.  Easiest path:
  delete `_StartupWindow` (the tkinter-based one) and keep
  `_NullStartupWindow` as the single startup-window
  implementation.  Or replace with a tiny `QSplashScreen` if you
  want the visible feedback during PySide6 startup.

## Also drop

* `_resolve_gui_class()` and any helpers that import from `gui/`.
  Search the file for `from gui` / `import gui` and clean up.

## Verification

* `python main.py` should launch the Qt app directly.
* `grep -rn "_resolve_gui_class\|opt_use_pyside6" .` → expect zero
  hits in code (CHANGELOG / docs OK).
