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
                        "width": 1920,
                        "height": 1080,
                        "pix_fmt": "yuv420p",
                        "avg_frame_rate": "24000/1001",
                    },
                    {"codec_type": "audio"},
                    {"codec_type": "audio"},
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
