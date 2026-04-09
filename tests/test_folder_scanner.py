from pathlib import Path

from tools.folder_scanner import FolderScanEntry, classify_entry, scan_folder


def _entry(*, name: str, path: str, is_dir: bool) -> FolderScanEntry:
    return {
        "name": name,
        "path": path,
        "size": 0,
        "size_str": "0 bytes",
        "is_dir": is_dir,
        "bad_name": False,
        "parent": None,
        "status": "WEIRD",
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
