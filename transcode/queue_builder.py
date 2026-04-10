from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core.pipeline import PipelineController, TranscodeJob, choose_available_output_path
from transcode.planner import TranscodePlan, ffmpeg_source_mode_label
from transcode.profiles import ProfileLoader, TranscodeProfile
from transcode.queue import TranscodeQueue


@dataclass(frozen=True)
class QueueBuildResult:
    jobs: list[TranscodeJob]
    queue_detail: str


def _entry_by_input_path(
    selected_entries: Sequence[Mapping[str, object]] | None,
) -> dict[str, Mapping[str, object]]:
    entry_by_path: dict[str, Mapping[str, object]] = {}
    for entry in selected_entries or []:
        entry_path = os.path.normpath(str(entry.get("path", "") or ""))
        if entry_path:
            entry_by_path[os.path.normcase(entry_path)] = entry
    return entry_by_path


def build_queue_jobs(
    *,
    plans: Sequence[TranscodePlan],
    profile_loader: ProfileLoader,
    backend: str,
    option_value: str,
    ffmpeg_source_mode: str,
    selected_entries: Sequence[Mapping[str, object]] | None = None,
    default_handbrake_preset: str = "Fast 1080p30",
) -> QueueBuildResult:
    backend_key = str(backend or "").strip().lower()
    pipeline = PipelineController(profile_loader)

    if backend_key == "ffmpeg":
        selected_profile = str(option_value or "").strip()
        if not selected_profile:
            raise ValueError("Choose an FFmpeg profile first.")

        queue_detail = (
            f"Profile: {selected_profile} | "
            f"Source: {ffmpeg_source_mode_label(ffmpeg_source_mode)}"
        )
        entry_by_path = _entry_by_input_path(selected_entries)
        for plan in plans:
            metadata: dict[str, Any] = {
                "source_relative_path": plan["relative_path"],
                "ffmpeg_source_mode": ffmpeg_source_mode,
            }
            selected_entry = entry_by_path.get(os.path.normcase(plan["input_path"]))
            duration_seconds = None
            if selected_entry is not None:
                duration_seconds = selected_entry.get("duration_seconds")
            if isinstance(duration_seconds, (int, float)) and duration_seconds > 0:
                metadata["source_duration_seconds"] = float(duration_seconds)
            pipeline.add_job(
                plan["input_path"],
                plan["output_path"],
                profile_name=selected_profile,
                metadata=metadata,
                backend="ffmpeg",
            )
    elif backend_key == "handbrake":
        selected_preset = str(option_value or "").strip() or default_handbrake_preset
        queue_detail = f"Preset: {selected_preset}"
        for plan in plans:
            pipeline.add_job(
                plan["input_path"],
                plan["output_path"],
                metadata={
                    "source_relative_path": plan["relative_path"],
                },
                backend="handbrake",
                backend_options={"preset": selected_preset},
            )
    else:
        raise ValueError(f"Unsupported transcode backend: {backend}")

    return QueueBuildResult(
        jobs=list(pipeline.get_queue()),
        queue_detail=queue_detail,
    )


def build_recommendation_job(
    *,
    plan: TranscodePlan,
    analysis: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    ffmpeg_source_mode: str,
) -> QueueBuildResult:
    profile = TranscodeProfile(
        str(recommendation["profile_name"]),
        dict(recommendation["profile_data"]),
    )
    output_path = choose_available_output_path(
        plan["output_path"],
        overwrite=profile.get("output", "overwrite", False),
        auto_increment=profile.get("output", "auto_increment", True),
    )
    metadata = {
        "source_relative_path": plan["relative_path"],
        "recommendation_id": recommendation["id"],
        "recommendation_label": recommendation["label"],
        "recommendation_details": recommendation["details"],
        "source_video_codec": analysis["video_codec"],
        "source_resolution": f"{analysis['width']}x{analysis['height']}",
        "source_bitrate_bps": analysis["bitrate_bps"],
        "source_duration_seconds": analysis["duration_seconds"],
        "ffmpeg_source_mode": ffmpeg_source_mode,
    }
    job = TranscodeJob(
        str(analysis["path"]),
        output_path,
        profile,
        metadata=metadata,
        backend="ffmpeg",
    )
    queue_detail = (
        f"{recommendation['label']} recommendation | "
        f"CRF {recommendation['crf']} | preset {recommendation['preset']} | "
        f"source {ffmpeg_source_mode_label(ffmpeg_source_mode)}"
    )
    return QueueBuildResult(jobs=[job], queue_detail=queue_detail)


def required_output_directories(
    jobs: Sequence[TranscodeJob],
    output_root: str,
) -> list[str]:
    directories: list[str] = []
    seen: set[str] = set()
    fallback_root = os.path.normpath(output_root)
    for job in jobs:
        directory = os.path.normpath(os.path.dirname(job.output_path) or fallback_root)
        key = os.path.normcase(directory)
        if key in seen:
            continue
        seen.add(key)
        directories.append(directory)
    return directories


def build_transcode_queue(
    *,
    jobs: Sequence[TranscodeJob],
    log_dir: str,
    ffmpeg_exe: str,
    ffprobe_exe: str,
    handbrake_exe: str,
    ffmpeg_source_mode: str,
    temp_root: str | None = None,
) -> TranscodeQueue:
    transcode_queue = TranscodeQueue(
        log_dir=log_dir,
        ffmpeg_exe=ffmpeg_exe,
        ffprobe_exe=ffprobe_exe,
        handbrake_exe=handbrake_exe,
        ffmpeg_source_mode=ffmpeg_source_mode,
        temp_root=temp_root,
    )
    for job in jobs:
        transcode_queue.add_job(job)
    return transcode_queue
