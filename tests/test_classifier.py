"""Tests for utils.classifier — title classification layer."""

import pytest
from utils.classifier import (
    ClassifiedTitle,
    classify_and_pick_main,
    classify_titles,
    format_classification_log,
)


def _title(tid, duration_s, size_gb, chapters=0, audio_tracks=None, name=None):
    """Helper to build a title dict matching MakeMKV parse output."""
    return {
        "id": tid,
        "name": name or f"Title {tid + 1}",
        "duration_seconds": duration_s,
        "size_bytes": int(size_gb * 1024 ** 3),
        "chapters": chapters,
        "audio_tracks": audio_tracks or [],
        "subtitle_tracks": [],
    }


# --- classify_titles ---


class TestClassifyTitles:
    def test_empty_input(self):
        assert classify_titles([]) == []

    def test_single_title_is_main(self):
        titles = [_title(0, 7200, 30.0, chapters=24)]
        result = classify_titles(titles)
        assert len(result) == 1
        assert result[0].label == "MAIN"
        assert result[0].confidence > 0.5

    def test_clear_main_plus_extras(self):
        titles = [
            _title(0, 7200, 30.0, chapters=24),  # 2h movie
            _title(1, 600, 2.0, chapters=1),      # 10min extra
            _title(2, 300, 1.0, chapters=1),      # 5min extra
        ]
        result = classify_titles(titles)
        labels = {ct.title_id: ct.label for ct in result}
        assert labels[0] == "MAIN"
        assert labels[1] == "EXTRA"
        assert labels[2] == "EXTRA"

    def test_duplicate_detection(self):
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 7200, 30.0, chapters=24),  # same duration + size
            _title(2, 600, 2.0),
        ]
        result = classify_titles(titles)
        labels = {ct.title_id: ct.label for ct in result}
        # One should be MAIN, the other DUPLICATE
        main_count = sum(1 for l in labels.values() if l == "MAIN")
        dup_count = sum(1 for l in labels.values() if l == "DUPLICATE")
        assert main_count == 1
        assert dup_count == 1
        assert labels[2] == "EXTRA"

    def test_near_duplicate_within_tolerance(self):
        """Titles within 60s duration and 5% size are duplicates."""
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 7250, 30.5, chapters=24),  # 50s diff, ~1.7% size diff
        ]
        result = classify_titles(titles)
        labels = {ct.title_id: ct.label for ct in result}
        assert "DUPLICATE" in labels.values()

    def test_unknown_label_for_ambiguous(self):
        """Medium-length title that isn't main, dup, or short = UNKNOWN."""
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 3600, 15.0, chapters=12),  # 1h, not short, not dup
        ]
        result = classify_titles(titles)
        labels = {ct.title_id: ct.label for ct in result}
        assert labels[0] == "MAIN"
        assert labels[1] == "UNKNOWN"

    def test_sorted_by_score_descending(self):
        titles = [
            _title(0, 300, 1.0),
            _title(1, 7200, 30.0, chapters=24),
            _title(2, 600, 2.0),
        ]
        result = classify_titles(titles)
        assert result[0].label == "MAIN"
        scores = [ct.score for ct in result]
        assert scores == sorted(scores, reverse=True)

    def test_many_duplicates_flagged(self):
        """Multiple identical titles all get DUPLICATE except the best."""
        titles = [_title(i, 7200, 30.0, chapters=24) for i in range(5)]
        result = classify_titles(titles)
        labels = [ct.label for ct in result]
        assert labels.count("MAIN") == 1
        assert labels.count("DUPLICATE") == 4


# --- Confidence ---


class TestConfidence:
    def test_high_confidence_with_clear_winner(self):
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 300, 1.0),
        ]
        result = classify_titles(titles)
        main = [ct for ct in result if ct.label == "MAIN"][0]
        assert main.confidence >= 0.85

    def test_lower_confidence_with_close_scores(self):
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 7100, 29.5, chapters=23),  # very close but not dup
        ]
        result = classify_titles(titles)
        main = [ct for ct in result if ct.label == "MAIN"][0]
        # Close scores should yield lower confidence
        assert main.confidence <= 0.85

    def test_extras_always_high_confidence(self):
        titles = [
            _title(0, 7200, 30.0),
            _title(1, 300, 1.0),
        ]
        result = classify_titles(titles)
        extra = [ct for ct in result if ct.label == "EXTRA"][0]
        assert extra.confidence == 0.95


# --- Reasons ---


class TestReasons:
    def test_main_gets_specific_reasons(self):
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 600, 2.0),
        ]
        result = classify_titles(titles)
        main = [ct for ct in result if ct.label == "MAIN"][0]
        assert len(main.reasons) > 0
        assert any("duration" in r or "size" in r for r in main.reasons)

    def test_duplicate_reason_mentions_main(self):
        titles = [
            _title(0, 7200, 30.0),
            _title(1, 7200, 30.0),
        ]
        result = classify_titles(titles)
        dup = [ct for ct in result if ct.label == "DUPLICATE"][0]
        assert any("main" in r.lower() for r in dup.reasons)

    def test_extra_reason_mentions_duration(self):
        titles = [
            _title(0, 7200, 30.0),
            _title(1, 300, 1.0),
        ]
        result = classify_titles(titles)
        extra = [ct for ct in result if ct.label == "EXTRA"][0]
        assert any("duration" in r.lower() for r in extra.reasons)


# --- ClassifiedTitle methods ---


class TestClassifiedTitle:
    def test_summary_format(self):
        ct = ClassifiedTitle(
            title={"id": 7, "name": "Title 8"},
            score=0.92,
            label="MAIN",
            confidence=0.92,
            reasons=["longest duration"],
        )
        assert "MAIN" in ct.summary()
        assert "92%" in ct.summary()

    def test_detail_includes_reason(self):
        ct = ClassifiedTitle(
            title={"id": 7, "name": "Title 8"},
            score=0.92,
            label="MAIN",
            confidence=0.92,
            reasons=["longest duration", "largest size"],
        )
        detail = ct.detail()
        assert "longest duration" in detail
        assert "largest size" in detail

    def test_title_id_property(self):
        ct = ClassifiedTitle(
            title={"id": 3, "name": "Test"},
            score=0.5,
            label="EXTRA",
            confidence=0.95,
            reasons=[],
        )
        assert ct.title_id == 3


# --- classify_and_pick_main ---


class TestClassifyAndPickMain:
    def test_empty_returns_none(self):
        main, classified = classify_and_pick_main([])
        assert main is None
        assert classified == []

    def test_returns_main_and_full_list(self):
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 600, 2.0),
        ]
        main, classified = classify_and_pick_main(titles)
        assert main is not None
        assert main.label == "MAIN"
        assert len(classified) == 2


# --- format_classification_log ---


class TestFormatLog:
    def test_log_format(self):
        titles = [
            _title(0, 7200, 30.0, chapters=24),
            _title(1, 600, 2.0),
        ]
        classified = classify_titles(titles)
        lines = format_classification_log(classified)
        assert len(lines) >= 2
        assert all(line.startswith("[SCAN]") for line in lines)
        assert any("MAIN" in line for line in lines)
        assert any("EXTRA" in line for line in lines)
