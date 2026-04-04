@echo off
REM Build JellyRip.exe and package JellyRipInstaller.exe with Inno Setup

set "PYTHON_EXE=.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"
set ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe
if not exist "%ISCC_EXE%" set ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe
if not exist "%ISCC_EXE%" set ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe

echo Building JellyRip.exe...
%PYTHON_EXE% -m PyInstaller JellyRip.spec
if errorlevel 1 (
    echo EXE build failed.
    exit /b 1
)

if not exist "%ISCC_EXE%" (
    echo Inno Setup compiler not found.
    echo Install Inno Setup 6, then run this script again.
    exit /b 1
)

echo Building JellyRipInstaller.exe...
"%ISCC_EXE%" installer\JellyRip.iss
if errorlevel 1 (
    echo Installer build failed.
    exit /b 1
)

echo.
echo Build complete:
echo   dist\JellyRip.exe
echo   dist\JellyRipInstaller.exe
