# SignPath.io OSS Program — Application Draft

> ⚠️ **Status: Not for submission (2026-05-02).** The maintainer
> decided same-day to defer code signing indefinitely after
> reviewing the legal-identity-verification requirement common to
> all code-signing paths. See
> [code-signing-plan.md](code-signing-plan.md) for the decision and
> rationale. **This document is preserved as paste-ready text in
> case the decision is revisited later** (e.g., after forming a
> legal entity that makes signing a different calculus). Do not
> submit this in its current state — the maintainer has chosen not
> to.

Companion to [code-signing-plan.md](code-signing-plan.md). Originally
written as prep work for a SignPath.io OSS program submission; now
preserved as reference text only.

## Where to submit

SignPath.io's OSS program lives at: **<https://signpath.io/foundation/>**
*(verify URL is current at submission time — programs occasionally rebrand)*.

Click "Apply" / "Submit project for free signing" / similar. The form
will ask for the categories of information laid out below. **Field
labels may differ from this draft's section names** — match by intent,
not by exact wording.

## Before you start the form — gather these

| Item | Where it comes from | Notes |
| --- | --- | --- |
| Maintainer real name (legal) | YOU | SignPath needs a real identity, not just a GitHub handle. Used for cert ownership records. |
| Maintainer email | YOU | Use one tied to the project. `michaelbarlow333@gmail.com` per memory if that's still right. |
| GitHub username | `unexpear` | Already public on the repo |
| Project URL | <https://github.com/unexpear/JellyRip> | Already public |
| License URL | <https://github.com/unexpear/JellyRip/blob/main/LICENSE> | GPL-3.0-only |
| Latest release URL | <https://github.com/unexpear/JellyRip/releases/tag/v1.0.19> | Already public |
| Description (one paragraph) | See *Project description* below | Paste-ready |
| Why you need signing (short reason) | See *Use case* below | Paste-ready |
| Build platform | GitHub Releases via `release.bat` (PyInstaller + Inno Setup) | Already documented |

The two items only YOU can provide are **legal name** and **email**.
Everything else is paste-ready below.

## Paste-ready paragraphs

### Project name

```
JellyRip
```

### Project URL

```
https://github.com/unexpear/JellyRip
```

### License

```
GPL-3.0-only
```

### Project description (paragraph)

> Adapt the wording slightly if the form asks for shorter / longer.

```
JellyRip is a Windows-first desktop application that uses MakeMKV
and ffprobe to rip Blu-ray and DVD discs, validate the output with
container-integrity checks, and organize the resulting MKV files
into a Jellyfin-friendly library structure. It is licensed under
GPL-3.0-only, written in Python 3.13+, and distributed as a
PyInstaller-built JellyRip.exe and an Inno Setup installer through
GitHub Releases. The project is currently pre-alpha with an active
release line at v1.0.19; releases ship from a strict, fail-fast
release pipeline (release.bat) that gates on git state, version
consistency across multiple files, and successful test runs before
publishing.
```

### Why code signing is needed (use case)

```
Releases are currently unsigned. Windows SmartScreen flags new
PyInstaller-built binaries as unrecognized publishers, which forces
end users to whitelist the download folder before running the app —
a hostile UX especially for non-technical users (Jellyfin's primary
audience). The project is also planning a migration to PySide6 for
its v1 release, which will increase the bundled binary size by
roughly 80-150 MB; without signing, SmartScreen reputation builds
slower on larger novel binaries, making the warning friction worse
exactly when v1 lands.

Signing via the SignPath OSS program would let JellyRip ship signed
artifacts from each release without taking on a commercial cert's
ongoing cost — appropriate for a single-maintainer GPLv3 project
that is not commercialized and has no funding stream for code
signing.
```

### How signing integrates (technical)

```
The release pipeline is automated through release.bat, which runs:
git verify → tests → version consistency check → PyInstaller build
→ Inno Setup installer build → output verification → push → GitHub
release publication. The SignPath signing step would slot in
between the build and the output-verification step, signing both
JellyRip.exe and JellyRipInstaller.exe before the GitHub release is
published.

Releases are infrequent (manual trigger; ~weekly to monthly
cadence). Artifact size is currently around 60 MB per build, rising
to roughly 130-180 MB after the PySide6 migration completes.
```

### Maintainer information

```
Maintainer: <FILL IN — your real name>
Email: <FILL IN — your project email>
GitHub: unexpear
Project URL: https://github.com/unexpear/JellyRip
Identity verification: GitHub profile + commit history under the
unexpear account; project commits and releases are made from this
identity.
```

### Project activity evidence

> SignPath wants assurance the project is real and maintained, not
> abandoned. This paragraph is paste-ready but verify the numbers
> aren't stale at submission time.

```
JellyRip has an active release cadence with the v1.0.19 release
shipped in 2026 and a release pipeline that enforces a green test
suite (currently 825+ passing tests) and clean working tree before
publishing. Recent commits address user-visible UX consistency
(product-name normalization), test coverage expansion (state
machine, controller integration, makemkvcon stdout parsing), and
planning artifacts for the PySide6 migration. The repository's
README, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md, and
THIRD_PARTY_NOTICES.md are all maintained.
```

### Optional fields you might be asked

| Field | Suggested value |
| --- | --- |
| **Are you the legal owner / authorized signer?** | Yes (you are the project's sole maintainer) |
| **Funding / commercial revenue?** | None. Project is non-commercial, GPLv3, single-maintainer. |
| **Number of contributors?** | One primary maintainer (you), as `unexpear`. |
| **Estimated number of signed releases per year?** | 12-24 (rough range — adjust to your actual cadence; over-estimate is fine, signing is per-release, not per-year capped) |
| **Will you accept SignPath's CI/CD signing (private key never leaves their servers)?** | Yes. This is more secure than holding a private key in CI yourself. |
| **Any prior code-signing certificates?** | None. (Unless you have one — fill in if so.) |

## What happens after you submit

Per [code-signing-plan.md](code-signing-plan.md):

1. SignPath manually reviews OSS applications. Typical timeline:
   **1-2 weeks**.
2. They may follow up with email questions (project-identity
   verification, license confirmation, etc.) — answer promptly to
   keep the clock running.
3. On approval, you'll receive credentials to integrate signing into
   your CI / `release.bat`. The integration is a single shell step
   between PyInstaller build and GitHub publish.
4. Test the signing on a pre-release tag before next real release.
5. Update README to drop the "whitelist the download folder"
   workaround once signed builds are flowing.

## Risks and contingencies

- **If application is rejected** (uncommon for clean OSS projects):
  document the reason, address what they flagged, and resubmit.
  Common reasons: unclear ownership, missing license file (you have
  one), inactive project (you don't have this issue).
- **If review takes longer than 2 weeks**: ping their support. The
  workflow-stabilization-then-PySide6 timeline has weeks of slack;
  this isn't blocking.
- **If SignPath OSS terms change** (paid-only, sunset, etc.): the
  contingency is a commercial cert (~$200-700/yr). Documented in
  [code-signing-plan.md](code-signing-plan.md) under "Risks and
  unknowns."

## Open items the maintainer must decide

These are NOT in the paste-ready text — you decide before submitting:

- **Real name on the application.** SignPath wants legal identity,
  not just `unexpear`. Provide your real name as it appears on
  ID-verifiable documents (passport, driver's license, etc.). They
  do NOT publish your real name on the cert; it's used for
  internal identity verification.
- **Project email.** Use one tied to the project (per memory:
  `michaelbarlow333@gmail.com` is your contact email; confirm
  whether that's the right address to use for SignPath
  correspondence, or whether you want a project-specific address).
- **Identity verification path.** SignPath may ask for additional
  proof (e.g., a 2FA-able GitHub account that has owned the repo
  for some duration, a public maintainer page, etc.). The
  `unexpear` account on `github.com/unexpear/JellyRip` should
  satisfy this, but be prepared for a follow-up email.

## What this document is NOT

- It is **not** an authorization to submit. You read this, decide
  the paragraphs are accurate, fill in your real name + email,
  paste into SignPath's form, and submit yourself.
- It is **not** a contract. SignPath's OSS terms are theirs, not
  inferable from this draft.
- It is **not** a guarantee of approval — but for a single-
  maintainer GPLv3 Python project with a public repo, an active
  release cadence, and a documented use case, approval is the
  expected outcome.

## When this document gets deleted

Delete this draft after the application is submitted and approved
(say a year out, when re-applying isn't a near-term concern). Keep
it under git as a historical artifact in the meantime, in case the
application has to be resubmitted for any reason and you want a
reference for the wording.
