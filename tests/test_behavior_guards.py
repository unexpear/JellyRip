"""High-value behavior guard tests for the ripping pipeline."""

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controller.controller import RipperController
import controller.controller as controller_module
from controller.naming import build_fallback_title
from engine.ripper_engine import RipperEngine
from utils.fallback import handle_fallback
from utils.media import select_largest_file
from utils.session_result import normalize_session_result
from utils.state_machine import SessionState, SessionStateMachine
from utils.scoring import choose_best_title


class DummyGUI:
    def __init__(self):
        self.messages = []

    def append_log(self, msg):
        self.messages.append(msg)

    def set_status(self, _status):
        pass


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


def test_normalize_session_result_abort_is_failure():
    assert normalize_session_result(
        abort=True,
        failed_titles=[],
        files=["a.mkv"],
        valid_files=["a.mkv"],
    ) is False


def test_normalize_session_result_failed_titles_is_failure():
    assert normalize_session_result(
        abort=False,
        failed_titles=[1],
        files=["a.mkv"],
        valid_files=["a.mkv"],
    ) is False


def test_normalize_session_result_mixed_validity_is_failure():
    assert normalize_session_result(
        abort=False,
        failed_titles=[],
        files=["a.mkv", "b.mkv"],
        valid_files=["a.mkv"],
    ) is False


def test_normalize_session_result_no_files_is_failure():
    assert normalize_session_result(
        abort=False,
        failed_titles=[],
        files=[],
        valid_files=[],
    ) is False


def test_normalize_session_result_full_success_passes():
    assert normalize_session_result(
        abort=False,
        failed_titles=[],
        files=["a.mkv", "b.mkv"],
        valid_files=["a.mkv", "b.mkv"],
    ) is True


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


def test_move_files_movie_with_extras_uses_clean_name_without_name_error(
    tmp_path, monkeypatch
):
    engine = RipperEngine(_engine_cfg(opt_check_dest_space=False))
    monkeypatch.setattr(engine, "_quick_ffprobe_ok", lambda _f, _l: True)

    src_main = Path(tmp_path, "01_sn11-D1.mkv")
    src_extra = Path(tmp_path, "02_sn13-F1.mkv")
    src_main.write_text("main")
    src_extra.write_text("extra")

    dest_folder = Path(tmp_path, "Movies", "Pitch Perfect 2 (2015)")
    extras_folder = dest_folder / "Extras"
    dest_folder.mkdir(parents=True, exist_ok=True)
    extras_folder.mkdir(parents=True, exist_ok=True)

    ok, next_extra_counter, moved_paths = engine.move_files(
        titles_list=[
            (str(src_main), 0, 0),
            (str(src_extra), 0, 0),
        ],
        main_indices=[0],
        episode_numbers=[],
        real_names=[],
        keep_extras=True,
        is_tv=False,
        title="Pitch Perfect 2",
        dest_folder=str(dest_folder),
        extras_folder=str(extras_folder),
        season=1,
        year="2015",
        extra_counter=1,
        on_progress=lambda _p: None,
        on_log=lambda _m: None,
    )

    assert ok is True
    assert next_extra_counter == 2
    assert len(moved_paths) == 2
    assert src_main.exists() is False
    assert src_extra.exists() is False


class TestComputeFileMinSize:
    """_compute_file_min_size: trusted expected vs. fallback floor."""

    _1_GB = 1 * 1024 ** 3
    _100_MB = 100 * 1024 * 1024
    _500_MB = 500 * 1024 * 1024

    def _min(self, expected, floor=_1_GB):
        return RipperController._compute_file_min_size(expected, floor)

    def test_credible_expected_overrides_1gb_floor(self):
        # 500 MB extra must NOT be forced to pass a 1 GB floor.
        result = self._min(self._500_MB)
        assert result < self._1_GB

    def test_credible_expected_is_half_of_expected(self):
        result = self._min(self._500_MB)
        assert result == self._500_MB // 2

    def test_zero_expected_falls_back_to_floor(self):
        assert self._min(0) == self._1_GB

    def test_garbage_small_expected_falls_back_to_floor(self):
        # 5 MB "expected" is a bad parse — must not be trusted.
        assert self._min(5 * 1024 * 1024) == self._1_GB

    def test_exactly_100mb_boundary_uses_floor(self):
        # Boundary value: exactly 100 MB is NOT > 100 MB, so falls back.
        assert self._min(self._100_MB) == self._1_GB

    def test_just_above_100mb_boundary_trusts_expected(self):
        just_above = self._100_MB + 1
        assert self._min(just_above) == just_above // 2

    def test_large_main_feature_trusts_expected(self):
        _7_GB = 7 * 1024 ** 3
        result = self._min(_7_GB)
        assert result == _7_GB // 2

    def test_inflated_expected_never_exceeds_expected(self):
        # Inflated playlist size: threshold must not exceed expected itself.
        _20_GB = 20 * 1024 ** 3
        result = self._min(_20_GB)
        assert result <= _20_GB


def test_map_title_ids_prefers_engine_tracked_file_map(tmp_path):
    controller, engine = _controller_with_engine()

    f_main = Path(tmp_path, "A.mkv")
    f_extra = Path(tmp_path, "B.mkv")
    f_main.write_text("m")
    f_extra.write_text("e")

    engine.last_title_file_map = {
        2: [str(f_main)],
        3: [str(f_extra)],
    }

    titles_list = [
        (str(f_extra), 0, 0),
        (str(f_main), 0, 0),
    ]
    mapped = controller._map_title_ids_to_analyzed_indices(titles_list, [2])
    assert mapped == [1]


def test_build_disc_fingerprint_uses_titles_beyond_top12(monkeypatch):
    controller, _engine = _controller_with_engine()

    base = [
        {
            "id": i,
            "duration_seconds": 10000 - i,
            "size_bytes": (10000 - i) * 1024,
            "chapters": 1,
            "audio_tracks": [1],
            "subtitle_tracks": [1],
        }
        for i in range(13)
    ]
    changed = [dict(t) for t in base]
    # Change only the 13th title signature; old top-12-only logic would collide.
    changed[12]["size_bytes"] += 123456

    monkeypatch.setattr(controller, "scan_with_retry", lambda: base)
    fp1 = controller._build_disc_fingerprint()
    monkeypatch.setattr(controller, "scan_with_retry", lambda: changed)
    fp2 = controller._build_disc_fingerprint()

    assert fp1 != fp2


def test_duplicate_resolution_prefers_custom_title_override_yes(monkeypatch):
    controller, _engine = _controller_with_engine()

    monkeypatch.setattr(
        controller.gui, "ask_yesno", lambda _p: True, raising=False
    )
    called = {"value": False}

    def _should_not_call(*_args, **_kwargs):
        called["value"] = True
        return "stop"

    monkeypatch.setattr(
        controller.gui,
        "ask_duplicate_resolution",
        _should_not_call,
        raising=False,
    )

    action = controller._resolve_duplicate_dump_disc(
        disc_number=2,
        total=2,
        per_disc_titles=["pitch perfect 2", "pitch perfect"],
    )

    assert action == "bypass"
    assert called["value"] is False


def test_preview_title_finds_nested_mkv_output(tmp_path, monkeypatch):
    controller, engine = _controller_with_engine(_engine_cfg(
        temp_folder=str(tmp_path)
    ))

    def fake_rip_preview(rip_path, title_id, preview_seconds, on_log):
        _ = (rip_path, title_id, preview_seconds, on_log)
        nested = Path(rip_path) / "subdir"
        nested.mkdir(parents=True, exist_ok=True)
        (nested / "sample.mkv").write_text("ok")
        return True

    monkeypatch.setattr(engine, "rip_preview_title", fake_rip_preview)
    monkeypatch.setattr(
        engine,
        "analyze_files",
        lambda files, _log: [(files[0], 40, 100)] if files else [],
    )
    monkeypatch.setattr("controller.controller.shutil.which", lambda _x: None)
    monkeypatch.setattr("controller.controller.time.sleep", lambda _x: None)

    # Run thread target inline for deterministic test behavior.
    class _ImmediateThread:
        def __init__(self, target, daemon=True):
            self._target = target
            self._daemon = daemon

        def start(self):
            self._target()

    monkeypatch.setattr("controller.controller.threading.Thread", _ImmediateThread)

    controller.preview_title(0)

    assert not any(
        "Preview failed: no preview file found." in m
        for m in controller.gui.messages
    )
    assert any(
        ("Preview ready, but VLC was not found in PATH." in m) or
        ("Preview opened in VLC:" in m)
        for m in controller.gui.messages
    )
    assert any("Preview candidate:" in m for m in controller.gui.messages)


def test_state_machine_invalid_transition_raises():
    sm = SessionStateMachine()
    sm.transition(SessionState.SCANNED)

    import pytest
    with pytest.raises(RuntimeError):
        sm.transition(SessionState.MOVED)


def test_handle_fallback_blocked_in_strict_mode():
    controller, engine = _controller_with_engine()
    engine.cfg["opt_strict_mode"] = True
    controller.gui.ask_yesno = lambda _prompt: True

    result = handle_fallback(controller, "mapping missing", lambda: [1])

    assert result is None


def test_select_largest_file_prefers_biggest(tmp_path):
    a = tmp_path / "a.mkv"
    b = tmp_path / "b.mkv"
    a.write_bytes(b"a" * 10)
    b.write_bytes(b"b" * 100)

    selected = select_largest_file([str(a), str(b)])

    assert selected == str(b)


def test_prompt_run_path_overrides_uses_defaults_when_declined():
    controller, engine = _controller_with_engine()
    engine.cfg["temp_folder"] = r"C:\TempDefault"
    engine.cfg["movies_folder"] = r"C:\MoviesDefault"

    controller.gui.ask_yesno = lambda _prompt: False

    resolved = controller._prompt_run_path_overrides([
        ("temp_folder", "Temp Folder"),
        ("movies_folder", "Movies Folder"),
    ])

    assert resolved["temp_folder"] == os.path.normpath(r"C:\TempDefault")
    assert resolved["movies_folder"] == os.path.normpath(r"C:\MoviesDefault")


def test_prompt_run_path_overrides_accepts_custom_existing_path(tmp_path):
    controller, engine = _controller_with_engine()
    default_temp = str(tmp_path / "default-temp")
    custom_temp = str(tmp_path / "custom-temp")
    os.makedirs(default_temp, exist_ok=True)
    os.makedirs(custom_temp, exist_ok=True)
    engine.cfg["temp_folder"] = default_temp

    controller.gui.ask_yesno = lambda _prompt: True

    responses = iter([custom_temp])

    def ask_input(_label, _prompt, show_browse=False, default_value=""):
        _ = (show_browse, default_value)
        return next(responses)

    controller.gui.ask_input = ask_input

    resolved = controller._prompt_run_path_overrides([
        ("temp_folder", "Temp Folder"),
    ])

    assert resolved["temp_folder"] == os.path.normpath(custom_temp)


def test_validate_paths_blocks_temp_equals_movies(tmp_path):
    controller, _engine = _controller_with_engine()
    same = str(tmp_path / "same")

    err = controller._validate_paths(same, movies=same, tv=None)

    assert err is not None
    assert "cannot be the same" in err.lower()


def test_validate_paths_blocks_non_writable(monkeypatch, tmp_path):
    controller, _engine = _controller_with_engine()
    target = str(tmp_path / "no-write")
    os.makedirs(target, exist_ok=True)

    monkeypatch.setattr("controller.controller.os.path.exists", lambda p: True)
    monkeypatch.setattr("controller.controller.os.access", lambda p, mode: False)

    err = controller._validate_paths(target, movies=None, tv=None)

    assert err is not None
    assert "not writable" in err.lower()


def test_get_path_requires_initialized_session_paths():
    controller, _engine = _controller_with_engine()
    controller.session_paths = None

    import pytest
    with pytest.raises(RuntimeError):
        controller.get_path("temp")


def test_session_paths_initialized_and_accessible(tmp_path):
    controller, _engine = _controller_with_engine()
    custom_temp = str(tmp_path / "temp")
    os.makedirs(custom_temp, exist_ok=True)

    controller._init_session_paths({"temp_folder": custom_temp})

    assert controller.get_path("temp") == os.path.normpath(custom_temp)
