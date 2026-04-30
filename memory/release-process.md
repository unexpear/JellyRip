# JellyRip — Release Process

## Command

```bat
release.bat <version>
```

Example: `release.bat 1.0.18`

## Pipeline (8 steps, abort-on-fail)

1. **Verify git state** — must be on `main`, working tree must be clean (no untracked / modified files).
2. **Run tests** — `pytest tests/ -q --tb=short`. Aborts if any fail.
3. **Check version consistency** — every one of these must contain the new version, or release aborts:
   - `shared/runtime.py` — `__version__ = "<version>"`
   - `pyproject.toml` — `version = "<version>"` (and must declare `GPL-3.0-only`)
   - `installer/JellyRip.iss` — `#define MyAppVersion "<version>"`
   - `CHANGELOG.md` — must have `[<version>]` entry
   - `release_notes.txt` — must mention `v<version>`
   - `LICENSE` and `THIRD_PARTY_NOTICES.md` must exist
4. **Build `JellyRip.exe`** — `pyinstaller JellyRip.spec` into `dist/main/`. Stages FFmpeg bundle (ffmpeg.exe, ffprobe.exe, ffplay.exe + FFmpeg-LICENSE.txt + FFmpeg-README.txt). Aborts if any are missing.
5. **Build `JellyRipInstaller.exe`** — Inno Setup compiler (`ISCC.exe`). Auto-detects under Program Files / Program Files (x86) / `%LOCALAPPDATA%\Programs\Inno Setup 6`.
6. **Verify build outputs** — sanity-check artifact sizes (e.g., `JellyRip.exe` must be ≥ 1 MB).
7. **Push code** to remote.
8. **Publish GitHub release** with assets attached in correct order.

## Files to bump for a new version (must all match `<version>`)

- `shared/runtime.py` (`__version__`)
- `pyproject.toml` (`version`)
- `installer/JellyRip.iss` (`MyAppVersion`)
- `CHANGELOG.md` (new `[<version>]` section)
- `release_notes.txt` (mention `v<version>`)
- `release_notes.md` (readable copy)
- `README.md` (status section + release page link, both `MAIN` and `AI` lines if applicable)

## Hard rules

- **Never run `release.bat` from a dirty tree** — it aborts; don't try to bypass.
- **Never run from a non-`main` branch** — same; pipeline refuses.
- **Never publish a release without assets** — the pipeline attaches them in order; don't manually create a release without bundling the executables and FFmpeg notices.
- **Build artifacts (`dist/`, `build/`) are git-ignored** — don't commit them.

## Build-only (no release)

- `build.bat` — standalone exe only
- `build_installer.bat` — exe + installer

Both write to `dist/main/`.
