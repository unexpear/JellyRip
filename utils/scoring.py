"""Scoring utilities implementation."""

from collections.abc import Mapping, Sequence

from .parsing import safe_int

Title = Mapping[str, object]
AudioTrack = Mapping[str, object]


def _numeric_field(title: Title, key: str) -> float:
    value = title.get(key, 0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def _sequence_length(title: Title, key: str) -> int:
    value = title.get(key, [])
    return len(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else 0


def score_title(t: Title, all_titles: Sequence[Title]) -> float:
    """
    Score a title relative to all titles on the disc.
    Returns a float 0.0-1.0. Higher = more likely to be the main feature.

    All five signals are normalized against the disc maximum so they
    contribute equally regardless of absolute scale. Weighting:
      0.35 duration  - most reliable signal, hard to fake
      0.30 size      - correlates with quality and length
      0.15 chapters  - main features are chaptered, extras often aren't
      0.15 audio     - more tracks = more likely primary content
      0.05 subtitles - weak signal but breaks ties

    This beats size-only selection on Blu-rays with obfuscation titles
    because fake titles fail across multiple axes simultaneously.
    """
    if not all_titles:
        return 0.0

    title_count = len(all_titles)

    max_size = max((_numeric_field(x, "size_bytes") for x in all_titles), default=0.0)
    max_duration = max((_numeric_field(x, "duration_seconds") for x in all_titles), default=0.0)
    max_chapters = max((safe_int(x.get("chapters")) for x in all_titles), default=0)
    max_audio = max((_sequence_length(x, "audio_tracks") for x in all_titles), default=0)
    max_subs = max((_sequence_length(x, "subtitle_tracks") for x in all_titles), default=0)

    duration_present = sum(1 for x in all_titles if _numeric_field(x, "duration_seconds") > 0)
    size_present = sum(1 for x in all_titles if _numeric_field(x, "size_bytes") > 0)
    chapters_present = sum(1 for x in all_titles if safe_int(x.get("chapters")) > 0)
    audio_present = sum(1 for x in all_titles if _sequence_length(x, "audio_tracks") > 0)
    subs_present = sum(1 for x in all_titles if _sequence_length(x, "subtitle_tracks") > 0)

    coverage_threshold = max(1, (title_count + 1) // 2)

    size_bytes = _numeric_field(t, "size_bytes")
    duration_seconds = _numeric_field(t, "duration_seconds")
    chapters = safe_int(t.get("chapters"))

    components: list[tuple[float, float]] = []
    if max_duration > 0 and duration_present >= coverage_threshold:
        components.append((duration_seconds / max_duration, 0.35))
    if max_size > 0 and size_present >= coverage_threshold:
        components.append((size_bytes / max_size, 0.30))
    if max_chapters > 0 and chapters_present >= coverage_threshold:
        components.append((chapters / max_chapters, 0.15))
    if max_audio > 0 and audio_present >= coverage_threshold:
        components.append((_sequence_length(t, "audio_tracks") / max_audio, 0.15))
    if max_subs > 0 and subs_present >= coverage_threshold:
        components.append((_sequence_length(t, "subtitle_tracks") / max_subs, 0.05))

    if not components:
        return 0.0

    total_weight = sum(weight for _, weight in components)
    if total_weight <= 0:
        return 0.0

    return sum(value * (weight / total_weight) for value, weight in components)


def choose_best_title(disc_titles: Sequence[Title], require_valid: bool = False) -> tuple[Title | None, float]:
    """Select best title by score; optionally gate invalid candidates."""
    if not disc_titles:
        return None, 0.0

    candidates: Sequence[Title] = disc_titles
    if require_valid:
        valid = [
            t for t in disc_titles
            if _numeric_field(t, "size_bytes") > 0 and _numeric_field(t, "duration_seconds") > 0
        ]
        if valid:
            candidates = valid

    scored = [(t, score_title(t, disc_titles)) for t in candidates]
    best, best_score = max(scored, key=lambda x: x[1])
    return best, best_score


def format_audio_summary(audio_tracks: Sequence[AudioTrack]) -> str:
    """Format audio track list as a readable string for the disc tree UI."""
    if not audio_tracks:
        return "-"

    parts: list[str] = []
    for track in audio_tracks:
        lang_value = track.get("lang_name") or track.get("lang") or ""
        codec_value = track.get("codec", "")
        channels_value = track.get("channels", "")
        label = " ".join(
            part for part in (str(lang_value).strip(), str(codec_value).strip(), str(channels_value).strip()) if part
        ).strip()
        if label:
            parts.append(label)
    return ", ".join(parts) if parts else "-"


__all__ = ["choose_best_title", "format_audio_summary", "score_title"]
