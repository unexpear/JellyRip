# Release Process

This doc describes how to build and ship a JellyRip release.

The PySide6 migration (Phase 3) introduced new bundle requirements:
QSS theme files, the `gui_qt` package, PySide6 modules, and
QtMultimedia for the MKV preview feature.  Phase 3f extended
`JellyRip.spec` to handle them.  This doc captures the manual
smoke-test steps that follow a build.

---

## Build (developer machine)

```bat
build.bat
```

This invokes PyInstaller with `JellyRip.spec` and stages the
FFmpeg bundle.  Output lands in `dist\main\`.

**Expected new bundle assets** (after Phase 3f):

* `gui_qt/qss/*.qss` — 6 generated theme files (plus the
  deprecated 0-byte `warm.qss` placeholder; filtered out at
  runtime by `gui_qt.theme._is_real_theme_file`)
* PySide6 platform plugins (`platforms/qwindows.dll`, etc.) —
  PyInstaller's PySide6 hook auto-collects these
* QtMultimedia codecs — auto-collected; size impact ~80-150 MB
  per the migration plan estimate

If any of those are missing, the spec's
`GUI_QT_HIDDEN_IMPORTS` / `PYSIDE6_HIDDEN_IMPORTS` /
`GUI_QT_DATAS` lists need adjustment — see
`tests/test_pyinstaller_spec.py` for the pinned list.

---

## Smoke test (clean machine or VM)

Run the freshly-built `JellyRip.exe` on a clean Windows install
(or VM) — not your dev machine, where the dev venv could mask
missing-bundle issues.

### Tkinter path (default)

The default cfg keeps `opt_use_pyside6: false` — verify nothing
about the migration broke the tkinter path.

- [ ] Launch — main window appears
- [ ] Drive list populates
- [ ] Click any rip mode — workflow proceeds
- [ ] Settings opens, all tabs render
- [ ] Close cleanly

### PySide6 path

Edit `%APPDATA%\JellyRip\config.json` to set:

```json
{
  "opt_use_pyside6": true,
  "opt_pyside6_theme": "dark_github"
}
```

Relaunch.

- [ ] Window appears (Qt frame, dark_github theme)
- [ ] Drive combo populates after the initial scan
- [ ] No "Qt platform plugin missing" errors in stderr
- [ ] Status bar visible
- [ ] Log pane visible
- [ ] All workflow buttons (`Rip TV / Movie / Dump / Organize / Prep`) appear styled
- [ ] Utility chips (Settings / Updates / Copy Log / Browse Folder)
- [ ] Stop Session button (red, disabled initially)

### Theme picker (Phase 3d)

- [ ] Click ⚙ Settings — settings dialog opens
- [ ] Theme tab is the only tab so far (everyday / advanced /
      expert tabs pending)
- [ ] All 6 themes listed (`dark_github`, `light_inverted`,
      `dracula_light`, `hc_dark`, `slate`, `frost`)
- [ ] Selecting a theme + clicking Apply → window restyles live
- [ ] Cancel after Apply → theme reverts
- [ ] OK persists choice; relaunch shows the picked theme

### MKV preview (Phase 3e — v1-blocking)

This is the headline feature.  Without it, the migration shouldn't
ship as v1.

- [ ] Launch a Smart Rip workflow that opens the disc-tree
      selector
- [ ] Right-click on any title row → preview clip rips, then
      preview window opens
- [ ] Video plays
- [ ] Play / pause / scrub / Esc / Space all work
- [ ] Close preview — temp clip cleaned up

### Wizard (Phase 3b)

- [ ] All 4 wizard steps render (scan results, content mapping,
      extras classification, output plan)
- [ ] Each step's buttons (Next, Cancel) are themed correctly per
      the active theme

### Dialogs (Phase 3c-ii / 3c-iii)

- [ ] Show info / show error work
- [ ] ask_yesno / ask_input work
- [ ] ask_space_override pops with red warn styling on the deny
      button
- [ ] ask_duplicate_resolution shows 3 buttons (retry / bypass /
      stop)
- [ ] ask_movie_setup / ask_tv_setup forms render with all fields
- [ ] show_disc_tree multi-select works
- [ ] show_extras_picker / show_file_list list-pickers work
- [ ] show_temp_manager renders with status colors per row

### Failure modes

- [ ] Corrupt / missing QSS file → app falls back to no
      stylesheet, doesn't crash
- [ ] Missing makemkvcon → drive scan logs the error, falls back
      to placeholder
- [ ] Workflow exception → error dialog with friendly message,
      app stays alive, status returns to "Ready"

---

## Per-phase test counts (sandbox-verified)

After Phase 3f, the sandbox-runnable subset should pass:

```
tests/test_pyside6_*.py  → 491 tests (Phase 3a-3e)
tests/test_pyinstaller_spec.py → 12 tests (Phase 3f)
```

The full Windows-venv suite expects ~1551+ tests passing
(includes wizard tests that need Python 3.11+ and tkinter).

---

## Polish items still hanging (not v1 blockers)

* Phase 3c full Prep transcode-queue UI port — see
  [`phase-3c-iii-prep-workflow.md`](handoffs/phase-3c-iii-prep-workflow.md)
* Phase 3d remaining tabs (everyday / advanced / expert) — see
  [`phase-3d-port-settings-tabs.md`](handoffs/phase-3d-port-settings-tabs.md)
* Wizard Step 5 inline Preview button (PreviewDialog wire-up
  on the output-plan-review row level)

---

## Release pipeline (after smoke passes)

```bat
release.bat 1.0.X
```

This already enforces correct order:
git-clean → tests → build → verify → push → publish.  After
Phase 3g (pytest-qt rewrites) lands, the test step automatically
includes the Qt tests.
