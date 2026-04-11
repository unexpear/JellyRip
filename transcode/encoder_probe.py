from __future__ import annotations

import re
import subprocess
from functools import lru_cache

_ENCODER_LINE = re.compile(r"^\s*[VAS][F.][S.][X.][B.][D.]\s+(\S+)")

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
