# JellyRip v1.0.14 Release Notes

## Release Channel

Unstable pre-release.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.14/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.14/JellyRipInstaller.exe)
- Release page: [v1.0.14 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.14)
- All releases: [GitHub Releases](https://github.com/unexpear/JellyRip/releases)

## What's New in 1.0.14

### Controller Boundary Cleanup

- Session path setup and validation now live in a plain controller helper module.
- Rip validation, size sanity checks, ffprobe integrity checks, and the one-shot retry policy now live outside the legacy controller mixin.
- Session recovery helpers now own resume prompt modeling, selected-title restoration, and failed-session metadata/wipe behavior.
- TV library scanning helpers now own episode filename parsing, Season 00/Specials detection, and highest-episode lookup.

### Testability

- New direct unit tests cover the extracted controller helper modules without importing Tk.
- The full test suite now covers 250 checks.

### Release Hygiene

- Release consistency coverage now checks version alignment across the repo.
- The root `JellyRip.exe` release binary is guarded against being tracked in git.
