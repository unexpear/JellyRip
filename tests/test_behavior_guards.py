"""High-value behavior guard tests for the ripping pipeline."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller.controller import RipperController
import controller.controller as controller_module
from controller.naming import build_fallback_title
from engine.ripper_engine import RipperEngine
from utils.scoring import choose_best_title


class DummyGUI:
    def __init__(self):
        self.messages = []

    def append_log(self, msg):
        self.messages.append(msg)


class ScriptedSetupGUI(DummyGUI):
    def __init__(self, scripted_inputs, scripted_confirms):
        super().__init__()
        self._inputs = iter(scripted_inputs)
        self._confirms = iter(scripted_confirms)

    def ask_input(self, _label, _prompt, default_value="", show_browse=False):
        return next(self._inputs)

    def ask_yesno(self, _prompt):
        return next(self._confirms)


def _engine_cfg(**overrides):
    cfg = {
        "makemkvcon_path": "makemkvcon",
        "ffprobe_path": "ffprobe",
        "opt_makemkv_global_args": "",
        "opt_makemkv_rip_args": "",
        "opt_drive_index": 0,
        "opt_auto_retry": True,
        "opt_retry_attempts": 3,
        "opt_clean_mkv_before_retry": True,
    }
    cfg.update(overrides)
    return cfg


def _controller_with_engine(cfg=None):
    engine = RipperEngine(cfg or _engine_cfg())
    gui = DummyGUI()
    return RipperController(engine, gui), engine


def test_controller_imports_make_rip_folder_name():
    assert callable(controller_module.make_rip_folder_name)


def test_unattended_setup_allows_editing_accidental_values():
    engine = RipperEngine(_engine_cfg())
    gui = ScriptedSetupGUI(
        scripted_inputs=[
            "2", "wrong title", "batch-a",   # first attempt (rejected)
            "3", "title1, title2", "batch-b",  # second attempt (accepted)
        ],
        scripted_confirms=[False, True],
    )
    controller = RipperController(engine, gui)

    total, per_disc_titles, batch_title = controller._collect_dump_all_multi_setup()

    assert total == 3
    assert per_disc_titles == ["title1", "title2"]
    assert batch_title == "batch-b"


def test_nonzero_exit_with_output_forces_failure_gate(tmp_path, monkeypatch):
    controller, engine = _controller_with_engine(
        _engine_cfg(opt_auto_retry=False, opt_retry_attempts=1)
    )

    def fake_run(_cmd, _on_progress, _on_log):
        Path(tmp_path, "bad.mkv").write_text("bad")
        return False

    monkeypatch.setattr(engine, "_run_rip_process", fake_run)
    monkeypatch.setattr(engine, "_quick_ffprobe_ok", lambda _f, _l: True)

    success, failed = engine.rip_selected_titles(
        str(tmp_path), [0], on_progress=lambda _p: None, on_log=controller.log
    )
    normalized_success, _files = controller._normalize_rip_result(
        str(tmp_path), success, failed
    )

    assert normalized_success is False
    assert any(
        "forcing failure regardless of output" in line
        for line in controller.gui.messages
    )


def test_partial_title_failure_forces_session_failure(tmp_path, monkeypatch):
    controller, engine = _controller_with_engine()
    Path(tmp_path, "file.mkv").write_text("ok")
    monkeypatch.setattr(engine, "_quick_ffprobe_ok", lambda _f, _l: True)

    normalized_success, _files = controller._normalize_rip_result(
        str(tmp_path), True, [1]
    )

    assert normalized_success is False


def test_zero_output_is_failure(tmp_path):
    controller, _engine = _controller_with_engine()

    normalized_success, files = controller._normalize_rip_result(
        str(tmp_path), True, []
    )

    assert normalized_success is False
    assert files == []


def test_abort_forces_failure_even_with_files(tmp_path, monkeypatch):
    controller, engine = _controller_with_engine()
    mkv = Path(tmp_path, "file.mkv")
    mkv.write_text("ok")

    monkeypatch.setattr(engine, "_quick_ffprobe_ok", lambda _f, _l: True)
    engine.abort()

    normalized_success, files = controller._normalize_rip_result(
        str(tmp_path), True, []
    )

    assert normalized_success is False
    assert files == [str(mkv)]


def test_mixed_quality_output_fails(tmp_path, monkeypatch):
    controller, engine = _controller_with_engine()
    good = Path(tmp_path, "good.mkv")
    bad = Path(tmp_path, "bad.mkv")
    good.write_text("good")
    bad.write_text("bad")

    monkeypatch.setattr(
        engine,
        "_quick_ffprobe_ok",
        lambda f, _l: Path(f).name == "good.mkv",
    )

    normalized_success, files = controller._normalize_rip_result(
        str(tmp_path), True, []
    )

    assert normalized_success is False
    assert len(files) == 2


def test_wipe_preserves_metadata(tmp_path):
    engine = RipperEngine(_engine_cfg())

    meta = Path(tmp_path, "_rip_meta.json")
    mkv = Path(tmp_path, "file.mkv")
    partial = Path(tmp_path, "file.partial")

    meta.write_text("{}")
    mkv.write_text("data")
    partial.write_text("data")

    engine.wipe_session_outputs(str(tmp_path), lambda _m: None)

    assert meta.exists()
    assert not mkv.exists()
    assert not partial.exists()


def test_purge_removes_existing_files(tmp_path):
    engine = RipperEngine(_engine_cfg())
    old = Path(tmp_path, "old.mkv")
    old.write_text("data")

    engine._purge_rip_target_files(str(tmp_path), lambda _m: None)

    assert not old.exists()


def test_timestamp_mode_uses_timestamp_fallback():
    name = build_fallback_title(
        {"opt_naming_mode": "timestamp"},
        make_temp_title_fn=lambda: "Disc_2026-03-27",
        clean_name_fn=lambda s: s,
        choose_best_title_fn=lambda _titles, require_valid=False: (None, 0.0),
        disc_titles=[],
    )
    assert name.startswith("Disc_")


def test_auto_name_fallback_when_no_titles():
    name = build_fallback_title(
        {"opt_naming_mode": "auto-title"},
        make_temp_title_fn=lambda: "Disc_2026-03-27",
        clean_name_fn=lambda s: s,
        choose_best_title_fn=lambda _titles, require_valid=False: (None, 0.0),
        disc_titles=[],
    )
    assert name.startswith("Disc_")


def test_auto_title_with_timestamp_mode():
    titles = [
        {
            "id": 0,
            "name": "Test Movie",
            "duration_seconds": 4000,
            "size_bytes": 2_000_000_000,
            "chapters": 20,
            "audio_tracks": [1, 2],
            "subtitle_tracks": [1],
        }
    ]

    name = build_fallback_title(
        {"opt_naming_mode": "auto-title+timestamp"},
        make_temp_title_fn=lambda: "Disc_2026-03-27",
        clean_name_fn=lambda s: s,
        choose_best_title_fn=choose_best_title,
        disc_titles=titles,
    )

    assert "Test Movie" in name
    assert name.startswith("Test Movie_")


def test_scoring_prefers_main_title():
    titles = [
        {
            "duration_seconds": 5000,
            "size_bytes": 4_000_000_000,
            "chapters": 20,
            "audio_tracks": [1, 2],
            "subtitle_tracks": [1],
        },
        {
            "duration_seconds": 300,
            "size_bytes": 200_000_000,
            "chapters": 1,
            "audio_tracks": [1],
            "subtitle_tracks": [],
        },
    ]

    best, _score = choose_best_title(titles)
    assert best["duration_seconds"] == 5000


def test_scoring_rejects_fake_size_tie():
    titles = [
        {
            "duration_seconds": 5000,
            "size_bytes": 4_000_000_000,
            "chapters": 20,
            "audio_tracks": [1, 2],
            "subtitle_tracks": [1],
        },
        {
            "duration_seconds": 5000,
            "size_bytes": 100_000_000,
            "chapters": 1,
            "audio_tracks": [1],
            "subtitle_tracks": [],
        },
    ]

    best, _score = choose_best_title(titles)
    assert best["size_bytes"] == 4_000_000_000


def test_retry_stops_on_success(tmp_path, monkeypatch):
    engine = RipperEngine(_engine_cfg(opt_retry_attempts=3, opt_auto_retry=True))
    outcomes = iter([False, True])
    calls = []

    def fake_run(_cmd, _on_progress, _on_log):
        calls.append("run")
        return next(outcomes)

    monkeypatch.setattr(engine, "_run_rip_process", fake_run)

    result = engine.rip_all_titles(
        str(tmp_path), on_progress=lambda _p: None, on_log=lambda _m: None
    )

    assert result is True
    assert len(calls) == 2


def test_retry_exhaustion(tmp_path, monkeypatch):
    engine = RipperEngine(_engine_cfg(opt_retry_attempts=3, opt_auto_retry=True))
    calls = []

    def fake_run(_cmd, _on_progress, _on_log):
        calls.append("run")
        return False

    monkeypatch.setattr(engine, "_run_rip_process", fake_run)

    result = engine.rip_all_titles(
        str(tmp_path), on_progress=lambda _p: None, on_log=lambda _m: None
    )

    assert result is False
    assert len(calls) == 3


def test_rip_all_titles_nonzero_exit_with_output_is_failure(tmp_path, monkeypatch):
    engine = RipperEngine(_engine_cfg(opt_auto_retry=False, opt_retry_attempts=1))
    logs = []

    def fake_run(_cmd, _on_progress, _on_log):
        Path(tmp_path, "partial.mkv").write_text("partial")
        return False

    monkeypatch.setattr(engine, "_run_rip_process", fake_run)

    result = engine.rip_all_titles(
        str(tmp_path), on_progress=lambda _p: None, on_log=logs.append
    )

    assert result is False
    assert any(
        "forcing failure regardless of output" in line
        for line in logs
    )


def test_abort_stops_rip(tmp_path):
    engine = RipperEngine(_engine_cfg())
    engine.abort()

    success, failed = engine.rip_selected_titles(
        str(tmp_path), [0], on_progress=lambda _p: None, on_log=lambda _m: None
    )

    assert success is False
    assert failed == []


def test_session_failure_triggers_wipe_and_metadata(tmp_path):
    controller, engine = _controller_with_engine()
    engine.write_temp_metadata(str(tmp_path), "Title", 1)

    mkv = Path(tmp_path, "output.mkv")
    mkv.write_text("data")

    controller._mark_session_failed(str(tmp_path), title="Title", media_type="movie")

    meta = engine.read_temp_metadata(str(tmp_path))
    assert not mkv.exists()
    assert meta is not None
    assert meta.get("status") == "failed"
    assert meta.get("phase") == "failed"
