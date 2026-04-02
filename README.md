# JellyRip

JellyRip is a Windows-first desktop app that uses MakeMKV and ffprobe to rip discs, validate output, and organize media into a Jellyfin-friendly library structure.

The project is currently pre-alpha. The codebase is actively tested and being hardened, but live disc workflows can still change quickly and should be treated as non-final.

## Project Status

- Current stable line: `v1.0.9` (latest published release)
- Platform target: Windows
- Runtime target: Python 3.13+
- Distribution target: standalone `JellyRip.exe` and optional installer
- Quality target: practical and safe for testing, not yet stable enough to treat as finished software

## What JellyRip Does

- rips movie and TV discs with MakeMKV
- validates outputs with ffprobe and file stabilization checks
- organizes files into Jellyfin-style movie and TV folder structures
- supports interactive, unattended, and smart-rip workflows
- keeps session logs and end-of-run warning summaries

## Quick Start

### From GitHub release (recommended, currently `v1.0.9`)

1. Download the exe: [JellyRip.exe latest](https://github.com/unexpear/JellyRip/releases/latest/download/JellyRip.exe)
2. If you want the installer build, open [latest release assets](https://github.com/unexpear/JellyRip/releases/latest) and download the installer from that page.
3. If SmartScreen/Defender flags the file, whitelist the download folder first (common PyInstaller false positive).

### From source (git clone)

```bash
git clone https://github.com/unexpear/JellyRip.git
cd JellyRip
pip install -r requirements.txt
python main.py
```

First launch tip: open **Settings** and confirm MakeMKV and ffprobe paths before the first rip.

## Requirements

- Windows
- MakeMKV
- ffprobe from HandBrake or ffmpeg
- optical drive for live ripping

## Main Workflows

- **TV Disc**: interactive disc ripping with episode-oriented organization
- **Movie Disc**: interactive movie ripping with metadata prompts
- **Smart Rip**: auto-pick the best main feature
- **Dump All**: raw dump mode for all titles
- **Organize Existing MKVs**: move and sort already-ripped files
- **Unattended Modes**: operator-assisted multi-disc flows with blocking confirmations and safety checks

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
pyinstaller --onefile --windowed --name JellyRip main.py
```

### Executable plus installer

```bash
build_installer.bat
```

Expected outputs:

- `dist/JellyRip.exe`
- `dist/JellyRipInstaller.exe`

Build output is intentionally git-ignored and should be published through GitHub Releases rather than committed to the repository.

## Support and Reporting

- Issues: [GitHub Issues](https://github.com/unexpear/JellyRip/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Release post text: [release_notes.md](release_notes.md)
- Tester worksheet: [TESTERS.md](TESTERS.md)

If Windows Defender flags the executable, whitelist the download folder before retrying. This is a known false-positive pattern for PyInstaller-built Windows executables.

## License

See [LICENSE](LICENSE).
