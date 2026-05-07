# Handoff Brief — Computer-Use Bot Smoke Test for JellyRip

**For:** a fresh Claude Code (or Cowork) session that has access to the
`mcp__computer-use__*` tools.
**Goal:** drive a built `JellyRip.exe` (or `python main.py`) through
the manual smoke checklist in `docs/release-process.md` by simulating
clicks and keystrokes via computer-use, then write a pass/fail report.
**Predecessor:** Phase 3f (build scripts) — assumes a runnable
build exists.

---

## ⚠️ READ FIRST — Safety rails

This bot drives the user's REAL machine. There is no VM isolation
unless the user set one up themselves. **You are moving the user's
mouse and typing on their keyboard for real.** Treat with care.

### Hard rules

1. **Never click outside JellyRip's window.** If a screenshot shows
   a different app frontmost, STOP and ask the user to focus JellyRip.
2. **Never send keystrokes when the frontmost app is not JellyRip.**
   The `request_access` allowlist enforces this — but double-check
   before every input action by reading the screenshot.
3. **Never click any UAC / "Run as Administrator" prompt.** Windows
   blocks input to elevated processes anyway. Ask the user.
4. **Never close other apps** (browser, editor, etc.). Stay in scope.
5. **Pause and ask the user before each test section** (see "Test
   plan" below). Don't run the whole smoke autonomously without a
   checkpoint.
6. **Honor git rules from `CLAUDE.md`**: no commits, no pushes, no
   `release.bat`, even if asked through the UI.
7. **Save the report progressively.** Append after every section,
   not at the end — if the bot crashes, partial results survive.

### Kill switches (DUAL — both active)

1. **File-based abort.** Before every action, check if
   `C:\Users\micha\Desktop\STOP_BOT.txt` exists (use the `Read` tool
   or `Bash` `test -f`). If it exists, immediately:
   - Take a final screenshot
   - Append `**ABORTED by STOP_BOT.txt at <timestamp>**` to the report
   - Exit cleanly (do not call any more computer-use tools)
2. **In-chat abort.** Between every action, check the conversation
   for the user's word "stop" (case-insensitive). If they typed it,
   abort the same way.

The user creates `STOP_BOT.txt` from any other app on their machine
(File Explorer → New Text Document → rename) when they want to halt.
That works even if the JellyRip window has focus and they can't reach
the chat.

---

## Prerequisites the user must do BEFORE starting

Tell the user to do these and confirm before requesting access:

1. **Build the .exe** (`build.bat`) OR plan to run from source
   (`python main.py`). Either is fine — you'll smoke whichever
   they have ready.
2. **Close anything sensitive.** Banking, password manager, etc.
   Bot is going to be moving the mouse on their machine.
3. **Have `STOP_BOT.txt` ready to create** if needed. Don't create
   it now — just know where (`C:\Users\micha\Desktop\STOP_BOT.txt`).
4. **Confirm `%APPDATA%\JellyRip\config.json` exists.** The bot
   will edit it to flip `opt_use_pyside6`. If it doesn't exist,
   the user should launch JellyRip once first to create it.

If the user hasn't done these, ask before proceeding.

---

## Computer-use access request

Once prereqs are confirmed, call `mcp__computer-use__request_access`
with this exact list (these are the apps the bot needs):

```
apps: ["JellyRip", "Notepad", "File Explorer"]
reason: "Run the JellyRip smoke test from docs/release-process.md by
clicking through the GUI and verifying each step."
```

**Why each app:**

- `JellyRip` — the app under test
- `Notepad` — to open + edit `config.json` to flip `opt_use_pyside6`
  between paths
- `File Explorer` — to navigate to / verify temp folders if the test
  step needs it (otherwise can be skipped)

`clipboardRead` / `clipboardWrite` / `systemKeyCombos` are NOT needed.
Don't request them.

If the user denies any app, ask before proceeding — some test
sections may not be runnable without a denied app.

---

## Test plan (translates `docs/release-process.md` into bot actions)

Run sections in this order. After EACH section, post the section's
mini-report to the user (pass / fail per checkbox) and ask "OK to
continue to the next section?" before doing the next one.

### Section 1 — Tkinter path (default config)

1. Verify `config.json` has `"opt_use_pyside6": false` (or absent —
   default is false). Use `Read` tool, NOT computer-use, for the
   config file.
2. Launch JellyRip via `mcp__computer-use__open_application` with
   `app: "JellyRip"`, OR ask the user to double-click the .exe.
3. Wait 5 seconds (`mcp__computer-use__wait`) for window to appear.
4. Screenshot. Assert: window titled "JellyRip" visible.
5. Find the drive combo / dropdown in the screenshot. Click it.
   Screenshot. Assert: dropdown lists at least one drive (or "No
   drives" message — also OK on a machine without an optical drive).
6. Click any rip-mode button (e.g. "Smart Rip"). Screenshot. Assert:
   the workflow advances (a wizard step or input prompt appears).
   Cancel out (`Escape` or "Cancel" button) — don't actually rip.
7. Click "Settings". Screenshot. Assert: settings dialog opens.
   Click through each tab (Everyday, Advanced, Expert). Screenshot
   each tab. Cancel out.
8. Close JellyRip via the close button (X) or `Alt+F4`. Wait 2
   seconds. Screenshot. Assert: app exited cleanly (no zombie
   window).

**Result:** record per-step pass/fail in
`docs/smoke-report-<date>.md`.

### Section 2 — Switch to PySide6 path

1. Open `%APPDATA%\JellyRip\config.json` in Notepad via
   `mcp__computer-use__open_application`. Then click into the file,
   `Ctrl+A` to select all, type the new content with both flags
   set:
   ```json
   {
     "opt_use_pyside6": true,
     "opt_pyside6_theme": "dark_github"
   }
   ```
   (Preserve any other keys the file already had — read first via
   `Read` tool, then merge.)
2. Save (`Ctrl+S`). Close Notepad.

### Section 3 — PySide6 path basic launch

1. Launch JellyRip again. Wait 5 seconds.
2. Screenshot. Assert: PySide6 frame visible (different from
   tkinter — usually has Qt-style buttons / chrome).
3. Verify expected widgets appear:
   - Status bar at bottom
   - Log pane somewhere (usually right side or bottom)
   - Workflow buttons (Rip TV / Movie / Dump / Organize / Prep)
   - Utility chips (Settings / Updates / Copy Log / Browse Folder)
   - Stop Session button (red, disabled initially)
4. Read stderr for "Qt platform plugin missing" — if visible in any
   error overlay or console window, that's a fail.

### Section 4 — Theme picker (6 themes)

1. Click ⚙ Settings. Screenshot. Assert: Settings dialog opens.
2. Find the theme tab. Click it. Screenshot. Assert: 6 themes
   listed: `dark_github`, `light_inverted`, `dracula_light`,
   `hc_dark`, `slate`, `frost`.
3. For each theme:
   1. Click the theme name in the list.
   2. Click "Apply".
   3. Wait 1 second.
   4. Screenshot.
   5. Assert: window restyled (background / button colors changed
      visibly from previous theme — use the `zoom` tool on a known
      button to compare colors).
   6. Note the visible color shift in the report.
4. After all 6 themes tested, pick `dark_github` again, click OK.
5. Close + relaunch JellyRip. Verify the persisted choice loaded.

### Section 5 — Wizard structural smoke

1. With JellyRip running on PySide6 path, click "Rip Movie" (the
   one most likely to open the wizard).
2. The wizard should hit Step 1 (scan results). Without a real
   disc, it'll either error gracefully or show a "no titles" empty
   state — both are OK as long as it doesn't crash.
3. Cancel (`Escape`).
4. Screenshot the post-cancel state. Assert: app returned to main
   window, status reads "Ready" (or similar).

### Section 6 — Dialog smoke

For each of these, find a way to trigger from the UI (or note in
the report that it's not user-triggerable):

- **Show info / show error** — try invalid input somewhere (e.g.,
  empty title in organize flow) to provoke an error dialog.
- **ask_yesno** — most workflows have "Continue?" prompts.
- **ask_input** — title input at start of organize flow.

Skip the rest if they need disc-state to trigger (`ask_space_override`,
`ask_duplicate_resolution`, etc.). Note in the report.

### Section 7 — Skip MKV preview (needs real disc)

The `release-process.md` MKV preview section needs a real DVD/Blu-ray
in a real drive. The bot CAN'T do this in software-only testing.
Note in the report: "skipped — needs disc + drive."

### Section 8 — Failure modes

- **Corrupt QSS file** — temporarily move
  `gui_qt/qss/dark_github.qss` to `dark_github.qss.bak` (use `Bash`,
  not computer-use). Relaunch with `opt_pyside6_theme: dark_github`.
  Assert: app falls back to no stylesheet, doesn't crash. Restore
  the file.
- **Missing makemkvcon** — temporarily edit `config.json` to set
  `makemkvcon_path` to a bogus path. Relaunch. Click drive scan.
  Assert: app logs the error, falls back to placeholder. Restore.
- **Workflow exception** — hard to provoke deterministically; skip
  unless you can think of a reliable trigger.

### Section 9 — Restore + cleanup

1. Restore `config.json` to its original state (or set
   `opt_use_pyside6: false` so the user gets the tkinter UI by
   default after testing).
2. Restore any moved/renamed files.
3. Take a final screenshot. Assert: app at clean default state.
4. Close JellyRip.

---

## Reporting

Write the report to `docs/smoke-report-<YYYY-MM-DD>.md`. Format:

```markdown
# Smoke Report — <date>

**Build under test:** <e.g. JellyRip.exe v1.0.19 + Phase 3 ports>
**Bot:** Claude (computer-use)
**Started:** <timestamp>

## Section 1 — Tkinter path

- [x] App launches
- [x] Drive list populates
- [ ] **Settings tabs render** — FAIL: Advanced tab shows empty
      content (screenshot: section1-step7-advanced.png)
- ...

## Section 2 — Switch to PySide6
...

(continue per section)

## Summary

- Total checks: 37
- Passed: 33
- Failed: 2
- Skipped (need disc / out of scope): 2

## Failures requiring attention

1. **Settings → Advanced tab empty** (Section 1, step 7)
   - Screenshot: `docs/smoke-screenshots/section1-step7.png`
   - Reproduction: launch tkinter path, click Settings, click Advanced
   - Suggested next step: ...

## Aborted? No / Yes (reason)
```

Save screenshots to `docs/smoke-screenshots/<section>-<step>.png` for
every failure (use `mcp__computer-use__screenshot` with
`save_to_disk: true`).

---

## Don't do these things

- **Don't run an untested build.** If the user hasn't done a fresh
  `build.bat`, ask before testing. Smoke-testing a stale build is
  misleading.
- **Don't mark something passing on a partial screenshot.** If the
  state is ambiguous, ask the user "does this look right?" rather
  than guess.
- **Don't try to fix bugs you find.** This is a smoke session, not
  a code session. Record findings, hand off to a fix session.
- **Don't run the whole 9 sections without checking in.** After
  each section, post the mini-report and ask the user before
  continuing. They might want to investigate one issue before
  moving on.
- **Don't escalate scope.** If the user asks during the smoke for
  things outside testing (e.g., "while you're there, fix the
  layout"), say no and offer to file it as a follow-up after the
  smoke completes.

---

## Estimated runtime

- Section 1 (tkinter smoke): ~5 min
- Section 2 (config flip): ~1 min
- Section 3 (PySide6 launch): ~5 min
- Section 4 (6 themes): ~10 min
- Section 5 (wizard): ~3 min
- Section 6 (dialogs): ~5 min
- Section 7 (skip MKV): ~0 min
- Section 8 (failure modes): ~10 min
- Section 9 (cleanup): ~3 min

**Total: ~40-45 min** with screenshots. Add user-checkpoint pauses
between sections — typically 1-2 min each, so realistic total
**~55-65 min** of wall-clock time.

---

## What this brief doesn't cover

- **Visual quality assessment.** Bot can verify "the dark_github
  theme produced different colors than light_inverted" but can't
  tell the user "the dark_github theme looks pleasant." Reserve
  that for human review of the screenshots.
- **Real-disc validation.** Phase 2 of the migration roadmap needs
  the user with a disc. Bot doesn't help there.
- **Performance / responsiveness.** Bot doesn't measure latency
  or smoothness. If the UI feels janky to the bot's wait timeouts
  (e.g., a dialog takes >5 seconds to render), that's worth a note
  in the report.
- **Cross-monitor / DPI testing.** Bot tests one monitor at the
  current DPI. If the user has multi-monitor or HiDPI concerns,
  that's a separate manual session.

---

## Hand off back to the user

When the smoke is complete (or aborted), post a final summary:

- Pass/fail counts
- Top 3 failures (if any) with reproduction
- Pointer to the saved report file
- Recommendation: ship / fix-then-ship / don't ship

Then stop. The user reviews the report and decides what to fix
before v1.
