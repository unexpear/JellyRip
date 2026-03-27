"""Scoring utilities implementation."""

from .parsing import safe_int


def score_title(t, all_titles):
    """
    Score a title relative to all titles on the disc.
    Returns a float 0.0-1.0. Higher = more likely to be the main feature.

    All five signals are normalized against the disc maximum so they
    contribute equally regardless of absolute scale. Weighting:
      0.35 duration  — most reliable signal, hard to fake
      0.30 size      — correlates with quality and length
      0.15 chapters  — main features are chaptered, extras often aren't
      0.15 audio     — more tracks = more likely primary content
      0.05 subtitles — weak signal but breaks ties

    This beats size-only selection on Blu-rays with obfuscation titles
    because fake titles fail across multiple axes simultaneously.
    """
    if not all_titles:
        return 0.0
    
    title_count = len(all_titles)

    max_size     = max(
        (
            x.get("size_bytes", 0)
            if isinstance(x.get("size_bytes"), (int, float)) else 0
            for x in all_titles
        ),
        default=0
    )
    max_duration = max(
        (
            x.get("duration_seconds", 0)
            if isinstance(x.get("duration_seconds"), (int, float)) else 0
            for x in all_titles
        ),
        default=0
    )
    max_chapters = max(
        (safe_int(x.get("chapters")) for x in all_titles), default=0
    )
    max_audio    = max(
        (len(x.get("audio_tracks", [])) for x in all_titles), default=0
    )
    max_subs     = max(
        (len(x.get("subtitle_tracks", [])) for x in all_titles), default=0
    )

    duration_present = sum(
        1 for x in all_titles
        if isinstance(x.get("duration_seconds"), (int, float)) and
        x.get("duration_seconds", 0) > 0
    )
    size_present = sum(
        1 for x in all_titles
        if isinstance(x.get("size_bytes"), (int, float)) and
        x.get("size_bytes", 0) > 0
    )
    chapters_present = sum(
        1 for x in all_titles
        if safe_int(x.get("chapters")) > 0
    )
    audio_present = sum(
        1 for x in all_titles
        if len(x.get("audio_tracks", [])) > 0
    )
    subs_present = sum(
        1 for x in all_titles
        if len(x.get("subtitle_tracks", [])) > 0
    )

    coverage_threshold = max(1, (title_count + 1) // 2)

    size_bytes = (
        t.get("size_bytes", 0)
        if isinstance(t.get("size_bytes"), (int, float)) else 0
    )
    duration_seconds = (
        t.get("duration_seconds", 0)
        if isinstance(t.get("duration_seconds"), (int, float)) else 0
    )
    chapters = safe_int(t.get("chapters"))

    components = []
    if max_duration > 0 and duration_present >= coverage_threshold:
        components.append((duration_seconds / max_duration, 0.35))
    if max_size > 0 and size_present >= coverage_threshold:
        components.append((size_bytes / max_size, 0.30))
    if max_chapters > 0 and chapters_present >= coverage_threshold:
        components.append((chapters / max_chapters, 0.15))
    if max_audio > 0 and audio_present >= coverage_threshold:
        components.append((len(t.get("audio_tracks", [])) / max_audio, 0.15))
    if max_subs > 0 and subs_present >= coverage_threshold:
        components.append((len(t.get("subtitle_tracks", [])) / max_subs, 0.05))

    if not components:
        return 0.0

    total_weight = sum(weight for _, weight in components)
    if total_weight <= 0:
        return 0.0

    return sum(
        value * (weight / total_weight)
        for value, weight in components
    )


def choose_best_title(disc_titles, require_valid=False):
    """Select best title by score; optionally gate invalid candidates."""
    if not disc_titles:
        return None, 0.0

    candidates = disc_titles
    if require_valid:
        valid = [
            t for t in disc_titles
            if t.get("size_bytes", 0) > 0 and t.get("duration_seconds", 0) > 0
        ]
        if valid:
            candidates = valid

    best = max(candidates, key=lambda t: score_title(t, disc_titles))
    return best, score_title(best, disc_titles)


def format_audio_summary(audio_tracks):
    """Format audio track list as a readable string for the disc tree UI."""
    if not audio_tracks:
        return "—"
    parts = []
    for a in audio_tracks:
        lang     = a.get("lang_name") or a.get("lang") or ""
        codec    = a.get("codec", "")
        channels = a.get("channels", "")
        label    = " ".join(
            filter(None, [lang, codec, channels])
        ).strip()
        if label:
            parts.append(label)
    return ", ".join(parts) if parts else "—"



__all__ = ["choose_best_title", "format_audio_summary", "score_title"]
