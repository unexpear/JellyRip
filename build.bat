@echo off
REM Build JellyRip.exe from source using PyInstaller

echo Building JellyRip.exe...
echo.

REM Check if PyInstaller is installed
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo Error: PyInstaller not installed
    echo Run: pip install pyinstaller
    pause
    exit /b 1
)

REM Clean previous builds
if exist dist rmdir /s /q dist >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1

REM Build the exe
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name JellyRip ^
    JellyRip.py

if errorlevel 1 (
    echo Build failed!
    pause
    exit /b 1
) else (
    echo.
    echo Build complete! Output: dist\JellyRip.exe
    pause
)
