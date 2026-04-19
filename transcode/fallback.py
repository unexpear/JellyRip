"""Post-encode fallback strategy (Option A).

When ``verify_output`` returns FAIL, the queue checks the job's
``fallback_rules`` metadata and, if a matching rule exists, builds a
corrected retry job to insert at the front of the queue.

Fallback rules
--------------
Each rule is a plain dict stored in ``job.metadata["fallback_rules"]``:

    {"trigger": "hdr_metadata",       "action": "strip_hdr"}
    {"trigger": "encoder_unavailable", "action": "use_cpu"}

Trigger matching
----------------
``"hdr_metadata"``      — fired when errors mention HDR transfer, color
                          primaries, or color space mismatch.
``"encoder_unavailable"``— fired when errors mention an encoder not being
                          available in the FFmpeg build.

Actions
-------
``"strip_hdr"`` — rebuild the job with HDR color metadata removed,
                  pixel format downgraded to yuv420p (8-bit SDR).
``"use_cpu"``   — rebuild the job with hw_accel forced to "cpu"
                  (libx265), keeping all other settings intact.
``"audio_layout_mismatch"`` — rebuild the job with a stereo downmix,
                  switching audio copy to AAC when a real encode is needed.

The fallback job's output path gets a ``_sdr_fallback`` or
``_cpu_fallback`` suffix so it does not overwrite the original attempt.
"""

from __future__ import annotations

import copy
import os
from typing import Any

from core.pipeline import TranscodeJob, choose_available_output_path
from transcode.post_encode_verifier import (
    OutputContract,
    VerificationOutcome,
    VerificationResult,
)
from transcode.profiles import TranscodeProfile, normalize_profile_data

_HDR_ERROR_KEYWORDS = ("hdr transfer", "color primaries", "color space")
_ENCODER_ERROR_KEYWORDS = ("not available",)
_BITRATE_COLLAPSE_KEYWORDS = ("bitrate collapse",)
_MUX_FAILURE_KEYWORDS = ("ffprobe failed", "ffprobe exited", "could not parse ffprobe")
_AUDIO_LAYOUT_KEYWORDS = ("audio layout mismatch",)

# Keys in x265-params that are HDR-specific and must be stripped for SDR fallback.
_HDR_PARAM_KEYS: frozenset[str] = frozenset({
    "colorprim", "transfer", "colormatrix",
    "hdr-opt", "master-display", "max-cll",
    "min-luma", "max-luma",
})


def find_applicable_rule(
    result: VerificationResult,
    rules: list[dict[str, str]],
) -> dict[str, str] | None:
    """Return the first rule in *rules* whose trigger matches *result*.

    Returns ``None`` when the outcome is not FAIL or no rule matches.
    """
    if result.outcome != VerificationOutcome.FAIL:
        return None

    errors_lower = [e.lower() for e in result.errors]

    for rule in rules:
        trigger = rule.get("trigger", "")
        if trigger == "hdr_metadata":
            if any(
                any(kw in e for kw in _HDR_ERROR_KEYWORDS)
                for e in errors_lower
            ):
                return rule
        elif trigger == "encoder_unavailable":
            if any(
                any(kw in e for kw in _ENCODER_ERROR_KEYWORDS)
                for e in errors_lower
            ):
                return rule
        elif trigger == "bitrate_collapse":
            if any(
                any(kw in e for kw in _BITRATE_COLLAPSE_KEYWORDS)
                for e in errors_lower
            ):
                return rule
        elif trigger == "mux_failure":
            if any(
                any(kw in e for kw in _MUX_FAILURE_KEYWORDS)
                for e in errors_lower
            ):
                return rule
        elif trigger == "audio_layout_mismatch":
            if any(
                any(kw in e for kw in _AUDIO_LAYOUT_KEYWORDS)
                for e in errors_lower
            ):
                return rule

    return None


def apply_fallback(
    job: TranscodeJob,
    rule: dict[str, str],
) -> TranscodeJob | None:
    """Build a fallback ``TranscodeJob`` by applying *rule* to *job*.

    Returns ``None`` when the action is unknown or the job has no profile.
    The returned job has a modified output path and does not carry a
    verification contract or fallback rules — it is a fresh attempt.
    """
    if job.profile is None:
        return None

    action = rule.get("action", "")
    profile_data = job.profile.to_dict()

    if action == "strip_hdr":
        return _build_sdr_fallback(job, profile_data)
    if action == "use_cpu":
        return _build_cpu_fallback(job, profile_data)
    if action == "lower_crf":
        return _build_lower_crf_fallback(job, profile_data)
    if action == "audio_layout_mismatch":
        return _build_audio_layout_fallback(job, profile_data)
    return None


# ── Internal builders ─────────────────────────────────────────────────────────

def _fallback_output_path(original: str, suffix: str) -> str:
    base, ext = os.path.splitext(original)
    return f"{base}_{suffix}{ext}"


def _clean_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *metadata* with verification/fallback keys stripped."""
    cleaned = dict(metadata)
    cleaned.pop("expected", None)
    cleaned.pop("fallback_rules", None)
    return cleaned


def _refresh_audio_layout_expected(
    metadata: dict[str, Any],
    *,
    switched_from_copy: bool,
) -> dict[str, Any] | None:
    """Return a refreshed contract for the stereo retry, if one exists."""
    expected = metadata.get("expected")
    if not isinstance(expected, dict):
        return None
    contract = OutputContract.from_dict(expected)
    contract.audio_layout = "stereo"
    if switched_from_copy:
        contract.audio_codec = "aac"
    return contract.as_dict()


def _build_sdr_fallback(job: TranscodeJob, profile_data: dict[str, Any]) -> TranscodeJob:
    pd = copy.deepcopy(profile_data)
    video = pd.get("video") or {}

    # Strip HDR-specific x265-params.
    extra: str = video.get("extra_video_params") or ""
    clean = [
        p for p in extra.split(":")
        if "=" in p and p.split("=", 1)[0] not in _HDR_PARAM_KEYS
    ]
    video["extra_video_params"] = ":".join(clean) or None

    # Downgrade pixel format and colour profile to 8-bit SDR.
    video["pix_fmt"] = "yuv420p"
    video["video_profile"] = "main"
    pd["video"] = video

    normalized = normalize_profile_data(pd)
    new_profile = TranscodeProfile(f"{job.profile.name}_sdr_fallback", normalized)

    raw_path = _fallback_output_path(job.output_path, "sdr_fallback")
    output_path = choose_available_output_path(raw_path, overwrite=False, auto_increment=True)

    metadata = _clean_metadata(dict(job.metadata or {}))
    metadata["fallback_from"] = job.output_path
    metadata["fallback_action"] = "strip_hdr"

    return TranscodeJob(
        job.input_path, output_path, new_profile,
        metadata=metadata, backend=job.backend,
        backend_options=dict(job.backend_options or {}),
    )


def _build_lower_crf_fallback(job: TranscodeJob, profile_data: dict[str, Any]) -> TranscodeJob:
    """Retry with CRF decremented by 3 (higher quality, larger file)."""
    pd = copy.deepcopy(profile_data)
    video = pd.get("video") or {}
    crf = video.get("crf")
    if isinstance(crf, (int, float)):
        video["crf"] = max(0, int(crf) - 3)
    pd["video"] = video

    normalized = normalize_profile_data(pd)
    new_profile = TranscodeProfile(f"{job.profile.name}_lowcrf_fallback", normalized)

    raw_path = _fallback_output_path(job.output_path, "lowcrf_fallback")
    output_path = choose_available_output_path(raw_path, overwrite=False, auto_increment=True)

    metadata = _clean_metadata(dict(job.metadata or {}))
    metadata["fallback_from"] = job.output_path
    metadata["fallback_action"] = "lower_crf"

    return TranscodeJob(
        job.input_path, output_path, new_profile,
        metadata=metadata, backend=job.backend,
        backend_options=dict(job.backend_options or {}),
    )


def _build_cpu_fallback(job: TranscodeJob, profile_data: dict[str, Any]) -> TranscodeJob:
    pd = copy.deepcopy(profile_data)
    video = pd.get("video") or {}
    video["hw_accel"] = "cpu"
    pd["video"] = video

    normalized = normalize_profile_data(pd)
    new_profile = TranscodeProfile(f"{job.profile.name}_cpu_fallback", normalized)

    raw_path = _fallback_output_path(job.output_path, "cpu_fallback")
    output_path = choose_available_output_path(raw_path, overwrite=False, auto_increment=True)

    metadata = _clean_metadata(dict(job.metadata or {}))
    metadata["fallback_from"] = job.output_path
    metadata["fallback_action"] = "use_cpu"

    return TranscodeJob(
        job.input_path, output_path, new_profile,
        metadata=metadata, backend=job.backend,
        backend_options=dict(job.backend_options or {}),
    )


def _build_audio_layout_fallback(
    job: TranscodeJob,
    profile_data: dict[str, Any],
) -> TranscodeJob:
    pd = copy.deepcopy(profile_data)
    audio = pd.get("audio") or {}

    # A channel-layout recovery must produce a real audio encode. If the
    # original job was copying audio, switch to AAC so "-ac 2" can take effect.
    audio_mode = str(audio.get("mode") or "copy").strip().lower()
    if audio_mode == "copy":
        audio["mode"] = "aac"

    # Clear any explicit channel target that would override the downmix path.
    audio["channels"] = None
    audio["downmix"] = True
    pd["audio"] = audio

    normalized = normalize_profile_data(pd)
    new_profile = TranscodeProfile(f"{job.profile.name}_stereo_fallback", normalized)

    raw_path = _fallback_output_path(job.output_path, "stereo_fallback")
    output_path = choose_available_output_path(raw_path, overwrite=False, auto_increment=True)

    original_metadata = dict(job.metadata or {})
    metadata = _clean_metadata(original_metadata)
    refreshed_expected = _refresh_audio_layout_expected(
        original_metadata,
        switched_from_copy=(audio_mode == "copy"),
    )
    if refreshed_expected is not None:
        metadata["expected"] = refreshed_expected
    metadata["fallback_from"] = job.output_path
    metadata["fallback_action"] = "audio_layout_mismatch"

    return TranscodeJob(
        job.input_path, output_path, new_profile,
        metadata=metadata, backend=job.backend,
        backend_options=dict(job.backend_options or {}),
    )
