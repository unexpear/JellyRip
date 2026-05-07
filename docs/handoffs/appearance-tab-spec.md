# Spec — Appearance Tab (consolidated UI customization)

**For:** Future implementation pass against MAIN.
**Predecessor:** Phase 3d theme-picker pass (delivered 2026-05-03)
+ this session's UX-polish pass (2026-05-04 — tray, splash,
toolbar, byte progress, log severity, drive glyph, output tree).
**Successor:** Phase 3d settings-tabs port
(`docs/handoffs/phase-3d-port-settings-tabs.md`).

---

## Goal

Replace the current single-purpose **Themes** tab with a
consolidated **Appearance** tab that exposes every visual /
chrome customization knob in one place.  No more hunting for
toggles in different tabs or editing `config.json` by hand.

Behavioral settings (Smart Rip thresholds, retry counts, naming
mode, paths) stay where they belong — the existing brief
`phase-3d-port-settings-tabs.md` ports those into Everyday /
Advanced / Expert tabs.  This spec only covers **how the UI
looks**, not **what it does**.

## Design principles

1. **Live preview, not live apply.**  Every control instantly
   updates the running widget so the user can see the result —
   but **does NOT touch cfg**.  cfg is reserved for OK.  This is
   the corrected interpretation after 2026-05-04 review: the
   earlier "click-to-apply" framing leaked previews into the
   shared cfg dict, which other code might read mid-preview.
2. **OK commits, Cancel reverts.**  OK reads every widget's
   current state, writes it to cfg, persists to disk, accepts.
   Cancel walks the snapshot taken at construction and reverses
   every runtime change (calls each live-preview hook with the
   original value).  cfg is never touched on Cancel.  Esc = Cancel.
3. **No Apply button.**  `SettingsDialog` has only OK / Cancel
   as of 2026-05-04.  Apply was redundant once selection became
   instant preview — there's no "uncommitted but visible" state
   to commit.
4. **Snapshot-on-open.**  The dialog snapshots every cfg key it
   can mutate at `__init__` time.  Cancel walks the snapshot to
   know what runtime state to restore.  apply() reads widgets
   directly (the snapshot isn't needed for commit).
5. **Single mutation point.**  `apply()` is the only place that
   writes cfg.  Every preview-and-revert cycle leaves cfg
   identical to what it was when the dialog opened.
6. **Defaults match current behavior.**  Every new toggle defaults
   to ON (match what's already shipping).  Users who don't open
   Settings see no change.  Users who do can dial things back.
7. **One cfg key per knob.**  Don't introduce nested dicts or
   compound keys.  Existing `config.json` files keep working
   because we only add keys, never rename.

## Current state (what's there today)

- `gui_qt/settings/dialog.py` — modal `QDialog` with
  `QTabWidget`.  Buttons: Apply / Cancel / OK.
- `gui_qt/settings/tab_themes.py` — single tab.  `QListWidget`
  of 6 themes; click selects, **doesn't apply**.  Apply button
  applies; OK = apply + close; Cancel = revert.
- Existing brief at
  `docs/handoffs/phase-3d-port-settings-tabs.md` plans Everyday
  / Advanced / Expert tabs ported from tkinter — orthogonal to
  this spec.

## What this session added that needs UI exposure

All currently hardcoded "always-on", no cfg toggle:

| Feature                       | Code lives in              | Hardcoded? |
|-------------------------------|----------------------------|------------|
| System tray icon              | `gui_qt/tray_icon.py`      | yes        |
| Startup splash screen         | `gui_qt/splash.py`         | yes        |
| Log severity color (warn/err) | `gui_qt/log_pane.py`       | yes        |
| Log severity glyph (⚠/✗)      | `gui_qt/log_pane.py`       | yes        |
| Drive-state glyph (◉/⊚/◌)     | `gui_qt/formatters.py`     | yes        |
| Byte-format progress          | `gui_qt/status_bar.py`     | opt-in by API |

## Tab layout

Single tab named **Appearance** (replaces "Theme").  Vertical
sections separated by horizontal dividers, matching the wizard's
`_add_section_header` style:

```
┌─ Appearance ──────────────────────────────────────────┐
│                                                       │
│  THEME                                                │
│  ─────                                                │
│  ┌─────────────────────────────────────────┐          │
│  │ ● Dark GitHub — dark                    │          │
│  │ ○ Light Inverted — light                │          │
│  │ ○ Dracula Light — light                 │          │
│  │ ○ HC Dark — dark                        │          │
│  │ ○ Slate — dark                          │          │
│  │ ○ Frost — dark                          │          │
│  └─────────────────────────────────────────┘          │
│  Notes: <subtitle + description for selected>         │
│                                                       │
│  LOG PANE                                             │
│  ────────                                             │
│  [✓] Color-code warnings and errors                   │
│  [✓] Show severity glyph (⚠/✗) on warn/error lines    │
│  Buffer cap:  [300_000] lines  (trim to [200_000])    │
│                                                       │
│  DRIVE PICKER                                         │
│  ────────────                                         │
│  [✓] Show disc-state glyph (◉ inserted / ⊚ empty /    │
│      ◌ unavailable) before disc name                  │
│                                                       │
│  WINDOW                                               │
│  ──────                                               │
│  [✓] System-tray icon (recommended for long rips)     │
│  [✓] Startup splash screen                            │
│  [ ] Remember window size and position                │
│  Font scale:  ( ) 90%  (●) 100%  ( ) 110%  ( ) 125%   │
│                                                       │
└───────────────────────────────────────────────────────┘
        [ Cancel ]                          [ OK ]
```

Notes:

- Theme section keeps `QListWidget` of 6 themes + notes label
  exactly as today.  Click on row → live theme swap.
- "Buffer cap" + "trim to" are spinboxes — the only non-toggle
  controls in the LOG PANE section.  Validate `trim < cap`.
- Font scale is radio buttons applied via
  `QApplication.setFont(QFont(family, base * scale))`.  Live
  preview means the dialog itself resizes — make sure the layout
  is robust to that.
- Window-position remember is the only NEW feature this spec
  introduces (everything else exposes existing code).  See
  "Open design questions" for whether it's in scope.

## Per-control spec

> **All "Click behavior" rows below describe runtime preview only.**
> No control writes to cfg during preview — that's the design
> principle.  cfg is written exclusively by ``apply()`` at OK time,
> and reverted to the snapshot by ``cancel()`` (which only re-fires
> the runtime hook with the original value; cfg stays untouched
> throughout because preview never wrote to it).

### Theme

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg key         | `opt_pyside6_theme` (existing — no change)         |
| Default         | `"dark_github"`                                    |
| Type            | string                                             |
| Control         | `QListWidget` (existing)                           |
| Preview behavior| `currentItemChanged` → `load_theme(app, name)` runtime swap.  cfg untouched |
| OK behavior     | Read selected row's theme ID, write `opt_pyside6_theme` to cfg, persist to disk |
| Cancel behavior | If selection differs from snapshot: `load_theme(app, original_theme)`.  cfg never written, no revert needed |

### Color-code warnings/errors

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg key         | `opt_log_color_levels` (NEW)                       |
| Default         | `True`                                             |
| Type            | bool                                               |
| Control         | `QCheckBox`                                        |
| Click behavior  | Toggle `LogPane._level_coloring_enabled` flag      |
| OK behavior     | Persist                                            |
| Cancel behavior | Revert flag to original                            |
| Implementation note | Need to add an enable flag to `LogPane`; today it auto-classifies unconditionally |

### Severity glyph (⚠/✗)

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg key         | `opt_log_glyph_prefix` (NEW)                       |
| Default         | `True`                                             |
| Type            | bool                                               |
| Control         | `QCheckBox`                                        |
| Click behavior  | Toggle `LogPane._glyph_prefix_enabled`             |
| Implementation note | Currently the glyph is added unconditionally inside `append`.  Add a flag, gate the prepend |

### Buffer cap / trim

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg keys        | `opt_log_cap_lines` / `opt_log_trim_lines` (existing) |
| Defaults        | 300_000 / 200_000                                  |
| Type            | int                                                |
| Control         | Two `QSpinBox` widgets, side-by-side               |
| Click behavior  | Live: re-set the LogPane's `_cfg["opt_log_cap_lines"]` so the next `_trim_to_cap` uses the new cap |
| Validation      | trim < cap; cap >= 1000; trim >= 100               |
| Cancel behavior | Restore both keys to snapshotted originals         |

### Disc-state glyph

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg key         | `opt_drive_state_glyph` (NEW)                      |
| Default         | `True`                                             |
| Type            | bool                                               |
| Control         | `QCheckBox`                                        |
| Click behavior  | Refresh the drive picker (`drive_handler.refresh_async`); `format_drive_label` reads cfg and skips the glyph when disabled |
| Implementation note | `format_drive_label` currently doesn't see cfg.  Either pass cfg through, or have the drive_handler decide and pass `include_glyph: bool` |

### System-tray icon

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg key         | `opt_tray_icon_enabled` (NEW)                      |
| Default         | `True`                                             |
| Type            | bool                                               |
| Control         | `QCheckBox`                                        |
| Click behavior  | If toggling ON: construct + show `JellyRipTray`. If OFF: call `tray.hide()` and clear `window._tray` |
| Implementation note | `app.py` currently constructs the tray unconditionally.  Wrap the construction in an `if cfg.get("opt_tray_icon_enabled", True):` check; the runtime toggle in this dialog tears down + reconstructs |

### Startup splash

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg key         | `opt_show_splash` (NEW)                            |
| Default         | `True`                                             |
| Type            | bool                                               |
| Control         | `QCheckBox`                                        |
| Click behavior  | None at runtime — splash only matters at next launch.  Show a help-text hint: "Takes effect on next launch" |
| Implementation note | `main.py:_create_startup_window` reads cfg before creating the splash.  Need to load cfg earlier (currently splash is built BEFORE `load_startup_config`).  Either: (a) read directly from `%APPDATA%\JellyRip\config.json` before splash, (b) accept the trade-off that this is the one toggle that needs an app restart |

### Remember window position (NEW behavior)

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg keys        | `opt_remember_window_geom` (bool), `_window_geom_x`, `_window_geom_y`, `_window_geom_w`, `_window_geom_h` (NEW) |
| Default         | `False` for the toggle                             |
| Type            | bool / ints                                        |
| Control         | `QCheckBox`                                        |
| Behavior        | When ON: save `geometry()` on `closeEvent`, restore at `__init__` if saved values exist; when OFF: clear saved values |
| Implementation note | Use `saveGeometry()` / `restoreGeometry()` (returns QByteArray) — simpler than tracking individual ints.  Encode as base64 string in cfg.  Or store a single key `_window_geom_b64`; the underscore prefix is the convention for "internal, don't show in advanced cfg view" |
| Out of scope?   | Possibly — see "Open design questions" |

### Font scale (NEW behavior)

| Property        | Value                                              |
|-----------------|----------------------------------------------------|
| Cfg key         | `opt_font_scale_pct` (NEW)                         |
| Default         | `100`                                              |
| Type            | int (one of 90 / 100 / 110 / 125)                  |
| Control         | `QButtonGroup` of 4 `QRadioButton`s                |
| Click behavior  | `QApplication.setFont(QFont(family, base_size * scale / 100))` — applies to entire app |
| Cancel behavior | Restore to snapshotted original                    |
| Out of scope?   | Possibly — see "Open design questions" |

## Dialog-level changes

### Remove the Apply button

`dialog.py:_on_apply` and the QPushButton at lines 82-85 go
away.  Tabs that today implement an `apply()` method keep doing
so — `_on_ok` already calls `apply()` on every tab.

### Cancel must trigger live revert

`_on_cancel` already calls `cancel()` on every tab.  Each tab's
`cancel()` must restore the runtime state, not just the cfg.

### Visual hint about live preview

Subtitle text under the tab title: "Changes apply instantly; OK
saves them, Cancel reverts."

### Width

Current dialog is 560 wide.  The new tab fits in that width but
might want 600 for the radio rows + spinboxes to breathe.
Decide on visual review.

## Open design questions

1. **Is "remember window position" in scope?**  It's the one
   spec item that adds genuinely new behavior.  All others
   expose existing features.  Recommend: NO for v1, file as
   follow-up.

2. **Is "font scale" in scope?**  Genuinely new feature.
   Recommend: NO for v1; if users want larger fonts, OS-level
   accessibility settings work today.  Revisit if user feedback
   surfaces.

3. **One tab or multiple?**  This spec proposes one tab with
   sections.  Alternative: split into "Theme" + "Visual touches"
   + "Window" tabs.  Recommend: ONE tab — keeps appearance
   stuff together; multiple tabs are paper cuts when you're
   trying to see the full state of your UI.

4. **Where do the existing "Everyday / Advanced / Expert" tabs
   sit relative to Appearance?**  Probably:
   `[ Appearance ] [ Everyday ] [ Advanced ] [ Expert ]` —
   appearance first because it's the most-used.  Open to
   reorder.

5. **What about the `opt_show_temp_manager` / `opt_warn_low_space`
   keys that the existing brief assigned to Everyday?**  These
   *are* UI behaviors (they control whether dialogs show).
   Recommend: keep them in Everyday — they gate behavior, not
   appearance.  Appearance is "how it looks", Everyday is
   "what shows up".

## Phasing

### Phase A — Minimum viable (recommended first pass)

Just expose the 5 hardcoded toggles from this session:

- Color-code warnings/errors
- Severity glyph
- Disc-state glyph
- Tray icon
- Startup splash

5 new cfg keys.  Plumb through to the relevant runtime sites
(small refactors at LogPane, formatters, app.py, main.py).

Theme section stays exactly as-is (rename tab to Appearance,
fold themes into the new layout).  Apply button removed.
Click-to-apply on theme list.

**Estimated scope:** ~150 lines + 6-10 tests.

### Phase B — Add window persistence

Adds `opt_remember_window_geom` + the `saveGeometry` /
`restoreGeometry` integration in MainWindow.  ~30 lines
+ 2 tests.

### Phase C — Add font scale

Adds `opt_font_scale_pct` + the QFont application logic.
~30 lines + 2 tests.

### Phase D — Buffer cap UI

Spinboxes for `opt_log_cap_lines` / `opt_log_trim_lines`
with validation.  ~40 lines + 4 tests.

## Tests to write

| Test                                                                     | Pins                              |
|--------------------------------------------------------------------------|-----------------------------------|
| `test_appearance_tab_replaces_themes_tab`                                | Tab name is "Appearance"          |
| `test_no_apply_button_in_settings_dialog`                                | `findChild(QPushButton, "applyButton")` returns None |
| `test_clicking_a_theme_applies_it_live`                                  | Click → `load_theme` called       |
| `test_clicking_a_theme_does_not_persist_until_ok`                        | Click alone doesn't write cfg     |
| `test_cancel_reverts_to_original_theme`                                  | Pick A, then B, then Cancel → A   |
| `test_color_log_levels_checkbox_persists`                                | Toggle → cfg key flips            |
| `test_color_log_levels_unchecked_disables_classification`                | LogPane appends, no color applied |
| `test_severity_glyph_checkbox_persists`                                  | Toggle → cfg key flips            |
| `test_severity_glyph_unchecked_strips_glyph`                             | LogPane.append, no glyph in text  |
| `test_drive_state_glyph_checkbox_persists`                               | Toggle → cfg key flips            |
| `test_tray_icon_checkbox_toggles_runtime_tray`                           | Toggle OFF → tray.isVisible False |
| `test_splash_checkbox_shows_help_about_next_launch`                      | Help text rendered                |
| `test_ok_persists_every_appearance_change`                               | OK → save_cfg called with all keys|
| `test_cancel_reverts_every_appearance_change`                            | Cancel → originals restored       |

## Out of scope for this spec

- Wizard appearance (already styled by QSS — no per-control toggles needed)
- Color picker for custom theme tokens (we ship 6 themes; no custom-theme builder)
- High-contrast mode toggle (HC Dark theme already exists; users pick it)
- Animated transitions (no Qt animation framework wired today)
- Sound effects on rip complete (separate feature, not appearance)

## Definition of done (Phase A)

- [ ] `gui_qt/settings/tab_themes.py` renamed to
      `gui_qt/settings/tab_appearance.py`; class `ThemesTab`
      renamed to `AppearanceTab`
- [ ] `gui_qt/settings/dialog.py` Apply button removed; tab
      label updated
- [ ] `currentItemChanged` on theme list calls `load_theme`
      (live preview)
- [ ] 5 new cfg keys + 5 new `QCheckBox` controls
- [ ] LogPane / formatters / app.py / main.py read the new
      keys; defaults preserve current behavior
- [ ] Tests for click-to-apply theme, no-apply-button, each
      checkbox round-trip, cancel-reverts
- [ ] STATUS.md updated
- [ ] Smoke: open dialog, toggle each, OK / Cancel each work
      visually

## Migration / risk notes

- **Cfg backward compat:** All new keys default to `True` so
  users with old `config.json` files see no behavior change.
- **Tray-icon toggle is destructive at runtime:** turning it
  off destroys the `JellyRipTray` instance.  If a rip is
  in progress, this loses the in-progress tooltip; reconstructing
  doesn't recover it.  Acceptable for v1 — rare action.
- **Splash toggle has no runtime effect:** documented in the
  control's help text.  If we want it to take effect immediately,
  it'd require a separate "won't show again" path; not worth it.
- **Buffer cap change while logs are streaming:** the next
  `_trim_to_cap` call uses the new cap.  Existing log content
  stays.  Reasonable.
- **Font scale change cascades:** every widget re-lays out.
  Test the wizard and the disc-tree dialog at 110% / 125% before
  shipping — there might be clipping cases.

---

**Status as of 2026-05-04:** spec draft, awaiting user approval
for Phase A scope.  Code changes from this session that this
spec depends on are sitting unbuilt; rebuild + test pass is
prerequisite to starting Phase A work.
