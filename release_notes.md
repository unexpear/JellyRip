# JellyRip v1.0.10 Release Notes

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.10/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.10/JellyRipInstaller.exe)
- Release page: [v1.0.10 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.10)
- All releases: [GitHub Releases](https://github.com/unexpear/JellyRip/releases)

## What's New in 1.0.10

### Tool discovery and validation

- Unified tool resolver for MakeMKV and ffprobe: checks saved config → common install paths → PATH environment variable.
- `validate_makemkvcon` and `validate_ffprobe` run a real probe command before accepting a tool path.
- Settings save now refuses to overwrite a working tool path with an unvalidated replacement.
- Engine `validate_tools` routes both dependencies through the resolver layer so PATH-only installs and custom locations are found automatically.

### Multi-disc and extras workflow

- Multi-disc dump mode renamed from "Unattended" to "Dump All" in UI labels and logs.
- Multi-disc dump flow now pauses with an explicit between-disc confirmation prompt (no default timeout).
- Unrecognized discs during multi-disc dump can now be bypassed or stopped instead of retry-only.
- Extras selection changed from yes/no keep-all to a multi-select picker for individual titles.
- Configurable prompt auto-timeouts and disc-swap timeouts in Settings → Advanced.

### Settings crash hardening

- Settings open callback is now wrapped in a safety handler so an exception during settings initialization shows an error dialog instead of crashing the app.

### Project and documentation

- Added `CONTRIBUTING.md`, `SECURITY.md`, `pyproject.toml`, and a GitHub Actions CI workflow.
- Added `docs/architecture.md` and `docs/repository-layout.md`.
- Version strings synchronized across `shared/runtime.py`, `pyproject.toml`, `installer/JellyRip.iss`, and CHANGELOG.
- Fixed Unicode mojibake in controller (corrupted arrow character).

## Previous versions

Full changelog: [CHANGELOG.md](https://github.com/unexpear/JellyRip/blob/main/CHANGELOG.md)

Build note: the repository tracks source and installer metadata; generated `dist/` binaries are published as release assets and are not committed to git.
