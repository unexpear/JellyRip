"""Tests for transcode.post_encode_verifier.

All tests mock the ffprobe subprocess — no real media files needed.

Coverage
--------
- build_contract: recommendation → OutputContract derivation
- OutputContract.as_dict / from_dict round-trip
- verify_output hard matches (FAIL on mismatch)
- verify_output soft matches (DEGRADED on mismatch)
- verify_output clean path (PASS)
- subtitle_mode semantics (burned / copy / none)
- ffprobe failure handling
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from transcode.post_encode_verifier import (
    OutputContract,
    VerificationOutcome,
    VerificationResult,
    _container_matches,
    _select_primary_audio,
    _select_primary_video,
    build_contract,
    contract_diff,
    verify_output,
)


# ── Test fixtures ─────────────────────────────────────────────────────────────

def _probe_json(
    video_codec: str = "hevc",
    pix_fmt: str = "yuv420p10le",
    color_transfer: str = "",
    color_primaries: str = "",
    color_space: str = "",
    audio_count: int = 2,
    audio_codec: str = "aac",
    audio_layout: str = "",
    sub_count: int = 0,
    format_name: str = "matroska,webm",
    duration: float = 3600.0,
    bit_rate: int | None = None,
) -> str:
    streams: list[dict[str, Any]] = [
        {
            "codec_type": "video",
            "codec_name": video_codec,
            "pix_fmt": pix_fmt,
            "color_transfer": color_transfer,
            "color_primaries": color_primaries,
            "color_space": color_space,
        }
    ]
    for _ in range(audio_count):
        s: dict[str, Any] = {"codec_type": "audio", "codec_name": audio_codec}
        if audio_layout:
            s["channel_layout"] = audio_layout
        streams.append(s)
    for _ in range(sub_count):
        streams.append({"codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle"})
    fmt: dict[str, Any] = {"format_name": format_name, "duration": str(duration)}
    if bit_rate is not None:
        fmt["bit_rate"] = str(bit_rate)
    return json.dumps({"streams": streams, "format": fmt})


def _make_proc(stdout: str, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


def _run_verify(contract: OutputContract, **probe_kwargs) -> VerificationResult:
    with patch("subprocess.run", return_value=_make_proc(_probe_json(**probe_kwargs))):
        return verify_output("output.mkv", contract)


def _rec(
    codec: str = "h265",
    pix_fmt: str = "yuv420p10le",
    extra_params: str = "",
    container: str = "mkv",
    audio_mode: str = "copy",
    audio_tracks: str = "all",
    burn_subs: bool = False,
    subtitle_mode: str = "all",
) -> dict[str, Any]:
    return {
        "id": "balanced",
        "label": "Balanced",
        "crf": 20,
        "preset": "medium",
        "profile_name": "test",
        "profile_data": {
            "video": {"codec": codec, "pix_fmt": pix_fmt, "extra_video_params": extra_params},
            "audio": {"mode": audio_mode, "tracks": audio_tracks},
            "subtitles": {"burn": burn_subs, "mode": subtitle_mode},
            "output": {"container": container},
        },
    }


def _analysis(
    audio_streams: list | None = None,
    duration: float = 3600.0,
    bitrate_bps: int = 25_000_000,
    audio_channel_layout: str | None = None,
) -> dict[str, Any]:
    d: dict[str, Any] = {
        "path": "/media/film.mkv",
        "video_codec": "h264",
        "width": 1920, "height": 1080,
        "bitrate_bps": bitrate_bps,
        "duration_seconds": duration,
        "audio_streams": audio_streams or [{"lang": "eng"}, {"lang": "fra"}],
    }
    if audio_channel_layout is not None:
        d["audio_channel_layout"] = audio_channel_layout
    return d


# ── build_contract: codec and container ──────────────────────────────────────

def test_contract_hevc_codec():
    c = build_contract(_rec(codec="h265"), _analysis())
    assert c.video_codec == "hevc"


def test_contract_h264_codec():
    c = build_contract(_rec(codec="h264"), _analysis())
    assert c.video_codec == "h264"


def test_contract_mkv_container():
    c = build_contract(_rec(container="mkv"), _analysis())
    assert c.container_format == "matroska"


def test_contract_mp4_container():
    c = build_contract(_rec(container="mp4"), _analysis())
    assert c.container_format == "mp4"


# ── build_contract: HDR and color space ──────────────────────────────────────

def test_contract_hdr10_color_fields():
    rec = _rec(extra_params="colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:hdr-opt=1")
    c = build_contract(rec, _analysis())
    assert c.color_transfer  == "smpte2084"
    assert c.color_primaries == "bt2020"
    assert c.colorspace      == "bt2020nc"


def test_contract_hlg_color_fields():
    rec = _rec(extra_params="colorprim=bt2020:transfer=arib-std-b67:colormatrix=bt2020nc")
    c = build_contract(rec, _analysis())
    assert c.color_transfer  == "arib-std-b67"
    assert c.color_primaries == "bt2020"
    assert c.colorspace      == "bt2020nc"


def test_contract_sdr_has_no_color_fields():
    c = build_contract(_rec(), _analysis())
    assert c.color_transfer  is None
    assert c.color_primaries is None
    assert c.colorspace      is None


def test_contract_bt2020c_colorspace():
    rec = _rec(extra_params="colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020c")
    c = build_contract(rec, _analysis())
    assert c.colorspace == "bt2020c"


# ── build_contract: audio ─────────────────────────────────────────────────────

def test_contract_audio_count_from_source():
    analysis = _analysis(audio_streams=[{"lang": "eng"}, {"lang": "fra"}, {"lang": "jpn"}])
    c = build_contract(_rec(audio_mode="copy", audio_tracks="all"), analysis)
    assert c.audio_stream_count == 3


def test_contract_audio_count_none_when_transcoding():
    c = build_contract(_rec(audio_mode="aac"), _analysis())
    assert c.audio_stream_count is None


def test_contract_audio_codec_aac():
    c = build_contract(_rec(audio_mode="aac"), _analysis())
    assert c.audio_codec == "aac"


def test_contract_audio_codec_none_for_copy():
    c = build_contract(_rec(audio_mode="copy"), _analysis())
    assert c.audio_codec is None


# ── build_contract: subtitle mode ────────────────────────────────────────────

def test_contract_subtitle_mode_burned():
    c = build_contract(_rec(burn_subs=True), _analysis())
    assert c.subtitle_mode == "burned"


def test_contract_subtitle_mode_copy():
    c = build_contract(_rec(burn_subs=False, subtitle_mode="all"), _analysis())
    assert c.subtitle_mode == "copy"


def test_contract_subtitle_mode_none():
    c = build_contract(_rec(burn_subs=False, subtitle_mode="none"), _analysis())
    assert c.subtitle_mode == "none"


# ── build_contract: duration ─────────────────────────────────────────────────

def test_contract_duration_bounds():
    c = build_contract(_rec(), _analysis(duration=3600.0))
    assert c.min_duration_seconds == pytest.approx(3564.0)
    assert c.max_duration_seconds == pytest.approx(3636.0)


# ── OutputContract serialisation ─────────────────────────────────────────────

def test_contract_roundtrip():
    original = OutputContract(
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        color_transfer="smpte2084",
        color_primaries="bt2020",
        colorspace="bt2020nc",
        audio_codec="aac",
        subtitle_mode="copy",
        audio_stream_count=2,
        container_format="matroska",
        min_duration_seconds=3564.0,
        max_duration_seconds=3636.0,
    )
    restored = OutputContract.from_dict(original.as_dict())
    assert restored == original


def test_contract_as_dict_includes_all_fields():
    c = OutputContract(video_codec="hevc", subtitle_mode="burned")
    d = c.as_dict()
    assert d["video_codec"] == "hevc"
    assert d["subtitle_mode"] == "burned"
    # None fields are still present (serialise as null)
    assert "color_transfer" in d


# ── verify_output: PASS ───────────────────────────────────────────────────────

def test_verify_pass_clean_hevc_encode():
    c = OutputContract(
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        container_format="matroska",
        audio_stream_count=2,
        min_duration_seconds=3564.0,
        max_duration_seconds=3636.0,
    )
    result = _run_verify(
        c,
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        format_name="matroska,webm",
        audio_count=2,
        duration=3600.0,
    )
    assert result.outcome == VerificationOutcome.PASS
    assert not result.errors
    assert not result.warnings


def test_verify_pass_hdr10():
    c = OutputContract(
        video_codec="hevc",
        color_transfer="smpte2084",
        color_primaries="bt2020",
        colorspace="bt2020nc",
    )
    result = _run_verify(
        c,
        video_codec="hevc",
        color_transfer="smpte2084",
        color_primaries="bt2020",
        color_space="bt2020nc",
    )
    assert result.outcome == VerificationOutcome.PASS


# ── verify_output: FAIL (hard mismatches) ────────────────────────────────────

def test_verify_fail_wrong_video_codec():
    c = OutputContract(video_codec="hevc")
    result = _run_verify(c, video_codec="h264")
    assert result.outcome == VerificationOutcome.FAIL
    assert any("codec" in e.lower() for e in result.errors)


def test_verify_fail_hdr_transfer_missing():
    c = OutputContract(color_transfer="smpte2084")
    result = _run_verify(c, color_transfer="")
    assert result.outcome == VerificationOutcome.FAIL
    assert any("washed out" in e.lower() or "transfer" in e.lower() for e in result.errors)


def test_verify_fail_color_primaries_mismatch():
    c = OutputContract(color_primaries="bt2020")
    result = _run_verify(c, color_primaries="bt709")
    assert result.outcome == VerificationOutcome.FAIL
    assert any("primaries" in e.lower() for e in result.errors)


def test_verify_fail_colorspace_mismatch():
    c = OutputContract(colorspace="bt2020nc")
    result = _run_verify(c, color_space="bt709")
    assert result.outcome == VerificationOutcome.FAIL
    assert any("color space" in e.lower() or "colorspace" in e.lower() for e in result.errors)


def test_verify_fail_audio_count_wrong():
    c = OutputContract(audio_stream_count=3)
    result = _run_verify(c, audio_count=2)
    assert result.outcome == VerificationOutcome.FAIL
    assert any("audio" in e.lower() for e in result.errors)


def test_verify_fail_burned_subs_still_present():
    c = OutputContract(subtitle_mode="burned")
    result = _run_verify(c, sub_count=2)
    assert result.outcome == VerificationOutcome.FAIL
    assert any("subtitle" in e.lower() for e in result.errors)


def test_verify_fail_container_mismatch():
    c = OutputContract(container_format="matroska")
    result = _run_verify(c, format_name="mp4")
    assert result.outcome == VerificationOutcome.FAIL
    assert any("container" in e.lower() for e in result.errors)


def test_verify_fail_output_too_short():
    c = OutputContract(min_duration_seconds=3564.0, max_duration_seconds=3636.0)
    result = _run_verify(c, duration=1200.0)
    assert result.outcome == VerificationOutcome.FAIL
    assert any("short" in e.lower() or "truncat" in e.lower() for e in result.errors)


def test_verify_fail_no_video_stream():
    c = OutputContract(video_codec="hevc")
    probe = json.dumps({
        "streams": [{"codec_type": "audio", "codec_name": "aac"}],
        "format": {"format_name": "matroska,webm", "duration": "3600.0"},
    })
    with patch("subprocess.run", return_value=_make_proc(probe)):
        result = verify_output("output.mkv", c)
    assert result.outcome == VerificationOutcome.FAIL
    assert any("no video" in e.lower() for e in result.errors)


# ── verify_output: DEGRADED (soft mismatches) ─────────────────────────────────

def test_verify_degraded_pix_fmt_mismatch():
    c = OutputContract(video_codec="hevc", pix_fmt="yuv420p10le")
    result = _run_verify(c, video_codec="hevc", pix_fmt="yuv420p")
    assert result.outcome == VerificationOutcome.DEGRADED
    assert any("pixel" in w.lower() or "pix_fmt" in w.lower() for w in result.warnings)


def test_verify_degraded_audio_codec_mismatch():
    c = OutputContract(audio_codec="aac")
    result = _run_verify(c, audio_codec="ac3")
    assert result.outcome == VerificationOutcome.DEGRADED
    assert any("audio codec" in w.lower() for w in result.warnings)


def test_verify_degraded_output_slightly_long():
    c = OutputContract(max_duration_seconds=3636.0)
    result = _run_verify(c, duration=3640.0)
    assert result.outcome == VerificationOutcome.DEGRADED
    assert any("duration" in w.lower() or "exceed" in w.lower() for w in result.warnings)


def test_verify_degraded_subtitle_copy_mode_no_streams():
    c = OutputContract(subtitle_mode="copy")
    result = _run_verify(c, sub_count=0)
    assert result.outcome == VerificationOutcome.DEGRADED
    assert any("subtitle" in w.lower() for w in result.warnings)


def test_verify_degraded_subtitle_none_mode_streams_found():
    c = OutputContract(subtitle_mode="none")
    result = _run_verify(c, sub_count=1)
    # subtitle_mode=none → warning, not error
    assert result.outcome == VerificationOutcome.DEGRADED
    assert any("subtitle" in w.lower() for w in result.warnings)


# ── verify_output: ffprobe failure handling ───────────────────────────────────

def test_verify_fail_when_ffprobe_missing():
    import subprocess as sp
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = verify_output("output.mkv", OutputContract())
    assert result.outcome == VerificationOutcome.FAIL
    assert any("ffprobe" in e.lower() for e in result.errors)


def test_verify_fail_when_ffprobe_nonzero_exit():
    with patch("subprocess.run", return_value=_make_proc("", returncode=1)):
        result = verify_output("output.mkv", OutputContract())
    assert result.outcome == VerificationOutcome.FAIL
    assert any("exit" in e.lower() or "code" in e.lower() for e in result.errors)


def test_verify_fail_when_ffprobe_output_not_json():
    with patch("subprocess.run", return_value=_make_proc("not json at all")):
        result = verify_output("output.mkv", OutputContract())
    assert result.outcome == VerificationOutcome.FAIL
    assert any("parse" in e.lower() or "json" in e.lower() for e in result.errors)


# ── verify_output: actual summary ────────────────────────────────────────────

def test_verify_actual_summary_populated():
    c = OutputContract(video_codec="hevc")
    result = _run_verify(
        c,
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        color_transfer="smpte2084",
        color_primaries="bt2020",
        color_space="bt2020nc",
        audio_count=2,
        audio_codec="aac",
        sub_count=1,
        format_name="matroska,webm",
        duration=3600.0,
    )
    assert result.actual["video_codec"]     == "hevc"
    assert result.actual["pix_fmt"]         == "yuv420p10le"
    assert result.actual["color_transfer"]  == "smpte2084"
    assert result.actual["color_primaries"] == "bt2020"
    assert result.actual["colorspace"]      == "bt2020nc"
    assert result.actual["audio_streams"]   == 2
    assert result.actual["audio_codec"]     == "aac"
    assert result.actual["subtitle_streams"] == 1
    assert "matroska" in result.actual["container"]
    assert result.actual["duration_seconds"] == pytest.approx(3600.0)


# ── VerificationResult.passed property ───────────────────────────────────────

def test_passed_true_for_pass():
    r = VerificationResult(outcome=VerificationOutcome.PASS)
    assert r.passed is True


def test_passed_true_for_degraded():
    r = VerificationResult(outcome=VerificationOutcome.DEGRADED)
    assert r.passed is True


def test_passed_false_for_fail():
    r = VerificationResult(outcome=VerificationOutcome.FAIL)
    assert r.passed is False


# ── _select_primary_video ─────────────────────────────────────────────────────

def _vstream(codec="hevc", width=1920, height=1080, pix_fmt="yuv420p10le",
             default=0, attached_pic=0, **extra) -> dict:
    return {
        "codec_type": "video", "codec_name": codec,
        "width": width, "height": height, "pix_fmt": pix_fmt,
        "disposition": {"default": default, "attached_pic": attached_pic},
        **extra,
    }


def test_primary_video_single_stream():
    s = _vstream()
    assert _select_primary_video([s]) == s


def test_primary_video_empty_returns_empty_dict():
    assert _select_primary_video([]) == {}


def test_primary_video_skips_attached_pic():
    cover = _vstream(width=600, height=600, attached_pic=1)
    main  = _vstream(width=1920, height=1080)
    result = _select_primary_video([cover, main])
    assert result["width"] == 1920


def test_primary_video_prefers_default_flagged():
    low_res  = _vstream(width=640,  height=480,  default=1)  # flagged, small
    high_res = _vstream(width=3840, height=2160, default=0)  # unflagged, large
    result = _select_primary_video([high_res, low_res])
    # default flag wins over resolution
    assert result["disposition"]["default"] == 1


def test_primary_video_prefers_higher_resolution_among_equals():
    sd  = _vstream(width=720,  height=576)
    hd  = _vstream(width=1920, height=1080)
    uhd = _vstream(width=3840, height=2160)
    result = _select_primary_video([sd, hd, uhd])
    assert result["width"] == 3840


def test_primary_video_prefers_10bit_over_8bit_same_resolution():
    s8  = _vstream(pix_fmt="yuv420p")
    s10 = _vstream(pix_fmt="yuv420p10le")
    result = _select_primary_video([s8, s10])
    assert "10" in result["pix_fmt"]


def test_primary_video_all_streams_attached_pic_returns_empty():
    """When every video stream is cover art, return empty (no primary video)."""
    covers = [_vstream(attached_pic=1), _vstream(attached_pic=1)]
    assert _select_primary_video(covers) == {}


# Primary audio selection -----------------------------------------------------

def _astream(layout="stereo", channels=2, default=0, index=0, title="", bitrate=0) -> dict:
    stream: dict[str, Any] = {
        "index": index,
        "codec_type": "audio",
        "codec_name": "aac",
        "channel_layout": layout,
        "channels": channels,
        "disposition": {"default": default},
    }
    if title:
        stream["tags"] = {"title": title}
    if bitrate:
        stream["bit_rate"] = str(bitrate)
    return stream


def test_primary_audio_prefers_default_stream():
    commentary = _astream(layout="stereo", channels=2, index=0, title="Commentary")
    main = _astream(layout="5.1(side)", channels=6, default=1, index=1)

    result = _select_primary_audio([commentary, main])

    assert result["channel_layout"] == "5.1(side)"


def test_primary_audio_prefers_more_channels_when_no_default():
    commentary = _astream(layout="stereo", channels=2, index=0, title="Commentary")
    main = _astream(layout="5.1(side)", channels=6, index=1)

    result = _select_primary_audio([commentary, main])

    assert result["channel_layout"] == "5.1(side)"


# ── _container_matches ────────────────────────────────────────────────────────

def test_container_matches_matroska_with_webm_suffix():
    assert _container_matches("matroska", "matroska,webm") is True


def test_container_matches_matroska_exact():
    assert _container_matches("matroska", "matroska") is True


def test_container_matches_mp4_in_mov_compound():
    # ffprobe returns "mov,mp4,m4a,3gp,3g2,mj2" for MP4 files
    assert _container_matches("mp4", "mov,mp4,m4a,3gp,3g2,mj2") is True


def test_container_no_false_positive_from_substring():
    # "mov" must not match "removed" via substring
    assert _container_matches("mov", "removed,garbage") is False


def test_container_no_match_wrong_format():
    assert _container_matches("matroska", "mp4") is False


def test_container_webm_satisfies_matroska():
    # WebM is a restricted subset of Matroska — treated as equivalent
    assert _container_matches("matroska", "webm") is True


# ── Mixed / all-streams audio codec check ────────────────────────────────────

def test_verify_degraded_mixed_audio_codecs():
    """When transcoding to AAC, all tracks must be AAC.  Mixed output is DEGRADED."""
    streams = [
        {"codec_type": "video",  "codec_name": "hevc"},
        {"codec_type": "audio",  "codec_name": "aac"},
        {"codec_type": "audio",  "codec_name": "ac3"},   # wrong codec on track 2
    ]
    probe = json.dumps({
        "streams": streams,
        "format": {"format_name": "matroska,webm", "duration": "3600.0"},
    })
    c = OutputContract(audio_codec="aac")
    with patch("subprocess.run", return_value=_make_proc(probe)):
        result = verify_output("output.mkv", c)
    assert result.outcome == VerificationOutcome.DEGRADED
    assert any("ac3" in w for w in result.warnings)
    assert any("1 track" in w for w in result.warnings)


def test_verify_pass_uniform_audio_codec():
    """All tracks matching the expected codec → no audio warning."""
    streams = [
        {"codec_type": "video", "codec_name": "hevc"},
        {"codec_type": "audio", "codec_name": "aac"},
        {"codec_type": "audio", "codec_name": "aac"},
    ]
    probe = json.dumps({
        "streams": streams,
        "format": {"format_name": "matroska,webm", "duration": "3600.0"},
    })
    c = OutputContract(audio_codec="aac")
    with patch("subprocess.run", return_value=_make_proc(probe)):
        result = verify_output("output.mkv", c)
    assert result.outcome == VerificationOutcome.PASS


# ── build_contract: bitrate bound ─────────────────────────────────────────────

def test_contract_bitrate_bound_set_from_source():
    c = build_contract(_rec(), _analysis(bitrate_bps=20_000_000))
    assert c.min_bitrate_bps == 2_000_000


def test_contract_bitrate_bound_not_punished_by_high_source_bitrate():
    c = build_contract(
        _rec(codec="h265"),
        {
            **_analysis(bitrate_bps=80_000_000),
            "width": 3840,
            "height": 2160,
            "video_codec": "hevc",
        },
    )
    assert c.min_bitrate_bps == 6_900_000


def test_contract_bitrate_bound_catches_bad_low_bitrate_for_compressed_source():
    c = build_contract(
        _rec(codec="h265"),
        {
            **_analysis(bitrate_bps=5_000_000),
            "width": 1920,
            "height": 1080,
            "video_codec": "hevc",
        },
    )
    assert c.min_bitrate_bps == 2_300_000


def test_contract_bitrate_bound_none_when_source_unknown():
    c = build_contract(_rec(), _analysis(bitrate_bps=0))
    assert c.min_bitrate_bps == 2_000_000


# ── build_contract: audio layout ──────────────────────────────────────────────

def test_contract_audio_layout_populated_from_analysis():
    c = build_contract(_rec(), _analysis(audio_channel_layout="5.1(side)"))
    assert c.audio_layout == "5.1(side)"


def test_contract_audio_layout_uses_primary_audio_stream():
    analysis = _analysis(
        audio_streams=[
            _astream(layout="stereo", channels=2, index=0, title="Commentary"),
            _astream(layout="5.1(side)", channels=6, default=1, index=1),
        ],
        audio_channel_layout="stereo",
    )
    c = build_contract(_rec(), analysis)
    assert c.audio_layout == "5.1(side)"


def test_contract_audio_layout_none_when_not_in_analysis():
    c = build_contract(_rec(), _analysis())
    assert c.audio_layout is None


# ── verify_output: bitrate collapse ───────────────────────────────────────────

def test_verify_fail_bitrate_collapse():
    c = OutputContract(min_bitrate_bps=5_000_000)
    result = _run_verify(c, bit_rate=100_000)  # 100 kbps << 5 Mbps floor
    assert result.outcome == VerificationOutcome.FAIL
    assert any("bitrate collapse" in e.lower() for e in result.errors)


def test_verify_pass_bitrate_above_floor():
    c = OutputContract(min_bitrate_bps=1_000_000)
    result = _run_verify(c, bit_rate=8_000_000)
    assert result.outcome == VerificationOutcome.PASS


def test_verify_pass_bitrate_check_skipped_when_probe_has_no_bitrate():
    """ffprobe output without bit_rate → check is skipped, not a false FAIL."""
    c = OutputContract(min_bitrate_bps=5_000_000)
    result = _run_verify(c)  # no bit_rate in probe JSON
    assert result.outcome == VerificationOutcome.PASS


# ── verify_output: audio layout ───────────────────────────────────────────────

def test_verify_fail_audio_layout_mismatch():
    c = OutputContract(audio_layout="5.1(side)")
    result = _run_verify(c, audio_layout="stereo")
    assert result.outcome == VerificationOutcome.FAIL
    assert any("audio layout mismatch" in e.lower() for e in result.errors)


def test_verify_pass_audio_layout_matches():
    c = OutputContract(audio_layout="5.1(side)")
    result = _run_verify(c, audio_layout="5.1(side)")
    assert result.outcome == VerificationOutcome.PASS


def test_verify_audio_layout_uses_primary_audio_stream_not_index_zero():
    streams = [
        {"codec_type": "video", "codec_name": "hevc"},
        _astream(layout="stereo", channels=2, index=0, title="Commentary"),
        _astream(layout="5.1(side)", channels=6, default=1, index=1),
    ]
    probe = json.dumps({
        "streams": streams,
        "format": {"format_name": "matroska,webm", "duration": "3600.0"},
    })
    c = OutputContract(audio_layout="5.1(side)")
    with patch("subprocess.run", return_value=_make_proc(probe)):
        result = verify_output("output.mkv", c)
    assert result.outcome == VerificationOutcome.PASS
    assert result.actual["audio_layout"] == "5.1(side)"


def test_verify_pass_audio_layout_skipped_when_no_audio_streams():
    """Layout check is skipped when there are no audio streams to compare."""
    c = OutputContract(audio_layout="5.1(side)")
    result = _run_verify(c, audio_count=0)
    assert result.outcome == VerificationOutcome.PASS


# ── verify_output: actual summary includes new fields ─────────────────────────

def test_verify_actual_includes_bitrate_and_layout():
    c = OutputContract()
    result = _run_verify(c, audio_layout="stereo", bit_rate=8_000_000)
    assert result.actual["bitrate_bps"] == 8_000_000
    assert result.actual["audio_layout"] == "stereo"


# ── contract_diff ─────────────────────────────────────────────────────────────

def test_contract_diff_reports_codec_mismatch():
    c = OutputContract(video_codec="hevc")
    actual = {"video_codec": "h264"}
    diff = contract_diff(c, actual)
    assert "video_codec" in diff
    assert diff["video_codec"]["expected"] == "hevc"
    assert diff["video_codec"]["actual"] == "h264"


def test_contract_diff_empty_when_all_match():
    c = OutputContract(video_codec="hevc", pix_fmt="yuv420p10le")
    actual = {"video_codec": "hevc", "pix_fmt": "yuv420p10le"}
    assert contract_diff(c, actual) == {}


def test_contract_diff_skips_none_contract_fields():
    c = OutputContract(video_codec=None, pix_fmt=None)
    actual = {"video_codec": "hevc", "pix_fmt": "yuv420p"}
    assert contract_diff(c, actual) == {}


def test_contract_diff_reports_audio_stream_count_mismatch():
    c = OutputContract(audio_stream_count=3)
    actual = {"audio_streams": 2}
    diff = contract_diff(c, actual)
    assert "audio_stream_count" in diff
    assert diff["audio_stream_count"]["expected"] == 3


def test_contract_diff_reports_duration_below_minimum():
    c = OutputContract(min_duration_seconds=3564.0)
    actual = {"duration_seconds": 1200.0}
    diff = contract_diff(c, actual)
    assert "duration_seconds" in diff
    assert "3564" in diff["duration_seconds"]["expected"]


def test_contract_diff_reports_bitrate_collapse():
    c = OutputContract(min_bitrate_bps=5_000_000)
    actual = {"bitrate_bps": 100_000}
    diff = contract_diff(c, actual)
    assert "bitrate_bps" in diff
    assert diff["bitrate_bps"]["actual"] == 100_000
