# JellyRip v1.0.24 Release Notes

JellyRip v1.0.24 — a large bug-fix + packaging release driven by a
full-codebase review: a working Stop button, a data-loss fix, Organize
repairs, a new theme system with a Theme Maker, and a new app format.

## DOWNLOAD FORMAT CHANGED

The standalone download is now **JellyRip-portable.zip** (a folder you
unzip and run) instead of a single `JellyRip.exe`. The app now starts
instantly — the old single-exe format unpacked ~600 MB to your temp
folder on every launch. If you previously downloaded the bare exe,
grab the portable zip or the installer this time.

## Download

- Portable: [JellyRip-portable.zip](https://github.com/unexpear/JellyRip/releases/download/v1.0.24/JellyRip-portable.zip)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.24/JellyRipInstaller.exe)
- Release page: [v1.0.24 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.24)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)

## Highlights

### Packaging

- **One-DIR app format**: instant launches, nothing written to %TEMP%,
  no leftover `_MEI` folders after crashes. FFmpeg ships once (inside
  `_internal\`); the installer shrinks to ~150 MB and cleans up the old
  staged FFmpeg on upgrade. Unused `ffplay.exe` dropped (~130 MB).

### Critical fixes

- **Stop Session works** — the button was never enabled by production
  code, so a 90-minute rip had no abort.
- **Stopping a multi-disc Dump All no longer deletes the most recently
  completed disc's files.**
- **Organize Existing MKVs**: real season numbers (was hardcoded S00,
  which Jellyfin shelves as Specials), separator-safe auto-delete (no
  more sibling-folder hazard), honest verdict on failed moves.

### Engine

- MakeMKV output decoded as **UTF-8** — non-ASCII disc titles no longer
  mojibake into filenames or kill the scan/rip reader.
- **Progress bar** tracks the whole rip (PRGV total/max) instead of
  running ahead and sawtoothing; the ETA is real.
- Moves **validate the staged copy before it takes the final library
  name**; failed non-atomic moves are quarantined; truncated "degraded"
  rips are rejected against the scanned title size.
- **Title-file mapping works for labeled discs**, enabling per-file
  integrity expectations on every disc.

### Themes

- **New token-based theme system with a Theme Maker** — live full-app
  preview, save, export to a shareable `.json`, import.
- **9 new built-in themes** (15 total): Monokai, Rosé Pine, Tokyo
  Night, Catppuccin Mocha, Everforest Dark, Synthwave, Ayu Mirage,
  IBM Carbon, Palenight.

### Quality of life

- Title-bar ✕ on Settings / MKV preview behaves like Cancel.
- Crashes write a readable `crash.log` next to `config.json`.
- Updater: the signature check actually runs; truncated downloads are
  detected. Blank log path no longer creates a junk `..txt` file.

## What's NOT in this release

FFmpeg/HandBrake transcoding remains unwired in the UI (its builder
got real fixes — AMD/Intel GPU support, correct GPU quality flags —
ready for when it lands).

## Companion fork: JellyRip AI

The AI fork ships an assistant layer (chat sidebar + AI provider
integrations + TMDB/OMDb disc auto-identification) on top of the same
disc-ripping core.

- AI release page: [ai-v1.0.24 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.24)
- AI project site: [unexpear-softwhere.github.io/JellyRipAI](https://unexpear-softwhere.github.io/JellyRipAI/)
