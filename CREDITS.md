# Credits

JellyRip stands on the shoulders of a lot of open-source work.  This
page is the human-readable acknowledgments — for the legal license
detail, see [`LICENSE`](LICENSE) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

## Maintainer

* **[unexpear](https://github.com/unexpear)** — author and primary
  maintainer.  Self-described "new to code projects" — the project
  exists because they wanted a Windows-first, Jellyfin-friendly
  disc-ripping pipeline that wasn't already a thing.

## External tools the user must install

JellyRip would not work without these.  None of them ship with
JellyRip releases — users install them separately.

* **[MakeMKV](https://www.makemkv.com/)** — the disc-ripping engine
  that does the actual hard work of reading discs and writing MKV
  output.  JellyRip is essentially a workflow / library wrapper on
  top of `makemkvcon`.  Live ripping is impossible without MakeMKV.
* **[Jellyfin](https://jellyfin.org/)** — the media server the
  output folder layout is shaped for.  JellyRip writes files into
  the directory conventions Jellyfin scans.

## Bundled with release builds

These ship inside [`JellyRip.exe`](https://github.com/unexpear/JellyRip/releases)
or alongside it in the installer.  See
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for the
license-text version.

* **[FFmpeg](https://ffmpeg.org/)** (Gyan Windows full build) —
  `ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe`.  Used for output
  validation (`ffprobe`), transcode workflows (`ffmpeg`), and as
  a fallback preview player.
* **[Python](https://www.python.org/)** — the runtime interpreter
  PyInstaller embeds.
* **[PySide6 / Qt](https://www.qt.io/qt-for-python)** — the desktop
  UI toolkit.  Phase 3 ported the entire UI from tkinter to Qt;
  themes, MKV preview, drive scanner, status bar, and tray icon
  all run on PySide6.
* **[PyInstaller](https://pyinstaller.org/)** — bundles the Python
  app + dependencies + Qt runtime into a single
  `JellyRip.exe`.
* **[Inno Setup](https://jrsoftware.org/isinfo.php)** — used to
  produce `JellyRipInstaller.exe`.

## Optional user-installed integrations

These are detected at runtime if installed; release builds do not
bundle them.

* **[HandBrakeCLI](https://handbrake.fr/)** — alternate transcode
  backend.
* **[VLC](https://www.videolan.org/)** — fallback preview player
  when the bundled Qt preview can't reach a file.

## AI-assisted development

A substantial portion of the v1.0.x development — including the
PySide6 migration, the smoke-session hardening of the cancel /
robot-mode / validate-tools pathways, and the `--profile`
multi-instance feature — was paired with **[Claude Code](https://claude.com/claude-code)**
(Anthropic).  Commits in the project history show
`Co-Authored-By: Claude Opus 4.7 …` where this happened.

## License

JellyRip itself is **[GPL-3.0](LICENSE)**.  Bundled FFmpeg is
GPL-3.0.  Other bundled components carry their own licenses
documented in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).
