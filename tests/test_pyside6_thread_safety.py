"""Phase 3c-ii — gui_qt.thread_safety tests.

Pins the Invoker + run_on_main + submit_to_main contract:

- Same-thread fast path (no marshaling overhead)
- Cross-thread blocking (worker waits, gets the result)
- Cross-thread async (worker doesn't wait)
- Exception propagation through run_on_main
- Order-preservation for multiple async submits
"""

from __future__ import annotations

import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytest.importorskip("pytestqt")

from PySide6.QtCore import QCoreApplication

from gui_qt.thread_safety import Invoker, run_on_main, submit_to_main


# ---------------------------------------------------------------------------
# Same-thread fast path
# ---------------------------------------------------------------------------


def test_run_on_main_returns_value_same_thread(qtbot):
    """When called from the invoker's own thread, ``run_on_main``
    skips marshaling and returns the callable's value directly.
    Pinned because this is the dominant case during tests + early-
    init code paths."""
    inv = Invoker()
    result = run_on_main(inv, lambda x, y: x + y, 2, 3)
    assert result == 5


def test_run_on_main_supports_kwargs_same_thread(qtbot):
    """kwargs are forwarded to the callable."""
    inv = Invoker()
    result = run_on_main(inv, lambda *, base, mult: base * mult, base=4, mult=10)
    assert result == 40


def test_submit_to_main_same_thread_runs_synchronously(qtbot):
    """``submit_to_main`` on the invoker's own thread bypasses the
    queue and runs the callable inline — pinned because callers
    rely on the side-effect being visible immediately when not
    cross-thread."""
    inv = Invoker()
    captured: list[int] = []
    submit_to_main(inv, captured.append, 42)
    assert captured == [42]


# ---------------------------------------------------------------------------
# Exception propagation
# ---------------------------------------------------------------------------


def test_run_on_main_propagates_exceptions(qtbot):
    """If ``fn`` raises, ``run_on_main`` re-raises the same exception
    on the calling thread.  Pinned because the controller depends on
    exceptions surfacing rather than being swallowed."""
    inv = Invoker()

    def boom():
        raise ValueError("expected")

    with pytest.raises(ValueError) as excinfo:
        run_on_main(inv, boom)
    assert "expected" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Cross-thread (worker submits to GUI thread)
# ---------------------------------------------------------------------------


def _drain_events_until(predicate, timeout: float = 2.0) -> bool:
    """Process Qt events until ``predicate()`` is true or timeout."""
    deadline = time.time() + timeout
    app = QCoreApplication.instance()
    while time.time() < deadline:
        if predicate():
            return True
        if app is not None:
            app.processEvents()
        time.sleep(0.005)
    return predicate()


def test_run_on_main_marshals_from_worker_thread(qtbot):
    """A worker thread calls ``run_on_main``; the callable executes
    on the invoker's thread and the result flows back."""
    inv = Invoker()
    captured: dict = {}

    def worker():
        try:
            captured["result"] = run_on_main(inv, lambda: 7 * 6)
        except BaseException as e:
            captured["error"] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    # Drain Qt events on the test thread (= GUI thread) so the
    # queued slot in the invoker fires.
    assert _drain_events_until(lambda: not t.is_alive(), timeout=2.0)
    t.join(timeout=0.5)

    assert "error" not in captured, f"unexpected error: {captured.get('error')}"
    assert captured["result"] == 42


def test_run_on_main_propagates_worker_thread_exceptions(qtbot):
    """When ``fn`` raises and the call came from a worker thread,
    the worker sees the same exception."""
    inv = Invoker()
    captured: dict = {}

    def worker():
        try:
            run_on_main(inv, lambda: (_ for _ in ()).throw(RuntimeError("from worker")))
        except RuntimeError as e:
            captured["caught"] = str(e)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    assert _drain_events_until(lambda: not t.is_alive(), timeout=2.0)
    t.join(timeout=0.5)

    assert captured.get("caught") == "from worker"


def test_submit_to_main_async_from_worker(qtbot):
    """A worker thread submits a fire-and-forget callable; it
    eventually runs on the GUI thread.  The worker doesn't block."""
    inv = Invoker()
    captured: list[str] = []

    def worker():
        submit_to_main(inv, captured.append, "hello")
        # Worker returns immediately — no waiting on the callable.

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=0.5)
    assert not t.is_alive()  # worker finished without blocking

    # Drain events so the queued callable runs.
    assert _drain_events_until(lambda: bool(captured), timeout=2.0)
    assert captured == ["hello"]


def test_submit_to_main_preserves_order_across_multiple_submits(qtbot):
    """Multiple async submits from the same worker run in submission
    order on the GUI thread.  Pinned because controller log lines
    rely on order-preserving append."""
    inv = Invoker()
    captured: list[int] = []

    def worker():
        for i in range(10):
            submit_to_main(inv, captured.append, i)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=0.5)

    assert _drain_events_until(lambda: len(captured) == 10, timeout=2.0)
    assert captured == list(range(10))


def test_run_on_main_blocks_worker_until_done(qtbot):
    """Even when the callable takes time on the GUI thread, the
    worker thread blocks in ``run_on_main`` until it finishes —
    no early-return."""
    inv = Invoker()
    state: dict = {"completed_at": None, "started_at": None}
    barrier = threading.Event()

    def slow_callable():
        # Run on GUI thread; barrier is the worker's signal that
        # it's about to block.  We sleep AFTER barrier set so the
        # worker is in run_on_main's done.wait() loop.
        state["started_at"] = time.time()
        barrier.wait(timeout=1.0)  # let the worker reach .wait()
        time.sleep(0.05)
        state["completed_at"] = time.time()
        return "done"

    captured: dict = {}

    def worker():
        # Start the callable, then signal we're about to block,
        # then wait for the result.
        barrier.set()
        captured["result"] = run_on_main(inv, slow_callable)
        captured["worker_returned_at"] = time.time()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    assert _drain_events_until(lambda: not t.is_alive(), timeout=3.0)

    assert captured["result"] == "done"
    # Worker returned only after the callable completed
    assert captured["worker_returned_at"] >= state["completed_at"]
