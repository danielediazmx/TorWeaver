"""Application use cases depend on small infrastructure interfaces."""

from contextlib import contextmanager
from dataclasses import dataclass
from threading import BoundedSemaphore
from typing import Protocol
from urllib.parse import urlsplit

from .browsers import BrowserProvider
from .tor import TorPool


class HttpClient(Protocol):
    def get(self, url: str, proxy: str, timeout: float): ...


@dataclass(frozen=True)
class FetchResult:
    url: str
    proxy: str
    value: str


class AutomationService:
    def __init__(
        self,
        pool: TorPool,
        http: HttpClient,
        browsers: BrowserProvider,
        browser_limit: int = 2,
        timeout: float = 60,
    ):
        self.pool, self.http, self.browsers = pool, http, browsers
        self.timeout = timeout
        self._browser_slots = BoundedSemaphore(browser_limit)

    @staticmethod
    def _validate(url: str):
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Only absolute HTTP and HTTPS URLs are supported")

    def fetch(self, url: str) -> FetchResult:
        self._validate(url)
        with self.pool.lease(self.timeout) as proxy:
            return FetchResult(url, proxy, self.http.get(url, proxy, self.timeout).text)

    def browse(self, url: str) -> FetchResult:
        self._validate(url)
        with self.page() as (proxy, browser):
            return FetchResult(url, proxy, browser.title(url))

    @contextmanager
    def page(self):
        """Share the same browser budget across every workflow using this service."""
        if not self._browser_slots.acquire(timeout=self.timeout):
            raise TimeoutError("Browser capacity unavailable")
        try:
            with self.pool.lease(self.timeout) as proxy, self.browsers.open(proxy) as browser:
                yield proxy, browser
        finally:
            self._browser_slots.release()
