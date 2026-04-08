"""Media file selection helpers."""

import os
from collections.abc import Sequence


def select_largest_file(files: Sequence[str]) -> str | None:
    if not files:
        return None
    largest: str | None = None
    largest_size = -1
    for path in files:
        try:
            size = os.path.getsize(path)
        except OSError:
            continue
        if size > largest_size:
            largest = path
            largest_size = size
    return largest
