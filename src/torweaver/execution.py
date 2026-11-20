"""Bounded thread/process execution with observable background failures."""

import logging
from collections.abc import Callable
from concurrent.futures import Future, ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import get_context
from threading import BoundedSemaphore, Lock
from typing import TypeVar

T = TypeVar("T")
log = logging.getLogger(__name__)


class TaskExecutor:
    """One capacity budget across both pools; submit never waits for capacity.

    A Future is always returned. Its result() optionally waits for completion.
    Process callables and arguments must be pickleable (module-level functions).
    """

    def __init__(self, threads: int = 4, processes: int = 2, capacity: int = 16):
        if min(threads, processes, capacity) < 1:
            raise ValueError("Worker counts and capacity must be positive")
        self._slots = BoundedSemaphore(capacity)
        self._threads = ThreadPoolExecutor(threads, thread_name_prefix="torweaver")
        self._processes = ProcessPoolExecutor(processes, mp_context=get_context("spawn"))
        self._lock = Lock()
        self._closed = False

    def submit(self, fn: Callable[..., T], *args, process: bool = False, **kwargs) -> Future[T]:
        with self._lock:
            if self._closed:
                raise RuntimeError("Executor is closed")
            if not self._slots.acquire(blocking=False):
                raise RuntimeError(
                    "Task capacity exhausted; consume results before submitting more"
                )
            try:
                pool = self._processes if process else self._threads
                future = pool.submit(fn, *args, **kwargs)
            except BaseException:
                self._slots.release()
                raise
        future.add_done_callback(self._finished)
        return future

    def _finished(self, future: Future) -> None:
        self._slots.release()
        if not future.cancelled() and (error := future.exception()) is not None:
            log.error("Background task failed", exc_info=(type(error), error, error.__traceback__))

    def close(self, wait: bool = True, cancel_pending: bool = False) -> None:
        with self._lock:
            self._closed = True
        self._threads.shutdown(wait=wait, cancel_futures=cancel_pending)
        self._processes.shutdown(wait=wait, cancel_futures=cancel_pending)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close(cancel_pending=exc[0] is not None)
