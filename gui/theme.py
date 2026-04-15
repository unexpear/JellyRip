"""Shared GUI theme primitives for JellyRip."""

from __future__ import annotations

import re
from collections.abc import Mapping


APP_THEME: dict[str, str] = {
    "window_bg": "#091321",
    "header_bg": "#112540",
    "header_border": "#31465f",
    "surface": "#13253d",
    "surface_alt": "#0d192a",
    "surface_deep": "#0a1320",
    "panel_border": "#31465f",
    "title": "#27b8ff",
    "text": "#f5f9ff",
    "muted": "#a8b7ca",
    "muted_soft": "#7f92ab",
    "input_bg": "#f6f8fc",
    "input_fg": "#0f1726",
    "toolbar_button": "#14263d",
    "toolbar_button_active": "#425470",
    "toolbar_button_text": "#f2f7ff",
    "toolbar_button_muted": "#d3ddec",
    "green": "#05b53f",
    "teal": "#0fa19a",
    "blue": "#2b63f2",
    "purple": "#a400ff",
    "orange": "#ff5a00",
    "abort": "#ff2f42",
    "ready_text": "#27d8ff",
    "progress_fill": "#00ee88",
    "progress_trough": "#122338",
    "log_bg": "#0d1522",
    "log_text": "#00f082",
    "pill_idle_bg": "#182a44",
    "pill_idle_border": "#37506f",
    "pill_active_bg": "#12311f",
    "pill_active_border": "#00ee88",
    "pill_warn_bg": "#3d2d10",
    "pill_warn_border": "#ffb34d",
    "pill_error_bg": "#411720",
    "pill_error_border": "#ff6c7b",
}


_HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{6}$")


def normalize_theme_color(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    token = value.strip()
    if not token or not _HEX_COLOR_RE.fullmatch(token):
        return None
    if not token.startswith("#"):
        token = f"#{token}"
    return token.lower()


def sanitize_theme_overrides(raw: object) -> dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}
    cleaned: dict[str, str] = {}
    for key, value in raw.items():
        if key not in APP_THEME:
            continue
        normalized = normalize_theme_color(value)
        if normalized is not None:
            cleaned[str(key)] = normalized
    return cleaned


def build_app_theme(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    theme = dict(APP_THEME)
    theme.update(sanitize_theme_overrides(overrides))
    return theme
