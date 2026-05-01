# JellyRip

JellyRip is a Windows-first desktop app that uses MakeMKV and ffprobe
to rip discs, validate output, and organize media into a
Jellyfin-friendly library structure.

The project is currently pre-alpha. The codebase is actively tested and
being hardened, but live disc workflows can still change quickly and
should be treated as non-final.

## Project Status

- Current unstable line: `v1.0.18` (latest unstable pre-release)
- MAIN release page: [v1.0.18](https://github.com/unexpear/JellyRip/releases/tag/v1.0.18)
- AI release page: [ai-v1.0.18](https://github.com/unexpear/JellyRip/releases/tag/ai-v1.0.18)
- Platform target: Windows
- Runtime target: Python 3.13+
- Distribution target: standalone `JellyRip.exe` and optional installer
- Quality target: practical and safe for testing,
  not yet stable enough to treat as finished software

## What JellyRip Does

- rips movie and TV discs with MakeMKV
- validates outputs with ffprobe and file stabilization checks
- organizes files into Jellyfin-style movie and TV folder structures
- supports interactive, semi-unattended, and smart-rip workflows
- keeps session logs and end-of-run warning summaries

## Quick Start

### From GitHub release

(recommended, currently `v1.0.18` unstable pre-release)

1. Go to the [current unstable release page](https://github.com/unexpear/JellyRip/releases/tag/v1.0.18).
2. Download `JellyRipInstaller.exe` (installer) or `JellyRip.exe` (standalone).
3. If SmartScreen/Defender flags the file, whitelist the download folder
  first (common PyInstaller false positive).
4. Run and open **Settings** to confirm MakeMKV and ffprobe paths before first rip.

### From source (git clone)

```bash
git clone https://github.com/unexpear/JellyRip.git
cd JellyRip
pip install -r requirements.txt
python main.py
```

First launch tip: open **Settings** and confirm MakeMKV and ffprobe
paths before the first rip.

## Requirements

- Windows
- MakeMKV
- FFmpeg (`ffmpeg` and `ffprobe`) for source runs; release builds bundle
  the GPLv3 Gyan full build
- optical drive for live ripping

## Main Workflows

- **TV Disc**: interactive disc ripping with episode-oriented organization(some testing)
- **Movie Disc**: interactive movie ripping with metadata prompts(some testing)
- **Dump All**: raw dump mode for all titles(some testing)
- **Organize Existing MKVs**: move and sort already-ripped files( not tested )
- **Prep for and use FFmpeg or handbrake**: simple transcoding( not tested )

## Configuration

Settings are stored at `%APPDATA%\JellyRip\config.json` on Windows.

You can configure:

- MakeMKV and ffprobe paths
- optional FFmpeg and HandBrakeCLI executable paths
- temp, movie, and TV folders
- retry behavior and quiet/stall warnings
- file stabilization and validation thresholds
- unattended prompt and disc-swap timeout behavior
- update-signature settings
- debug logging options

Windows tool lookup is strict by default. JellyRip prefers explicit
configured paths, bundled binaries, and known install locations.
PATH-based lookup is disabled unless you enable
`Allow PATH-based tool lookup (advanced, less predictable)` in
**Settings -> Advanced**.

App-directory `.env` files are no longer loaded at startup.

## Development

### Repository layout

- [main.py](main.py) - primary entrypoint
- [JellyRip.py](JellyRip.py) - compatibility entrypoint and project map
- [gui](gui) - tkinter UI layer
- [controller](controller) - workflow orchestration
- [engine](engine) - MakeMKV, ffprobe, and file operations
- [utils](utils) - helper modules
- [shared](shared) - shared runtime defaults and constants
- [tools/ui_sandbox_launcher.py](tools/ui_sandbox_launcher.py) - UI-only sandbox launcher for exercising flows without disc hardware or external tools
- [tests](tests) - automated regression coverage
- [docs/architecture.md](docs/architecture.md) - architecture overview
- [docs/repository-layout.md](docs/repository-layout.md) - repository layout rationale

### Testing

```bash
python -m pytest -q
```

For manual UI flow checks without MakeMKV, ffprobe, or disc hardware:

```bash
python tools/ui_sandbox_launcher.py
```

Manual live-rip validation worksheet:

- [TESTERS.md](TESTERS.md)

Contribution and security guidance:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [docs/branch-workflow.md](docs/branch-workflow.md)
- [SECURITY.md](SECURITY.md)

## Building Releases

### Standalone executable

```bash
build.bat
```

The MAIN build scripts place standalone build artifacts under `dist\main`.
`build.bat` wraps `pyinstaller JellyRip.spec` with the MAIN artifact and
work directories preconfigured.
The spec bundles the Gyan FFmpeg full build (`ffmpeg.exe`, `ffprobe.exe`,
and `ffplay.exe`). Put the extracted build under `.\ffmpeg\` or `..\ffmpeg\`,
or set `JELLYRIP_FFMPEG_DIR` before building. Release builds must also ship
`FFmpeg-LICENSE.txt` and `FFmpeg-README.txt`.

### Executable plus installer

```bash
build_installer.bat
```

Commercial installer builds require an appropriate Inno Setup license.

Expected outputs:

- `dist/main/JellyRip.exe`
- `dist/main/JellyRipInstaller.exe`
- `dist\main\ffmpeg.exe`, `dist\main\ffprobe.exe`, and `dist\main\ffplay.exe`
- `dist\main\FFmpeg-LICENSE.txt` and `dist\main\FFmpeg-README.txt`

Build output is intentionally git-ignored and should be published
through GitHub Releases rather than committed to the repository.

### Full release pipeline

```bash
release.bat 1.0.18
```

This runs tests, checks version consistency, builds both executables,
pushes code, and publishes a GitHub release with assets attached in the
correct order. It also refuses to run from a dirty working tree or a
branch other than `main`. Never create a release without assets.

## Support and Reporting

- Issues: [GitHub Issues](https://github.com/unexpear/JellyRip/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Release post text: [release_notes.txt](release_notes.txt)
- Readable release notes: [release_notes.md](release_notes.md)
- Tester worksheet: [TESTERS.md](TESTERS.md)

If Windows Defender flags the executable, whitelist the download folder
before retrying. This is a known false-positive pattern for
PyInstaller-built Windows executables.

## License

JellyRip is licensed under GPLv3. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
