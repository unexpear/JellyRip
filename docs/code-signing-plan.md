# Code Signing Plan

**Status:** **Deferred indefinitely (2026-05-02)**. After reviewing
the legal-identity-verification requirement common to *all* code-
signing paths — including the free SignPath.io OSS program — the
maintainer decided to stay unsigned. Releases continue to ship
unsigned; the README's existing "whitelist the download folder"
paragraph is the documented contingency for SmartScreen friction.
This document is preserved as a record of the decision and the
research, in case the decision is revisited later (e.g., if the
project ever forms a legal entity that makes signing a different
calculus).

## Why this exists

The current release pipeline ships **unsigned** PyInstaller
binaries. The README documents the workaround:

> "If Windows Defender flags the executable, whitelist the download
> folder before retrying. This is a known false-positive pattern for
> PyInstaller-built Windows executables."

This works for technically-comfortable users but is hostile UX for
everyone else. The issue gets worse with PySide6 — the bundle grows
~80-150 MB, reputation builds slower, and SmartScreen warnings get
more emphatic on larger novel binaries. Per the
[pyside6-migration-plan.md](pyside6-migration-plan.md), the
migration is v1-blocking; SmartScreen is a v1 ship-quality concern.

## Decision (2026-05-02 — superseded same day)

**Initial direction**: SignPath.io's open-source program (free,
identity-verified OSS code signing). The application draft was
written and would have been ready to submit.

**Final direction (same day, after maintainer review)**: **stay
unsigned.** All code-signing paths — paid commercial certs ($200-700/
year), free SignPath OSS program, even Microsoft Store
($19 one-time) — require legal-identity verification of the
maintainer per CA/Browser Forum baseline requirements. The
maintainer reviewed this requirement and chose not to provide legal
identity for cert ownership at the project's current
single-maintainer pre-alpha maturity. The SmartScreen UX hit (a
warning that users dismiss by whitelisting the download folder) is
accepted as the trade-off.

The original SignPath.io OSS program selection rationale is
preserved below for historical context — it remains the path of
choice if/when the maintainer revisits this decision (e.g., after
forming an LLC under which signing carries no personal-identity
implications).

---

## Original direction (preserved for reference)

The selected path was: **SignPath.io's open-source program**, as
the answer to PySide6 migration plan question #8 ("SmartScreen
story for larger binary").

Selection criteria from the open-questions phase:
- **Free** — no monthly or annual cost
- **No strings** — no commercial obligations beyond staying OSS
- **Best-in-class for OSS** — real cert from a trusted CA, recognized
  by Windows SmartScreen

| Option | Free? | No strings? | SmartScreen-effective? | Picked? |
| --- | --- | --- | --- | --- |
| Stay unsigned (current) | ✅ | ✅ | ❌ | — |
| Self-signed cert | ✅ | ✅ | ❌ (Windows treats self-signed and unsigned roughly equivalently for new binaries) | — |
| **SignPath.io OSS program** | ✅ | ✅ (just OSS verification) | ✅ | ✅ **picked** |
| Microsoft Store | ❌ ($19 individual dev fee, one-time) | ❌ (sandboxing + MSIX packaging) | ✅ | — |
| Azure Trusted Signing | ❌ ($10/mo) + ❌ (requires Microsoft Partner status / 3-yr incorporation history) | ❌ | ✅ | — |
| Commercial code-signing cert | ❌ ($200-700/yr) | ❌ | ✅ | — |

## What SignPath.io OSS provides

- Free code-signing certificates for verified open-source projects
- Real EV-equivalent cert from a trusted CA — Windows SmartScreen
  recognizes it
- CI/CD integration — signing happens automatically during release
- Used by significant OSS projects (Notepad++, OBS, Audacity at
  various points, others)
- No monetary cost
- No contractual lock-in beyond their OSS terms (project must remain
  open-source — JellyRip is GPLv3, fits)

## What SignPath.io requires

- Project approval — they manually review OSS projects (~1-2 weeks)
- Project must remain open-source (already true; GPLv3)
- Maintainer identity verification (paperwork — name, contact, GitHub
  profile, project URL)
- CI/CD signing integration in the release workflow (their tooling
  hooks into the release pipeline)
- Project must be under active maintenance (code commits, issues
  responded to, releases shipped — JellyRip qualifies)

## Integration with the existing release pipeline

The current `release.bat` runs an 8-step pipeline (git verify, tests,
version consistency, PyInstaller build, Inno Setup installer build,
verify outputs, push, publish GitHub release). SignPath integration
slots in between *build* and *publish*:

```
[1-3] git verify, tests, version consistency
[4-5] PyInstaller exe + Inno Setup installer        ← (build artifacts)
[NEW] SignPath sign artifacts                        ← (sign step)
[6]   Verify build outputs (size, FFmpeg bundle)
[7-8] Push, publish GitHub release with signed assets
```

SignPath's CI/CD model: the unsigned artifact is uploaded to their
service, signed there with their cert (the private key never leaves
their secure environment), the signed artifact is downloaded back and
attached to the GitHub release. This is more secure than holding a
private key in CI.

The existing fail-fast contract of `release.bat` is preserved — if
the sign step fails, the publish step does not run.

## Sequencing

Per [pyside6-migration-plan.md](pyside6-migration-plan.md), code
signing is **parallel-track work** that does NOT block on workflow
stabilization. Apply for the SignPath.io OSS program now (1-2 week
review); by the time PySide6 work begins, signing is in place for
v1 ship.

Suggested order:
1. Apply to SignPath.io OSS program (single application form). **Paste-ready draft text in [code-signing-application-draft.md](code-signing-application-draft.md)** — fill in real name + email, submit yourself.
2. Wait for review (~1-2 weeks)
3. On approval, integrate signing into `release.bat` between steps 5
   and 6
4. Test with a pre-release tag (sign + publish a test asset)
5. README update — replace the "whitelist the download folder"
   workaround paragraph with "downloads are signed; SmartScreen will
   recognize them after first user warmup"
6. Use for next real release

## What does NOT change

- GitHub Releases stays the primary distribution channel. SignPath
  signing complements it; doesn't replace it.
- The `JellyRip.exe` standalone and `JellyRipInstaller.exe` formats
  are unchanged. Both get signed.
- The Gyan FFmpeg bundle inside the standalone is unchanged. Only
  the JellyRip-built executables get JellyRip's signature.
- Open-source license (GPLv3) is unchanged. Required by SignPath OSS
  terms anyway.
- The README's `unexpear/JellyRip` GitHub identity is unchanged.

## Risks and unknowns

- **SignPath.io continued operation** — if SignPath shuts down,
  signing stops. Mitigation: documented fallback to commercial cert
  (~$200-700/yr) at that point.
- **Review timeline** — 1-2 weeks is typical, but if review reveals
  paperwork gaps the timeline extends. Apply early to absorb this.
- **First-user reputation curve** — even with a real cert, SmartScreen
  builds reputation on download counts. The first ~50-200 downloads
  may still trigger a milder warning. Reputation builds within days
  for an actively-released project.
- **AI BRANCH coverage** — single SignPath project covers both
  branches' release artifacts; no separate application needed.
- **EV vs OV** — SignPath provides an EV-equivalent for OSS, which
  gets instant SmartScreen reputation. If they switch to OV-only at
  some point, reputation curve gets longer. Worth monitoring their
  program terms.

## Open questions

- Who handles the SignPath application paperwork (maintainer time
  cost ~30-60 minutes for the form)
- What email / identity to register the SignPath account under (the
  GitHub `unexpear` identity is the natural fit)
- Whether to pre-sign older releases retroactively (probably no — too
  much overhead for releases users have already accepted unsigned)

## Not a commitment

This document captures direction. Application has not been submitted.
Update when application is filed and again when approved.

## Related

- [pyside6-migration-plan.md](pyside6-migration-plan.md) — decision
  #8 (SmartScreen story) → captured here.
- [release.bat](../release.bat) — the integration point for the new
  sign step.
- [README.md](../README.md) — the SmartScreen workaround paragraph
  gets rewritten when signing is live.
