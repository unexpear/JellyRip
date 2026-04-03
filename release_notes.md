# JellyRip v1.0.11 Release Notes

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.11/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.11/JellyRipInstaller.exe)
- Release page: [v1.0.11 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.11)
- All releases: [GitHub Releases](https://github.com/unexpear/JellyRip/releases)

## What's New in 1.0.11

### Disc-level metadata (CINFO parsing)

- Scan now extracts disc title, language code, language name, and volume ID from MakeMKV `CINFO:` output.
- `build_fallback_title()` prefers CINFO disc name over per-title TINFO name when the disc name is available and non-generic.

### MakeMKV `--minlength` filter

- New setting: minimum title length in seconds (Settings → Advanced → MakeMKV, default off).
- Titles shorter than the threshold are excluded during scan, reducing noise from menus and trailers.

### Jellyfin metadata ID support

- Smart Rip, Manual Disc, and Organize flows now prompt for an optional TMDB/IMDB/TVDB ID.
- Folder names get Jellyfin-compatible tags like `Movie (2024) [tmdbid-12345]` or `Show [tvdbid-79168]`.
- `parse_metadata_id()` accepts flexible input: `tmdb:12345`, `tmdb-12345`, `tt1234567`, `tvdb:79168`, or bare integers (assumed TMDB).
- Centralized via `build_movie_folder_name()` and `build_tv_folder_name()`.

### Build and encoding fixes

- Fixed 73 mojibake em dashes in controller.py (triple-encoded UTF-8 bytes replaced with proper U+2014).
- 34 new tests for the naming module (180 total passing).

## Previous versions

Full changelog: [CHANGELOG.md](https://github.com/unexpear/JellyRip/blob/main/CHANGELOG.md)

Build note: the repository tracks source and installer metadata; generated `dist/` binaries are published as release assets and are not committed to git.
