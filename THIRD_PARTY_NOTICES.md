# Third-Party Notices

This file is a practical license notice for JellyRip release artifacts. It is
not legal advice.

## JellyRip

JellyRip is licensed under the GNU General Public License version 3. See
`LICENSE`.

## Distributed With JellyRip Builds

- Python 3.13 runtime: Python Software Foundation License Version 2.
  See <https://docs.python.org/3/license.html>.
- Tcl/Tk runtime components used by tkinter: Tcl/Tk license terms distributed
  with Python's Tcl/Tk runtime.
- PyInstaller bootloader and loader files: GPL-2.0-or-later WITH the
  PyInstaller bootloader exception. The exception permits embedding the
  compiled bootloader into generated executables.
- PyInstaller runtime hooks, when included: Apache-2.0.
- Inno Setup installer runtime: Inno Setup license. See
  <https://jrsoftware.org/files/is/license.txt>. The local Inno Setup
  compiler may be licensed for non-commercial use only; buy the appropriate
  Inno Setup license before using it for commercial installer builds.
- FFmpeg / ffprobe / ffplay: Gyan FFmpeg 64-bit static Windows full build,
  version `2026-04-01-git-eedf8f0165-full_build-www.gyan.dev`.
  License: GNU General Public License version 3. Source code:
  <https://github.com/FFmpeg/FFmpeg/commit/eedf8f0165>. JellyRip release
  artifacts include `ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe`,
  `FFmpeg-LICENSE.txt`, and `FFmpeg-README.txt`; the README file is copied
  from the Gyan package and contains the build configuration and external
  library version disclosure.

## Used But Not Distributed By JellyRip Releases

JellyRip resolves and launches these tools when they are installed by the user.
Do not bundle any of these binaries in JellyRip releases without updating this
notice and shipping the license/source materials required by that tool's
license.

- MakeMKV / makemkvcon: user-installed MakeMKV is required for live disc
  ripping. Users must comply with MakeMKV's own license terms.
- HandBrakeCLI: optional user-installed transcode backend. HandBrake is
  primarily GPLv2, with some BSD-licensed portions.
- VLC: optional user-installed preview player.

## Release Rule

Before publishing a release, confirm the release artifacts contain
the expected `ffmpeg.exe`, `ffprobe.exe`, `ffplay.exe`,
`FFmpeg-LICENSE.txt`, and `FFmpeg-README.txt`, and do not contain
`makemkvcon.exe`, `HandBrakeCLI.exe`, or `vlc.exe`. If JellyRip ever ships
another third-party tool, publish the required license notices and
corresponding source materials in the same release.
