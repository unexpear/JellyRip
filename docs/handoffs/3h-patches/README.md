# Phase 3h Patch Pack

> ⚠️ **HISTORICAL — superseded 2026-05-04.** These patches were
> pre-staged before Phase 3h actually executed. The retirement
> landed via direct edits per
> [`phase-3h-tkinter-retirement.md`](../phase-3h-tkinter-retirement.md),
> and the version bump landed on **v1.0.19** rather than v1.0.0.
> Kept as the original-plan record; do not apply now (the changes
> are already in the working tree).

**Purpose:** ready-to-apply diffs for the Phase 3h release, so the
deletes don't have to be re-derived after the Phase 3f manual smoke
clears.

**Order of application:**
1. Run the manual smoke per [`docs/release-process.md`](../../release-process.md)
   on a clean Windows venv.  If it fails, fix the spec **first**
   (don't apply this patch pack — it removes the tkinter fallback
   you'd need to keep limping along).
2. Apply each patch in this directory in any order.  They're
   independent of each other.
3. Re-run the test suite.  Re-run `build.bat`.  Re-walk the smoke
   on the post-delete bundle.
4. Bump version in [`shared/runtime.py`](../../../shared/runtime.py)
   (`__version__ = "1.0.0"`).
5. Run `release.bat 1.0.0` only on explicit user go-ahead.

**Files in this pack:**

| Patch | Target | What it does |
|-------|--------|--------------|
| `runtime-defaults.patch.md` | `shared/runtime.py` | Drop `opt_use_pyside6` key + comment block |
| `main-py-branch.patch.md` | `main.py` | Drop the feature-flag branch; Qt becomes the unconditional path |
| `jellyrip-spec.patch.md` | `JellyRip.spec` | Strip tkinter / Tcl-Tk bundling, hidden imports, runtime hook |
| `audit-set-empty.patch.md` | `tests/test_phase_3g_audit.py` | Empty `_LEGITIMATE_TKINTER_TOUCHING_TESTS` — audit becomes regression guard |
| `delete-list.md` | (filesystem) | Files / directories to delete outright |

**Already landed during 3h prep (no action needed):**

- `requirements.txt` — already updated 2026-05-04 to drop the
  tkinter comment and add `PySide6>=6.5`.
- `README.md` — already announces Qt as the shipping UI.
- `CHANGELOG.md` — already has the v1.0.0 entry.
- `docs/handoffs/phase-3h-release.md` — full brief with acceptance
  gate and definition of done.
