from __future__ import annotations

from controller.library_scan import (
    episodes_from_filename,
    get_next_episode,
    scan_episode_files,
    scan_highest_episode,
    scan_library_folder,
)


def test_get_next_episode_fills_lowest_gap():
    assert get_next_episode({1, 2, 4, 5}) == 3


def test_episodes_from_filename_handles_chained_episode_tokens():
    assert episodes_from_filename("Show - S01E01E02E03.mkv", 1) == {1, 2, 3}


def test_episodes_from_filename_ignores_wrong_season():
    assert episodes_from_filename("Show - S02E01E02.mkv", 1) == set()


def test_scan_episode_files_supports_episode_n_format(tmp_path):
    (tmp_path / "Episode 4.mkv").write_text("")
    (tmp_path / "episode 7.mkv").write_text("")

    assert scan_episode_files(str(tmp_path), 1) == {4, 7}
    assert scan_highest_episode(str(tmp_path), 1) == 7


def test_scan_library_folder_detects_specials_and_logs(tmp_path):
    messages: list[str] = []
    specials = tmp_path / "Specials"
    season = tmp_path / "Season 01"
    specials.mkdir()
    season.mkdir()
    (specials / "Episode 1.mkv").write_text("")
    (season / "Show - S01E02.mkv").write_text("")

    result = scan_library_folder(str(tmp_path), log_fn=messages.append)

    assert result == {0: [1], 1: [2]}
    assert any("Specials/Season 00 detected" in message for message in messages)
