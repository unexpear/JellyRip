import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # type: ignore[import-not-found]


def test_autofill_updates_invalid_paths(monkeypatch):
    cfg = {
        "makemkvcon_path": "",
        "ffprobe_path": "",
    }
    saved = {"called": False}

    monkeypatch.setattr(main, "auto_locate_tools", lambda: ("mkv.exe", "ffp.exe"))
    monkeypatch.setattr(main, "validate_makemkvcon", lambda p: (p == "mkv.exe", "bad"))
    monkeypatch.setattr(main, "validate_ffprobe", lambda p: (p == "ffp.exe", "bad"))
    monkeypatch.setattr(main, "save_config", lambda _cfg: saved.__setitem__("called", True))

    main._autofill_tool_paths(cfg)

    assert cfg["makemkvcon_path"] == "mkv.exe"
    assert cfg["ffprobe_path"] == "ffp.exe"
    assert saved["called"] is True


def test_autofill_keeps_working_paths(monkeypatch):
    cfg = {
        "makemkvcon_path": "current-mkv.exe",
        "ffprobe_path": "current-ffp.exe",
    }
    saved = {"called": False}

    monkeypatch.setattr(main, "auto_locate_tools", lambda: ("new-mkv.exe", "new-ffp.exe"))
    monkeypatch.setattr(main, "validate_makemkvcon", lambda p: (p == "current-mkv.exe", "bad"))
    monkeypatch.setattr(main, "validate_ffprobe", lambda p: (p == "current-ffp.exe", "bad"))
    monkeypatch.setattr(main, "save_config", lambda _cfg: saved.__setitem__("called", True))

    main._autofill_tool_paths(cfg)

    assert cfg["makemkvcon_path"] == "current-mkv.exe"
    assert cfg["ffprobe_path"] == "current-ffp.exe"
    assert saved["called"] is False
