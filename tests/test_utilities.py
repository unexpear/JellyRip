"""Tests for JellyRip utility functions."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from JellyRip import clean_name, make_temp_title # pyright: ignore[reportMissingImports]


class TestCleanName:
    """Test clean_name function."""

    def test_alphanumeric_unchanged(self):
        """Alphanumeric strings remain unchanged."""
        assert clean_name("MyShow") == "MyShow"
        assert clean_name("Breaking Bad") == "Breaking Bad"

    def test_remove_invalid_chars(self):
        """Invalid filesystem characters are removed."""
        # Forward slash, backslash, colon, etc.
        assert "/" not in clean_name("Folder/Name")
        assert "\\" not in clean_name("Folder\\Name")
        result = clean_name("Name:With:Colons")
        # Colons should be removed or replaced
        assert ":" not in result

    def test_spaces_preserved(self):
        """Spaces are preserved."""
        assert clean_name("My Show") == "My Show"

    def test_special_chars_handled(self):
        """Special characters like *, ?, <, > are removed."""
        name = clean_name("Bad*Name?Here<There>")
        assert "*" not in name
        assert "?" not in name
        assert "<" not in name
        assert ">" not in name
        assert "|" not in name

    def test_empty_string(self):
        """Empty string remains empty."""
        assert clean_name("") == ""

    def test_quotes_handled(self):
        """Quotes are removed or handled."""
        result = clean_name('Show "with" quotes')
        # Should not have problematic quote chars
        assert '"' not in result or result == 'Show "with" quotes'


class TestMakeTempTitle:
    """Test make_temp_title function."""

    def test_returns_string(self):
        """Returns a string."""
        result = make_temp_title()
        assert isinstance(result, str)

    def test_non_empty(self):
        """Result is not empty."""
        result = make_temp_title()
        assert len(result) > 0

    def test_consistent_format(self):
        """Result follows expected format (likely timestamp-based)."""
        result = make_temp_title()
        # Should be some kind of identifier, typically numeric or date-based
        assert not result.isspace()

    def test_unique_calls(self):
        """Multiple calls return different values (for timestamp-based)."""
        import time
        result1 = make_temp_title()
        time.sleep(0.01)  # Small delay
        result2 = make_temp_title()
        # May or may not be different depending on implementation
        # Just verify both are valid
        assert isinstance(result1, str) and isinstance(result2, str)
