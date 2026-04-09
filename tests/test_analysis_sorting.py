from pathlib import Path

from engine.ripper_engine import RipperEngine


def _engine_cfg(**overrides):
    cfg = {
        "makemkvcon_path": "makemkvcon",
        "ffprobe_path": "ffprobe",
        "opt_makemkv_global_args": "",
        "opt_makemkv_rip_args": "",
        "opt_drive_index": 0,
        "opt_auto_retry": True,
        "opt_retry_attempts": 3,
        "opt_clean_mkv_before_retry": True,
    }
    cfg.update(overrides)
    return cfg


class _FakeFuture:
    def __init__(self, fn, *args):
        self._fn = fn
        self._args = args

    def result(self):
        return self._fn(*self._args)


class _FakeExecutor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = (exc_type, exc, tb)
        return False

    def submit(self, fn, *args):
        return _FakeFuture(fn, *args)


def test_analyze_files_sorts_by_duration_then_size(monkeypatch, tmp_path: Path):
    engine = RipperEngine(_engine_cfg())
    files = [
        tmp_path / "alpha.mkv",
        tmp_path / "bravo.mkv",
        tmp_path / "charlie.mkv",
    ]
    for path in files:
        path.write_bytes(b"x")

    results_by_name = {
        "alpha.mkv": (100.0, 300),
        "bravo.mkv": (100.0, 400),
        "charlie.mkv": (200.0, 100),
    }

    monkeypatch.setattr("engine.ripper_engine.ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(
        "engine.ripper_engine.as_completed",
        lambda futures: list(reversed(futures)),
    )
    monkeypatch.setattr(
        engine,
        "_probe_file_duration_and_size",
        lambda path, **_kwargs: results_by_name[Path(path).name],
    )

    analyzed = engine.analyze_files([str(path) for path in files], lambda _m: None)

    assert [Path(path).name for path, _dur, _mb in analyzed] == [
        "charlie.mkv",
        "bravo.mkv",
        "alpha.mkv",
    ]


def test_analyze_files_sorts_unknowns_by_size(monkeypatch, tmp_path: Path):
    engine = RipperEngine(_engine_cfg())
    files = [
        tmp_path / "alpha.mkv",
        tmp_path / "bravo.mkv",
        tmp_path / "charlie.mkv",
    ]
    for path in files:
        path.write_bytes(b"x")

    results_by_name = {
        "alpha.mkv": (-1.0, 300),
        "bravo.mkv": (-1.0, 400),
        "charlie.mkv": (-1.0, 100),
    }

    monkeypatch.setattr("engine.ripper_engine.ThreadPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(
        "engine.ripper_engine.as_completed",
        lambda futures: list(reversed(futures)),
    )
    monkeypatch.setattr(
        engine,
        "_probe_file_duration_and_size",
        lambda path, **_kwargs: results_by_name[Path(path).name],
    )

    analyzed = engine.analyze_files([str(path) for path in files], lambda _m: None)

    assert [Path(path).name for path, _dur, _mb in analyzed] == [
        "bravo.mkv",
        "alpha.mkv",
        "charlie.mkv",
    ]
