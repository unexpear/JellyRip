# PySide6 Migration Plan

**Status:** Approved direction (2026-05-02). Gated on workflow
stabilization per decision #2 below. v1-blocking per decision #4.
The eight open questions originally listed below now have answers —
see [Decisions Captured 2026-05-02](#decisions-captured-2026-05-02).
Migration code does not begin until the workflow stabilization gate
closes.

## Why

The current GUI layer is built on tkinter. [gui/main_window.py](../gui/main_window.py)
is the single largest source file in the repository (~7,800 lines), and
most of that bulk is layout, binding, and `tk.after()` polling glue
rather than product logic. Several capabilities the product wants are
either impossible or fragile under tkinter:

- **MKV preview before commit.** Confirming a selected title is the
  intended movie or episode before writing 30+ GB to disk requires a
  video widget tkinter does not provide. PySide6's `QtMultimedia`
  (`QMediaPlayer`) plays MKV directly. This is the single largest
  direct Jellyfin-outcome win available from a UI change, because the
  failure mode it prevents is *the wrong title gets ripped*.
- **AI chat sidebar UX (AI branch).** The sidebar in
  [gui/main_window.py](../gui/main_window.py) renders streamed AI
  responses inside a tkinter `Text` widget with manual tag-config for
  formatting. PySide6's `QTextBrowser` + `QTextDocument` render
  markdown, code blocks, and inline links natively. The current
  ceiling on chat UX quality is the widget, not the model.
- **Progress and stall visibility.** Multi-stage progress (scan →
  identify → rip → stabilize → validate → move → transcode →
  organize), per-task progress in a queue view, native Windows taskbar
  progress, and inline stall warnings on the bar itself are natural
  in Qt and cobbled-together in tkinter. Stall detection already
  exists in config; surfacing it well in the UI changes whether users
  notice and intervene before a hung MakeMKV writes a half-disc.
- **HiDPI on Windows.** Tkinter's mixed-DPI multi-monitor behavior is
  a known fight. Qt handles it natively.
- **Threading model.** MakeMKV streaming today flows through
  `tk.after()` polling against a queue. Qt replaces this with
  `QThread.signal -> slot` dispatch. Hundreds of lines of polling glue
  collapse to direct signal connections.
- **Native integrations.** Tray notifications on rip completion,
  drag-and-drop, splitter widgets, native file dialogs, dock panels,
  rich tooltips — all are built-in and thematically consistent in Qt.

## What changes

The migration touches the presentation layer only. In layered terms:

- **Layer 1** (MakeMKV, ffprobe, FFmpeg, HandBrake) — unchanged.
  [engine/ripper_engine.py](../engine/ripper_engine.py) and the
  scan/rip parsers are untouched.
- **Layer 2** (parsing, classifier, scoring, confidence) — unchanged.
  [utils/classifier.py](../utils/classifier.py),
  [utils/scoring.py](../utils/scoring.py), and the controller
  workflow in [controller/](../controller/) keep their contracts.
- **Layer 3** (UI surface) — replaced.

Concretely, the files in scope:

- All of [gui/](../gui/) is rewritten. Per-screen modules replace the
  `~7,800` line `main_window.py`. `secure_tk.py` deletes — its job is
  to wrap tkinter for safety and Qt has its own safety patterns.
- Most of [ui/](../ui/) — the UI adapters and dialog helpers are
  coupled to the tkinter event model and need new equivalents.
- The dark GitHub theme moves from tkinter color palette wiring to a
  QSS stylesheet. This is a code reduction, not a rewrite.
- The threading + event glue around MakeMKV streaming flips from
  `tk.after()` polling to Qt signals.

## What does not change

The architecture vision continues to apply: this is a Layer 3
investment, not a rewrite of the decision engine. Specifically:

- The "decision engine over MakeMKV" thesis is unchanged.
- The classifier, scoring, and confidence engine continue to live in
  `utils/`.
- The session workflow (scan -> classify -> setup -> rip -> transcode
  -> organize) is unchanged.
- All MakeMKV / ffprobe / FFmpeg integration is unchanged.

The behavior-first test layer (`test_behavior_guards.py`,
`test_imports.py`, `test_parsing.py`) survives the migration, since
those tests cover non-UI contracts. UI-touching tests (limited today
because tkinter is hard to test) gain `pytest-qt` as the canonical
harness — `qtbot.click`, `qtbot.waitSignal`, headless via the
offscreen platform plugin. This is a net coverage gain.

## Trade-offs

| Dimension | Today (tkinter) | After (PySide6) |
| --- | --- | --- |
| Bundle size | small | +80 to 150 MB |
| Cold launch | near-instant | a few hundred ms |
| Resident memory | ~30-60 MB | ~150-300 MB |
| HiDPI / native feel | fight | free |
| MKV preview | impossible | trivial |
| AI chat rendering | tkinter `Text` + tag-config | `QTextBrowser` + markdown |
| Threading glue | hundreds of `.after()` lines | native signal/slot |
| UI test ceiling | "can't really test" | `pytest-qt` real coverage |
| PyInstaller spec complexity | moderate | higher (Qt plugins) |
| SmartScreen false-positive surface | already an issue | larger binary, same signing path |
| Tester recognition of UI | familiar | effectively a new app |

## Risk: timing relative to pre-alpha

The README documents that TV / Movie / Dump All workflows are at "some
testing" maturity and that Organize Existing MKVs and FFmpeg /
HandBrake transcoding are "not tested." Migrating the UI while
workflow logic is still stabilizing produces two unstable surfaces at
once. Bug triage gets harder because failures can be attributed
either to a workflow change or to a port miss.

The conservative sequencing is: lock workflow behavior first, then
port the UI. The aggressive sequencing is: port now and use the new
UI to drive workflow stabilization (with the cost of having to
re-validate everything in the new framework).

This document does not pick a sequence. It records the trade-off so
the choice is explicit.

## Branch-specific notes

### MAIN

The MAIN README and [requirements.txt](../requirements.txt) state
that JellyRip ships with no external runtime dependencies and that
"All imports are standard library." That stance dies in this
migration. Whether MAIN should accept a heavyweight runtime
dependency is the headline question for this branch — not whether Qt
is technically a better framework. If MAIN exists primarily because
it is lean, the migration is in tension with its identity.

If MAIN exists primarily because it is "AI features stripped," the
identity question dissolves and the migration is fine.

### AI branch

The AI branch already ships with the Anthropic SDK and other
provider-side dependencies. The marginal dependency cost of PySide6
is much smaller. The user-visible upside is also concentrated here:

- `gui/ai_chat_sidebar.*` rendering quality is currently bottlenecked
  on the tkinter `Text` widget, not on the providers
- `gui/ai_provider_dialog.py` is a settings UI shaped exactly like a
  `QDialog` + `QFormLayout`
- AI-driven inline overrides (confidence sliders, alternate
  suggestions, undo) are natural in Qt and clumsy in tkinter

Because of this concentration, doing the AI branch first is a
defensible incremental plan: prove the migration on the branch where
it pays off most, then decide whether to follow on MAIN.

## Open questions

These need answers before scheduling, not before proposing.

1. **Scope.** Both branches at once, AI branch first, or MAIN only.
2. **Timing.** Before or after workflow stabilization. The pre-alpha
   risk argument cuts toward "after."
3. **Single-shot vs incremental.** Replace the whole UI in one
   release vs run tkinter and Qt screens side-by-side behind a flag
   during the transition.
4. **MKV preview as a forcing function.** If MKV preview is treated
   as a required feature for v1, the migration moves from "Someday"
   to a v1 dependency.
5. **Test rewrite policy.** Adopt `pytest-qt` for new UI tests; do
   existing tkinter-touching tests get rewritten or deleted in
   place.
6. **Theme parity.** QSS stylesheet that matches the current dark
   GitHub theme exactly, or take the migration as an opportunity to
   refresh the visual language.
7. **Distribution.** PyInstaller bundle structure, Inno Setup
   installer changes, and the SmartScreen story for a larger binary.

## Concrete capabilities unlocked

For reference when sizing the payoff:

- MKV preview before commit (catch wrong-title-selected before disk write)
- Per-task queue view with independent progress bars
- Multi-stage breadcrumb showing scan -> rip -> validate -> ...
- Native Windows taskbar progress overlay
- System tray completion notifications
- Stall warnings rendered on the progress bar itself
- Cancel button wired natively to thread interruption
- Markdown / code-block / streamed rendering in the AI chat sidebar
- Naming and folder-structure preview pane (what Jellyfin will see)
- Confidence sliders and inline override UI for classifier decisions
- Real HiDPI behavior on Windows multi-monitor setups

## Not a commitment

> **Update 2026-05-02**: This section is preserved for historical
> context, but the eight open questions have now been answered — see
> [Decisions Captured 2026-05-02](#decisions-captured-2026-05-02)
> below. The migration is approved direction, gated on workflow
> stabilization (decision #2), and v1-blocking (decision #4).

This document is a planning artifact. It does not authorize the
migration, set a date, or change current priorities. Workflow
stabilization, the test-coverage push, and shipping v1 take
precedence. Update this document when the open questions are
answered.

## Decisions Captured 2026-05-02

The eight open questions above received answers in a session on
2026-05-02. They are recorded here so the plan stops being
exploratory and so future contributors know what's settled vs. what
is still open.

| # | Question | Decision | Implication |
| --- | --- | --- | --- |
| 1 | Scope | **MAIN first** | AI BRANCH stays tkinter until MAIN's port is proven; AI BRANCH plan revisits after MAIN ships |
| 2 | Timing | **After workflow stabilization** | PySide6 code does NOT start now. Workflow stabilization (the README's "some testing" / "not tested" gates) closes first. **Concrete gate criteria** — what "workflow stabilization complete" actually means — are documented in [workflow-stabilization-criteria.md](workflow-stabilization-criteria.md). The migration is unblocked when every checkbox there is checked. |
| 3 | Single-shot vs incremental | **Single-shot. tkinter only where impossible — not just hard.** | No long-lived hybrid. The release that ships the port is the release that retires tkinter from MAIN. tkinter as fallback only for genuinely-unavailable Qt features (e.g., specific dialog types where Qt's equivalent is broken on Windows). |
| 4 | MKV preview as forcing function | **Yes — v1-blocking** | The migration moves from Someday to a v1 dependency. v1 ship requires PySide6 because v1 ship requires MKV preview before commit (catch wrong-title-selected before 30+ GB writes to disk). |
| 5 | Test rewrite policy | **pytest-qt for new UI tests; existing tkinter-touching tests get rewritten or deleted in place** | Behavior-first tests survive (state machine, parsers, event, pipeline state trajectory, app display name, etc.). UI-touching tests in `test_imports.py` and `test_main_window_formatters.py` get rewritten under pytest-qt or removed if the underlying widget is replaced wholesale. |
| 6 | Chat sidebar parity (AI branch) | **N/A in MAIN-first phase. Revisit when AI BRANCH port begins.** | Decision deferred to the AI BRANCH migration phase, which follows MAIN. |
| 7 | Theme parity | **Refresh — equipable theme system from day 1, 2-3 themes initial** | QSS supports multi-theme natively (`setStyleSheet(THEMES[name])`). Settings exposes a theme picker. Initial theme set: current palette ported as-is + inverted-primary variant (closes UX/A11y Finding #2 contrast bug via design pattern) + one lighter or warmer variant TBD. Themes live as separate `qss/*.qss` files, easier to iterate than embedded color constants. |
| 8 | SmartScreen / signing | **Stay unsigned. README workaround documented.** *(Updated 2026-05-02 after maintainer's review of the legal-identity-verification requirement common to all code-signing paths — including the free SignPath.io OSS program. Decision: not signing.)* | Releases continue to ship unsigned. The existing README paragraph documenting the "whitelist the download folder" SmartScreen workaround is the user-facing contingency. Revisit if/when project maturity warrants forming a legal entity (LLC etc.) under which signing becomes a different decision. Full rationale in [code-signing-plan.md](code-signing-plan.md). |

**Status update flowing from these decisions:**
- This plan moves from `Status: Proposed` to `Status: Approved direction, gated on workflow stabilization`.
- The `TASKS.md` PySide6 entry moves from Someday to Active.
- The framework-limited items in [ux-copy-and-accessibility-plan.md](ux-copy-and-accessibility-plan.md) ("Items that wait for PySide6") now have a definite future home rather than indefinite Someday.
- Code signing gets its own planning artifact in [code-signing-plan.md](code-signing-plan.md).

**What's still NOT decided** (will need answers when the gate
opens):
- Workflow stabilization completion criteria — what counts as "done"
- Concrete schedule (start date, milestone breakdown)
- Whether the migration version bump is v0.x → v1.0 (the natural cut)
  or some intermediate version
- Lighter/warmer theme variant — specific palette
- AI BRANCH port timing relative to MAIN's release
