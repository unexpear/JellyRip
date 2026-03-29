# Changelog

## [1.0.8] - 2026-03-28

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

### Tests

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

### Tests

- Added 7 regression tests covering `_ensure_session_paths`, `_verify_container_integrity` with and without pre-analyzed data, integrity failure cases (zero duration, count mismatch), and advisory log format.
- Added 4 regression tests for degraded rip classification: degraded success path, real failure path (no files), session report population, and session summary warnings vs. clean success branching.

## 1.0.6 - 2026-03-27

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

## 1.0.5 - 2026-03-25

### Critical bug fixes

- **Fixed Movie/Unattended mode deadlock**: Movie and Unattended buttons now work without freezing. Moved mode-picker logic from main thread to background thread to prevent tkinter callback deadlock during dialog prompts.
- **Fixed log file path handling**: Log file paths without `.txt` extension are now automatically suffixed to prevent "Permission denied" errors on Windows.
- **Enhanced analysis error handling**: Added explicit logging of analysis results and exception handling to help debug silent failures during file analysis.
- **Fixed abort during mode picker starting task**: Pressing Abort while the "Movie/Unattended mode?" prompt is showing no longer starts the rip — it now cancels cleanly.

### Features

- **Smart Rip now asks to keep extras**: After auto-selecting the main feature, Smart Rip now asks "Keep extras from this disc?" and rips/moves all additional titles to the Extras folder if yes.

### UI/UX improvements

- Better error messages when file analysis fails, with option to retry instead of silently skipping.

## 1.0.4 - 2026-03-25

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
