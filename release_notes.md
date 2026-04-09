# JellyRip v1.0.13 Release Notes

## Release Channel

Unstable pre-release.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.13/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.13/JellyRipInstaller.exe)
- Release page: [v1.0.13 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.13)
- All releases: [GitHub Releases](https://github.com/unexpear/JellyRip/releases)

## What's New in 1.0.13

### FFmpeg Source Handling

- New `Safe (Copy First)` mode copies the source MKV to a temporary working file before FFmpeg starts.
- New `Fast (Read Original)` mode reads the original MKV directly while still writing a separate output file.
- The UI now explains both options in plain language in Settings and in the transcode queue builder.

### Release Cleanup

- The working release line is now cleanly aligned to `1.0.13`, with `1.0.12` treated as the previous revision point in git history.
- Release metadata files are synced so the README, installer, release notes, and release script all point at the same version.

### Build Polish

- `JellyRip.exe` now includes Windows file and product version metadata for a cleaner Explorer/version-info experience.
- Release consistency coverage remains in place so future version bumps are easier to verify.
