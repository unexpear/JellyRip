from __future__ import annotations

import json
import os
import subprocess
from typing import Any, TypedDict


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


class FFmpegRecommendation(TypedDict):
    id: str
    label: str
    summary: str
    details: str
    why: str
    crf: int
    preset: str
    profile_name: str
    profile_data: dict[str, Any]


class RecommendationResult(TypedDict):
    recommended_id: str
    recommendation_reason: str
    advisory: str
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
        return {"higher_quality": 20, "balanced": 22, "smaller_file": 24}
    if height_bucket == "1080p":
        return {"higher_quality": 18, "balanced": 20, "smaller_file": 22}
    if height_bucket == "720p":
        return {"higher_quality": 19, "balanced": 21, "smaller_file": 23}
    return {"higher_quality": 18, "balanced": 20, "smaller_file": 22}


def _bitrate_budget_mbps(height_bucket: str) -> float:
    if height_bucket == "4k":
        return 12.0
    if height_bucket == "1080p":
        return 6.0
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


def _build_profile_data(
    *,
    crf: int,
    preset: str,
    profile_label: str,
) -> dict[str, Any]:
    return {
        "video": {
            "codec": "h265",
            "mode": "crf",
            "crf": crf,
            "bitrate": None,
            "preset": preset,
            "hw_accel": "cpu",
        },
        "audio": {
            "mode": "copy",
            "language": None,
            "tracks": "all",
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
        "width": _safe_int(video_stream.get("width")),
        "height": _safe_int(video_stream.get("height")),
        "pix_fmt": str(video_stream.get("pix_fmt", "") or "").lower(),
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
    }


def build_ffmpeg_recommendations(analysis: MediaAnalysis) -> RecommendationResult:
    height_bucket = _height_bucket(analysis["height"])
    crf_table = _crf_table(height_bucket)
    codec_family = _source_codec_family(analysis["video_codec"])
    bitrate_mbps = analysis["bitrate_bps"] / 1_000_000 if analysis["bitrate_bps"] > 0 else 0.0

    recommended_id = "balanced"
    recommendation_reason = (
        "It is the safest first pass: good space savings without getting too aggressive."
    )
    advisory = ""

    if codec_family in {"hevc", "modern"} and bitrate_mbps > 0:
        if bitrate_mbps <= _bitrate_budget_mbps(height_bucket):
            recommended_id = "higher_quality"
            recommendation_reason = (
                "This file is already using an efficient codec at a fairly modest bitrate, "
                "so if you re-encode it, the safer move is to hold onto more detail."
            )
            advisory = (
                "This source already looks fairly efficient on paper. Re-encoding it may save "
                "less space than you expect and can still cost quality."
            )
    elif codec_family in {"h264", "legacy"} and (
        bitrate_mbps >= _bitrate_budget_mbps(height_bucket) * 1.5 or
        analysis["size_bytes"] >= 12 * 1024**3
    ):
        advisory = (
            "This looks like a strong H.265 candidate. You should usually get worthwhile size savings "
            "without touching audio or subtitles."
        )

    profiles = [
        (
            "smaller_file",
            "Save Space",
            "Pushes harder for space savings.",
            "Useful when storage matters more than keeping every last bit of detail.",
            "slow",
        ),
        (
            "balanced",
            "Best Overall",
            "Best first try for most big MKVs.",
            "Keeps the encode conservative enough for a first pass while still shrinking the file.",
            "medium",
        ),
        (
            "higher_quality",
            "Keep More Quality",
            "Safer if you care more about keeping detail.",
            "Uses a lower CRF so it holds onto more detail, especially in darker or busy scenes.",
            "slow",
        ),
    ]

    recommendations: list[FFmpegRecommendation] = []
    for rec_id, label, summary, why, preset in profiles:
        crf = crf_table[rec_id]
        profile_label = f"Recommended - {label}"
        recommendations.append(
            {
                "id": rec_id,
                "label": label,
                "summary": summary,
                "details": (
                    f"FFmpeg H.265 encode using CRF {crf}, preset {preset}, "
                    "audio copy, subtitle copy, and MKV output."
                ),
                "why": why,
                "crf": crf,
                "preset": preset,
                "profile_name": profile_label,
                "profile_data": _build_profile_data(
                    crf=crf,
                    preset=preset,
                    profile_label=profile_label,
                ),
            }
        )

    return {
        "recommended_id": recommended_id,
        "recommendation_reason": recommendation_reason,
        "advisory": advisory,
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
    audio_text = f"{analysis['audio_streams']} audio track(s)"
    subtitle_text = f"{analysis['subtitle_streams']} subtitle track(s)"

    return [
        f"Codec: {codec_text}",
        f"Resolution: {resolution}",
        f"Runtime: {duration_text}",
        f"Size: {size_text}",
        f"Bitrate: {bitrate_text}",
        f"Frame rate: {fps_text}",
        f"Streams: {audio_text}, {subtitle_text}",
    ]


__all__ = [
    "FFmpegRecommendation",
    "MediaAnalysis",
    "RecommendationResult",
    "build_ffmpeg_recommendations",
    "format_analysis_summary",
    "probe_media_for_recommendation",
]
