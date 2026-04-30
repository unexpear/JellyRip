"""Tests for shared.windows_exec — path-trust contract.

The module resolves trusted absolute paths to PowerShell, Explorer, and
the Windows system / root directories. The actual security property is
**path trust**: every public function returns either an absolute path
under `C:\\Windows`, or a documented non-Windows fallback string. There
is no PATH lookup, no argv construction, no shell-metacharacter quoting
in this module — those concerns live at the *callers* (tested separately
in `tests/test_security_hardening.py`).

Reframe note: the original test-strategy doc described this as an
"injection fuzz" target, which doesn't match the actual code. See
`memory/test-coverage.md` §5 correction.
"""

from __future__ import annotations

import os
import sys

import pytest

from shared import windows_exec


# --------------------------------------------------------------------------
# Path-trust on Windows
# --------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
@pytest.mark.parametrize(
    "resolver",
    [windows_exec.get_powershell_executable, windows_exec.get_explorer_executable],
    ids=["powershell", "explorer"],
)
def test_resolver_returns_absolute_normalized_path_under_windows(resolver):
    path = resolver()

    # Absolute: cannot be a bare name like "powershell" or "explorer".
    assert os.path.isabs(path), f"expected absolute path, got: {path!r}"
    # Normalized: re-normalizing must be idempotent.
    assert path == os.path.normpath(path)
    # No relative-traversal segments.
    assert ".." not in path.split(os.sep)
    # Lives under C:\Windows (case-insensitive).
    assert path.lower().startswith("c:\\windows")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
@pytest.mark.parametrize(
    "resolver",
    [windows_exec.get_powershell_executable, windows_exec.get_explorer_executable],
    ids=["powershell", "explorer"],
)
def test_resolver_is_path_independent(monkeypatch, resolver):
    """The resolver must NOT consult PATH. Set PATH to empty (and to a
    hostile value) — the trusted path must come back unchanged."""
    baseline = resolver()

    monkeypatch.setenv("PATH", "")
    assert resolver() == baseline

    monkeypatch.setenv("PATH", r"C:\Attacker\bin;C:\Other\bin")
    assert resolver() == baseline


# --------------------------------------------------------------------------
# Hardcoded fallback when on-disk file is missing
# --------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
def test_powershell_falls_back_to_hardcoded_path_when_file_missing(monkeypatch):
    """If the System32 path constructed via the API doesn't exist on disk,
    the resolver falls through to a hardcoded literal — never empty,
    never a bare name."""
    monkeypatch.setattr(windows_exec.os.path, "isfile", lambda _p: False)

    result = windows_exec.get_powershell_executable()

    assert result == os.path.normpath(
        r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
def test_explorer_falls_back_to_hardcoded_path_when_file_missing(monkeypatch):
    monkeypatch.setattr(windows_exec.os.path, "isfile", lambda _p: False)

    result = windows_exec.get_explorer_executable()

    assert result == os.path.normpath(r"C:\Windows\explorer.exe")


# --------------------------------------------------------------------------
# get_windows_root_directory — env-var fallback chain
# --------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
def test_root_directory_uses_systemroot_when_api_returns_empty(monkeypatch):
    """When the ctypes API call returns "", SystemRoot env var is consulted
    first."""
    monkeypatch.setattr(windows_exec, "_get_windows_directory", lambda _api: "")
    monkeypatch.setenv("SystemRoot", r"C:\AlternateRoot")
    monkeypatch.delenv("WINDIR", raising=False)

    result = windows_exec.get_windows_root_directory()

    assert result == os.path.normpath(r"C:\AlternateRoot")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
def test_root_directory_uses_windir_when_systemroot_absent(monkeypatch):
    monkeypatch.setattr(windows_exec, "_get_windows_directory", lambda _api: "")
    monkeypatch.delenv("SystemRoot", raising=False)
    monkeypatch.setenv("WINDIR", r"C:\WindirRoot")

    result = windows_exec.get_windows_root_directory()

    assert result == os.path.normpath(r"C:\WindirRoot")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
def test_root_directory_falls_back_to_hardcoded_when_no_env_vars(monkeypatch):
    monkeypatch.setattr(windows_exec, "_get_windows_directory", lambda _api: "")
    monkeypatch.delenv("SystemRoot", raising=False)
    monkeypatch.delenv("WINDIR", raising=False)

    result = windows_exec.get_windows_root_directory()

    assert result == os.path.normpath(r"C:\Windows")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only contract")
def test_system_directory_falls_back_to_hardcoded_when_api_returns_empty(monkeypatch):
    """`get_windows_system_directory` has no env-var chain — it goes
    straight from API → hardcoded."""
    monkeypatch.setattr(windows_exec, "_get_windows_directory", lambda _api: "")

    result = windows_exec.get_windows_system_directory()

    assert result == os.path.normpath(r"C:\Windows\System32")


# --------------------------------------------------------------------------
# Non-Windows behavior (each function has a documented non-win32 return)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "func,expected",
    [
        (lambda: windows_exec._get_windows_directory("GetSystemDirectoryW"), ""),
        (windows_exec.get_windows_system_directory, ""),
        (windows_exec.get_windows_root_directory, ""),
        (windows_exec.get_powershell_executable, "powershell"),
        (windows_exec.get_explorer_executable, "explorer"),
    ],
    ids=[
        "_get_windows_directory",
        "get_windows_system_directory",
        "get_windows_root_directory",
        "get_powershell_executable",
        "get_explorer_executable",
    ],
)
def test_non_windows_returns_documented_fallback(monkeypatch, func, expected):
    """Pretend we're on Linux: every function returns its non-Windows
    documented value. This is how the module behaves on CI / dev machines
    that happen not to be Windows; pinning it ensures cross-platform
    behavior remains predictable."""
    monkeypatch.setattr(sys, "platform", "linux")
    assert func() == expected


def test_get_powershell_executable_never_returns_empty():
    """Defense-in-depth: even with hostile env, the function must always
    return a non-empty string (so callers can rely on the truthy-return
    contract)."""
    result = windows_exec.get_powershell_executable()
    assert result  # truthy: never None, never ""


def test_get_explorer_executable_never_returns_empty():
    result = windows_exec.get_explorer_executable()
    assert result
