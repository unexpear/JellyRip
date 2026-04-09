import os
import unittest.mock


class _FakeTkBase:
    pass


def test_build_transcode_plan_preserves_relative_mkv_paths(tmp_path):
    source_root = tmp_path / "source"
    output_root = tmp_path / "output"
    first = source_root / "Season 01" / "episode01.mkv"
    second = source_root / "Extras" / "featurette.mkv"
    first.parent.mkdir(parents=True, exist_ok=True)
    second.parent.mkdir(parents=True, exist_ok=True)
    first.write_text("x", encoding="utf-8")
    second.write_text("x", encoding="utf-8")

    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import _build_transcode_plan

    plans = _build_transcode_plan(
        str(source_root),
        [str(first), str(second), str(first)],
        str(output_root),
    )

    assert [plan["relative_path"] for plan in plans] == [
        os.path.normpath("Season 01\\episode01.mkv"),
        os.path.normpath("Extras\\featurette.mkv"),
    ]
    assert [plan["output_relative_path"] for plan in plans] == [
        os.path.normpath("Season 01\\episode01.mkv"),
        os.path.normpath("Extras\\featurette.mkv"),
    ]
    assert [plan["output_path"] for plan in plans] == [
        os.path.normpath(str(output_root / "Season 01" / "episode01.mkv")),
        os.path.normpath(str(output_root / "Extras" / "featurette.mkv")),
    ]


def test_build_transcode_plan_falls_back_to_basename_for_outside_path(tmp_path):
    source_root = tmp_path / "source"
    outside_file = tmp_path / "other" / "movie.mkv"
    outside_file.parent.mkdir(parents=True, exist_ok=True)
    outside_file.write_text("x", encoding="utf-8")

    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import _build_transcode_plan

    plans = _build_transcode_plan(
        str(source_root),
        [str(outside_file)],
        str(tmp_path / "output"),
    )

    assert len(plans) == 1
    assert plans[0]["relative_path"] == "movie.mkv"
    assert plans[0]["output_relative_path"] == "movie.mkv"


def test_suggest_transcode_output_root_mentions_backend(tmp_path):
    scan_root = tmp_path / "My MKVs"
    scan_root.mkdir()

    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import _suggest_transcode_output_root

    ffmpeg_output = _suggest_transcode_output_root(str(scan_root), "ffmpeg")
    handbrake_output = _suggest_transcode_output_root(str(scan_root), "handbrake")

    assert ffmpeg_output.endswith("My MKVs - FFmpeg Output")
    assert handbrake_output.endswith("My MKVs - HandBrake Output")


def test_ffmpeg_builder_uses_custom_executable(tmp_path):
    from transcode.ffmpeg_builder import FFmpegBuilder
    from transcode.profiles import ProfileLoader

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    profile = loader.get_profile()
    cmd = FFmpegBuilder(
        profile,
        "input.mkv",
        "output.mkv",
        executable_path="C:\\Tools\\ffmpeg.exe",
    ).build_command()

    assert cmd[0] == "C:\\Tools\\ffmpeg.exe"
    assert cmd[-1] == "output.mkv"


def test_handbrake_engine_dry_run_uses_preset_and_custom_executable(tmp_path):
    from core.pipeline import TranscodeJob
    from transcode.engine import TranscodeEngine

    job = TranscodeJob(
        "input.mkv",
        "output.mkv",
        profile=None,
        backend="handbrake",
        backend_options={"preset": "Fast 1080p30"},
    )
    engine = TranscodeEngine(
        log_dir=str(tmp_path / "logs"),
        handbrake_exe="C:\\Tools\\HandBrakeCLI.exe",
    )
    cmd = engine.run_job(job, dry_run=True)

    assert cmd[0] == "C:\\Tools\\HandBrakeCLI.exe"
    assert "--preset" in cmd
    assert "Fast 1080p30" in cmd


def test_pipeline_controller_supports_handbrake_jobs_without_profile(tmp_path):
    from core.pipeline import PipelineController
    from transcode.profiles import ProfileLoader

    loader = ProfileLoader(str(tmp_path / "profiles.json"))
    controller = PipelineController(loader)
    output_path = tmp_path / "out" / "movie.mkv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("existing", encoding="utf-8")

    added = controller.add_job(
        "input.mkv",
        str(output_path),
        backend="handbrake",
        backend_options={"preset": "Fast 1080p30"},
    )

    assert added is True
    job = controller.get_queue()[0]
    assert job.profile is None
    assert job.backend == "handbrake"
    assert job.backend_options["preset"] == "Fast 1080p30"
    assert job.output_path.endswith("_1.mkv")


def test_choose_available_output_path_auto_increments(tmp_path):
    from core.pipeline import choose_available_output_path

    output_path = tmp_path / "movie.mkv"
    output_path.write_text("existing", encoding="utf-8")

    chosen = choose_available_output_path(str(output_path))

    assert chosen.endswith("_1.mkv")
