"""Parsing-focused unit tests for JellyRip helper functions."""

import os
import sys

# Import from project root when tests are run from this folder.
sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)

from JellyRip import parse_duration_to_seconds, safe_int


class TestSafeInt:
    """Behavior checks for integer parsing fallback logic."""

    def test_valid_integer(self):
        assert safe_int("42") == 42

    def test_zero(self):
        assert safe_int("0") == 0

    def test_invalid_string(self):
        assert safe_int("abc") == 0


class TestParseDuration:
    """Behavior checks for duration parsing helper."""

    def test_valid_hms_format(self):
        assert (
            parse_duration_to_seconds("01:23:45")
            == 1 * 3600 + 23 * 60 + 45
        )

    def test_zero_duration(self):
        assert parse_duration_to_seconds("00:00:00") == 0

    def test_empty_string(self):
        assert parse_duration_to_seconds("") == 0
