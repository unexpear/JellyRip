import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from JellyRip import safe_int, parse_duration_to_seconds

class TestSafeInt:
    def test_valid_integer(self):
        assert safe_int("42") == 42
    def test_zero(self):
        assert safe_int("0") == 0
    def test_invalid_string(self):
        assert safe_int("abc") == 0

class TestParseDuration:
    def test_valid_hms_format(self):
        assert parse_duration_to_seconds("01:23:45") == 1 * 3600 + 23 * 60 + 45
    def test_zero_duration(self):
        assert parse_duration_to_seconds("00:00:00") == 0
    def test_empty_string(self):
        assert parse_duration_to_seconds("") == 0
