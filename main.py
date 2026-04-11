"""Main entrypoint for the split package layout."""

import os
import sys
from pathlib import Path

from config import load_config


def _bootstrap_tk_paths() -> None:
    """Set Tcl/Tk library paths when Python's auto-discovery is broken."""
    if sys.platform != "win32":
        return
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    candidate_roots: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = Path(str(getattr(sys, "_MEIPASS", "")))
        candidate_roots.append(meipass)
        candidate_roots.append(meipass / "tcl")

    base_prefix = Path(str(getattr(sys, "base_prefix", sys.prefix)))
    candidate_roots.append(base_prefix / "tcl")

    for root in candidate_roots:
        if root.name == "tcl":
            tcl_dir = root / "tcl8.6"
            tk_dir = root / "tk8.6"
        else:
            tcl_dir = root / "_tcl_data"
            tk_dir = root / "_tk_data"
        if (tcl_dir / "init.tcl").is_file() and tk_dir.is_dir():
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
            os.environ.setdefault("TK_LIBRARY", str(tk_dir))
            return

        tcl_dir = root / "tcl8.6"
        tk_dir = root / "tk8.6"
        if (tcl_dir / "init.tcl").is_file() and tk_dir.is_dir():
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
            os.environ.setdefault("TK_LIBRARY", str(tk_dir))
            return


_bootstrap_tk_paths()

from gui.main_window import JellyRipperGUI


def _set_windows_app_user_model_id() -> None:
    if sys.platform != "win32":
        return

    import ctypes
    import logging

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "JellyRip.App.1"
        )
    except Exception as e:
        logging.warning("SetCurrentProcessExplicitAppUserModelID failed: %s", e)


def _shutdown_after_interrupt(app: JellyRipperGUI) -> None:
    """Best-effort cleanup after a console interrupt in source/dev runs."""
    try:
        app.engine.abort()
    except Exception:
        pass
    try:
        app.destroy()
    except Exception:
        pass


def main() -> None:
    _set_windows_app_user_model_id()

    config = load_config()
    # No autofill or mutation allowed
    app = JellyRipperGUI(config)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        _shutdown_after_interrupt(app)
        print(
            "JellyRip received a console interrupt (Ctrl+C/terminal stop) "
            "and shut down.",
            file=sys.stderr,
        )
        raise SystemExit(130)
    except Exception as e:
        import traceback

        print(f"[ERROR] JellyRip GUI crashed: {e}", file=sys.stderr)
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()


# -----------------------------------------------------------------------------
# Project file map (quick navigation when chat history is unavailable)
# -----------------------------------------------------------------------------
# Main GUI entrypoint: gui/main_window.py
# Workflow/controller logic: controller/controller.py
# Disc + file operations engine: engine/ripper_engine.py
# Config load/save and defaults bridge: config.py
# Shared defaults/runtime primitives: shared/runtime.py
# Utility exports: utils/__init__.py
# Session state machine: utils/state_machine.py
# Fallback policy gateway: utils/fallback.py
# File selection helpers: utils/media.py
# Behavioral tests: tests/test_behavior_guards.py
