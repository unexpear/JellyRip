"""Tests for the lossless episode splitter (engine.episode_split).

The marker->span logic is pure and exhaustively tested; the ffmpeg
invocation is tested through an injected ``runner`` so these stay
hermetic (no real ffmpeg, no real files except tiny stand-ins).

Covers the "watch a multi-episode title and mark episodes" flow
(2026-06-13): markers are episode START points, spans run to the next
marker (last to end of file), pre-first-marker pre-roll is dropped,
zero-length spans are skipped, the ffmpeg command is a lossless
stream copy with input seeking + duration, and a single failed cut
doesn't sink the others.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.episode_split import (
    EpisodeMarker,
    EpisodeSpan,
    build_episode_spans,
    build_split_command,
    split_title,
)


# ---------------------------------------------------------------------------
# build_episode_spans — pure logic
# ---------------------------------------------------------------------------


def test_three_markers_make_three_spans_last_to_end():
    spans = build_episode_spans(
        [
            EpisodeMarker(0.0, "Pilot"),
            EpisodeMarker(1320.0, "Episode 2"),
            EpisodeMarker(2640.0, "Episode 3"),
        ],
        total_seconds=3960.0,
    )
    assert [(s.index, s.start_seconds, s.end_seconds, s.name) for s in spans] == [
        (1, 0.0, 1320.0, "Pilot"),
        (2, 1320.0, 2640.0, "Episode 2"),
        (3, 2640.0, 3960.0, "Episode 3"),
    ]


def test_markers_are_sorted_by_time():
    """The UI can collect markers out of order; spans come out ordered."""
    spans = build_episode_spans(
        [EpisodeMarker(2000.0, "C"), EpisodeMarker(0.0, "A"), EpisodeMarker(1000.0, "B")],
        total_seconds=3000.0,
    )
    assert [s.name for s in spans] == ["A", "B", "C"]
    assert [s.index for s in spans] == [1, 2, 3]


def test_preroll_before_first_marker_is_dropped():
    """A first marker at 30s means [0,30) (a disc logo) is not an
    episode — start a marker at 0 to keep it."""
    spans = build_episode_spans(
        [EpisodeMarker(30.0, "Ep1"), EpisodeMarker(1500.0, "Ep2")],
        total_seconds=3000.0,
    )
    assert spans[0].start_seconds == 30.0
    assert spans[0].name == "Ep1"
    assert len(spans) == 2


def test_unknown_duration_leaves_last_span_open_ended():
    spans = build_episode_spans(
        [EpisodeMarker(0.0, "A"), EpisodeMarker(100.0, "B")],
        total_seconds=None,
    )
    assert spans[-1].end_seconds is None


def test_zero_length_span_is_skipped():
    """Two markers at the same time, or one at/after the end, collapse."""
    spans = build_episode_spans(
        [EpisodeMarker(0.0, "A"), EpisodeMarker(100.0, "B"), EpisodeMarker(100.0, "dup")],
        total_seconds=200.0,
    )
    # A:[0,100), then B and dup are both at 100 — B:[100,100) drops,
    # dup:[100,200) survives.  Re-indexed 1..2.
    assert [(s.start_seconds, s.end_seconds) for s in spans] == [(0.0, 100.0), (100.0, 200.0)]
    assert [s.index for s in spans] == [1, 2]


def test_negative_marker_clamped_to_zero():
    spans = build_episode_spans([EpisodeMarker(-5.0, "A")], total_seconds=100.0)
    assert spans[0].start_seconds == 0.0


def test_no_markers_gives_no_spans():
    assert build_episode_spans([], total_seconds=100.0) == []


# ---------------------------------------------------------------------------
# build_split_command — the ffmpeg argv
# ---------------------------------------------------------------------------


def test_command_is_lossless_copy_with_seek_and_duration():
    cmd = build_split_command(
        "ffmpeg.exe", "src.mkv",
        EpisodeSpan(2, 1320.0, 2640.0, "Ep2"), "out.mkv",
    )
    # Lossless: stream copy, all streams mapped.
    assert "-c" in cmd and cmd[cmd.index("-c") + 1] == "copy"
    assert cmd[cmd.index("-map") + 1] == "0"
    # Input seeking (before -i) for speed.
    assert cmd.index("-ss") < cmd.index("-i")
    assert cmd[cmd.index("-ss") + 1] == "1320.000"
    # Duration, not -to (avoids the relative-to-what ambiguity).
    assert "-to" not in cmd
    assert cmd[cmd.index("-t") + 1] == "1320.000"  # 2640 - 1320
    assert cmd[-1] == "out.mkv"


def test_first_span_at_zero_omits_seek():
    cmd = build_split_command(
        "ffmpeg.exe", "src.mkv", EpisodeSpan(1, 0.0, 100.0, "Ep1"), "o.mkv",
    )
    assert "-ss" not in cmd  # no point seeking to 0


def test_final_open_ended_span_omits_duration():
    cmd = build_split_command(
        "ffmpeg.exe", "src.mkv", EpisodeSpan(3, 2640.0, None, "Ep3"), "o.mkv",
    )
    assert "-ss" in cmd
    assert "-t" not in cmd  # runs to end of file


# ---------------------------------------------------------------------------
# split_title — orchestration (ffmpeg injected)
# ---------------------------------------------------------------------------


def _fake_runner_factory(out_files_created, fail_indices=()):
    """A runner that 'creates' each output file and returns rc=0,
    except for span indices in ``fail_indices`` (rc=1, no file)."""
    calls = {"n": 0}

    def run(cmd):
        calls["n"] += 1
        out_path = cmd[-1]
        # ffmpeg failure for the nth call?
        if calls["n"] in fail_indices:
            return 1
        with open(out_path, "wb") as f:
            f.write(b"x" * 2048)
        out_files_created.append(out_path)
        return 0

    return run, calls


def test_split_writes_one_file_per_span_with_names(tmp_path):
    created: list[str] = []
    run, _ = _fake_runner_factory(created)
    spans = build_episode_spans(
        [EpisodeMarker(0.0, "Pilot"), EpisodeMarker(100.0, "The Big One")],
        total_seconds=200.0,
    )
    written = split_title(
        "ffmpeg.exe", "src.mkv", spans, str(tmp_path), runner=run,
    )
    names = sorted(os.path.basename(p) for p in written)
    assert names == ["Pilot.mkv", "The Big One.mkv"]
    assert all(os.path.isfile(p) for p in written)


def test_split_uses_filename_fn_for_library_naming(tmp_path):
    created: list[str] = []
    run, _ = _fake_runner_factory(created)
    spans = build_episode_spans(
        [EpisodeMarker(0.0, "Pilot"), EpisodeMarker(100.0, "")],
        total_seconds=200.0,
    )
    # Caller injects the Jellyfin S01Exx convention.
    written = split_title(
        "ffmpeg.exe", "src.mkv", spans, str(tmp_path), runner=run,
        filename_fn=lambda s: f"3rd Rock - S01E{s.index:02d}.mkv",
    )
    assert sorted(os.path.basename(p) for p in written) == [
        "3rd Rock - S01E01.mkv", "3rd Rock - S01E02.mkv",
    ]


def test_unnamed_span_falls_back_to_episode_number(tmp_path):
    created: list[str] = []
    run, _ = _fake_runner_factory(created)
    spans = build_episode_spans([EpisodeMarker(0.0, "")], total_seconds=100.0)
    written = split_title("ffmpeg.exe", "src.mkv", spans, str(tmp_path), runner=run)
    assert os.path.basename(written[0]) == "Episode 01.mkv"


def test_one_failed_cut_does_not_sink_the_others(tmp_path):
    created: list[str] = []
    run, _ = _fake_runner_factory(created, fail_indices={2})  # 2nd cut fails
    spans = build_episode_spans(
        [EpisodeMarker(0.0, "A"), EpisodeMarker(100.0, "B"), EpisodeMarker(200.0, "C")],
        total_seconds=300.0,
    )
    written = split_title("ffmpeg.exe", "src.mkv", spans, str(tmp_path), runner=run)
    got = sorted(os.path.basename(p) for p in written)
    assert got == ["A.mkv", "C.mkv"]  # B failed, A and C still written


def test_no_ffmpeg_returns_empty(tmp_path):
    assert split_title("", "src.mkv", [EpisodeSpan(1, 0.0, 1.0, "A")], str(tmp_path)) == []


def test_bad_chars_sanitized_out_of_filename(tmp_path):
    created: list[str] = []
    run, _ = _fake_runner_factory(created)
    spans = [EpisodeSpan(1, 0.0, 100.0, 'S01E01: "Pilot" <a/b>')]
    written = split_title("ffmpeg.exe", "src.mkv", spans, str(tmp_path), runner=run)
    base = os.path.basename(written[0])
    assert not any(c in base[:-4] for c in '<>:"/\\|?*')
    assert base.endswith(".mkv")
