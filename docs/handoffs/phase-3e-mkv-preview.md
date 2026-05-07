# Handoff Brief — Phase 3e: MKV Preview (the v1-blocking feature)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3e in `docs/migration-roadmap.md`.
**Predecessor:** Phase 3d (settings).
**Successor:** Phase 3f (build/release scripts).

---

## Why this is the v1-blocking feature

Per migration plan decision #4: v1 ships when MKV preview ships.
The failure mode it prevents is *the wrong title gets ripped*. A
30+ GB write to disk catches a misclassification only after the
fact today; preview catches it before the rip starts.

This is the headline feature of the entire PySide6 migration.

## ⚠️ READ FIRST

- `docs/migration-roadmap.md`
- `docs/pyside6-migration-plan.md` "Why" section, MKV preview rationale
- `gui_qt/setup_wizard.py` (3b output) — preview lives in the
  output-plan-review step
- `STATUS.md`

## Goal

Add a video-preview widget to the setup wizard's "review output
plan" step. User can play any selected title's first ~30 seconds
inline. They see what they're about to rip before committing 30+ GB.

## Concrete plan

1. **Probe MakeMKV's `--minlength` flag** for short test rips. The
   preview workflow rips ~30 seconds to a temp file, plays it,
   discards it.
2. **Build `gui_qt/preview_widget.py`** using `QtMultimedia`:
   - `QMediaPlayer` for playback
   - `QVideoWidget` for display
   - Play/pause/scrub controls (`QSlider`, `QPushButton`)
3. **Wire into the wizard's output-plan-review step**: each
   selected title gets a "Preview" button that triggers the short
   rip + opens the preview widget.
4. **Cleanup**: preview temp files get auto-deleted via existing
   `cleanup_partial_files` infrastructure (or a dedicated
   `cleanup_preview_files` helper if more appropriate).
5. **Tests**: pytest-qt smoke test for the widget; behavior test
   that asserts preview-button click triggers the right makemkvcon
   args.

## Branch identity guardrails

Same. **No AI features in MAIN.**

## Definition of done

- [ ] `gui_qt/preview_widget.py` exists and renders MKV files
- [ ] Wired into the wizard's review step
- [ ] User can preview each selected title before committing
- [ ] Preview temp files cleaned up after viewing
- [ ] Tests pass
- [ ] Manual smoke test: real disc, run preview, verify video plays
- [ ] STATUS.md reflects 3e complete
- [ ] **Update README** — `## Main Workflows` section can now
      mention "Preview before commit" as a Smart Rip feature

## After this ships

You're now feature-complete for v1. Phases 3f (build), 3g (tests),
3h (release prep) remain.

## PyInstaller note

`QtMultimedia` adds substantial bundle size (additional codecs,
GStreamer/DirectShow plugins). Sub-phase 3f handles the spec
update; 3e just builds the widget. Don't worry about bundle size
here.
