# JellyRip AI v1.0.19 Release Notes

This file is the **AI-fork** release notes, parallel to
[release_notes.md](release_notes.md) (MAIN). It exists in MAIN so the
two forks can co-author the messaging without divergence; AI BRANCH
ships its own copy when its release lands.

## Release Channel

Unstable pre-release.
Close to stable, but still lightly tested.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear-softwhere/JellyRipAI/releases/download/v1.0.19/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear-softwhere/JellyRipAI/releases/download/v1.0.19/JellyRipInstaller.exe)
- Release page: [v1.0.19 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/v1.0.19)
- All releases: [GitHub Releases](https://github.com/unexpear-softwhere/JellyRipAI/releases)

## What This Fork Adds

JellyRip AI extends the [MAIN](https://github.com/unexpear/JellyRip)
disc-ripping pipeline with assistive features:

- **Chat sidebar** — ask the assistant about a disc you're ripping,
  what to do with an ambiguous title, or how a config option behaves.
- **AI provider configuration** — pick a provider, paste an API key,
  pick a model.
- **Identity assist** — confidence sliders, alternate suggestions,
  and undo on the classifier's per-title decisions.
- **Workflow history** — chat context persists across sessions.

The disc-ripping pipeline itself (MakeMKV, ffprobe, the workflows,
the validation, the move-into-Jellyfin layout) is exactly MAIN's. The
fork's value is the assistive layer on top.

## What's New in 1.0.19

AI BRANCH absorbs the engine-level fixes from MAIN's 1.0.19 release.
The Qt UI changes from MAIN are **not** in this AI BRANCH release —
they ship when Phase 4 closes (see *What's Coming Next* below).

### Live progress that actually moves

- MakeMKV runs with `-r` (robot mode) on every invocation, so the
  engine sees the machine-readable progress events it needs to
  parse. Previously a rip that was actually running could look
  hung in the GUI for 20–60 minutes.
- The engine's `run_job` now forwards GUI hooks (`on_log`,
  `on_progress`) all the way down to the rip subprocess, so the
  live log and progress bar stay updated for the whole rip.

### Friendlier error surfaces

- Workflow buttons now run a tool-path pre-flight before launching.
  A missing or moved `makemkvcon` / `ffprobe` produces a clear
  "Required Tool Not Found" dialog with the path-suggestion text
  instead of a cryptic `[Errno 2] No such file or directory`.
- A user-cancelled session no longer reports "completed
  successfully" in the done dialog. The session state machine has
  a real cancel class with a `was_cancelled` flag and a `cancel(reason)`
  helper.

### Disk-space pre-check robustness

- `shutil.disk_usage` raising `OSError` (offline network share,
  vanished mount point) now degrades to a logged warning rather
  than crashing the workflow. Better to proceed without a pre-flight
  and let MakeMKV catch a real ENOSPC than to refuse the rip on a
  broken pre-check.

### Release hygiene

- Release metadata aligns on the `1.0.19` line across the app,
  installer, docs, tester worksheet, and release notes.
- AI BRANCH builds stage `JellyRip.exe`, `JellyRipInstaller.exe`,
  bundled FFmpeg binaries, and notice files under `dist/main` (same
  layout as MAIN).

## What's Coming Next

The headline upgrade for the next AI BRANCH release will be the
**PySide6 (Qt) UI port**, mirroring MAIN's Qt-only milestone:

- `QTextBrowser`-rendered chat sidebar with native markdown and
  code-block formatting (vs the current tkinter `Text`-widget
  literal rendering).
- Native streaming response animation via Qt signals (no more
  `after()` polling).
- Same six switchable themes as MAIN (`dark_github`,
  `light_inverted`, `dracula_light`, `hc_dark`, `slate`, `frost`).
- Right-click MKV preview before commit, the v1-blocking feature
  shipped on MAIN.
- Friendly `Required Tool Not Found` dialog instead of the cryptic
  `[Errno 2]` message when MakeMKV or ffprobe is missing.
- Tray icon, splash screen, status-bar progress, log-line severity
  glyphs (`⚠` warn, `✗` error), drive-state glyphs (`◉ / ⊚ / ◌`).

The Qt port is gated on MAIN's PySide6 release proving stable in
the wild (which it now has — see
[smoke-report-2026-05-04.md](docs/smoke-report-2026-05-04.md) for
the v1.0 acceptance smoke). The handoff brief for the AI BRANCH
port lives at
[docs/handoffs/phase-4-ai-branch-port.md](docs/handoffs/phase-4-ai-branch-port.md).

## Compatibility Notes

- Config files port forward unchanged. The chat history file
  (`workflow_history.json`) and AI provider settings stay readable
  across upgrades.
- The Anthropic SDK is a runtime dependency on the AI fork only —
  installing JellyRip AI from source pulls it via the fork's
  `requirements.txt`. The MAIN binary does not include it.
- Both forks share the same MakeMKV / ffprobe path resolution, the
  same registry lookup, the same Jellyfin-friendly output layout.
  Move between forks without reconfiguring tool paths.
