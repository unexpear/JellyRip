from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass
class ValidationResult:
    """Structured result of an FFmpeg command validation check."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when there are no errors (warnings are non-blocking)."""
        return not self.errors

    def __bool__(self) -> bool:
        return self.ok


def _flag_values(args: list[str], flag: str) -> list[str]:
    """Return every value that immediately follows *flag* in *args*."""
    return [
        args[i + 1]
        for i, arg in enumerate(args)
        if arg == flag and i + 1 < len(args)
    ]


def _has_flag(args: list[str], flag: str) -> bool:
    return flag in args


def _stream_type(map_value: str) -> str:
    """Return the stream-type letter from a map specifier like '0:a:0' → 'a'."""
    parts = map_value.lstrip("-").split(":")
    return parts[1] if len(parts) > 1 else ""


def _is_specific_map(map_value: str) -> bool:
    """True when the map selects a particular stream, not just a stream type.

    '0:a'   → False  (all audio — type-level, not a conflict with -map 0)
    '0:a:0' → True   (first audio — specific stream)
    '0:a:m:language:eng' → True
    '0:s:m:forced'  → True
    """
    if not map_value.startswith("0:"):
        return False
    return len(map_value.split(":")) > 2


def validate_ffmpeg_command(
    cmd: Sequence[str],
    ffmpeg_exe: Optional[str] = None,
) -> ValidationResult:
    """Check a built FFmpeg command for common structural problems.

    Parameters
    ----------
    cmd:
        The complete FFmpeg command as a sequence of strings.
    ffmpeg_exe:
        When provided, the validator probes the binary with
        ``ffmpeg -encoders`` and reports an error if the video encoder
        named in the command is not available on this machine.  Results
        are cached so the probe only runs once per executable path.

    Checks
    ------
    1.  ``-map 0`` plus specific stream maps without a negative map first
        → creates duplicate streams in the output.
    2.  Subtitle burn ``-filter_complex`` overlay plus ``-c:s``
        → burned subtitles produce no subtitle stream; ``-c:s`` is contradictory.
    3.  GPU encoder (nvenc/qsv/amf) with ``-x265-params``
        → x265-params are silently ignored by hardware encoders.
    4.  ``-crf`` with ``-c:v copy``
        → quality targeting is meaningless during stream copy.
    5.  ``-pix_fmt`` with ``-c:v copy``
        → pixel format conversion requires re-encoding.
    6.  Non-mov_text subtitle copy into MP4
        → MP4 only supports mov_text (tx3g).
    7.  ``libopus`` audio in MP4
        → not supported in ISO Base Media containers; will fail at mux.
    8.  Missing ``-i`` input flag.
    9.  (optional) Video encoder not available in this FFmpeg build.
    """
    result = ValidationResult()
    args = list(cmd)

    if not args:
        result.errors.append("Command is empty.")
        return result

    # ── Derived values ────────────────────────────────────────────────────────
    maps = _flag_values(args, "-map")
    vcodec = (_flag_values(args, "-c:v") or [""])[0]
    audio_codecs = _flag_values(args, "-c:a")
    subtitle_codecs = _flag_values(args, "-c:s")
    filter_complex_values = _flag_values(args, "-filter_complex")
    has_subtitle_overlay = any("overlay" in v for v in filter_complex_values)
    output_path = args[-1] if args else ""

    # ── Check 1: -map 0 + specific stream maps without negative cancellation ──
    if "0" in maps:
        # Collect stream types that have been negated (e.g. -0:a → "a")
        negated: set[str] = set()
        for m in maps:
            if m.startswith("-0:"):
                t = _stream_type(m)
                if t:
                    negated.add(t)

        conflicting = [
            m for m in maps
            if _is_specific_map(m) and _stream_type(m) not in negated
        ]
        if conflicting:
            result.errors.append(
                f"-map 0 already selects all streams; the additional specific "
                f"map(s) {conflicting} duplicate streams already included. "
                f"Use a negative map first (e.g. -map -0:a) to remove the "
                f"broad selection, then re-add the specific stream."
            )

    # ── Check 2: subtitle burn + -c:s ────────────────────────────────────────
    if has_subtitle_overlay and subtitle_codecs:
        result.errors.append(
            "-c:s is set alongside a subtitle burn-in (filter_complex overlay). "
            "Burned subtitles produce no output subtitle stream — remove -c:s."
        )

    # ── Check 3: GPU encoder + -x265-params ──────────────────────────────────
    _GPU = {"h264_nvenc", "hevc_nvenc", "h264_qsv", "hevc_qsv", "h264_amf", "hevc_amf"}
    if vcodec in _GPU and _has_flag(args, "-x265-params"):
        result.warnings.append(
            f"-x265-params has no effect with {vcodec}. "
            "HDR color metadata in that field will be silently ignored by "
            "the hardware encoder."
        )

    # ── Check 4: -crf with copy ───────────────────────────────────────────────
    if _has_flag(args, "-crf") and vcodec == "copy":
        result.errors.append(
            "-crf cannot be used when video codec is copy. "
            "Remove -crf or change the video codec to a real encoder."
        )

    # ── Check 5: -pix_fmt with copy ───────────────────────────────────────────
    if _has_flag(args, "-pix_fmt") and vcodec == "copy":
        result.warnings.append(
            "-pix_fmt is ignored when video codec is copy. "
            "Re-encoding is required to change the pixel format."
        )

    # ── Check 6: subtitle copy in MP4 ────────────────────────────────────────
    if output_path.lower().endswith(".mp4") and subtitle_codecs:
        result.warnings.append(
            "MP4 containers only support mov_text (tx3g) subtitles. "
            "Copying PGS, ASS, or SRT streams into MP4 will likely fail "
            "at the muxing stage."
        )

    # ── Check 7: libopus in MP4 ──────────────────────────────────────────────
    # This is an error, not a warning: libopus is not part of the ISO Base
    # Media spec and FFmpeg will typically fail at the mux stage.  Users who
    # hit this will produce a broken file, not just a suboptimal one.
    if "libopus" in audio_codecs and output_path.lower().endswith(".mp4"):
        result.errors.append(
            "libopus audio cannot be stored in an MP4 container. "
            "Use AAC or AC3 for MP4, or switch the container to MKV."
        )

    # ── Check 8: missing -i ──────────────────────────────────────────────────
    if not _has_flag(args, "-i"):
        result.errors.append("Command has no input file (-i is missing).")

    # ── Check 9 (optional): encoder availability ─────────────────────────────
    if ffmpeg_exe and vcodec and vcodec not in ("copy", ""):
        from transcode.encoder_probe import available_encoders
        known = available_encoders(ffmpeg_exe)
        if known and vcodec not in known:
            result.errors.append(
                f"Encoder '{vcodec}' is not available in this FFmpeg build. "
                f"Run 'ffmpeg -encoders' to see what is supported."
            )

    return result
