"""Media file selection helpers."""

import os


def select_largest_file(files):
    if not files:
        return None
    largest = None
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
