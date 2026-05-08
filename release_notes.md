# JellyRip v1.0.21 Release Notes

JellyRip v1.0.21 — audit-driven cleanup.  Adds a configurable
drive-probe retry count, picks the 64-bit MakeMKV binary on x64
Windows, and trims a stale empty file from the bundle.  Engine
behavior under default settings is unchanged from v1.0.20 — every
new option falls back to the prior hardcoded value.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.21/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.21/JellyRipInstaller.exe)
- Release page: [v1.0.21 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.21)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)

## What's New in 1.0.21

### Engine

- **Drive-probe retries are now config-driven.**
  Two new options in `DEFAULTS`:
  - `opt_drive_probe_retries` (default 3) — number of retries before
    giving up if the drive isn't ready.
  - `opt_drive_probe_backoff_seconds` (default 2.0) — base delay
    between retries; exponential, capped at 8s.

  Users with slow trays can bump these without code changes.
  Default behavior matches the prior hardcoded 3-retries-with-2-4-8
  backoff exactly.

- **64-bit MakeMKV binary preferred on x64 Windows.**
  `_DEFAULT_MAKEMKVCON` now picks `makemkvcon64.exe` when
  `ProgramW6432` is set (i.e., 64-bit Windows host).  Matches the
  64-bit Python + Qt runtime PyInstaller bundles; avoids the rare
  mixed-bitness "process suspended" hang.  Falls back to
  `makemkvcon.exe` on 32-bit Windows or non-Windows.

### Bundle / repo

- **Removed `gui_qt/qss/warm.qss`** (empty 0-byte placeholder from
  the early 3-theme design exploration).  Was filtered at load time
  but still shipping into the bundle.
- **`pyproject.toml` keywords** — dropped `tkinter` (retired in
  v1.0.19), added `pyside6` + `qt`.

### Documentation

- README "shipped path as of v1.0.0" → "since v1.0.19" (the
  Qt-only milestone).

### What's NOT in this release

No user-facing UI changes.  No workflow changes.  Engine behavior
under default settings is byte-identical to v1.0.20.

## Companion fork: JellyRip AI

- AI release page: [ai-v1.0.21 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.21)
- AI project site: [unexpear-softwhere.github.io/JellyRipAI](https://unexpear-softwhere.github.io/JellyRipAI/)
