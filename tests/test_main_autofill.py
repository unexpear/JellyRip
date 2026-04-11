import os
import sys

import pytest

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


def test_main_cleans_up_and_exits_130_on_console_interrupt(monkeypatch, capsys):
    cfg = {
        "makemkvcon_path": "",
        "ffprobe_path": "",
        "ffmpeg_path": "",
        "handbrake_path": "",
    }
    launched = {"aborted": False, "destroyed": False}

    class _FakeEngine:
        def abort(self):
            launched["aborted"] = True

    class _FakeGUI:
        engine = _FakeEngine()

        def __init__(self, config):
            launched["config"] = config

        def mainloop(self):
            raise KeyboardInterrupt

        def destroy(self):
            launched["destroyed"] = True

    monkeypatch.setattr(main, "load_config", lambda: cfg)
    monkeypatch.setattr(main, "JellyRipperGUI", _FakeGUI)
    monkeypatch.setattr(main.sys, "platform", "linux")

    with pytest.raises(SystemExit) as exc_info:
        main.main()

    assert exc_info.value.code == 130
    assert launched["config"] is cfg
    assert launched["aborted"] is True
    assert launched["destroyed"] is True
    assert "console interrupt" in capsys.readouterr().err
