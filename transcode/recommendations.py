from __future__ import annotations

import json
import os
import subprocess
from typing import Any, NotRequired, TypedDict


class MediaAnalysis(TypedDict):
    path: str
    name: str
    size_bytes: int
    duration_seconds: float
    bitrate_bps: int
    video_codec: str
    width: int
    height: int
    pix_fmt: str
    fps: float
    audio_streams: int
    subtitle_streams: int
    profile: NotRequired[str]
    bit_depth: NotRequired[int]
    color_transfer: NotRequired[str]
    color_primaries: NotRequired[str]
    color_space: NotRequired[str]
    audio_channel_layout: NotRequired[str]
    """Channel layout of the default/primary audio stream."""


class FFmpegRecommendation(TypedDict):
    id: str
    label: str
    summary: str
    details: str
    why: str
    best_for: str
    caution: str
    expected_result: str
    crf: int
    preset: str
    profile_name: str
    profile_data: dict[str, Any]


class RecommendationResult(TypedDict):
    recommended_id: str
    recommendation_reason: str
    advisory: str
    source_notes: list[str]
    decision_factors: list[str]
    recommendations: list[FFmpegRecommendation]


def _safe_int(value: Any) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def _parse_frame_rate(value: Any) -> float:
    token = str(value or "").strip()
    if not token:
        return 0.0
    if "/" in token:
        left, right = token.split("/", 1)
        numerator = _safe_float(left)
        denominator = _safe_float(right)
        if denominator > 0:
            return numerator / denominator
        return 0.0
    return _safe_float(token)


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _safe_text(value).lower()


def _height_bucket(height: int) -> str:
    if height >= 1800:
        return "4k"
    if height >= 1000:
        return "1080p"
    if height >= 700:
        return "720p"
    return "sd"


def _crf_table(height_bucket: str) -> dict[str, int]:
    if height_bucket == "4k":
        return {"higher_quality": 18, "balanced": 20, "smaller_file": 22}
    if height_bucket == "1080p":
        return {"higher_quality": 18, "balanced": 20, "smaller_file": 23}
    if height_bucket == "720p":
        return {"higher_quality": 19, "balanced": 21, "smaller_file": 23}
    return {"higher_quality": 18, "balanced": 20, "smaller_file": 22}


def _bitrate_budget_mbps(height_bucket: str, *, hdr: bool = False) -> float:
    if height_bucket == "4k":
        return 24.0 if hdr else 18.0
    if height_bucket == "1080p":
        return 10.0 if hdr else 8.0
    if height_bucket == "720p":
        return 4.0
    return 2.5


def _source_codec_family(codec_name: str) -> str:
    codec = str(codec_name or "").strip().lower()
    if codec in {"hevc", "h265", "libx265"}:
        return "hevc"
    if codec in {"h264", "avc1", "libx264"}:
        return "h264"
    if codec in {"mpeg2video", "vc1", "mpeg4"}:
        return "legacy"
    if codec in {"av1", "vp9"}:
        return "modern"
    return codec or "unknown"


def _audio_channel_score(stream: dict[str, Any]) -> int:
    channels = _safe_int(stream.get("channels"))
    if channels > 0:
        return channels
    layout = _safe_lower(stream.get("channel_layout"))
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


def _is_commentary_audio(stream: dict[str, Any]) -> bool:
    tags = stream.get("tags") or {}
    if not isinstance(tags, dict):
        tags = {}
    text = " ".join(str(value).lower() for value in tags.values())
    return "commentary" in text or "comment" in text


def _select_primary_audio(streams: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        stream for stream in streams
        if _safe_lower(stream.get("codec_type")) == "audio"
    ]
    if not candidates:
        return {}
    if len(candidates) == 1:
        return candidates[0]

    def _score(stream: dict[str, Any]) -> tuple[int, int, int, int, int]:
        disposition = stream.get("disposition") or {}
        if not isinstance(disposition, dict):
            disposition = {}
        return (
            int(disposition.get("default") or 0),
            0 if _is_commentary_audio(stream) else 1,
            _audio_channel_score(stream),
            _safe_int(stream.get("bit_rate")),
            -_safe_int(stream.get("index")),
        )

    return max(candidates, key=_score)


def _infer_bit_depth(video_stream: dict[str, Any], pix_fmt: str) -> int:
    explicit_depth = _safe_int(
        video_stream.get("bits_per_raw_sample") or video_stream.get("bits_per_sample")
    )
    if explicit_depth > 0:
        return explicit_depth
    normalized_fmt = _safe_lower(pix_fmt)
    if "12" in normalized_fmt:
        return 12
    if "10" in normalized_fmt:
        return 10
    if normalized_fmt:
        return 8
    return 0


def _analysis_int(analysis: MediaAnalysis, key: str) -> int:
    return _safe_int(analysis.get(key, 0))


def _analysis_text(analysis: MediaAnalysis, key: str) -> str:
    return _safe_lower(analysis.get(key, ""))


def _hdr_class(analysis: MediaAnalysis | None) -> str:
    """Classify the source HDR type.

    Returns one of:
      'hdr10'      — PQ transfer (smpte2084), or BT.2020 without explicit transfer
      'hlg'        — HLG transfer (arib-std-b67)
      'bt2020_sdr' — BT.2020 primaries/colorspace but no recognised HDR transfer
      'sdr'        — everything else
    """
    if analysis is None:
        return "sdr"
    transfer = _analysis_text(analysis, "color_transfer")
    primaries = _analysis_text(analysis, "color_primaries")
    color_space = _analysis_text(analysis, "color_space")
    if transfer == "smpte2084":
        return "hdr10"
    if transfer == "arib-std-b67":
        return "hlg"
    if primaries == "bt2020" or color_space in {"bt2020nc", "bt2020c"}:
        return "bt2020_sdr"
    return "sdr"


def _is_hdr(analysis: MediaAnalysis) -> bool:
    return _hdr_class(analysis) in {"hdr10", "hlg", "bt2020_sdr"}


def _format_mbps(value: float) -> str:
    if value <= 0:
        return "unknown bitrate"
    return f"{value:.2f} Mbps"


def _format_gb(value: float) -> str:
    if value <= 0:
        return "unknown size"
    return f"{value:.2f} GB"


def _source_notes(
    *,
    analysis: MediaAnalysis,
    codec_family: str,
    height_bucket: str,
    bitrate_mbps: float,
    budget_mbps: float,
    hdr: bool,
) -> list[str]:
    notes: list[str] = []
    codec_name = analysis["video_codec"] or "unknown codec"
    if codec_family in {"hevc", "modern"}:
        notes.append(f"Source codec is already efficient ({codec_name}).")
    elif codec_family in {"h264", "legacy"}:
        notes.append(f"Source codec is a better H.265 candidate ({codec_name}).")
    else:
        notes.append(f"Source codec is {codec_name}; recommendation confidence is lower.")

    if bitrate_mbps > 0 and budget_mbps > 0:
        ratio = bitrate_mbps / budget_mbps
        if ratio >= 2.5:
            notes.append("Bitrate is very high for this resolution, so size savings are likely.")
        elif ratio >= 1.35:
            notes.append("Bitrate is above the conservative target, so savings are possible.")
        else:
            notes.append("Bitrate is already modest, so big savings are not guaranteed.")

    if height_bucket == "4k":
        notes.append("4K sources need a more conservative first pass than 1080p.")
    if hdr:
        notes.append("HDR or BT.2020 metadata was detected; compare a short sample before a full run.")
    return notes


def _source_bit_depth(analysis: "MediaAnalysis | None") -> int:
    """Return the source bit depth, checking explicit field then inferring from pix_fmt."""
    if analysis is None:
        return 0
    explicit = _safe_int(analysis.get("bit_depth", 0))
    if explicit > 0:
        return explicit
    pix_fmt = _safe_lower(analysis.get("pix_fmt", ""))
    if "12" in pix_fmt:
        return 12
    if "10" in pix_fmt:
        return 10
    if pix_fmt:
        return 8
    return 0


def _build_profile_data(
    *,
    crf: int,
    preset: str,
    profile_label: str,
    analysis: MediaAnalysis | None = None,
) -> dict[str, Any]:
    bit_depth = _source_bit_depth(analysis)
    hdr_type = _hdr_class(analysis)
    is_hdr = hdr_type in {"hdr10", "hlg", "bt2020_sdr"}

    # Pixel format and encoder profile
    if bit_depth >= 10 or is_hdr:
        pix_fmt: str | None = "yuv420p10le"
        video_profile: str | None = "main10"
    elif bit_depth > 0:
        pix_fmt = "yuv420p"
        video_profile = "main"
    else:
        # Bit depth genuinely unknown — let ffmpeg decide
        pix_fmt = None
        video_profile = None

    # x265 color metadata (libx265 only; GPU encoders need different flags).
    # bt2020_sdr is 10-bit BT.2020 without a recognised HDR transfer function —
    # carry the pixel depth but don't assert a specific HDR transfer curve.
    if analysis is not None and hdr_type in {"hdr10", "hlg"}:
        cs = _analysis_text(analysis, "color_space")
        colormatrix = "bt2020c" if cs == "bt2020c" else "bt2020nc"
        if hdr_type == "hdr10":
            extra_video_params: str | None = (
                f"colorprim=bt2020:transfer=smpte2084"
                f":colormatrix={colormatrix}:hdr-opt=1"
            )
        else:  # hlg
            extra_video_params = (
                f"colorprim=bt2020:transfer=arib-std-b67:colormatrix={colormatrix}"
            )
    else:
        extra_video_params = None

    return {
        "video": {
            "codec": "h265",
            "mode": "crf",
            "crf": crf,
            "bitrate": None,
            "preset": preset,
            "hw_accel": "cpu",
            "tune": None,
            "video_profile": video_profile,
            "pix_fmt": pix_fmt,
            "keyint": None,
            "bframes": None,
            "refs": None,
            "extra_video_params": extra_video_params,
        },
        "audio": {
            "mode": "copy",
            "language": None,
            "tracks": "all",
            "bitrate": None,
            "channels": None,
            "sample_rate": None,
            "downmix": False,
        },
        "subtitles": {
            "mode": "all",
            "burn": False,
            "language": None,
        },
        "output": {
            "container": "mkv",
            "naming": "{title}_{profile}",
            "overwrite": False,
            "auto_increment": True,
        },
        "constraints": {
            "skip_if_below_gb": None,
            "skip_if_codec_matches": False,
        },
        "metadata": {
            "preserve": True,
        },
        "advanced": {
            "extra_output_args": None,
        },
    }


def probe_media_for_recommendation(path: str, ffprobe_exe: str) -> MediaAnalysis:
    creationflags = 0x08000000 if os.name == "nt" else 0
    proc = subprocess.run(
        [
            ffprobe_exe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        creationflags=creationflags,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip() or f"Exited with code {proc.returncode}"
        raise RuntimeError(f"ffprobe could not analyze the file: {stderr}")

    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"ffprobe returned invalid JSON: {exc}") from exc

    streams = payload.get("streams", [])
    format_data = payload.get("format", {})
    video_stream = next(
        (stream for stream in streams if str(stream.get("codec_type", "")).lower() == "video"),
        {},
    )
    primary_audio = _select_primary_audio(streams)

    size_bytes = _safe_int(format_data.get("size")) or (
        os.path.getsize(path) if os.path.isfile(path) else 0
    )
    duration_seconds = _safe_float(format_data.get("duration"))
    bitrate_bps = _safe_int(format_data.get("bit_rate"))
    if bitrate_bps <= 0 and duration_seconds > 0 and size_bytes > 0:
        bitrate_bps = int((size_bytes * 8) / duration_seconds)

    return {
        "path": os.path.normpath(path),
        "name": os.path.basename(path),
        "size_bytes": size_bytes,
        "duration_seconds": duration_seconds,
        "bitrate_bps": bitrate_bps,
        "video_codec": str(video_stream.get("codec_name", "") or "").lower(),
        "profile": _safe_text(video_stream.get("profile")),
        "width": _safe_int(video_stream.get("width")),
        "height": _safe_int(video_stream.get("height")),
        "pix_fmt": _safe_lower(video_stream.get("pix_fmt")),
        "bit_depth": _infer_bit_depth(
            video_stream,
            str(video_stream.get("pix_fmt", "") or ""),
        ),
        "color_transfer": _safe_lower(video_stream.get("color_transfer")),
        "color_primaries": _safe_lower(video_stream.get("color_primaries")),
        "color_space": _safe_lower(video_stream.get("color_space")),
        "fps": _parse_frame_rate(
            video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
        ),
        "audio_streams": sum(
            1 for stream in streams
            if str(stream.get("codec_type", "")).lower() == "audio"
        ),
        "subtitle_streams": sum(
            1 for stream in streams
            if str(stream.get("codec_type", "")).lower() == "subtitle"
        ),
        "audio_channel_layout": primary_audio.get("channel_layout"),
    }


def build_ffmpeg_recommendations(analysis: MediaAnalysis) -> RecommendationResult:
    height_bucket = _height_bucket(analysis["height"])
    crf_table = _crf_table(height_bucket)
    codec_family = _source_codec_family(analysis["video_codec"])
    bitrate_mbps = analysis["bitrate_bps"] / 1_000_000 if analysis["bitrate_bps"] > 0 else 0.0
    size_gb = analysis["size_bytes"] / (1024**3) if analysis["size_bytes"] > 0 else 0.0
    hdr = _is_hdr(analysis)
    bit_depth = _analysis_int(analysis, "bit_depth")
    budget_mbps = _bitrate_budget_mbps(height_bucket, hdr=hdr)
    bitrate_ratio = bitrate_mbps / budget_mbps if bitrate_mbps > 0 and budget_mbps > 0 else 0.0

    recommended_id = "balanced"
    recommendation_reason = (
        "It is the safest first pass: good space savings without getting too aggressive."
    )
    advisory = ""

    if codec_family in {"hevc", "modern"}:
        if height_bucket == "4k" or hdr:
            recommended_id = "higher_quality"
            recommendation_reason = (
                "This is already an efficient 4K/HDR-style source, so the safest first pass is "
                "to protect detail and test a short sample before chasing file size."
            )
            advisory = (
                "High-bitrate 4K or HDR sources can still shrink, but they are easier to make worse. "
                "Use a short sample before running the full movie."
            )
        elif bitrate_ratio <= 1.25 or size_gb < 8:
            recommended_id = "higher_quality"
            recommendation_reason = (
                "This file is already using an efficient codec at a modest size or bitrate, "
                "so the safer move is to hold onto more detail."
            )
            advisory = (
                "This source already looks fairly efficient on paper. Re-encoding it may save "
                "less space than you expect and can still cost quality."
            )
        elif bitrate_ratio >= 2.0 and size_gb >= 20:
            advisory = (
                "This is an efficient codec, but the bitrate is high enough that a conservative "
                "H.265 pass may still save real space. Compare a sample first."
            )
        else:
            recommended_id = "higher_quality"
            recommendation_reason = (
                "The source codec is already efficient, so it is better to start quality-first "
                "unless you have a specific size target."
            )
    elif codec_family in {"h264", "legacy"} and (
        bitrate_ratio >= 1.5 or
        analysis["size_bytes"] >= 12 * 1024**3
    ):
        advisory = (
            "This looks like a strong H.265 candidate. You should usually get worthwhile size savings "
            "without touching audio or subtitles."
        )
    elif bitrate_mbps > 0 and bitrate_ratio <= 1.0:
        recommended_id = "higher_quality"
        recommendation_reason = (
            "The source bitrate is already modest for its resolution, so a quality-first pass "
            "is less likely to cause visible damage."
        )

    if hdr and recommended_id != "higher_quality":
        recommended_id = "higher_quality"
        recommendation_reason = (
            "HDR/BT.2020 metadata was detected, so the safest first pass is the quality-preserving option."
        )
        advisory = advisory or (
            "HDR sources deserve a conservative test encode before a full run."
        )

    source_notes = _source_notes(
        analysis=analysis,
        codec_family=codec_family,
        height_bucket=height_bucket,
        bitrate_mbps=bitrate_mbps,
        budget_mbps=budget_mbps,
        hdr=hdr,
    )
    decision_factors = [
        f"Classified as {height_bucket.upper()} / {codec_family.upper()}",
        f"Source bitrate: {_format_mbps(bitrate_mbps)}",
        f"Conservative H.265 comfort target: {_format_mbps(budget_mbps)}",
    ]
    if size_gb > 0:
        decision_factors.append(f"Source size: {_format_gb(size_gb)}")
    if bit_depth > 0:
        decision_factors.append(f"Bit depth: {bit_depth}-bit")
    if hdr:
        decision_factors.append("HDR/BT.2020 detected")

    profiles = [
        {
            "id": "smaller_file",
            "label": "Save Space",
            "summary": "Smallest of the three, highest visual risk.",
            "why": "Useful when storage matters more than preserving every bit of grain and dark-scene detail.",
            "best_for": "Large H.264, MPEG-2, VC-1, or other high-bitrate sources you are comfortable testing.",
            "caution": "Most likely to soften fine grain, dark scenes, or 4K/HDR detail.",
            "expected_result": "Best chance of a noticeably smaller file, not the safest quality choice.",
            "preset": "slow",
        },
        {
            "id": "balanced",
            "label": "Best Overall",
            "summary": "Best first try for most large MKVs.",
            "why": "Keeps the encode conservative enough for a first pass while still aiming for real savings.",
            "best_for": "Big 1080p rips and high-bitrate sources where you want a sensible default.",
            "caution": "Still a re-encode, so compare a sample if the movie is dark, grainy, or important.",
            "expected_result": "Good odds of shrinking the file without getting too aggressive.",
            "preset": "medium",
        },
        {
            "id": "higher_quality",
            "label": "Keep More Quality",
            "summary": "Safest re-encode, least aggressive shrink.",
            "why": "Uses a lower CRF so it holds onto more detail, especially in darker, busy, 4K, or HDR scenes.",
            "best_for": "4K/HDR sources, already-efficient HEVC/AV1 files, or anything you really care about.",
            "caution": "May not save much space if the source is already efficient.",
            "expected_result": "Lowest quality risk of the three, with smaller or less predictable savings.",
            "preset": "slow",
        },
    ]

    recommendations: list[FFmpegRecommendation] = []
    for profile in profiles:
        rec_id = profile["id"]
        crf = crf_table[rec_id]
        profile_label = f"Recommended - {profile['label']}"
        recommendations.append(
            {
                "id": rec_id,
                "label": profile["label"],
                "summary": profile["summary"],
                "details": (
                    f"FFmpeg H.265 encode using CRF {crf}, preset {profile['preset']}, "
                    "audio copy, subtitle copy, and MKV output."
                ),
                "why": profile["why"],
                "best_for": profile["best_for"],
                "caution": profile["caution"],
                "expected_result": profile["expected_result"],
                "crf": crf,
                "preset": profile["preset"],
                "profile_name": profile_label,
                "profile_data": _build_profile_data(
                    crf=crf,
                    preset=profile["preset"],
                    profile_label=profile_label,
                    analysis=analysis,
                ),
            }
        )

    return {
        "recommended_id": recommended_id,
        "recommendation_reason": recommendation_reason,
        "advisory": advisory,
        "source_notes": source_notes,
        "decision_factors": decision_factors,
        "recommendations": recommendations,
    }


def format_analysis_summary(analysis: MediaAnalysis) -> list[str]:
    resolution = "unknown resolution"
    if analysis["width"] > 0 and analysis["height"] > 0:
        resolution = f"{analysis['width']}x{analysis['height']}"

    duration_text = "unknown runtime"
    if analysis["duration_seconds"] > 0:
        total_seconds = int(round(analysis["duration_seconds"]))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            duration_text = f"{hours:d}:{minutes:02d}:{seconds:02d}"
        else:
            duration_text = f"{minutes:02d}:{seconds:02d}"

    size_text = "unknown size"
    if analysis["size_bytes"] > 0:
        size_text = f"{analysis['size_bytes'] / (1024**3):.2f} GB"

    bitrate_text = "unknown bitrate"
    if analysis["bitrate_bps"] > 0:
        bitrate_text = f"{analysis['bitrate_bps'] / 1_000_000:.2f} Mbps"

    fps_text = "unknown fps"
    if analysis["fps"] > 0:
        fps_text = f"{analysis['fps']:.2f} fps"

    codec_text = analysis["video_codec"] or "unknown codec"
    profile_text = _safe_text(analysis.get("profile", ""))
    if profile_text:
        codec_text = f"{codec_text} ({profile_text})"
    bit_depth = _analysis_int(analysis, "bit_depth")
    technical_parts = []
    if analysis["pix_fmt"]:
        technical_parts.append(analysis["pix_fmt"])
    if bit_depth > 0:
        technical_parts.append(f"{bit_depth}-bit")
    color_transfer = _analysis_text(analysis, "color_transfer")
    if color_transfer:
        technical_parts.append(f"transfer {color_transfer}")
    color_primaries = _analysis_text(analysis, "color_primaries")
    if color_primaries:
        technical_parts.append(f"primaries {color_primaries}")

    audio_text = f"{analysis['audio_streams']} audio track(s)"
    subtitle_text = f"{analysis['subtitle_streams']} subtitle track(s)"

    lines = [
        f"Codec: {codec_text}",
        f"Resolution: {resolution}",
        f"Runtime: {duration_text}",
        f"Size: {size_text}",
        f"Bitrate: {bitrate_text}",
        f"Frame rate: {fps_text}",
        f"Streams: {audio_text}, {subtitle_text}",
    ]
    if technical_parts:
        lines.append(f"Video format: {', '.join(technical_parts)}")
    return lines


__all__ = [
    "FFmpegRecommendation",
    "MediaAnalysis",
    "RecommendationResult",
    "build_ffmpeg_recommendations",
    "format_analysis_summary",
    "probe_media_for_recommendation",
]
