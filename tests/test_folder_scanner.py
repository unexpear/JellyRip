from pathlib import Path

from tools.folder_scanner import FolderScanEntry, classify_entry, scan_folder


def _entry(*, name: str, path: str, is_dir: bool) -> FolderScanEntry:
    return {
        "name": name,
        "path": path,
        "relative_path": name,
        "size": 0,
        "size_str": "0 bytes",
        "is_dir": is_dir,
        "bad_name": False,
        "parent": None,
        "status": "WEIRD",
        "modified_ts": 0.0,
        "modified_str": "n/a",
        "duration_seconds": None,
        "duration_str": "n/a",
    }


def test_classify_entry_detects_raw_disc(tmp_path: Path) -> None:
    disc_dir = tmp_path / "Movie Disc"
    (disc_dir / "BDMV").mkdir(parents=True)

    status = classify_entry(_entry(name=disc_dir.name, path=str(disc_dir), is_dir=True))

    assert status == "RAW DISC"


def test_scan_folder_marks_named_file_as_ok(tmp_path: Path) -> None:
    movie_file = tmp_path / "Movie Name (2024).mkv"
    movie_file.write_bytes(b"x" * 1024)

    results = scan_folder(str(tmp_path))

    file_entry = next(entry for entry in results if entry["path"] == str(movie_file))
    assert file_entry["status"] == "OK"
    assert file_entry["bad_name"] is False


def test_scan_folder_marks_multi_mkv_directory_as_raw_rip(tmp_path: Path) -> None:
    rip_dir = tmp_path / "Rip Folder"
    rip_dir.mkdir()
    (rip_dir / "title00.mkv").write_bytes(b"x" * 1024)
    (rip_dir / "title01.mkv").write_bytes(b"y" * 2048)

    results = scan_folder(str(tmp_path))

    dir_entry = next(
        entry for entry in results if entry["is_dir"] and entry["path"] == str(rip_dir)
    )
    assert dir_entry["status"] == "RAW RIP"


def test_scan_folder_bad_names_mode_sorts_alphabetically(tmp_path: Path) -> None:
    (tmp_path / "Zulu.mkv").write_bytes(b"x" * 1024)
    (tmp_path / "Alpha.mkv").write_bytes(b"y" * 2048)

    results = scan_folder(str(tmp_path), mode=2)

    assert [entry["name"] for entry in results] == ["Alpha.mkv", "Zulu.mkv"]


def test_scan_folder_recursive_file_only_excludes_directory_rows(tmp_path: Path) -> None:
    nested = tmp_path / "Disc 1"
    nested.mkdir()
    movie_file = nested / "Movie Name (2024).mkv"
    movie_file.write_bytes(b"x" * 1024)

    results = scan_folder(str(tmp_path), include_dirs=False)

    assert [entry["path"] for entry in results] == [str(movie_file)]
    assert all(entry["is_dir"] is False for entry in results)


def test_scan_folder_non_recursive_stays_in_selected_folder(tmp_path: Path) -> None:
    top = tmp_path / "Top Movie (2024).mkv"
    nested_dir = tmp_path / "Nested"
    nested_dir.mkdir()
    nested = nested_dir / "Nested Movie (2024).mkv"
    top.write_bytes(b"x" * 1024)
    nested.write_bytes(b"y" * 1024)

    results = scan_folder(str(tmp_path), include_dirs=False, recursive=False)

    assert [entry["path"] for entry in results] == [str(top)]


def test_scan_folder_size_sort_descending(tmp_path: Path) -> None:
    small = tmp_path / "Small (2024).mkv"
    big = tmp_path / "Big (2024).mkv"
    small.write_bytes(b"x" * 1024)
    big.write_bytes(b"y" * 4096)

    results = scan_folder(str(tmp_path), mode="size_desc", include_dirs=False)

    assert [entry["name"] for entry in results] == ["Big (2024).mkv", "Small (2024).mkv"]


def test_scan_folder_duration_sort_uses_ffprobe_metadata(monkeypatch, tmp_path: Path) -> None:
    short = tmp_path / "Short (2024).mkv"
    long = tmp_path / "Long (2024).mkv"
    short.write_bytes(b"x" * 1024)
    long.write_bytes(b"y" * 1024)

    durations = {
        str(short): 120.0,
        str(long): 360.0,
    }

    monkeypatch.setattr(
        "tools.folder_scanner._probe_duration_seconds",
        lambda path, _ffprobe_exe: durations[path],
    )
    monkeypatch.setattr(
        "tools.folder_scanner._resolve_ffprobe_exe",
        lambda _ffprobe_exe: "ffprobe",
    )

    results = scan_folder(
        str(tmp_path),
        mode="duration_desc",
        include_dirs=False,
        ffprobe_exe="ffprobe",
    )

    assert [entry["name"] for entry in results] == ["Long (2024).mkv", "Short (2024).mkv"]
    assert results[0]["duration_seconds"] == 360.0
