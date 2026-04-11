"""Tests for transcode.fallback.

Coverage
--------
- find_applicable_rule: trigger matching for hdr_metadata and encoder_unavailable
- apply_fallback: strip_hdr and use_cpu actions
- Output path suffix insertion
- Metadata cleanup (expected / fallback_rules stripped from fallback job)
- Edge cases: no rules, no profile, unknown action, non-FAIL outcome
"""

from __future__ import annotations

import pytest

from core.pipeline import TranscodeJob
from transcode.fallback import (
    _fallback_output_path,
    apply_fallback,
    find_applicable_rule,
)
from transcode.post_encode_verifier import VerificationOutcome, VerificationResult
from transcode.profiles import TranscodeProfile, normalize_profile_data


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_result(outcome: VerificationOutcome, errors=(), warnings=()):
    return VerificationResult(
        outcome=outcome,
        errors=list(errors),
        warnings=list(warnings),
    )


def _make_job(
    output_path: str = "output.mkv",
    hw_accel: str = "cpu",
    extra_params: str = "",
    metadata: dict | None = None,
) -> TranscodeJob:
    pd = normalize_profile_data({
        "video": {
            "hw_accel": hw_accel,
            "extra_video_params": extra_params or None,
            "pix_fmt": "yuv420p10le" if extra_params else None,
            "video_profile": "main10" if extra_params else None,
        }
    })
    profile = TranscodeProfile("test", pd)
    return TranscodeJob(
        "input.mkv", output_path, profile,
        metadata=dict(metadata or {}), backend="ffmpeg",
    )


_HDR_JOB_PARAMS = (
    "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:hdr-opt=1"
)
_HDR_FAIL_RESULT = _make_result(
    VerificationOutcome.FAIL,
    errors=["HDR transfer mismatch: expected 'smpte2084', got '(not set)'. "
            "HDR playback will look washed out."],
)
_ENCODER_FAIL_RESULT = _make_result(
    VerificationOutcome.FAIL,
    errors=["Encoder 'hevc_nvenc' is not available in this FFmpeg build."],
)
_BITRATE_FAIL_RESULT = _make_result(
    VerificationOutcome.FAIL,
    errors=["Bitrate collapse: output 50,000 bps is below minimum 2,000,000 bps (2% of floor). "
            "Encode may be severely over-compressed."],
)
_MUX_FAIL_RESULT = _make_result(
    VerificationOutcome.FAIL,
    errors=["ffprobe failed: [Errno 2] No such file or directory: 'ffprobe'"],
)
_AUDIO_LAYOUT_FAIL_RESULT = _make_result(
    VerificationOutcome.FAIL,
    errors=["Audio layout mismatch: expected '5.1(side)', got 'stereo'."],
)
_PASS_RESULT = _make_result(VerificationOutcome.PASS)


# ── find_applicable_rule ──────────────────────────────────────────────────────

def test_find_rule_hdr_trigger_matches():
    rules = [{"trigger": "hdr_metadata", "action": "strip_hdr"}]
    rule = find_applicable_rule(_HDR_FAIL_RESULT, rules)
    assert rule is not None
    assert rule["action"] == "strip_hdr"


def test_find_rule_encoder_trigger_matches():
    rules = [{"trigger": "encoder_unavailable", "action": "use_cpu"}]
    rule = find_applicable_rule(_ENCODER_FAIL_RESULT, rules)
    assert rule is not None
    assert rule["action"] == "use_cpu"


def test_find_rule_first_match_wins():
    """HDR error → first matching rule is returned, not all matches."""
    rules = [
        {"trigger": "hdr_metadata",       "action": "strip_hdr"},
        {"trigger": "encoder_unavailable", "action": "use_cpu"},
    ]
    rule = find_applicable_rule(_HDR_FAIL_RESULT, rules)
    assert rule["action"] == "strip_hdr"


def test_find_rule_no_match_returns_none():
    """Encoder error but only an HDR rule → no match."""
    rules = [{"trigger": "hdr_metadata", "action": "strip_hdr"}]
    assert find_applicable_rule(_ENCODER_FAIL_RESULT, rules) is None


def test_find_rule_empty_rules_returns_none():
    assert find_applicable_rule(_HDR_FAIL_RESULT, []) is None


def test_find_rule_pass_outcome_returns_none():
    rules = [{"trigger": "hdr_metadata", "action": "strip_hdr"}]
    assert find_applicable_rule(_PASS_RESULT, rules) is None


def test_find_rule_degraded_outcome_returns_none():
    result = _make_result(VerificationOutcome.DEGRADED, warnings=["pixel format drift"])
    rules = [{"trigger": "hdr_metadata", "action": "strip_hdr"}]
    assert find_applicable_rule(result, rules) is None


def test_find_rule_bitrate_collapse_trigger_matches():
    rules = [{"trigger": "bitrate_collapse", "action": "lower_crf"}]
    rule = find_applicable_rule(_BITRATE_FAIL_RESULT, rules)
    assert rule is not None
    assert rule["action"] == "lower_crf"


def test_find_rule_mux_failure_trigger_matches():
    rules = [{"trigger": "mux_failure", "action": "mux_failure"}]
    rule = find_applicable_rule(_MUX_FAIL_RESULT, rules)
    assert rule is not None
    assert rule["trigger"] == "mux_failure"


def test_find_rule_audio_layout_mismatch_trigger_matches():
    rules = [{"trigger": "audio_layout_mismatch", "action": "audio_layout_mismatch"}]
    rule = find_applicable_rule(_AUDIO_LAYOUT_FAIL_RESULT, rules)
    assert rule is not None
    assert rule["trigger"] == "audio_layout_mismatch"


def test_find_rule_bitrate_collapse_does_not_match_encoder_error():
    rules = [{"trigger": "bitrate_collapse", "action": "lower_crf"}]
    assert find_applicable_rule(_ENCODER_FAIL_RESULT, rules) is None


# ── apply_fallback: strip_hdr ─────────────────────────────────────────────────

def test_strip_hdr_removes_color_params():
    job = _make_job(extra_params=_HDR_JOB_PARAMS)
    fallback = apply_fallback(job, {"trigger": "hdr_metadata", "action": "strip_hdr"})
    assert fallback is not None
    extra = fallback.profile.get("video", "extra_video_params")
    assert extra is None or "colorprim" not in (extra or "")
    assert extra is None or "transfer" not in (extra or "")
    assert extra is None or "hdr-opt" not in (extra or "")


def test_strip_hdr_downgrades_pix_fmt():
    job = _make_job(extra_params=_HDR_JOB_PARAMS)
    fallback = apply_fallback(job, {"trigger": "hdr_metadata", "action": "strip_hdr"})
    assert fallback.profile.get("video", "pix_fmt") == "yuv420p"


def test_strip_hdr_downgrades_video_profile():
    job = _make_job(extra_params=_HDR_JOB_PARAMS)
    fallback = apply_fallback(job, {"trigger": "hdr_metadata", "action": "strip_hdr"})
    assert fallback.profile.get("video", "video_profile") == "main"


def test_strip_hdr_output_path_has_suffix():
    job = _make_job(output_path="output.mkv", extra_params=_HDR_JOB_PARAMS)
    fallback = apply_fallback(job, {"trigger": "hdr_metadata", "action": "strip_hdr"})
    assert "sdr_fallback" in fallback.output_path


def test_strip_hdr_metadata_records_action():
    job = _make_job(extra_params=_HDR_JOB_PARAMS)
    fallback = apply_fallback(job, {"trigger": "hdr_metadata", "action": "strip_hdr"})
    assert fallback.metadata["fallback_action"] == "strip_hdr"
    assert fallback.metadata["fallback_from"] == job.output_path


def test_strip_hdr_clears_expected_and_fallback_rules():
    """Fallback job must not carry the original contract or rules."""
    job = _make_job(
        extra_params=_HDR_JOB_PARAMS,
        metadata={
            "expected": {"video_codec": "hevc"},
            "fallback_rules": [{"trigger": "hdr_metadata", "action": "strip_hdr"}],
        },
    )
    fallback = apply_fallback(job, {"trigger": "hdr_metadata", "action": "strip_hdr"})
    assert "expected" not in fallback.metadata
    assert "fallback_rules" not in fallback.metadata


def test_strip_hdr_preserves_non_color_extra_params():
    """Non-HDR x265 tuning keys (e.g. deblock) must survive the strip."""
    job = _make_job(
        extra_params=_HDR_JOB_PARAMS + ":deblock=-1,-1:sao=0"
    )
    fallback = apply_fallback(job, {"trigger": "hdr_metadata", "action": "strip_hdr"})
    extra = fallback.profile.get("video", "extra_video_params") or ""
    assert "deblock" in extra
    assert "sao" in extra
    assert "colorprim" not in extra


# ── apply_fallback: use_cpu ───────────────────────────────────────────────────

def test_use_cpu_sets_hw_accel():
    job = _make_job(hw_accel="nvenc")
    fallback = apply_fallback(job, {"trigger": "encoder_unavailable", "action": "use_cpu"})
    assert fallback is not None
    assert fallback.profile.get("video", "hw_accel") == "cpu"


def test_use_cpu_output_path_has_suffix():
    job = _make_job(output_path="output.mkv", hw_accel="nvenc")
    fallback = apply_fallback(job, {"trigger": "encoder_unavailable", "action": "use_cpu"})
    assert "cpu_fallback" in fallback.output_path


def test_use_cpu_metadata_records_action():
    job = _make_job(hw_accel="nvenc")
    fallback = apply_fallback(job, {"trigger": "encoder_unavailable", "action": "use_cpu"})
    assert fallback.metadata["fallback_action"] == "use_cpu"


def test_use_cpu_preserves_other_video_settings():
    """hw_accel change must not affect CRF, preset, or codec."""
    job = _make_job(hw_accel="nvenc")
    original_crf    = job.profile.get("video", "crf")
    original_preset = job.profile.get("video", "preset")
    original_codec  = job.profile.get("video", "codec")
    fallback = apply_fallback(job, {"trigger": "encoder_unavailable", "action": "use_cpu"})
    assert fallback.profile.get("video", "crf")    == original_crf
    assert fallback.profile.get("video", "preset") == original_preset
    assert fallback.profile.get("video", "codec")  == original_codec


# ── apply_fallback: edge cases ────────────────────────────────────────────────

def test_apply_fallback_unknown_action_returns_none():
    job = _make_job()
    assert apply_fallback(job, {"action": "do_something_unknown"}) is None


def test_apply_fallback_no_profile_returns_none():
    job = TranscodeJob("input.mkv", "output.mkv", profile=None)
    assert apply_fallback(job, {"action": "strip_hdr"}) is None


# ── _fallback_output_path ────────────────────────────────────────────────────

def test_fallback_output_path_inserts_suffix_before_extension():
    assert _fallback_output_path("movie.mkv", "sdr_fallback") == "movie_sdr_fallback.mkv"


def test_fallback_output_path_handles_path_with_directory():
    result = _fallback_output_path("/output/movie.mkv", "cpu_fallback")
    assert result == "/output/movie_cpu_fallback.mkv"


def test_fallback_output_path_no_extension():
    result = _fallback_output_path("movie", "sdr_fallback")
    assert result == "movie_sdr_fallback"


# ── apply_fallback: lower_crf ─────────────────────────────────────────────────

def test_lower_crf_decrements_crf_by_3():
    job = _make_job()
    original_crf = job.profile.get("video", "crf")  # default is 22
    fallback = apply_fallback(job, {"trigger": "bitrate_collapse", "action": "lower_crf"})
    assert fallback is not None
    assert fallback.profile.get("video", "crf") == original_crf - 3


def test_lower_crf_output_path_has_suffix():
    job = _make_job(output_path="output.mkv")
    fallback = apply_fallback(job, {"trigger": "bitrate_collapse", "action": "lower_crf"})
    assert "lowcrf_fallback" in fallback.output_path


def test_lower_crf_metadata_records_action():
    job = _make_job()
    fallback = apply_fallback(job, {"trigger": "bitrate_collapse", "action": "lower_crf"})
    assert fallback.metadata["fallback_action"] == "lower_crf"
    assert fallback.metadata["fallback_from"] == job.output_path


def test_lower_crf_preserves_other_video_settings():
    """CRF change must not affect hw_accel, preset, or codec."""
    job = _make_job(hw_accel="nvenc")
    original_accel  = job.profile.get("video", "hw_accel")
    original_preset = job.profile.get("video", "preset")
    original_codec  = job.profile.get("video", "codec")
    fallback = apply_fallback(job, {"trigger": "bitrate_collapse", "action": "lower_crf"})
    assert fallback.profile.get("video", "hw_accel") == original_accel
    assert fallback.profile.get("video", "preset")   == original_preset
    assert fallback.profile.get("video", "codec")    == original_codec


def test_lower_crf_floor_is_zero():
    """CRF cannot go below 0 regardless of starting value."""
    pd = normalize_profile_data({"video": {"crf": 1}})
    profile = TranscodeProfile("test", pd)
    from core.pipeline import TranscodeJob
    job = TranscodeJob("input.mkv", "output.mkv", profile)
    fallback = apply_fallback(job, {"trigger": "bitrate_collapse", "action": "lower_crf"})
    assert fallback.profile.get("video", "crf") == 0


def test_lower_crf_clears_expected_and_fallback_rules():
    job = _make_job(
        metadata={
            "expected": {"video_codec": "hevc"},
            "fallback_rules": [{"trigger": "bitrate_collapse", "action": "lower_crf"}],
        },
    )
    fallback = apply_fallback(job, {"trigger": "bitrate_collapse", "action": "lower_crf"})
    assert "expected" not in fallback.metadata
    assert "fallback_rules" not in fallback.metadata


# ── apply_fallback: unknown / classify-only actions ───────────────────────────

def test_mux_failure_action_returns_none():
    """mux_failure has no recovery — apply_fallback returns None."""
    job = _make_job()
    assert apply_fallback(job, {"trigger": "mux_failure", "action": "mux_failure"}) is None


def test_audio_layout_mismatch_action_returns_none():
    """audio_layout_mismatch has no recovery — apply_fallback returns None."""
    job = _make_job()
    assert apply_fallback(
        job, {"trigger": "audio_layout_mismatch", "action": "audio_layout_mismatch"}
    ) is None
