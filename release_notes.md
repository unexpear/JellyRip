# JellyRip v1.0.27 Release Notes

JellyRip v1.0.27 — a feedback pass on ripping.  The progress bar now
tracks the file growing on disk (so it moves even on stubborn discs
MakeMKV can't report progress for), the live log shows readable MakeMKV
messages instead of raw template text, and the Browse Folder window shows
a thumbnail for each MKV as it scans.

## Download

- Portable: [JellyRip-portable.zip](https://github.com/unexpear/JellyRip/releases/download/v1.0.27/JellyRip-portable.zip)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.27/JellyRipInstaller.exe)
- Release page: [v1.0.27 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.27)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)

## Added

- **Thumbnails in the Browse Folder window.**  Scanning a folder now shows
  a video-frame preview for each MKV, like a file browser, so you can tell
  titles apart at a glance.

## Fixed

- **The rip progress bar moves again.**  It's driven by the output file
  growing on disk — weighted by each title's size — so it climbs steadily
  even on difficult discs (e.g. region-mismatched ones) where MakeMKV emits
  no progress ticks at all.  The old bar could sit frozen at 0%.

## Changed

- **The live rip log is readable.**  MakeMKV messages now show their
  resolved text (e.g. "Region setting … does not match …") instead of the
  raw `%1 …` format template, and the bar's progress is echoed to the log
  as a "Ripping: X.X / Y.Y GB (NN%)" line.

## Companion fork: JellyRip AI

The AI fork ships the same changes plus its assistant layer (chat sidebar,
AI providers, and TMDB/OMDb — plus TVmaze/TheTVDB for TV — disc
auto-identification).

- AI release page: [ai-v1.0.27 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.27)
- AI project site: [unexpear-softwhere.github.io/JellyRipAI](https://unexpear-softwhere.github.io/JellyRipAI/)
