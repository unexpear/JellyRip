import os

import pytest

from controller.session_paths import (
    ensure_session_paths,
    get_session_path,
    init_session_paths,
    log_session_paths,
    validate_session_paths,
)


def test_init_session_paths_applies_overrides(tmp_path):
    cfg = {
        "temp_folder": str(tmp_path / "temp"),
        "movies_folder": str(tmp_path / "movies"),
        "tv_folder": str(tmp_path / "tv"),
    }

    session_paths = init_session_paths(
        cfg,
        {"temp_folder": str(tmp_path / "custom-temp")},
    )

    assert session_paths["temp"] == os.path.normpath(str(tmp_path / "custom-temp"))
    assert session_paths["movies"] == os.path.normpath(str(tmp_path / "movies"))
    assert session_paths["tv"] == os.path.normpath(str(tmp_path / "tv"))


def test_get_and_ensure_session_paths_require_initialization():
    with pytest.raises(RuntimeError):
        get_session_path(None, "temp")

    with pytest.raises(RuntimeError):
        ensure_session_paths(None)


def test_log_session_paths_emits_expected_lines():
    messages: list[str] = []

    log_session_paths(
        {"temp": r"C:\temp", "movies": r"D:\movies", "tv": r"E:\tv"},
        version="1.2.3",
        log_fn=messages.append,
    )

    assert messages == [
        "=== JellyRip v1.2.3 - session start ===",
        r"Temp:   C:\temp",
        r"Movies: D:\movies",
        r"TV:     E:\tv",
        "=================",
    ]


def test_validate_session_paths_blocks_non_writable(monkeypatch, tmp_path):
    target = tmp_path / "no-write"
    target.mkdir()

    monkeypatch.setattr("controller.session_paths.os.access", lambda path, mode: False)

    error = validate_session_paths(str(target))

    assert error is not None
    assert "not writable" in error.lower()
