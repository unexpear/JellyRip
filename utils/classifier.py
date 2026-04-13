"""Title classification layer built on top of scoring.

Wraps the existing score_title / choose_best_title logic to produce
human-readable labels, confidence percentages, and reason strings.
Does NOT rewrite or replace scoring — only interprets its output.
"""

from __future__ import annotations

from collections.abc import Sequence

from .scoring import Title, score_title, _numeric_field, _sequence_length
from .parsing import safe_int


class ClassifiedTitle:
    """A disc title with its score translated into a decision."""

    __slots__ = ("title", "score", "label", "confidence", "reasons")

    def __init__(
        self,
        title: Title,
        score: float,
        label: str,
        confidence: float,
        reasons: list[str],
    ) -> None:
        self.title = title
        self.score = score
        self.label = label
        self.confidence = confidence
        self.reasons = reasons

    @property
    def title_id(self) -> int:
        return int(self.title.get("id", -1))

    @property
    def display_name(self) -> str:
        return str(self.title.get("name", f"Title {self.title_id + 1}"))

    def summary(self) -> str:
        """One-line summary: 'Title 008 — MAIN (92%)'."""
        pct = int(self.confidence * 100)
        return f"{self.display_name} — {self.label} ({pct}%)"

    def detail(self) -> str:
        """Multi-line detail for logs."""
        pct = int(self.confidence * 100)
        reason_str = " + ".join(self.reasons) if self.reasons else "no strong signals"
        return (
            f"{self.display_name} — {self.label} ({pct}%)\n"
            f"  Reason: {reason_str}"
        )

    def __repr__(self) -> str:
        return (
            f"ClassifiedTitle({self.display_name!r}, label={self.label!r}, "
            f"confidence={self.confidence:.2f})"
        )


def _build_reasons(
    title: Title,
    all_titles: Sequence[Title],
    label: str,
    best_title: Title | None,
) -> list[str]:
    """Build human-readable reasons for a title's classification."""
    reasons: list[str] = []

    duration = _numeric_field(title, "duration_seconds")
    size = _numeric_field(title, "size_bytes")
    chapters = safe_int(title.get("chapters"))

    max_duration = max((_numeric_field(t, "duration_seconds") for t in all_titles), default=0.0)
    max_size = max((_numeric_field(t, "size_bytes") for t in all_titles), default=0.0)
    max_chapters = max((safe_int(t.get("chapters")) for t in all_titles), default=0)
    max_audio = max((_sequence_length(t, "audio_tracks") for t in all_titles), default=0)

    if label == "MAIN":
        if max_duration > 0 and duration == max_duration:
            reasons.append("longest duration")
        elif max_duration > 0 and duration >= max_duration * 0.95:
            reasons.append("near-longest duration")
        if max_size > 0 and size == max_size:
            reasons.append("largest size")
        elif max_size > 0 and size >= max_size * 0.95:
            reasons.append("near-largest size")
        if max_chapters > 0 and chapters == max_chapters:
            reasons.append("most chapters")
        if max_audio > 0 and _sequence_length(title, "audio_tracks") == max_audio:
            reasons.append("most audio tracks")
        if not reasons:
            reasons.append("highest combined score")

    elif label == "DUPLICATE":
        if best_title is not None:
            reasons.append("same duration and size as main title")

    elif label == "EXTRA":
        if duration < 1200:
            reasons.append("short duration (<20 min)")
        elif duration < 2400:
            reasons.append("short duration (<40 min)")
        else:
            reasons.append("low score relative to main")

    elif label == "UNKNOWN":
        reasons.append("ambiguous signals")

    return reasons


def _compute_confidence(best_score: float, second_score: float, label: str) -> float:
    """Derive confidence from the gap between top candidates.

    Confidence reflects how decisive the classification is, not the
    raw quality score. A large gap means clear winner = high confidence.
    """
    if label == "EXTRA":
        # Extras are classified by duration, not gap — high confidence
        # when clearly short, lower when borderline.
        return 0.95

    if label == "DUPLICATE":
        # Duplicates are identified by matching duration+size, not score gap.
        return 0.89

    # For MAIN and UNKNOWN, confidence comes from separation.
    gap = best_score - second_score

    if gap > 0.3:
        return 0.95
    elif gap > 0.15:
        return 0.85
    elif gap > 0.05:
        return 0.70
    else:
        return 0.60


def _is_duplicate(
    title: Title, best_title: Title, duration_tolerance: float = 60.0, size_ratio: float = 0.05
) -> bool:
    """Check if a title is a likely duplicate of the best title.

    Duplicates have nearly identical duration AND size — this catches
    playlist obfuscation where studios create multiple identical titles.
    """
    dur_a = _numeric_field(title, "duration_seconds")
    dur_b = _numeric_field(best_title, "duration_seconds")
    size_a = _numeric_field(title, "size_bytes")
    size_b = _numeric_field(best_title, "size_bytes")

    if dur_b <= 0 or size_b <= 0:
        return False

    duration_close = abs(dur_a - dur_b) < duration_tolerance
    size_close = abs(size_a - size_b) / size_b < size_ratio if size_b > 0 else False

    return duration_close and size_close


def classify_titles(disc_titles: Sequence[Title]) -> list[ClassifiedTitle]:
    """Classify all titles on a disc into MAIN / DUPLICATE / EXTRA / UNKNOWN.

    Wraps the existing score_title() without modifying it. Returns a list
    of ClassifiedTitle objects sorted by score (best first).
    """
    if not disc_titles:
        return []

    # Score everything using existing logic.
    scored = [(t, score_title(t, disc_titles)) for t in disc_titles]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_title, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0.0

    results: list[ClassifiedTitle] = []

    for title, score in scored:
        # Assign label.
        if title is best_title:
            label = "MAIN"
        elif _is_duplicate(title, best_title):
            label = "DUPLICATE"
        elif _numeric_field(title, "duration_seconds") < 1200:
            label = "EXTRA"
        else:
            label = "UNKNOWN"

        confidence = _compute_confidence(best_score, second_score, label)
        reasons = _build_reasons(title, disc_titles, label, best_title)

        results.append(ClassifiedTitle(
            title=title,
            score=score,
            label=label,
            confidence=confidence,
            reasons=reasons,
        ))

    return results


def classify_and_pick_main(
    disc_titles: Sequence[Title],
) -> tuple[ClassifiedTitle | None, list[ClassifiedTitle]]:
    """Convenience: classify titles and return (main, all_classified).

    Returns (None, []) if no titles. The main title is also included
    in the full list.
    """
    classified = classify_titles(disc_titles)
    if not classified:
        return None, []

    main = classified[0]  # Already sorted best-first
    return main, classified


def format_classification_log(classified: list[ClassifiedTitle]) -> list[str]:
    """Format classification results for the session log.

    Each title gets one line combining label, confidence, reason, and stats:
      [SCAN] MAIN: Title 8 (92%) — longest duration + largest size [7200s 30.0GB ch24]
    """
    lines: list[str] = []
    for ct in classified:
        pct = int(ct.confidence * 100)
        dur = int(_numeric_field(ct.title, "duration_seconds"))
        size_gb = _numeric_field(ct.title, "size_bytes") / (1024 ** 3)
        chapters = safe_int(ct.title.get("chapters"))
        reason_str = " + ".join(ct.reasons) if ct.reasons else "no strong signals"

        lines.append(
            f"[SCAN] {ct.label}: {ct.display_name} ({pct}%) "
            f"— {reason_str} "
            f"[{dur}s {size_gb:.1f}GB ch{chapters}]"
        )
    return lines


__all__ = [
    "ClassifiedTitle",
    "classify_and_pick_main",
    "classify_titles",
    "format_classification_log",
]
