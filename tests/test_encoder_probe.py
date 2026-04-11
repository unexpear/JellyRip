"""Tests for transcode.encoder_probe."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from transcode.encoder_probe import (
    available_encoders,
    encoder_available,
    resolve_hw_accel,
    GPU_ENCODERS,
)


# Minimal fragment from a real `ffmpeg -encoders` output.
_ENCODERS_OUTPUT = """\
Encoders:
 V..... = Video
 A..... = Audio
 S..... = Subtitle
 .F.... = Frame-level multithreading
 ..S... = Slice-level multithreading
 ...X.. = Codec is experimental
 ....B. = Supports draw_horiz_band
 .....D = Supports direct rendering method 1
 ------
 V....D libx265             libx265 H.265 / HEVC
 V....D libx264             libx264 H.264 / AVC
 V....D hevc_nvenc          NVIDIA NVENC hevc encoder
 V....D h264_nvenc          NVIDIA NVENC H264 encoder
 A....D aac                 AAC (Advanced Audio Coding)
 A....D libopus             libopus Opus
"""


def _make_proc(stdout: str, returncode: int = 0) -> MagicMock:
    proc = MagicMock()
    proc.stdout = stdout
    proc.returncode = returncode
    return proc


# ── Parsing ──────────────────────────────────────────────────────────────────

def test_parses_known_encoders():
    with patch("subprocess.run", return_value=_make_proc(_ENCODERS_OUTPUT)):
        available_encoders.cache_clear()
        encoders = available_encoders("ffmpeg")
    assert "libx265" in encoders
    assert "libx264" in encoders
    assert "hevc_nvenc" in encoders
    assert "h264_nvenc" in encoders
    assert "aac" in encoders
    assert "libopus" in encoders


def test_does_not_include_header_lines():
    with patch("subprocess.run", return_value=_make_proc(_ENCODERS_OUTPUT)):
        available_encoders.cache_clear()
        encoders = available_encoders("ffmpeg")
    assert "Encoders:" not in encoders
    assert "Video" not in encoders
    assert "------" not in encoders


# ── Error handling ────────────────────────────────────────────────────────────

def test_returns_empty_frozenset_when_binary_not_found():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        available_encoders.cache_clear()
        result = available_encoders("missing_ffmpeg")
    assert result == frozenset()


def test_returns_empty_frozenset_on_timeout():
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ffmpeg", 10)):
        available_encoders.cache_clear()
        result = available_encoders("ffmpeg")
    assert result == frozenset()


def test_returns_empty_frozenset_on_oserror():
    with patch("subprocess.run", side_effect=OSError("permission denied")):
        available_encoders.cache_clear()
        result = available_encoders("ffmpeg")
    assert result == frozenset()


# ── encoder_available ─────────────────────────────────────────────────────────

def test_encoder_available_true_for_known_encoder():
    with patch("subprocess.run", return_value=_make_proc(_ENCODERS_OUTPUT)):
        available_encoders.cache_clear()
        assert encoder_available("libx265", "ffmpeg") is True


def test_encoder_available_false_for_missing_encoder():
    with patch("subprocess.run", return_value=_make_proc(_ENCODERS_OUTPUT)):
        available_encoders.cache_clear()
        assert encoder_available("hevc_qsv", "ffmpeg") is False


def test_encoder_available_false_when_probe_fails():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        available_encoders.cache_clear()
        # Empty frozenset → False (safe default)
        assert encoder_available("libx265", "ffmpeg") is False


# ── GPU_ENCODERS constant ─────────────────────────────────────────────────────

def test_gpu_encoders_contains_expected_names():
    assert "hevc_nvenc" in GPU_ENCODERS
    assert "hevc_qsv"   in GPU_ENCODERS
    assert "hevc_amf"   in GPU_ENCODERS
    assert "h264_nvenc" in GPU_ENCODERS
    # CPU encoders must not be in the set
    assert "libx265" not in GPU_ENCODERS
    assert "libx264" not in GPU_ENCODERS


# ── resolve_hw_accel ──────────────────────────────────────────────────────────

def test_resolve_cpu_passthrough():
    # "cpu" always passes through unchanged — no probe needed.
    resolved, reason = resolve_hw_accel("cpu", "h265", "ffmpeg")
    assert resolved == "cpu"
    assert reason is None


def test_resolve_auto_prefer_passthrough():
    resolved, reason = resolve_hw_accel("auto_prefer", "h265", "ffmpeg")
    assert resolved == "auto_prefer"
    assert reason is None


def test_resolve_nvenc_available():
    with patch("subprocess.run", return_value=_make_proc(_ENCODERS_OUTPUT)):
        available_encoders.cache_clear()
        resolved, reason = resolve_hw_accel("nvenc", "h265", "ffmpeg")
    assert resolved == "nvenc"
    assert reason is None


def test_resolve_nvenc_unavailable_falls_back_to_cpu():
    # Build with no GPU encoders.
    output_no_gpu = _ENCODERS_OUTPUT.replace("hevc_nvenc", "").replace("h264_nvenc", "")
    with patch("subprocess.run", return_value=_make_proc(output_no_gpu)):
        available_encoders.cache_clear()
        resolved, reason = resolve_hw_accel("nvenc", "h265", "ffmpeg")
    assert resolved == "cpu"
    assert reason is not None
    assert "nvenc" in reason.lower() or "hevc_nvenc" in reason.lower()


def test_resolve_qsv_unavailable_falls_back_to_cpu():
    with patch("subprocess.run", return_value=_make_proc(_ENCODERS_OUTPUT)):
        available_encoders.cache_clear()
        # hevc_qsv is not in _ENCODERS_OUTPUT
        resolved, reason = resolve_hw_accel("qsv", "h265", "ffmpeg")
    assert resolved == "cpu"
    assert reason is not None


def test_resolve_probe_failure_does_not_change_hw_accel():
    # When the probe fails we cannot confirm availability — don't block.
    with patch("subprocess.run", side_effect=FileNotFoundError):
        available_encoders.cache_clear()
        resolved, reason = resolve_hw_accel("nvenc", "h265", "ffmpeg")
    assert resolved == "nvenc"
    assert reason is None


def test_resolve_unknown_combination_passthrough():
    # An unrecognised hw_accel/codec pair is left alone.
    with patch("subprocess.run", return_value=_make_proc(_ENCODERS_OUTPUT)):
        available_encoders.cache_clear()
        resolved, reason = resolve_hw_accel("someother", "h265", "ffmpeg")
    assert resolved == "someother"
    assert reason is None
