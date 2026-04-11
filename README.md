# JellyRip

JellyRip is a Windows-first desktop app that uses MakeMKV and ffprobe
to rip discs, validate output, and organize media into a
Jellyfin-friendly library structure.

The project is currently pre-alpha. The codebase is actively tested and
being hardened, but live disc workflows can still change quickly and
should be treated as non-final.

## Project Status

- Current unstable line: `v1.0.15` (next unstable pre-release)
- Platform target: Windows
- Runtime target: Python 3.13+
- Distribution target: standalone `JellyRip.exe` and optional installer
- Quality target: practical and safe for testing,
  not yet stable enough to treat as finished software

## What JellyRip Does

- rips movie and TV discs with MakeMKV
- validates outputs with ffprobe and file stabilization checks
- organizes files into Jellyfin-style movie and TV folder structures
- supports interactive, unattended, and smart-rip workflows
- keeps session logs and end-of-run warning summaries

## Quick Start

### From GitHub release

(recommended, currently `v1.0.15` unstable pre-release)

1. Go to the [latest release page](https://github.com/unexpear/JellyRip/releases/latest).
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
- ffprobe (from ffmpeg)
- optical drive for live ripping

## Main Workflows

- **TV Disc**: interactive disc ripping with episode-oriented organization
- **Movie Disc**: interactive movie ripping with metadata prompts
- **Smart Rip**: auto-pick the best main feature
- **Dump All**: raw dump mode for all titles
- **Organize Existing MKVs**: move and sort already-ripped files
- **Unattended Modes**: operator-assisted multi-disc flows with
  blocking confirmations and safety checks

## Configuration

Settings are stored at `%APPDATA%\JellyRip\config.json` on Windows.

You can configure:

- MakeMKV and ffprobe paths
- temp, movie, and TV folders
- retry behavior and quiet/stall warnings
- file stabilization and validation thresholds
- unattended prompt and disc-swap timeout behavior
- update-signature settings
- debug logging options

## Development

### Repository layout

- [main.py](main.py) - primary entrypoint
- [JellyRip.py](JellyRip.py) - compatibility entrypoint and project map
- [gui](gui) - tkinter UI layer
- [controller](controller) - workflow orchestration
- [engine](engine) - MakeMKV, ffprobe, and file operations
- [utils](utils) - helper modules
- [shared](shared) - shared runtime defaults and constants
- [tests](tests) - automated regression coverage
- [docs/architecture.md](docs/architecture.md) - architecture overview
- [docs/repository-layout.md](docs/repository-layout.md) - repository layout rationale

### Testing

```bash
python -m pytest -q
```

Manual live-rip validation worksheet:

- [TESTERS.md](TESTERS.md)

Contribution and security guidance:

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)

## Building Releases

### Standalone executable

```bash
pip install pyinstaller
pyinstaller JellyRip.spec
```

The spec bundles `ffmpeg.exe`, `ffprobe.exe`, and `ffplay.exe`. Put an
extracted FFmpeg build under `.\ffmpeg\` or `..\ffmpeg\`, or set
`JELLYRIP_FFMPEG_DIR` before building.

### Executable plus installer

```bash
build_installer.bat
```

Expected outputs:

- `dist/JellyRip.exe`
- `dist/JellyRipInstaller.exe`

Build output is intentionally git-ignored and should be published
through GitHub Releases rather than committed to the repository.

### Full release pipeline

```bash
release.bat 1.0.15
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

See [LICENSE](LICENSE).
