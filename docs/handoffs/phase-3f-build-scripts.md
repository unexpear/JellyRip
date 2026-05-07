# Handoff Brief — Phase 3f: Update Build/Release Scripts (MAIN)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3f in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3e (MKV preview).
**Successor:** Phase 3g (pytest-qt rewrites).

---

## ⚠️ READ FIRST

- `docs/migration-roadmap.md`
- `JellyRip.spec` — current PyInstaller spec
- `build.bat`, `build_installer.bat`, `release.bat`
- `experiments/pyside6_smoke/` — proved Qt + PyInstaller works
  with `--onefile --windowed`. The bundle size grew 50 MB for the
  smoke test (QtCore/QtGui/QtWidgets only). Real bundle with
  QtMultimedia (3e) expected at +80-150 MB.

## Goal

Update build/release pipeline to handle Qt artifacts:

1. PyInstaller spec includes Qt plugins
2. `build.bat` produces a working Qt-based `.exe`
3. `build_installer.bat` includes Qt runtime in the installer
4. `release.bat` runs pytest-qt tests as part of validation
5. Bundle smoke test on a clean Windows machine (or VM)

## Concrete plan

### 1. Update `JellyRip.spec`

PySide6 ships with built-in PyInstaller hooks since 6.0. Most Qt
plugins are auto-bundled. Specifics to verify:

- `qt_multimedia_plugins` — required for MKV preview
- `imageformats` — for theme assets
- `platforms` — windows platform plugin

The smoke test in `experiments/pyside6_smoke/` had a working spec
shape. Mirror it for the production spec.

### 2. `build.bat`

May need:
- Verify PySide6 install in venv before invoking PyInstaller
- Pass `--collect-all PySide6` if hooks miss anything

### 3. `release.bat`

Already runs `python -m pytest`. After 3g lands, this picks up
pytest-qt automatically. Verify nothing else needs changing.

### 4. Smoke test

Build the `.exe` on this machine. Then run it on a clean Windows
machine (or fresh VM). Confirm:
- Window appears
- All themes render (6 themes as of 2026-05-03 — see `docs/design/themes/README.md`; the original 3-theme placeholder set was superseded when mockups landed)
- Setup wizard works
- MKV preview works
- No "Qt platform plugin missing" errors

Document the smoke test in `docs/release-process.md` (or wherever
release process lives).

## Definition of done

- [ ] `JellyRip.spec` updated for Qt
- [ ] `build.bat` produces a working `.exe`
- [ ] `build_installer.bat` produces a working `.msi`/`.exe` installer
- [ ] Bundle smoke test passes on a clean Windows machine
- [ ] Release process doc updated
- [ ] STATUS.md reflects 3f complete

## Branch identity

Same guardrails. **No AI features in MAIN.**

The AI BRANCH equivalent of these files (when Phase 4 runs) will
add Anthropic SDK to the bundle. That's Phase 4, not now.
