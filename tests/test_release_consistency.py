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


def test_release_script_checks_git_state_and_release_notes():
    release_script = _read("release.bat")
    version = _current_version()

    assert "git status --porcelain" in release_script
    assert "git rev-parse --abbrev-ref HEAD" in release_script
    assert 'findstr /C:"v%VERSION%" release_notes.txt' in release_script
    assert f"REM  Usage:  release.bat {version}" in release_script
    assert f"echo Example: release.bat {version}" in release_script


def test_spec_avoids_machine_specific_ffmpeg_paths():
    spec = _read("JellyRip.spec")

    assert "JELLYRIP_FFMPEG_DIR" in spec
    assert "TCL_LIBRARY" in spec
    assert "TK_LIBRARY" in spec
    assert 'StringStruct("ProductVersion", version)' in spec
    assert 'StringStruct("FileVersion", version)' in spec
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
