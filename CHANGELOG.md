# Changelog

<!-- markdownlint-disable MD013 -->

## [1.0.27] - 2026-07-01

Unstable pre-release — a feedback pass on ripping: progress you can watch,
cleaner logs, and thumbnails while browsing a folder.

### Added

- **Thumbnails in the Browse Folder window.**  Scanning a folder now shows a
  video-frame preview for each MKV, like a file browser, so you can tell
  titles apart at a glance.

### Fixed

- **The rip progress bar moves again.**  It's now driven by the output file
  growing on disk — weighted by each title's size — so it climbs steadily
  even on difficult discs (e.g. region-mismatched ones) where MakeMKV emits
  no progress ticks at all.  The old bar could sit frozen at 0%.

### Changed

- **The live rip log is readable.**  MakeMKV messages now show their resolved
  text (e.g. "Region setting … does not match …") instead of the raw
  `%1 …` format template, and the bar's progress is echoed to the log as a
  "Ripping: X.X / Y.Y GB (NN%)" line.

## [1.0.26] - 2026-06-14

Unstable pre-release — a workflow + UI pass on the TV ripping flow.

### Added

- **Watch a title before you rip it.**  The disc picker has a "Watch in
  VLC" control that rips the selected title to a temporary file and
  plays it, so you can confirm what a title actually is before
  committing to a full rip.
- **Name and number episodes right in the disc picker.**  The picker now
  has editable **Ep #** and **Episode name** columns, with each title's
  length and size beside it — set it all in one window.  A title left
  without a number is filed as an extra.
- **Cut / Copy / Paste in the picker's editable cells** (right-click
  menu; the usual Ctrl+C / V / X work too).
- **Type with a single click, plus Select All / Select None.**  The Ep #
  and Episode name cells open for editing on a single click and show a
  faint hint so it's obvious you can type in them, and two buttons check
  or uncheck every title at once.
- **Organize & resume use the picker too.**  Numbering already-ripped
  episodes (Organize Existing MKVs, or resuming a disc) now uses the same
  per-title picker — so a missing episode or an extra is handled the same
  friendly way as a fresh rip, instead of typing comma-separated lists.

### Changed

- **The post-rip "Episode Numbers" and "Episode Names" prompts are
  gone.**  A TV rip builds its plan straight from the picker instead of
  asking you to type comma-separated lists afterward.  The
  duplicate-number and existing-file safety checks still run, ending in
  a move preview you confirm.
- **TV picker and file lists sort by title number**, and each title
  shows both its "Title N" label and MakeMKV's real output filename so
  the scan list lines up with the files you get.
- **TV discs are treated as episodes, not one "main feature."**  The scan
  now labels full-length titles as Episodes and pre-checks them all,
  instead of picking a single "MAIN" and rejecting the equal-length
  episodes as duplicates; the rip logs read in episode terms.
- **Continue a box set across seasons.**  When there's another disc in
  the set, the app asks whether it's the same season or a new one (and
  which number), so Season 1 → Season 2 flows in one session instead of
  forcing a brand-new run.

### Polish

- **Tactile UI pass.**  Buttons darken on press and show a focus ring
  for keyboard navigation; clickable controls take a pointing-hand
  cursor; inputs and list rows gained hover/selected states.  Derived
  per-theme, so every built-in and custom theme gets it.

## [1.0.25] - 2026-06-10

Small fix release for the Settings dialog under light themes.

### Fixed

- Settings dialog now follows the theme under light themes.  A
  top-level `QDialog`'s background isn't reliably painted over the
  native window surface on Windows, so the dialog stayed dark under
  light themes (fresh and on live theme switch) while its controls
  restyled.  It now wraps content in a themed `#settingsDialogBody`
  surface, the same pattern the main window uses with `#mainCentral`.
- Settings tab bar is now themed.  It had no QSS rules, so unselected
  tabs lost contrast (white-on-white) once the dialog correctly went
  light.  Tabs now use muted labels with an accent underline on the
  selected tab, readable in every theme.

## [1.0.24] - 2026-06-09

Large bug-fix + packaging release driven by a full-codebase review.

### Changed

- **One-DIR app format.**  The app ships as a folder (exe + `_internal\`)
  instead of a single exe: instant launches (onefile unpacked ~600 MB to
  %TEMP% on every start), no leftover `_MEI` folders after crashes, and
  FFmpeg ships once instead of twice.  The portable download is now
  `JellyRip-portable.zip`; the installer shrinks to ~150 MB and cleans up
  the old staged FFmpeg on upgrade.  Unused `ffplay.exe` dropped.
- **New token-based theme system** with a Theme Maker (live full-app
  preview, save/export/import) and 9 new built-in themes (15 total).

### Fixed

- **Stop Session works** — the button was never enabled by production
  code; a long rip had no abort.  And stopping a multi-disc Dump All no
  longer deletes the most recently completed disc's files.
- **Organize Existing MKVs**: real season numbers (was hardcoded S00),
  separator-safe auto-delete (no more sibling-folder/temp-root hazard),
  and an honest "Organize Incomplete" on failed moves.
- **MakeMKV output decoded as UTF-8** — non-ASCII disc titles no longer
  mojibake into filenames or kill the scan/rip reader.
- **Progress bar math** — percent now derives from PRGV total/max, so the
  bar tracks the whole rip instead of running ahead / sawtoothing.
- **Move validation order** — the staged copy is validated BEFORE taking
  the final library name; failed non-atomic moves are quarantined.
  Truncated "degraded" rips are rejected against the scanned title size.
- **Title-file mapping for labeled discs** (previously only discs
  literally named "title" matched), enabling per-file integrity checks.
- **Title-bar X behaves like Cancel** in Settings (theme previews revert)
  and the MKV preview (file handle released).
- **Crash logging** — unhandled exceptions and native faults now write to
  `crash.log` in the profile config dir (the windowed exe was silent).
- **Updater** — the Authenticode query never worked (PowerShell param
  binding); downloads are now staged + length-checked.
- **Transcode builder (latent)** — `auto_prefer` probes the FFmpeg build
  (CPU fallback on AMD/Intel), CRF maps to GPU quality flags, and every
  command carries `-nostdin` + an explicit overwrite flag.
- **Blank log path** no longer appends every session log to a junk
  `..txt` file.

## [1.0.23] - 2026-05-30

Bug-fix release on top of the 1.0.22 audit cleanup — two user-facing
fixes around disc scanning and tool detection.

### Fixed

- **Stop is now responsive during disc scan.**  The scan loop read
  MakeMKV's output with a blocking ``readline()``, so the Stop button
  could appear frozen until the next line arrived.  Scan output now
  feeds through a reader thread + queue with ``proc.poll()``, so Stop
  takes effect promptly and trailing title metadata isn't dropped.

- **Blank tool path no longer breaks FFmpeg / MakeMKV auto-detect.**
  ``os.path.normpath("")`` returns ``"."``, which the tool resolvers
  read as a configured directory — so an empty ``ffprobe_path`` /
  ``makemkvcon_path`` (meaning "auto-detect") found nothing and
  reported "tool not found".  A new ``_norm_tool_path`` helper keeps a
  blank path blank, so auto-detection (and the bundled FFmpeg) work.

### Tests

- Scan-disc process test fakes gained ``poll()`` + ``stdout.close()``
  to match the reader-thread scan loop.  Full suite: 1647 passed, 5
  skipped.

## [1.0.22] - 2026-05-28

Audit-driven cleanup release.  No functional regressions; lots of
small correctness and ergonomics improvements pulled together
across a deep audit pass.

### Fixed

- **`stabilize_timeout` is now an actual deadline.**  The pre-move
  source-file stability check used to take a single before/after
  sample over ~1 second and fail immediately if sizes differed,
  despite the config key being named ``opt_stabilize_timeout_seconds``
  (default 60).  Replaced with a real polling loop that waits up to
  the configured timeout for the file to settle, polling every
  0.1–1.0s and honoring abort_event between samples.

- **ffprobe cache key now normcased on Windows.**  ``cache_key``
  used ``os.path.abspath(path)`` only, so reaching the same file
  via ``C:\Foo`` and ``c:\foo`` produced two separate entries.
  Now ``os.path.normcase`` is applied (no-op on POSIX).

- **Engine ``print()`` routed through logging.**  A bare
  ``print(f"Warning: failed to update session metadata ...")`` in
  ``update_temp_metadata`` bypassed the controller's log capture
  and interleaved with progress output on stdout.  Now uses
  stdlib ``logging.warning`` like the other 8 warning sites.

- **ffprobe duration return-type consistency.**  The
  abort-mid-process exit returned ``-1`` (int) where the other
  early-exit sites return ``-1.0`` (float).  Unified to float.

- **``_move_extras_to_categories`` now returns bool.**  Was None
  with silent partial-failure swallow.  Both callers in
  ``_run_smart_rip_inner`` and ``_run_smart_movie_extras_phase``
  now flip ``partial_rip = True`` on any extras-move failure,
  triggering ``_preserve_partial_session`` instead of falsely
  reporting "session complete" with bonus files stranded.

- **Settings tab persist failures now log.**  All 4 tabs (Everyday,
  Paths, Reliability, Appearance) caught ``self._save_cfg`` failures
  with bare ``except Exception: pass``.  Now log via
  ``logging.warning`` with the tab name so a disk-full or locked-
  config.json save error leaves a session-log breadcrumb.

- **Utility chip dispatch failures now surface in 3 places.**
  Handler exceptions in ``utility_handlers._dispatch`` used to write
  a single log-pane line and that was it.  Now also flips the
  status bar and calls ``logging.exception`` so the full stack
  trace lands in the session log.

- **Appearance tab live-apply / cancel-restore failures now log.**
  Four ``except Exception: pass`` swallows in
  ``tab_appearance.py`` (live-preview handler, theme-preview load,
  cancel-restore theme, cancel-restore live hook) now log instead
  of silent swallow.

- **Pages baseurl set so docs nav doesn't 404.**  ``docs/_config.yml``
  now declares ``baseurl: /JellyRip`` so Jekyll's ``{% link %}`` tag
  resolves to the project-path URLs instead of bare ``/foo.html``
  that only worked at the apex domain.

### Added

- **5 named constants in ``engine/ripper_engine.py``** replacing four
  magic numbers (raw-line capture cap 5000, ambiguity threshold 0.05,
  scan-cache TTL 300s, log-rollover threshold 5 GB).  Each has a
  comment documenting the rationale.

- **``opt_disc_presence_probe_seconds`` added to DEFAULTS.**  Was read
  from cfg at ``controller.py:1567`` with a hardcoded 45-second
  fallback but missing from the master DEFAULTS dict.  Now
  documented at the source.

### Changed

- **Drive-probe retries default bumped from 3 to 5.**  Slow optical
  drives that previously gave up after 3 retries (worst case 14s)
  now get 2 more attempts before the rip aborts.  Backoff base
  unchanged at 2.0s (capped at 8s per attempt).  Harmonizes with
  the AI fork's existing 5-retry default.

### Removed

- **Dead ``scan_disc`` delegate** in ``engine/ripper_engine.py``.
  Python's "last def wins" rule made the 3-line delegate at line
  553 unreachable — the live ``scan_disc`` was the ~325-line
  inline implementation later in the file.  Verified via
  ``RipperEngine.scan_disc.__code__.co_firstlineno``.  Removed
  the unreachable copy.

- **Dead resume-after-interrupt scaffolding** from
  ``_run_disc_inner``.  The locals ``resume_meta``, ``resume_path``,
  and ``active_resume`` were declared and read in ~15 branches but
  never populated, because ``check_resume`` was never called from
  this code path.  Every truthy-branch was unreachable.  Cleanup
  inlines the always-true fallback values and deletes the dead
  conditionals.  AI BRANCH keeps the feature wired up via its own
  ``check_resume`` call site.

- **Dead config key ``opt_use_pyside6``** from DEFAULTS.  The flag
  that gated tkinter-vs-Qt UI was retired alongside tkinter itself
  in v1.0.19; only the DEFAULTS entry and an obsolete-removed
  comment in ``main.py`` remained.  Deleted both.

- **Dead profile imports in ``main.py``** —
  ``get_active_profile`` and ``get_profile_window_title`` were
  imported but never referenced.

### Tests

- **3 of 5 truncated test bodies reconstructed.**  Three tests had
  ``pytest.skip("test body was truncated; awaiting reconstruction")``
  stubs.  Reconstructed from their names + sibling-test patterns
  and verified passing:
  ``test_episodes_from_filename_wrong_season_returns_empty``,
  ``test_run_smart_rip_warn_with_opt_warn_low_space_off_skips_prompt``,
  ``test_smart_rip_path_overrides_cancel_does_not_touch_sm``.
  Two stubs (``test_app_display_name_propagates_through_window_title_string``
  — obsolete since tkinter retirement; and
  ``test_engine_abort_called_before_run_job_terminates_subprocess`` —
  ambiguous original intent) were reframed with explicit notes.

- **2 of 5 skipped security tests reframed as positive tests.**
  ``test_update_check_stub_does_not_shell_out`` pins the negative
  property that the deferred-port update stub doesn't shell out.
  ``test_update_check_stub_logs_releases_url_to_match_fork`` pins
  that the stub directs users to MAIN's releases page.  One
  obsolete test (``test_notify_complete_uses_trusted_powershell``)
  deleted entirely — Qt path uses ``QSystemTrayIcon.showMessage``
  natively, no subprocess.  Two remain skipped (explorer
  open/reveal — features genuinely absent on Qt path).

- **Mojibake cleared from `CHANGELOG.md`, `smoke-report-2026-05-04.md`,
  and `tests/test_behavior_guards.py`** (14 sites in the test file).
  Same UTF-8-misread-as-cp1252 pattern that was cleared from
  ``engine/ripper_engine.py`` in v1.0.19.

Test suite: **1645 passed, 8 skipped** (was 1642 / 11).

## [1.0.21] - 2026-05-08

Audit-driven cleanup release.  Engine-side improvement: drive-probe
retries are now config-driven (was: hardcoded).  Plus pyproject
metadata fix and a bundle-content cleanup.

### Added

- `opt_drive_probe_retries` (default 3) and
  `opt_drive_probe_backoff_seconds` (default 2.0) added to
  `DEFAULTS`.  Users with slow optical drives can now bump the
  retry count without code changes.  Backed by the existing
  `_wait_for_drive_ready` retry loop.
- `_DEFAULT_MAKEMKVCON` resolver in `shared/runtime.py` — picks
  `makemkvcon64.exe` on 64-bit Windows hosts (where `ProgramW6432`
  is set), falls back to `makemkvcon.exe` elsewhere.  Matches the
  64-bit Python + Qt runtime PyInstaller bundles, avoiding the rare
  mixed-bitness "process suspended" hang.

### Changed

- `_wait_for_drive_ready` exponential backoff is now capped at 8s
  but scales cleanly from the configured base — at the default 2s
  base it produces 2 → 4 → 8 (the prior hardcoded sequence), but a
  user with `opt_drive_probe_backoff_seconds=1.0` would see
  1 → 2 → 4 → 8 → 8 with `opt_drive_probe_retries=5`.
- `pyproject.toml` keywords updated: dropped `tkinter` (retired in
  v1.0.19), added `pyside6` and `qt`.

### Removed

- `gui_qt/qss/warm.qss` — empty 0-byte placeholder leftover from
  the original 3-theme design exploration.  The QSS collector was
  shipping it into the bundle even though `_is_real_theme_file`
  filtered it at load time; deleting at the source means the
  bundle no longer carries the dead file.

### Fixed

- README "shipped path as of v1.0.0" → "since v1.0.19" (the
  Qt-only milestone).
- `STATUS.md:142` stale `__version__ = "1.0.19"` → 1.0.20 + clarifying
  context for v1.0.20 / v1.0.21.

## [1.0.20] - 2026-05-08

Documentation and repo-hygiene release.  No code or behavior changes
in the bundled `JellyRip.exe` — if you're already running v1.0.19 you
gain a public documentation site and a cleaner tracked tree, but the
ripping engine is byte-identical.

### Added

- GitHub Pages site published at
  [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/).
  Cayman theme, source = `main` branch / `docs/` folder.  Internal
  phase handoffs, smoke reports, code-signing drafts, and design-system
  source files are excluded via `docs/_config.yml` so they stay
  tracked for contributors but don't render on the public site.
- `docs/index.md` landing page with download CTA, project-info link
  set, in-site documentation TOC, and cross-link to the JellyRip AI
  fork.

### Removed

- `dashboard.html` — Claude productivity dashboard (reads `CLAUDE.md`,
  renders memory tabs).  Local-only tooling that was inadvertently
  tracked alongside the now-gitignored `CLAUDE.md`.  Untracked via
  `git rm --cached` and added to `.gitignore`.
- `ui_visual_assets_copy/` — visual-asset reference snapshot of the
  retired tkinter UI (8 files, ~4700 lines of dead Python with live
  `import tkinter` statements).  Untracked; kept locally for as long
  as the visual reference is useful.
- `release_notes_ai.{md,txt}` — drift'd duplicates of the AI fork's
  own release notes.  The AI fork now maintains its own copies on
  `unexpear-softwhere/JellyRipAI`; MAIN no longer carries a stale
  mirror.

## [1.0.19] - 2026-05-04

The Qt-only release. This closes out the multi-month PySide6
migration: the legacy tkinter UI has been retired across the live
import surface and the Qt path is now the only path. Minor-version
bump from 1.0.x signals the UI rewrite as a milestone change.

### Added

- PySide6 (Qt) desktop UI as the default and only shipped UI
  (`gui_qt/` package).
- Six built-in themes — `dark_github`, `light_inverted`,
  `dracula_light`, `hc_dark`, `slate`, `frost` — generated from a
  shared token table (`gui_qt/themes.py`) by `tools/build_qss.py`,
  switchable live from **Settings -> Themes**.
- Right-click MKV preview in the disc tree, backed by QtMultimedia
  (`gui_qt/preview_widget.py`), with transport controls and a
  scrubbable position slider.
- Setup wizard fully reimplemented in Qt across all four steps
  (scan results, content mapping, extras classification, output plan).
- Thread-safe GUI marshaling layer (`gui_qt/thread_safety.py`) so
  worker threads can post status, progress, and dialog calls back to
  the main thread without race conditions.
- Drive scanning runs on a worker thread and populates the drive
  combo via the same marshaling layer (`gui_qt/drive_handler.py`).
- pytest-qt regression coverage for every Qt module, gated behind
  `pytest.importorskip("pytestqt")` so non-GUI environments still
  run the rest of the suite cleanly.
- `requirements-dev.txt` pinning `pyinstaller>=6`, `PySide6>=6.5`,
  `pytest>=7`, and `pytest-qt>=4`.
- Phase-3g audit (`tests/test_phase_3g_audit.py`) acting as a
  regression guard against tkinter re-introduction.

### Changed

- `JellyRip.spec` now bundles PySide6 (including QtMultimedia and
  QtMultimediaWidgets), the six generated QSS files, and 22
  `gui_qt` submodule hidden imports. tkinter / Tcl-Tk bundling is
  removed.
- `requirements.txt` lists PySide6 as a runtime dependency.
- The `opt_use_pyside6` feature flag has been removed; Qt is the
  only UI path. `opt_pyside6_theme` controls the active theme.
- `docs/release-process.md` documents the manual smoke checklist
  for the v1 acceptance gate.

### Removed

- The tkinter UI (`gui/main_window.py`, `gui/setup_wizard.py`,
  `gui/session_setup_dialog.py`, `gui/secure_tk.py`,
  `gui/theme.py`).
- Tkinter-coupled tests (`tests/test_label_color_and_libredrive.py`,
  `tests/test_main_window_formatters.py`) and the
  `_FakeTkBase` / `test_gui_import` scaffolding inside
  `tests/test_imports.py`.
- The `pyinstaller_tk_runtime_hook.py` runtime hook.

### Migration notes

- Existing config files keep the same shape. The `opt_use_pyside6`
  key, if present, is silently ignored on first launch.
- Custom QSS overrides should target the objectNames documented in
  `gui_qt/qss/` rather than baking color values into Python.

### Smoke-session polish (added 2026-05-04 evening)

The following landed in the same release line as the Qt-only
milestone, after a real-disc smoke session uncovered remaining
v1-blockers and UX gaps. AI BRANCH absorbs all of these during
Phase 4 (see
`docs/handoffs/phase-4-ai-branch-port.md`).

- **MakeMKV `-r` (robot mode) flag** is now passed on every
  `makemkvcon` invocation (preview, all-titles rip, selected-titles
  rip), so the engine sees the machine-readable `PRGV:` / `PRGT:` /
  `MSG:` lines it needs to parse for live progress. Without it, a
  rip that was actually running looked hung in the GUI for 20–60
  minutes. AST-based regression tests in
  `tests/test_rip_robot_mode.py`.
- **`engine.run_job(on_log=, on_progress=)`** keyword arguments
  forward GUI hooks into the rip subprocess. Previously `run_job`
  swallowed every callback into a local list, so the live log and
  progress bar stayed silent for the whole rip. Pinned by
  `tests/test_run_job_callbacks.py`.
- **Session-state-machine cancel class fixed.** A user-cancelled
  session no longer reports "completed successfully" in the done
  dialog. New `SessionStateMachine.cancel(reason)` plus
  `was_cancelled` flag, and `write_session_summary` precedence
  walks `was_cancelled → COMPLETED → FAILED → INIT`. Pinned by
  28 regression tests in `tests/test_state_machine.py` and
  `tests/test_controller_cancel_class.py`.
- **Right-click MKV preview wired.** The disc-tree dialog now
  sets `setContextMenuPolicy(CustomContextMenu)` and connects
  `customContextMenuRequested` to `_on_tree_context_menu`. Pre-fix
  the handler was defined but never called. Pinned by signal-level
  regression tests.
- **`WorkflowLauncher` runs `engine.validate_tools()` pre-flight**
  on every disc-touching workflow click. A missing or moved
  `makemkvcon` / `ffprobe` now surfaces the friendly "Required
  Tool Not Found" dialog with the path-suggestion text instead of
  a cryptic `[Errno 2]` log line. Pinned by 8 tests under
  "Tool-path pre-flight" in
  `tests/test_pyside6_workflow_launchers.py`.
- **QSS theme loader robustness.** `gui_qt.theme.load_theme` now
  catches `OSError` and `UnicodeDecodeError` and raises
  `FileNotFoundError` with the available-themes hint, so a corrupt
  or locked `.qss` file can no longer crash startup before the
  main window appears. Pinned by `tests/test_failure_modes_section_8.py`.
- **UX upgrades.** Tray icon for long rips, splash screen during
  startup, toolbar replacing utility chip row, log-line severity
  glyphs (`⚠ warn`, `✗ error`), drive-state glyphs (`◉ / ⊚ / ◌`),
  byte-progress format on the progress bar, real `QTreeWidget` for
  the OutputPlan step (was a `QPlainTextEdit` placeholder). Symbol
  conventions documented in `docs/symbol-library.md`.
- **Pure-preview Appearance settings tab.** Theme picker now
  previews on click, applies on OK, reverts on Cancel. No Apply
  button. Five new cfg keys for log-pane density, drive-glyph
  display, severity-glyph display, status-bar density, and
  toolbar density.
- **UX copy sweep.** 12 user-facing strings rewrote for clarity
  (workflow seed lines, status messages, dialog prompts,
  pluralization for `N title(s)` → `N title`/`N titles`). UTF-8
  em-dash mojibake (the `â` `€` `"` triple that UTF-8 em-dashes
  collapse into when misread as Windows-1252) cleared throughout
  `engine/ripper_engine.py` and `controller/controller.py`.
- **Preview "already running" status-bar surface.** When a user
  rapidly re-clicks Preview during a busy preview, the "Wait for
  it to finish" message now also shows in the status bar where
  impatient re-clickers actually look.

Final smoke-session state: 1,608 tests green / 11 skipped / 0
failed. Real-disc rip of *The Aristocats* Blu-ray (78 min)
succeeded end-to-end with all UX upgrades visible and working.
Full trace at `docs/smoke-report-2026-05-04.md`.

## [1.0.18] - 2026-04-19

### Changed

- Release metadata is aligned on the `1.0.18` line across the app runtime, installer, docs, tester worksheet, and release notes.
- MAIN builds continue to stage `JellyRip.exe`, `JellyRipInstaller.exe`, bundled FFmpeg binaries, and notice files under `dist/main`.

### Fixed

- Transcode prep now falls back to a valid detected FFmpeg or HandBrakeCLI binary when a stale configured path no longer resolves.
- Manual movie-disc runs now preserve the selected edition when building the destination folder name.
- Settings saves now avoid partial config commits when the paired expert-profile write fails.
- The signed-update block path now shows the intended GUI error instead of throwing a callback arity exception.
- Verification fallback retries no longer report a rejected transcode as completed before the retry starts.

## [1.0.17] - 2026-04-15

### Changed

- MAIN release builds now stage `JellyRip.exe`, `JellyRipInstaller.exe`, bundled FFmpeg binaries, and notice files under `dist/main` so the trunk worktree has a dedicated artifact location.
- Build, installer, and release scripts now read release assets from `dist/main`, matching the documented MAIN-only packaging flow.

### Fixed

- FFmpeg bundle discovery now checks the nested Desktop sibling layout used by this MAIN worktree, so bundled release builds still find the provided full build without copying it into the repo.
- Release metadata is aligned on the `1.0.17` line across the app runtime, installer, docs, tester worksheet, and release notes.

## [1.0.16] - 2026-04-13

### Changed

- Improved FFmpeg abort handling, copy-progress logging, and transcode validation for more reliable encode and packaging flows.
- Restored the richer `JellyRip.spec` release configuration so packaged builds consistently carry version metadata, bundled FFmpeg assets, and runtime dependencies.
- Aligned release metadata on the `1.0.16` line across the app runtime, installer, docs, tester worksheet, and release notes.

### Fixed

- Build output policy is back in sync with the docs: release executables stay in GitHub Releases instead of being tracked in the repository.
- In-app update checks now follow the newest published release, including unstable prereleases, so the updater no longer falls back to the older stable line.

## [1.0.15] - 2026-04-11

### Fixed

- Restored a visible top-level `ABORT SESSION` control so the user can abort a running task even when the inline prompt bar is hidden.
- Fixed log auto-follow behavior by checking whether the log was already near the bottom before appending new text.

## [1.0.14] - 2026-04-11

### Added

- Added plain controller boundary modules for session paths, rip validation/retry policy, session recovery, and TV library scanning.
- Added direct unit coverage for those extracted modules so the logic can be tested without importing Tk or the legacy controller mixin.
- Added a release consistency guard that checks version alignment and prevents the root `JellyRip.exe` binary from being tracked in git.

### Changed

- Shrank `controller/legacy_compat.py` by turning session path, rip validation, session recovery, and library scan helpers into thin compatibility wrappers.
- Moved resume selection prompt-model logic out of `SessionHelpers.check_resume` while keeping the UI yes/no callback at the edge.
- Kept the full behavior-guard suite passing while expanding the test suite to cover 250 checks.

## [1.0.13] - 2026-04-09

### Added

- FFmpeg source handling now offers two user-facing modes: `Safe (Copy First)` and `Fast (Read Original)`, with plain-language explanations in Settings and the queue builder.

### Changed

- The current working release line is now aligned as `1.0.13`, with `1.0.12` left as the previous git revision point.
- FFmpeg queue jobs and one-click recommendations now carry the selected source-handling mode through to logs and execution.

### Fixed

- `JellyRip.exe` now embeds Windows file and product version metadata so the next build shows a clean application version in Explorer.
- Release metadata files (`README`, release notes, installer version, and release script examples) are synchronized for the `1.0.13` line.

## [1.0.12] - 2026-04-04

### Changed

- In-app updater now launches `JellyRipInstaller.exe` in silent in-place update mode (`/VERYSILENT /CLOSEAPPLICATIONS /NORESTART`) and falls back to normal launch if silent invocation fails.
- Inno Setup installer is now explicitly configured for update flows (`UsePreviousAppDir`, `CloseApplications`, `CloseApplicationsFilter`, `RestartApplications=no`) so reinstalling acts as an updater.
- Build and release scripts now build via `JellyRip.spec` instead of ad-hoc CLI flags, ensuring release artifacts consistently include the same runtime hooks and bundled dependencies as tested builds.

### Fixed

- Movie resume path now always uses a fresh temp rip folder instead of reusing the previous session folder, preventing `_purge_rip_target_files` from deleting previously successful MKVs during a retry.
- Smart Rip now exits immediately when abort is triggered during metadata prompts (title/year/metadata), avoiding fallback-name/0000-year continuation after user abort.
- Auto-title fallback is now informational log output only and no longer appears as a session warning/failure summary line.

## [1.0.11] - 2026-04-03

### Added

- CINFO disc-level parsing: scan now extracts disc title, language code, language name, and volume ID from MakeMKV output.
- `--minlength` scan filter: new `opt_minlength_seconds` setting (Advanced → MakeMKV) tells MakeMKV to skip titles shorter than the configured threshold during scan.
- Jellyfin metadata ID prompts: Smart Rip, Manual Disc, and Organize flows now ask for an optional TMDB/IMDB/TVDB ID. Folder names get Jellyfin-compatible tags like `[tmdbid-603]` or `[imdbid-tt1375666]`.
- `parse_metadata_id()` accepts flexible input formats: `tmdb:12345`, `tmdb-12345`, `tt1234567`, `tvdb:79168`, or bare integers (assumed TMDB).
- `build_movie_folder_name()` and `build_tv_folder_name()` centralize Jellyfin-style folder naming with optional metadata tags.
- 34 new tests for the naming module (180 total tests passing).

### Changed

- `build_fallback_title()` now prefers CINFO disc name over per-title TINFO name when the disc name is available and non-generic.
- Generic disc name detection expanded to catch both "Title NN" and "Title_NN" patterns plus "Disc"-prefixed names.

### Fixed

- Fixed 73 mojibake em dashes in controller.py (triple-encoded UTF-8 bytes replaced with proper U+2014).

## [1.0.10] - 2026-04-02

### Added

- Added repository-standard project files: `CONTRIBUTING.md`, `SECURITY.md`, `pyproject.toml`, and a Windows GitHub Actions test workflow.
- Added `docs/architecture.md` and `docs/repository-layout.md` to explain the app's layered design and flat-layout rationale.
- Added settings for optional prompt auto-timeouts and optional unattended disc-swap timeouts.
- Added unified tool resolver layer (`resolve_tool`, `resolve_makemkvcon`, `resolve_ffprobe`) with resolution order: saved config → common install paths → PATH environment variable.
- Added `validate_makemkvcon` and `validate_ffprobe` helpers that run a live probe command and return a success flag and error message.
- Added `should_keep_current_tool_path` safeguard: a working saved tool path is never replaced by an unvalidated new path.
- Added `tests/test_config_tools.py` with 5 regression tests covering resolver order and the overwrite-guard rule.

### Changed

- Reworked repository documentation to better match the expectations of a maintained small Windows desktop app project.
- Updated preview-related tests so pytest never launches a real media player during local or CI test runs.
- Settings save flow now validates new tool paths before accepting them; rejects silently-broken replacements and logs the rejection reason.
- Engine `validate_tools` now routes both MakeMKV and ffprobe through the resolver layer so PATH installs and custom locations are found automatically.
- Multi-disc dump mode renamed from "Unattended" to "Dump All" in UI labels and log messages for clarity.
- Extras selection changed from a yes/no keep-all toggle to a multi-select picker so individual extra titles can be deselected.

### Fixed

- Multi-disc dump flow now pauses with an explicit between-disc confirmation prompt and no longer times out by default while waiting for user swap actions.
- Unrecognized discs during multi-disc dump can now be advanced manually (bypass) or stopped instead of being forced into retry-only behavior.
- GUI prompt timeout behaviour is now configurable via Settings → Advanced → Interactive Timeouts instead of being a hard-coded 300-second safety value.

## [1.0.9] - 2026-03-29

### Windows UX + path hardening

- Removed browse UI flows for now (Settings browse buttons and inline input browse) to keep path entry deterministic while Windows dialog stability work is deferred.
- Added `CREATE_NO_WINDOW` flags to Windows subprocess calls to stop black console-window flashes during MakeMKV/ffprobe/PowerShell operations.
- Update installer launch now uses `os.startfile(...)` with a pre-launch UAC notice so elevation is handed off to Windows correctly.
- Added Windows reserved-name and empty-name guards in `clean_name` (e.g. `NUL`, `COM1`) to avoid invalid or dangerous filenames.
- Added Windows-friendly path validation using probe-write checks (instead of `os.access(..., os.W_OK)`) and drive-letter-agnostic system-path blocking.
- Added long-path (`\\?\\`) file-I/O handling in the engine for move/copy/log/metadata operations so deep TV paths do not fail at 260 characters.

### Docs / release metadata sync

- README build instructions now use `main.py`, matching the current packaged entrypoint.
- Release notes now include both `JellyRip.exe` and `JellyRipInstaller.exe` download links for `v1.0.9` and `latest`.
- Documentation now states explicitly that generated `dist/` binaries are published through GitHub Releases and are not committed to the repository.

### Safety / Deadlock fixes (gui/main_window.py)

- **`ask_yesno`**: the wait loop now checks `abort_event` and applies a 300-second safety timeout, matching the existing guard in `ask_input`. Previously the loop was unbounded — if the `_abort_watch` thread failed to fire `done`, the worker thread would hang forever.
- **`ask_input` race condition**: added `self._input_lock = threading.Lock()` (initialised in `__init__`). Every call to `ask_input` acquires this lock before touching the shared `_input_result`/`_input_event` state, serialising concurrent prompts and eliminating the read-clobber race.

### Correctness fixes

- **`rip_selected_titles`** (engine/ripper_engine.py): return value changed from `(not abort, failed_titles)` to `(not abort and not bool(failed_titles), failed_titles)`. Previously `True` was returned even when individual titles failed, which was misleading — `_normalize_rip_result` was the real gate but the signal was confusing. The change is safe: callers all pass the result through `_normalize_rip_result` which does file-presence + ffprobe validation.
- **`SessionStateMachine.complete()`** (utils/state_machine.py): new method that forces the state to COMPLETED if the session has not already failed. Used by `_run_disc` which manages its own multi-disc loop and never tracked intermediate state transitions.
- **`_run_disc`** (controller/controller.py): calls `self.sm.complete()` before `write_session_summary()` at the end of the disc loop. Previously the state machine was always in INIT (never transitioned by this flow), causing `write_session_summary` to skip the COMPLETED branch and miss the warning-list display logic.

### Security fixes

- **Update download TOCTOU** (gui/main_window.py): replaced the predictable fixed temp path (`tempdir/JellyRipUpdate/`) with `tempfile.mkdtemp(prefix="JellyRipUpdate_")`. The unique directory is cleaned up (`shutil.rmtree`) on every failure path and before early returns, preventing stale downloads from lingering.
- **Path injection in `get_authenticode_signature`** (utils/updater.py): replaced string-formatting the file path into a PowerShell command (only escaped single quotes, leaving backticks and `$(...)` injectable) with a `param([string]$p)` block and `-LiteralPath $p`. The path is now passed as a PowerShell parameter value, never interpolated into command text.

### Architecture / Bad patterns

- **`handle_fallback`** (utils/fallback.py): removed three `hasattr(controller, "_record_fallback_event")` duck-checks. The function is hardwired to `RipperController` — pretending to be generic via `hasattr` added noise without value. Direct calls are cleaner and any AttributeError is now a real programming error.
- **`shared/runtime.py` `__all__`**: removed all stdlib re-exports (`os`, `re`, `json`, `threading`, `datetime`, `tk`, `ttk`, etc.). `__all__` now only lists runtime constants and project-specific helpers. Stdlib is imported directly by callers.
- **`gui/main_window.py`**: replaced `from shared.runtime import *` with explicit imports of stdlib (os, re, json, tkinter, etc.) and the specific runtime symbols it needs.
- **`JellyRip.py`**: replaced `from shared.runtime import *` with explicit imports of only the symbols it re-exports.
- **`config.py`** and **`utils/helpers.py`**: replaced `from shared.runtime import json, os, shutil, ...` with direct stdlib imports.
- **`tests/test_imports.py`**: split GUI import into its own `test_gui_import` function guarded by `unittest.mock.patch("tkinter.Tk")`. The original test crashed on headless CI because tkinter requires a display at import time.

## [1.0.8] - 2026-03-28

### Code review fixes (10 issues closed)

- **`_normalize_rip_result`**: glob pattern changed to `**/*.mkv` with `recursive=True` — previously missed MKV files when MakeMKV wrote into subdirectories, causing rips to be silently treated as failures.
- **`get_available_drives`**: added `proc.wait(timeout=30)` with `kill()` on `TimeoutExpired` — previously the thread could hang indefinitely if `makemkvcon` stalled on startup.
- **`check_disk_space`**: removed `os.makedirs` side-effect; now returns early with a log warning if the target path doesn't exist rather than silently creating it.
- **`config.py` `load_config`**: split `except Exception` into `except json.JSONDecodeError` (logs "config corrupt, resetting") and a general `except Exception` (logs the actual error). Config loss is now visible to the user.
- **`clean_name`**: regex extended to strip ASCII control characters and null bytes (`\x00–\x1f`) in addition to forbidden filename characters — disc names with embedded control chars could silently corrupt filenames.
- **`scan_with_retry`**: removed unreachable `if result is not None` branch that followed an `if result is None: continue`.
- **`choose_best_title`**: pre-computes `score_title` once per candidate into a list and selects the max — previously called `score_title` twice on the winning title.
- **`_parse_int_or_default`** removed; call sites replaced with `safe_int(…)` (already imported from `utils.parsing`) with an `or 1` fallback where the default was non-zero.
- **`DummyGUI`** in `tests/test_behavior_guards.py`: added `set_progress`, `start_indeterminate`, `stop_indeterminate` stubs — missing methods caused `AttributeError` in any test that hit `scan_with_retry`.
- **README**: version header updated from v1.0.6 to v1.0.8.

### Correctness hardening — tiered integrity validation

- Replaced the single 60% duration threshold in `_verify_container_integrity` with a three-tier model: severe (<50% or <40% for short titles), likely-truncation (50–75% / 40–60%), minor mismatch (75–90% / 60–85%). Normal variance (≥90%) produces no warning.
- Added multi-signal escalation: a file only escalates to TRUNCATION ERROR when **both** duration and size are below threshold simultaneously, preventing false positives from inaccurate disc-scan metadata.
- Expected size values below 200 MB are now excluded from size-based escalation (disc scan metadata is unreliable for small titles).
- Multi-file titles (seamless branching) now aggregate their total duration/size before comparing against expected, preventing per-file false warnings.
- Duplicate warnings are deduplicated by `title_id` — at most one warning per logical title regardless of how many physical files it spans.
- Short titles (expected < 600 s) use widened tiers to account for higher relative variance in disc timing metadata.
- Both `run_smart_rip` and `_run_disc` (TV path) now pass `expected_durations`, `expected_sizes`, and `title_file_map` to `_verify_container_integrity`, making the tiered check universal across all ripping modes.
- In strict mode (`opt_strict_mode`), any tier below "minor" (< 75%) escalates to a hard failure.

### Attach to existing library

- New "Continue an existing show folder?" prompt at the start of every TV disc rip. Users can point JellyRip at a show folder that was created in a previous session (or by another tool); the app scans for existing season folders and episode files and writes new episodes directly into that folder.
- `_scan_library_folder(show_root)` scans a show root for `Season XX` subdirectories and their episode files, returning a dict of `{season_num: [ep_nums]}`. Used to display which seasons already exist in the prompt.
- `_scan_episode_files(folder, season)` recognises three naming formats: `SxxEyy` (standard), `Nx01` (1x01), and `Episode N`. Case-insensitive. Only reads the directory listing.
- `get_next_episode(existing)` implements gap-fill logic: returns the lowest missing episode number rather than simply appending after the highest. If Season 1 has E01, E02, E04 (E03 missing), the next suggestion is E03.
- Episode number prompt in `_select_and_move` now pre-fills using gap-fill logic and logs whether it is "gap-filling from" or "continuing from" the detected offset.
- When an existing library folder is selected the season prompt shows which seasons were detected (e.g. `S01  S02`) and the destination is written directly into the selected folder rather than constructing a new path under `tv_root`.

### Regression tests

- 5 regression tests for tiered integrity: severe warn-only (no size), severe + size escalation, expected-size clamping, strict-mode failure, minor mismatch passes.
- 8 regression tests for integrity aggregation: multi-file title aggregation, dedup (one warning per title), size floor, short-title tolerance.
- 4 tests for `get_next_episode` gap-fill.
- 6 tests for `_scan_highest_episode` / `_scan_episode_files` (compat wrapper, case-insensitive, season isolation, missing folder, None dest_folder, `1x01` format, `Episode N` format).
- 5 tests for `_scan_library_folder` (season dir detection, non-season dir exclusion, empty root, missing path, sorted episode lists).

## [1.0.7] - 2026-03-28

### Correctness hardening

- Eliminated duplicate ffprobe analysis passes in TV/Movie disc (`_run_disc`) and Smart Rip (`run_smart_rip`) pipelines. `analyze_files()` result is now shared with `_verify_container_integrity()` via a new `analyzed=` parameter — each file is probed exactly once per pipeline step.
- Fixed `run_smart_rip` state machine: `STABILIZED` transition was missing on the normal (non-retry) path; `VALIDATED` transition was dead code (placed after an unconditional `return`). Both are now correctly placed on the success path.
- Fixed `run_organize()` path drift: removed early `cfg["tv_folder"]` / `cfg["movies_folder"]` / `cfg["temp_folder"]` reads that silently bypassed run-time path overrides. All three folder roots now derive exclusively from `get_path()` after `_init_session_paths()`.
- Added `_ensure_session_paths()` guard: raises `RuntimeError` immediately if `session_paths` has not been initialized, making misconfigured calls fail loudly rather than silently writing to the wrong folder.
- Cleaned up post-stabilization size advisory log to use the format: `X MB (below threshold — expected Y GB → threshold Z GB)`.
- Replaced exit-code-based rip failure forcing with validation-based degraded success classification. MakeMKV frequently exits non-zero on real discs even when output is usable; the engine now checks whether files were actually produced. Non-zero exit + files present → degraded success (warning added to session report, downstream stabilization and ffprobe still validate the file). Non-zero exit + no files → real failure, unchanged. Session summary now distinguishes "All discs completed successfully" from "Completed with warnings" when degraded titles were detected.

### Test coverage

- Added 7 regression tests covering `_ensure_session_paths`, `_verify_container_integrity` with and without pre-analyzed data, integrity failure cases (zero duration, count mismatch), and advisory log format.
- Added 4 regression tests for degraded rip classification: degraded success path, real failure path (no files), session report population, and session summary warnings vs. clean success branching.

## [1.0.6] - 2026-03-27

### New features

- Added per-title Preview actions in the title picker, including short disposable sample rips and VLC launch support.
- Added fallback title naming mode in Settings with friendly options: timestamp, auto title, or auto title plus timestamp.

### Resume and workflow improvements

- Expanded workflow-level resume metadata to restore key inputs (title, year, season, selected titles, episode fields).
- Added resume-aware defaults in input prompts so interrupted sessions can continue with less manual re-entry.
- Added metadata phase tracking updates through setup, ripping, analyzing, moving, failed, and complete states.

### Reliability hardening

- Enforced all-or-nothing rip normalization: aborts, failed titles, missing outputs, or invalid outputs are treated as session failure.
- Added failed-session cleanup that wipes output files while preserving metadata for future workflow resume.
- Added pre-rip target file purge for `.mkv` and `.partial` files to prevent file-level resume artifacts.
- Added regression guard coverage that enforces `rc != 0` as failure even if MKV output files exist.
- Added complementary guard coverage that enforces abort as failure even when output files are present and ffprobe-valid.

### UI and settings

- Reworked Settings into tabbed sections for easier navigation across Paths, Everyday, Validation, Advanced, and Logs.
- Added low-confidence Smart Rip threshold control and improved naming-mode presentation in the settings UI.
- Added a top-bar Check Updates action that checks GitHub Releases and can download/launch update packages.

### Distribution

- Added Inno Setup installer support (`installer/JellyRip.iss`) targeting per-user install at `%LOCALAPPDATA%\Programs\JellyRip`.
- Added `build_installer.bat` to build both `JellyRip.exe` and `JellyRipInstaller.exe`.

## [1.0.5] - 2026-03-25

### Critical bug fixes

- **Fixed Movie/Unattended mode deadlock**: Movie and Unattended buttons now work without freezing. Moved mode-picker logic from main thread to background thread to prevent tkinter callback deadlock during dialog prompts.
- **Fixed log file path handling**: Log file paths without `.txt` extension are now automatically suffixed to prevent "Permission denied" errors on Windows.
- **Enhanced analysis error handling**: Added explicit logging of analysis results and exception handling to help debug silent failures during file analysis.
- **Fixed abort during mode picker starting task**: Pressing Abort while the "Movie/Unattended mode?" prompt is showing no longer starts the rip — it now cancels cleanly.

### Features

- **Smart Rip now asks to keep extras**: After auto-selecting the main feature, Smart Rip now asks "Keep extras from this disc?" and rips/moves all additional titles to the Extras folder if yes.

### UI/UX improvements

- Better error messages when file analysis fails, with option to retry instead of silently skipping.

## [1.0.4] - 2026-03-25

### Reliability and parsing hardening

- Hardened duration parsing so malformed values safely default to 0.
- Hardened size parsing to tolerate variants like 3.7GB, 3,7 GB, and trailing text.
- Added safe dictionary access for optional audio and subtitle track lists in scoring/logging paths.

### Ripping and process stability

- Kept rip success based on MakeMKV exit code while preserving fallback behavior when files are actually produced on non-zero exits.
- Maintained abort-safe process handling with local subprocess snapshot usage.
- Added extra guardrails for destination path race conditions during atomic move.

### Observability and diagnostics

- Added optional safe_int debug warnings (de-duplicated and throttled; off by default).
- Added optional malformed-duration debug warnings (de-duplicated and throttled; off by default).
- Expanded score visibility with explicit score breakdown and ambiguity warning when top candidates are close.

### Testing and docs

- Added printable live-rip pass/fail worksheet for testers: TESTERS.md.
- Updated README links so testers can find worksheet and issue reporting flow quickly.
