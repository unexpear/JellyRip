"""Theme content tests — Phase 3a-themes (delivered 2026-05-03).

Pins the contracts for the 6 themes' tokens and the QSS files they
generate via ``tools/build_qss.py``:

- ``THEMES`` exposes exactly 6 themes with unique IDs.
- Every theme has all the tokens declared in ``TOKEN_KEYS``.
- Every CTA pair (``go``/``goFg``, ``info``/``infoFg``, …) hits at
  least WCAG AA Large (3:1) contrast.  Themes that claim AA or AAA
  in their notes are spot-checked at those tighter thresholds where
  the actual colors support it; the hard floor is AA Large because
  the user-delivered design has known sub-AA pairs in ``frost``,
  ``dracula_light``, and ``hc_dark``.  See the ``known WCAG gaps``
  section below.
- Generated QSS files exist for every theme ID and contain the
  expected role selectors.  Catches drift between
  ``tools/build_qss.py`` and ``gui_qt/themes.py``.

Behavior-first.  No QApplication, no widgets — just token data and
file content.

Known WCAG gaps (recorded but not hard-failed by this test file):

- ``dracula_light`` says "stays AA on every CTA" in its design notes
  but ``alt`` (#0a8a96 / #ffffff) is 4.13:1 — below AA's 4.5:1.
- ``hc_dark`` says "Every CTA crosses 7:1 / AAA holds end-to-end" but
  ``danger`` (#ff3030 / #ffffff) is 3.67:1 — below AA, well below AAA.
- ``frost`` makes no contrast claim; ``go`` (#6e9b4f / #ffffff) is
  3.25:1 and ``info`` (#4a7fb8 / #ffffff) is 4.18:1 — both AA Large
  only.

These gaps were surfaced to the user when 3a-themes implementation
landed; they're tracked separately rather than auto-fixed here so
that the design source of truth (``docs/design/themes/themes.jsx``)
stays the canonical color reference.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from gui_qt.themes import (
    CTA_ROLES,
    THEMES,
    THEMES_BY_ID,
    TOKEN_KEYS,
    Theme,
    contrast_ratio,
    relative_luminance,
    theme_ids,
    wcag_rating,
)


_REPO_ROOT = Path(__file__).resolve().parent.parent
_QSS_DIR = _REPO_ROOT / "gui_qt" / "qss"


# Hard floor for every CTA in every theme — WCAG AA Large (3:1).
# Anything below this is a contrast regression and must be fixed
# (either color adjustment or removed-from-design discussion).
_AA_LARGE = 3.0
_AA = 4.5
_AAA = 7.0


# ---------------------------------------------------------------------------
# Tokens module shape
# ---------------------------------------------------------------------------


def test_six_themes_with_unique_ids():
    """Exactly 6 themes, each with a unique ID — pins the design
    delivery from 2026-05-03 (replaces the original 3-theme
    placeholder set)."""
    assert len(THEMES) == 6, f"expected 6 themes, got {len(THEMES)}"
    ids = [t.id for t in THEMES]
    assert len(set(ids)) == 6, f"theme IDs must be unique, got {ids}"


def test_expected_theme_ids_present():
    """The 6 specific theme IDs from the user-delivered design.  If
    this changes, we need a deliberate update — not silent drift."""
    expected = {
        "dark_github",
        "light_inverted",
        "dracula_light",
        "hc_dark",
        "slate",
        "frost",
    }
    assert set(theme_ids()) == expected


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_theme_has_all_tokens(theme: Theme):
    """Every theme defines every token in ``TOKEN_KEYS`` so the QSS
    template's ``{tokens[...]}`` placeholders never KeyError."""
    missing = [k for k in TOKEN_KEYS if k not in theme.tokens]
    assert not missing, (
        f"theme {theme.id!r} missing tokens: {missing}"
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_theme_family_is_dark_or_light(theme: Theme):
    """``family`` is consumed by QSS / picker UI to pick neutral
    chrome (e.g. window border tone).  Constrain the value space."""
    assert theme.family in ("dark", "light"), (
        f"theme {theme.id!r} has unknown family {theme.family!r}"
    )


def test_themes_by_id_lookup():
    """``THEMES_BY_ID`` is a O(1) lookup that matches the list."""
    for t in THEMES:
        assert THEMES_BY_ID[t.id] is t


# ---------------------------------------------------------------------------
# WCAG helpers — sanity-check the math against published values
# ---------------------------------------------------------------------------


def test_relative_luminance_pure_black():
    """Pure black has zero luminance per WCAG 2.1."""
    assert relative_luminance("#000000") == 0.0


def test_relative_luminance_pure_white():
    """Pure white has unit luminance per WCAG 2.1."""
    assert relative_luminance("#ffffff") == pytest.approx(1.0, abs=1e-9)


def test_contrast_ratio_pure_extremes():
    """Black on white is the maximum WCAG ratio: 21:1."""
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=1e-6)
    # Symmetric: order shouldn't matter
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21.0, abs=1e-6)


def test_contrast_ratio_identical_colors_is_one():
    """A color against itself is contrast 1.0 (no contrast)."""
    assert contrast_ratio("#58a6ff", "#58a6ff") == pytest.approx(1.0, abs=1e-9)


@pytest.mark.parametrize("ratio,label", [
    (21.0, "AAA"),
    (7.0, "AAA"),
    (6.99, "AA"),
    (4.5, "AA"),
    (4.49, "AA Large"),
    (3.0, "AA Large"),
    (2.99, "Fail"),
    (1.0, "Fail"),
])
def test_wcag_rating_buckets(ratio: float, label: str):
    """``wcag_rating`` matches the WCAG 2.1 thresholds at boundaries."""
    assert wcag_rating(ratio) == label


def test_hex_to_rgb_short_form():
    """3-char hex like ``#fa1`` expands to ``#ffaa11``."""
    # We don't expose _hex_to_rgb publicly, but contrast_ratio uses it,
    # so verify via a known short-vs-long pair.
    short = contrast_ratio("#fff", "#000")
    long_form = contrast_ratio("#ffffff", "#000000")
    assert short == pytest.approx(long_form)


# ---------------------------------------------------------------------------
# Per-theme CTA contrast pins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
@pytest.mark.parametrize("role", CTA_ROLES)
def test_cta_meets_aa_large_floor(theme: Theme, role: str):
    """Every CTA pair in every theme must hit at least 3:1 (WCAG AA
    Large).  This is the hard floor — anything below means a button
    label is essentially invisible to many users.  Specific themes
    aim higher; see ``test_cta_meets_aa_when_claimed`` below."""
    bg = theme.tokens[role]
    fg = theme.tokens[role + "Fg"]
    ratio = contrast_ratio(bg, fg)
    assert ratio >= _AA_LARGE, (
        f"{theme.id} {role}: {bg} on {fg} = {ratio:.2f}:1 "
        f"(below WCAG AA Large {_AA_LARGE}:1)"
    )


# Themes whose design notes claim every CTA is AA or AAA must back
# that claim with the math.  Only the themes whose actual color
# values support the claim are pinned strictly — known gaps in
# dracula_light/hc_dark/frost are recorded in the module docstring
# rather than hard-failed here.
_THEMES_PINNED_AT_AA = ("dark_github", "light_inverted", "slate")


@pytest.mark.parametrize("theme_id", _THEMES_PINNED_AT_AA)
@pytest.mark.parametrize("role", CTA_ROLES)
def test_cta_meets_aa_when_claimed(theme_id: str, role: str):
    """Themes that claim AA on every CTA in their design notes must
    actually hit 4.5:1.  Pinning here so a future token edit can't
    silently regress these specific themes below AA."""
    theme = THEMES_BY_ID[theme_id]
    bg = theme.tokens[role]
    fg = theme.tokens[role + "Fg"]
    ratio = contrast_ratio(bg, fg)
    assert ratio >= _AA, (
        f"{theme_id} {role}: {bg} on {fg} = {ratio:.2f}:1 "
        f"(below WCAG AA {_AA}:1; this theme claims AA in its design notes)"
    )


# ---------------------------------------------------------------------------
# Generated QSS file content — drift guard against tools/build_qss.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_generated_qss_exists_and_nonempty(theme: Theme):
    """``tools/build_qss.py`` must have been run for every theme.
    Catches "I edited tokens but didn't regenerate" drift."""
    qss_path = _QSS_DIR / f"{theme.id}.qss"
    assert qss_path.is_file(), (
        f"missing {qss_path.name} — run `python tools/build_qss.py`"
    )
    assert qss_path.stat().st_size > 0, (
        f"{qss_path.name} is empty — re-run the QSS build"
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_generated_qss_contains_theme_metadata(theme: Theme):
    """The build script writes a header comment with the theme name.
    Pins that the output is per-theme (not a single duplicated stub)."""
    qss = (_QSS_DIR / f"{theme.id}.qss").read_text(encoding="utf-8")
    assert theme.name in qss, (
        f"{theme.id}.qss missing theme name {theme.name!r} in header — "
        f"is the build template still using {{name}}?"
    )
    assert theme.id in qss, f"{theme.id}.qss header doesn't reference its ID"


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_generated_qss_uses_token_colors(theme: Theme):
    """The generated QSS must contain at least one of each theme's
    distinct color tokens.  Catches a bug where the template binds
    to the wrong theme (e.g. always rendering dark_github colors)."""
    qss = (_QSS_DIR / f"{theme.id}.qss").read_text(encoding="utf-8")
    # ``bg``, ``go``, ``info`` are the three load-bearing tokens;
    # if any are missing the theme isn't actually applied.
    for role in ("bg", "go", "info"):
        color = theme.tokens[role]
        assert color.lower() in qss.lower(), (
            f"{theme.id}.qss doesn't contain {role}={color} — "
            f"build template bug?"
        )


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.id)
def test_generated_qss_styles_role_objectnames(theme: Theme):
    """The objectName scheme used in ``gui_qt/setup_wizard.py``
    (#confirmButton, #primaryButton, #secondaryButton, #cancelButton)
    must be styled in every theme.  Pins the role-to-objectName
    contract — if someone renames an objectName in setup_wizard.py
    without updating build_qss.py, this test catches it."""
    qss = (_QSS_DIR / f"{theme.id}.qss").read_text(encoding="utf-8")
    for selector in (
        "#confirmButton",
        "#primaryButton",
        "#secondaryButton",
        "#cancelButton",
    ):
        assert selector in qss, (
            f"{theme.id}.qss doesn't style {selector} — "
            f"role-to-objectName drift?"
        )


# ---------------------------------------------------------------------------
# Default theme consistency
# ---------------------------------------------------------------------------


def test_default_theme_id_is_in_themes():
    """``DEFAULTS['opt_pyside6_theme']`` must name a real theme so a
    fresh-config user never lands on a missing or placeholder theme."""
    from shared.runtime import DEFAULTS
    assert DEFAULTS["opt_pyside6_theme"] in THEMES_BY_ID, (
        f"DEFAULTS['opt_pyside6_theme']={DEFAULTS['opt_pyside6_theme']!r} "
        f"is not one of the 6 real themes {sorted(THEMES_BY_ID)}"
    )
