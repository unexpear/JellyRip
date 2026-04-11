# JellyRip v1.0.15 Release Notes

## Release Channel

Unstable pre-release.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.15/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.15/JellyRipInstaller.exe)
- Release page: [v1.0.15 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.15)
- All releases: [GitHub Releases](https://github.com/unexpear/JellyRip/releases)

## What's New in 1.0.15

### Hotfix

- Restored a visible top-level `ABORT SESSION` button so abort is available during running tasks even when no inline prompt is open.
- Fixed log auto-follow behavior so the log continues to scroll when the user was already at the bottom.

### Testability

- The full test suite still covers 250 checks.
- A live Tk smoke check verified the Abort button is outside the hidden prompt bar and toggles state correctly.
