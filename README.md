# JellyRip v1.0.9

MakeMKV companion for ripping and organizing discs into a Jellyfin library.

> **⚠️ Pre-Alpha Software** — The latest version is working, but TV show workflows are still untested. Expect edge-case bugs and behavior changes while development continues. Please report issues on [GitHub Issues](https://github.com/unexpear/JellyRip/issues).

Tester worksheet (printable): [TESTERS.md](TESTERS.md)
Release notes: [CHANGELOG.md](CHANGELOG.md)

Latest exe (direct): [JellyRip.exe latest](https://github.com/unexpear/JellyRip/releases/latest/download/JellyRip.exe)
Latest installer (direct): [JellyRipInstaller.exe latest](https://github.com/unexpear/JellyRip/releases/latest/download/JellyRipInstaller.exe)
Latest release page: [latest release](https://github.com/unexpear/JellyRip/releases/latest)

Quick links: [Main entry](main.py) | [Legacy entry](JellyRip.py) | [Engine](engine) | [Controller](controller) | [GUI](gui) | [Utils](utils) | [Build script](build.bat) | [Requirements](requirements.txt) | [Changelog](CHANGELOG.md) | [Release post text](release_notes.md) | [Tester sheet](TESTERS.md) | [Tests](tests)

## Quick Navigation

- Main entry: [main.py](main.py)
- Legacy entry (kept for compatibility): [JellyRip.py](JellyRip.py)
- Engine package: [engine](engine)
- Controller package: [controller](controller)
- GUI package: [gui](gui)
- Utils package: [utils](utils)
- Build script: [build.bat](build.bat)
- Requirements: [requirements.txt](requirements.txt)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Release post text: [release_notes.md](release_notes.md)
- Tester worksheet: [TESTERS.md](TESTERS.md)
- Automated tests: [tests](tests)
- Issues: [GitHub Issues](https://github.com/unexpear/JellyRip/issues)
- Downloads: [GitHub Releases](https://github.com/unexpear/JellyRip/releases)

## Project Status

- Current stable build: **v1.0.9**
- Development stage: **Pre-Alpha**
- Stability: **Highly unstable / pre-release quality**
- Testing status: **Core flows working; TV show workflows still untested**
- Maintainer experience: **New to code projects**
- Recommendation: use on non-critical discs only until stable releases return

## Installation

### Option 1: Standalone Executable (Recommended)

1. Download `JellyRip.exe` from [releases](https://github.com/unexpear/JellyRip/releases)
2. Run it directly — no installation required

Direct latest exe: [JellyRip.exe latest](https://github.com/unexpear/JellyRip/releases/latest/download/JellyRip.exe)

Installer (recommended for auto-updates): [JellyRipInstaller.exe latest](https://github.com/unexpear/JellyRip/releases/latest/download/JellyRipInstaller.exe)

Auto-update flow:

1. In JellyRip, click **Check Updates**.
2. If a newer GitHub Release exists, JellyRip downloads the installer/exe package.
3. JellyRip launches the update package and closes so Windows can replace files.

**Windows Defender False Positive?**

The exe is 100% safe (70+ antivirus vendors verified). If Windows Defender blocks it:

1. Open **Settings** → **Virus & threat protection**
2. Click **Manage settings**
3. Scroll to **Exclusions** → **Add exclusion** → **Folder**
4. Add: `C:\path\to\where\you\downloaded\JellyRip`
5. Download and run `JellyRip.exe` again — no more blocks!

## Unstable Builds

Pre-alpha builds are available for users who want the newest fixes before a stable release.

Shortcut links:

- Latest unstable release page: [unstable-latest release](https://github.com/unexpear/JellyRip/releases/tag/unstable-latest)
- Latest unstable direct download: [JellyRip.exe (unstable-latest)](https://github.com/unexpear/JellyRip/releases/download/unstable-latest/JellyRip.exe)

- Check [Releases](https://github.com/unexpear/JellyRip/releases) for tags marked as **pre-release**
- Download the `JellyRip.exe` asset from that pre-release tag
- Expect regressions, rough edges, and breaking behavior changes between builds
- If you hit issues, report them on [GitHub Issues](https://github.com/unexpear/JellyRip/issues)
- Use the printable pass/fail worksheet during live tests: [TESTERS.md](TESTERS.md)

Use unstable builds only if you are comfortable testing and troubleshooting.

### Option 2: From Source

Requires Python 3.13+:

```bash
pip install -r requirements.txt
python main.py
```

## Usage

JellyRip provides multiple operating modes for different workflows:

- **TV Disc** — Interactive mode for ripping TV series with episode selection
- **Movie Disc** — Interactive mode for ripping movies with metadata
- **Smart Rip** — Automatic selection of main feature (best for casual users)
- **Organize** — Organize existing MKV files into library structure

## Requirements

- **MakeMKV** — [Download](https://www.makemkv.com/)
- **FFprobe** — Included with HandBrake or ffmpeg
- Optical drive with disc

## Features

- **Multi-layer architecture** — Clean separation between logic, workflow, and UI
- **Disc scoring algorithm** — Automatically selects best quality title
- **Retry logic** — Automatic retries with escalating MakeMKV flags
- **Stall detection** — Detects and aborts frozen rip processes
- **Configurable workflow** — 15+ options for customization
- **Session logging** — Full audit trail of all operations

## Configuration

Settings auto-save to `%APPDATA%\JellyRip\config.json` on Windows.

Open Settings from the UI to configure:

- Tool paths (MakeMKV, ffprobe)
- Folder locations (temp, TV, movies)
- Retry behavior and timeouts
- Space warnings and cleanup options
- Optional debug warnings for malformed parse values (safe_int and duration)

## Tester Workflow

For live ripping validation and issue reporting:

- Run the one-page worksheet: [TESTERS.md](TESTERS.md)
- File results and logs on [GitHub Issues](https://github.com/unexpear/JellyRip/issues)

## Building from Source

Requires PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name JellyRip main.py
```

Output: `dist/JellyRip.exe`

To build installer too (requires Inno Setup 6):

```bash
build_installer.bat
```

Outputs:

- `dist/JellyRip.exe`
- `dist/JellyRipInstaller.exe`

Note: `dist/` build outputs are intentionally git-ignored and are published through GitHub Releases rather than committed to the repository.

## License

See LICENSE file.
