# JellyRip v1.0.25 Release Notes

JellyRip v1.0.25 — a small fix release.  The Settings dialog now follows
your theme correctly under light themes, and its tab bar stays readable
on every theme.

## Download

- Portable: [JellyRip-portable.zip](https://github.com/unexpear/JellyRip/releases/download/v1.0.25/JellyRip-portable.zip)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.25/JellyRipInstaller.exe)
- Release page: [v1.0.25 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.25)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)

## Fixed

- **Settings dialog now follows the theme under light themes.** A
  top-level dialog's background isn't reliably painted over the native
  window surface on Windows, so the Settings dialog stayed dark under
  light themes — both freshly opened and on a live theme switch — while
  its controls restyled around it. The dialog now wraps its content in a
  themed surface, the same approach the main window uses, so it follows
  the theme instantly.
- **Settings tab bar stays readable on every theme.** It was unstyled,
  so once the dialog correctly went light the unselected tabs (Everyday
  / Paths / Reliability) vanished white-on-white. Tabs are now themed:
  muted labels with an accent underline on the selected tab.

## Companion fork: JellyRip AI

The AI fork ships the same fixes plus its assistant layer (chat sidebar
+ AI provider integrations + TMDB/OMDb disc auto-identification).

- AI release page: [ai-v1.0.25 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.25)
- AI project site: [unexpear-softwhere.github.io/JellyRipAI](https://unexpear-softwhere.github.io/JellyRipAI/)
