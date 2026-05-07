# UX Copy and Accessibility Plan

**Status:** Proposed. Findings captured from a 2026-05-02 audit pass
across both branches. This document is the working list of what needs
attention in user-visible strings, contrast, keyboard behavior, and
screen-reader exposure on this branch. It does not authorize
implementation.

This is the MAIN-branch plan. AI-branch findings (Explain prompt,
provider dialog, AI text-action voice, etc.) live in the AI branch's
copy of this document.

## Motivation

The audit pass surfaced three categories of work:

1. **Accessibility issues with concrete fixes** — contrast, focus
   indicators, error-message recovery copy, keyboard parity. Most are
   small string or theme-constant changes.
2. **Accessibility issues that are framework-limited** — `tk.Canvas`
   based scrollable lists are opaque to screen readers, and tkinter
   on Windows exposes minimal MSAA / UI Automation. These are tracked
   here for completeness but their real fix sits inside the PySide6
   migration ([pyside6-migration-plan.md](pyside6-migration-plan.md)).
3. **Copy quality gaps** — voice inconsistency, ALL-CAPS labels read
   as code, jargon without inline gloss, and a real product-name
   inconsistency where three different names appear in user-visible
   strings.

The biggest single accessibility lever the project has is the PySide6
migration. The biggest single copy lever is establishing a one-page
voice rule + a glossary so future strings stop drifting.

## Scope

In scope:

- Setup wizard and rip-flow dialogs
  ([gui/setup_wizard.py](../gui/setup_wizard.py),
  [gui/session_setup_dialog.py](../gui/session_setup_dialog.py))
- Main window toolbar, tabs, settings, log surface, abort flow
  ([gui/main_window.py](../gui/main_window.py))
- Transcode profile descriptions
  ([transcode/profiles.py](../transcode/profiles.py),
  [transcode/profile_summary.py](../transcode/profile_summary.py))
- Update flow ([gui/update_ui.py](../gui/update_ui.py))
- Live-log strings emitted from controller and engine layers
  ([controller/legacy_compat.py](../controller/legacy_compat.py),
  [controller/session.py](../controller/session.py),
  [engine/](../engine/))
- Color contrast across the dark-GitHub theme palette

Out of scope (until decided separately):

- Localization / `gettext` extraction — the work below assumes a
  single-language product. If localization is ever a goal, every
  hardcoded string flagged here would need extraction first.
- Complete enumeration of every string in
  [gui/main_window.py](../gui/main_window.py) (~7,800 lines).
  The audit sampled systematically; full coverage is a separate
  multi-hour pass.

## Findings — Critical (🔴)

### 1. Product-name inconsistency in user-visible strings

> ✅ **Closed 2026-05-02**. `APP_DISPLAY_NAME = "JellyRip"` constant
> added to [shared/runtime.py](../shared/runtime.py); 13 hardcoded
> variants in `gui/main_window.py` and 2 in `main.py` substituted via
> f-string. Drift-guard parametric test in
> [tests/test_app_display_name.py](../tests/test_app_display_name.py)
> protects against the legacy variants returning. The big top-of-window
> header now renders natural-case "JellyRip" rather than the prior
> ALL-CAPS three-word legacy variant. Original finding body retained
> below for historical context.

MAIN does not have an `APP_DISPLAY_NAME` constant. The product name
is hardcoded in three different forms across user-visible dialogs:

| File:line | What user sees |
| --- | --- |
| [gui/setup_wizard.py:152](../gui/setup_wizard.py) | "JellyRip has scanned and classified the disc titles." |
| [gui/main_window.py:402](../gui/main_window.py) | "Jellyfin Raw Ripper opened with safe defaults..." |
| [gui/main_window.py:7562](../gui/main_window.py) | "Close Raw Jelly Ripper?" |

Three names. One product. The exit confirmation calls it "Raw Jelly
Ripper" — neither the README name nor the wizard name. WCAG 3.2.4
(Consistent Identification) is implicated; brand integrity is the
bigger concern. AI branch already has the constant
(`shared/runtime.py:33`); MAIN never received the cleanup.

**Fix:** Add `APP_DISPLAY_NAME = "JellyRip"` to
[shared/runtime.py](../shared/runtime.py), replace the hardcoded
strings with f-string substitution. ~10 minutes of work.

### 2. White-on-blue primary buttons fail contrast

> ✅ **Closed 2026-05-02** (minimal fix — full equipable theme system
> deferred to PySide6 migration per decision #7). New constant
> `_ACCENT_BUTTON_BG = "#1f6feb"` in
> [gui/setup_wizard.py](../gui/setup_wizard.py); the two Movie / TV
> Show buttons now use it instead of the failing `_ACCENT` (`#58a6ff`)
> for the white-text background. Measured contrast: **4.63:1** against
> white — passes WCAG 1.4.3 AA's 4.5:1 threshold (audit doc estimated
> ~4.6:1, matched). Drift-guard test in
> [tests/test_button_contrast.py](../tests/test_button_contrast.py)
> (9 tests): pins the constant value, computes the WCAG ratio
> programmatically, and asserts the prior failing pattern
> `bg=_ACCENT, fg="white"` cannot return to the source. The minimal
> tkinter fix only — the multi-theme equipable version (where users
> can switch between filled and inverted primary button styles)
> lands during the PySide6 migration with QSS, not as tkinter
> infrastructure. AI BRANCH had the same bug (different shape:
> palette key existed but buttons used the wrong key) — fixed
> symmetrically. Original finding body retained below.

Movie / TV Show buttons in setup wizard Step 1
([gui/setup_wizard.py:288-301](../gui/setup_wizard.py)) use
`bg=_ACCENT (#58a6ff), fg="white"` at 12pt bold. White on `#58a6ff`
measures **2.5:1**. WCAG 1.4.3 AA requires 4.5:1 for normal text and
3:1 for large text. This fails both.

The same pattern likely repeats wherever `_ACCENT` is used as a
button background in the codebase.

**Fix options:**
- Darken accent for button backgrounds (e.g., `#1f6feb` measures
  ~4.6:1 with white)
- Invert: white background, blue text
- Both work; the second matches GitHub's actual primary-button
  pattern better

### 3. Flat buttons have no visible focus indicator

> ✅ **Closed 2026-05-02** (minimal `option_add` global default
> approach). Four `self.option_add()` calls in
> `JellyRipperGUI.__init__` ([gui/main_window.py](../gui/main_window.py))
> install tkinter-wide defaults for the `Button` class:
> `*Button.highlightThickness=2`, `*Button.highlightBackground` (dark
> surface so the ring is invisible at rest), `*Button.highlightColor`
> (accent so the ring is clearly visible when focused),
> `*Button.takeFocus=1` (Tab navigation includes buttons). Buttons
> that explicitly set their own `highlight*` options keep them (no
> override). This is the smallest possible change with broadest
> coverage — catches every `tk.Button` that doesn't override. The
> full `tk.Button`-helper refactor + Qt-native focus treatment lands
> during the PySide6 migration. Drift-guard test in
> [tests/test_focus_indicators.py](../tests/test_focus_indicators.py)
> (5 tests) — pins each option_add call by source-text regex so a
> future refactor that removes them fails loudly. Same fix landed
> in AI BRANCH (using AI BRANCH's `_COLORS` palette for the colors).

`relief="flat"` is used on most buttons across the wizard, dialogs,
and toolbar. Tk's default focus border is removed by `flat`, and no
`highlightthickness` / `highlightcolor` is configured. Keyboard users
cannot see which button has focus. WCAG 2.4.7 violation.

**Fix:** Add `highlightthickness=2, highlightbackground=_BG2,
highlightcolor=_ACCENT, takefocus=True` to the standard button style.
Ideally a single helper that wraps `tk.Button` so the style is
applied uniformly.

### 4. ALL-CAPS classification labels read as code constants

> ✅ **Closed 2026-05-02**. New `_LABEL_DISPLAY` mapping +
> `_label_display(label)` helper in
> [gui/setup_wizard.py](../gui/setup_wizard.py); the two display
> sites (`text=f"  {ct.label}"` and `text=f"{ct.label}"`) now route
> through the helper, rendering as `Main` / `Duplicate` / `Extra` /
> `Unknown`. The `_LABEL_COLORS` keys stay uppercase per the audit's
> recommendation — only the display strings change. The
> "MAIN is pre-selected" subtitle in step 3 also softened to
> "Main is pre-selected." Same change landed in AI BRANCH.

`MAIN` / `DUPLICATE` / `EXTRA` / `UNKNOWN` are rendered directly as
user-facing labels in the wizard
([gui/setup_wizard.py:36-40, 212, 414](../gui/setup_wizard.py)).
ALL-CAPS conveys "this is an enum constant" rather than "this is a
category." WCAG 3.1.5 (Reading Level) is implicated since the labels
require translation in the user's head from code-style to
human-readable.

**Fix:** Title-case throughout. `Main` / `Duplicate` / `Extra` /
`Unknown`. The hex color map can stay keyed by upper-case; the
display string changes.

### 5. Framework-limited: tkinter screen-reader exposure

`tk.Canvas`-based scrollable lists in setup wizard
([gui/setup_wizard.py:191-247](../gui/setup_wizard.py)) are announced
as "Canvas" with no children. Rows and checkboxes are invisible to
Narrator and NVDA. WCAG 4.1.2 violation.

**Fix:** Framework-level. Qt's `QListView` / `QTreeView` exposes a
proper accessibility tree. Tracked in
[pyside6-migration-plan.md](pyside6-migration-plan.md). No
in-tkinter workaround that scales — individual `tk.Label`s in a
non-canvas frame would be announced, but the scrolling layouts here
require canvas.

## Findings — Major (🟡)

### 6. Step 3 title is jargon

[gui/setup_wizard.py:353](../gui/setup_wizard.py) — "Step 3: Content
Mapping." "Content Mapping" reads as a database term. Candidates:
*Pick Titles*, *Choose What to Rip*, *Select Titles*.

### 7. "ABORT SESSION" is harsh

> ✅ **Closed 2026-05-02**. All user-visible "ABORT" strings in
> [gui/main_window.py](../gui/main_window.py) softened to "Stop": the
> "ABORT SESSION" button label (4 occurrences) → "Stop Session";
> "Abort the current session first" dialog body → "Stop the current
> session first"; "ABORT REQUESTED BY USER" log line → "Stop
> requested by user"; "ABORTING..." button label → "Stopping...";
> "Aborting..." status line → "Stopping...". Existing tests in
> `test_imports.py` and `test_security_hardening.py` updated to pin
> the new strings. Same change landed in AI BRANCH.

[gui/main_window.py:1105, 1253, 7541, 7551, 7557](../gui/main_window.py)
and the related `"Abort the current session first"` message at line
6125. Modern convention: *Stop Session* / *Stopping…*. Same applies
to `"ABORT REQUESTED BY USER"` at line 7555 in the log surface.

### 8. Error messages identify failure but rarely recovery

> ✅ **Closed 2026-05-03**. New `friendly_error(base_message, exception)`
> helper in [ui/dialogs.py](../ui/dialogs.py) — maps caught exception
> types (PermissionError, FileNotFoundError, IsADirectoryError,
> NotADirectoryError, OSError + errno-specific cases for ENOSPC,
> ENOTEMPTY, EACCES, EBUSY, TimeoutError, ConnectionError, MemoryError,
> ValueError, fallback) to user-facing recovery text. The raw
> exception text is **NOT** included in the returned dialog body —
> raw detail belongs in the session log (where it already is, via
> `controller.log()`). 17 raw-dump call sites in
> [gui/main_window.py](../gui/main_window.py) converted to use the
> helper — load/save/set-default/create/duplicate/delete profile,
> create/prepare output folders, build queue, load transcode profiles,
> analyze MKV, open Settings, open/reveal path. Drift-guard test in
> [tests/test_friendly_error.py](../tests/test_friendly_error.py)
> (18 tests) — covers each known exception type's recovery text,
> ordering caveats (TimeoutError/ConnectionError must be checked
> before OSError since they're subclasses in Python 3.11+),
> multiline base messages with path info, and the critical
> sentinel-string assertion that raw exception text never leaks
> into the returned message. Same fix landed in AI BRANCH.

Pattern: `f"Could not save expert profile:\n{exc}"` raw-dumps the
exception into a dialog. WCAG 3.3.3 (Error Suggestion) wants a
recovery path. The AI branch's chat error helper is a working model
for this pattern — it maps quota / timeout / network errors to
actionable copy. The same shape applies cleanly to file-system,
configuration, and network errors here.

**Fix:** A `_friendly_error(message, exception)` helper that maps
common exception types (PermissionError, FileNotFoundError, OSError
errno codes, etc.) to recovery text, with raw exception detail
relegated to "Show details" or the log file rather than the dialog
body.

### 9. Config-key names leak into user dialogs

> ✅ **Closed 2026-05-02**. The dev-leak paragraph
> *"Set opt_update_signer_thumbprint in Settings to your release
> certificate thumbprint before using auto-update."* dropped from the
> Update Blocked dialog body in
> [gui/update_ui.py](../gui/update_ui.py). The user-friendly paragraph
> earlier in the same dialog ("To enable updates, open Settings →
> Advanced, and set the 'Update Signer Thumbprint' field...") covers
> what the dropped paragraph said in human-readable form. The
> developer-facing controller log line still includes the config key
> name (logs are appropriate places for config keys; user dialogs are
> not). Existing security-hardening test updated to drop the assertion
> on the user-visible config-key string. Same change landed in AI BRANCH.

[gui/update_ui.py:251-256](../gui/update_ui.py) — the Update Blocked
dialog body contains:

> "Set opt_update_signer_thumbprint in Settings to your release
> certificate thumbprint before using auto-update."

`opt_update_signer_thumbprint` is a developer-facing config key. A
user has no anchor for what `opt_*` means. The same dialog earlier
already explains the action in plain language ("open Settings →
Advanced, and set the 'Update Signer Thumbprint' field..."), so the
config-key paragraph is a redundant developer leak.

**Fix:** Drop the third paragraph; the human paragraph already
covers it.

### 10. EXTRA label color collides with muted body text

> ✅ **Closed 2026-05-03**. Changed `_LABEL_COLORS["EXTRA"]` from
> `#8b949e` (muted gray, same as `_FG_DIM`) to **`#a371f7`** (purple)
> in [gui/setup_wizard.py](../gui/setup_wizard.py). Distinct from the
> other label hues (blue/amber/orange), distinct from `_FG_DIM`, and
> measures ~5.65:1 contrast against the dark `#0d1117` background
> (passes WCAG 4.5:1). Same fix landed in AI BRANCH via
> `gui/theme.py:CLASSIFICATION_LABEL_COLORS["EXTRA"]`. Drift-guard
> tests in [tests/test_label_color_and_libredrive.py](../tests/test_label_color_and_libredrive.py)
> pin the new value, assert it differs from `_FG_DIM`, and confirm
> all four classification labels have distinct colors.

[gui/setup_wizard.py:38](../gui/setup_wizard.py) — `"EXTRA": "#8b949e"`
is the same hex as `_FG_DIM` (the muted body-text color). Visually,
the category label "EXTRA" reads as muted body text, not as a label
distinct from the description text next to it. Hierarchy collapses.
Not a strict WCAG violation, but real damage.

**Fix:** Pick a distinct hue for EXTRA that is not the muted body
color.

### 11. LibreDrive status assumes the term is known

> ✅ **Closed 2026-05-03**. All three LibreDrive status strings in
> [gui/setup_wizard.py](../gui/setup_wizard.py) now carry an inline
> gloss telling the user why the status matters:
> - *"LibreDrive: enabled — disc decryption ready"*
> - *"LibreDrive: possible — firmware patch may help"*
> - *"LibreDrive: not available — UHD discs may not work"*
>
> Same change landed in AI BRANCH. Drift-guard test in
> [tests/test_label_color_and_libredrive.py](../tests/test_label_color_and_libredrive.py)
> pins each gloss explicitly, plus catches any future bare
> "LibreDrive: \<state\>" string introduced without an em-dash gloss.

[gui/setup_wizard.py:170-183](../gui/setup_wizard.py) — three
statuses (`enabled` / `possible` / `unavailable`) for a term most
users encounter once. Even "enabled" doesn't tell them why they
should care.

**Fix:** Inline gloss. "LibreDrive: enabled — disc decryption ready"
/ "LibreDrive: possible — firmware patch may help" / "LibreDrive:
not available."

### 12. Tab order may not match visual reading order

[gui/setup_wizard.py:288-320](../gui/setup_wizard.py) — Cancel
button is created in a separate `btn_row` packed after the
Movie/TV/Standard buttons. Tab order follows widget creation, so
verify whether keyboard users land on Cancel before the primary
actions.

**Fix:** Verify by tabbing through the live wizard. If wrong, set
explicit `takefocus` order or rearrange creation.

### 13. Disc-swap timeout has no in-context extension

Settings → Advanced has a configurable disc-swap timeout, but a user
mid-prompt cannot extend it — the timeout fires regardless. WCAG
2.2.1 (Timing Adjustable) is implicated.

**Fix:** Add a "Wait longer" button to any timed prompt that gives
the user N more seconds before the auto-cancel fires.

### 14. Live-log emits dev-style strings to the user

[controller/legacy_compat.py](../controller/legacy_compat.py) and
related controller modules surface log lines such as:

- `"[Diagnostics][DEBUG] LibreDrive raw: \"{raw}\""`
- `"=" * 44` border separators around section headers (terminal-style)
- `"Auto-title fallback used: '{title}'"`
- `"Custom run-folder override selected — collecting paths."`
- `"Run override — {label}: {chosen}"`
- `"WARNING: {context} timed out; continuing."`

The log panel is a primary user-visible surface (the README
documents it). Dev-style log output undermines product polish.

**Fix:** Two-tier logging — keep developer/debug logs going to file
unconditionally, but route the live-log panel through a "user-style"
filter that either rewrites or suppresses lines tagged as
diagnostic. Easier near-term fix: review high-frequency lines and
rewrite the user-visible ones to read like product status.

## Findings — Minor (🟢)

### 15. Voice inconsistency across dialogs

- Wizard Step 1: passive third-person ("JellyRip has scanned…")
- Dump session: imperative second-person ("Choose how this dump
  session should run.")
- Step 5 subtitle: marketing-voice ("No guessing, no surprises.")

Each is fine in isolation; together they sound like multiple
products. A one-page voice rule would converge future copy.

### 16. Required-field asterisks rely on legend lookup

[gui/session_setup_dialog.py:209, 399](../gui/session_setup_dialog.py)
— "(* required)" + inline `*` markers. Modern convention: mark
optional fields explicitly, or label inline ("Title — required").

### 17. Auto-generated copy minor inconsistency

[gui/session_setup_dialog.py:682, 715](../gui/session_setup_dialog.py)
— "auto-generated timestamp name" / "auto-generated batch folder
name." Both fine; flagged only for consistency review.

### 18. Step numbering skips and reuses across files

The wizard advertises Steps 1, 3, 4, 5 in
[setup_wizard.py](../gui/setup_wizard.py); Step 2 is in
[session_setup_dialog.py](../gui/session_setup_dialog.py). Numbers
work across files but a user only sees them in flow — either commit
to numbers everywhere or drop them.

### 19. "No guessing, no surprises." oversells given pre-alpha status

[gui/setup_wizard.py:680](../gui/setup_wizard.py) — reassurance copy
that lands harder than the README's honesty about workflow maturity.
Tone down while pre-alpha.

### 20. Friendly transcode summary already exists, sitting unused

> ✅ **Closed 2026-05-02**. Wired via opt-in Settings toggle
> ("Show plain-English transcode profile descriptions") rather than
> always-on, so users keep the terse summary by default and don't get
> a UX shift forced on them. New `opt_plain_english_profile_summary`
> defaults to `False` in DEFAULTS; `ui/settings.py:summarize_profile`
> takes a `plain_english=` kwarg and dispatches to
> `profile_summary_readable` with safe fallback to `describe_profile`
> on shape mismatch. Both call sites in `gui/main_window.py` read the
> flag from cfg. Test coverage:
> [tests/test_settings_summarize_profile.py](../tests/test_settings_summarize_profile.py)
> (11 tests). Same fix landed in AI branch. Original finding body
> retained below.

[transcode/profile_summary.py](../transcode/profile_summary.py)
already produces plain-English profile descriptions ("Convert video
to H.265 (smaller files, good quality), balanced quality (CRF 22),
hardware acceleration if available"). Per [TASKS.md](../TASKS.md)
it's a half-built feature never wired into the GUI. The expert-mode
summary in [transcode/profiles.py:242](../transcode/profiles.py)
(`describe_profile`) is codec-jargon-dense.

**Fix:** Wire `profile_summary_readable` to the non-Expert summary
path. This is the cheapest copy win in the repo because the words
already exist.

### 21. `ui_visual_assets_copy/` directories may drift from live UI

[ui_visual_assets_copy/](../ui_visual_assets_copy/) contains older
copies of `gui/main_window.py`, `gui/setup_wizard.py`,
`ui/settings.py`, etc. Some user-visible strings exist in both the
live source and these copies. If they are being maintained in both,
they will drift over time. AI branch's copy of this plan flags the
same risk for AI prompts that exist in two places.

**Fix:** Confirm whether `ui_visual_assets_copy/` is still
load-bearing. If yes, document its role and link it from the live
file. If no, archive it (move outside the source tree) so it stops
attracting edits.

## Color Contrast — Computed Ratios

Computed from the actual hex constants in
[gui/setup_wizard.py:26-40](../gui/setup_wizard.py).

| Element | FG | BG | Ratio | Required | Pass |
| --- | --- | --- | --- | --- | --- |
| Body text | `#c9d1d9` | `#0d1117` | 12.3:1 | 4.5 | ✅ |
| Body text | `#c9d1d9` | `#161b22` | 11.7:1 | 4.5 | ✅ |
| Dim text | `#8b949e` | `#0d1117` | 6.3:1 | 4.5 | ✅ |
| Dim text | `#8b949e` | `#161b22` | 6.0:1 | 4.5 | ✅ |
| Accent header | `#58a6ff` | `#161b22` | 7.3:1 | 4.5 | ✅ |
| LibreDrive enabled | `#3fb950` | `#161b22` | 7.2:1 | 4.5 | ✅ |
| LibreDrive possible | `#d29922` | `#161b22` | 7.2:1 | 4.5 | ✅ |
| LibreDrive unavailable | `#f85149` | `#161b22` | 5.6:1 | 4.5 | ✅ |
| `MAIN` label | `#58a6ff` | `#0d1117` | 7.5:1 | 4.5 | ✅ |
| `DUPLICATE` label | `#d29922` | `#0d1117` | 7.6:1 | 4.5 | ✅ |
| `EXTRA` label | `#8b949e` | `#0d1117` | 6.3:1 | 4.5 | ✅ (but see #10) |
| `UNKNOWN` label | `#f0883e` | `#0d1117` | 7.6:1 | 4.5 | ✅ |
| Green primary button | `#FFFFFF` | `#238636` | 4.65:1 | 4.5 | ✅ (just) |
| **Blue primary button** | `#FFFFFF` | `#58a6ff` | **2.5:1** | 4.5 | ❌ |

## Foundation Documents to Consider

These prevent the next 100 strings from drifting further. Both are
proposed-not-required; they sit alongside this plan.

### ~~`docs/copy-style.md` (proposed)~~ ✅ landed 2026-05-03 — see [copy-style.md](copy-style.md)

A one-page rule sheet. Suggested content:

- Default to second person, present tense
- Sentence case for buttons and labels (no ALL-CAPS except literal
  acronyms like UHD, HEVC, SHA256)
- No marketing reassurance ("no guessing, no surprises")
- No jargon without inline gloss
- No config-key names in user dialogs
- One product name (`APP_DISPLAY_NAME`), substituted via constant
- Errors say what happened *and* what to try next
- Prefer "Stop" over "Abort"; "Pick" over "Map"; "Choose" over
  "Select" when action is causal

### ~~`docs/glossary.md` (proposed)~~ ✅ landed 2026-05-03 — see [glossary.md](glossary.md)

A canonical short-definition list for the terms users will encounter
without prior background. Suggested first entries:

- LibreDrive — MakeMKV's mode that lets the app read encrypted discs
  directly when the optical drive supports it. Without it, some
  discs cannot be ripped.
- UHD — Ultra-HD Blu-ray (4K resolution discs).
- HEVC / H.265 — A modern video codec; produces smaller files than
  H.264 at similar quality.
- CRF — Constant Rate Factor; a quality target for transcoding.
  Lower numbers mean higher quality and bigger files.
- AAC — A common audio format used in MKV files.
- Main track — The audio track most likely to be the primary one
  (e.g., the original-language stereo mix).
- Burn (subtitles) — Permanently render subtitles into the video,
  rather than as a selectable track.
- Metadata: preserve / drop — Whether existing tags are kept or
  stripped during transcode.
- Main / Duplicate / Extra / Unknown — JellyRip's classifier labels
  for disc titles.

A glossary serves two audiences on this branch: the GUI (link from
on-hover) and the [profile_summary.py](../transcode/profile_summary.py)
friendly descriptions. AI branch gets a third use (anchoring the AI
Explain prompt), tracked separately in the AI branch's plan.

## Sequencing

Quick wins that do not depend on the PySide6 migration (the order
roughly maps to value-per-effort):

1. ~~App-name constant (#1) — bug-grade fix~~ ✅ closed 2026-05-02
2. ~~Wire up [profile_summary.py](../transcode/profile_summary.py) (#20)~~ ✅ closed 2026-05-02 (opt-in Settings toggle)
3. ~~Title-case classification labels (#4)~~ ✅ closed 2026-05-02
4. ~~Darken accent for button backgrounds (#2)~~ ✅ closed 2026-05-02 (minimal fix; theme-system version deferred to migration)
5. ~~Add focus indicators to flat buttons (#3)~~ ✅ closed 2026-05-02 (minimal `option_add` global default; full helper refactor deferred to PySide6 migration)
6. ~~Soften "ABORT" → "Stop" across button + dialog body + log (#7)~~ ✅ closed 2026-05-02
7. ~~Drop config-key paragraph from Update Blocked dialog (#9)~~ ✅ closed 2026-05-02
8. ~~EXTRA label color (#10)~~ ✅ closed 2026-05-03
9. ~~LibreDrive inline gloss (#11)~~ ✅ closed 2026-05-03
10. ~~Friendly-error helper for messagebox dialogs (#8)~~ ✅ closed 2026-05-03

Items that wait for PySide6 *(per
[pyside6-migration-plan.md](pyside6-migration-plan.md), the migration
is now Approved direction — these items have a definite future home,
not indefinite Someday)*:

- Screen-reader exposure of canvas-based lists (#5)
- MSAA / UI Automation in general
- Proper label-for-input association
- Live regions for log streaming
- **Equipable theme system** *(deliberately deferred to migration —
  decision #7 captured in the migration plan; QSS is naturally suited
  to multi-theme architecture; tkinter equivalent would have been
  throwaway infrastructure)*
- Finding #2 (white-on-blue button contrast) full closure *(the
  `bg=#1f6feb` minimal contrast fix may land in tkinter as a quick
  win before migration; the multi-theme equipable version lands
  during migration)*

Items that need a separate decision:

- Voice rule in `docs/copy-style.md`
- Glossary in `docs/glossary.md`
- Two-tier log filter (user-style vs developer) (#14)
- Disc-swap timeout extension UX (#13)

## Open Questions

1. Is `docs/copy-style.md` worth committing to before the PySide6
   migration, or do we let the migration force a rewrite?
2. Should the glossary live as `docs/glossary.md`, or as inline
   tooltip strings? Both have trade-offs (single source vs.
   contextual proximity).
3. Two-tier log filtering — is this worth doing now, or does the
   migration's better log widget make it moot?
4. Verifying tab order across all dialogs is a hands-on task — who
   runs it and against which Windows + Narrator combination.
5. If the glossary lands, should AI branch's plan reference it
   directly from the rewritten Explain prompt?

## Not a Commitment

This document is a tracked plan, not an authorization. Workflow
stabilization, the test-coverage push, and shipping v1 take
precedence. Items above can be addressed incrementally — most are
isolated string changes — without blocking on each other or on the
larger PySide6 migration.

## Related

- [pyside6-migration-plan.md](pyside6-migration-plan.md) — The
  framework-limited findings (#5, parts of #13) are tracked there.
- [TASKS.md](../TASKS.md) — Someday entry pointing here.
- AI branch's copy of this document — covers AI-only findings
  (Explain prompt, provider dialog, AI text-action voice, main
  assistant prompt verbosity).
