"""
Unit tests for JellyRip core logic
Tests RipperEngine functions without requiring MakeMKV, FFprobe, or optical drive
"""

import unittest
import os
import sys
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock

# Import functions to test
sys.path.insert(0, os.path.dirname(__file__))
from JellyRip import (
    parse_duration_to_seconds,
    clean_name,
    score_title,
    parse_episode_names,
    format_audio_summary,
)


class TestDurationParsing(unittest.TestCase):
    """Test parse_duration_to_seconds helper"""
    
    def test_h_mm_ss_format(self):
        """Test duration with hours"""
        result = parse_duration_to_seconds("1:30:45")
        self.assertEqual(result, 5445)  # 1*3600 + 30*60 + 45
    
    def test_m_ss_format(self):
        """Test duration without hours"""
        result = parse_duration_to_seconds("45:30")
        self.assertEqual(result, 2730)  # 45*60 + 30
    
    def test_invalid_format(self):
        """Test invalid duration returns 0"""
        result = parse_duration_to_seconds("invalid")
        self.assertEqual(result, 0)
    
    def test_empty_string(self):
        """Test empty string returns 0"""
        result = parse_duration_to_seconds("")
        self.assertEqual(result, 0)
    
    def test_zero_duration(self):
        """Test zero duration"""
        result = parse_duration_to_seconds("0:00:00")
        self.assertEqual(result, 0)


class TestCleanName(unittest.TestCase):
    """Test clean_name helper"""
    
    def test_remove_illegal_chars(self):
        """Test removal of illegal filename characters"""
        result = clean_name('Test <Movie>: "The Title" | 2024')
        self.assertEqual(result, "Test Movie The Title  2024")
    
    def test_remove_trailing_dots(self):
        """Test removal of trailing dots/spaces"""
        result = clean_name("Movie Name... ")
        self.assertEqual(result, "Movie Name")
    
    def test_normal_name(self):
        """Test normal name passes through"""
        result = clean_name("The Paper Boy 2012")
        self.assertEqual(result, "The Paper Boy 2012")


class TestEpisodeNameParsing(unittest.TestCase):
    """Test parse_episode_names helper"""
    
    def test_comma_separated(self):
        """Test comma-separated episodes"""
        result = parse_episode_names("Episode 1, Episode 2, Episode 3")
        self.assertEqual(result, ["Episode 1", "Episode 2", "Episode 3"])
    
    def test_quoted_with_commas(self):
        """Test quoted names with commas inside"""
        result = parse_episode_names('"Title, Part 1", "Title, Part 2"')
        self.assertEqual(result, ["Title, Part 1", "Title, Part 2"])
    
    def test_empty_input(self):
        """Test empty input returns empty list"""
        result = parse_episode_names("")
        self.assertEqual(result, [])
    
    def test_single_episode(self):
        """Test single episode"""
        result = parse_episode_names("Only Episode")
        self.assertEqual(result, ["Only Episode"])


class TestAudioSummary(unittest.TestCase):
    """Test format_audio_summary helper"""
    
    def test_empty_tracks(self):
        """Test empty audio tracks"""
        result = format_audio_summary([])
        self.assertEqual(result, "—")
    
    def test_single_track(self):
        """Test single audio track"""
        tracks = [{"lang_name": "English", "codec": "AC3", "channels": "5.1"}]
        result = format_audio_summary(tracks)
        self.assertEqual(result, "English AC3 5.1")
    
    def test_multiple_tracks(self):
        """Test multiple audio tracks"""
        tracks = [
            {"lang_name": "English", "codec": "AC3", "channels": "5.1"},
            {"lang_name": "Spanish", "codec": "AAC", "channels": "2.0"},
        ]
        result = format_audio_summary(tracks)
        self.assertIn("English", result)
        self.assertIn("Spanish", result)
    
    def test_partial_track_info(self):
        """Test tracks with missing fields"""
        tracks = [{"lang_name": "English"}]
        result = format_audio_summary(tracks)
        self.assertEqual(result, "English")


class TestScoreTitle(unittest.TestCase):
    """Test title scoring algorithm"""
    
    def test_empty_title_list(self):
        """Test empty title list doesn't crash"""
        result = score_title({}, [])
        self.assertEqual(result, 0.0)
    
    def test_single_title(self):
        """Test scoring with single title"""
        title = {
            "id": 0,
            "size_bytes": 1000000000,
            "duration_seconds": 5400,
            "chapters": 20,
            "audio_tracks": [{"lang": "en"}],
            "subtitle_tracks": [{"lang": "en"}],
        }
        result = score_title(title, [title])
        self.assertGreater(result, 0.5)  # Single title should score high
    
    def test_title_with_best_qualities(self):
        """Test that best title scores higher"""
        good_title = {
            "id": 0,
            "size_bytes": 5000000000,  # Largest
            "duration_seconds": 7200,  # Longest
            "chapters": 30,  # Most chapters
            "audio_tracks": [{"lang": "en"}, {"lang": "es"}],  # Most audio
            "subtitle_tracks": [{"lang": "en"}, {"lang": "es"}],  # Most subs
        }
        
        bad_title = {
            "id": 1,
            "size_bytes": 500000000,   # Smallest
            "duration_seconds": 600,   # Shortest
            "chapters": 0,
            "audio_tracks": [],
            "subtitle_tracks": [],
        }
        
        good_score = score_title(good_title, [good_title, bad_title])
        bad_score = score_title(bad_title, [good_title, bad_title])
        
        self.assertGreater(good_score, bad_score)
    
    def test_score_range(self):
        """Test scores are between 0 and 1"""
        title = {
            "id": 0,
            "size_bytes": 1000000000,
            "duration_seconds": 5400,
            "chapters": 20,
            "audio_tracks": [{"lang": "en"}],
            "subtitle_tracks": [{"lang": "en"}],
        }
        result = score_title(title, [title])
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)


class TestRipperEngineInit(unittest.TestCase):
    """Test RipperEngine initialization"""
    
    def test_engine_init(self):
        """Test engine can be initialized"""
        from JellyRip import RipperEngine
        
        cfg = {
            "makemkvcon_path": "C:\\path\\to\\makemkvcon.exe",
            "ffprobe_path": "C:\\path\\to\\ffprobe.exe",
        }
        
        engine = RipperEngine(cfg)
        self.assertEqual(engine.cfg, cfg)
        self.assertIsNotNone(engine.abort_event)
        self.assertFalse(engine.abort_event.is_set())


def run_tests():
    """Run all tests and print results"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDurationParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestCleanName))
    suite.addTests(loader.loadTestsFromTestCase(TestEpisodeNameParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestAudioSummary))
    suite.addTests(loader.loadTestsFromTestCase(TestScoreTitle))
    suite.addTests(loader.loadTestsFromTestCase(TestRipperEngineInit))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
