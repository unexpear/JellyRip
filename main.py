"""Main entrypoint for the split package layout."""

import os
import sys
from pathlib import Path

from config import (
    auto_locate_tools,
    load_config,
    save_config,
    validate_ffprobe,
    validate_makemkvcon,
)

def _bootstrap_tk_paths():
    """Set Tcl/Tk library paths when Python's auto-discovery is broken."""
    if sys.platform != "win32":
        return
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    candidate_roots = []
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        candidate_roots.append(meipass)
        candidate_roots.append(meipass / "tcl")

    base_prefix = Path(getattr(sys, "base_prefix", sys.prefix))
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


def _autofill_tool_paths(cfg):
    """Auto-populate missing/invalid tool paths without overwriting working ones."""
    found_mkv, found_ffp = auto_locate_tools()
    updates = {
        "makemkvcon_path": (found_mkv, validate_makemkvcon),
        "ffprobe_path": (found_ffp, validate_ffprobe),
    }

    changed = False
    for key, (found, validator) in updates.items():
        current = str(cfg.get(key, "") or "").strip()
        current_ok = False
        if current:
            current_ok, _ = validator(current)
        if current_ok:
            continue
        if not found:
            continue
        candidate = str(found).strip()
        candidate_ok, _ = validator(candidate)
        if candidate_ok and candidate != current:
            cfg[key] = candidate
            changed = True

    if changed:
        save_config(cfg)


def main():
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "JellyRip.App.1"
            )
        except Exception as e:
            import logging
            logging.warning("SetCurrentProcessExplicitAppUserModelID failed: %s", e)

    cfg = load_config()
    try:
        _autofill_tool_paths(cfg)
    except Exception as e:
        import logging
        logging.warning("_autofill_tool_paths failed: %s", e)
    app = JellyRipperGUI(cfg)
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
