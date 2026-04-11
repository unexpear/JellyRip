from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from core.pipeline import PipelineController, TranscodeJob, choose_available_output_path
from transcode.encoder_probe import resolve_hw_accel
from transcode.planner import TranscodePlan, ffmpeg_source_mode_label
from transcode.post_encode_verifier import build_contract
from transcode.profiles import ProfileLoader, TranscodeProfile, normalize_profile_data
from transcode.queue import TranscodeQueue

# hw_accel values that route to a hardware encoder at build time.
_GPU_ACCEL: frozenset[str] = frozenset({"nvenc", "qsv", "amf", "auto_prefer"})


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


def _gpu_adaptation_notes(
    profile_data: dict[str, Any],
    hw_accel: str,
) -> list[str]:
    """Return notes describing what the GPU encoder will handle differently.

    The recommendation was generated against a CPU libx265 baseline.  When
    the user routes the job through a hardware encoder, several assumptions
    no longer hold.  This function makes those differences explicit so they
    are recorded in the job metadata rather than silently ignored.
    """
    video = profile_data.get("video") or {}
    notes: list[str] = []

    crf = video.get("crf")
    if isinstance(crf, (int, float)):
        notes.append(
            f"CRF {crf} was calibrated for libx265. GPU encoders "
            f"({hw_accel}) use a different quality scale — verify output "
            f"quality and adjust if needed."
        )

    preset = video.get("preset")
    if hw_accel == "amf" and isinstance(preset, str):
        notes.append(
            f"AMF preset '{preset}' may not be valid; AMF uses "
            f"'quality', 'balanced', or 'speed'."
        )

    extra = video.get("extra_video_params") or ""
    if extra and hw_accel != "cpu":
        notes.append(
            "extra_video_params (x265-params) will be translated to ffmpeg "
            "color flags for GPU encoders; encoder-specific tuning keys "
            "(deblock, sao, etc.) will be silently dropped."
        )

    if hw_accel in ("nvenc", "qsv", "amf"):
        notes.append(
            f"{hw_accel.upper()} may silently ignore keyint, bframes, and "
            f"refs depending on driver version and encoder configuration."
        )

    if hw_accel == "auto_prefer":
        notes.append(
            "hw_accel=auto_prefer will select a GPU encoder if one is "
            "available. All GPU-specific caveats above apply."
        )

    return notes


def build_recommendation_job(
    *,
    plan: TranscodePlan,
    analysis: Mapping[str, Any],
    recommendation: Mapping[str, Any],
    ffmpeg_source_mode: str,
    ffmpeg_exe: str | None = None,
) -> QueueBuildResult:
    profile_data = dict(recommendation["profile_data"])
    normalized = normalize_profile_data(profile_data)

    # ── Capability-aware encoder resolution ──────────────────────────────────
    # If the profile requests a GPU encoder that is not available in this
    # FFmpeg build, fall back to CPU *before* the job is queued — so the
    # failure is caught here, not at execution time.
    video_section: dict[str, Any] = dict(normalized.get("video") or {})
    hw_accel: str = video_section.get("hw_accel") or "cpu"
    codec: str    = video_section.get("codec") or "h265"
    capability_notes: list[str] = []

    if ffmpeg_exe and hw_accel not in ("cpu", "auto_prefer"):
        resolved, reason = resolve_hw_accel(hw_accel, codec, ffmpeg_exe)
        if reason:
            video_section["hw_accel"] = resolved
            normalized = {**normalized, "video": video_section}
            hw_accel = resolved
            capability_notes.append(reason)

    profile = TranscodeProfile(str(recommendation["profile_name"]), normalized)

    # ── GPU feedback loop ────────────────────────────────────────────────────
    gpu_notes: list[str] = []
    if hw_accel in _GPU_ACCEL:
        gpu_notes = _gpu_adaptation_notes(normalized, hw_accel)

    output_path = choose_available_output_path(
        plan["output_path"],
        overwrite=profile.get("output", "overwrite", False),
        auto_increment=profile.get("output", "auto_increment", True),
    )
    # Build the output contract *before* the encode so it travels with the job
    # and can be checked by verify_output once FFmpeg completes.
    contract = build_contract(dict(recommendation), dict(analysis))

    # Build the fallback chain (Option A).  Rules are checked in order;
    # the first matching rule wins.
    fallback_rules: list[dict[str, str]] = []
    if contract.color_transfer:
        # HDR job: if color metadata is lost, retry as SDR.
        fallback_rules.append({"trigger": "hdr_metadata", "action": "strip_hdr"})
    if hw_accel not in ("cpu",):
        # GPU job: if the encoder is unavailable at runtime, retry on CPU.
        fallback_rules.append({"trigger": "encoder_unavailable", "action": "use_cpu"})
    # Bitrate collapse: if output bitrate implodes, retry at lower CRF.
    if contract.min_bitrate_bps:
        fallback_rules.append({"trigger": "bitrate_collapse", "action": "lower_crf"})
    # Mux failure: classify the failure even when no auto-recovery is possible.
    fallback_rules.append({"trigger": "mux_failure", "action": "mux_failure"})
    # Audio layout mismatch: classify only (downmix recovery not implemented).
    if contract.audio_layout:
        fallback_rules.append({"trigger": "audio_layout_mismatch", "action": "audio_layout_mismatch"})

    metadata: dict[str, Any] = {
        "source_relative_path": plan["relative_path"],
        "recommendation_id": recommendation["id"],
        "recommendation_label": recommendation["label"],
        "recommendation_details": recommendation["details"],
        "recommendation_why": recommendation.get("why", ""),
        "recommendation_caution": recommendation.get("caution", ""),
        "recommendation_expected_result": recommendation.get("expected_result", ""),
        "source_video_codec": analysis["video_codec"],
        "source_resolution": f"{analysis['width']}x{analysis['height']}",
        "source_bitrate_bps": analysis["bitrate_bps"],
        "source_duration_seconds": analysis["duration_seconds"],
        "ffmpeg_source_mode": ffmpeg_source_mode,
        "expected": contract.as_dict(),
        "fallback_rules": fallback_rules,
    }
    if capability_notes:
        metadata["capability_notes"] = capability_notes
    if gpu_notes:
        metadata["gpu_adaptation_notes"] = gpu_notes

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
    abort_event=None,
) -> TranscodeQueue:
    transcode_queue = TranscodeQueue(
        log_dir=log_dir,
        ffmpeg_exe=ffmpeg_exe,
        ffprobe_exe=ffprobe_exe,
        handbrake_exe=handbrake_exe,
        ffmpeg_source_mode=ffmpeg_source_mode,
        temp_root=temp_root,
        abort_event=abort_event,
    )
    for job in jobs:
        transcode_queue.add_job(job)
    return transcode_queue
