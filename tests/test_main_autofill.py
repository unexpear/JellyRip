import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # type: ignore[import-not-found]


def test_main_has_no_startup_autofill_helper():
    assert not hasattr(main, "_autofill_tool_paths")


def test_main_launches_gui_with_loaded_config(monkeypatch):
    cfg = {
        "makemkvcon_path": "",
        "ffprobe_path": "",
        "ffmpeg_path": "",
        "handbrake_path": "",
    }
    launched = {"config": None, "mainloop_called": False}

    class _FakeGUI:
        def __init__(self, config):
            launched["config"] = config

        def mainloop(self):
            launched["mainloop_called"] = True

    monkeypatch.setattr(main, "load_config", lambda: cfg)
    monkeypatch.setattr(main, "JellyRipperGUI", _FakeGUI)
    monkeypatch.setattr(main.sys, "platform", "linux")

    main.main()

    assert launched["config"] is cfg
    assert launched["mainloop_called"] is True
