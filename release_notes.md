# JellyRip v1.0.9 Release Notes

## Download

- Direct download (v1.0.9): [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.9/JellyRip.exe)
- Direct download (latest): [JellyRip.exe latest](https://github.com/unexpear/JellyRip/releases/latest/download/JellyRip.exe)
- Direct URL copy: https://github.com/unexpear/JellyRip/releases/download/v1.0.9/JellyRip.exe
- Release page: [v1.0.9 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.9)
- Release page URL copy: https://github.com/unexpear/JellyRip/releases/tag/v1.0.9
- Latest releases list: [all releases](https://github.com/unexpear/JellyRip/releases)
- Releases URL copy: https://github.com/unexpear/JellyRip/releases

## What's New in 1.0.9

### Safety
- `ask_yesno` now has a 300-second safety timeout and abort-event check — previously the wait loop was unbounded and could hang the app permanently if the UI missed a callback.
- `ask_input` is now serialised with a lock — concurrent prompts no longer clobber each other's result.

### Reliability
- Version number is now printed at the start of every rip session in the log (`=== JellyRip v1.0.9 — session start ===`) so old logs are unambiguous.
- `rip_selected_titles` now returns failure when individual titles fail, not just on full abort.
- Session state machine is now correctly reset and completed in the TV/movie disc flow — session summary warnings were previously silently skipped.

### Security
- Auto-update download now uses a unique temp directory per download (prevents TOCTOU path-prediction attacks).
- PowerShell signature check now uses `-LiteralPath` with a parameter block — the file path is no longer interpolated into the command string.

### Code quality (1.0.8 + 1.0.9)
- `_normalize_rip_result` now scans MKV files recursively — MakeMKV subdirectory outputs are no longer silently missed.
- `get_available_drives` now has a 30-second timeout — a stalled MakeMKV can no longer hang the app on startup.
- `check_disk_space` no longer creates directories as a side effect.
- Corrupt config file now logs a visible warning instead of silently resetting to defaults.
- All wildcard `from shared.runtime import *` replaced with explicit imports.
- `handle_fallback` simplified — duck-check `hasattr` guards removed.
- `DummyGUI` in tests now has all required stub methods.

## Previous versions

Full changelog: [CHANGELOG.md](https://github.com/unexpear/JellyRip/blob/main/CHANGELOG.md)
