# JellyRip v1.0.16 Release Notes

## Release Channel

Unstable pre-release.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.16/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.16/JellyRipInstaller.exe)
- Release page: [v1.0.16 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.16)
- All releases: [GitHub Releases](https://github.com/unexpear/JellyRip/releases)

## What's New in 1.0.16

### FFmpeg and transcode reliability

- Improved FFmpeg abort handling so queued work shuts down more cleanly.
- Expanded copy-progress logging and transcode validation around FFmpeg workflows.

### Release bundling and packaging

- Bundled FFmpeg runtime assets and notices more intentionally for packaged releases.
- Restored the richer PyInstaller spec so release builds carry version metadata and bundled runtime dependencies consistently.

### Release hygiene

- Release metadata now aligns on the `1.0.16` line across the app, installer, docs, and release notes.
- Build output remains a GitHub Releases artifact instead of a tracked repository binary.
- In-app update checks now follow the newest published release, including unstable prereleases.
