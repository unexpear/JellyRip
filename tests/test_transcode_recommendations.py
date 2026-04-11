import json

from transcode.recommendations import (
    build_ffmpeg_recommendations,
    format_analysis_summary,
    probe_media_for_recommendation,
)


def test_probe_media_for_recommendation_parses_ffprobe_json(monkeypatch, tmp_path):
    sample = tmp_path / "sample.mkv"
    sample.write_text("x", encoding="utf-8")

    class _Result:
        returncode = 0
        stderr = ""
        stdout = json.dumps(
            {
                "format": {
                    "duration": "600.25",
                    "size": "2147483648",
                    "bit_rate": "12000000",
                },
                "streams": [
                    {
                        "codec_type": "video",
                        "codec_name": "h264",
                        "profile": "High 10",
                        "width": 1920,
                        "height": 1080,
                        "pix_fmt": "yuv420p",
                        "bits_per_raw_sample": "10",
                        "color_transfer": "smpte2084",
                        "color_primaries": "bt2020",
                        "color_space": "bt2020nc",
                        "avg_frame_rate": "24000/1001",
                    },
                    {
                        "index": 1,
                        "codec_type": "audio",
                        "channel_layout": "stereo",
                        "channels": 2,
                        "tags": {"title": "Commentary"},
                    },
                    {
                        "index": 2,
                        "codec_type": "audio",
                        "channel_layout": "5.1(side)",
                        "channels": 6,
                        "disposition": {"default": 1},
                    },
                    {"codec_type": "subtitle"},
                ],
            }
        )

    monkeypatch.setattr(
        "transcode.recommendations.subprocess.run",
        lambda *args, **kwargs: _Result(),
    )

    analysis = probe_media_for_recommendation(str(sample), "ffprobe.exe")

    assert analysis["video_codec"] == "h264"
    assert analysis["width"] == 1920
    assert analysis["height"] == 1080
    assert analysis["audio_streams"] == 2
    assert analysis["subtitle_streams"] == 1
    assert round(analysis["fps"], 2) == 23.98
    assert analysis["bitrate_bps"] == 12000000
    assert analysis["profile"] == "High 10"
    assert analysis["bit_depth"] == 10
    assert analysis["color_transfer"] == "smpte2084"
    assert analysis["color_primaries"] == "bt2020"
    assert analysis["audio_channel_layout"] == "5.1(side)"


def test_build_ffmpeg_recommendations_prefers_balanced_for_large_h264():
    analysis = {
        "path": "movie.mkv",
        "name": "movie.mkv",
        "size_bytes": 28 * 1024**3,
        "duration_seconds": 7200.0,
        "bitrate_bps": 25000000,
        "video_codec": "h264",
        "width": 1920,
        "height": 1080,
        "pix_fmt": "yuv420p",
        "fps": 23.976,
        "audio_streams": 1,
        "subtitle_streams": 1,
    }

    result = build_ffmpeg_recommendations(analysis)

    assert result["recommended_id"] == "balanced"
    assert len(result["recommendations"]) == 3
    labels = {rec["id"]: rec["label"] for rec in result["recommendations"]}
    assert labels == {
        "smaller_file": "Save Space",
        "balanced": "Best Overall",
        "higher_quality": "Keep More Quality",
    }
    balanced = next(rec for rec in result["recommendations"] if rec["id"] == "balanced")
    assert balanced["crf"] == 20
    assert balanced["preset"] == "medium"
    assert "candidate" in result["advisory"].lower()


def test_build_ffmpeg_recommendations_warns_when_hevc_is_already_efficient():
    analysis = {
        "path": "movie.mkv",
        "name": "movie.mkv",
        "size_bytes": 6 * 1024**3,
        "duration_seconds": 7200.0,
        "bitrate_bps": 5000000,
        "video_codec": "hevc",
        "width": 1920,
        "height": 1080,
        "pix_fmt": "yuv420p10le",
        "fps": 23.976,
        "audio_streams": 1,
        "subtitle_streams": 0,
    }

    result = build_ffmpeg_recommendations(analysis)

    assert result["recommended_id"] == "higher_quality"
    assert "already" in result["advisory"].lower()
    assert result["decision_factors"]
    assert result["source_notes"]


def test_build_ffmpeg_recommendations_is_conservative_for_4k_hdr_hevc():
    analysis = {
        "path": "movie.mkv",
        "name": "movie.mkv",
        "size_bytes": 69 * 1024**3,
        "duration_seconds": 7200.0,
        "bitrate_bps": 70000000,
        "video_codec": "hevc",
        "profile": "Main 10",
        "width": 3840,
        "height": 2160,
        "pix_fmt": "yuv420p10le",
        "bit_depth": 10,
        "color_transfer": "smpte2084",
        "color_primaries": "bt2020",
        "color_space": "bt2020nc",
        "fps": 23.976,
        "audio_streams": 2,
        "subtitle_streams": 3,
    }

    result = build_ffmpeg_recommendations(analysis)

    assert result["recommended_id"] == "higher_quality"
    assert "sample" in result["advisory"].lower()
    assert any("HDR" in factor for factor in result["decision_factors"])
    higher_quality = next(
        rec for rec in result["recommendations"] if rec["id"] == "higher_quality"
    )
    assert higher_quality["crf"] == 18
    assert "4K/HDR" in higher_quality["best_for"]
    assert higher_quality["caution"]


def test_format_analysis_summary_includes_human_readable_lines():
    analysis = {
        "path": "movie.mkv",
        "name": "movie.mkv",
        "size_bytes": 10 * 1024**3,
        "duration_seconds": 3661.0,
        "bitrate_bps": 10000000,
        "video_codec": "h264",
        "width": 1920,
        "height": 1080,
        "pix_fmt": "yuv420p",
        "fps": 24.0,
        "audio_streams": 2,
        "subtitle_streams": 3,
    }

    lines = format_analysis_summary(analysis)

    assert any("1920x1080" in line for line in lines)
    assert any("1:01:01" in line for line in lines)
    assert any("10.00 GB" in line for line in lines)


# ---------------------------------------------------------------------------
# Profile-data fixture tests — verify recommendations carry the right encoding
# parameters for different source characteristics, not just structure.
# ---------------------------------------------------------------------------

def _make_analysis(**overrides):
    """Minimal analysis dict; callers supply source-specific fields."""
    base = {
        "path": "movie.mkv",
        "name": "movie.mkv",
        "size_bytes": 20 * 1024**3,
        "duration_seconds": 7200.0,
        "bitrate_bps": 20_000_000,
        "video_codec": "h264",
        "width": 1920,
        "height": 1080,
        "pix_fmt": "yuv420p",
        "fps": 23.976,
        "audio_streams": 1,
        "subtitle_streams": 1,
    }
    base.update(overrides)
    return base


def _all_profile_data(analysis):
    """Return profile_data dicts for all three recommendations."""
    result = build_ffmpeg_recommendations(analysis)
    return [rec["profile_data"] for rec in result["recommendations"]]


def test_recommendation_profile_8bit_sdr_seeds_yuv420p_main():
    analysis = _make_analysis(video_codec="h264", pix_fmt="yuv420p", bit_depth=8)
    for pd in _all_profile_data(analysis):
        assert pd["video"]["pix_fmt"] == "yuv420p"
        assert pd["video"]["video_profile"] == "main"
        assert pd["video"]["extra_video_params"] is None


def test_recommendation_profile_10bit_sdr_seeds_yuv420p10le_no_color_params():
    # 10-bit without HDR transfer → depth preserved but no HDR signaling
    analysis = _make_analysis(
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        bit_depth=10,
    )
    for pd in _all_profile_data(analysis):
        assert pd["video"]["pix_fmt"] == "yuv420p10le"
        assert pd["video"]["video_profile"] == "main10"
        assert pd["video"]["extra_video_params"] is None


def test_recommendation_profile_hdr10_seeds_full_color_params():
    analysis = _make_analysis(
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        bit_depth=10,
        color_transfer="smpte2084",
        color_primaries="bt2020",
        color_space="bt2020nc",
    )
    for pd in _all_profile_data(analysis):
        assert pd["video"]["pix_fmt"] == "yuv420p10le"
        assert pd["video"]["video_profile"] == "main10"
        params = pd["video"]["extra_video_params"] or ""
        assert "colorprim=bt2020" in params
        assert "transfer=smpte2084" in params
        assert "colormatrix=bt2020nc" in params
        assert "hdr-opt=1" in params


def test_recommendation_profile_hlg_seeds_hlg_color_params():
    analysis = _make_analysis(
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        bit_depth=10,
        color_transfer="arib-std-b67",
        color_primaries="bt2020",
        color_space="bt2020nc",
    )
    for pd in _all_profile_data(analysis):
        params = pd["video"]["extra_video_params"] or ""
        assert "transfer=arib-std-b67" in params
        assert "colorprim=bt2020" in params
        assert "colormatrix=bt2020nc" in params
        assert "hdr-opt=1" not in params  # HLG does not signal HDR10


def test_recommendation_profile_bt2020_sdr_seeds_10bit_no_hdr_params():
    # BT.2020 primaries but no HDR transfer — preserve bit depth, omit HDR signaling
    analysis = _make_analysis(
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        bit_depth=10,
        color_primaries="bt2020",
        color_space="bt2020nc",
    )
    for pd in _all_profile_data(analysis):
        assert pd["video"]["pix_fmt"] == "yuv420p10le"
        assert pd["video"]["video_profile"] == "main10"
        assert pd["video"]["extra_video_params"] is None


def test_recommendation_profile_unknown_depth_seeds_none():
    # No pix_fmt, no bit_depth — ffmpeg picks the defaults
    analysis = _make_analysis(pix_fmt="", bit_depth=0)
    for pd in _all_profile_data(analysis):
        assert pd["video"]["pix_fmt"] is None
        assert pd["video"]["video_profile"] is None
        assert pd["video"]["extra_video_params"] is None


def test_recommendation_profile_hdr10_bt2020c_uses_correct_colormatrix():
    # Constant-luminance BT.2020 (rare) maps to bt2020c, not bt2020nc
    analysis = _make_analysis(
        video_codec="hevc",
        pix_fmt="yuv420p10le",
        bit_depth=10,
        color_transfer="smpte2084",
        color_primaries="bt2020",
        color_space="bt2020c",
    )
    for pd in _all_profile_data(analysis):
        params = pd["video"]["extra_video_params"] or ""
        assert "colormatrix=bt2020c" in params
        assert "colormatrix=bt2020nc" not in params
