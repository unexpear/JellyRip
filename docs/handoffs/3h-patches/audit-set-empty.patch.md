# Patch — `tests/test_phase_3g_audit.py`

Empty `_LEGITIMATE_TKINTER_TOUCHING_TESTS` — after Phase 3h, no
test file should touch tkinter, and the audit becomes a regression
guard.

## Find (around lines 25-50)

```python
# The exhaustive list of tests that legitimately touch tkinter.
# Each entry is justified in
# ``docs/handoffs/phase-3g-test-audit.md`` and gets deleted (or
# its specific tkinter test gets removed) in Phase 3h alongside
# ``gui/``.
_LEGITIMATE_TKINTER_TOUCHING_TESTS: frozenset[str] = frozenset({
    # Imports the tkinter gui module via _FakeTkBase patch — pinned
    # because the tkinter side is still load-bearing until Phase 3h.
    "test_imports.py",
    # Source-text introspection of gui/setup_wizard.py.  Doesn't
    # actually construct tkinter widgets.
    "test_label_color_and_libredrive.py",
    # Exercises pure helper methods on the tkinter GUI class via
    # object.__new__ — no actual widget construction.
    "test_main_window_formatters.py",
})
```

## Replace with

```python
# After Phase 3h, no test file should touch tkinter.  This audit
# now acts as a regression guard: if a new test imports tkinter,
# the assertion in ``test_no_unexpected_tkinter_touching_tests``
# below will fail with the file name surfaced.
_LEGITIMATE_TKINTER_TOUCHING_TESTS: frozenset[str] = frozenset()
```

## Also drop

`test_legitimate_tkinter_files_still_present` (around lines
107-118) becomes meaningless when the set is empty — delete it.

## Verification

* `pytest tests/test_phase_3g_audit.py` — should still pass (the
  no-unexpected check now expects the empty set).
* If anything fails, the failure message will name the test file
  that needs to be deleted or rewritten.
