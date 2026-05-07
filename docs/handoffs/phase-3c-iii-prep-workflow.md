# Handoff Brief — Phase 3c-iii: Prep MKVs Workflow Port (MAIN)

**For:** a fresh Claude Code session in JellyRip MAIN.
**Phase reference:** Sub-phase 3c-iii follow-up — the last 3c task.
**Predecessor:** Phase 3c-iii (disc-tree, list pickers, drive scan,
temp manager — all done 2026-05-03).
**Successor:** Phase 3d (settings + theme picker).

---

## ⚠️ READ FIRST

- `STATUS.md` — current Phase 3 state.  Phase 3c is functionally
  complete except for the Prep MKVs workflow.
- `docs/handoffs/phase-3c-port-main-window.md` — main 3c brief for
  context.
- `gui_qt/workflow_launchers.py` — already has an MVP handler at
  `_run_prep_mvp` that opens a folder picker and lists MKVs.  This
  brief is about the full port that replaces that MVP.

## Goal

Port the tkinter Prep MKVs workflow — a 3-window flow:

1. **Folder scanner subwindow** — `gui/main_window.py:1370`
   `_open_folder_scanner`.  Asks for a folder, then opens a
   progress window while `tools.folder_scanner.scan_folder`
   probes each MKV with ffprobe.  Returns a list of scanned
   entries (each with codec, duration, size, etc.).
2. **Transcode queue builder subwindow** —
   `gui/main_window.py:3204` `_open_transcode_queue_builder`.
   Shows the scanned entries in a tree, lets the user pick
   which to transcode, choose backend (FFmpeg vs HandBrake),
   choose output root, choose profile.
3. **Queue progress subwindow** —
   `gui/main_window.py:3688` `_run_transcode_queue`.  Shows
   per-job progress, status, completion log.

## Branch identity guardrails

Same as 3a/3b/3c.  **No AI features in MAIN, ever.**

## Concrete plan

This is a substantial port — likely **2 sessions**.  Suggested split:

### Session 1 — Folder scanner + queue builder

- `gui_qt/dialogs/folder_scanner.py` — port the scan-progress
  window.  Uses `tools.folder_scanner.scan_folder` (already
  tkinter-free) for the actual probing.  Public function returns
  `list[dict]` of scanned entries or `None` on cancel.
- `gui_qt/dialogs/transcode_queue_builder.py` — port the queue
  builder.  Uses `transcode.queue_builder.build_queue_jobs`
  (already tkinter-free) to construct the queue.  Returns a
  `QueueBuildResult` dataclass or `None` on cancel.
- Tests for both.

### Session 2 — Queue progress + workflow wiring

- `gui_qt/dialogs/transcode_queue_progress.py` — port the
  progress display.  Subscribes to per-job progress events,
  updates a per-job progress bar.  Side-effect-only; returns
  `None`.
- Update `gui_qt/workflow_launchers.py` — replace the
  `_run_prep_mvp` method's MKV-listing logic with the real
  3-window flow:
  1. Call the folder scanner (returns scanned entries or None)
  2. Call the queue builder (returns `QueueBuildResult` or None)
  3. Call `show_temp_manager` if cfg's `opt_show_temp_manager`
     wants it
  4. Build the queue via `transcode.queue.build_transcode_queue`
  5. Call the queue progress dialog
- Tests for the workflow.
- Manual smoke test on Windows venv with a folder of test MKVs.

## Pure helpers already in place

These already exist tkinter-free:

- `tools.folder_scanner.scan_folder(scan_request)` — does the
  ffprobe-driven probing.  Tkinter-free.
- `tools.folder_scanner.build_folder_scan_request` — builds the
  request object.  Tkinter-free.
- `transcode.queue_builder.build_queue_jobs` — builds the per-job
  list from scanned entries + chosen backend.  Tkinter-free.
- `transcode.queue.build_transcode_queue` — assembles the runnable
  queue.  Tkinter-free.

You only need to port the **3 subwindows** — the actual
transcode logic is already shared.

## Definition of done

- [ ] `gui_qt/dialogs/folder_scanner.py` exists, tested, returns
      same shape as tkinter
- [ ] `gui_qt/dialogs/transcode_queue_builder.py` exists, tested
- [ ] `gui_qt/dialogs/transcode_queue_progress.py` exists, tested
- [ ] `gui_qt/workflow_launchers.py:_run_prep_mvp` replaced with
      the 3-window flow
- [ ] All MainWindow Prep tests still pass
- [ ] Manual smoke on a folder with test MKVs works end-to-end on
      Windows venv
- [ ] STATUS.md marks Phase 3c **complete**

## Notes

- The MVP handler currently logs every MKV file path it finds.
  Keep that in the full port — users like the verbose feedback.
- The tkinter version uses `ttk.Progressbar` for per-job progress.
  In Qt, use a `QProgressBar` per row in a list, or a single
  bar that updates as each job completes.
- Transcode jobs run on worker threads via the existing
  `transcode.queue` machinery — the GUI just subscribes to
  progress events.  Use `gui_qt.thread_safety` to marshal updates
  to the GUI thread.

## After this lands

Phase 3c is **complete**.  3d (settings + theme picker) starts
next — see `docs/handoffs/phase-3d-port-settings.md`.
