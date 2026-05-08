---
title: JellyRip
description: Windows desktop ripping into a Jellyfin-friendly library
---

JellyRip is a Windows-first desktop app that uses MakeMKV and ffprobe to
rip discs, validate output, and organize media into a Jellyfin-friendly
library structure.

The project is currently **pre-alpha**.  The codebase is actively tested
and being hardened, but live disc workflows can still change quickly and
should be treated as non-final.

## Download

[Latest release: v1.0.20](https://github.com/unexpear/JellyRip/releases/tag/v1.0.20){: .btn .btn-primary }
[Installer (.exe)](https://github.com/unexpear/JellyRip/releases/download/v1.0.20/JellyRipInstaller.exe){: .btn }
[Standalone (.exe)](https://github.com/unexpear/JellyRip/releases/download/v1.0.20/JellyRip.exe){: .btn }

If Windows SmartScreen flags the executable, whitelist the download folder
before retrying — this is a known false-positive pattern for
PyInstaller-built Windows binaries.

## What JellyRip does

- Rips movie and TV discs with MakeMKV
- Validates outputs with ffprobe and file-stabilization checks
- Organizes files into Jellyfin-style movie and TV folder structures
- Supports interactive, unattended, and smart-rip workflows
- Keeps session logs and end-of-run warning summaries

## Project information

The repo's top-level documents:

- [README](https://github.com/unexpear/JellyRip/blob/main/README.md) —
  project overview, requirements, build instructions
- [Changelog](https://github.com/unexpear/JellyRip/blob/main/CHANGELOG.md) —
  version-by-version diff
- [Release notes](https://github.com/unexpear/JellyRip/blob/main/release_notes.md) —
  human-readable narrative for the latest tag
- [Credits](https://github.com/unexpear/JellyRip/blob/main/CREDITS.md) —
  bundled tools, integrations, AI-assisted development
- [Third-party notices](https://github.com/unexpear/JellyRip/blob/main/THIRD_PARTY_NOTICES.md) —
  legal license text for bundled components
- [Security](https://github.com/unexpear/JellyRip/blob/main/SECURITY.md) —
  reporting policy
- [Contributing](https://github.com/unexpear/JellyRip/blob/main/CONTRIBUTING.md) —
  contribution and development guidance
- [Testers' worksheet](https://github.com/unexpear/JellyRip/blob/main/TESTERS.md) —
  manual live-rip validation steps
- [Feature map](https://github.com/unexpear/JellyRip/blob/main/FEATURE_MAP.md) —
  file-to-feature mapping

## Documentation

Deeper technical material lives in this site's `docs/`:

- [Architecture overview]({% link architecture.md %})
- [Repository layout]({% link repository-layout.md %})
- [Branch workflow]({% link branch-workflow.md %})
- [Glossary]({% link glossary.md %})
- [Copy style guide]({% link copy-style.md %})
- [Symbol library]({% link symbol-library.md %})
- [UX copy and accessibility plan]({% link ux-copy-and-accessibility-plan.md %})

## Companion fork: JellyRip AI

JellyRip AI is the assistant-enabled fork.  Same disc-ripping core; adds
a chat sidebar and integrations with Anthropic Claude, OpenAI, Google
Gemini, and Ollama for on-device models.

- [JellyRip AI on GitHub](https://github.com/unexpear-softwhere/JellyRipAI)
- [JellyRip AI documentation site](https://unexpear-softwhere.github.io/JellyRipAI/)
- [Latest AI release: ai-v1.0.20](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.20)

## Source and license

- GitHub: [unexpear/JellyRip](https://github.com/unexpear/JellyRip)
- License: [GPL-3.0](https://github.com/unexpear/JellyRip/blob/main/LICENSE)
- Issues / bug reports: [GitHub Issues](https://github.com/unexpear/JellyRip/issues)
