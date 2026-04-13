from __future__ import annotations

import re
import subprocess
from functools import lru_cache

_ENCODER_LINE = re.compile(r"^\s*[VAS][F.][S.][X.][B.][D.]\s+(\S+)")

# ── FFmpeg minimum version ────────────────────────────────────────────────────
# 4.0 (April 2018) introduced reliable hevc_nvenc CRF-quality support and
# the -disposition:s:0 stream-specifier syntax that JellyRip emits.
_MIN_FFMPEG_VERSION: tuple[int, int, int] = (4, 0, 0)
_MIN_FFMPEG_BUILD_YEAR: int = 2018

_RELEASE_VERSION_RE = re.compile(r"ffmpeg version (\d+)\.(\d+)(?:\.(\d+))?")
_BUILD_YEAR_RE      = re.compile(r"built on \w+\s+\d+\s+(\d{4})")

# Hardware encoder names the rest of the pipeline cares about.
GPU_ENCODERS: frozenset[str] = frozenset({
    "h264_nvenc", "hevc_nvenc",
    "h264_qsv",   "hevc_qsv",
    "h264_amf",   "hevc_amf",
})


@lru_cache(maxsize=8)
def available_encoders(ffmpeg_exe: str = "ffmpeg") -> frozenset[str]:
    """Return the set of encoder names reported by ``ffmpeg -encoders``.

    Results are cached per executable path so the subprocess is only
    spawned once per session.  Returns an empty frozenset when the binary
    cannot be found or times out — callers must treat an empty set as
    "unknown" rather than "none available".
    """
    try:
        proc = subprocess.run(
            [ffmpeg_exe, "-encoders", "-v", "quiet"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        names: set[str] = set()
        for line in proc.stdout.splitlines():
            m = _ENCODER_LINE.match(line)
            if m:
                names.add(m.group(1))
        return frozenset(names)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return frozenset()


@lru_cache(maxsize=8)
def get_ffmpeg_version_info(ffmpeg_exe: str = "ffmpeg") -> dict:
    """Probe *ffmpeg_exe* and return version metadata.

    Returns a dict with keys:
    - ``"release"`` — ``(major, minor, patch)`` tuple, or ``None`` for dev builds
      whose version string starts with ``N-``.
    - ``"build_year"`` — the integer year parsed from the ``built on`` line, or ``None``.
    - ``"label"`` — human-readable version string (e.g. ``"6.1.1"`` or
      ``"N-55702-g920046a"``).
    - ``"too_old"`` — ``True`` when the build is known to be below the minimum
      requirement (either release version < 4.0.0, or build year < 2018).
    """
    info: dict = {"release": None, "build_year": None, "label": "unknown", "too_old": False}
    try:
        proc = subprocess.run(
            [ffmpeg_exe, "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        text = proc.stdout

        m_ver = _RELEASE_VERSION_RE.search(text)
        if m_ver:
            v = (int(m_ver.group(1)), int(m_ver.group(2)), int(m_ver.group(3) or "0"))
            info["release"] = v
            info["label"] = f"{v[0]}.{v[1]}.{v[2]}"
            if v < _MIN_FFMPEG_VERSION:
                info["too_old"] = True
        else:
            m_str = re.search(r"ffmpeg version (\S+)", text)
            if m_str:
                info["label"] = m_str.group(1)

        m_year = _BUILD_YEAR_RE.search(text)
        if m_year:
            year = int(m_year.group(1))
            info["build_year"] = year
            if year < _MIN_FFMPEG_BUILD_YEAR and not info["too_old"]:
                info["too_old"] = True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return info


def encoder_available(encoder: str, ffmpeg_exe: str = "ffmpeg") -> bool:
    """Return True when *encoder* appears in ``ffmpeg -encoders`` output.

    Returns False for unknown encoders only when the probe succeeds.
    When the binary cannot be found the probe returns an empty set; this
    function then returns False, which is the safe default.
    """
    return encoder in available_encoders(ffmpeg_exe)


# Map of (hw_accel, codec) → the actual encoder name FFmpeg uses.
_ENCODER_FOR_ACCEL: dict[tuple[str, str], str] = {
    ("nvenc", "h265"): "hevc_nvenc",
    ("nvenc", "h264"): "h264_nvenc",
    ("qsv",   "h265"): "hevc_qsv",
    ("qsv",   "h264"): "h264_qsv",
    ("amf",   "h265"): "hevc_amf",
    ("amf",   "h264"): "h264_amf",
}


def resolve_hw_accel(
    hw_accel: str,
    codec: str = "h265",
    ffmpeg_exe: str = "ffmpeg",
) -> tuple[str, str | None]:
    """Check whether *hw_accel* is available and return the resolved value.

    Returns ``(resolved_hw_accel, fallback_reason)``.

    * ``"cpu"`` and ``"auto_prefer"`` pass through unchanged — ``"cpu"``
      needs no check; ``"auto_prefer"`` lets FFmpeg decide at runtime.
    * When the requested encoder is available, or when the probe failed
      (empty frozenset = binary missing), returns ``(hw_accel, None)``.
    * When the encoder is definitively *not* listed in this build, returns
      ``("cpu", reason)`` so the caller can adapt before queuing the job.
    """
    if hw_accel in ("cpu", "auto_prefer"):
        return hw_accel, None

    encoder = _ENCODER_FOR_ACCEL.get((hw_accel, codec))
    if encoder is None:
        # Unknown hw_accel/codec combination — don't interfere.
        return hw_accel, None

    known = available_encoders(ffmpeg_exe)
    if not known:
        # Probe failed — treat as unknown rather than blocking.
        return hw_accel, None

    if encoder in known:
        return hw_accel, None

    return "cpu", (
        f"Requested encoder '{encoder}' ({hw_accel}) is not available "
        f"in this FFmpeg build; falling back to CPU (libx265)."
    )
