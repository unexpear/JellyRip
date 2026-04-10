from __future__ import annotations

import os
from typing import TypedDict

from .engine import (
    FFMPEG_SOURCE_MODE_FAST_DIRECT,
    FFMPEG_SOURCE_MODE_SAFE_COPY,
    normalize_ffmpeg_source_mode,
)


class TranscodePlan(TypedDict):
    input_path: str
    relative_path: str
    output_relative_path: str
    output_path: str


FFMPEG_SOURCE_MODE_VALUE_TO_LABEL = {
    FFMPEG_SOURCE_MODE_SAFE_COPY: "Safe (Copy First)",
    FFMPEG_SOURCE_MODE_FAST_DIRECT: "Fast (Read Original)",
}
FFMPEG_SOURCE_MODE_LABEL_TO_VALUE = {
    label: value for value, label in FFMPEG_SOURCE_MODE_VALUE_TO_LABEL.items()
}


def ffmpeg_source_mode_label(value: str) -> str:
    normalized = normalize_ffmpeg_source_mode(value)
    return FFMPEG_SOURCE_MODE_VALUE_TO_LABEL.get(
        normalized,
        FFMPEG_SOURCE_MODE_VALUE_TO_LABEL[FFMPEG_SOURCE_MODE_SAFE_COPY],
    )


def transcode_backend_label(backend: str) -> str:
    return "HandBrake" if str(backend).strip().lower() == "handbrake" else "FFmpeg"


def suggest_transcode_output_root(scan_root: str, backend: str) -> str:
    normalized_root = os.path.normpath(scan_root)
    trimmed_root = normalized_root.rstrip("\\/")
    parent = os.path.dirname(trimmed_root)
    if not parent:
        drive, _tail = os.path.splitdrive(trimmed_root)
        parent = (drive + os.sep) if drive else normalized_root
    folder_name = os.path.basename(trimmed_root) or "MKVs"
    suffix = (
        "HandBrake Output"
        if str(backend).strip().lower() == "handbrake"
        else "FFmpeg Output"
    )
    return os.path.join(parent, f"{folder_name} - {suffix}")


def build_transcode_plan(
    scan_root: str,
    selected_paths: list[str],
    output_root: str,
) -> list[TranscodePlan]:
    normalized_root = os.path.normpath(scan_root)
    normalized_output = os.path.normpath(output_root)
    plans: list[TranscodePlan] = []
    seen_paths: set[str] = set()

    for input_path in selected_paths:
        normalized_input = os.path.normpath(input_path)
        dedupe_key = os.path.normcase(normalized_input)
        if dedupe_key in seen_paths:
            continue
        seen_paths.add(dedupe_key)

        try:
            relative_path = os.path.relpath(normalized_input, normalized_root)
        except ValueError:
            relative_path = os.path.basename(normalized_input)

        if relative_path.startswith(".."):
            relative_path = os.path.basename(normalized_input)

        relative_base, _relative_ext = os.path.splitext(relative_path)
        output_relative_path = f"{relative_base}.mkv"
        plans.append(
            {
                "input_path": normalized_input,
                "relative_path": os.path.normpath(relative_path),
                "output_relative_path": os.path.normpath(output_relative_path),
                "output_path": os.path.normpath(
                    os.path.join(normalized_output, output_relative_path)
                ),
            }
        )

    return plans
