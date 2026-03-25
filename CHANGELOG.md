# Changelog

## 1.0.4 - 2026-03-25

### Reliability and parsing hardening
- Hardened duration parsing so malformed values safely default to 0.
- Hardened size parsing to tolerate variants like 3.7GB, 3,7 GB, and trailing text.
- Added safe dictionary access for optional audio and subtitle track lists in scoring/logging paths.

### Ripping and process stability
- Kept rip success based on MakeMKV exit code while preserving fallback behavior when files are actually produced on non-zero exits.
- Maintained abort-safe process handling with local subprocess snapshot usage.
- Added extra guardrails for destination path race conditions during atomic move.

### Observability and diagnostics
- Added optional safe_int debug warnings (de-duplicated and throttled; off by default).
- Added optional malformed-duration debug warnings (de-duplicated and throttled; off by default).
- Expanded score visibility with explicit score breakdown and ambiguity warning when top candidates are close.

### Testing and docs
- Added printable live-rip pass/fail worksheet for testers: TESTERS.md.
- Updated README links so testers can find worksheet and issue reporting flow quickly.
