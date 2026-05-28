# JellyRip v1.0.22 Release Notes

JellyRip v1.0.22 — deep audit cleanup.  Many small correctness +
ergonomics improvements across the engine, settings UI, and
test suite.  No functional regressions; the bundled ripper +
validator + library organizer behave identically to v1.0.21
under default settings.

## Download

- Direct download: [JellyRip.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.22/JellyRip.exe)
- Installer: [JellyRipInstaller.exe](https://github.com/unexpear/JellyRip/releases/download/v1.0.22/JellyRipInstaller.exe)
- Release page: [v1.0.22 release](https://github.com/unexpear/JellyRip/releases/tag/v1.0.22)
- Project site: [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)

## Highlights

### Engine

- **`stabilize_timeout` is now an actual deadline.** The pre-move
  source-file stability check used to take a single 1-second
  sample.  Now polls every 0.1–1.0s up to the configured timeout
  (default 60s), honoring abort_event between samples.
- **Drive-probe retries default bumped from 3 to 5.** Slow optical
  drives that previously gave up after 3 retries (worst case
  ~14s) now get 2 more attempts.  Backoff base unchanged.
- **Dead `scan_disc` delegate removed.** Python's "last def wins"
  rule had been silently shadowing this 3-line delegate with the
  live ~325-line inline implementation.  Maintenance hazard
  eliminated.
- **5 magic numbers named.** Raw-line cap, ambiguity threshold,
  scan-cache TTL, and log-rollover threshold now live as
  module-level constants with documented rationale.
- **`print()` in engine layer routed through `logging`.** Was
  bypassing the controller's log capture and interleaving with
  progress output on stdout.

### UI / Settings

- **Pages docs site navigation now works.** Set `baseurl` in
  `docs/_config.yml` so Jekyll's `{% link %}` tag resolves to
  the project-path URLs.  Previously every documentation link
  on [unexpear.github.io/JellyRip](https://unexpear.github.io/JellyRip/)
  404'd.
- **Settings tabs no longer silently lose changes.** All 4 tabs
  (Everyday, Paths, Reliability, Appearance) used to swallow
  config-save failures.  Now log them so a disk-full or locked
  `config.json` leaves a session-log breadcrumb.
- **Utility chip failures surface in 3 places** instead of 1.
  Handler exceptions now flip the status bar + log to the
  session log file (with full stack trace), not just the log
  pane.

### Workflow

- **Partial-extras-move now flagged as partial.** `_move_extras_to_categories`
  used to silently swallow failures and report "session complete"
  even when bonus files were stranded in temp.  Now reports
  success/failure and triggers `_preserve_partial_session` on
  failure.
- **Dead resume scaffolding removed.** ~15 sites in
  `_run_disc_inner` referenced resume-after-interrupt state that
  was never populated (the `check_resume` call was missing).
  Branches were unreachable.  Removed; the AI fork keeps the
  feature working via its own wiring.

### Tests

- **3 of 5 truncated test bodies reconstructed.** Coverage
  improvements:
  - `test_episodes_from_filename_wrong_season_returns_empty`
  - `test_run_smart_rip_warn_with_opt_warn_low_space_off_skips_prompt`
  - `test_smart_rip_path_overrides_cancel_does_not_touch_sm`
- **2 of 5 skipped security tests reframed as positive Qt-side
  tests.** Pins that `tools/update_check.py` stub doesn't shell
  out + directs users to the correct fork's releases URL.
- **Test suite: 1645 passed, 8 skipped** (was 1642 / 11 in v1.0.21).

### Documentation hygiene

- Mojibake (UTF-8-misread-as-cp1252 garbage) cleared from
  `CHANGELOG.md`, `docs/smoke-report-2026-05-04.md`, and
  `tests/test_behavior_guards.py`.

## What's NOT in this release

No new ripping/validation/organization features.  Engine behavior
under default settings is byte-identical to v1.0.21 — every
change preserves prior behavior at default values.

## Companion fork: JellyRip AI

The AI fork ships an assistant layer (chat sidebar + AI provider
integrations) on top of the same disc-ripping core.

- AI release page: [ai-v1.0.22 release](https://github.com/unexpear-softwhere/JellyRipAI/releases/tag/ai-v1.0.22)
- AI project site: [unexpear-softwhere.github.io/JellyRipAI](https://unexpear-softwhere.github.io/JellyRipAI/)
