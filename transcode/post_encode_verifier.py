"""Post-encode output verification.

Two-step usage
--------------
*Before* the encode::

    contract = build_contract(recommendation, analysis)
    job.metadata["expected"] = contract.as_dict()

*After* the encode::

    contract = OutputContract.from_dict(job.metadata["expected"])
    result = verify_output(output_path, contract, ffprobe_exe)
    if result.outcome == VerificationOutcome.FAIL:
        mark_job_failed(job, result.errors)
    elif result.outcome == VerificationOutcome.DEGRADED:
        mark_job_degraded(job, result.warnings)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field, fields
from enum import Enum
from typing import Any, Mapping, Optional

_CODEC_NAMES: dict[str, str] = {"h265": "hevc", "h264": "h264", "av1": "av1"}
_CONTAINER_NAMES: dict[str, str] = {"mkv": "matroska", "mp4": "mp4", "mov": "mov"}
_AUDIO_CODECS: dict[str, str] = {
    "aac": "aac", "ac3": "ac3", "eac3": "eac3",
    "mp3": "mp3", "opus": "opus", "flac": "flac",
}
_DURATION_TOLERANCE = 0.01  # 1 %

# ffprobe returns format_name as a comma-separated list of format identifiers
# (e.g. "matroska,webm", "mov,mp4,m4a,3gp,3g2,mj2").  Map each canonical
# container name we care about to all identifiers that satisfy it.
_CONTAINER_EQUIV: dict[str, frozenset[str]] = {
    "matroska": frozenset({"matroska", "webm"}),
    "mp4":      frozenset({"mp4", "mov", "m4a", "3gp", "3g2", "mj2"}),
    "mov":      frozenset({"mov", "mp4", "m4a", "3gp", "3g2", "mj2"}),
}


def _container_matches(expected: str, actual_format_name: str) -> bool:
    """Return True when *actual_format_name* satisfies *expected*.

    Splits the ffprobe format_name string on commas and checks whether any
    resulting token belongs to the set of identifiers that represent the
    expected container — avoiding false positives from substring matching
    (e.g. "mov" appearing as a substring of "removed").
    """
    actual_parts = frozenset(
        p.strip().lower() for p in actual_format_name.split(",") if p.strip()
    )
    acceptable = _CONTAINER_EQUIV.get(expected.lower(), frozenset({expected.lower()}))
    return bool(actual_parts & acceptable)


def _select_primary_video(streams: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the primary video stream from *streams*, excluding cover art.

    Scoring (higher = preferred):
      1. ``disposition.default`` — streams explicitly flagged as default.
      2. Resolution (width × height) — prefer the highest-resolution stream.
      3. Bit depth inferred from ``pix_fmt`` — prefer 10-bit over 8-bit.

    Returns an empty dict when no video stream is present.
    """
    candidates = [
        s for s in streams
        if s.get("codec_type") == "video"
        and not (s.get("disposition") or {}).get("attached_pic")
    ]
    if not candidates:
        return {}
    if len(candidates) == 1:
        return candidates[0]

    def _score(s: dict[str, Any]) -> tuple[int, int, int]:
        d   = s.get("disposition") or {}
        pix = s.get("pix_fmt") or ""
        return (
            int(d.get("default") or 0),
            int(s.get("width") or 0) * int(s.get("height") or 0),
            10 if "10" in pix else 8,
        )

    return max(candidates, key=_score)


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _audio_channel_score(stream: Mapping[str, Any]) -> int:
    channels = _safe_int(stream.get("channels"))
    if channels > 0:
        return channels
    layout = str(stream.get("channel_layout") or "").lower()
    if "7.1" in layout:
        return 8
    if "6.1" in layout:
        return 7
    if "5.1" in layout:
        return 6
    if "4.0" in layout:
        return 4
    if "stereo" in layout or "2.0" in layout:
        return 2
    if "mono" in layout:
        return 1
    return 0


def _is_commentary_stream(stream: Mapping[str, Any]) -> bool:
    tags = stream.get("tags") or {}
    if not isinstance(tags, Mapping):
        tags = {}
    text = " ".join(str(value).lower() for value in tags.values())
    return "commentary" in text or "comment" in text


def _select_primary_audio(streams: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the default/best audio stream instead of assuming index 0."""
    candidates = [s for s in streams if s.get("codec_type") == "audio"]
    if not candidates:
        return {}
    if len(candidates) == 1:
        return candidates[0]

    def _score(s: dict[str, Any]) -> tuple[int, int, int, int, int]:
        disposition = s.get("disposition") or {}
        return (
            int(disposition.get("default") or 0),
            0 if _is_commentary_stream(s) else 1,
            _audio_channel_score(s),
            _safe_int(s.get("bit_rate")),
            -_safe_int(s.get("index")),
        )

    return max(candidates, key=_score)


def _height_bucket(height: int) -> str:
    if height >= 1800:
        return "4k"
    if height >= 1400:
        return "1440p"
    if height >= 1000:
        return "1080p"
    if height >= 700:
        return "720p"
    return "sd"


def _source_codec_family(codec_name: Any) -> str:
    codec = str(codec_name or "").strip().lower()
    if codec in {"hevc", "h265", "libx265", "x265"}:
        return "efficient"
    if codec in {"av1", "vp9"}:
        return "efficient"
    if codec in {"mpeg2video", "vc1", "mpeg4"}:
        return "legacy"
    if codec in {"h264", "avc1", "libx264", "x264"}:
        return "standard"
    return "unknown"


def _output_codec_factor(codec_name: Any) -> float:
    codec = str(codec_name or "").strip().lower()
    if codec in {"av1"}:
        return 0.75
    if codec in {"h264"}:
        return 1.35
    return 1.0


def _resolution_floor_bps(height_bucket: str) -> int:
    return {
        "4k": 6_000_000,
        "1440p": 3_500_000,
        "1080p": 2_000_000,
        "720p": 900_000,
        "sd": 350_000,
    }[height_bucket]


def _expected_min_bitrate_bps(
    recommendation: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> Optional[int]:
    """Resolution/codec/CRF collapse guard with source bitrate as an upper cap."""
    profile_data = recommendation.get("profile_data") or {}
    video = profile_data.get("video") or {}
    video_mode = str(video.get("mode") or "crf").strip().lower()
    if video_mode == "copy":
        return None

    codec = _CODEC_NAMES.get(str(video.get("codec") or "h265"), video.get("codec") or "h265")
    bitrate_value = video.get("bitrate")
    if video_mode == "bitrate" and isinstance(bitrate_value, (int, float)) and bitrate_value > 0:
        target_bps = int(float(bitrate_value) * 1000)
        return max(100_000, int(target_bps * 0.45))

    height = _safe_int(analysis.get("height"))
    if height <= 0:
        return None

    crf = video.get("crf", recommendation.get("crf", 20))
    try:
        crf_value = float(crf)
    except (TypeError, ValueError):
        crf_value = 20.0

    base = _resolution_floor_bps(_height_bucket(height))
    crf_scale = max(0.45, min(2.25, 2 ** ((20.0 - crf_value) / 6.0)))
    source_family = _source_codec_family(analysis.get("video_codec"))
    source_factor = {
        "efficient": 1.15,
        "legacy": 0.90,
        "standard": 1.0,
        "unknown": 1.0,
    }[source_family]
    model_floor = int(round(base * crf_scale * source_factor * _output_codec_factor(codec)))

    src_bitrate = analysis.get("bitrate_bps")
    if isinstance(src_bitrate, (int, float)) and src_bitrate > 0:
        source_cap = int(src_bitrate * 0.90)
        model_floor = min(model_floor, source_cap)

    return max(100_000, model_floor)


class VerificationOutcome(str, Enum):
    PASS     = "pass"      # all checks clean
    DEGRADED = "degraded"  # soft mismatches only — file plays, quality may vary
    FAIL     = "fail"      # hard error — file is likely broken or unusable


@dataclass
class OutputContract:
    """The serialisable expected-output contract for one encode job.

    Hard-matched fields (mismatch → FAIL):
        video_codec, color_transfer, color_primaries, colorspace,
        audio_stream_count, subtitle_mode, container_format,
        min_duration_seconds.

    Soft-matched fields (mismatch → DEGRADED):
        pix_fmt, audio_codec, max_duration_seconds.

    Build one *before* the encode with :func:`build_contract` and store it
    in ``job.metadata["expected"]``.  After the encode, restore it with
    :meth:`from_dict` and call :func:`verify_output`.
    """

    video_codec: Optional[str] = None
    """ffprobe ``codec_name`` for the primary video stream, e.g. ``"hevc"``."""

    pix_fmt: Optional[str] = None
    """Expected pixel format, e.g. ``"yuv420p10le"`` — soft match."""

    color_transfer: Optional[str] = None
    """Expected ``color_transfer`` tag, e.g. ``"smpte2084"``."""

    color_primaries: Optional[str] = None
    """Expected ``color_primaries`` tag, e.g. ``"bt2020"``."""

    colorspace: Optional[str] = None
    """Expected ``color_space`` tag (color matrix), e.g. ``"bt2020nc"``."""

    audio_codec: Optional[str] = None
    """Expected codec on audio streams.  ``None`` means copy is skipped."""

    subtitle_mode: str = "none"
    """``"burned"`` → no sub streams expected; ``"copy"`` → streams expected;
    ``"none"`` → no sub streams, but only a warning if found."""

    audio_stream_count: Optional[int] = None
    """Expected number of audio streams."""

    container_format: Optional[str] = None
    """Substring that must appear in ffprobe ``format_name``, e.g. ``"matroska"``."""

    min_duration_seconds: Optional[float] = None
    max_duration_seconds: Optional[float] = None

    min_bitrate_bps: Optional[int] = None
    """Expected minimum output bitrate in bits/s.
    Resolution/codec/CRF-based catastrophic-collapse guard."""

    audio_layout: Optional[str] = None
    """Expected channel layout for the default/primary audio stream."""

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict suitable for job metadata storage."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> OutputContract:
        """Restore a contract that was serialised with :meth:`as_dict`."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class VerificationResult:
    """Outcome of comparing ffprobe output against an :class:`OutputContract`."""

    outcome: VerificationOutcome
    errors: list[str] = field(default_factory=list)
    """Hard failures — the encode is likely broken."""

    warnings: list[str] = field(default_factory=list)
    """Soft concerns — the file plays but quality may not match the recommendation."""

    actual: dict[str, Any] = field(default_factory=dict)
    """A summary of what ffprobe actually found."""

    @property
    def passed(self) -> bool:
        """True when outcome is PASS or DEGRADED (not FAIL)."""
        return self.outcome != VerificationOutcome.FAIL


def build_contract(
    recommendation: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> OutputContract:
    """Derive the expected output contract from a recommendation + source analysis.

    Call this *before* the encode starts.  Store the result in
    ``job.metadata["expected"]`` via :meth:`OutputContract.as_dict`.
    """
    profile_data = recommendation.get("profile_data") or {}
    video     = profile_data.get("video")     or {}
    audio     = profile_data.get("audio")     or {}
    subtitles = profile_data.get("subtitles") or {}
    output    = profile_data.get("output")    or {}

    codec = video.get("codec", "h265")
    video_codec: Optional[str] = _CODEC_NAMES.get(codec, codec)

    # Parse all color metadata from x265-params / extra_video_params at once.
    extra: str = video.get("extra_video_params") or ""
    kv = dict(p.split("=", 1) for p in extra.split(":") if "=" in p)
    color_transfer: Optional[str]  = kv.get("transfer")
    color_primaries: Optional[str] = kv.get("colorprim")
    colorspace: Optional[str]      = kv.get("colormatrix")

    container = output.get("container", "mkv")
    container_format: Optional[str] = _CONTAINER_NAMES.get(str(container))

    # Duration bounds (1 % tolerance).
    dur = analysis.get("duration_seconds")
    min_dur: Optional[float] = None
    max_dur: Optional[float] = None
    if isinstance(dur, (int, float)) and dur > 0:
        min_dur = dur * (1.0 - _DURATION_TOLERANCE)
        max_dur = dur * (1.0 + _DURATION_TOLERANCE)

    # Audio stream count: only predictable when copying all tracks.
    # analysis["audio_streams"] may be an int (count) or a list (stream dicts).
    audio_mode: str = audio.get("mode") or "copy"
    audio_count: Optional[int] = None
    if audio_mode == "copy" and audio.get("tracks") in (None, "", "all"):
        src = analysis.get("audio_streams")
        if isinstance(src, int) and src > 0:
            audio_count = src
        elif isinstance(src, (list, tuple)) and src:
            audio_count = len(src)

    # Audio codec: only when transcoding (copy = unpredictable, skip check).
    audio_codec: Optional[str] = _AUDIO_CODECS.get(audio_mode)

    # Subtitle mode.
    if subtitles.get("burn", False):
        subtitle_mode = "burned"
    elif (subtitles.get("mode") or "all") == "none":
        subtitle_mode = "none"
    else:
        subtitle_mode = "copy"

    # Minimum output bitrate: resolution/codec/CRF catastrophic-collapse guard.
    min_bitrate = _expected_min_bitrate_bps(recommendation, analysis)

    # Audio channel layout: carry through the default/primary source stream.
    audio_layout: Optional[str] = None
    src_audio = analysis.get("audio_streams")
    if isinstance(src_audio, list):
        primary_audio = _select_primary_audio(src_audio)
        raw_layout = primary_audio.get("channel_layout")
        if not raw_layout:
            raw_layout = analysis.get("audio_channel_layout")
    else:
        raw_layout = analysis.get("audio_channel_layout")
    if isinstance(raw_layout, str) and raw_layout.strip():
        audio_layout = raw_layout.strip()

    return OutputContract(
        video_codec=video_codec,
        pix_fmt=video.get("pix_fmt") or None,
        color_transfer=color_transfer,
        color_primaries=color_primaries,
        colorspace=colorspace,
        audio_codec=audio_codec,
        subtitle_mode=subtitle_mode,
        audio_stream_count=audio_count,
        container_format=container_format,
        min_duration_seconds=min_dur,
        max_duration_seconds=max_dur,
        min_bitrate_bps=min_bitrate,
        audio_layout=audio_layout,
    )


def verify_output(
    output_path: str,
    contract: OutputContract,
    ffprobe_exe: str = "ffprobe",
) -> VerificationResult:
    """Run ffprobe on *output_path* and diff it against *contract*.

    Hard mismatches populate ``errors`` and set ``outcome=FAIL``.
    Soft mismatches populate ``warnings`` and set ``outcome=DEGRADED``.
    A clean result sets ``outcome=PASS``.
    """
    try:
        proc = subprocess.run(
            [
                ffprobe_exe, "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                output_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        return VerificationResult(
            outcome=VerificationOutcome.FAIL,
            errors=[f"ffprobe failed: {exc}"],
        )

    if proc.returncode != 0:
        return VerificationResult(
            outcome=VerificationOutcome.FAIL,
            errors=[f"ffprobe exited with code {proc.returncode}."],
        )

    try:
        probe = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return VerificationResult(
            outcome=VerificationOutcome.FAIL,
            errors=[f"Could not parse ffprobe output: {exc}"],
        )

    errors:   list[str] = []
    warnings: list[str] = []

    streams = probe.get("streams") or []
    fmt     = probe.get("format")  or {}

    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    primary_audio = _select_primary_audio(streams)
    sub_streams   = [s for s in streams if s.get("codec_type") == "subtitle"]

    # Use scored selection rather than "first stream wins".  Attached pictures
    # (cover art stored as a video stream) are excluded from consideration.
    vs: dict[str, Any] = _select_primary_video(streams)

    # ── Hard matches ─────────────────────────────────────────────────────────

    if contract.video_codec:
        if not vs:
            errors.append("No video stream found in output.")
        elif vs.get("codec_name") != contract.video_codec:
            errors.append(
                f"Video codec mismatch: expected '{contract.video_codec}', "
                f"got '{vs.get('codec_name', '')}'."
            )

    if contract.color_transfer and vs:
        actual = vs.get("color_transfer", "")
        if actual != contract.color_transfer:
            errors.append(
                f"HDR transfer mismatch: expected '{contract.color_transfer}', "
                f"got '{actual or '(not set)'}'. "
                f"HDR playback will look washed out."
            )

    if contract.color_primaries and vs:
        actual = vs.get("color_primaries", "")
        if actual != contract.color_primaries:
            errors.append(
                f"Color primaries mismatch: expected '{contract.color_primaries}', "
                f"got '{actual or '(not set)'}'."
            )

    if contract.colorspace and vs:
        actual = vs.get("color_space", "")
        if actual != contract.colorspace:
            errors.append(
                f"Color space mismatch: expected '{contract.colorspace}', "
                f"got '{actual or '(not set)'}'."
            )

    if contract.audio_stream_count is not None:
        n = len(audio_streams)
        if n != contract.audio_stream_count:
            errors.append(
                f"Audio stream count mismatch: expected "
                f"{contract.audio_stream_count}, got {n}."
            )

    if contract.subtitle_mode == "burned" and sub_streams:
        errors.append(
            f"Expected no subtitle streams (burned into video), "
            f"but found {len(sub_streams)}."
        )
    elif contract.subtitle_mode == "copy" and not sub_streams:
        # Soft: subtitles may have been absent in the source.
        warnings.append(
            "Subtitle mode is 'copy' but no subtitle streams found in output."
        )
    elif contract.subtitle_mode == "none" and sub_streams:
        warnings.append(
            f"Subtitle mode is 'none' but {len(sub_streams)} subtitle "
            f"stream(s) found in output."
        )

    if contract.container_format:
        actual = fmt.get("format_name", "")
        if not _container_matches(contract.container_format, actual):
            errors.append(
                f"Container mismatch: expected '{contract.container_format}', "
                f"got '{actual}'."
            )

    actual_dur: Optional[float] = None
    try:
        raw = fmt.get("duration")
        if raw is not None:
            actual_dur = float(raw) or None
    except (ValueError, TypeError):
        pass

    if actual_dur is not None and contract.min_duration_seconds is not None:
        if actual_dur < contract.min_duration_seconds:
            errors.append(
                f"Output shorter than source by >{_DURATION_TOLERANCE:.0%}: "
                f"expected ≥ {contract.min_duration_seconds:.1f}s, "
                f"got {actual_dur:.1f}s. Possible truncation."
            )

    actual_bitrate: int = 0
    try:
        raw_bps = fmt.get("bit_rate")
        if raw_bps is not None:
            actual_bitrate = int(raw_bps)
    except (ValueError, TypeError):
        pass

    if contract.min_bitrate_bps is not None and actual_bitrate > 0:
        if actual_bitrate < contract.min_bitrate_bps:
            errors.append(
                f"Bitrate collapse: output {actual_bitrate:,} bps is below minimum "
                f"{contract.min_bitrate_bps:,} bps "
                f"({actual_bitrate * 100 // contract.min_bitrate_bps}% of floor). "
                f"Encode may be severely over-compressed."
            )

    if contract.audio_layout and primary_audio:
        actual_layout = primary_audio.get("channel_layout", "")
        if actual_layout != contract.audio_layout:
            errors.append(
                f"Audio layout mismatch: expected '{contract.audio_layout}', "
                f"got '{actual_layout or '(not set)'}'."
            )

    # ── Soft matches ─────────────────────────────────────────────────────────

    if contract.pix_fmt and vs:
        if vs.get("pix_fmt") != contract.pix_fmt:
            warnings.append(
                f"Pixel format mismatch: expected '{contract.pix_fmt}', "
                f"got '{vs.get('pix_fmt', '')}'."
            )

    if contract.audio_codec and audio_streams:
        # Check every transcoded track, not just the first.  Mixed-codec output
        # (e.g. AAC + AC3 when all should be AAC) indicates a mux or filter error.
        mismatches = [
            s.get("codec_name", "?")
            for s in audio_streams
            if s.get("codec_name") != contract.audio_codec
        ]
        if mismatches:
            unexpected = sorted(set(mismatches))
            warnings.append(
                f"Audio codec mismatch: expected '{contract.audio_codec}' on all "
                f"tracks, found {unexpected} on {len(mismatches)} track(s)."
            )

    if actual_dur is not None and contract.max_duration_seconds is not None:
        if actual_dur > contract.max_duration_seconds:
            warnings.append(
                f"Output duration ({actual_dur:.1f}s) exceeds source by "
                f">{_DURATION_TOLERANCE:.0%}."
            )

    actual_summary: dict[str, Any] = {
        "video_codec":      vs.get("codec_name"),
        "pix_fmt":          vs.get("pix_fmt"),
        "color_transfer":   vs.get("color_transfer"),
        "color_primaries":  vs.get("color_primaries"),
        "colorspace":       vs.get("color_space"),
        "audio_streams":    len(audio_streams),
        "subtitle_streams": len(sub_streams),
        "container":        fmt.get("format_name"),
        "duration_seconds": actual_dur,
        "bitrate_bps":      actual_bitrate or None,
        "audio_layout":     primary_audio.get("channel_layout") if primary_audio else None,
    }
    if primary_audio:
        actual_summary["audio_codec"] = primary_audio.get("codec_name")

    outcome = (
        VerificationOutcome.FAIL     if errors   else
        VerificationOutcome.DEGRADED if warnings else
        VerificationOutcome.PASS
    )
    return VerificationResult(
        outcome=outcome,
        errors=errors,
        warnings=warnings,
        actual=actual_summary,
    )


def contract_diff(
    contract: OutputContract,
    actual: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return ``{field: {"expected": X, "actual": Y}}`` for mismatched fields.

    Only contract fields that are explicitly set (not ``None``) and differ from
    the corresponding value in *actual* are included.  Suitable for embedding
    in fallback job metadata or emitting human-readable before/after context.
    """
    diff: dict[str, dict[str, Any]] = {}

    def _check(field: str, expected: Any, actual_val: Any) -> None:
        if expected is not None and actual_val != expected:
            diff[field] = {"expected": expected, "actual": actual_val}

    _check("video_codec",    contract.video_codec,    actual.get("video_codec"))
    _check("pix_fmt",        contract.pix_fmt,        actual.get("pix_fmt"))
    _check("color_transfer", contract.color_transfer, actual.get("color_transfer"))
    _check("color_primaries",contract.color_primaries,actual.get("color_primaries"))
    _check("colorspace",     contract.colorspace,     actual.get("colorspace"))
    _check("audio_codec",    contract.audio_codec,    actual.get("audio_codec"))
    _check("audio_layout",   contract.audio_layout,   actual.get("audio_layout"))

    if (
        contract.audio_stream_count is not None
        and actual.get("audio_streams") != contract.audio_stream_count
    ):
        diff["audio_stream_count"] = {
            "expected": contract.audio_stream_count,
            "actual": actual.get("audio_streams"),
        }

    dur = actual.get("duration_seconds")
    if dur is not None:
        if (
            contract.min_duration_seconds is not None
            and dur < contract.min_duration_seconds
        ):
            diff["duration_seconds"] = {
                "expected": f">={contract.min_duration_seconds:.1f}s",
                "actual": f"{dur:.1f}s",
            }
        elif (
            contract.max_duration_seconds is not None
            and dur > contract.max_duration_seconds
        ):
            diff["duration_seconds"] = {
                "expected": f"<={contract.max_duration_seconds:.1f}s",
                "actual": f"{dur:.1f}s",
            }

    bps = actual.get("bitrate_bps")
    if (
        bps is not None
        and contract.min_bitrate_bps is not None
        and bps < contract.min_bitrate_bps
    ):
        diff["bitrate_bps"] = {
            "expected": f">={contract.min_bitrate_bps:,}",
            "actual": bps,
        }

    return diff
