# Handoff Brief — Phase 4: PySide6 Port to AI BRANCH

**For:** a fresh Claude Code session in JellyRip **AI BRANCH** (the
fork at `unexpear-softwhere/JellyRipAI`), not MAIN.
**Phase reference:** Phase 4 in
[`docs/migration-roadmap.md`](../migration-roadmap.md).
**Predecessor:** Phase 3h (MAIN tkinter retirement) — done
2026-05-04, see
[`phase-3h-tkinter-retirement.md`](phase-3h-tkinter-retirement.md).
**Successor:** AI BRANCH v1.0 release (no further phases planned).
**User direction (2026-05-03):** *"AI BRANCH stays tkinter the whole
time MAIN is migrating. AI BRANCH gets ported in Phase 4."*

---

## ⚠️ READ FIRST

Before any edits, in this exact order:

1. [`docs/migration-roadmap.md`](../migration-roadmap.md) Phase 4
   section — the why behind sub-phase ordering.
2. [`docs/pyside6-migration-plan.md`](../pyside6-migration-plan.md)
   decisions #1 (MAIN-first) and #6 (chat sidebar parity revisit) —
   the upstream constraints this brief lives under.
3. [`docs/handoffs/phase-3h-tkinter-retirement.md`](phase-3h-tkinter-retirement.md)
   — what MAIN looks like *now* and what AI BRANCH is rebasing onto.
4. The AI BRANCH `gui/` directory — specifically
   `gui/ai_chat_sidebar.*`, `gui/ai_provider_dialog.py`, and any
   files referencing `controller/assist.py` or
   `shared/workflow_history.py`. These four are the AI surface that
   MUST survive the port.

This brief is the port plan. Sub-phases run sequentially; out-of-order
edits will break the suite mid-run.

## State entering this phase

### What MAIN ships today

After Phase 3h closed, MAIN is **Qt-only** with:

- `gui_qt/` package as the entire UI (six themes, MKV preview, drive
  scanner, setup wizard, status bar, log pane, tray icon, splash,
  toolbar, appearance settings tab).
- `tools/build_qss.py` generating `gui_qt/qss/*.qss` from a shared
  token table (`gui_qt/themes.py`).
- Thread-safe GUI marshaling layer (`gui_qt/thread_safety.py`).
- `WorkflowLauncher` with `validate_tools()` pre-flight gate
  surfacing friendly "MakeMKV not found" errors instead of cryptic
  `[Errno 2]` (closed 2026-05-04 evening, see
  [`tests/test_pyside6_workflow_launchers.py`](../../tests/test_pyside6_workflow_launchers.py)
  "Tool-path pre-flight" section).
- Log-line severity glyphs (`⚠ warn` / `✗ error`), drive-state
  glyphs (`◉ / ⊚ / ◌`), and the symbol library at
  [`docs/symbol-library.md`](../symbol-library.md).
- `OutputPlan` real tree widget (not a placeholder).
- All `.qss`-load failures normalized to `FileNotFoundError` so a
  corrupt or locked theme can't crash startup
  ([`gui_qt/theme.py`](../../gui_qt/theme.py)).
- `run_job(on_log=, on_progress=)` keyword forwarding so the
  controller's GUI hooks stay live during the rip
  ([`engine/ripper_engine.py`](../../engine/ripper_engine.py)).
- Required `-r` (robot mode) flag on every makemkvcon invocation
  ([`engine/rip_ops.py`](../../engine/rip_ops.py)).
- 1,608 tests green, full smoke report at
  [`docs/smoke-report-2026-05-04.md`](../smoke-report-2026-05-04.md).

### What AI BRANCH ships today

Pre-Phase-4: AI BRANCH is still **tkinter** with:

- `gui/` package as the UI (no `gui_qt/`).
- `gui/ai_chat_sidebar.py` — multi-line `Text` widget for chat
  rendering. Markdown / code blocks render as plain text per
  [`docs/pyside6-migration-plan.md:145`](../pyside6-migration-plan.md)
  ("rendering quality currently bottlenecked by tkinter").
- `gui/ai_provider_dialog.py` — provider selection / API key entry
  form, `ttk` widgets.
- `controller/assist.py` — identity-assist UI surfaces (confidence
  sliders, alternate suggestions, undo).
- `shared/workflow_history.py` — chat history persistence.
- Anthropic SDK runtime dependency (MAIN does not have this).
- `APP_DISPLAY_NAME = "JellyRip AI"` (MAIN: `"JellyRip"`).

### What changes between today and Phase 4 close

AI BRANCH absorbs ~all of MAIN's `gui_qt/` foundation, ports the four
AI-specific files into Qt, and ships v1.0 with the same UX/quality
bar MAIN has. **Nothing in MAIN changes** during Phase 4.

---

## Branch identity guardrails

Repeated from
[`docs/migration-roadmap.md`](../migration-roadmap.md). Non-negotiable
during Phase 4:

1. **No AI features in MAIN, ever.** Phase 4 is one-way: MAIN's
   gui_qt copies *into* AI BRANCH. Nothing AI-shaped goes back the
   other way.
2. **Preserve AI BRANCH's AI surface.** The chat sidebar must keep
   its current capability. The port improves rendering
   (`QTextBrowser` markdown), it does not strip features. If a
   feature requires deeper rework to port, document it as a follow-up
   — don't drop it silently.
3. **Test symmetry where it makes sense, divergence where it
   doesn't.** Both branches share most tests. Some test names
   already diverge (e.g. `test_workflow_coverage_audit.py`'s
   multi-candidate row for TV-disc). Preserve current divergence; do
   not align unless you have a specific reason.
4. **Both branches use the same QSS theme system.** AI BRANCH may
   add chat-specific styling, but the base palette matches MAIN.
   Themes live in `gui_qt/qss/*.qss` per migration plan decision #7.
5. **Branch-aware constants stay branch-aware.** `APP_DISPLAY_NAME =
   "JellyRip AI"` on AI BRANCH stays. Any user-visible string that
   differs between branches stays that way.
6. **No "while we're here" cross-branch cleanup.** The port isn't a
   refactor opportunity to homogenize. Stay on the migration goal.
7. **Git rules from `CLAUDE.md` still apply.** No commits, pushes,
   tags, or `release.bat` runs without explicit user go-ahead. Local
   file edits are fine.

---

## Sub-phase 4a — Rebase AI BRANCH on MAIN's PySide6 base

**Goal:** AI BRANCH ends this sub-phase with `gui_qt/` present,
`gui/` retired (matching MAIN's post-3h state), all of MAIN's
non-AI tests passing, and a clean baseline ready for the AI-feature
ports in 4b–4c.

**Estimated:** 2 focused Claude sessions (longer than MAIN's 3h
because of the merge complexity, not the work itself).

### Pre-flight checklist

Before opening any merge, verify:

- AI BRANCH suite is **green at HEAD** (`python -m pytest`). Don't
  start a port on a red branch.
- `git log` shows the AI-only commits AI BRANCH has accumulated
  while MAIN migrated. List them — those are the diffs that need
  resolution against MAIN's gui_qt files.
- The Anthropic SDK pin in AI BRANCH `requirements.txt` is current.
  PySide6 6.5+ pulls Qt 6 widgets that some older SDK versions
  conflict with — test in a fresh venv first if uncertain.

### Step 1 — Merge MAIN into AI BRANCH

```bash
git fetch origin
git checkout main      # AI BRANCH's main (which is the AI fork's main)
git merge origin/main  # pull MAIN's main into AI BRANCH's main
                       # OR: git rebase origin/main, depending on
                       # which the user prefers — ask before doing
                       # destructive history rewrites
```

Conflicts will land in:

- `controller/controller.py` — likely AI-feature-specific session
  state (workflow history, assist confidence) AI BRANCH has and
  MAIN doesn't. Resolve in favor of keeping AI features.
- `shared/runtime.py` — `APP_DISPLAY_NAME` and any AI-only DEFAULTS
  keys. Keep AI BRANCH values.
- `requirements.txt` — likely both forks added different deps.
  Combine — PySide6 from MAIN + Anthropic SDK from AI BRANCH.
- `JellyRip.spec` — PyInstaller spec. MAIN added Qt plugins +
  `gui_qt` hidden imports. AI BRANCH may have AI-only hidden
  imports. Combine.
- `tests/test_imports.py` — MAIN deleted the tkinter import test.
  AI BRANCH may still need its own. Re-add an AI-flavored version
  if needed.

**Do not** resolve conflicts by deleting AI files just because MAIN
doesn't have them. Re-read guardrail #1.

### Step 2 — Verify gui_qt loads with AI BRANCH's controller

After the merge resolves cleanly:

```bash
python -m pytest tests/test_pyside6_*.py -q
```

Most of these come from MAIN and exercise the gui_qt scaffolding.
They must pass without changes — if they don't, the merge dropped
something. Common drops:

- `gui_qt/qss/*.qss` files (binary-ish; some merge tools mishandle).
  Verify all six themes regenerate via `python tools/build_qss.py`.
- `gui_qt/__init__.py` exports.

### Step 3 — Retire AI BRANCH's `gui/` directory

Mirror what MAIN did in Phase 3h, but for the AI BRANCH set:

- Lift any shared dataclasses out of `gui/setup_wizard.py` into
  `shared/wizard_types.py` (already done in MAIN — confirm the file
  exists post-merge).
- **Do NOT delete `gui/ai_chat_sidebar.*`,
  `gui/ai_provider_dialog.py` yet** — those get ported in 4b/4c
  before deletion.
- Delete the rest of `gui/` per Phase 3h's deletion order.
- Remove tkinter-coupled tests as 3h did.

### Step 4 — Update `APP_DISPLAY_NAME` rendering

The Qt main window title bar currently reads `"JellyRip"` because it
came from MAIN. On AI BRANCH it must read `"JellyRip AI"`. Verify by
launching:

```bash
python main.py
```

Window title should be `"JellyRip AI"`. If it's wrong, the source
is `shared/runtime.py` — fix there, not in `gui_qt/main_window.py`
(branch-aware constants stay branch-aware per guardrail #5).

### Step 5 — Sub-phase 4a acceptance

- All MAIN-equivalent tests pass on AI BRANCH (excluding
  AI-specific suites still using tkinter — those get fixed in 4b/4c).
- `python main.py` launches the Qt window titled `"JellyRip AI"`.
- The chat sidebar is **broken** (still imports tkinter, won't
  render). That's expected — 4b ports it.
- The AI provider dialog is **broken** (same reason). 4c.
- No `gui.<retired-module>` imports anywhere in the live tree
  (grep confirms zero matches outside of git history).

---

## Sub-phase 4b — Port the chat sidebar to Qt

**Goal:** `gui_qt/ai_chat_sidebar.py` exists and replaces
`gui/ai_chat_sidebar.*` end-to-end. Markdown and code-block
rendering improves dramatically (the headline-feature reason MAIN
went Qt in the first place).

**Estimated:** 1–2 focused sessions.

### Why QTextBrowser + QTextDocument

Per [`docs/pyside6-migration-plan.md`](../pyside6-migration-plan.md)
decision rationale: tkinter's `Text` widget renders markdown as
literal text. QTextBrowser parses HTML/rich text natively, so a
markdown-to-HTML pipeline (e.g. `markdown` Python package, already
likely in deps for tkinter rendering) feeds the browser directly.
Code blocks get monospace styling for free; tables and lists
render as expected; copy-paste preserves formatting.

### Step 1 — Build the widget shell

`gui_qt/ai_chat_sidebar.py`:

- `QDockWidget`-shaped container so users can detach / re-dock the
  sidebar like every other Qt-native chat UI.
- Inside the dock: a `QSplitter` (vertical) with the chat
  `QTextBrowser` on top and an input `QPlainTextEdit` plus Send
  button on the bottom.
- Markdown rendering via `QTextDocument.setMarkdown(text)` (Qt 5.14+,
  zero extra deps).
- Streaming responses: provider returns chunks via Qt signal
  (`message_chunk_received(str)`); slot appends to the document.
  **Replaces tkinter's `after()` polling** — Qt signals are the
  native pattern.

### Step 2 — Wire the streaming pathway

The current tkinter pathway probably looks like:

```python
def on_chunk(text):
    self.text_widget.insert("end", text)
    self.text_widget.after(50, ...)  # poll for more
```

The Qt version is:

```python
class ChatSidebar(QDockWidget):
    chunk_received = Signal(str)

    def __init__(self):
        ...
        self.chunk_received.connect(self._on_chunk)

    @Slot(str)
    def _on_chunk(self, text: str) -> None:
        cursor = self._browser.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertMarkdown(text)
        self._browser.setTextCursor(cursor)
        self._browser.ensureCursorVisible()
```

The provider thread emits `chunk_received.emit(...)`; the slot runs
on the GUI thread. **No `after()` polling, no manual marshaling** —
Qt's signal/slot machinery handles the cross-thread hop.

### Step 3 — Theme integration

The sidebar **must** pick up the current QSS theme. Reuse the same
`objectName`s as MAIN's modules so the existing six QSS files don't
need to know about AI:

- `chatSidebarDock` for the dock widget.
- `chatBrowser` for the browser (inherits `QTextBrowser` styling).
- `chatInput` for the input field (inherits `QPlainTextEdit`).
- `chatSendButton` for the send button (inherits `QPushButton`).

If chat-specific styling is genuinely needed (e.g. user vs assistant
message backgrounds), add a single `chat-message-user` /
`chat-message-assistant` class via inline HTML — don't fork the QSS
files. Per guardrail #4: AI BRANCH may extend, not diverge from, the
base palette.

### Step 4 — Tests

Mirror the MAIN test pattern:
[`tests/test_pyside6_log_pane.py`](../../tests/test_pyside6_log_pane.py)
is a good template (similar widget shape — a streaming text view).

Specifically pin:

- Sidebar widget instantiates with no errors under `pytest-qt`.
- `chunk_received.emit("# Hello")` renders as an `<h1>` (assert via
  `browser.toHtml()` containing `<h1>`).
- Streaming multiple chunks accumulates correctly (no chunks lost).
- Markdown code blocks render with monospace font (assert via
  inspecting the document's character format).
- Send button click emits `message_sent(str)` with the input field
  text and clears the input.
- Theme switch (calling `app.setStyleSheet(...)` mid-life) doesn't
  break the rendered HTML.

### Step 5 — Sub-phase 4b acceptance

- Chat sidebar opens, accepts input, sends to provider, streams
  response back, renders markdown.
- Messages from a long previous session load via `workflow_history`
  without errors.
- All sidebar regression tests pass.
- `gui/ai_chat_sidebar.*` is deleted.

---

## Sub-phase 4c — Port the AI provider dialog + identity assist UI

**Goal:** `gui_qt/ai_provider_dialog.py` exists. Identity-assist
controls (confidence sliders, alternate suggestions, undo) live in
`controller/assist.py` UI surfaces ported to Qt widgets.

**Estimated:** 1 focused session.

### Provider dialog port

The `gui/ai_provider_dialog.py` is shaped like a settings form: a
provider dropdown, an API key field, an optional model dropdown,
and a Test Connection button. **`QDialog` + `QFormLayout` is the
right Qt shape** — matches the existing settings tabs in
[`gui_qt/settings/`](../../gui_qt/settings/).

Steps:

- New file `gui_qt/dialogs/ai_provider.py`.
- Mirror the field set from the tkinter version exactly.
- API key field → `QLineEdit` with `EchoMode.PasswordEchoOnEdit`.
- Test Connection button → fires the existing controller
  `test_ai_provider(provider, key)` method on a worker thread (use
  `gui_qt/thread_safety.py`'s `run_in_background` pattern, same as
  drive scan).
- Result lands in the dialog's status bar via signal.

### Identity assist surfaces

The assist UI lives inside the setup wizard's content-mapping step
on AI BRANCH. The tkinter version has:

- Confidence slider (0–100%) per identified episode/movie.
- "Alternate" dropdown showing other classifier candidates.
- "Undo" button rolling back the last assist suggestion.

Port locations:

- Confidence slider → `QSlider` with a value label, embedded in the
  same row of the content-mapping step as `gui_qt/setup_wizard.py`
  uses for episode rows on MAIN.
- Alternate dropdown → `QComboBox`, populated from the candidate
  list `controller/assist.py` already provides.
- Undo button → `QPushButton`, wired to the existing
  `assist.undo_last()` controller method.

### Tests

- Provider dialog opens, accepts input, fires Test Connection,
  renders result without crashing.
- Pre-existing API key (saved in config) pre-fills.
- Confidence slider in the wizard updates the controller state.
- Alternate dropdown selection swaps the row's classification.
- Undo button rolls back the last assist change (verify by
  asserting the controller state matches pre-change snapshot).

### Sub-phase 4c acceptance

- Provider dialog reachable from the toolbar (the same toolbar
  MAIN added in Tier 2).
- All four AI-specific UI surfaces work end-to-end against a real
  provider (you'll need an API key to truly verify — Claude can
  test with a mock).
- `gui/ai_provider_dialog.py` deleted.
- `controller/assist.py` UI references the Qt widgets, not tkinter.

---

## Sub-phase 4d — Test parity, smoke, release prep

**Goal:** AI BRANCH passes its full suite, smoke-tests cleanly on a
real `.exe` build, and is ready for `release.bat`.

**Estimated:** 1 session (mostly verification, not authoring).

### Test pass

```bash
python -m pytest -q
```

Target: same green-suite size as MAIN's 1,608 + whatever AI-specific
tests exist on AI BRANCH (probably 50–100 more). No tkinter
references in the live import tree (`tests/test_phase_3g_audit.py`
or its AI BRANCH equivalent enforces this).

### Smoke test

Run [`docs/handoffs/bot-smoke-test.md`](bot-smoke-test.md) against
the AI BRANCH `.exe`. Most sections are MAIN-shared; add three
AI-specific sections:

- **Chat sidebar smoke:** open sidebar, send "hello world", verify
  markdown response renders, verify the streaming animation looks
  smooth (no dropped chunks visible).
- **Provider dialog smoke:** open from toolbar, switch providers,
  Test Connection succeeds with a real key.
- **Identity assist smoke:** run a movie disc setup wizard, see
  confidence sliders populated, change one alternate, verify the
  output plan reflects the new classification.

### Release prep

- Bump `__version__` in `shared/runtime.py` to whatever AI BRANCH's
  next version is (likely `1.1.0` to mirror MAIN's milestone bump
  from 1.0.x to the Qt-only release).
- Update CHANGELOG.md with the AI-specific changes.
- Update `release_notes.md` and `release_notes.txt` (AI BRANCH has
  its own; the AI-fork-specific cousins on MAIN are
  `release_notes_ai.md` / `.txt` for reference, not for AI BRANCH
  to commit).
- Run `release.bat <version>` only on explicit user go-ahead.

---

## Failure modes & risk register

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Anthropic SDK conflicts with PySide6 6.5+ in same venv | Low | High (port stalls) | Test in fresh venv before merging; downgrade SDK if needed |
| `QTextBrowser.setMarkdown` renders differently from tkinter pseudo-markdown | Medium | Low (cosmetic) | Pin via tests; accept rendering changes as upgrades |
| Chat sidebar streaming looks janky on slow providers | Medium | Medium (UX) | Throttle `chunk_received` to ~20ms intervals; debounce |
| Identity assist undo loses state during the rebase | Low | High (data loss) | Run undo regression test before deletion; assert state matches pre-change snapshot |
| Theme QSS regenerates differently on AI BRANCH than MAIN | Very low | Low | `tools/build_qss.py` is deterministic; diff the QSS output as a smoke check |
| MAIN absorbs an AI feature by accident during merge | Low | Critical (breaks guardrail #1) | Code review every merged file; reject anything mentioning `assist`, `ai_chat`, `workflow_history`, or `anthropic` if it landed in a non-AI file |

---

## Acceptance criteria for Phase 4 close

All of:

- [ ] AI BRANCH `gui/` directory contains no tkinter UI files
      (matches MAIN's post-3h state).
- [ ] `gui_qt/ai_chat_sidebar.py` exists, renders markdown,
      streams chunks, integrates with the active QSS theme.
- [ ] `gui_qt/dialogs/ai_provider.py` exists, opens from the
      toolbar, handles provider selection + API key + Test
      Connection.
- [ ] Identity assist UI surfaces (slider, alternate, undo) work
      in the setup wizard.
- [ ] All MAIN-shared tests pass on AI BRANCH.
- [ ] AI-specific tests pass (chat sidebar, provider dialog,
      assist).
- [ ] No `from gui.<X>` imports remain (grep confirms).
- [ ] `python main.py` launches the Qt window titled
      `"JellyRip AI"`.
- [ ] `.exe` smoke test passes for chat + provider + assist
      sections.
- [ ] `__version__` bumped, CHANGELOG updated, release notes
      drafted.
- [ ] User has signed off on the rebuild and is ready for
      `release.bat`.

---

## References

- [`docs/migration-roadmap.md`](../migration-roadmap.md) — phase
  ordering, branch identity guardrails (canonical).
- [`docs/pyside6-migration-plan.md`](../pyside6-migration-plan.md)
  — original migration decisions including #1 (MAIN-first) and #6
  (chat sidebar parity).
- [`docs/handoffs/phase-3a-pyside6-scaffolding.md`](phase-3a-pyside6-scaffolding.md)
  — MAIN's 3a brief; the gui_qt foundation patterns AI BRANCH
  inherits.
- [`docs/handoffs/phase-3c-port-main-window.md`](phase-3c-port-main-window.md)
  — patterns for the toolbar, log pane, status bar.
- [`docs/handoffs/phase-3d-port-settings-tabs.md`](phase-3d-port-settings-tabs.md)
  — patterns for QDialog + QFormLayout (4c reuses these).
- [`docs/handoffs/phase-3e-mkv-preview.md`](phase-3e-mkv-preview.md)
  — patterns for QtMultimedia + signal/slot threading (4b reuses
  the threading patterns).
- [`docs/handoffs/phase-3h-tkinter-retirement.md`](phase-3h-tkinter-retirement.md)
  — exact deletion order, applies to 4a Step 3.
- [`docs/symbol-library.md`](../symbol-library.md) — glyph
  conventions; AI BRANCH inherits these unchanged.
- [`docs/smoke-report-2026-05-04.md`](../smoke-report-2026-05-04.md)
  — what MAIN looked like at 1.0 sign-off; AI BRANCH targets
  parity.

---

## How to use this brief

- **You** — re-read when starting a Phase 4 session, or when you've
  lost track of where in the port you are.
- **Claude (fresh session)** — read top to bottom before any edits.
  This brief is the contract for the port.
- **Both** — when something doesn't match this brief but seems
  right anyway, **stop and ask the user**. The guardrails exist
  because cross-branch drift was a real problem in past sessions.
