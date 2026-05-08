# JellyRip v1.0.20 Release Notes

JellyRip v1.0.20 — repository hygiene + GitHub Pages landing page.
This is a documentation/cleanup release; the bundled `JellyRip.exe`
is functionally identical to v1.0.19.  Upgrade for the public docs
site and the cleaner tracked tree, not for any new ripping behavior.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.20/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.20/JellyRipInstaller.exe)
- Release page: [v1.0.20 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.20)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)

## What's New in 1.0.20

### Documentation

- GitHub Pages site published at
  [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)
  with a download landing page, project-info links, and an in-site
  documentation TOC.  Cayman theme, source = `main` branch / `docs/`
  folder.  Internal phase handoffs, smoke reports, code-signing
  drafts, and design-system source files stay tracked but are
  excluded from the public site via `docs/_config.yml`.

### Repository hygiene

- `dashboard.html` (Claude productivity dashboard) untracked from
  the repo — local-only tooling that was inadvertently still tracked
  alongside the gitignored `CLAUDE.md`.  Kept locally and gitignored.
- `ui_visual_assets_copy/` untracked from the repo — ~4700 lines of
  retired tkinter UI snapshot mirroring the live `gui_qt/` tree, with
  live `import tkinter` statements.  Kept locally and gitignored.
- `release_notes_ai.{md,txt}` deleted — drift'd duplicates of the AI
  fork's own release notes.  The AI fork now maintains its own.

### What's NOT in this release

No code or behavior changes.  The bundled MakeMKV invocation,
ffprobe validation, library organization, and all UI workflows are
byte-identical to v1.0.19.

## Companion fork: JellyRip AI

The AI fork ships an assistant layer (chat sidebar + AI provider
integrations) on top of the same disc-ripping core.

- AI release page: [ai-v1.0.20 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.20)
- AI project site: [unexpear-softwhere.github.io/JellyRipAI](https://unexpear-softwhere.github.io/JellyRipAI/)
