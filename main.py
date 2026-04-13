"""Main entrypoint for the split package layout."""

import os
import sys
from pathlib import Path


def _load_env_file() -> None:
    """Load .env file from app directory if present (for API keys etc.)."""
    env_path = Path(__file__).parent / ".env"
    if not env_path.is_file():
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env_file()

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
    app.mainloop()


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
