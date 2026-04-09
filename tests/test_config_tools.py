from config import AppConfig
# Example test using direct AppConfig construction
def test_appconfig_direct_construction():
    config = AppConfig(source="makemkvcon.exe", output="ffprobe.exe", quality="high")
    assert config.source == "makemkvcon.exe"
    assert config.output == "ffprobe.exe"
    assert config.quality == "high"
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # type: ignore[import-not-found]


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")


def test_resolve_tool_prefers_configured_path(tmp_path):
    configured = tmp_path / "cfg" / "ffprobe.exe"
    fallback = tmp_path / "fallback" / "ffprobe.exe"
    _touch(configured)
    _touch(fallback)

    resolved = config.resolve_tool(
        str(configured),
        [str(fallback)],
        "ffprobe",
    )

    assert os.path.normpath(resolved) == os.path.normpath(str(configured))


def test_resolve_tool_prefers_common_path_over_env(monkeypatch, tmp_path):
    configured = tmp_path / "missing" / "ffprobe.exe"
    fallback = tmp_path / "fallback" / "ffprobe.exe"
    env_tool = tmp_path / "path" / "ffprobe.exe"
    _touch(fallback)
    _touch(env_tool)

    monkeypatch.setattr(config.shutil, "which", lambda _name: str(env_tool))

    resolved = config.resolve_tool(
        str(configured),
        [str(fallback)],
        "ffprobe",
    )

    assert os.path.normpath(resolved) == os.path.normpath(str(fallback))


def test_resolve_tool_falls_back_to_env_path(monkeypatch, tmp_path):
    configured = tmp_path / "missing" / "ffprobe.exe"
    env_tool = tmp_path / "path" / "ffprobe.exe"
    _touch(env_tool)

    monkeypatch.setattr(config.shutil, "which", lambda _name: str(env_tool))

    resolved = config.resolve_tool(
        str(configured),
        [],
        "ffprobe",
    )

    assert os.path.normpath(resolved) == os.path.normpath(str(env_tool))


def test_auto_locate_ffmpeg_prefers_bundled_binary(monkeypatch, tmp_path):
    bundled = tmp_path / "ffmpeg.exe"
    bundled.write_text("x", encoding="utf-8")

    monkeypatch.setattr(config, "_bundled_binary_candidates", lambda _name: [str(bundled)])

    assert os.path.normpath(config.auto_locate_ffmpeg()) == os.path.normpath(str(bundled))


def test_should_keep_current_tool_path_when_new_is_invalid():
    def validator(path):
        return (path == "good.exe", "bad")

    keep_current = config.should_keep_current_tool_path(
        "good.exe",
        "bad.exe",
        validator,
    )

    assert keep_current is True


def test_should_not_keep_current_when_existing_path_is_not_working():
    def validator(path):
        return (path == "new-good.exe", "bad")

    keep_current = config.should_keep_current_tool_path(
        "old-bad.exe",
        "new-good.exe",
        validator,
    )

    assert keep_current is False
