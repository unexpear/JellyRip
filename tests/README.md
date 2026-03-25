# JellyRip Test Suite

Automated tests for JellyRip core functions.

## Running Tests

**Prerequisites:**

```bash
pip install pytest
```

**Run all tests:**

```bash
pytest
```

**Run specific test file:**

```bash
pytest tests/test_parsing.py
```

**Run with verbose output:**

```bash
pytest -v
```

**Run and stop on first failure:**

```bash
pytest -x
```

## Test Coverage

| Module | Tests | Status |
| ------ | ----- | ------ |
| `safe_int()` | 8 | ✓ Core parsing |
| `parse_duration_to_seconds()` | 11 | ✓ Duration parsing |
| `clean_name()` | 6 | ✓ Filename sanitization |
| `make_temp_title()` | 4 | ✓ Temp naming |

## Missing Coverage

The following areas are **not yet tested**:

- GUI components (tkinter)
- MakeMKV subprocess integration
- File I/O operations
- Configuration loading/saving
- Threading behavior
- Full end-to-end rip workflows

These would benefit from integration tests or manual testing.

## Adding Tests

1. Create test file in `tests/test_*.py`
2. Use `class Test*` for test grouping
3. Use `def test_*` for individual test cases
4. Run `pytest` to execute

Example:

```python
def test_my_function():
    from JellyRip import my_function
    assert my_function(5) == 10
```

## CI/CD

Not yet configured. To add:

- GitHub Actions workflow (`.github/workflows/test.yml`)
- Run `pytest` on each push
- Report coverage

See [TODO in CHANGELOG.md](../CHANGELOG.md) for future enhancements.
