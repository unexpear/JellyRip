# Handoff Brief — Phase 3a: PySide6 Scaffolding + Theme System (MAIN)

**For:** a fresh Claude Code session in the JellyRip MAIN repo.
**Author:** Claude (handoff written 2026-05-03).
**Phase reference:** Sub-phase 3a in `docs/migration-roadmap.md`.

---

## 📌 3a-themes update — 2026-05-03 (post-scaffolding)

The original brief below assumed **3 themes** (`dark_github`,
`light_inverted`, `warm`). User delivered design mockups on
2026-05-03 with **6 themes**. Scope of 3a-themes (the un-done part of
this brief) has changed accordingly.

**Source of truth for the new theme set:**
[`../design/themes/README.md`](../design/themes/README.md) — index
linking to `themes.jsx` (token tables), `qt-mock.jsx` (layout),
`styles.css` (recipe), `theme-preview.html` (browsable preview),
`../design/symbol-library.md` (button glyphs).

**The 6 themes:**

| id | Family | Notes |
|----|--------|-------|
| `dark_github` | dark | Current tkinter palette, default |
| `light_inverted` | light | Forest-green primary, no purple, closes A11y Finding #2 |
| `dracula_light` | light | Pale lavender bg, Dracula CTAs |
| `hc_dark` | dark | Pure black, AAA contrast on every CTA |
| `slate` | dark | Desaturated cool-only neutrals |
| `frost` | dark | Nord with saturation dialed up |

**Steps in this brief that are now superseded** (read this section
instead, then return to the original brief for context only):

- **Step 3 (directory listing)** — `gui_qt/qss/` should end up with
  six files: `dark_github.qss`, `light_inverted.qss`,
  `dracula_light.qss`, `hc_dark.qss`, `slate.qss`, `frost.qss`. The
  empty `warm.qss` placeholder created during scaffolding gets
  **deleted**.
- **Step 6 (theme writeup)** — Don't hand-author colors. Translate
  the `tokens` object for each theme in `themes.jsx` into QSS by
  binding the role keys (bg / card / fg / accent / go / info / alt /
  warn / danger / hover / selection / logBg / promptFg / answerFg /
  shadow) to QSS selectors. The role-to-objectName mapping is
  implicit in `qt-mock.jsx`; the `confirmButton` / `primaryButton`
  objectName split already in use in `gui_qt/setup_wizard.py` maps
  to the `go` role.
- **Step 8 (cfg keys)** — `opt_pyside6_theme` already exists. Widen
  its allowed-values set from 3 → 6 (or remove the validator if
  it's discoverability-driven via `gui_qt.theme.list_themes()`).
- **Step 9 (tests)** — Assertion "list_themes returns the 3 expected
  names" becomes 6. WCAG contrast pin needs to cover every CTA in
  every theme, not just `light_inverted` primary. `themes.jsx`
  ships a `wcagRating` helper used in the design preview — pin the
  same grading in Python.
- **Definition of done** — first three checkboxes scale to 6 themes;
  WCAG pin covers every CTA in every theme; smoke test launches
  each of the 6.

**What's still correct in the original brief:** the directory
structure (`gui_qt/qss/` location), `gui_qt/theme.py` shape,
`gui_qt/app.py` shape, the feature-flag wiring in `main.py`, the
branch identity guardrails, the scope-discipline section. None of
those change.

**CSS bits that don't translate cleanly to QSS** (polish, not
blockers): `color-mix(in oklab, …)` for darkened button borders
(pre-bake the values), `::before` gradient sheens (skip or use
`QGraphicsEffect`), keyframe animations like the LED pulse and the
180° rotate-on-active refresh button (use `QPropertyAnimation` or
omit), CSS `transition` (Qt has its own animation system; for v1
just snap state changes).

---

## ⚠️ READ FIRST — Gating

Per `docs/migration-roadmap.md`, Phase 3 is **gated on Phase 2 (real-disc
validation) closing**. As of this brief's writing, Phase 2 is still open.

**Before doing any work in this brief, ask the user:**

> "The migration roadmap says Phase 3 is gated on Phase 2 closing.
> Phase 2's real-disc validation checkboxes in `workflow-
> stabilization-criteria.md` sections 1-5 are still unchecked. Do you
> want me to proceed with Phase 3a anyway, or should I wait?"

Wait for explicit go-ahead. If the user says wait, write a brief
"standing by" message and stop. If they say proceed, continue.

The defensible reason to proceed in parallel: Phase 3a only adds new
code under a new `gui_qt/` directory. It does not modify any of `gui/`
or any workflow code, so it cannot create false bug attributions
during Phase 2.

---

## Goal

Add PySide6 scaffolding + theme system to MAIN, behind a feature
flag, with no actual workflow porting yet. When you're done:

- A user can launch JellyRip with `opt_use_pyside6=True` and see a
  themed empty PySide6 window
- A user can launch JellyRip with `opt_use_pyside6=False` (default)
  and see the existing tkinter UI unchanged
- The theme system is in place: 2-3 QSS files in `gui_qt/qss/`, a
  loader that reads the configured theme, runtime swap support
- No functional regression in the tkinter path

This is **scaffolding only**. No actual screens are ported. That's
sub-phase 3b's job.

## Branch identity guardrails — DO NOT VIOLATE

Repeated from `docs/migration-roadmap.md` because they're
non-negotiable:

1. **No AI features in MAIN, ever.** This branch must not import
   anything from `gui/ai_chat_sidebar*`, `controller/assist*`, or
   `shared/workflow_history*` (those don't exist on MAIN; if they
   appear, something is wrong).
2. **Both branches use the same QSS theme system.** When AI BRANCH
   ports later in Phase 4, it will reuse the `gui_qt/qss/*.qss`
   files you create here. Design accordingly — themes are about
   the base palette, not AI-feature styling.
3. **Branch-aware constants stay branch-aware.** Don't change
   `APP_DISPLAY_NAME` in `shared/runtime.py`. MAIN's value is
   `"JellyRip"`; that's correct on MAIN.
4. **No commits, pushes, tags, or `release.bat` runs without
   explicit user go-ahead.** Local edits only. Per
   `CLAUDE.md` working preferences.
5. **No "while we're here" refactors.** Don't modernize
   unrelated tkinter code "for cleanliness" — that creates
   migration debt and false-bug-attribution risk during Phase 2.

## Background — what's been done

This is one session in a multi-session migration. Read these in
order before doing any code work:

1. **`docs/migration-roadmap.md`** — the long view. All 4 phases.
2. **`docs/pyside6-migration-plan.md`** — original migration plan.
   The "Decisions Captured 2026-05-02" section has the answers to
   the 8 open questions. Decision #7 (equipable theme system) is
   directly relevant to this sub-phase.
3. **`experiments/pyside6_smoke/`** — 7-test toolchain validation
   from 2026-05-02. PySide6 6.11.0 installs cleanly, PyInstaller
   bundles work, QSS theming works. The toolchain is proven.
4. **`docs/workflow-stabilization-criteria.md`** — workflow-
   stabilization criteria. 6/6 cross-cutting closed; 0/5
   per-workflow real-disc sections closed (that's Phase 2).
5. **`shared/runtime.py`** — current cfg DEFAULTS dict; you'll add
   `opt_use_pyside6` and `opt_pyside6_theme` here.
6. **`main.py`** — current entrypoint, launches `JellyRipperGUI`
   from `gui/main_window.py`. You'll add a feature-flag branch.

## Concrete plan

### Step 1 — read the references above

Don't skip. The migration plan's decision rationale is load-bearing.

### Step 2 — install PySide6 in this venv

```bash
pip install PySide6
```

If `pip install` errors (network, permissions), stop and report —
don't try alternative install methods. The smoke test already proved
the toolchain; if it fails here, something environmental changed.

### Step 3 — create the directory structure

```
gui_qt/
  __init__.py            # empty for now
  app.py                 # QApplication entry point
  theme.py               # theme loader / swap logic
  qss/
    dark_github.qss      # current palette ported as-is
    light_inverted.qss   # inverted-primary variant (closes UX/A11y Finding #2)
    warm.qss             # third theme TBD — pick a sensible warm palette
```

`gui_qt/` is a sibling of `gui/`, NOT a child. The two trees coexist
during the migration; `gui/` is removed only after Phase 3 ships.

### Step 4 — implement `gui_qt/app.py`

Minimal QApplication entry point:

- Constructs `QApplication`
- Reads `opt_pyside6_theme` from cfg (default `"dark_github"`)
- Loads the selected QSS file via `gui_qt.theme.load_theme()`
- Constructs an empty `QMainWindow` titled `"JellyRip — PySide6 (scaffolding)"`
- Shows the window
- Runs the event loop

For now, this window is empty. Sub-phase 3b will start porting actual
screens.

### Step 5 — implement `gui_qt/theme.py`

A small theme loader:

```python
from pathlib import Path
from PySide6.QtWidgets import QApplication

THEME_DIR = Path(__file__).parent / "qss"

def list_themes() -> list[str]:
    """Return available theme names (without .qss extension)."""
    return sorted(p.stem for p in THEME_DIR.glob("*.qss"))

def load_theme(app: QApplication, theme_name: str) -> None:
    """Apply the named QSS theme to the running QApplication.
    Raises FileNotFoundError if the theme doesn't exist."""
    qss_path = THEME_DIR / f"{theme_name}.qss"
    if not qss_path.exists():
        raise FileNotFoundError(f"Theme not found: {theme_name}")
    app.setStyleSheet(qss_path.read_text(encoding="utf-8"))
```

Keep it small — sub-phase 3d will add the user-facing theme picker.

### Step 6 — write the three initial QSS themes

- **`dark_github.qss`** — port the current tkinter dark-GitHub
  palette. Read `gui/main_window.py` for the existing color
  constants and translate to QSS rules. Target widgets: `QMainWindow`,
  `QPushButton`, `QLabel`, `QLineEdit`, `QTextEdit`, `QListWidget`,
  `QComboBox`, `QProgressBar`. The base palette is what matters; you
  don't have to match every minor styling detail.
- **`light_inverted.qss`** — same palette but with primary buttons
  inverted (white background, blue text). This closes UX/A11y
  Finding #2's contrast bug via theme variant rather than per-widget
  patches. Verify WCAG 4.5:1 contrast on primary buttons before
  considering this done.
- **`warm.qss`** — pick a sensible warm/cream variant. Doesn't need
  to be perfect; sub-phase 3d may iterate. Target users: people who
  prefer warmer screens at night.

### Step 7 — wire `main.py`

Add the feature-flag branch:

```python
# At the top of main(), or wherever the GUI is launched:
if cfg.get("opt_use_pyside6", False):
    from gui_qt.app import run_qt_app
    return run_qt_app(cfg)
# else: existing tkinter path unchanged
```

The default is `False` so users see the existing tkinter UI unless
they explicitly opt in.

### Step 8 — add the cfg keys

In `shared/runtime.py` `DEFAULTS`:

```python
"opt_use_pyside6": False,
"opt_pyside6_theme": "dark_github",
```

Document them in any cfg-keys comment block that exists in
`shared/runtime.py`.

### Step 9 — write tests

Behavior-first, per migration plan decision #5:

- **`tests/test_pyside6_scaffolding.py`** — small. ~5-8 tests:
  - `gui_qt.theme.list_themes()` returns the 3 expected names
  - `gui_qt.theme.load_theme()` raises `FileNotFoundError` on bad name
  - `gui_qt.theme.load_theme()` succeeds on each of the 3 names (don't actually launch a window — patch `QApplication.setStyleSheet` to capture the loaded QSS)
  - `opt_use_pyside6` and `opt_pyside6_theme` are in `DEFAULTS`
  - WCAG contrast pin: `light_inverted.qss` primary-button colors meet 4.5:1 (use the same `_relative_luminance` / `_wcag_contrast_ratio` helpers from `tests/test_button_contrast.py`)
- Don't write a "launches the app" test yet — that needs `pytest-qt`,
  which is sub-phase 3g territory.

### Step 10 — verify

- `python -m pytest tests/test_pyside6_scaffolding.py -v` → all green
- `python -m pytest -q` → existing 978 passed / 1 skipped, plus your new tests, no regressions
- Manual smoke: edit `%APPDATA%/JellyRip/config.json` to set `"opt_use_pyside6": true`, run `python main.py`, confirm a themed empty PySide6 window appears. Edit back to `false`, confirm the tkinter UI launches normally.

## Stop-and-report protocol

After EVERY step above, write a status report to `STATUS.md` at the
repo root. Update format:

```markdown
# Phase 3a Status — [timestamp]

## Done
- Step N: <what landed, files touched>

## Working
- Step N+1: <what you're trying right now, if anything>

## Left
- Step N+2: <next step description>
- Step N+3: ...

## Blocked on
- (anything you need from the user, or "nothing" if smooth sailing)

## Suite state
- MAIN: <count> passed, <count> skipped
- AI BRANCH: not touched this session

## Notes for next session
- Any non-obvious findings, gotchas, design decisions.
```

**Update this file after each step, not just at the end.** If your
session crashes, runs out of context, gets interrupted, or you hit
a blocker that needs the user, the user can read `STATUS.md` to know
exactly where things stand.

## Scope discipline — what NOT to do

- **Do not port actual screens.** Setup wizard, main window, settings —
  all of those are later sub-phases (3b, 3c, 3d). Touching them here
  is scope creep and will create merge pain when the dedicated
  sub-phases run.
- **Do not modify `gui/` files.** The whole point of `gui_qt/`
  living alongside `gui/` is that they can coexist. You should be
  able to run a full `pytest` suite and have all 978 existing tests
  still pass.
- **Do not start the AI BRANCH port.** Phase 4 is gated on Phase 3
  shipping. Touching AI BRANCH here is wrong.
- **Do not add the theme picker UI.** That's sub-phase 3d's job.
  Just the loader + the QSS files for now.
- **Do not update `release.bat` / `build.bat` / `JellyRip.spec`.**
  That's sub-phase 3f's job.

## Definition of done

You're done with Phase 3a when ALL of the following are true:

- [ ] `gui_qt/` directory exists with the structure above
- [ ] All 3 QSS themes load without error
- [ ] `light_inverted.qss` primary-button contrast pinned at WCAG ≥ 4.5:1
- [ ] `opt_use_pyside6` and `opt_pyside6_theme` in DEFAULTS
- [ ] `main.py` feature-flag branch wires PySide6 path when flag is True
- [ ] Default behavior (flag False) is unchanged
- [ ] New test file passes
- [ ] Full suite green: 978 → 985-987 (depending on how many tests you add)
- [ ] Manual smoke test: PySide6 window appears with each of the 3 themes
- [ ] `STATUS.md` reflects this final state

When all 9 boxes are checked, write the final status report to
`STATUS.md` and stop. Do not start sub-phase 3b. The user reviews
3a before authorizing 3b.

## After this session

- The user reviews your `STATUS.md` and the new code
- If they're happy, they update `docs/migration-roadmap.md` to mark
  Sub-phase 3a as complete
- They request the next handoff brief (sub-phase 3b: port setup
  wizard) when ready

## Self-check before starting

Before writing any code, confirm to yourself:

- [ ] You've read `docs/migration-roadmap.md`
- [ ] You've read `docs/pyside6-migration-plan.md` "Decisions Captured 2026-05-02"
- [ ] You've checked Phase 2's gate status (read
  `workflow-stabilization-criteria.md` per-workflow sections — are
  any ticked yet?)
- [ ] You've asked the user about the gate per the "READ FIRST"
  section above, and gotten explicit go-ahead
- [ ] You understand the branch identity guardrails — especially #1
  (no AI features in MAIN, ever)

If any of these is no, stop and fix that before continuing.
