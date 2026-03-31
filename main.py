"""Main entrypoint for the split package layout."""

import sys

from config import load_config
from gui.main_window import JellyRipperGUI


def main():
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "JellyRip.App.1"
            )
        except Exception:
            pass

    cfg = load_config()
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
