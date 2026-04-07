@echo off
REM ============================================================
REM  JellyRip release pipeline — enforces correct order:
REM    tests -> build -> verify -> push -> publish
REM
REM  Usage:  release.bat 1.0.12
REM ============================================================
setlocal enabledelayedexpansion

set VERSION=%~1
if "%VERSION%"=="" (
    echo Usage: release.bat ^<version^>
    echo Example: release.bat 1.0.12
    exit /b 1
)

set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC_EXE%" set ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe
if not exist "%ISCC_EXE%" set ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe

echo.
echo ========================================
echo  JellyRip Release Pipeline v%VERSION%
echo ========================================
echo.

REM ---- Step 1: Run tests ----
echo [1/7] Running tests...
%PYTHON_EXE% -m pytest tests/ -q --tb=short
if errorlevel 1 (
    echo.
    echo ABORT: Tests failed. Fix before releasing.
    exit /b 1
)
echo       Tests passed.
echo.

REM ---- Step 2: Check version consistency ----
echo [2/7] Checking version consistency...

findstr /C:"__version__ = \"%VERSION%\"" shared\runtime.py >nul 2>&1
if errorlevel 1 (
    echo ABORT: shared\runtime.py does not contain version %VERSION%
    echo        Update __version__ before running this script.
    exit /b 1
)

findstr /C:"version = \"%VERSION%\"" pyproject.toml >nul 2>&1
if errorlevel 1 (
    echo ABORT: pyproject.toml does not contain version %VERSION%
    exit /b 1
)

findstr /C:"#define MyAppVersion \"%VERSION%\"" installer\JellyRip.iss >nul 2>&1
if errorlevel 1 (
    echo ABORT: installer\JellyRip.iss does not contain version %VERSION%
    exit /b 1
)

findstr /C:"[%VERSION%]" CHANGELOG.md >nul 2>&1
if errorlevel 1 (
    echo ABORT: CHANGELOG.md has no entry for %VERSION%
    exit /b 1
)
echo       All files show v%VERSION%.
echo.

REM ---- Step 3: Build exe ----
echo [3/7] Building JellyRip.exe...
%PYTHON_EXE% -m PyInstaller JellyRip.spec >nul 2>&1
if errorlevel 1 (
    echo ABORT: PyInstaller build failed.
    exit /b 1
)
if not exist dist\JellyRip.exe (
    echo ABORT: dist\JellyRip.exe not found after build.
    exit /b 1
)
echo       dist\JellyRip.exe built.
echo.

REM ---- Step 4: Build installer ----
echo [4/7] Building JellyRipInstaller.exe...
if not exist "%ISCC_EXE%" (
    echo ABORT: Inno Setup compiler not found.
    exit /b 1
)
"%ISCC_EXE%" installer\JellyRip.iss >nul 2>&1
if errorlevel 1 (
    echo ABORT: Installer build failed.
    exit /b 1
)
if not exist dist\JellyRipInstaller.exe (
    echo ABORT: dist\JellyRipInstaller.exe not found after build.
    exit /b 1
)
echo       dist\JellyRipInstaller.exe built.
echo.

REM ---- Step 5: Verify build outputs ----
echo [5/7] Verifying build outputs...
for %%F in (dist\JellyRip.exe) do (
    if %%~zF LSS 1000000 (
        echo ABORT: JellyRip.exe is suspiciously small (%%~zF bytes).
        exit /b 1
    )
)
for %%F in (dist\JellyRipInstaller.exe) do (
    if %%~zF LSS 1000000 (
        echo ABORT: JellyRipInstaller.exe is suspiciously small (%%~zF bytes).
        exit /b 1
    )
)
echo       Both executables verified.
echo.

REM ---- Step 6: Push code ----
echo [6/7] Pushing to GitHub...
git push origin main
if errorlevel 1 (
    echo ABORT: git push failed.
    exit /b 1
)
echo       Code pushed.
echo.

REM ---- Step 7: Create release with assets ----
echo [7/7] Publishing release v%VERSION% with assets...
gh release create v%VERSION% dist\JellyRip.exe dist\JellyRipInstaller.exe --title "JellyRip v%VERSION% (UNSTABLE)" --notes-file release_notes.txt --prerelease
if errorlevel 1 (
    echo ABORT: gh release create failed.
    exit /b 1
)
echo.
echo ========================================
echo  Release v%VERSION% published!
echo ========================================
echo.
echo  Assets:
echo    - JellyRip.exe
echo    - JellyRipInstaller.exe
echo.
echo  Verify: https://github.com/unexpear/JellyRip/releases/tag/v%VERSION%
echo.
