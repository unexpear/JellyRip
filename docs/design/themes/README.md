# Theme design assets

User-delivered design materials for sub-phase 3a-themes (received 2026-05-03).

These are **source-of-truth design artifacts**, not active code. The QSS
files under `gui_qt/qss/` are the implementation; this directory is the
spec they implement against. When a token here disagrees with a token in
QSS, the file here wins until the spec changes — update the QSS, not
this directory.

## Files

| File | Role | What it's source-of-truth for |
|------|------|-------------------------------|
| `themes.jsx` | **Token tables** | The 6 themes' color tokens. Every QSS file in `gui_qt/qss/` must match the `tokens` object for its theme id. Also includes the WCAG `contrastRatio` / `wcagRating` helpers used to grade button color pairs. |
| `qt-mock.jsx` | **Layout reference** | The actual JellyRip layout — header, drive row, utility chips, primary buttons, secondary buttons, progress + status, stop session, log panel, input bar. Mirrors `gui/main_window.py`. The role-to-objectName mapping for Qt widgets is implicit here. |
| `styles.css` | **CSS recipe** | How the layout is skinned in CSS-land. Translates structurally to QSS. CSS-only bits (`color-mix`, `::before` overlays, `transition`, keyframe animations) need adaptation — most of those are polish, none are blocking. |
| `theme-preview.html` | Preview shell | Loads the JSX/CSS files into a browsable preview with theme switcher and contrast inspector. Open in a browser to see the themes side-by-side. Not a QSS deliverable. |
| `tweaks-panel.jsx` | Preview harness | Reusable React form-control library used by `theme-preview.html`. Not a QSS deliverable. |

`../symbol-library.md` (one level up) is the Unicode-glyph reference for
button labels and status indicators. Used by `gui_qt/` button text in
later sub-phases (3b/3c), not by QSS.

## The 6 themes

| id | Family | Subtitle | Notes |
|----|--------|----------|-------|
| `dark_github` | dark | Current tkinter palette, ported | Direct port of today's `#0d1117` / `#58a6ff` palette. Zero visual surprise for existing users. Default value of `opt_pyside6_theme`. |
| `light_inverted` | light | Closes A11y Finding #2 | Forest-green primary, deep teal secondary, mustard tertiary, rust caution, crimson destructive. No purple in the action row. |
| `dracula_light` | light | Dracula palette, light surface | Pale lavender bg, canonical Dracula CTAs (purple / pink / cyan / yellow / red). |
| `hc_dark` | dark | Accessibility-first AAA | Pure black surfaces, neon CTAs that all cross 7:1 against their label color. |
| `slate` | dark | Cool blue-grey neutrals | Desaturated cool-only CTAs (sea-foam / pale sky / periwinkle / bronze / brick). |
| `frost` | dark | Muted Nordic dark | Nord background with the saturation dialed up on every CTA. |

Original 3-theme placeholder set (`dark_github` / `light_inverted` /
`warm`) is superseded. The `warm` slot is gone; four new themes replace
it. `gui_qt/qss/warm.qss` placeholder should be deleted when 3a-themes
runs.

## Token shape

Every theme defines the same role keys, only the colors differ. So one
parameterized QSS template can render all six. Roles (from `themes.jsx`):

```
bg, card, input, border          surfaces
fg, muted, accent                text + brand accent
go / goFg                        primary CTA      (start, confirm, rip)
info / infoFg                    secondary CTA    (dump titles)
alt / altFg                      tertiary CTA     (organize)
warn / warnFg                    caution CTA      (prep for ffmpeg)
danger / dangerFg                destructive      (stop session)
hover, selection                 interaction state
logBg, promptFg, answerFg        log panel coloring
shadow                           drop shadow rgba
```

The `confirmButton` / `primaryButton` objectName split already in use in
`gui_qt/setup_wizard.py` maps to the `go` role here.

## Branch identity

These assets live in MAIN. When AI BRANCH ports later (Phase 4), it
reuses this same theme system — themes are about base palette, not
AI-feature styling. Don't add AI-specific tokens here.
