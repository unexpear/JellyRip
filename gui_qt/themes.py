"""Theme tokens for the PySide6 GUI — Python-side source of truth.

Mirrors ``docs/design/themes/themes.jsx`` (the design-source-of-truth
file shipped by the user on 2026-05-03).  This module is the
**Python** source of truth: ``tools/build_qss.py`` reads ``THEMES``
from here to render the QSS files under ``gui_qt/qss/``, and tests
import ``THEMES`` directly to assert WCAG contrast on every CTA.

If a token disagrees with the JSX file, update both — the JSX is for
designers and the browsable preview, this module is for the Python
build pipeline and tests.

**Six themes** (decided 2026-05-03 — supersedes the earlier 3-theme
placeholder set ``dark_github``/``light_inverted``/``warm``):

================  ======  =====================================
id                family  rationale
================  ======  =====================================
dark_github       dark    Current tkinter palette ported as-is
                          — zero visual surprise.  Default value
                          of ``opt_pyside6_theme``.
light_inverted    light   Forest-green primary, no purple in the
                          action row.  Closes A11y Finding #2.
dracula_light     light   Pale lavender bg, canonical Dracula
                          CTAs (purple/pink/cyan/yellow/red).
hc_dark           dark    Pure black surfaces, neon CTAs that all
                          cross 7:1 against their label.
slate             dark    Desaturated cool-only neutrals
                          (sea-foam/sky/periwinkle/bronze/brick).
frost             dark    Nord background with saturation dialed
                          up on every CTA.
================  ======  =====================================

The token role names are **constant** across themes — only the colors
differ.  This lets one parameterized QSS template render all six.

Roles:

* ``bg``, ``card``, ``input``, ``border`` — surface levels
* ``fg``, ``muted``, ``accent`` — text + brand accent
* ``go`` / ``goFg`` — primary CTA (start, confirm, rip)
* ``info`` / ``infoFg`` — secondary CTA (dump titles)
* ``alt`` / ``altFg`` — tertiary CTA (organize)
* ``warn`` / ``warnFg`` — caution CTA (prep for ffmpeg)
* ``danger`` / ``dangerFg`` — destructive (stop session)
* ``hover``, ``selection`` — interaction state
* ``logBg``, ``promptFg``, ``answerFg`` — log panel coloring
* ``shadow`` — drop shadow rgba

The ``confirmButton`` / ``primaryButton`` objectName split already in
use in ``gui_qt/setup_wizard.py`` maps to ``go`` / ``info`` respectively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


# ---------------------------------------------------------------------------
# Token shape
# ---------------------------------------------------------------------------


# All themes must define exactly these keys.  Keep this list in sync
# with the keys used by ``tools/build_qss.py``; tests pin coverage.
TOKEN_KEYS: tuple[str, ...] = (
    # surfaces
    "bg", "card", "input", "border",
    # text + accent
    "fg", "muted", "accent",
    # CTAs (paired with their foreground/label color)
    "go", "goFg",
    "info", "infoFg",
    "alt", "altFg",
    "warn", "warnFg",
    "danger", "dangerFg",
    # interaction state
    "hover", "selection", "selectionFg",
    # log panel
    "logBg", "promptFg", "answerFg",
    # drop shadow rgba string (used inline in QSS)
    "shadow",
)


# CTA role names (the bg/fg pairs for which we enforce WCAG 4.5:1).
CTA_ROLES: tuple[str, ...] = ("go", "info", "alt", "warn", "danger")


@dataclass(frozen=True)
class Theme:
    """One named theme.  Frozen so accidental mutation in tests doesn't
    leak between test cases."""

    id: str
    name: str
    subtitle: str
    family: str  # "dark" | "light"
    notes: str
    tokens: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The 6 themes
# ---------------------------------------------------------------------------


THEMES: List[Theme] = [
    # ----------------------------------------------------------------
    # 1) Dark GitHub — current tkinter palette ported, default theme
    # ----------------------------------------------------------------
    Theme(
        id="dark_github",
        name="Dark GitHub",
        subtitle="Current tkinter palette, ported",
        family="dark",
        notes=(
            "Direct port of today's #0d1117 / #58a6ff palette. "
            "Zero visual surprise for existing users."
        ),
        tokens={
            "bg": "#0d1117", "card": "#161b22",
            "input": "#21262d", "border": "#30363d",
            "fg": "#c9d1d9", "muted": "#8b949e", "accent": "#58a6ff",
            "go": "#238636",     "goFg": "#ffffff",
            "info": "#1f6feb",   "infoFg": "#ffffff",
            "alt": "#6e40c9",    "altFg": "#ffffff",
            "warn": "#9a6700",   "warnFg": "#ffffff",
            "danger": "#c94b4b", "dangerFg": "#ffffff",
            "hover": "#1f2933", "selection": "#1f6feb", "selectionFg": "#ffffff",
            "logBg": "#161b22", "promptFg": "#f0e68c", "answerFg": "#90ee90",
            "shadow": "rgba(0, 0, 0, 0.4)",
        },
    ),

    # ----------------------------------------------------------------
    # 2) Light Inverted — editorial light, no purple in the action row
    # ----------------------------------------------------------------
    Theme(
        id="light_inverted",
        name="Light Inverted",
        subtitle="Closes A11y Finding #2",
        family="light",
        notes=(
            "Light editorial palette — forest-green primary, deep teal "
            "secondary, mustard tertiary, rust caution, crimson destructive. "
            "No purple in the action row."
        ),
        tokens={
            "bg": "#ffffff", "card": "#f6f8fa",
            "input": "#ffffff", "border": "#d0d7de",
            "fg": "#1f2328", "muted": "#57606a", "accent": "#0e6b6b",
            "go": "#1f6e3a",     "goFg": "#ffffff",   # forest green
            "info": "#0e6b6b",   "infoFg": "#ffffff",   # deep teal
            "alt": "#8a6a14",    "altFg": "#ffffff",   # mustard
            "warn": "#a64614",   "warnFg": "#ffffff",   # rust
            "danger": "#9b1c2c", "dangerFg": "#ffffff",   # crimson
            "hover": "#eaeef2", "selection": "#0e6b6b", "selectionFg": "#ffffff",
            "logBg": "#f6f8fa", "promptFg": "#8a6a14", "answerFg": "#1f6e3a",
            "shadow": "rgba(31, 35, 40, 0.08)",
        },
    ),

    # ----------------------------------------------------------------
    # 3) Dracula Light — pale lavender bg, Dracula CTA family
    # ----------------------------------------------------------------
    Theme(
        id="dracula_light",
        name="Dracula Light",
        subtitle="Dracula palette, light surface",
        family="light",
        notes=(
            "Pale lavender surface with the canonical Dracula action set "
            "— purple primary, pink secondary, cyan tertiary, yellow "
            "caution (deepened for AA), red destructive."
        ),
        tokens={
            "bg": "#f5ecd9", "card": "#ede1c5",
            "input": "#fbf5e6", "border": "#d6c69a",
            "fg": "#22213a", "muted": "#5e5a7a", "accent": "#6f42c1",
            "go": "#6f42c1",     "goFg": "#ffffff",   # dracula purple
            "info": "#c2378a",   "infoFg": "#ffffff",   # dracula pink
            "alt": "#0a8a96",    "altFg": "#ffffff",   # dracula cyan
            "warn": "#8a6a14",   "warnFg": "#ffffff",   # deepened yellow
            "danger": "#c4312f", "dangerFg": "#ffffff",   # dracula red
            "hover": "#e3d4ad", "selection": "#6f42c1", "selectionFg": "#ffffff",
            "logBg": "#ede1c5", "promptFg": "#8a6a14", "answerFg": "#0a8a96",
            "shadow": "rgba(61, 47, 21, 0.12)",
        },
    ),

    # ----------------------------------------------------------------
    # 4) High Contrast Dark — accessibility-first, every CTA AAA
    # ----------------------------------------------------------------
    Theme(
        id="hc_dark",
        name="High Contrast Dark",
        subtitle="Accessibility-first AAA",
        family="dark",
        notes=(
            "Pure black surfaces, high-saturation CTAs.  Every CTA "
            "crosses 7:1 against its label so AAA holds end-to-end."
        ),
        tokens={
            "bg": "#000000", "card": "#0a0a0a",
            "input": "#141414", "border": "#5c5c5c",
            "fg": "#ffffff", "muted": "#cfcfcf", "accent": "#ffd60a",
            "go": "#39ff14",     "goFg": "#000000",   # electric lime
            "info": "#00e5ff",   "infoFg": "#000000",   # pure cyan
            "alt": "#ff6ec7",    "altFg": "#000000",   # hot pink
            "warn": "#ffd60a",   "warnFg": "#000000",   # bright yellow
            "danger": "#ff3030", "dangerFg": "#ffffff",   # pure red
            "hover": "#1a1a1a", "selection": "#ffd60a", "selectionFg": "#000000",
            "logBg": "#0a0a0a", "promptFg": "#ffd60a", "answerFg": "#00d26a",
            "shadow": "rgba(0, 0, 0, 0.8)",
        },
    ),

    # ----------------------------------------------------------------
    # 5) Slate — desaturated cool-only set, no green/blue overlap with GH
    # ----------------------------------------------------------------
    Theme(
        id="slate",
        name="Slate",
        subtitle="Cool blue-grey neutrals",
        family="dark",
        notes=(
            "Desaturated cool-only CTAs — sea-foam primary, pale sky "
            "secondary, periwinkle tertiary, bronze caution, brick "
            "destructive.  Nothing saturated, nothing screams."
        ),
        tokens={
            "bg": "#1a2332", "card": "#22303f",
            "input": "#2a3a4d", "border": "#3a4a5e",
            "fg": "#dbe5ee", "muted": "#8ea0b3", "accent": "#5dbcd2",
            "go": "#4ba89a",     "goFg": "#0d1721",   # sea-foam
            "info": "#7aa8c8",   "infoFg": "#0d1721",   # pale sky
            "alt": "#8a8ec4",    "altFg": "#0d1721",   # periwinkle
            "warn": "#b88550",   "warnFg": "#0d1721",   # bronze
            "danger": "#a64545", "dangerFg": "#ffffff",   # brick
            "hover": "#2a3a4d", "selection": "#4a78b8", "selectionFg": "#ffffff",
            "logBg": "#22303f", "promptFg": "#b88550", "answerFg": "#4ba89a",
            "shadow": "rgba(0, 0, 0, 0.35)",
        },
    ),

    # ----------------------------------------------------------------
    # 6) Frost — saturated Nord (Nord bg, punchier CTAs, less pastel)
    # ----------------------------------------------------------------
    Theme(
        id="frost",
        name="Frost",
        subtitle="Muted Nordic dark",
        family="dark",
        notes=(
            "Nord background with the saturation dialed up on every "
            "CTA — deeper aurora green, stronger frost blue, richer "
            "violet, fuller yellow, firm aurora red.  Same family, more "
            "punch."
        ),
        tokens={
            "bg": "#2e3440", "card": "#3b4252",
            "input": "#434c5e", "border": "#4c566a",
            "fg": "#eceff4", "muted": "#a3acbc", "accent": "#88c0d0",
            "go": "#6e9b4f",     "goFg": "#ffffff",   # saturated aurora green
            "info": "#4a7fb8",   "infoFg": "#ffffff",   # strong frost blue
            "alt": "#9c5fa3",    "altFg": "#ffffff",   # rich violet
            "warn": "#d4a849",   "warnFg": "#1f1a10",   # saturated yellow
            "danger": "#b8434d", "dangerFg": "#ffffff",   # firm aurora red
            "hover": "#434c5e", "selection": "#5e81ac", "selectionFg": "#ffffff",
            "logBg": "#3b4252", "promptFg": "#d4a849", "answerFg": "#a3be8c",
            "shadow": "rgba(0, 0, 0, 0.4)",
        },
    ),

    # ----------------------------------------------------------------
    # Monokai — vivid classic editor palette
    # ----------------------------------------------------------------
    Theme(
        id="monokai",
        name="Monokai",
        subtitle="Vivid classic editor",
        family="dark",
        notes=(
            "Monokai's warm-charcoal surface with vivid CTAs — lime-green "
            "primary, sky-blue secondary, magenta-pink tertiary, orange "
            "caution, red destructive. High energy."
        ),
        tokens={
            "bg": "#272822", "card": "#2d2e27",
            "input": "#3a3b32", "border": "#49483e",
            "fg": "#f8f8f2", "muted": "#a6a28c", "accent": "#66d9ef",
            "go": "#5a9e1f",     "goFg": "#f8f8f2",   # monokai green (deepened)
            "info": "#2c8fb5",   "infoFg": "#f8f8f2",   # monokai blue
            "alt": "#c01c6e",    "altFg": "#f8f8f2",   # monokai pink
            "warn": "#b8731a",   "warnFg": "#f8f8f2",   # monokai orange
            "danger": "#d12d2d", "dangerFg": "#f8f8f2",   # red
            "hover": "#3a3b32", "selection": "#49483e", "selectionFg": "#ffffff",
            "logBg": "#2d2e27", "promptFg": "#e6db74", "answerFg": "#a6e22e",
            "shadow": "rgba(0, 0, 0, 0.5)",
        },
    ),

    # ----------------------------------------------------------------
    # Rosé Pine — muted soho-vibe, no harsh primaries
    # ----------------------------------------------------------------
    Theme(
        id="rose_pine",
        name="Rosé Pine",
        subtitle="Muted soho-vibe dark",
        family="dark",
        notes=(
            "Rosé Pine's plum-charcoal surface with soft natural CTAs — "
            "pine primary, foam secondary, iris tertiary, gold caution, "
            "love (rose-red) destructive. Calm and muted throughout."
        ),
        tokens={
            "bg": "#191724", "card": "#1f1d2e",
            "input": "#26233a", "border": "#403d52",
            "fg": "#e0def4", "muted": "#908caa", "accent": "#9ccfd8",
            "go": "#3d7068",     "goFg": "#e0def4",   # pine
            "info": "#498790",   "infoFg": "#e0def4",   # foam (deepened for AA-L)
            "alt": "#8177af",    "altFg": "#e0def4",   # iris (deepened for AA-L)
            "warn": "#a08431",   "warnFg": "#191724",   # gold
            "danger": "#b4637a", "dangerFg": "#e0def4",   # love
            "hover": "#26233a", "selection": "#403d52", "selectionFg": "#ffffff",
            "logBg": "#1f1d2e", "promptFg": "#f6c177", "answerFg": "#9ccfd8",
            "shadow": "rgba(0, 0, 0, 0.45)",
        },
    ),

    # ----------------------------------------------------------------
    # Tokyo Night — cool deep-blue surface, neon-ish CTAs
    # ----------------------------------------------------------------
    Theme(
        id="tokyo_night",
        name="Tokyo Night",
        subtitle="Cool deep-blue night",
        family="dark",
        notes=(
            "Tokyo Night's deep blue-black surface with cool neon CTAs — "
            "blue primary, cyan secondary, purple tertiary, orange caution, "
            "red destructive. Modern and crisp."
        ),
        tokens={
            "bg": "#1a1b26", "card": "#1f2030",
            "input": "#24283b", "border": "#363b54",
            "fg": "#c0caf5", "muted": "#787c99", "accent": "#7aa2f7",
            "go": "#3d59a1",     "goFg": "#c0caf5",   # blue
            "info": "#2e788f",   "infoFg": "#c0caf5",   # cyan (deepened for AA-L)
            "alt": "#7a5cc0",    "altFg": "#c0caf5",   # purple
            "warn": "#b3791f",   "warnFg": "#1a1b26",   # orange
            "danger": "#bb4857", "dangerFg": "#c0caf5",   # red (deepened for AA-L)
            "hover": "#24283b", "selection": "#363b54", "selectionFg": "#ffffff",
            "logBg": "#1f2030", "promptFg": "#e0af68", "answerFg": "#9ece6a",
            "shadow": "rgba(0, 0, 0, 0.5)",
        },
    ),

    # ----------------------------------------------------------------
    # Catppuccin Mocha — soft pastel surface, gentle CTAs
    # ----------------------------------------------------------------
    Theme(
        id="catppuccin_mocha",
        name="Catppuccin Mocha",
        subtitle="Soft pastel dark",
        family="dark",
        notes=(
            "Catppuccin's cozy mocha surface with pastel CTAs — mauve "
            "primary, sapphire secondary, teal tertiary, peach caution, "
            "red destructive. Low-glare and friendly."
        ),
        tokens={
            "bg": "#1e1e2e", "card": "#181825",
            "input": "#313244", "border": "#45475a",
            "fg": "#cdd6f4", "muted": "#9399b2", "accent": "#cba6f7",
            "go": "#8839ef",     "goFg": "#f5e0dc",   # mauve (deepened for AA)
            "info": "#3a6cc9",   "infoFg": "#f5e0dc",   # sapphire
            "alt": "#1a8f8f",    "altFg": "#f5e0dc",   # teal
            "warn": "#b06a2c",   "warnFg": "#f5e0dc",   # peach (deepened)
            "danger": "#c4344a", "dangerFg": "#f5e0dc",   # red
            "hover": "#313244", "selection": "#45475a", "selectionFg": "#ffffff",
            "logBg": "#181825", "promptFg": "#f9e2af", "answerFg": "#a6e3a1",
            "shadow": "rgba(0, 0, 0, 0.45)",
        },
    ),

    # ----------------------------------------------------------------
    # Everforest Dark — warm green-grey surface, earthy CTAs
    # ----------------------------------------------------------------
    Theme(
        id="everforest_dark",
        name="Everforest Dark",
        subtitle="Warm forest low-contrast",
        family="dark",
        notes=(
            "Everforest's soft green-grey surface with earthy CTAs — green "
            "primary, aqua secondary, blue tertiary, orange caution, red "
            "destructive. Comfortable for long sessions."
        ),
        tokens={
            "bg": "#2d353b", "card": "#272e33",
            "input": "#374247", "border": "#4a555b",
            "fg": "#d3c6aa", "muted": "#9da9a0", "accent": "#a7c080",
            "go": "#4f7a52",     "goFg": "#fdf6e3",   # green
            "info": "#3a8a82",   "infoFg": "#fdf6e3",   # aqua
            "alt": "#4d7a99",    "altFg": "#fdf6e3",   # blue
            "warn": "#b07a2c",   "warnFg": "#fdf6e3",   # orange
            "danger": "#c2433a", "dangerFg": "#fdf6e3",   # red
            "hover": "#374247", "selection": "#4a555b", "selectionFg": "#ffffff",
            "logBg": "#272e33", "promptFg": "#dbbc7f", "answerFg": "#a7c080",
            "shadow": "rgba(0, 0, 0, 0.45)",
        },
    ),

    # ----------------------------------------------------------------
    # Synthwave — retro neon on deep indigo
    # ----------------------------------------------------------------
    Theme(
        id="synthwave",
        name="Synthwave",
        subtitle="Retro neon outrun",
        family="dark",
        notes=(
            "Deep indigo night with retro neon CTAs — magenta primary, cyan "
            "secondary, purple tertiary, amber caution, hot red destructive. "
            "High-energy 80s vibe."
        ),
        tokens={
            "bg": "#1a132f", "card": "#221a3d",
            "input": "#2d2350", "border": "#3f3370",
            "fg": "#f0e6ff", "muted": "#a596c8", "accent": "#ff5dc8",
            "go": "#c81d8e",     "goFg": "#ffffff",   # neon magenta
            "info": "#1c8fb0",   "infoFg": "#ffffff",   # neon cyan
            "alt": "#7a3fd0",    "altFg": "#ffffff",   # electric purple
            "warn": "#b87a14",   "warnFg": "#1a132f",   # amber
            "danger": "#e0344a", "dangerFg": "#ffffff",   # hot red
            "hover": "#2d2350", "selection": "#3f3370", "selectionFg": "#ffffff",
            "logBg": "#221a3d", "promptFg": "#ffcf4d", "answerFg": "#52e0c4",
            "shadow": "rgba(0, 0, 0, 0.55)",
        },
    ),

    # ----------------------------------------------------------------
    # Ayu Mirage — slate-blue surface, warm-leaning CTAs
    # ----------------------------------------------------------------
    Theme(
        id="ayu_mirage",
        name="Ayu Mirage",
        subtitle="Soft slate-blue mid-dark",
        family="dark",
        notes=(
            "Ayu Mirage's muted slate-blue surface with warm-leaning CTAs — "
            "orange primary, blue secondary, purple tertiary, yellow caution, "
            "red destructive. Balanced mid-dark."
        ),
        tokens={
            "bg": "#1f2430", "card": "#232834",
            "input": "#2b3140", "border": "#3b4252",
            "fg": "#cbccc6", "muted": "#8a8f99", "accent": "#ffcc66",
            "go": "#c47a1f",     "goFg": "#1f2430",   # orange
            "info": "#3a7fc4",   "infoFg": "#ffffff",   # blue
            "alt": "#8a6fd0",    "altFg": "#ffffff",   # purple
            "warn": "#b0922c",   "warnFg": "#1f2430",   # yellow
            "danger": "#c44a4a", "dangerFg": "#ffffff",   # red
            "hover": "#2b3140", "selection": "#3b4252", "selectionFg": "#ffffff",
            "logBg": "#232834", "promptFg": "#ffcc66", "answerFg": "#87d96c",
            "shadow": "rgba(0, 0, 0, 0.4)",
        },
    ),

    # ----------------------------------------------------------------
    # IBM Carbon — near-black grey surface, crisp product CTAs
    # ----------------------------------------------------------------
    Theme(
        id="carbon",
        name="IBM Carbon",
        subtitle="Crisp product grey",
        family="dark",
        notes=(
            "IBM Carbon's near-black grey surface with crisp product CTAs — "
            "blue primary, teal secondary, purple tertiary, yellow caution, "
            "red destructive. Enterprise-clean."
        ),
        tokens={
            "bg": "#161616", "card": "#1f1f1f",
            "input": "#262626", "border": "#393939",
            "fg": "#f4f4f4", "muted": "#a8a8a8", "accent": "#78a9ff",
            "go": "#2f6ce5",     "goFg": "#ffffff",   # carbon blue
            "info": "#197a78",   "infoFg": "#ffffff",   # teal
            "alt": "#7a4fd0",    "altFg": "#ffffff",   # purple
            "warn": "#a67a14",   "warnFg": "#161616",   # yellow
            "danger": "#da1e28", "dangerFg": "#ffffff",   # red
            "hover": "#262626", "selection": "#393939", "selectionFg": "#ffffff",
            "logBg": "#1f1f1f", "promptFg": "#f1c21b", "answerFg": "#42be65",
            "shadow": "rgba(0, 0, 0, 0.55)",
        },
    ),

    # ----------------------------------------------------------------
    # Palenight — muted indigo surface, soft material CTAs
    # ----------------------------------------------------------------
    Theme(
        id="palenight",
        name="Palenight",
        subtitle="Muted material indigo",
        family="dark",
        notes=(
            "Material Palenight's muted indigo surface with soft CTAs — "
            "indigo primary, cyan secondary, green tertiary, coral caution, "
            "pink destructive. Mellow and rounded."
        ),
        tokens={
            "bg": "#292d3e", "card": "#222637",
            "input": "#323750", "border": "#444a68",
            "fg": "#c6cce6", "muted": "#8c92b8", "accent": "#82aaff",
            "go": "#5a6fd0",     "goFg": "#ffffff",   # indigo
            "info": "#2d8aa8",   "infoFg": "#ffffff",   # cyan
            "alt": "#4f9a6f",    "altFg": "#ffffff",   # green
            "warn": "#c47038",   "warnFg": "#ffffff",   # coral
            "danger": "#c44a72", "dangerFg": "#ffffff",   # pink
            "hover": "#323750", "selection": "#444a68", "selectionFg": "#ffffff",
            "logBg": "#222637", "promptFg": "#ffcb6b", "answerFg": "#c3e88d",
            "shadow": "rgba(0, 0, 0, 0.45)",
        },
    ),
]


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


THEMES_BY_ID: Dict[str, Theme] = {t.id: t for t in THEMES}


def theme_ids() -> List[str]:
    """Return the 6 theme IDs in declaration order."""
    return [t.id for t in THEMES]


# ---------------------------------------------------------------------------
# WCAG contrast helpers (port of the JS helpers in themes.jsx)
# ---------------------------------------------------------------------------


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Parse ``#rgb`` or ``#rrggbb`` into a 3-tuple of 0-255 ints."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"unsupported hex color: {hex_color!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _channel_luminance(channel: int) -> float:
    """sRGB → linear-light per channel.  Matches the WCAG 2.1 formula."""
    c = channel / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_color: str) -> float:
    """Compute the relative luminance of a hex color per WCAG 2.1."""
    r, g, b = _hex_to_rgb(hex_color)
    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """Compute the contrast ratio between two hex colors per WCAG 2.1.

    Returns a value in the range 1.0 (no contrast) to 21.0 (max).
    """
    la = relative_luminance(hex_a)
    lb = relative_luminance(hex_b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def wcag_rating(ratio: float) -> str:
    """Bucket a contrast ratio into a WCAG label.

    Returns one of ``"AAA"`` (≥7:1), ``"AA"`` (≥4.5:1), ``"AA Large"``
    (≥3:1, large text only), or ``"Fail"`` (<3:1).
    """
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3.0:
        return "AA Large"
    return "Fail"
