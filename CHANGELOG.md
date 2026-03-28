# Changelog

## [Unreleased]

### Correctness hardening

- Eliminated duplicate ffprobe analysis passes in TV/Movie disc (`_run_disc`) and Smart Rip (`run_smart_rip`) pipelines. `analyze_files()` result is now shared with `_verify_container_integrity()` via a new `analyzed=` parameter — each file is probed exactly once per pipeline step.
- Fixed `run_smart_rip` state machine: `STABILIZED` transition was missing on the normal (non-retry) path; `VALIDATED` transition was dead code (placed after an unconditional `return`). Both are now correctly placed on the success path.
- Fixed `run_organize()` path drift: removed early `cfg["tv_folder"]` / `cfg["movies_folder"]` / `cfg["temp_folder"]` reads that silently bypassed run-time path overrides. All three folder roots now derive exclusively from `get_path()` after `_init_session_paths()`.
- Added `_ensure_session_paths()` guard: raises `RuntimeError` immediately if `session_paths` has not been initialized, making misconfigured calls fail loudly rather than silently writing to the wrong folder.
- Cleaned up post-stabilization size advisory log to use the format: `X MB (below threshold — expected Y GB → threshold Z GB)`.

### Tests

- Added 7 regression tests covering `_ensure_session_paths`, `_verify_container_integrity` with and without pre-analyzed data, integrity failure cases (zero duration, count mismatch), and advisory log format.

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
