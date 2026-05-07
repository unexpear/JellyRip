"""Phase 3c-i — gui_qt.log_pane tests.

Pins the contract for the QPlainTextEdit-based log widget:

- Pure helper ``is_scrolled_to_bottom`` (no Qt needed)
- Append plain lines and tagged lines (prompt / answer)
- Autoscroll only when at bottom
- Line-cap trim using cfg's opt_log_cap_lines / opt_log_trim_lines
- ``get_text()`` returns full content
- HTML-escaping for tagged lines (defends against log content that
  happens to look like HTML)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QPlainTextEdit

from gui_qt.log_pane import LogPane, _classify_log_line, is_scrolled_to_bottom


# ---------------------------------------------------------------------------
# Pure helper — is_scrolled_to_bottom
# ---------------------------------------------------------------------------


def test_is_scrolled_to_bottom_with_no_scroll():
    """When the document fits without scrolling (max=0), treat as
    "at bottom" — appending a line should still autoscroll into the
    visible area."""
    assert is_scrolled_to_bottom(0, 0) is True


def test_is_scrolled_to_bottom_at_max():
    """value == max → at bottom."""
    assert is_scrolled_to_bottom(100, 100) is True


def test_is_scrolled_to_bottom_within_5_percent():
    """value within 5% of max → still "at bottom" (matches tkinter's
    yview()[1] > 0.95)."""
    assert is_scrolled_to_bottom(95, 100) is True
    assert is_scrolled_to_bottom(96, 100) is True


def test_is_scrolled_to_bottom_below_threshold():
    """User has scrolled up — not at bottom."""
    assert is_scrolled_to_bottom(50, 100) is False
    assert is_scrolled_to_bottom(94, 100) is False


def test_is_scrolled_to_bottom_at_top():
    """At the top of the document — definitely not at bottom."""
    assert is_scrolled_to_bottom(0, 100) is False


# ---------------------------------------------------------------------------
# Widget construction
# ---------------------------------------------------------------------------


def test_log_pane_is_readonly(qtbot):
    """The log shouldn't accept typing — pinned because we override
    isReadOnly elsewhere on Qt widgets occasionally."""
    pane = LogPane()
    qtbot.addWidget(pane)
    assert pane.isReadOnly()


def test_log_pane_has_object_name(qtbot):
    """``logPane`` objectName so QSS can target it."""
    pane = LogPane()
    qtbot.addWidget(pane)
    assert pane.objectName() == "logPane"


def test_log_pane_no_word_wrap(qtbot):
    """Log lines shouldn't wrap — fixed-width terminal-ish look."""
    pane = LogPane()
    qtbot.addWidget(pane)
    assert pane.lineWrapMode() == QPlainTextEdit.LineWrapMode.NoWrap


# ---------------------------------------------------------------------------
# Append behavior
# ---------------------------------------------------------------------------


def test_append_plain_line(qtbot):
    """Plain-text append shows up verbatim in get_text()."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("MakeMKV started")
    assert "MakeMKV started" in pane.get_text()


def test_append_strips_trailing_newline(qtbot):
    """Caller may pass text with or without a trailing newline.
    Either way the line shows up once, not twice."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("line one\n")
    pane.append("line two")
    text = pane.get_text()
    # No double-spacing between lines
    assert "line one\n\nline two" not in text
    assert "line one" in text
    assert "line two" in text


def test_append_multiple_lines_preserves_order(qtbot):
    """Append order is preserved in the output."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("first")
    pane.append("second")
    pane.append("third")
    text = pane.get_text()
    assert text.index("first") < text.index("second") < text.index("third")


def test_append_with_prompt_tag_applies_color(qtbot):
    """A prompt-tagged line gets the prompt color attached as a
    QTextCharFormat foreground.  The widget's ``block_color_at``
    helper exposes this for tests."""
    pane = LogPane(tag_colors={"prompt": "#abcdef", "answer": "#fedcba"})
    qtbot.addWidget(pane)
    pane.append("? Title 02 keep? (y/n)", tag="prompt")
    # Plain text shows the message verbatim
    assert "? Title 02 keep? (y/n)" in pane.get_text()
    # The block ended up colored with the prompt color
    assert pane.block_color_at(0) == "#abcdef"


def test_append_with_answer_tag_applies_color(qtbot):
    """An answer-tagged line uses the answer color."""
    pane = LogPane(tag_colors={"prompt": "#abcdef", "answer": "#112233"})
    qtbot.addWidget(pane)
    pane.append("y", tag="answer")
    assert pane.block_color_at(0) == "#112233"


def test_append_untagged_line_has_no_explicit_color(qtbot):
    """Plain (untagged) lines don't get an explicit foreground —
    they pick up whatever color the widget's QSS sets.  Pinned so
    tagged-line testing isn't a false positive on default formatting."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("plain line, no tag")
    assert pane.block_color_at(0) is None


def test_append_preserves_user_special_characters(qtbot):
    """Log content with angle brackets, ampersands, etc. must be
    preserved verbatim — pinned because tool output sometimes
    contains XML/HTML-looking fragments."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("<script>alert(1)</script>")
    text = pane.get_text()
    assert "<script>alert(1)</script>" in text


def test_default_tag_colors_match_dark_github(qtbot):
    """If no ``tag_colors`` dict is passed, defaults are the
    ``dark_github`` theme's prompt/answer colors.  Tests against
    drift when those theme tokens change."""
    pane = LogPane()
    qtbot.addWidget(pane)
    assert pane.tag_colors["prompt"] == "#f0e68c"
    assert pane.tag_colors["answer"] == "#90ee90"


# ---------------------------------------------------------------------------
# Trim behavior
# ---------------------------------------------------------------------------


def test_trim_kicks_in_at_cap(qtbot):
    """When line count exceeds cap, trim to trim_lines.  Use a small
    cap so the test runs fast — production defaults are 300k/200k."""
    cfg = {"opt_log_cap_lines": 10, "opt_log_trim_lines": 5}
    pane = LogPane(cfg=cfg)
    qtbot.addWidget(pane)
    for i in range(20):
        pane.append(f"line {i}")
    # Trim fires when blockCount > cap, so the high-water bound is
    # cap itself (between trims, blockCount fluctuates between
    # trim and cap).  Pin only the bound, not the exact post-trim
    # count, because the trailing-empty-block accounting is fiddly.
    assert pane.blockCount() <= 10
    # The most recent line must still be present.
    assert "line 19" in pane.get_text()
    # The earliest lines must have been trimmed away.
    assert "line 0" not in pane.get_text()


def test_trim_does_not_kick_in_below_cap(qtbot):
    """Below the cap, no trim — content is preserved verbatim."""
    cfg = {"opt_log_cap_lines": 100, "opt_log_trim_lines": 50}
    pane = LogPane(cfg=cfg)
    qtbot.addWidget(pane)
    for i in range(10):
        pane.append(f"line {i}")
    text = pane.get_text()
    assert "line 0" in text
    assert "line 9" in text


def test_trim_uses_defaults_with_no_cfg(qtbot):
    """Without cfg, defaults are 300k/200k — way above any test
    volume, so no trim occurs in this test."""
    pane = LogPane()  # no cfg
    qtbot.addWidget(pane)
    for i in range(20):
        pane.append(f"line {i}")
    assert "line 0" in pane.get_text()
    assert "line 19" in pane.get_text()


# ---------------------------------------------------------------------------
# get_text and clear
# ---------------------------------------------------------------------------


def test_get_text_returns_full_content(qtbot):
    """``get_text()`` is the public Copy-Log helper — must return all
    lines including the final one."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("alpha")
    pane.append("beta")
    pane.append("gamma")
    text = pane.get_text()
    assert "alpha" in text
    assert "beta" in text
    assert "gamma" in text


def test_clear_empties_log(qtbot):
    """``clear()`` empties the log without raising."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("about to be cleared")
    pane.clear()
    assert pane.get_text().strip() == ""


# ---------------------------------------------------------------------------
# Log-level classification — auto-color warn/error lines
#
# Added 2026-05-04 alongside the QSystemTrayIcon / byte-progress UX
# pass.  Classifier mirrors ``status_role_for_message`` so the live
# log stays consistent with the status bar.  Pinned tightly because
# false positives (a benign info line painted red) would erode trust
# in the color signal.
# ---------------------------------------------------------------------------


def test_classify_error_prefix():
    assert _classify_log_line("ERROR — disk full") == "error"
    assert _classify_log_line("ERROR: scan aborted") == "error"
    assert _classify_log_line("FAILED to open drive") == "error"
    assert _classify_log_line("Traceback (most recent call last):") == "error"


def test_classify_warn_prefix():
    assert _classify_log_line("WARNING: low disk space") == "warn"
    assert _classify_log_line("[WARN] makemkvcon retried") == "warn"
    assert _classify_log_line("Cancelled.") == "warn"
    assert _classify_log_line("Aborted by user") == "warn"


def test_classify_strips_leading_timestamp():
    """Real log lines arrive with a ``[HH:MM:SS]`` prefix added by
    the controller.  The classifier must look past it."""
    assert _classify_log_line("[11:27:46] ERROR — disk full") == "error"
    assert _classify_log_line("[11:27:46] WARNING: ...") == "warn"
    assert _classify_log_line("[11:27:46] Cancelled.") == "warn"


def test_classify_info_returns_none():
    """Default log lines must not get colored — only obvious
    warn/error prefixes do.  Pinned to defend against the classifier
    growing too aggressive over time."""
    assert _classify_log_line("Disc scan complete. Found 2 titles.") is None
    assert _classify_log_line("Ripping: 33%  ~12m 30s remaining") is None
    assert _classify_log_line("BEST: Title 1 (score=1.000)") is None
    assert _classify_log_line("[11:27:46] Movie folder: ...") is None
    # "no errors found" is a benign info line — must not trip the
    # error classifier just because it contains the word "errors".
    assert _classify_log_line("No errors found.") is None


def test_append_warn_line_gets_warn_color(qtbot):
    """End-to-end: append a line that classifies as warn → the
    resulting block carries the warn color from the active palette."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("WARNING: low disk space")
    expected = pane.tag_colors["warn"]
    # Block 0 is the first (and only) line.
    assert pane.block_color_at(0) == expected


def test_append_error_line_gets_error_color(qtbot):
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("ERROR — makemkvcon exited 1")
    expected = pane.tag_colors["error"]
    assert pane.block_color_at(0) == expected


def test_append_info_line_has_no_color(qtbot):
    """Info lines (the bulk of the log) stay default-colored — the
    palette's regular foreground.  The block-color helper returns
    None when no per-block color was applied."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("Disc scan complete. Found 2 titles.")
    assert pane.block_color_at(0) is None


def test_explicit_tag_overrides_classifier(qtbot):
    """If the caller passes an explicit tag, the classifier must
    not second-guess it.  Pinned because the prompt/answer flow
    relies on this — those messages can contain words that would
    otherwise trip the warn classifier."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("WARNING about something the user typed", tag="prompt")
    assert pane.block_color_at(0) == pane.tag_colors["prompt"]


# ---------------------------------------------------------------------------
# Severity glyph prefix — added 2026-05-04 per docs/symbol-library.md
#
# Color-coding is the live-UI signal; the glyph is the plain-text
# signal that survives a copy-log round-trip.  Pinned tightly so a
# careless refactor can't drop one or the other.
# ---------------------------------------------------------------------------


def test_warn_line_gets_warning_glyph_prefix(qtbot):
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("WARNING: low disk space")
    assert pane.get_text().startswith("⚠  ")  # ⚠
    assert "WARNING: low disk space" in pane.get_text()


def test_error_line_gets_cross_glyph_prefix(qtbot):
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("ERROR — makemkvcon exited 1")
    assert pane.get_text().startswith("✗  ")  # ✗
    assert "ERROR — makemkvcon exited 1" in pane.get_text()


def test_info_line_has_no_glyph_prefix(qtbot):
    """Plain info lines (the bulk of the log) stay unprefixed —
    adding ⓘ to every line would be visual noise."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("Disc scan complete. Found 2 titles.")
    text = pane.get_text()
    assert not text.startswith("⚠")  # no warn glyph
    assert not text.startswith("✗")  # no error glyph
    assert text.startswith("Disc scan complete.")


def test_explicit_tag_skips_glyph_prefix(qtbot):
    """When the caller passes an explicit tag (e.g., ``"prompt"``),
    the glyph prefix MUST NOT be applied.  Pinned because the
    classifier could otherwise double-flag a prompt that happens
    to contain "WARNING" — we already pin that the color stays
    "prompt", and the glyph must follow the same rule."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("WARNING about something the user typed", tag="prompt")
    text = pane.get_text()
    assert not text.startswith("⚠")
    assert text.startswith("WARNING about")


def test_glyph_prefix_with_timestamped_log_line(qtbot):
    """Real log lines arrive with a ``[HH:MM:SS]`` prefix.  The
    classifier looks past it — the glyph still gets prepended at
    the front of the rendered line, before the timestamp.  This
    makes the severity scan-friendly even when the timestamp gets
    in the way."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("[11:27:46] ERROR — disk full")
    text = pane.get_text()
    assert text.startswith("✗  [11:27:46] ERROR")


# ---------------------------------------------------------------------------
# Appearance toggles — added 2026-05-04 with the Appearance tab.
#
# The classifier-based color + glyph behavior is still tested above;
# these tests pin that the toggles correctly suppress each signal
# independently and that the runtime setters work for click-to-apply.
# ---------------------------------------------------------------------------


def test_color_levels_disabled_via_cfg(qtbot):
    """Constructing with ``opt_log_color_levels=False`` skips the
    color application even though the line still classifies as
    warn."""
    pane = LogPane(cfg={"opt_log_color_levels": False})
    qtbot.addWidget(pane)
    pane.append("WARNING: low disk space")
    # No per-block color applied — classifier doesn't paint.
    assert pane.block_color_at(0) is None


def test_color_levels_disabled_still_keeps_glyph_prefix(qtbot):
    """Coloring and glyph are independently toggleable.  Disabling
    color must not strip the glyph (and vice versa)."""
    pane = LogPane(cfg={
        "opt_log_color_levels": False,
        "opt_log_glyph_prefix": True,
    })
    qtbot.addWidget(pane)
    pane.append("WARNING: low disk space")
    assert pane.block_color_at(0) is None
    assert pane.get_text().startswith("⚠  ")


def test_glyph_prefix_disabled_via_cfg(qtbot):
    """Constructing with ``opt_log_glyph_prefix=False`` strips the
    ⚠/✗ prefix.  Color (when enabled) still applies."""
    pane = LogPane(cfg={
        "opt_log_color_levels": True,
        "opt_log_glyph_prefix": False,
    })
    qtbot.addWidget(pane)
    pane.append("WARNING: low disk space")
    text = pane.get_text()
    assert not text.startswith("⚠")
    # Color still applies.
    assert pane.block_color_at(0) == pane.tag_colors["warn"]


def test_both_disabled_renders_plain_text(qtbot):
    """Both toggles off → log is exactly what the caller passed in:
    no glyph, no color, classifier doesn't even run."""
    pane = LogPane(cfg={
        "opt_log_color_levels": False,
        "opt_log_glyph_prefix": False,
    })
    qtbot.addWidget(pane)
    pane.append("ERROR — disk full")
    assert pane.get_text() == "ERROR — disk full"
    assert pane.block_color_at(0) is None


def test_set_color_levels_enabled_runtime_toggle(qtbot):
    """Runtime setter — used by the Appearance tab for live preview."""
    pane = LogPane()
    qtbot.addWidget(pane)
    assert pane.color_levels_enabled is True
    pane.set_color_levels_enabled(False)
    assert pane.color_levels_enabled is False
    pane.set_color_levels_enabled(True)
    assert pane.color_levels_enabled is True


def test_set_glyph_prefix_enabled_runtime_toggle(qtbot):
    pane = LogPane()
    qtbot.addWidget(pane)
    assert pane.glyph_prefix_enabled is True
    pane.set_glyph_prefix_enabled(False)
    assert pane.glyph_prefix_enabled is False
    pane.set_glyph_prefix_enabled(True)
    assert pane.glyph_prefix_enabled is True


def test_runtime_toggle_only_affects_subsequent_appends(qtbot):
    """Toggling at runtime must not re-render existing log content;
    only new ``append`` calls reflect the new state.  Pinned
    because the alternative (re-rendering history) is expensive
    and would lose the "click-to-apply" interactive feel."""
    pane = LogPane()
    qtbot.addWidget(pane)
    pane.append("WARNING: line one")
    # Toggle off, append a new line.
    pane.set_color_levels_enabled(False)
    pane.set_glyph_prefix_enabled(False)
    pane.append("WARNING: line two")
    text = pane.get_text()
    # First line still has the glyph (it was rendered with toggles ON).
    assert text.startswith("⚠  WARNING: line one")
    # Second line is plain (toggles OFF when it was rendered).
    assert "\nWARNING: line two" in text
