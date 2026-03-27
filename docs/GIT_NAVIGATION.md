# Git Navigation Guide

This guide makes it easier to move through JellyRip's history, files, and release flow.

## Quick Repo Map

- `JellyRip.py`: Main single-file application (engine, controller, UI)
- `README.md`: User install and usage overview
- `CHANGELOG.md`: Versioned release history
- `release_notes.txt`: Short release summary text
- `build.bat`: Windows build helper for `dist/JellyRip.exe`
- `tests/`: Focused test suite (`pytest`)
- `TESTERS.md`: Manual rip-testing worksheet
- `.github/ISSUE_TEMPLATE/`: Issue templates

## Fast History Commands

Run these from the repo root.

```powershell
git log --oneline -n 30
```

```powershell
git log --oneline --graph --decorate --all -n 40
```

```powershell
git show <commit_sha>
```

```powershell
git diff HEAD~1..HEAD
```

## Find Changes by File

```powershell
git log --oneline -- JellyRip.py
```

```powershell
git log -p -- CHANGELOG.md
```

```powershell
git blame JellyRip.py
```

## Release Navigation

- Current version marker: `JellyRip.py` (`__version__`)
- Human-readable release notes: `CHANGELOG.md`
- Short post text: `release_notes.txt`
- Built binary output: `dist/JellyRip.exe`

Typical release checks:

```powershell
git status --short
python -m pytest -q
```

```powershell
python -m PyInstaller --onefile --windowed --name JellyRip JellyRip.py
```

## Common Workflows

### 1) Inspect what changed recently

```powershell
git log --oneline -n 15
git show HEAD
```

### 2) Review pending work before commit

```powershell
git status --short
git diff
```

### 3) Publish a completed change

```powershell
git add <files>
git commit -m "type: short summary"
git push origin main
```

## Commit Message Pattern Used in This Repo

Common prefixes seen in history:

- `fix:` bug fixes
- `build:` build process updates
- `release:` version/release prep
- `chore:` housekeeping/docs/lint cleanup

Keeping this pattern makes the log easier to scan.
