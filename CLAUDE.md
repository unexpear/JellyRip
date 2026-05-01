# JellyRip — Working Memory

## Project
Windows-first desktop app: rips discs with MakeMKV, validates with ffprobe, organizes into a Jellyfin-friendly library. Pre-alpha, current line `v1.0.18`. Python 3.13+, tkinter UI, distributed as `JellyRip.exe` (+ optional installer).

Owner: GitHub `unexpear`. License: GPLv3.

## Layout
- `main.py` — entrypoint
- `gui/` — tkinter UI
- `ui/` — UI adapters / dialogs / settings
- `controller/` — workflow orchestration, session lifecycle
- `core/` — pipeline + media scan
- `engine/` — MakeMKV, ffprobe, file ops (rip_ops, scan_ops, ripper_engine)
- `transcode/` — ffmpeg/HandBrake planning, queue, recommendations
- `utils/` — helpers, parsing, classifier, updater, state machine
- `shared/` — runtime, events, windows_exec, ai_diagnostics
- `tests/` — pytest suite
- `config.py` — settings
- `docs/architecture.md`, `docs/repository-layout.md`, `FEATURE_MAP.md`

## Workflow status (per README)
- TV Disc, Movie Disc, Dump All — some testing
- Organize Existing MKVs — not tested
- FFmpeg / HandBrake transcoding — not tested

## Quality bar
- `python -m pytest` — currently 565 tests, ~52s, all passing
- `pyright` strict mode — 8292 errors at baseline (mostly missing annotations, not real bugs); use as a *trend*, not a gate
- `release.bat <version>` is the full release pipeline; refuses dirty tree or non-`main` branch

## Conventions
- Windows-first; bash via Git Bash, PowerShell available
- Explicit binary paths preferred; PATH lookup is opt-in via Settings → Advanced
- Config at `%APPDATA%\JellyRip\config.json`
- Build artifacts under `dist/main/`, git-ignored

## Working preferences
- **Local writes are fine; no git updates without explicit go-ahead.** Don't commit, push, tag, or run `release.bat` unless I say so. Editing files locally is OK.
- **No git worktrees.** Work directly in this directory. Do not create extra worktrees, and if a `.claude/worktrees/<name>` folder appears, remove it. From the repository root:
  ```bash
  git worktree remove --force .claude/worktrees/<name>
  git branch -D claude/<name>
  ```
  If files are locked because another session has them open, close that session and remove any leftover folder with `Remove-Item -Recurse -Force .claude/worktrees/<name>` from PowerShell. `.claude/worktrees/` is in `.gitignore` so accidental appearances will not be committed.

## Current focus
(empty — update as we work)
