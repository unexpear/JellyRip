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

    def set_progress(self, _value):
        pass

    def start_indeterminate(self):
        pass

    def stop_indeterminate(self):
        pass


class ScriptedSetupGUI(DummyGUI):
    def __init__(self, scripted_inputs, scripted_confirms):
        super().__init__()
        self._inputs = iter(scripted_inputs)
        self._confirms = iter(scripted_confirms)

    def ask_input(self, _label, _prompt, default_value=""):
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


def test_nonzero_exit_with_output_is_degraded_success(tmp_path, monkeypatch):
    """rip_selected_titles: non-zero exit + files produced = degraded success, not failure."""
    controller, engine = _controller_with_engine(
        _engine_cfg(opt_auto_retry=False, opt_retry_attempts=1)
    )

    def fake_run(_cmd, _on_progress, _on_log):
        Path(tmp_path, "title_t00.mkv").write_text("data")
        return False  # non-zero exit

    monkeypatch.setattr(engine, "_run_rip_process", fake_run)

    success, failed = engine.rip_selected_titles(
        str(tmp_path), [0], on_progress=lambda _p: None, on_log=controller.log
    )

    assert success is True
    assert failed == []
    assert engine.last_degraded_titles == [1]
    assert any("degraded success" in m for m in controller.gui.messages)


def test_partial_title_failure_forces_session_failure(tmp_path, monkeypatch):
    controller, engine = _controller_with_engine()
    Path(tmp_path, "file.mkv").write_text("ok")
    monkeypatch.setattr(engine, "_quick_ffprobe_ok", lambda _f, _l: True)

    normalized_success, _files = controller._normalize_rip_result(
        str(tmp_path), True, [1]
    )

    assert normalized_success is False


def test_ffprobe_cache_accumulates_entries(tmp_path, monkeypatch):
    _controller, engine = _controller_with_engine()
    first = tmp_path / "first.mkv"
    second = tmp_path / "second.mkv"
    first.write_bytes(b"a" * 10)
    second.write_bytes(b"b" * 20)

    class FakeProc:
        def poll(self):
            return 0

        def communicate(self):
            return ('{"format": {"duration": "60"}}', "")

    monkeypatch.setattr(
        "engine.ripper_engine.subprocess.Popen",
        lambda *args, **kwargs: FakeProc(),
    )

    engine._probe_file_duration_and_size(str(first), ffprobe="ffprobe")
    engine._probe_file_duration_and_size(str(second), ffprobe="ffprobe")

    assert len(engine._ffprobe_cache) == 2


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
        extra_indices=None,
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


def test_wait_for_new_unique_disc_allows_manual_advance_when_unverified(monkeypatch):
    controller, _engine = _controller_with_engine()
    seen = set()

    monkeypatch.setattr(
        controller.gui, "show_info", lambda *_a, **_k: None, raising=False
    )
    monkeypatch.setattr(controller, "_wait_for_disc_state", lambda *_a, **_k: True)

    calls = iter([None, None])
    monkeypatch.setattr(controller, "_build_disc_fingerprint", lambda: next(calls))
    monkeypatch.setattr(
        controller.gui,
        "ask_duplicate_resolution",
        lambda *_a, **_k: "bypass",
        raising=False,
    )

    result = controller._wait_for_new_unique_disc(
        seen_fingerprints=seen,
        disc_number=2,
        total=4,
    )

    assert result == "manual-advance"
    assert any(
        "could not read disc fingerprint" in line.lower()
        for line in controller.session_report
    )


def test_wait_for_new_unique_disc_stop_after_unverified(monkeypatch):
    controller, _engine = _controller_with_engine()

    monkeypatch.setattr(
        controller.gui, "show_info", lambda *_a, **_k: None, raising=False
    )
    monkeypatch.setattr(controller, "_wait_for_disc_state", lambda *_a, **_k: True)

    calls = iter([None, None])
    monkeypatch.setattr(controller, "_build_disc_fingerprint", lambda: next(calls))
    monkeypatch.setattr(
        controller.gui,
        "ask_duplicate_resolution",
        lambda *_a, **_k: "stop",
        raising=False,
    )

    result = controller._wait_for_new_unique_disc(
        seen_fingerprints=set(),
        disc_number=2,
        total=4,
    )

    assert result is None
    assert any(
        "stopped after unverified disc prompt" in line.lower()
        for line in controller.session_report
    )


def test_preview_title_finds_nested_mkv_output(tmp_path, monkeypatch):
    controller, engine = _controller_with_engine(_engine_cfg(
        temp_folder=str(tmp_path)
    ))
    opened = []

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
    real_isfile = controller_module.os.path.isfile
    monkeypatch.setattr(
        "controller.controller.os.path.isfile",
        lambda path: False if "VideoLAN\\VLC\\vlc.exe" in str(path) else real_isfile(path),
    )
    monkeypatch.setattr(
        "controller.controller.subprocess.Popen",
        lambda args: opened.append(args),
    )
    monkeypatch.setattr(
        "controller.controller.os.startfile",
        lambda path: opened.append(path),
    )
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
        ("VLC not found; opening in default player:" in m) or
        ("Preview opened in VLC:" in m)
        for m in controller.gui.messages
    )
    assert any("Preview candidate:" in m for m in controller.gui.messages)
    assert len(opened) == 1


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

    def ask_input(_label, _prompt, default_value=""):
        _ = default_value
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


def test_ensure_session_paths_raises_before_init():
    """_ensure_session_paths() must raise RuntimeError if called before init."""
    controller, _engine = _controller_with_engine()
    controller.session_paths = None

    import pytest
    with pytest.raises(RuntimeError, match="session_paths not initialized"):
        controller._ensure_session_paths()


def test_ensure_session_paths_passes_after_init(tmp_path):
    """_ensure_session_paths() must not raise once _init_session_paths ran."""
    controller, engine = _controller_with_engine()
    engine.cfg["temp_folder"] = str(tmp_path / "temp")
    engine.cfg["movies_folder"] = str(tmp_path / "movies")
    engine.cfg["tv_folder"] = str(tmp_path / "tv")

    controller._init_session_paths({})
    controller._ensure_session_paths()  # must not raise


def test_verify_container_integrity_uses_preanalyzed_data(monkeypatch, tmp_path):
    """_verify_container_integrity(analyzed=...) must not call analyze_files."""
    controller, engine = _controller_with_engine()

    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    analyze_called = {"times": 0}

    def fake_analyze(files, log):
        analyze_called["times"] += 1
        return [(str(files[0]), 5400.0, 4200)]

    monkeypatch.setattr(engine, "analyze_files", fake_analyze)

    # Pass pre-analyzed data — analyze_files must NOT be called.
    preanalyzed = [(str(f), 5400.0, 4200)]
    result = controller._verify_container_integrity([str(f)], analyzed=preanalyzed)

    assert result is True
    assert analyze_called["times"] == 0


def test_verify_container_integrity_calls_analyze_when_no_preanalyzed(
    monkeypatch, tmp_path
):
    """Without analyzed=, _verify_container_integrity must call analyze_files."""
    controller, engine = _controller_with_engine()

    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    analyze_called = {"times": 0}

    def fake_analyze(files, log):
        analyze_called["times"] += 1
        return [(str(files[0]), 5400.0, 4200)]

    monkeypatch.setattr(engine, "analyze_files", fake_analyze)

    result = controller._verify_container_integrity([str(f)])

    assert result is True
    assert analyze_called["times"] == 1


def test_verify_container_integrity_fails_on_zero_duration(tmp_path):
    """A file with duration <= 0 in pre-analyzed data must fail integrity."""
    controller, _engine = _controller_with_engine()

    f = tmp_path / "corrupt.mkv"
    f.write_text("bad")

    preanalyzed = [(str(f), 0.0, 100)]
    result = controller._verify_container_integrity([str(f)], analyzed=preanalyzed)

    assert result is False
    assert any("Container integrity check failed" in m for m in controller.gui.messages)


def test_verify_container_integrity_fails_on_count_mismatch(tmp_path):
    """If analyzed count < file count, integrity check must fail."""
    controller, _engine = _controller_with_engine()

    f1 = tmp_path / "a.mkv"
    f2 = tmp_path / "b.mkv"
    f1.write_text("a")
    f2.write_text("b")

    # Only one result for two files.
    preanalyzed = [(str(f1), 5400.0, 4200)]
    result = controller._verify_container_integrity(
        [str(f1), str(f2)], analyzed=preanalyzed
    )

    assert result is False
    assert any("incomplete" in m for m in controller.gui.messages)


def test_size_advisory_log_uses_arrow_format(tmp_path, monkeypatch):
    """Post-stabilization advisory must use 'expected X GB → threshold Y GB' format."""
    import time as time_module

    controller, engine = _controller_with_engine({
        **_engine_cfg(),
        "opt_file_stabilization": True,
        "opt_stabilize_timeout_seconds": 5,
        "opt_stabilize_required_polls": 1,
        "opt_min_rip_size_gb": 1,
        "opt_expected_size_ratio_pct": 70,
        "opt_hard_fail_ratio_pct": 40,
    })

    tiny = tmp_path / "title_t02.mkv"
    tiny.write_bytes(b"x" * (1 * 1024 * 1024))  # 1 MB

    monkeypatch.setattr(
        "controller.controller.time.sleep", lambda _s: None
    )
    monkeypatch.setattr(
        controller, "_stabilize_file",
        lambda _f, _timeout, _polls: (True, False)
    )

    # 500 MB expected → floor = 250 MB; actual is 1 MB so advisory fires.
    expected_size_by_title = {2: 500 * 1024 * 1024}
    controller._stabilize_ripped_files(
        [str(tiny)], expected_size_by_title=expected_size_by_title
    )

    advisory_lines = [
        m for m in controller.gui.messages
        if "below threshold" in m
    ]
    assert advisory_lines, "Expected an advisory log line"
    assert "→" in advisory_lines[0]
    assert "expected" in advisory_lines[0]
    assert "threshold" in advisory_lines[0]


# ── Degraded rip classification ──────────────────────────────────────────────

def test_nonzero_exit_no_files_is_real_failure(tmp_path, monkeypatch):
    """rip_selected_titles: non-zero exit + no files = real failure."""
    controller, engine = _controller_with_engine(
        _engine_cfg(opt_auto_retry=False, opt_retry_attempts=1)
    )

    def fake_run(_cmd, _on_progress, _on_log):
        return False  # exit error, no files written

    monkeypatch.setattr(engine, "_run_rip_process", fake_run)

    success, failed = engine.rip_selected_titles(
        str(tmp_path), [0], on_progress=lambda _p: None, on_log=controller.log
    )

    assert success is False or 1 in failed
    assert engine.last_degraded_titles == []


def test_degraded_rip_added_to_session_report(tmp_path, monkeypatch):
    """_warn_degraded_rips() must append a warning to session_report."""
    controller, engine = _controller_with_engine(
        _engine_cfg(opt_auto_retry=False, opt_retry_attempts=1)
    )

    def fake_run(_cmd, _on_progress, _on_log):
        Path(tmp_path, "title_t00.mkv").write_text("data")
        return False

    monkeypatch.setattr(engine, "_run_rip_process", fake_run)

    engine.rip_selected_titles(
        str(tmp_path), [0], on_progress=lambda _p: None, on_log=controller.log
    )
    controller._warn_degraded_rips()

    assert any("degraded rip" in line for line in controller.session_report)


def test_session_summary_shows_warnings_on_degraded_rip(tmp_path, monkeypatch):
    """write_session_summary: COMPLETED state + session_report → 'Completed with warnings'."""
    controller, engine = _controller_with_engine()

    controller._reset_state_machine()
    # Manually drive state to COMPLETED with a warning in session_report.
    for state in (
        SessionState.SCANNED,
        SessionState.RIPPED,
        SessionState.STABILIZED,
        SessionState.VALIDATED,
        SessionState.MOVED,
        SessionState.COMPLETED,
    ):
        controller.sm.transition(state)

    controller.session_report.append("Title 1: MakeMKV read errors (degraded rip)")

    controller.write_session_summary()

    assert any(
        "Completed with warnings" in m for m in controller.gui.messages
    )
    assert not any(
        "All discs completed successfully" in m for m in controller.gui.messages
    )


def test_session_summary_clean_when_no_warnings():
    """write_session_summary: COMPLETED state + empty session_report → clean success message."""
    controller, _engine = _controller_with_engine()

    controller._reset_state_machine()
    for state in (
        SessionState.SCANNED,
        SessionState.RIPPED,
        SessionState.STABILIZED,
        SessionState.VALIDATED,
        SessionState.MOVED,
        SessionState.COMPLETED,
    ):
        controller.sm.transition(state)

    controller.write_session_summary()

    assert any(
        "All discs completed successfully" in m for m in controller.gui.messages
    )


# ── Fallback logging ──────────────────────────────────────────────────────────

def test_fallback_title_from_mode_logs_to_session_report(monkeypatch):
    """_fallback_title_from_mode must emit a session report entry."""
    controller, _engine = _controller_with_engine()

    monkeypatch.setattr(
        "controller.controller.build_fallback_title",
        lambda *_a, **_kw: "Auto-Title-2026",
    )

    result = controller._fallback_title_from_mode()

    assert result == "Auto-Title-2026"
    assert any("Auto-Title-2026" in line for line in controller.session_report)


# ── Duration sanity check (tiered + aggregation + clamping) ──────────────────

def test_integrity_severe_duration_warns_only_no_size(tmp_path):
    """< 50% duration alone → severe warning but still returns True."""
    controller, _engine = _controller_with_engine()
    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    # 600 s actual, 3600 s expected → 16.7% — severe tier (long title).
    preanalyzed = [(str(f), 600.0, 100)]
    result = controller._verify_container_integrity(
        [str(f)],
        analyzed=preanalyzed,
        expected_durations={str(f): 3600.0},
    )

    assert result is True  # warning only when size not confirmed
    assert any("Severe" in line or "severe" in line for line in controller.session_report)


def test_integrity_severe_duration_and_size_logs_error(tmp_path):
    """< 50% duration AND < 50% size (above 200MB floor) → TRUNCATION ERROR."""
    controller, _engine = _controller_with_engine()
    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    # 600 s (16.7%), 400 MB actual vs 4000 MB expected (10%) — both severe.
    preanalyzed = [(str(f), 600.0, 400)]  # size_mb = 400 (above 200MB floor)
    result = controller._verify_container_integrity(
        [str(f)],
        analyzed=preanalyzed,
        expected_durations={str(f): 3600.0},
        expected_sizes={str(f): 4000 * 1024 * 1024},
    )

    assert result is True  # error in report, still not hard fail (no strict)
    assert any("TRUNCATION ERROR" in line for line in controller.session_report)


def test_integrity_small_expected_size_disables_escalation(tmp_path):
    """expected_size < 200 MB floor → size signal ignored, no escalation."""
    controller, _engine = _controller_with_engine()
    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    # 600 s (16.7%) duration — would be severe. But expected_size only 50 MB
    # — below 200 MB floor so size signal must be ignored.
    preanalyzed = [(str(f), 600.0, 10)]  # actual 10 MB
    result = controller._verify_container_integrity(
        [str(f)],
        analyzed=preanalyzed,
        expected_durations={str(f): 3600.0},
        expected_sizes={str(f): 50 * 1024 * 1024},  # 50 MB — below floor
    )

    assert result is True
    assert not any("TRUNCATION ERROR" in line for line in controller.session_report)
    assert any("Severe" in line for line in controller.session_report)  # dur warning still fires


def test_integrity_strict_mode_fails_on_likely_truncation(tmp_path):
    """Strict mode: likely truncation (50-75% duration) → returns False."""
    controller, engine = _controller_with_engine()
    engine.cfg["opt_strict_mode"] = True
    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    # 2000 s actual, 3600 s expected → 55.6% — likely truncation tier.
    preanalyzed = [(str(f), 2000.0, 100)]
    result = controller._verify_container_integrity(
        [str(f)],
        analyzed=preanalyzed,
        expected_durations={str(f): 3600.0},
    )

    assert result is False
    assert any("Strict mode" in line for line in controller.gui.messages)


def test_integrity_minor_mismatch_warns_but_passes(tmp_path):
    """75–90% duration → minor warning, still returns True."""
    controller, _engine = _controller_with_engine()
    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    # 2880 s actual, 3600 s expected → 80% — minor tier.
    preanalyzed = [(str(f), 2880.0, 100)]
    result = controller._verify_container_integrity(
        [str(f)],
        analyzed=preanalyzed,
        expected_durations={str(f): 3600.0},
    )

    assert result is True
    assert any("Minor" in line or "minor" in line for line in controller.session_report)


def test_integrity_normal_variance_no_warning(tmp_path):
    """>= 90% duration → no warning at all."""
    controller, _engine = _controller_with_engine()
    f = tmp_path / "title_t00.mkv"
    f.write_text("fake")

    # 3300 s actual, 3600 s expected → 91.7% — normal variance.
    preanalyzed = [(str(f), 3300.0, 100)]
    result = controller._verify_container_integrity(
        [str(f)],
        analyzed=preanalyzed,
        expected_durations={str(f): 3600.0},
    )

    assert result is True
    assert controller.session_report == []


def test_integrity_multi_file_title_aggregates_before_comparing(tmp_path):
    """Two files from one title: aggregate duration before comparing — no false warning."""
    controller, _engine = _controller_with_engine()
    f1 = tmp_path / "part1.mkv"
    f2 = tmp_path / "part2.mkv"
    f1.write_text("p1")
    f2.write_text("p2")

    # Each file is 1800 s (30 min). Expected total 3600 s.
    # Per-file: 1800/3600 = 50% → would trigger "likely" warning.
    # Aggregated: 3600/3600 = 100% → no warning.
    preanalyzed = [(str(f1), 1800.0, 200), (str(f2), 1800.0, 200)]
    result = controller._verify_container_integrity(
        [str(f1), str(f2)],
        analyzed=preanalyzed,
        expected_durations={str(f1): 3600.0, str(f2): 0},  # expect only on group
        title_file_map={0: [str(f1), str(f2)]},
    )

    assert result is True
    assert controller.session_report == []


def test_integrity_multi_file_dedup_only_one_warning(tmp_path):
    """Two files from one title both below threshold → only ONE warning emitted."""
    controller, _engine = _controller_with_engine()
    f1 = tmp_path / "part1.mkv"
    f2 = tmp_path / "part2.mkv"
    f1.write_text("p1")
    f2.write_text("p2")

    # Total 600 s, expected 3600 s → 16.7% — severe, one warning for the group.
    preanalyzed = [(str(f1), 300.0, 100), (str(f2), 300.0, 100)]
    result = controller._verify_container_integrity(
        [str(f1), str(f2)],
        analyzed=preanalyzed,
        expected_durations={str(f1): 1800.0, str(f2): 1800.0},
        title_file_map={0: [str(f1), str(f2)]},
    )

    assert result is True
    # Only one warning entry for the title group, not two.
    warn_lines = [l for l in controller.session_report if "Severe" in l or "severe" in l]
    assert len(warn_lines) == 1



# ---------------------------------------------------------------------------
# Library-scanning helpers — append / gap-fill / existing show support
# ---------------------------------------------------------------------------

# --- get_next_episode gap-fill logic ---

def test_get_next_episode_empty_set_returns_1():
    """No existing episodes → first episode is 1."""
    c, _ = _controller_with_engine()
    assert c.get_next_episode(set()) == 1


def test_get_next_episode_appends_after_max():
    """Contiguous set → suggest next after the last."""
    c, _ = _controller_with_engine()
    assert c.get_next_episode({1, 2, 3}) == 4


def test_get_next_episode_fills_gap():
    """Missing episode 3 → suggest 3, not 6."""
    c, _ = _controller_with_engine()
    assert c.get_next_episode({1, 2, 4, 5}) == 3


def test_get_next_episode_fills_earliest_gap():
    """Multiple gaps → always return the lowest missing."""
    c, _ = _controller_with_engine()
    # 2 and 4 are both missing; 2 is earlier
    assert c.get_next_episode({1, 3, 5}) == 2


# --- _scan_episode_files (replaces _scan_highest_episode internally) ---

def test_scan_highest_episode_returns_zero_for_empty_folder(tmp_path):
    """No episode files → returns 0 (first disc starts at episode 1)."""
    controller, _ = _controller_with_engine()
    result = controller._scan_highest_episode(str(tmp_path), 1)
    assert result == 0


def test_scan_highest_episode_detects_existing_episodes(tmp_path):
    """Three S01Exx files present → returns highest episode number."""
    controller, _ = _controller_with_engine()
    (tmp_path / "Show - S01E01 - Pilot.mkv").write_text("")
    (tmp_path / "Show - S01E02 - Second.mkv").write_text("")
    (tmp_path / "Show - S01E08 - Eight.mkv").write_text("")
    result = controller._scan_highest_episode(str(tmp_path), 1)
    assert result == 8


def test_scan_highest_episode_ignores_other_seasons(tmp_path):
    """Files from a different season are not counted."""
    controller, _ = _controller_with_engine()
    (tmp_path / "Show - S01E05 - One.mkv").write_text("")
    (tmp_path / "Show - S02E10 - Two.mkv").write_text("")
    result = controller._scan_highest_episode(str(tmp_path), 1)
    assert result == 5


def test_scan_highest_episode_case_insensitive(tmp_path):
    """Filenames with mixed-case S/E markers are still detected."""
    controller, _ = _controller_with_engine()
    (tmp_path / "show - s01e03 - lower.mkv").write_text("")
    result = controller._scan_highest_episode(str(tmp_path), 1)
    assert result == 3


def test_scan_highest_episode_nonexistent_folder():
    """Non-existent folder returns 0 safely (no exception)."""
    controller, _ = _controller_with_engine()
    result = controller._scan_highest_episode("/path/that/does/not/exist", 1)
    assert result == 0


def test_scan_highest_episode_returns_zero_when_dest_none():
    """None dest_folder returns 0 (TV path not yet created)."""
    controller, _ = _controller_with_engine()
    result = controller._scan_highest_episode(None, 1)
    assert result == 0


def test_scan_episode_files_detects_1x01_format(tmp_path):
    """NxEE filename format (1x03) is recognised."""
    c, _ = _controller_with_engine()
    (tmp_path / "Show 1x01 Title.mkv").write_text("")
    (tmp_path / "Show 1x02 Title.mkv").write_text("")
    result = c._scan_episode_files(str(tmp_path), 1)
    assert result == {1, 2}


def test_scan_episode_files_detects_episode_n_format(tmp_path):
    """'Episode N' filename format is recognised."""
    c, _ = _controller_with_engine()
    (tmp_path / "Episode 4.mkv").write_text("")
    (tmp_path / "episode 7.mkv").write_text("")
    result = c._scan_episode_files(str(tmp_path), 1)
    assert 4 in result
    assert 7 in result


# --- _scan_library_folder ---

def test_scan_library_folder_detects_season_dirs(tmp_path):
    """Season subdirs with episode files are returned keyed by season number."""
    c, _ = _controller_with_engine()
    s1 = tmp_path / "Season 01"
    s1.mkdir()
    (s1 / "Show - S01E01.mkv").write_text("")
    (s1 / "Show - S01E02.mkv").write_text("")
    s2 = tmp_path / "Season 02"
    s2.mkdir()
    (s2 / "Show - S02E01.mkv").write_text("")

    result = c._scan_library_folder(str(tmp_path))
    assert 1 in result and result[1] == [1, 2]
    assert 2 in result and result[2] == [1]


def test_scan_library_folder_ignores_non_season_dirs(tmp_path):
    """Non-season directories are ignored, while Specials maps to season 0."""
    c, _ = _controller_with_engine()
    (tmp_path / "Extras").mkdir()
    (tmp_path / "Specials").mkdir()
    (tmp_path / "Specials" / "Episode 1.mkv").write_text("")
    s1 = tmp_path / "Season 01"
    s1.mkdir()
    (s1 / "Show - S01E01.mkv").write_text("")

    result = c._scan_library_folder(str(tmp_path))
    assert set(result.keys()) == {0, 1}
    assert result[0] == [1]


def test_scan_library_folder_empty_show_root(tmp_path):
    """Empty show root (no season folders) returns an empty dict."""
    c, _ = _controller_with_engine()
    result = c._scan_library_folder(str(tmp_path))
    assert result == {}


def test_scan_library_folder_nonexistent_path():
    """Non-existent path returns empty dict without raising."""
    c, _ = _controller_with_engine()
    result = c._scan_library_folder("/does/not/exist")
    assert result == {}


def test_scan_library_folder_returns_sorted_episodes(tmp_path):
    """Episode lists in the returned dict are sorted ascending."""
    c, _ = _controller_with_engine()
    s1 = tmp_path / "Season 01"
    s1.mkdir()
    for ep in (5, 1, 3, 2, 4):
        (s1 / f"Show - S01E{ep:02d}.mkv").write_text("")

    result = c._scan_library_folder(str(tmp_path))
    assert result[1] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Multi-episode filenames (S01E01E02.mkv), Season 00, duplicate protection
# ---------------------------------------------------------------------------

# --- multi-episode filename detection ---

def test_multi_episode_file_contributes_both_episodes(tmp_path):
    """S01E01E02.mkv must register BOTH E01 and E02."""
    c, _ = _controller_with_engine()
    (tmp_path / "Show - S01E01E02 - Title.mkv").write_text("")
    result = c._scan_episode_files(str(tmp_path), 1)
    assert result == {1, 2}


def test_multi_episode_file_three_episodes(tmp_path):
    """S01E01E02E03.mkv registers three episodes."""
    c, _ = _controller_with_engine()
    (tmp_path / "Show - S01E01E02E03 - Title.mkv").write_text("")
    result = c._scan_episode_files(str(tmp_path), 1)
    assert result == {1, 2, 3}


def test_multi_episode_file_does_not_report_gap_for_covered_range(tmp_path):
    """When S01E01E02.mkv exists, get_next_episode should suggest E03, not E02."""
    c, _ = _controller_with_engine()
    (tmp_path / "Show - S01E01E02.mkv").write_text("")
    existing = c._scan_episode_files(str(tmp_path), 1)
    assert c.get_next_episode(existing) == 3


def test_multi_episode_ignores_wrong_season(tmp_path):
    """S02E01E02.mkv must not register episodes for season 1."""
    c, _ = _controller_with_engine()
    (tmp_path / "Show - S02E01E02 - Title.mkv").write_text("")
    result = c._scan_episode_files(str(tmp_path), 1)
    assert result == set()


# --- Season 00 / Specials ---

def test_scan_library_folder_detects_season_00(tmp_path):
    """'Season 00' directory is returned as season 0."""
    c, _ = _controller_with_engine()
    s0 = tmp_path / "Season 00"
    s0.mkdir()
    (s0 / "Show - S00E01 - Special.mkv").write_text("")
    result = c._scan_library_folder(str(tmp_path))
    assert 0 in result
    assert result[0] == [1]


def test_scan_library_folder_detects_specials_folder(tmp_path):
    """A folder named 'Specials' maps to season 0."""
    c, _ = _controller_with_engine()
    sp = tmp_path / "Specials"
    sp.mkdir()
    (sp / "Episode 1.mkv").write_text("")
    result = c._scan_library_folder(str(tmp_path))
    assert 0 in result


def test_scan_library_folder_season_00_logs_detection(tmp_path):
    """Detecting Season 00 emits a log line (not silently ignored)."""
    c, _ = _controller_with_engine()
    s0 = tmp_path / "Season 00"
    s0.mkdir()
    (s0 / "Show - S00E01.mkv").write_text("")
    c._scan_library_folder(str(tmp_path))
    assert any("Specials" in m or "Season 00" in m for m in c.session_log)


# --- _episodes_from_filename edge cases ---

def test_episodes_from_filename_single(tmp_path):
    """Standard S01E05 returns {5}."""
    c, _ = _controller_with_engine()
    assert c._episodes_from_filename("Show - S01E05 - Title.mkv", 1) == {5}


def test_episodes_from_filename_wrong_season_returns_empty(tmp_path):
    """S02E05 returns empty set when queried for season 1."""
    c, _ = _controller_with_engine()
    assert c._episodes_from_filename("Show - S02E05.mkv", 1) == set()
