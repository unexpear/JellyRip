from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _current_version() -> str:
    runtime_text = _read("shared/runtime.py")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', runtime_text)
    assert match is not None
    return match.group(1)


def test_release_metadata_matches_current_version():
    version = _current_version()
    installer_text = _read("installer/JellyRip.iss")
    changelog_text = _read("CHANGELOG.md")
    readme = _read("README.md")

    assert f'version = "{version}"' in _read("pyproject.toml")
    assert f'#define MyAppVersion "{version}"' in installer_text
    assert "VersionInfoVersion={#MyAppVersion}" in installer_text
    assert "VersionInfoProductVersion={#MyAppVersion}" in installer_text
    assert f"- Current unstable line: `v{version}`" in readme
    assert f"(recommended, currently `v{version}` unstable pre-release)" in readme
    assert f"v{version}" in _read("TESTERS.md")
    assert f"v{version}" in _read("release_notes.txt")
    assert f"v{version}" in _read("release_notes.md")
    assert re.search(rf"^## \[{re.escape(version)}\] - ", changelog_text, re.MULTILINE)


def test_readme_points_to_spec_build_and_release_notes_txt():
    readme = _read("README.md")
    version = _current_version()

    assert "pyinstaller JellyRip.spec" in readme
    assert "release_notes.txt" in readme
    assert f"release.bat {version}" in readme
    # One-DIR bundle (2026-06-09): the build output is an app folder
    # (exe + _internal\), the portable download is a zip of it, and
    # the FFmpeg notices ship inside _internal\licenses\ffmpeg\ —
    # there are no staged FFmpeg-LICENSE.txt copies anymore.
    assert "dist\\main\\JellyRip\\JellyRip.exe" in readme
    assert "JellyRip-portable.zip" in readme
    assert "_internal\\licenses\\ffmpeg\\" in readme
    assert "FFmpeg-LICENSE.txt" not in readme
    assert "ffplay" not in readme


def test_release_script_checks_git_state_and_release_notes():
    release_script = _read("release.bat")
    version = _current_version()

    assert "git status --porcelain" in release_script
    assert "git rev-parse --abbrev-ref HEAD" in release_script
    assert 'findstr /C:"v%VERSION%" release_notes.txt' in release_script
    assert 'set "ARTIFACT_DIR=dist\\main"' in release_script
    # One-DIR bundle (2026-06-09): the staging step is retired — FFmpeg
    # ships inside the app folder's _internal\, and the portable
    # artifact is a zip of the folder instead of a bare exe.
    assert "stage_ffmpeg_bundle.ps1" not in release_script
    assert "%ARTIFACT_DIR%\\JellyRip\\JellyRip.exe" in release_script
    assert "_internal\\ffmpeg.exe" in release_script
    assert "_internal\\ffprobe.exe" in release_script
    assert "_internal\\licenses\\ffmpeg\\LICENSE" in release_script
    assert "JellyRip-portable.zip" in release_script
    assert "Compress-Archive" in release_script
    assert "LICENSE THIRD_PARTY_NOTICES.md --title" in release_script
    # ffplay was dropped 2026-06-09 (unused; ~130 MB per artifact).
    assert "ffplay" not in release_script.lower()
    assert "is missing; JellyRip releases intentionally bundle FFmpeg" in release_script
    assert f"REM  Usage:  release.bat {version}" in release_script
    assert f"echo Example: release.bat {version}" in release_script


def test_release_metadata_tracks_license_notices():
    readme = _read("README.md")
    pyproject = _read("pyproject.toml")
    installer = _read("installer/JellyRip.iss")
    notices = _read("THIRD_PARTY_NOTICES.md")

    assert 'license = { text = "GPL-3.0-only" }' in pyproject
    assert "GNU General Public License v3 (GPLv3)" in pyproject
    assert "THIRD_PARTY_NOTICES.md" in readme
    assert "2026-04-01-git-eedf8f0165-full_build-www.gyan.dev" in notices
    assert "https://github.com/FFmpeg/FFmpeg/commit/eedf8f0165" in notices
    assert '#define MyAppBuildOutputDir "..\\dist\\main"' in installer
    # One-DIR bundle: the installer packages the whole app folder; the
    # old per-file FFmpeg sources are gone, and stale staged copies
    # from pre-onedir installs are deleted on upgrade (the app prefers
    # an exe-dir ffmpeg over the bundled one).
    assert 'Source: "{#MyAppBuildOutputDir}\\JellyRip\\*"' in installer
    assert "recursesubdirs" in installer
    assert "[InstallDelete]" in installer
    assert 'Name: "{app}\\ffmpeg.exe"' in installer
    assert '_internal\\ffprobe.exe' in installer
    assert 'Source: "..\\LICENSE"' in installer
    assert 'Source: "..\\THIRD_PARTY_NOTICES.md"' in installer


def test_spec_bundles_ffmpeg_intentionally():
    spec = _read("JellyRip.spec")

    # One-DIR bundle: EXE excludes binaries; COLLECT assembles the
    # app folder.  No runtime extraction (the onefile-only
    # runtime_tmpdir knob must stay gone).
    assert "exclude_binaries=True" in spec
    assert "COLLECT(" in spec
    assert "runtime_tmpdir" not in spec

    assert "TCL_LIBRARY" in spec
    assert "TK_LIBRARY" in spec
    assert 'StringStruct("ProductVersion", version)' in spec
    assert 'StringStruct("FileVersion", version)' in spec
    assert "FFMPEG_FILENAMES" in spec
    assert "FFMPEG_NOTICE_FILENAMES" in spec
    assert "binaries=FFMPEG_BINARIES" in spec
    assert "*FFMPEG_NOTICE_DATAS" in spec
    assert "THIRD_PARTY_NOTICES.md" in spec
    assert "ffmpeg.exe" in spec.lower()
    assert "ffprobe.exe" in spec.lower()
    # ffplay is referenced only in the drop-note comment, never bundled.
    assert '"ffplay.exe"' not in spec
    assert "C:/Users/" not in spec
    assert "Desktop/ffmpeg" not in spec


def test_root_release_binary_is_not_tracked():
    git_exe = shutil.which("git")
    if not git_exe:
        return

    result = subprocess.run(
        [git_exe, "ls-files", "--error-unmatch", "JellyRip.exe"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode != 0, "JellyRip.exe should not be tracked in git"
