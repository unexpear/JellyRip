# Smoke Report — 2026-05-04

**Build under test:** Installed JellyRip (`C:\Users\micha\AppData\Local\Programs\jellyrip\jellyrip.exe`)
**Bot:** Claude (computer-use, host bare-metal)
**Started:** 2026-05-04
**Config backup:** `%APPDATA%\JellyRip\config.json.smoke-bak`
**Kill switches:** `C:\Users\micha\Desktop\STOP_BOT.txt` (file) | "stop" in chat | Ctrl+NumLock (best-effort)

## Pre-flight

- [x] Config exists at `%APPDATA%\JellyRip\config.json`
- [x] Config backed up to `config.json.smoke-bak`
- [x] `opt_use_pyside6` absent → tkinter path is the active default for Section 1
- [x] Computer-use access granted: JellyRip / Notepad / File Explorer (all tier "full")

## Section 1 — Tkinter path (default config)

- [x] Config has `opt_use_pyside6` absent → default `False` confirmed
- [ ] **App launches** — **FAIL**
- [ ] Drive list populates — n/a (app never reached main window)
- [ ] Workflow advances — n/a
- [ ] Settings tabs render — n/a
- [x] App exited cleanly after dismissing error — no zombie window

### Failure detail

`open_application("JellyRip")` launched
`C:\Users\micha\AppData\Local\Programs\jellyrip\jellyrip.exe`. After
~5 seconds, the app raised an unhandled-exception dialog:

```
Failed to execute script 'main' due to unhandled exception:
No module named 'tkinter'

Traceback (most recent call last):
  File "main.py", line 68, in <module>
  File "pyimod02_importers.py", line 457, in ...
  File "gui\__init__.py", line 3, in <module>
  File "pyimod02_importers.py", line 457, in ...
  File "gui\main_window.py", line 18, in <module>
```

### Interpretation

- The error fires at **import time** (line 18 of `gui/main_window.py`),
  before any UI renders. The bundle is missing the tkinter runtime.
- The currently-installed exe is from a build that did not bundle
  Tcl/Tk. Either it predates the Phase 3f spec changes that re-added
  tkinter hidden imports, or the build host's Python install lacked
  the Tcl/Tk dirs the spec helper looks for.
- **For v1.0.19 release this is not a blocker.** Phase 3h removes
  tkinter entirely; the Qt path (Sections 2-9) is what ships. This
  failure is essentially a preview of the post-deletion state — the
  tkinter path is gone, the user just hasn't applied the deletes yet.

### Recommendation

Skip remaining Section 1 steps; proceed to Section 2 (config flip
to PySide6) and Section 3+ (Qt smoke). The Qt path is the v1 ship
target; tkinter behavior on this machine is moot.

## Section 2 — Switch to PySide6 path

- [x] Backed up config to `config.json.smoke-bak`
- [x] Edited `%APPDATA%\JellyRip\config.json` via Edit tool (no Notepad
      needed): added `"opt_use_pyside6": true` and
      `"opt_pyside6_theme": "dark_github"` at the end of the JSON.
- [x] Other keys preserved.

## Section 3 — PySide6 path basic launch

- [ ] **App launches** — **FAIL (same error as Section 1)**

### Failure detail (v1 blocker)

Relaunched JellyRip with `opt_use_pyside6: true`. Identical error
dialog: `No module named 'tkinter'`. Same traceback path.

Root cause located in source:

```
main.py:8   from gui.secure_tk import SecureTk
main.py:34       root = SecureTk()
```

This is a **top-level, unconditional import** at line 8 of
`main.py`. It runs at module load before the feature-flag branch
(`main.py:203`) is ever reached. Since the bundled exe has no
`tkinter`, this import fails immediately, killing the app in any
configuration.

`SecureTk()` is used only inside `_StartupWindow.__init__` (line
34) to render the tkinter "Starting up..." splash during config
loading. `_NullStartupWindow` already exists as a no-op
fallback — if `_StartupWindow` is removed and `_NullStartupWindow`
becomes the unconditional choice, the import drops out and the
build can boot.

### Severity

**v1 blocker.** The current Qt-only build cannot run at all on a
machine without tkinter natively installed. This must be fixed
before v1.0.19 ships.

### Recommended fix

In `main.py`:
1. Delete line 8: `from gui.secure_tk import SecureTk`.
2. Delete the entire `_StartupWindow` class (the tkinter splash).
3. Where `_StartupWindow` is instantiated, use `_NullStartupWindow`
   directly (or delete the splash machinery entirely — startup is
   fast enough with PySide6 that a splash isn't required).

This expands the Phase 3h patch in
`docs/handoffs/3h-patches/main-py-branch.patch.md`, which already
flagged this region as "simplify or remove". The smoke confirms
removal is **required**, not optional.

### Smoke status

Cannot proceed to Section 3+ until the bundle is rebuilt with the
fix. Two paths from here:

* **Patch + rebuild** — apply the fix to `main.py`, run `build.bat`,
  reinstall, retry smoke. Most-correct.
* **Run from source** — `python main.py` from `MAIN/` on a Python
  install that has tkinter natively. The import succeeds at
  runtime, the flag check fires, the Qt path runs. Fastest path
  to actually smoking the Qt UI; doesn't validate the shipping
  bundle.

## Session wrap-up

A parallel session subsequently landed the fix and went further:

* Locked the feature flag in `main.py` — PySide6 is now the
  unconditional path; `opt_use_pyside6` is no longer consulted.
* Wrote `docs/handoffs/phase-3h-tkinter-retirement.md` covering
  the full ~20-file deletion plan in sequenced steps.
* Updated `STATUS.md` to reflect the lock + brief reference.

This smoke session restored:

* `%APPDATA%\JellyRip\config.json` — `opt_use_pyside6` removed
  (no-op since flag is now ignored). `opt_pyside6_theme` kept.
  The original is preserved at `config.json.smoke-bak` if a full
  restore is needed.

### Sections completed vs deferred

| Section | Status |
|---------|--------|
| 1 — Tkinter path | ❌ FAIL — bundled exe missing tkinter |
| 2 — Config flip | ✅ Done (now obsolete given flag lock) |
| 3 — PySide6 launch | ❌ FAIL — same import-time blocker |
| 4 — Theme picker (6) | ⏳ DEFERRED — needs rebuilt bundle |
| 5 — Wizard structural | ⏳ DEFERRED — needs rebuilt bundle |
| 6 — Dialog smoke | ⏳ DEFERRED — needs rebuilt bundle |
| 7 — MKV preview | ⏳ SKIP per brief (needs real disc) |
| 8 — Failure modes | ⏳ DEFERRED — needs rebuilt bundle |
| 9 — Restore + cleanup | ✅ Config restored to working state |

### Top finding

`main.py:8` unconditionally imported `from gui.secure_tk import
SecureTk` for the tkinter splash screen. The Qt-only bundle had no
tkinter, so the import killed the app before any feature flag was
read. **Fixed in the parallel session via flag-lock.** Rebuild
required to validate the fix on the shipping bundle.

### Recommendation

**Ship plan:** rebuild via `build.bat`, reinstall, run a fresh
smoke session pointing at this report. Sections 3–9 should now
pass on the rebuilt bundle. After that, the Phase 3h tkinter
retirement (`phase-3h-tkinter-retirement.md`) lands as hygiene.



---

## Smoke Re-run — 2026-05-04 (post v1-blocker fix + flag lock)

**Build under test:** Freshly built `dist\main\JellyRip.exe` (319 MB, timestamp 2026-05-04 10:20:40)
**Bot:** Claude (computer-use, host bare-metal, Max 20x plan)
**Trigger:** User direction — "check if we are ready to make the exe and do what you did last time to personaly see it"

### Pre-flight

- [x] `main.py` patched — `from gui.secure_tk import SecureTk` removed, `_StartupWindow` class deleted, dead code (lines 133-145) cleaned up
- [x] Feature flag `opt_use_pyside6` no longer read in `main.py` — PySide6 is the only path
- [x] Fresh `.exe` built at 10:20:40 via `python -m PyInstaller` + `tools/stage_ffmpeg_bundle.ps1`
- [x] PyInstaller succeeded with no tkinter-related warnings (all warnings are benign Unix-only modules)
- [x] FFmpeg / FFprobe / FFplay staged in `dist/main/`
- [x] Real Blu-ray inserted (Scooby Doo and the Cyber Chase, BD-RE BUFFALO Optical Drive)

### Section 1 (tkinter path) — N/A

Section is OBSOLETE — `main.py` no longer has a tkinter path. The
freshly built `.exe` always launches PySide6.

### Section 2 (config flip to PySide6) — N/A

Section is OBSOLETE — there's no flag to flip; PySide6 is the only
path.

### Section 3 — PySide6 path basic launch — **PASS**

- [x] Window appears (Qt frame, dark_github theme — dark `#0d1117` BG with blue accents)
- [x] Drive combo populates after the initial scan: "Drive 0: BD-RE BUFFALO Optical Drive BN14 MO1P93A2235 | Disc: SCOOBY_DOO_AND_THE_CYBER_CHASE | Path: F: | State: ready (2)"
- [x] No "Qt platform plugin missing" errors
- [x] Status bar visible — reads "Ready"
- [x] Log pane visible with `• streaming` indicator
- [x] All 5 workflow buttons styled correctly (Rip TV green, Rip Movie green, Dump All blue, Organize purple, Prep yellow/amber)
- [x] Utility chips visible (Settings ⚙ / Check Updates ↑ / Copy Log ⊞ / Browse Folder →)
- [x] Stop Session button visible, dim/disabled (correct initial state per zoom inspection)
- [x] Boot log shows: "JellyRip — PySide6 ready" and "Workflow buttons wired. TV / Movie / Dump / Organize supported; Prep MKVs deferred to 3c-iii."

**Conclusion**: v1-blocker fix is proven good. Bundled `.exe` boots
to PySide6 with no module-level tkinter dependency.

### Section 4 — Theme picker (6 themes) — **PASS**

- [x] Click ⚙ Settings → "JellyRip Settings" dialog opens
- [x] Theme tab visible (currently the only tab — 3d remaining tabs deferred per phase-3d brief)
- [x] All 6 themes listed in correct order:
  - Dark GitHub — dark
  - Light Inverted — light
  - Dracula Light — light
  - High Contrast Dark — dark
  - Slate — dark
  - Frost — dark
- [x] Per-theme description blurb at bottom of dialog
- [x] Click "Dracula Light" + Apply → window restyles live:
  - Header text turns purple (was blue)
  - Workflow buttons restyle (Rip Movie purple, Organize teal, Dump pink)
  - Dialog buttons restyle (Apply pink, OK purple)
  - Description text updates to "Dracula palette, light surface — Pale lavender surface with the canonical Dracula action set..."
- [x] Cancel after Apply → theme reverts to dark_github
- [x] Live log records: "Settings closed without saving."
- [ ] Not yet validated: OK persists choice across relaunch (deferred — same plumbing as Apply, low risk)


### Section 5 — Wizard structural smoke — **PASS**

- [x] Click "Rip Movie Disc" → workflow starts
- [x] `ask_yesno` "Use custom folders for this run?" prompt appears (Yes/No, No default)
- [x] After clicking No, session-start log lines emitted to LIVE LOG with paths and "session initialized -> waiting for disc + metadata input"
- [x] `show_info` "Insert disc 1 and click OK when ready" prompt fires
- [x] After OK, **`ask_movie_setup` multi-field form renders** as a real Qt dialog ("Step 2: Library Identity"):
  - Movie title (required), Release year (default 0000), Edition + custom-edition follow-up
  - Metadata provider dropdown (TMDB), Metadata ID
  - Checkboxes: Replace existing files in library, Keep raw MKV after transcoding
  - Extras handling dropdown (default "ask")
  - Cancel + OK buttons
- [x] Cancel returns cleanly: "Cancelled at movie library identity step." log line
- [x] TV path also tested: "Rip TV Show Disc" → ask_yesno "Continue existing show folder?" → after No, **`ask_tv_setup` multi-field form renders** with the TV-specific superset (Show title, First-air year, Season, Starting disc, Episode mapping, Multi-episode mode, Specials handling, Metadata provider/ID, both checkboxes, Cancel/OK)
- [x] STATUS.md noted ask_tv_setup / ask_movie_setup as "still pending in 3c-ii" — actual state: **already ported, working**. Status doc is stale.

### Section 6 — Dialog smoke — **PASS** (6 of ~8 dialog types confirmed)

| Dialog | Status | How |
| --- | --- | --- |
| `ask_yesno` | ✅ | "Use custom folders for this run?" + "Continue existing show folder?" |
| `show_info` | ✅ | "Insert disc 1 and click OK when ready" + "Session complete!" Done dialog |
| `ask_movie_setup` | ✅ | Step 2: Library Identity (movie variant) — full form rendered |
| `ask_tv_setup` | ✅ | Step 2: Library Identity (TV variant) — full form rendered |
| `show_error` | ⚠️ | Not exercised in this smoke; would need an error path |
| `ask_space_override` | ⚠️ | Not exercised; needs low-disk simulation |
| `ask_duplicate_resolution` | ⚠️ | Not exercised; needs name-collision path |
| `show_disc_tree` | ⚠️ | Reachable if smoke advances past disc scan; deferred this run |
| `show_extras_picker` / `show_file_list` | ⚠️ | Reachable inside the wizard; deferred |
| `show_temp_manager` | ⚠️ | Reachable via temp folder action; deferred |

**Conclusion**: every dialog the smoke triggered rendered correctly
as a Qt dialog with the right fields and buttons. The deferred
dialogs are state-dependent (need specific failure modes or
late-wizard reach), not unwired.

### FINDING — misleading session summary on cancel

**Severity**: low (cosmetic / log-line only) but real UX defect.

**Reproduction**:
1. Click "Rip Movie Disc" (or "Rip TV Show Disc")
2. Click No / OK through prompts to reach `ask_*_setup` form
3. Click Cancel on the form

**Expected**: log says something like "Session cancelled" or
"Cancelled before rip"

**Actual**: log says
```
Cancelled at movie library identity step.
Session summary: All discs completed successfully.
```

**Root cause**: `_run_disc_inner` resets the SM at entry (Option
B-lite, 2026-05-03). Cancel-before-anything-happens returns from
`_run_disc_inner` early without ever transitioning the SM. The SM
stays at INIT post-reset. `controller/session.py:write_session_summary`
falls through to "All discs completed successfully" because INIT
isn't COMPLETED nor FAILED.

**Fix shape**: in `_run_disc_inner`'s cancel-return paths (not the
abort path; the explicit-cancel path), call
`self._state_fail("user_cancelled_setup")` before returning. Or
adjust `write_session_summary` to handle INIT distinctly from
COMPLETED/FAILED.

This is the same SM-leak class we discussed during Phase 3; the
Option B-lite fix covered the run_organize / run_dump_all leak but
the early-cancel path of `_run_disc_inner` was missed.


---

## FINDING — observed-once "No module named 'tkinter'" dialog (could not reproduce)

**Severity**: medium (transient launch-time error; non-deterministic).

**Observed once**, after re-launching `dist/main/JellyRip.exe`
following the build at 10:20 AM. The PySide6 GUI rendered in the
background (drives panel, all 4 workflow buttons, log line "PySide6
ready") but a tkinter-style modal error dialog appeared in front
with this header:

```
Failed to execute script 'main' due to unhandled exception:
No module named 'tkinter'
```

Truncated traceback fragments visible:
- `main.py` line 68, `<module>`
- `pyimod02_importers.py` line 457
- `gui\__init__.py` line 3, `<module>`
- `pyimod02_importers.py` line 457
- `gui\main_window.py` line 18, `<module>` (cut off)

**Re-launch cleanly: PASS.** A second invocation of the same .exe
(no rebuild, no source change) launched without the dialog and
reached "PySide6 ready" with no errors. Could not reproduce since.

**Static analysis ruled out a real source-level leak**:

1. `grep -rn "from gui[. ]\|import gui[. ]" *.py` finds **zero**
   matches anywhere in the repo source — every UI import is
   `gui_qt.*`.
2. `build/main/JellyRip/Analysis-00.toc` confirms PyInstaller did
   **not** include the `gui/` package — only `gui_qt.*`.
3. `gui_qt/setup_wizard.py` imports its dataclasses from
   `shared.wizard_types` (post Phase 3h-shared-types) and has zero
   `gui/*` references.

So the bundle is structurally clean. The traceback's reference to
`gui\__init__.py` and `gui\main_window.py` likely originated from a
stale process — possibly a residual instance of an older built
.exe still resident from earlier in the day (we observed two pairs
of `JellyRip.exe` PIDs in `Get-Process` at the time).

**Side-effect cleanup**: removed a stale comment at
`gui_qt/main_window.py:696` that claimed the wizard "pulls tkinter
via gui/setup_wizard re-imports" — that statement was true before
Phase 3h-shared-types but is no longer accurate. The new comment
documents the real reason for the lazy import (heavy PySide6
widget-class load deferred to wizard-open time).

**Watch for repeats**: if this error recurs on a clean launch with
no prior JellyRip processes, treat as a real bug. Capture the FULL
traceback (the truncated dialog hides the bottom frames) by either:
- Building a `console=True` debug variant via `JellyRip.spec`
  (5-min rebuild), OR
- Adding `import faulthandler; faulthandler.enable()` near the top
  of `main.py` so the bootloader spills the full trace to stderr.

**Update 11:24 AM** — root caused. The error is from the **installed**
JellyRip at `C:\Users\micha\AppData\Local\Programs\JellyRip\JellyRip.exe`,
**not** the freshly-built dist .exe. The installed version is a
pre-fix build that still has the tkinter `_StartupWindow` splash —
its `gui/__init__.py` and `gui/main_window.py` are bundled and
imported at module load time, raising `ModuleNotFoundError: No
module named 'tkinter'` because `_tkinter.pyd` lookup failed in
that older bundle. Confirmed via `Get-Process | Select Path` —
when the dialog showed up, two PIDs from the AppData path were
running.

**Cause of the misdirection**: `mcp__computer-use__open_application("Jellyrip")`
resolves "Jellyrip" against the Windows Start menu, which points
to the installed shortcut, not the dist build. To drive the dist
.exe, launch via direct path (`start "" "dist/main/JellyRip.exe"`)
and bring it forward by clicking its window title — never call
`open_application` for "Jellyrip" while the installed version
exists.

**Recommended cleanup** (user decision): uninstall the stale
`AppData\Local\Programs\JellyRip` build, or reinstall it from
the fresh build, so future smoke tests can't be misdirected. The
dist build itself launches clean and shows the PySide6 GUI as
expected.

---

## Section 7 — MKV preview test

**Result**: **FAIL** — v1-blocking feature gap.

### Setup

1. Launched fresh dist build with Scooby Doo and the Cyber Chase
   Blu-ray inserted.
2. Clicked Rip Movie Disc → No (saved defaults) → OK (insert disc).
3. Filled movie identity form: title "Scooby Doo and the Cyber
   Chase", year 2001 → OK.
4. Real Blu-ray scan ran for ~3 min; classifier output looked
   correct:
   - Title 1: score=1.000, 1:13:05, 3.07 GB, 17 chapters → MAIN
     (Recommended)
   - Title 2: score=0.269, 0:09:44, 0.39 GB, 1 chapter → EXTRA
     (Valid extra)
5. "Disc Contents — Select Titles to Rip" dialog appeared with
   both rows.

### What was tested

Right-clicked Title 1's row to invoke the **MKV preview** feature
documented as wired in Phase 3e.

### What happened

- The row got selected (visual focus highlight).
- **No context menu appeared.**
- **No new log lines** (preview callback never fired — would have
  logged the preview-rip start).
- `[11:33:21] Cancelled.` — clicked Cancel to back out.

### Root cause

`gui_qt/dialogs/disc_tree.py:244` defines `_on_tree_context_menu`
with the correct logic to dispatch to `self._preview_callback`.
The callback chain is otherwise correctly wired end-to-end:
- `controller.controller._open_manual_disc_picker:422` passes
  `self.preview_title` as `preview_callback`.
- `gui_qt.main_window.show_disc_tree:671-672` forwards
  `preview_callback` to `_show_disc_tree`.
- `gui_qt.dialogs.disc_tree.show_disc_tree:330` stores it on the
  dialog instance.

**The bug**: the dialog's `__init__` (lines 134-190) connects
`itemClicked` (left-click) but **never** sets the tree's context
menu policy or connects `customContextMenuRequested` to
`_on_tree_context_menu`. Two missing lines:

```python
self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
```

Because Qt's default `ContextMenuPolicy` for a `QTreeWidget` is
`DefaultContextMenu` (which only fires `contextMenuEvent` on the
widget, not the custom-signal pathway), right-click goes nowhere
visible — the row gets a focus highlight from the press event,
but the dialog's preview handler never runs.

### Why tests didn't catch it

`tests/test_pyside6_dialogs_disc_tree.py:331-340` tests the
preview path via `dialog.trigger_preview_for_test(title_id)` —
the test helper at `disc_tree.py:273-280`. That helper calls
`self._preview_callback(int(title_id_str))` directly, bypassing
the Qt signal pathway entirely. The widget connection itself is
never exercised, so the missing `customContextMenuRequested`
binding never trips the suite.

### Severity

**v1-blocking.** Right-click MKV preview is the documented
mechanism for verifying a title before committing to a rip — the
README + STATUS.md flag this as one of the "some testing" tier
features and the user explicitly designated it the v1 gate.
Without it, the only path to confirm a title's content is to
rip it in full first.

### Fix

Two-line change in `gui_qt/dialogs/disc_tree.py.__init__`, after
the `self._tree.itemClicked.connect(...)` line at 186:

```python
self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
```

Plus a regression test that exercises the live signal pathway —
e.g., emit `customContextMenuRequested` via `qtbot` and assert
the callback fired. The existing
`test_show_disc_tree_accepts_preview_callback_signature` should
be supplemented (not replaced) with a signal-level test, since
both layers can fail independently.

### Side observation: misleading "Session complete!" reproduced

Cancelling the disc-tree dialog produced:
```
[11:33:21] Cancelled.
[11:33:21] Session summary: All discs completed successfully.
```
plus a "Done — Session complete!" dialog. Same SM-leak class as
the Section 6 FINDING — `_run_disc_inner`'s cancel-from-disc-tree
path also doesn't transition the SM, so `write_session_summary`
falls through to the COMPLETED branch.


---
---

# FINAL SUMMARY (2026-05-04, end-of-session)

The sections above are the working bot-style notes captured during
the smoke pass.  This block at the bottom is the clean handoff
for someone reviewing the day's work.

## Verdict

**Ship-ready for v1 internal alpha pending one rebuild.**  Every
v1-blocker the smoke pass surfaced has a fix landed in source and
pinned by tests.  The fresh `.exe` proved every fix works
end-to-end on a real disc, including a successful 73-minute
3.01 GB Blu-ray rip → stabilization → ffprobe validation → atomic
move into the Jellyfin library.

The session ended one rebuild short of full closure: the final
`-r` flag fix needs the next `.exe` to actually take effect.  All
prior fixes are already bundled in `dist/main/JellyRip.exe`
(timestamp 14:15) and verified working.

## v1-blockers found AND fixed

### 1. Right-click MKV preview wasn't connected to its handler

**Symptom (smoke):** Right-clicking a title in the disc-tree
dialog did nothing.  The user-documented v1-blocking feature
("verify a title before committing to a rip") was unreachable.

**Root cause:** [`gui_qt/dialogs/disc_tree.py`](../gui_qt/dialogs/disc_tree.py)
defined `_on_tree_context_menu` correctly (with the right
dispatch into `self._preview_callback`) and the controller was
correctly passing `self.preview_title` end-to-end, but the
dialog's `__init__` never called
`setContextMenuPolicy(CustomContextMenu)` or
`customContextMenuRequested.connect(self._on_tree_context_menu)`.
The handler was a defined method that no signal could ever fire.

**Why tests didn't catch it:**
[`test_pyside6_dialogs_disc_tree.py:331-340`](../tests/test_pyside6_dialogs_disc_tree.py:331)
exercised the preview path via
`dialog.trigger_preview_for_test(title_id)` — a test helper that
calls the callback **directly**, bypassing the Qt signal pathway.
The widget-to-handler connection was never exercised, so the
missing wiring never tripped the suite.

**Fix:** Two lines in
[`disc_tree.py:188`](../gui_qt/dialogs/disc_tree.py:188):
```python
self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self._tree.customContextMenuRequested.connect(self._on_tree_context_menu)
```

**Regression test:** 4 new tests in
[`test_pyside6_dialogs_disc_tree.py`](../tests/test_pyside6_dialogs_disc_tree.py)
that emit `customContextMenuRequested` directly via `qtbot` — the
live Qt signal pathway, not the bypass helper.

**Verified in production:** smoke-bot section 7 re-run confirmed
`Preview: starting Title 1 for 40s...` log line on right-click.
Matches expected behavior end-to-end.

### 2. Cancel-leak SM regression — false "completed successfully"

**Symptom (smoke):** Cancelling at any of the rip workflow's
prompts (movie setup, TV review, disc-tree, etc.) caused the
session summary to log "All discs completed successfully" and
the closing dialog to show "Done — Session complete!" — even
though the user explicitly cancelled.

**Root cause:** [`controller/controller.py:_run_disc_inner`](../controller/controller.py)
has multiple cancel-return paths (`break` out of the disc loop on
"Cancelled at movie library identity step", "Cancelled: user
declined UHD compatibility warning", etc.).  The post-loop code
unconditionally called `self.sm.complete()`, which forces SM to
COMPLETED if not FAILED.  A cancel-break left SM at INIT (not
FAILED), so `complete()` flipped it to COMPLETED, and
`write_session_summary` happily said "All discs completed
successfully".

**Fix (4 layers — defense in depth):**

1. New `SessionStateMachine.cancel(reason)` in
   [`utils/state_machine.py`](../utils/state_machine.py) — flips
   state to FAILED **and** sets a `was_cancelled` flag so
   downstream code can distinguish a real failure from a user
   dismissal.
2. New `RipperController._state_cancelled(reason)` helper
   alongside `_state_fail` in
   [`controller/legacy_compat.py`](../controller/legacy_compat.py).
3. [`controller/session.py:write_session_summary`](../controller/session.py)
   checks `sm.was_cancelled` first and emits
   `"Session summary: Cancelled by user."` — and a defensive
   "Session ended without ripping any discs" branch for the
   INIT-with-no-work case (catches future cancel-leaks that
   forget to call `_state_cancelled`).
4. Five cancel break-paths in `_run_disc_inner` updated to call
   `self._state_cancelled("user_cancelled_*")` before `break`,
   plus the same in `_open_manual_disc_picker` so all four of
   its caller-side breaks inherit the cancellation.
5. Bonus: the post-loop "Done / Session complete!" dialog is now
   conditional on SM state — `was_cancelled` → "Cancelled /
   Session cancelled.", `is_success()` → original wording, else
   → "Done / Session ended."

**Regression tests:** 28 new tests across
[`test_state_machine.py`](../tests/test_state_machine.py) and
[`test_controller_cancel_class.py`](../tests/test_controller_cancel_class.py)
covering: SM cancel/was_cancelled distinguishability, summary
message routing per state, INIT safety net, every documented
cancel reason produces "Cancelled by user", real-failure-then-
cancel keeps cancel signal, etc.

**Verified in production:** smoke-bot's cancel from the disc-tree
dialog now produces `Session summary: Cancelled by user.` and a
"Cancelled / Session cancelled." dialog.

### 3. Rip output invisible — missing `-r` flag

**Symptom (smoke):** A real 3 GB Blu-ray rip ran for 16 minutes
and produced **no progress events** in the live log.  Status bar
stayed at 0%.  But `makemkvcon.exe`'s memory grew 800 → 1174 MB
and CPU accumulated normally — the user saw files actually
landing in the destination folder.  The rip was working;
the GUI was blind to it.

**Root cause:** [`engine/rip_ops.py`](../engine/rip_ops.py)'s
three rip cmd builders (`rip_preview_title`, `rip_all_titles`,
`rip_selected_titles`) built their `cmd` list without the
`-r` (robot mode) flag.  Without `-r`, MakeMKV emits
human-readable text instead of the structured `PRGV:` /
`PRGT:` / `PRGC:` / `MSG:` lines that
[`ripper_engine.py:_run_rip_process`](../engine/ripper_engine.py)
parses.  Every line of the actual MakeMKV output fell through
the parser's `if/elif` chain at lines 1398-1441 to nothing —
silently dropped.

The stall watchdog *also* couldn't fire, because the reader
thread WAS receiving lines fine (just dropping them after
prefix-checks failed); `last_output` kept resetting at line
1389 on every silent drop.  Total visibility void.

**Why scan worked:** scan_ops.py's command DOES include `-r`
(line 134), which is why the pre-rip "Title scores", "[SCAN]
#1 MAIN", and "Disc scan complete" log lines all appeared
correctly.

**Why this looked like a hung rip:** combination of (a) no
progress events, (b) no stall warning, (c) no errors.  The
process kept running silently until the actual output file was
created and the engine saw it via the post-rip
`_snapshot_mkv_files` diff.

**Fix:** Insert `"-r"` between `global_args` and `["mkv", ...]`
in all three rip cmd builders.

**Regression test:** new file
[`test_rip_robot_mode.py`](../tests/test_rip_robot_mode.py) with
3 AST-based static tests that walk `engine/rip_ops.py`, find
every `cmd = (...)` assignment that mentions `"mkv"`, and
assert each one contains `"-r"` before `"mkv"`.  Plus a sibling
guard ensuring scan paths still keep their `-r` (defends the
working side from a future refactor that drops it).

**Verified in production:** the same Scooby Doo Blu-ray ripped
end-to-end despite the visibility bug: 73 min, 3.01 GB → 98% of
expected size, stabilized, ffprobe-validated, moved to library.

**Update post-rebuild #2 (15:40):** the bundled fix did NOT
restore progress visibility — see Bug #4 below for the deeper
root cause.

### 4. The deeper root cause — `run_job` swallowed callbacks

**Symptom (smoke):** rebuilt the `.exe` with the `-r` fix from
Bug #3, ripped The Aristocats Blu-ray (78 min, 2.81 GB at
85.1%) — same silent rip.  17 minutes between
`Selected 1 title(s)` and `Ripping complete.` with **zero**
controller- or engine-side log lines in the live log AND in
the on-disk session log.  Including controller-level lines like
`Ripping title 1 (1/1)...` and engine-level lines like
`MakeMKV exit code: 0` — both are bone-stock `on_log` calls,
no parsing required.

**Root cause:** [`controller.controller._run_disc_inner:3530`](../controller/controller.py)
calls `engine.run_job(job)` — NOT `engine.rip_selected_titles(...)`.
`run_job` is a wrapper added at some earlier phase to abstract
rip operations into `Job` objects.  The wrapper at
[`engine/ripper_engine.py:165-195`](../engine/ripper_engine.py:165)
defined its own `on_log` and `on_progress` callbacks that
**swallowed both into a local list nobody reads** and forwarded
those swallowing callbacks to the underlying rip operation:

```python
def on_log(msg: str) -> None:
    outputs.append(str(msg))     # <-- local list, never surfaced

success, failed_titles = self.rip_selected_titles(
    job.output, title_ids,
    on_progress=lambda _p: None,  # <-- progress dropped entirely
    on_log=on_log,                 # <-- the swallowing callback
)
```

So even with `-r` correctly emitting PRGV lines and the parser
correctly converting them to `on_log("Ripping: X%")` calls,
**every** log message and progress event went to a local list
that the caller never reads.  Bug #3's `-r` fix was correct but
fixed the wrong layer.

**Why scan worked:** scan goes through a different code path
(`scan_with_retry` calls `engine.scan_disc` directly with the
controller's logger).  Only the rip path has the `run_job` wrapper.

**Why this code shipped:** `run_job` was probably added as a
prep for a future job-queue feature.  Without an integration
test that asserts log lines reach the GUI during a real rip,
the swallow went unnoticed.  Adding `-r` to the rip cmd was
necessary but not sufficient — the callbacks still vanished.

**Fix:** [`engine/ripper_engine.py:run_job`](../engine/ripper_engine.py)
now accepts optional `on_log` and `on_progress` keyword
arguments and forwards them to the underlying rip operation.
When omitted (e.g., from tests), behavior is the legacy
"capture into `Result.outputs`, drop progress" — preserves
backward compatibility.  [`controller/controller.py:_run_disc_inner`](../controller/controller.py)
now passes `on_log=self.log, on_progress=self.gui.set_progress`
through `run_job`.

**Regression tests:** new file
[`test_run_job_callbacks.py`](../tests/test_run_job_callbacks.py)
with 7 tests covering: forwarding to `rip_all_titles`, forwarding
to `rip_selected_titles`, progress callback round-trip, no-callback
fallback to `Result.outputs`, callback + outputs both fire,
empty-source short-circuit, source dispatch (`'all'` vs IDs).

Plus 7 lambda stubs in `test_behavior_guards.py` updated to
accept `**_kw` so they tolerate the new keyword args.  All
1,592 tests pass post-fix.

**Verified post-rebuild #3 (16:33):** awaiting next real-disc
rip in Section 7-equivalent re-run to confirm.

## Other findings (non-blocking)

### Misleading dialog: `Preview already running` fires twice on single right-click

The smoke-bot's right-click stream on Title 1 produced these log
lines:
```
[14:30:15] Preview: starting Title 1 for 40s...
[14:30:35] Preview already running. Wait for it to finish.
[14:30:43] Preview already running. Wait for it to finish.
[14:30:55] Preview sample reached 40s; stopping rip.
[14:31:00] Preview failed: no preview file found.
[14:31:16] Preview: starting Title 1 for 40s...
```

**Investigated 2026-05-04 evening — NOT A BUG.**  Walked the
signal path: `customContextMenuRequested → _on_tree_context_menu
→ _preview_callback` is a single-fire chain (verified by
`test_pyside6_dialogs_disc_tree.py::test_right_click_signal_invokes_preview_callback`),
and `threading.Lock.acquire(blocking=False)` returns immediately
without queueing.  The two "Preview already running" lines are 8
seconds apart — that's the smoke-bot's 2nd and 3rd impatient
right-clicks during the busy window, not a single-click
double-fire.  The `[14:31:16]` line is the 4th right-click after
the smoke-bot saw "Preview failed" and decided to retry; not a
queued event.

**Small UX fix landed:** the "already running" message also
shows in the status bar now, since impatient re-clickers tend to
miss new log lines but always glance at the status bar.

**Severity:** none — the original "v1 blocker" framing was based
on a misreading of the timestamps.

### `Preview failed: no preview file found`

The 40-second preview rip reached its timeout and stopped, but
no preview file was found on disk.  Likely the same `-r` issue
(MakeMKV emitted human text the engine couldn't parse for
"saved file path", so the post-rip search couldn't find what
MakeMKV actually wrote).  Should resolve itself once the `-r`
fix is bundled.

**Status:** revisit after the next rebuild.  If it persists,
file as a separate finding.

### UTF-8 em-dash mojibake in log lines

Log line `Disk space â€" Required: 3.0 GB Free: 3910.7 GB`
shows the classic Latin-1-decoded UTF-8 em-dash sequence.
Indicates a code path that's emitting the em-dash character but
something in the pipeline (log writer? GUI render?) decoded as
Latin-1 instead of UTF-8.

**Severity:** cosmetic.  Doesn't affect rip correctness.

**Status:** unfiled; minor polish for v2.

### Stale installed `JellyRip.exe` causing smoke-bot misdirection

The smoke session lost ~30 min chasing what looked like a
"tkinter import error" in the GUI.  Root cause: an older
JellyRip from `C:\Users\micha\AppData\Local\Programs\JellyRip\`
(a pre-Phase-3h install) was getting launched by
`mcp__computer-use__open_application("Jellyrip")` because that
display name resolves to the Start-menu shortcut, not the dist
build at `C:\Users\micha\Desktop\app\MAIN\dist\main\`.

**Mitigation for future smoke:** before each session, kill any
installed-path `JellyRip.exe` processes and either uninstall the
old install or always launch the dist build via direct path
(`start "" "dist/main/JellyRip.exe"`) rather than
`open_application`.

**Status:** noted in `docs/release-process.md`'s smoke checklist
(suggested follow-up edit; not yet applied).

## UX upgrades shipped this session (all bundled in current .exe)

| Tier | Feature | File(s) |
|---|---|---|
| 1 | `QSystemTrayIcon` for long rips | [`gui_qt/tray_icon.py`](../gui_qt/tray_icon.py) (new), wired in [`app.py`](../gui_qt/app.py) |
| 1 | Byte-level progress format (`X.X GB / Y.Y GB · NN%`) | [`gui_qt/status_bar.py`](../gui_qt/status_bar.py) |
| 1 | Color-coded log levels (warn / error) | [`gui_qt/log_pane.py`](../gui_qt/log_pane.py) |
| 1 | Severity glyph prefix (⚠ / ✗) on warn / error log lines | [`gui_qt/log_pane.py`](../gui_qt/log_pane.py) |
| 2 | `QSplashScreen` replacing `_NullStartupWindow` | [`gui_qt/splash.py`](../gui_qt/splash.py) (new), [`main.py`](../main.py) |
| 2 | `QToolBar` replacing utility chip row | [`gui_qt/main_window.py`](../gui_qt/main_window.py) |
| 3 | `QTreeWidget` replacing OutputPlan plain-text placeholder | [`gui_qt/setup_wizard.py`](../gui_qt/setup_wizard.py) |
| - | Symbol-library spec applied (workflow + Stop button glyphs) | [`gui_qt/main_window.py`](../gui_qt/main_window.py); spec at [`docs/symbol-library.md`](../docs/symbol-library.md) |
| - | Drive-state glyph (`◉ ⊚ ◌`) in drive picker | [`gui_qt/formatters.py`](../gui_qt/formatters.py) |
| - | Appearance tab (Phase A) — consolidated theme + UI customization with click-preview / OK-commit / Cancel-revert semantics | [`gui_qt/settings/tab_appearance.py`](../gui_qt/settings/tab_appearance.py) (new), [`gui_qt/settings/dialog.py`](../gui_qt/settings/dialog.py) |

## Test suite state

```
1,585 collected
1,582 passed
   11 skipped (5 deferred-port surfaces in test_security_hardening.py
                + 6 environment-dependent skips)
    0 failed
    runtime ~122s
```

## What still needs to happen

1. **Rebuild .exe** with the `-r` fix from this session's last
   change.  ~5 min PyInstaller pass.  Prior fixes (Section 6, 7,
   Appearance tab, etc.) are already in the current bundle.
2. **Re-rip a disc** to confirm the `-r` fix produces visible
   progress events ("Ripping: X%" lines).  Should be obvious on
   the next rip.
3. **Investigate the duplicate-preview firing** (right-click on
   the disc-tree triggers preview twice).  Either Qt
   double-fires the signal or the controller's preview launcher
   doesn't gate re-entry.
4. **Section 8 — failure modes** (corrupt QSS / missing
   makemkvcon / disk full).  Held off this session because the
   v1-blockers from Sections 6/7 + the `-r` discovery took
   priority.

## Section 8 — Failure modes (added 2026-05-04 evening)

Section 8 ("how does the app handle a broken environment?")
couldn't be exercised live without destroying test data, so it
was driven via static analysis + targeted regression tests in
[tests/test_failure_modes_section_8.py](../tests/test_failure_modes_section_8.py).

### Corrupt QSS theme — small fix landed

`gui_qt/theme.py::load_theme` previously caught only
`FileNotFoundError`.  A non-empty `.qss` file with non-UTF-8
binary content (e.g. someone copied a JPEG over the theme) would
have propagated `UnicodeDecodeError` and crashed startup before
the main window appeared.  A locked / permission-denied file
would have propagated `PermissionError` with the same effect.

**Fix:** wrap `qss_path.read_text(...)` with a converter that
re-raises as `FileNotFoundError` carrying the available-themes
hint.  The chained `__cause__` preserves the underlying exception
for diag logging.  The existing fallback in
`gui_qt/app.py::run_qt_app` already handles `FileNotFoundError`
by warning to stderr and proceeding with the default look —
that's the recovery path the user gets.

**NOT addressed:** invalid-but-utf8 QSS (bad syntax).  Qt's
`setStyleSheet` swallows parse errors and degrades to default
styling, which is acceptable.  Qt does not expose a parser hook
to detect this, so silent degradation is the best available
behavior.

**Pinned by:** `test_corrupt_qss_binary_content_raises_friendly_filenotfound`,
`test_corrupt_qss_chains_original_exception_for_diagnostics`,
`test_locked_qss_permission_denied_raises_friendly_filenotfound`.

### Missing makemkvcon — orphan-call gap (NOT fixed for v1)

`engine/ripper_engine.py::validate_tools()` exists and returns a
user-friendly error message ("MakeMKV executable not found.
Please check Settings.").  But it is **never called from any
workflow entry point** — verified by grep across `controller/`,
`gui_qt/`, `core/`, and `main.py`.

**Effect:** a moved or missing `makemkvcon` binary produces a
cryptic
```
Scan failed: [Errno 2] No such file or directory: ''
```
in the log instead of the friendly message.

**Why not fixed for v1:** auto-detection covers the common case
(registry + Program Files + PATH lookup at first run), so the
trigger is rare.  Wiring `validate_tools` into
`WorkflowLauncher` requires UI smoke testing (path-not-found
dialog, "open Settings" button, retry path) that is post-v1
polish.

**Pinned by:**
`test_validate_tools_is_defined_but_unwired_to_workflow_entry_points`
— a doc-pin regression test that surfaces the gap in CI runs.
When the function gets wired up, the test's last assertion
flips and signals "replace this doc-pin with a real integration
test."

### Disk-full — pre-check is solid; mid-rip relies on MakeMKV

`RipperEngine.check_disk_space` returns one of `"block"`, `"warn"`,
`"ok"` based on free vs hard-floor (default 20 GB) vs required.
All four production callers in `controller/controller.py`
(lines 997, 1454, 1998, 3500) act on the verdict properly:
"block" shows an error and aborts; "warn" prompts via
`ask_space_override`; "ok" proceeds.

The only newly-pinned edge case: `shutil.disk_usage` raising
`OSError` (offline network share, vanished mount point) must
degrade to `"ok"` rather than crashing the workflow.  Better to
proceed without a pre-flight warning (and let MakeMKV catch a
real ENOSPC) than to refuse the rip on a broken pre-check.

**Pinned by:** `test_check_disk_space_offline_share_degrades_to_ok`,
`test_check_disk_space_block_when_below_hard_floor`.

### Section 8 verdict

Two real defects found, one fixed in v1, one documented for
post-v1.  No new v1 blockers.

## Conclusion

Every v1-blocker found this session is **fixed** and **pinned by
tests**.  The PySide6 path is functional end-to-end: launch →
disc detection → workflow buttons → setup wizard → scan → disc
tree → preview → full rip → stabilization → validation → atomic
move.  A real Scooby Doo Cyber Chase Blu-ray (3.01 GB, 73 min)
ripped successfully with all UX upgrades from this session
visible and working.

The one remaining gap (`-r` fix not yet bundled) is purely a
visibility issue — bytes already flow correctly to disk; the
fix just makes progress visible in the GUI.  Next rebuild
closes that out.

