# Handoff Brief — Phase 3d: Port Settings Tabs (everyday / advanced / expert)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3d follow-up.
**Predecessor:** Phase 3d theme-picker pass (delivered 2026-05-03).
**Successor:** Phase 3e (MKV preview).

---

## ⚠️ READ FIRST

- `STATUS.md`
- `docs/handoffs/phase-3d-port-settings.md` — original 3d brief
- `gui_qt/settings/dialog.py` — already has the QTabWidget shell
  with the Themes tab.  This brief is about adding the remaining
  tabs to the existing dialog.

## Goal

Port the everyday / advanced / expert tabs of the tkinter
settings dialog to `gui_qt/settings/`.

## Branch identity guardrails

Same as prior phases.  **No AI features in MAIN.**

## Source of truth

The tkinter settings dialog lives **inline** in
`gui/main_window.py:6157` as `open_settings()` — 1296 lines.  Each
tab is built up via `ttk.Notebook.add()` calls within that method.
Read carefully and split per-tab as you port.

## Concrete plan

Suggested 3-session split (one tab per session):

### Session 1 — Everyday tab

Cfg keys (read directly from `open_settings`):

* `opt_smart_rip_mode`, `opt_smart_min_minutes`
* `opt_naming_mode` ("timestamp" / "title")
* `opt_show_temp_manager`
* `opt_warn_low_space`
* `tv_folder`, `movies_folder` (path pickers)
* `opt_log_cap_lines`, `opt_log_trim_lines` (deserve their own
  validation)

New module: `gui_qt/settings/tab_everyday.py`.  `EverydayTab(QWidget)`
with `apply()` that round-trips cfg.

### Session 2 — Advanced tab

Cfg keys:

* `makemkvcon_path`, `ffmpeg_path`, `ffprobe_path`,
  `handbrake_path` (path pickers + auto-detect buttons)
* `opt_allow_path_tool_resolution`
* `opt_debug_safe_int`, `opt_debug_duration`
* `opt_drive_index` (read-only display — drive picker is in main)
* `opt_extras_concurrent`, `opt_organize_concurrent`

New module: `gui_qt/settings/tab_advanced.py`.

### Session 3 — Expert profiles tab

This is the most complex.  Manages transcode profiles —
add / edit / delete / duplicate.  Calls into
`transcode.profiles.ProfileLoader` (already tkinter-free).

Cfg keys:

* `opt_expert_mode` (gates the whole tab)
* Profile JSON lives in `transcode_profiles.json`, not directly in
  cfg.

New module: `gui_qt/settings/tab_expert.py`.  Likely needs
sub-dialogs for profile editing (separate `gui_qt/settings/
profile_editor.py`).

## Each tab needs

* `apply()` method on the tab class that:
  - Reads form values
  - Validates them (raise / show error if invalid)
  - Writes back to cfg
  - The dialog calls `apply()` on each tab when user presses OK
* `cancel()` method (optional) for tabs that preview changes live
* Form fields with `QFormLayout` (already used in TV/Movie setup
  for reference shape)
* objectNames on every styled widget for QSS theming

## Definition of done

For each tab session:

- [ ] New tab module added to `gui_qt/settings/`
- [ ] Tab added to `SettingsDialog._tabs` in `dialog.py`
- [ ] All cfg keys round-trip (read-into-form, write-from-form)
- [ ] Validation errors surface inline (per the
      `gui_qt/dialogs/session_setup.py` pattern)
- [ ] Tests under `tests/test_pyside6_settings_<tab>.py`
- [ ] STATUS.md updated

## Critical: cfg shape is unchanged

Don't rename keys, restructure DEFAULTS, or change persistence
format.  Existing user `config.json` files must keep working.

## After all 3 tabs land

Phase 3d is **complete**, and 3e (MKV preview, v1-blocking) starts.
