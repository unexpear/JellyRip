"""Phase 3c-i — gui_qt.formatters tests.

Pins the contract for the pure-Python formatters that the Qt path
uses in lieu of methods on ``JellyRipperGUI``.  Same input → same
output as the tkinter helpers in ``gui/main_window.py`` (covered by
``tests/test_main_window_formatters.py``).

Behavior-first.  No Qt, no tkinter — pure Python only.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from gui_qt.formatters import (
    format_drive_label,
    status_role_for_message,
    trim_context_label,
)
from utils.helpers import MakeMKVDriveInfo


# ---------------------------------------------------------------------------
# format_drive_label
# ---------------------------------------------------------------------------


def _drive(
    *,
    index: int = 0,
    state_code: int = 2,
    drive_name: str = "BD-RE HL-DT-ST",
    disc_name: str = "BREAKING_BAD_S03_D2",
    device_path: str = "disc:0",
) -> MakeMKVDriveInfo:
    return MakeMKVDriveInfo(
        index=index,
        state_code=state_code,
        flags_code=999,
        disc_type_code=0,
        drive_name=drive_name,
        disc_name=disc_name,
        device_path=device_path,
    )


def test_format_drive_label_full_info():
    """Happy path — every field populated.  The disc name is
    prefixed with the loaded-state glyph (``◉``) per
    docs/symbol-library.md Section 1.3."""
    label = format_drive_label(_drive(
        index=2,
        state_code=2,
        drive_name="BD-RE HL-DT-ST",
        disc_name="BREAKING_BAD_S03_D2",
        device_path="disc:2",
    ))
    assert label == (
        "Drive 2: BD-RE HL-DT-ST | "
        "Disc: ◉ BREAKING_BAD_S03_D2 | "
        "Path: disc:2 | "
        "State: ready (2)"
    )


def test_format_drive_label_falls_back_on_empty_drive_name():
    """Missing drive name → "Unknown drive"."""
    label = format_drive_label(_drive(drive_name="", disc_name="X", device_path="disc:1", index=1))
    assert "Drive 1: Unknown drive" in label


def test_format_drive_label_falls_back_on_empty_disc_name():
    """Missing disc name → "No disc" with the loaded-state glyph
    (state_code=2 in the default fixture).  When the disc-name
    fallback fires alongside an actual empty tray, the glyph
    switches to ⊚ — covered by ``test_format_drive_label_glyph_*``
    below."""
    label = format_drive_label(_drive(disc_name="", drive_name="X", device_path="disc:0"))
    assert "Disc: ◉ No disc" in label


def test_format_drive_label_falls_back_on_empty_device_path():
    """Missing device path → "disc:{index}"."""
    label = format_drive_label(_drive(device_path="", index=3, drive_name="X", disc_name="Y"))
    assert "Path: disc:3" in label


def test_format_drive_label_includes_state_code():
    """State name + numeric code in parens."""
    label = format_drive_label(_drive(state_code=0))  # 0 → "empty"
    assert "State: empty (0)" in label


def test_format_drive_label_unknown_state_falls_back():
    """Unknown state codes get formatted as ``state {code}``."""
    label = format_drive_label(_drive(state_code=42))
    assert "State: state 42 (42)" in label


# ---------------------------------------------------------------------------
# Disc-state glyph (added 2026-05-04 per docs/symbol-library.md)
# ---------------------------------------------------------------------------


def test_format_drive_label_glyph_ready():
    """state_code=2 (ready) → fisheye ``◉``."""
    label = format_drive_label(_drive(state_code=2, disc_name="DISC_X"))
    assert "Disc: ◉ DISC_X" in label


def test_format_drive_label_glyph_empty_tray():
    """state_code=0 (empty) → circled ring ``⊚``.

    The empty-tray glyph reads as "outline of a disc with nothing
    in it" — the user can spot it as different from ``◉`` even at
    a glance."""
    label = format_drive_label(_drive(state_code=0, disc_name=""))
    assert "Disc: ⊚ No disc" in label


def test_format_drive_label_glyph_unavailable():
    """state_code=256 (unavailable) and any other non-2 / non-0 code
    → dotted circle ``◌``.  Distinguishes "drive offline / busy"
    from "tray empty"."""
    label_256 = format_drive_label(_drive(state_code=256, disc_name=""))
    assert "Disc: ◌ No disc" in label_256
    label_42 = format_drive_label(_drive(state_code=42, disc_name="X"))
    assert "Disc: ◌ X" in label_42


def test_format_drive_label_include_state_glyph_false_strips_glyph():
    """The Appearance tab's ``opt_drive_state_glyph`` toggle flows
    here as ``include_state_glyph=False`` — the disc name field
    must lose the leading glyph but the rest of the label is
    unchanged."""
    label = format_drive_label(
        _drive(state_code=2, disc_name="DISC_X"),
        include_state_glyph=False,
    )
    assert "Disc: DISC_X" in label
    assert "◉" not in label
    assert "⊚" not in label
    assert "◌" not in label


def test_format_drive_label_include_state_glyph_default_true():
    """Default behavior is unchanged — every existing call site
    that omits the kwarg keeps getting the glyph."""
    label = format_drive_label(_drive(state_code=2, disc_name="DISC_X"))
    assert "Disc: ◉ DISC_X" in label


# ---------------------------------------------------------------------------
# trim_context_label
# ---------------------------------------------------------------------------


def test_trim_under_limit_returns_unchanged():
    """Strings within the limit pass through untouched (modulo
    whitespace collapse — the limit check happens after collapse)."""
    assert trim_context_label("hello") == "hello"
    assert trim_context_label("a" * 40) == "a" * 40


def test_trim_at_limit_returns_unchanged():
    """At exactly ``limit`` chars, no truncation."""
    assert trim_context_label("a" * 40, limit=40) == "a" * 40


def test_trim_over_limit_appends_ellipsis():
    """Beyond ``limit``, truncate to limit-1 chars + ellipsis."""
    result = trim_context_label("a" * 50, limit=10)
    assert result == "aaaaaaaaa…"
    assert len(result) == 10


def test_trim_collapses_whitespace_runs():
    """Multi-whitespace collapses to a single space."""
    assert trim_context_label("hello   world") == "hello world"


def test_trim_collapses_newlines_and_tabs():
    """Newlines and tabs are whitespace too — collapse them."""
    assert trim_context_label("hello\n\nworld\there") == "hello world here"


def test_trim_strips_leading_and_trailing_whitespace():
    """``str.split()`` handles edges automatically."""
    assert trim_context_label("   padded   ") == "padded"


def test_trim_default_limit_is_40():
    """Caller default — pinned because the production callers rely
    on this default."""
    long = "x" * 100
    result = trim_context_label(long)
    assert len(result) == 40
    assert result.endswith("…")


def test_trim_handles_empty_string():
    """Empty input → empty output, no crash."""
    assert trim_context_label("") == ""


def test_trim_handles_whitespace_only():
    """Whitespace-only input collapses to empty."""
    assert trim_context_label("   \t\n   ") == ""


# ---------------------------------------------------------------------------
# status_role_for_message
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("msg", ["", " ", "ready", "Ready", "IDLE", "idle"])
def test_status_role_idle_states_are_ready(msg: str):
    """Empty / "ready" / "idle" all bucket to ``ready``."""
    assert status_role_for_message(msg) == "ready"


def test_status_role_choose_a_mode_is_ready():
    """The "Choose a mode" prompt is the post-launch ready state."""
    assert status_role_for_message("Choose a mode to start.") == "ready"
    assert status_role_for_message("Please choose a mode") == "ready"


def test_status_role_none_input_is_ready():
    """``None`` (defensive — controller may pass it) → ready."""
    assert status_role_for_message(None) == "ready"


@pytest.mark.parametrize("msg", [
    "MakeMKV failed to scan",
    "Disk space invalid",
    "Update blocked",
    "MakeMKV missing",
    "FFmpeg unavailable",
    "Encoding error: codec mismatch",
])
def test_status_role_error_tokens_bucket_to_error(msg: str):
    """Any of failed/error/missing/invalid/blocked/unavailable → error."""
    assert status_role_for_message(msg) == "error"


@pytest.mark.parametrize("msg", [
    "Aborting current rip",
    "Operation cancelled",
    "Operation canceled",
    "Retry attempt 3",
    "Waiting for confirmation",
    "Attention: re-insert disc",
    "Warning: low disk space",
])
def test_status_role_warn_tokens_bucket_to_warn(msg: str):
    """Any of attention/warning/aborting/cancelled/canceled/retry/
    waiting → warn."""
    assert status_role_for_message(msg) == "warn"


@pytest.mark.parametrize("msg", [
    "Ripping title 02",
    "Scanning drive E:",
    "Encoding S03E04.mkv",
    "Decrypting BD",
])
def test_status_role_active_messages_bucket_to_busy(msg: str):
    """Any other in-progress message → busy."""
    assert status_role_for_message(msg) == "busy"


def test_status_role_error_takes_precedence_over_warn():
    """If a message contains both error and warn tokens, error wins
    (matches tkinter's check ordering)."""
    # "warning" is a warn token; "failed" is an error token; both
    # appear → error should win.
    assert status_role_for_message("Warning: encode failed") == "error"


def test_status_role_is_case_insensitive():
    """Token matching ignores case."""
    assert status_role_for_message("FAILED to start") == "error"
    assert status_role_for_message("Cancelled") == "warn"
