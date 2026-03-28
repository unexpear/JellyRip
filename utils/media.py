"""Media file selection helpers."""

import os


def select_largest_file(files):
    if not files:
        return None
    return max(files, key=os.path.getsize)
