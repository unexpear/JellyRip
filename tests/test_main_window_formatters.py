"""Tests for pure presentation formatters in gui/main_window.py.

These methods take a domain model and return display data (string, tuple,
bool) with no Tk side effects. They're already separated from widget code,
so no source refactor is needed — just direct tests.

Pattern (mirrors `tests/test_imports.py`):
    with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
        from gui.main_window import JellyRipperGUI
    gui = object.__new__(JellyRipperGUI)  # skip Tk __init__

Methods covered:
- `_format_drive_label`     (@staticmethod, line 252) — MakeMKVDriveInfo → str
- `_trim_context_label`     (@staticmethod, line 544) — text, limit → str
- `_main_status_style_for_message`        (line 622) — message → 3-color tuple
- `_get_text_widget_selection`            (line 465) — widget → str
- `_ffmpeg_version_ok`                    (line 5163) — exe path → bool
"""

from __future__ import annotations

import unittest.mock

import pytest

from utils.helpers import MakeMKVDriveInfo


class _FakeTkBase:
    pass


with unittest.mock.patch("tkinter.Tk", new=_FakeTkBase):
    from gui.main_window import JellyRipperGUI


def _gui() -> JellyRipperGUI:
    """Construct a JellyRipperGUI without running its Tk __init__.

    Per the test_imports.py convention, this gives access to all instance
    methods. Methods that touch Tk state must have any required attributes
    set explicitly by the caller before invocation.
    """
    return object.__new__(JellyRipperGUI)


# --------------------------------------------------------------------------
# _format_drive_label — static, pure
# --------------------------------------------------------------------------


def _drive(**overrides) -> MakeMKVDriveInfo:
    base = dict(
        index=0,
        state_code=2,
        flags_code=0,
        disc_type_code=0,
        drive_name="LG BH16NS40",
        disc_name="MOVIE_DISC",
        device_path="D:",
    )
    base.update(overrides)
    return MakeMKVDriveInfo(**base)


def test_format_drive_label_includes_all_fields_when_populated():
    label = JellyRipperGUI._format_drive_label(_drive())
    assert "Drive 0:" in label
    assert "LG BH16NS40" in label
    assert "Disc: MOVIE_DISC" in label
    assert "Path: D:" in label
    assert "State: ready (2)" in label


@pytest.mark.parametrize(
    "field,blank_value,expected_substring",
    [
        ("drive_name", "", "Unknown drive"),
        ("disc_name", "", "Disc: No disc"),
        ("device_path", "", "Path: disc:0"),  # falls back to f"disc:{index}"
    ],
)
def test_format_drive_label_uses_fallbacks_for_missing_fields(
    field, blank_value, expected_substring
):
    drive = _drive(**{field: blank_value})
    label = JellyRipperGUI._format_drive_label(drive)
    assert expected_substring in label


@pytest.mark.parametrize(
    "state_code,expected_state_text",
    [
        (2, "ready (2)"),
        (0, "empty (0)"),
        (256, "unavailable (256)"),
        (99, "state 99 (99)"),  # unknown code falls through
    ],
)
def test_format_drive_label_decodes_state_codes(state_code, expected_state_text):
    label = JellyRipperGUI._format_drive_label(_drive(state_code=state_code))
    assert f"State: {expected_state_text}" in label


# --------------------------------------------------------------------------
# _trim_context_label — static, pure
# --------------------------------------------------------------------------


def test_trim_context_label_passes_short_text_through():
    assert JellyRipperGUI._trim_context_label("hello") == "hello"


def test_trim_context_label_collapses_internal_whitespace():
    assert JellyRipperGUI._trim_context_label("hello   world\n\ttest") == "hello world test"


def test_trim_context_label_keeps_text_at_exactly_the_limit():
    s = "x" * 40
    assert JellyRipperGUI._trim_context_label(s, limit=40) == s


def test_trim_context_label_trims_with_ellipsis_when_over_limit():
    s = "x" * 50
    result = JellyRipperGUI._trim_context_label(s, limit=40)
    assert result.endswith("...")
    # The output is at most `limit` chars total: limit-3 of the original + "...".
    assert len(result) == 40


def test_trim_context_label_rstrips_before_appending_ellipsis():
    """Pin the rstrip behavior — trailing whitespace just before the cut
    point is removed before the ellipsis is appended."""
    text = "abcd" + " " * 10 + "efgh"          # "abcd          efgh"
    # After whitespace-collapse: "abcd efgh" (9 chars). Stays as-is.
    assert JellyRipperGUI._trim_context_label(text, limit=40) == "abcd efgh"
    # Force a trim with whitespace just before the cut: a longer input where
    # the limit-3 boundary lands on whitespace.
    long_input = "word " * 20  # "word word word ..." (5 chars per word)
    result = JellyRipperGUI._trim_context_label(long_input, limit=12)
    assert result.endswith("...")
    # No double-space before "..."
    assert "  ..." not in result


def test_trim_context_label_handles_empty_string():
    assert JellyRipperGUI._trim_context_label("") == ""


# --------------------------------------------------------------------------
# _main_status_style_for_message — uses self._theme (or builds default)
# --------------------------------------------------------------------------


@pytest.fixture
def gui_with_default_theme():
    """A minimal JellyRipperGUI with `_theme` pre-populated to the default
    theme. Returns (gui, theme) for cross-checking expected colors.

    Why we set `_theme` explicitly instead of relying on the source's
    `getattr(self, "_theme", None) or build_app_theme()` fallback: when
    other test files run first and import `gui.main_window` with the real
    `tkinter.Tk` base class, our module-level `_FakeTkBase` patch doesn't
    take effect (sys.modules cache). The instance returned by
    `object.__new__(JellyRipperGUI)` then has the real Tk in its MRO
    without `Tk.__init__` ever running, so `getattr(self, "_theme", None)`
    falls into `Tk.__getattr__` which recurses on the missing `self.tk`
    attribute. Setting `_theme` directly bypasses that path while still
    exercising the same downstream branch logic this fixture is meant
    to test."""
    from gui.theme import build_app_theme
    theme = build_app_theme()
    gui = _gui()
    gui._theme = theme
    return gui, theme


@pytest.mark.parametrize(
    "msg",
    ["", "  ", None, "Ready", "ready", "IDLE", "Choose a mode to begin"],
)
def test_main_status_style_idle_messages_use_idle_pill(gui_with_default_theme, msg):
    gui, theme = gui_with_default_theme
    bg, border, fg = gui._main_status_style_for_message(msg)
    assert (bg, border, fg) == (
        theme["pill_idle_bg"],
        theme["pill_idle_border"],
        theme["ready_text"],
    )


@pytest.mark.parametrize(
    "msg",
    [
        "Operation failed",
        "Encountered an ERROR",
        "ffmpeg missing",
        "Invalid input",
        "Drive blocked",
        "Resource unavailable",
    ],
)
def test_main_status_style_error_tokens_use_error_pill(gui_with_default_theme, msg):
    gui, theme = gui_with_default_theme
    bg, border, fg = gui._main_status_style_for_message(msg)
    assert bg == theme["pill_error_bg"]
    assert border == theme["pill_error_border"]
    assert fg == theme["pill_error_border"]


@pytest.mark.parametrize(
    "msg",
    [
        "Needs attention",
        "Warning: low space",
        "Aborting rip",
        "User cancelled",
        "Operation canceled",
        "Will retry",
        "Waiting for disc",
    ],
)
def test_main_status_style_warning_tokens_use_warning_pill(gui_with_default_theme, msg):
    gui, theme = gui_with_default_theme
    bg, border, fg = gui._main_status_style_for_message(msg)
    assert bg == theme["pill_warn_bg"]
    assert border == theme["pill_warn_border"]
    assert fg == theme["pill_warn_border"]


def test_main_status_style_active_messages_use_active_pill(gui_with_default_theme):
    gui, theme = gui_with_default_theme
    # Anything that doesn't match idle/error/warning falls through to active.
    bg, border, fg = gui._main_status_style_for_message("Ripping title 1")
    assert bg == theme["pill_active_bg"]
    assert border == theme["pill_active_border"]
    assert fg == theme["pill_active_border"]


def test_main_status_style_error_token_wins_over_warning_token():
    """When both an error keyword and a warning keyword appear in the same
    message, the error branch wins because it's checked first. Pin this
    ordering so a refactor can't quietly invert priority."""
    from gui.theme import build_app_theme
    theme = build_app_theme()
    gui = _gui()
    gui._theme = theme  # see gui_with_default_theme fixture for rationale
    # "failed" → error; "retry" → warning. Both present → error wins.
    bg, _, _ = gui._main_status_style_for_message("Rip failed; will retry")
    assert bg == theme["pill_error_bg"]


def test_main_status_style_falls_back_to_build_app_theme_when_self_theme_is_none():
    """Source: `colors = getattr(self, "_theme", None) or build_app_theme()`.
    When `_theme` is None (or any other falsy value), the fallback fires
    and the result matches the default theme. Sets `_theme = None`
    explicitly so `getattr` doesn't fall through to `Tk.__getattr__` and
    recurse on the missing `self.tk` (see fixture rationale)."""
    from gui.theme import build_app_theme
    gui = _gui()
    gui._theme = None  # explicit: hits the `... or build_app_theme()` branch
    expected = build_app_theme()

    bg, border, fg = gui._main_status_style_for_message("ready")

    assert (bg, border, fg) == (
        expected["pill_idle_bg"],
        expected["pill_idle_border"],
        expected["ready_text"],
    )


def test_main_status_style_uses_self_theme_when_set():
    """If `self._theme` is already populated, the method must use it
    instead of rebuilding from `build_app_theme()`."""
    gui = _gui()
    gui._theme = {
        "pill_idle_bg": "#000000",
        "pill_idle_border": "#111111",
        "ready_text": "#222222",
        "pill_error_bg": "#aa0000",
        "pill_error_border": "#bb0000",
        "pill_warn_bg": "#aa6600",
        "pill_warn_border": "#bb6600",
        "pill_active_bg": "#00aa00",
        "pill_active_border": "#00bb00",
    }
    bg, border, fg = gui._main_status_style_for_message("ready")
    assert (bg, border, fg) == ("#000000", "#111111", "#222222")


# --------------------------------------------------------------------------
# _get_text_widget_selection — defensive widget dispatcher
#
# Note: the real `tk.Entry`/`tk.Text` branches require a running Tk root,
# which we deliberately don't provide here. These tests pin the *defensive*
# behavior — the method must return "" and never raise for any input that
# isn't a recognized widget (or that raises on attribute access).
# --------------------------------------------------------------------------


def test_get_text_widget_selection_returns_empty_for_unrecognized_widget():
    gui = _gui()
    not_a_widget = object()
    assert gui._get_text_widget_selection(not_a_widget) == ""


def test_get_text_widget_selection_returns_empty_when_widget_raises():
    """Any exception during inspection must be swallowed and return ""."""
    class _ExplodingWidget:
        def __getattr__(self, name):
            raise RuntimeError(f"hostile attribute access: {name}")
    gui = _gui()
    assert gui._get_text_widget_selection(_ExplodingWidget()) == ""


def test_get_text_widget_selection_returns_empty_for_none():
    gui = _gui()
    assert gui._get_text_widget_selection(None) == ""


# --------------------------------------------------------------------------
# _ffmpeg_version_ok — gates the encode pipeline against ancient FFmpeg builds
# --------------------------------------------------------------------------


def test_ffmpeg_version_ok_returns_true_for_empty_path():
    """Empty path: defer to the normal "binary not found" error downstream."""
    gui = _gui()
    assert gui._ffmpeg_version_ok("") is True


def test_ffmpeg_version_ok_returns_true_when_file_does_not_exist(monkeypatch):
    monkeypatch.setattr("gui.main_window.os.path.isfile", lambda _p: False)
    gui = _gui()
    assert gui._ffmpeg_version_ok(r"C:\nope\ffmpeg.exe") is True


def test_ffmpeg_version_ok_returns_true_when_version_is_current(monkeypatch):
    monkeypatch.setattr("gui.main_window.os.path.isfile", lambda _p: True)
    monkeypatch.setattr(
        "gui.main_window.get_ffmpeg_version_info",
        lambda _exe: {"too_old": False, "label": "6.1.1", "build_year": 2024},
    )
    gui = _gui()
    assert gui._ffmpeg_version_ok(r"C:\ok\ffmpeg.exe") is True


def test_ffmpeg_version_ok_prompts_user_when_too_old_and_returns_choice(monkeypatch):
    """When the binary is too old, the function shows a blocking warning
    and returns whatever the user picked. This pins the contract so the
    pipeline gate can be relied upon: True means "user said proceed",
    False means "user said abort"."""
    monkeypatch.setattr("gui.main_window.os.path.isfile", lambda _p: True)
    monkeypatch.setattr(
        "gui.main_window.get_ffmpeg_version_info",
        lambda _exe: {"too_old": True, "label": "3.4.2", "build_year": 2017},
    )
    prompts: list[tuple] = []

    def fake_askyesno(title, msg, parent=None):
        prompts.append((title, msg, parent))
        return True

    monkeypatch.setattr("gui.main_window.messagebox.askyesno", fake_askyesno)

    gui = _gui()
    assert gui._ffmpeg_version_ok(r"C:\old\ffmpeg.exe") is True

    # Pin user-facing message content so changes here are deliberate.
    assert len(prompts) == 1
    title, msg, _parent = prompts[0]
    assert "FFmpeg Too Old" in title
    assert "3.4.2" in msg
    assert "built 2017" in msg
    assert "FFmpeg 4.0+" in msg


def test_ffmpeg_version_ok_returns_false_when_user_aborts_old_binary(monkeypatch):
    monkeypatch.setattr("gui.main_window.os.path.isfile", lambda _p: True)
    monkeypatch.setattr(
        "gui.main_window.get_ffmpeg_version_info",
        lambda _exe: {"too_old": True, "label": "3.0.0", "build_year": None},
    )
    monkeypatch.setattr(
        "gui.main_window.messagebox.askyesno",
        lambda *_a, **_kw: False,
    )

    gui = _gui()
    assert gui._ffmpeg_version_ok(r"C:\old\ffmpeg.exe") is False


def test_ffmpeg_version_ok_omits_build_year_when_unknown(monkeypatch):
    """Pin the message-construction branch: when build_year is None, the
    "(built YYYY)" suffix is omitted entirely."""
    monkeypatch.setattr("gui.main_window.os.path.isfile", lambda _p: True)
    monkeypatch.setattr(
        "gui.main_window.get_ffmpeg_version_info",
        lambda _exe: {"too_old": True, "label": "3.0.0", "build_year": None},
    )
    captured: list[str] = []
    monkeypatch.setattr(
        "gui.main_window.messagebox.askyesno",
        lambda _t, msg, **_kw: captured.append(msg) or True,
    )

    gui = _gui()
    gui._ffmpeg_version_ok(r"C:\old\ffmpeg.exe")

    assert captured
    assert "built " not in captured[0]
