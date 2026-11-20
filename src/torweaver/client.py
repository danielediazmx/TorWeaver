"""Public library facade. One client owns one shared resource budget."""

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import Future
from contextlib import contextmanager
from dataclasses import replace
from threading import Lock
from typing import TypeVar

from .bootstrap import build_service
from .config import Settings
from .execution import TaskExecutor
from .service import AutomationService

T = TypeVar("T")
R = TypeVar("R")


class TorWeaverClient:
    """Coordinate Requests and browser sessions through Tor SOCKS proxies.

    Tor is the network transport, not the browser engine. HTTP uses Requests;
    page sessions use Chrome via Selenium or the optional Camoufox backend.
    Defaults read environment variables, without implicitly loading any .env file.
    Explicit keyword overrides take precedence. Inject a service for offline tests.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        service: AutomationService | None = None,
        **overrides,
    ):
        self.settings = replace(settings or Settings.from_env(), **overrides)
        self._service = service or build_service(self.settings)
        self._executor = TaskExecutor(
            self.settings.threads, self.settings.processes, self.settings.capacity
        )
        self._lock = Lock()
        self._accepting = True
        self._closed = False

    def get(self, url: str) -> str:
        """Return HTTP response text through Tor, without starting a browser."""
        self._ensure_open()
        return self._service.fetch(url).value

    @contextmanager
    def page(self, url: str):
        """Open an isolated page; release the browser and Tor lease on exit.

        The page belongs to the calling worker; never pass it to another worker.
        """
        self._ensure_open()
        self._service._validate(url)
        with self._service.page() as (_, page):
            page.goto(url)
            yield page

    def submit(self, fn: Callable[..., R], *args, process: bool = False, **kwargs) -> Future[R]:
        """Schedule a job and immediately return its Future."""
        with self._lock:
            if not self._accepting:
                raise RuntimeError("Client is closing or closed")
            return self._executor.submit(fn, *args, process=process, **kwargs)

    def map(self, fn: Callable[[T], R], items: Iterable[T]) -> Iterator[R]:
        """Yield results in input order, admitting at most capacity jobs per batch.

        Consuming the iterator starts work. Do not invoke map from a task running
        on this same client's executor. Admission shares capacity with submit().
        """
        from itertools import islice

        iterator = iter(items)
        while batch := list(islice(iterator, self.settings.capacity)):
            futures = []
            try:
                for item in batch:
                    futures.append(self.submit(fn, item))
                for future in futures:
                    yield future.result()
            finally:
                for future in futures:
                    future.cancel()

    def _ensure_open(self):
        if self._closed:
            raise RuntimeError("Client is closed")

    def close(self):
        """Drain scheduled jobs before closing; call from the owning thread."""
        with self._lock:
            self._accepting = False
        self._executor.close()
        self._closed = True

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, *exc):
        self.close()
