# Handoff Brief — Phase 3d: Port Settings + Theme Picker (MAIN)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3d in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3c (main window).
**Successor:** Phase 3e (MKV preview — the v1-blocking feature).

---

## ⚠️ READ FIRST

- `docs/migration-roadmap.md`
- `STATUS.md`
- The settings code currently lives **inside** `gui/main_window.py`
  (not a separate file). Search for "settings_window" / "expert
  profile" / "_pick_movie_mode" / "open_settings_*" methods.

## Goal

Port the settings UI to `gui_qt/settings/` as a `QDialog` with
`QTabWidget` for the tab structure (Everyday, Advanced, Expert
profiles, etc.). Plus the in-app **theme picker** that swaps QSS
files at runtime per migration plan decision #7.

## Branch identity guardrails

Same as prior phases. **No AI features in MAIN.**

## Target structure

```
gui_qt/settings/
  __init__.py
  dialog.py            # QDialog + QTabWidget shell
  tab_everyday.py      # everyday options
  tab_advanced.py      # PATH lookup, debug flags, etc.
  tab_expert.py        # transcode profiles editor
  tab_themes.py        # the new theme picker (decision #7)
```

## Concrete plan

1. Read the existing settings code in `gui/main_window.py`. The
   tabs and field layout already exist — the structure is there;
   just translate widget by widget.
2. Build `dialog.py` with the tab shell.
3. Port each tab's fields. Reuse existing cfg-key reads/writes —
   don't change the persistence shape.
4. **Theme picker tab** — new feature. Lists themes from
   `gui_qt.theme.list_themes()`. Selection writes
   `cfg["opt_pyside6_theme"]`. Apply button triggers
   `gui_qt.theme.load_theme(app, name)` for runtime swap, then
   persists cfg.
5. Tests: tab construction, field round-trip (cfg → form → cfg),
   theme picker swap behavior.

## Definition of done

- [ ] Settings dialog opens from the main window
- [ ] Every tkinter-side cfg field has a Qt equivalent
- [ ] Theme picker swaps QSS at runtime AND persists the choice
- [ ] Tests pass
- [ ] STATUS.md reflects 3d complete

## Critical: cfg shape is unchanged

Don't rename keys, restructure DEFAULTS, or change persistence
format. The settings UI shape changes; what it writes does not.
This way users with existing `config.json` don't lose their settings.
