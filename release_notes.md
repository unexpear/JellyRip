# JellyRip v1.0.23 Release Notes

JellyRip v1.0.23 — bug-fix release on top of the v1.0.22 audit
cleanup.  Two user-facing fixes (disc-scan responsiveness + tool
auto-detection); no new features.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.23/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.23/JellyRipInstaller.exe)
- Release page: [v1.0.23 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.23)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)

## Highlights

### Engine

- **Stop is now responsive during disc scan.** The scan loop read
  MakeMKV's output with a blocking `readline()`, so Stop could
  appear frozen until the next line arrived. Scan output now feeds
  through a reader thread + queue with `proc.poll()`, so Stop takes
  effect promptly and trailing title metadata isn't dropped.
- **Blank tool path no longer breaks FFmpeg/ffprobe auto-detect.**
  `os.path.normpath("")` returns `"."`, which the resolvers read as
  a configured directory — so an empty `ffprobe_path` /
  `makemkvcon_path` (meaning "auto-detect") found nothing and
  reported "tool not found". A new `_norm_tool_path` helper keeps a
  blank path blank, so auto-detection (and the bundled FFmpeg) work.

### Tests

- Scan-disc process test fakes gained `poll()` + `stdout.close()` to
  match the reader-thread scan loop.
- **Full suite: 1647 passed, 5 skipped.**

## What's NOT in this release

No new ripping/validation/organization features — these are
targeted fixes to scan responsiveness and tool detection.

## Companion fork: JellyRip AI

The AI fork ships an assistant layer (chat sidebar + AI provider
integrations) on top of the same disc-ripping core.

- AI release page: [ai-v1.0.23 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.23)
- AI project site: [unexpear-softwhere.github.io/JellyRipAI](https://unexpear-softwhere.github.io/JellyRipAI/)
