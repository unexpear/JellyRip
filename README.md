# JellyRip

JellyRip is a Windows-first desktop app that uses MakeMKV and ffprobe
to rip discs, validate output, and organize media into a
Jellyfin-friendly library structure.

The project is currently pre-alpha. The codebase is actively tested and
being hardened, but live disc workflows can still change quickly and
should be treated as non-final.

## Project Status

- Current unstable line: `v1.0.25` (latest unstable pre-release)
- MAIN release page: [v1.0.25](https://github.com/unexpear/JellyRip/releases/tag/v1.0.25)
- AI release page: [ai-v1.0.25](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.25) (fork — separate repo, `ai-v*` tag prefix)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)
- Platform target: Windows
- Runtime target: Python 3.13+
- Distribution target: portable app folder (`JellyRip-portable.zip`) and optional installer
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

(recommended, currently `v1.0.25` unstable pre-release)

1. Go to the [current unstable release page](https://github.com/unexpear/JellyRip/releases/tag/v1.0.25).
2. Download `JellyRipInstaller.exe` (installer) or `JellyRip-portable.zip`
   (portable - unzip anywhere and run `JellyRip.exe` inside the folder).
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

`requirements.txt` pulls PySide6 (the Qt GUI toolkit). For tests and
release builds also install `requirements-dev.txt`, which adds
`pyinstaller`, `pytest`, and `pytest-qt`.

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

## User Interface

JellyRip ships a PySide6 (Qt) desktop UI. The Qt path is the only
shipped path as of v1.0.19; the legacy tkinter UI was retired during
the Phase 3 migration. Fifteen built-in themes ship out of the box
and can be switched live from **Settings -> Appearance**, which also
includes a Theme Maker for building, saving, and sharing custom
themes (stored under `%APPDATA%\JellyRip\themes\`). The disc tree
supports right-click MKV preview using QtMultimedia.

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
- [gui_qt](gui_qt) - PySide6 (Qt) UI layer (themes, dialogs, preview)
- [gui_qt/qss](gui_qt/qss) - generated theme stylesheet snapshots
  (dev reference; at runtime themes render live from token palettes)
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

### Portable app folder

```bash
build.bat
```

The MAIN build scripts place the app folder under `dist\main\JellyRip`.
`build.bat` wraps `pyinstaller JellyRip.spec` with the MAIN artifact and
work directories preconfigured.
The spec bundles the Gyan FFmpeg full build (`ffmpeg.exe` and
`ffprobe.exe`) into the app's `_internal\` folder, along with the FFmpeg
license and README under `_internal\licenses\ffmpeg\`. Put the extracted
FFmpeg build under `.\ffmpeg\` or `..\ffmpeg\`, or set
`JELLYRIP_FFMPEG_DIR` before building.

### Executable plus installer

```bash
build_installer.bat
```

Commercial installer builds require an appropriate Inno Setup license.

Expected outputs:

- `dist\main\JellyRip\JellyRip.exe` - the app folder; `_internal\`
  carries the Python runtime, `ffmpeg.exe`, `ffprobe.exe`, and the
  FFmpeg notices under `_internal\licenses\ffmpeg\`
- `dist\main\JellyRipInstaller.exe`
- `dist\main\JellyRip-portable.zip` - zip of the app folder, created
  by `release.bat` (this is the release's portable download)

Build output is intentionally git-ignored and should be published
through GitHub Releases rather than committed to the repository.

### Full release pipeline

```bash
release.bat 1.0.25
```

This runs tests, checks version consistency, builds both executables,
pushes code, and publishes a GitHub release with assets attached in the
correct order. It also refuses to run from a dirty working tree or a
branch other than `main`. Never create a release without assets.

## Support and Reporting

- Issues: [GitHub Issues](https://github.com/unexpear/JellyRip/issues)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Release post text (MAIN): [release_notes.txt](release_notes.txt)
- Readable release notes (MAIN): [release_notes.md](release_notes.md)
- Release post text (AI fork): [release_notes_ai.txt](release_notes_ai.txt)
- Readable release notes (AI fork): [release_notes_ai.md](release_notes_ai.md)
- AI BRANCH PySide6 port plan: [docs/handoffs/phase-4-ai-branch-port.md](docs/handoffs/phase-4-ai-branch-port.md)
- Tester worksheet: [TESTERS.md](TESTERS.md)

If Windows Defender flags the executable, whitelist the download folder
before retrying. This is a known false-positive pattern for
PyInstaller-built Windows executables.

## License

JellyRip is licensed under GPLv3. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Credits

A human-readable list of the tools, libraries, and people that make
JellyRip possible lives at [CREDITS.md](CREDITS.md).
