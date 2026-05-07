# Patch — `shared/runtime.py`

Drop the `opt_use_pyside6` feature flag and its comment block.
**Keep** `opt_pyside6_theme` — Settings consumes it.

## Find (around line 138-148)

```python
    # Phase 3a — PySide6 migration scaffolding.  Default
    # False so the existing tkinter UI is unchanged for users who
    # haven't opted in to the in-progress migration.  See
    # docs/migration-roadmap.md and docs/pyside6-migration-plan.md.
    "opt_use_pyside6": False,
    # Selected QSS theme name (without .qss extension).  Available
    # themes live under gui_qt/qss/.  Sub-phase 3d will add an
    # in-app picker; for now users edit config.json directly.
    "opt_pyside6_theme": "dark_github",
```

## Replace with

```python
    # Selected QSS theme name (without .qss extension).  Available
    # themes live under gui_qt/qss/.  Switchable from
    # Settings -> Themes.
    "opt_pyside6_theme": "dark_github",
```

## Also bump (around line 29)

```python
__version__ = "1.0.18"
```

→

```python
__version__ = "1.0.0"
```

## Verification

* Run the test suite — anything that depended on the flag will surface here.
* Search for stragglers: `grep -rn "opt_use_pyside6" .`
  Expect zero hits except in CHANGELOG / migration docs.
