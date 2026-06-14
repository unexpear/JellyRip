"""Split one multi-episode title into separate, named episode files.

The "watch and mark episodes" flow (2026-06-13): some TV discs put
several episodes in a single "Play All" title.  The user watches that
title in the app's own player and drops a marker at the start of each
episode (with a name); this module turns those markers into episode
spans and cuts the title into one file per episode.

Cutting is **lossless stream-copy** (``-c copy``): no re-encode, so it's
near-instant and bit-for-bit identical to the source.  The cost is that
copy cuts can only land on a keyframe, so an episode may begin up to a
GOP (~a second or two) before the exact marker — fine for episode
boundaries, which sit on hard scene cuts.  Frame-exact cuts would need a
re-encode (slow + lossy) and are intentionally not done here.

Pure, Qt-free, and (apart from the ffmpeg subprocess) hermetic:
``build_episode_spans`` is pure and fully unit-tested; ``split_title``
takes the ffmpeg path + a runner so tests can drive it without ffmpeg.

Note: title-to-title boundaries on a multi-title disc are already
separate files — this module is only for the *within-a-title* case.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Sequence

# Suppress the black console flash when spawning ffmpeg on Windows.
_POPEN_FLAGS = {"creationflags": 0x08000000} if sys.platform == "win32" else {}

# Characters Windows forbids in a filename, plus control chars.
_BAD_FILENAME_CHARS = '<>:"/\\|?*'


@dataclass(frozen=True)
class EpisodeMarker:
    """A user-dropped marker: an episode STARTS at ``start_seconds`` and
    is called ``name`` (which may be empty — the caller then falls back
    to a positional ``Episode N``)."""

    start_seconds: float
    name: str = ""


@dataclass(frozen=True)
class EpisodeSpan:
    """A resolved, cuttable episode: ``[start_seconds, end_seconds)``.
    ``end_seconds`` is ``None`` for the final span (runs to end of
    file).  ``index`` is 1-based within the title."""

    index: int
    start_seconds: float
    end_seconds: float | None
    name: str


def _safe_filename(name: str) -> str:
    """Strip characters Windows can't put in a filename; collapse
    whitespace; never return empty."""
    cleaned = "".join(
        (" " if ch in _BAD_FILENAME_CHARS or ord(ch) < 32 else ch)
        for ch in str(name or "")
    )
    cleaned = " ".join(cleaned.split()).strip(" .")
    return cleaned or "Episode"


def build_episode_spans(
    markers: Sequence[EpisodeMarker],
    total_seconds: float | None,
) -> list[EpisodeSpan]:
    """Turn episode-start markers into ordered, non-overlapping spans.

    Each marker is the START of an episode; an episode runs until the
    next marker's start, and the last runs to ``total_seconds`` (or
    open-ended when the duration is unknown / ``None``).  Markers are
    sorted by time, so the UI can collect them in any order.

    Any region BEFORE the first marker (e.g. a disc logo / pre-roll) is
    intentionally dropped — start a marker at 0:00 to keep it.  Markers
    that collapse to a zero/negative-length span (two at the same time,
    or one at/after the end) are skipped.
    """
    ordered = sorted(markers, key=lambda m: max(0.0, float(m.start_seconds)))
    spans: list[EpisodeSpan] = []
    for i, marker in enumerate(ordered):
        start = max(0.0, float(marker.start_seconds))
        if i + 1 < len(ordered):
            end: float | None = max(0.0, float(ordered[i + 1].start_seconds))
        else:
            end = float(total_seconds) if total_seconds else None
        if end is not None and end <= start:
            continue  # zero/negative length — skip
        spans.append(
            EpisodeSpan(
                index=len(spans) + 1,
                start_seconds=start,
                end_seconds=end,
                name=str(marker.name or "").strip(),
            )
        )
    return spans


def _default_filename(span: EpisodeSpan, ext: str) -> str:
    base = _safe_filename(span.name) if span.name else f"Episode {span.index:02d}"
    return base + ext


def build_split_command(
    ffmpeg_exe: str,
    src_path: str,
    span: EpisodeSpan,
    out_path: str,
) -> list[str]:
    """Build the ffmpeg argv for one lossless episode cut.

    Input seeking (``-ss`` before ``-i``) is fast; ``-t`` (duration)
    rather than ``-to`` avoids ffmpeg's "is -to relative to the seek or
    the file" ambiguity.  ``-map 0`` keeps every stream (all audio /
    subtitle tracks); ``-avoid_negative_ts make_zero`` rebases
    timestamps so the cut file starts cleanly at 0.
    """
    cmd = [ffmpeg_exe, "-nostdin", "-y"]
    if span.start_seconds > 0:
        cmd += ["-ss", f"{span.start_seconds:.3f}"]
    cmd += ["-i", src_path]
    if span.end_seconds is not None:
        duration = max(0.0, span.end_seconds - span.start_seconds)
        cmd += ["-t", f"{duration:.3f}"]
    cmd += ["-map", "0", "-c", "copy", "-avoid_negative_ts", "make_zero", out_path]
    return cmd


def split_title(
    ffmpeg_exe: str,
    src_path: str,
    spans: Sequence[EpisodeSpan],
    out_dir: str,
    on_log: Callable[[str], None] | None = None,
    *,
    ext: str = ".mkv",
    filename_fn: Callable[[EpisodeSpan], str] | None = None,
    runner: Callable[[list[str]], int] | None = None,
) -> list[str]:
    """Cut ``src_path`` into one file per span under ``out_dir``.

    ``filename_fn(span)`` names each output (defaults to the marker name
    or ``Episode NN``); the library naming convention is injected by the
    caller through it.  ``runner(cmd)->returncode`` is injected by tests;
    in production it runs ffmpeg.  Returns the list of files that were
    written.  A failed cut is logged and skipped — the others still run.
    """
    def _log(msg: str) -> None:
        if on_log:
            on_log(msg)

    if not ffmpeg_exe:
        _log("Episode split: no ffmpeg available — cannot split.")
        return []
    if not spans:
        _log("Episode split: no episode markers — nothing to split.")
        return []

    os.makedirs(out_dir, exist_ok=True)
    run = runner if runner is not None else _run_ffmpeg
    written: list[str] = []
    for span in spans:
        name = (filename_fn(span) if filename_fn else _default_filename(span, ext))
        out_path = os.path.join(out_dir, name)
        cmd = build_split_command(ffmpeg_exe, src_path, out_path=out_path, span=span)
        label = span.name or f"Episode {span.index:02d}"
        _log(f"Episode split: cutting {label} -> {os.path.basename(out_path)}")
        try:
            rc = run(cmd)
        except Exception as exc:  # noqa: BLE001 — one bad cut mustn't abort the rest
            _log(f"Episode split: {label} failed ({exc.__class__.__name__}).")
            continue
        if rc == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            written.append(out_path)
        else:
            _log(f"Episode split: {label} produced no file (ffmpeg rc={rc}).")
    _log(f"Episode split: wrote {len(written)} of {len(spans)} episode(s).")
    return written


def _run_ffmpeg(cmd: list[str]) -> int:
    """Run ffmpeg quietly, return its exit code."""
    proc = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        **_POPEN_FLAGS,
    )
    return proc.returncode
