"""Theme loader for the PySide6 GUI.

Themes are color **token** sets rendered to QSS at runtime via
``gui_qt.qss_render`` — no static ``.qss`` files are read at load time.
The built-in themes live in ``gui_qt.themes``; user-made custom themes
live as JSON under ``%APPDATA%\\JellyRip\\themes\\``
(``gui_qt.custom_themes``), created/edited in the Theme Maker dialog
(``gui_qt/dialogs/theme_maker.py``).  So the picker shows the built-ins
plus anything the user has made or imported, and either kind renders the
exact same way.

``tools/build_qss.py`` still writes the built-in themes to
``gui_qt/qss/*.qss`` as committed dev-time artifacts (handy for diffing
a token change in review), but those files are no longer read at
runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from gui_qt.qss_render import render_qss_from_tokens
from gui_qt.themes import THEMES, THEMES_BY_ID

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication


# Kept for backward-compat with anything still referencing it; the
# committed ``.qss`` files are now just dev-time diff artifacts and are
# no longer read at runtime (themes render from tokens).
THEME_DIR = Path(__file__).parent / "qss"


def _custom_module() -> Any:
    """Lazy import so a stale/broken custom-themes dir never blocks
    startup or the built-in theme path."""
    try:
        from gui_qt import custom_themes
        return custom_themes
    except Exception:
        return None


def theme_tokens(theme_name: str) -> dict[str, str] | None:
    """Return the token dict for a theme id (built-in or custom), or
    ``None`` if the id resolves to neither."""
    built_in = THEMES_BY_ID.get(theme_name)
    if built_in is not None:
        return dict(built_in.tokens)
    cm = _custom_module()
    if cm is not None:
        custom = cm.get_custom(theme_name)
        if custom is not None:
            return dict(custom.get("tokens", {}))
    return None


def theme_meta(theme_name: str) -> tuple[str, str, str]:
    """Return ``(display_name, family, notes)`` for a theme id, with
    sensible fallbacks for unknown ids."""
    built_in = THEMES_BY_ID.get(theme_name)
    if built_in is not None:
        return built_in.name, built_in.family, built_in.notes
    cm = _custom_module()
    if cm is not None:
        custom = cm.get_custom(theme_name)
        if custom is not None:
            return (
                str(custom.get("name", theme_name)),
                str(custom.get("family", "dark")),
                "",
            )
    return theme_name, "dark", ""


def list_themes() -> list[str]:
    """Return all theme ids: the built-in themes (in declaration order)
    first, then user-made custom themes (sorted).  A custom id that
    collides with a built-in is dropped so built-ins can't be shadowed.
    """
    builtin = [t.id for t in THEMES]
    custom: list[str] = []
    cm = _custom_module()
    if cm is not None:
        try:
            custom = sorted(str(c["id"]) for c in cm.list_custom())
        except Exception:
            custom = []
    seen = set(builtin)
    return builtin + [c for c in custom if c not in seen]


def load_theme(app: "QApplication", theme_name: str) -> None:
    """Render the named theme's tokens to QSS and apply them to the
    running ``QApplication``.

    Works for both built-in and custom themes — everything renders from
    color tokens via ``gui_qt.qss_render``.  Raises ``FileNotFoundError``
    (name kept for caller compatibility — ``gui_qt.app`` already catches
    it) if the id resolves to no built-in or custom theme, or if the
    token set can't be rendered.  Callers surface a clear error rather
    than silently rendering an unstyled window or crashing startup.
    """
    tokens = theme_tokens(theme_name)
    if tokens is None:
        raise FileNotFoundError(
            f"Theme not found: {theme_name!r}. "
            f"Available: {', '.join(list_themes()) or '<none>'}"
        )
    name, family, notes = theme_meta(theme_name)
    try:
        qss = render_qss_from_tokens(
            tokens, id=theme_name, name=name, family=family, notes=notes,
        )
    except Exception as exc:
        raise FileNotFoundError(
            f"Theme {theme_name!r} could not be rendered "
            f"({type(exc).__name__}: {exc})."
        ) from exc
    app.setStyleSheet(qss)
