"""Validated environment configuration without import-time side effects."""

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    proxies: tuple[str, ...] = ("socks5h://127.0.0.1:19050", "socks5h://127.0.0.1:19060")
    threads: int = 4
    processes: int = 2
    capacity: int = 16
    browser_limit: int = 2
    timeout: float = 60
    backend: str = "selenium"
    headless: bool = True
    chrome_no_sandbox: bool = False
    webgl_vendor: str | None = None
    webgl_renderer: str | None = None

    def __post_init__(self):
        if not self.proxies:
            raise ValueError("At least one Tor proxy is required")
        for proxy in self.proxies:
            parsed = urlsplit(proxy)
            if (
                parsed.scheme != "socks5h"
                or not parsed.hostname
                or not parsed.port
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Tor proxies must be socks5h://host:port without credentials")
        if min(self.threads, self.processes, self.capacity, self.browser_limit, self.timeout) <= 0:
            raise ValueError("Concurrency limits and timeout must be positive")
        if self.backend not in {"selenium", "camoufox"}:
            raise ValueError("BROWSER_BACKEND must be selenium or camoufox")
        if bool(self.webgl_vendor) != bool(self.webgl_renderer):
            raise ValueError("WEBGL_VENDOR and WEBGL_RENDERER must be set together")
        if self.webgl_vendor and self.backend != "camoufox":
            raise ValueError("Explicit WebGL profiles require Camoufox")

    @classmethod
    def from_env(cls):
        headless = os.getenv("HEADLESS", "true").lower()
        if headless not in {"true", "false"}:
            raise ValueError("HEADLESS must be true or false")
        no_sandbox = os.getenv("CHROME_NO_SANDBOX", "false").lower()
        if no_sandbox not in {"true", "false"}:
            raise ValueError("CHROME_NO_SANDBOX must be true or false")
        return cls(
            proxies=tuple(
                p.strip()
                for p in os.getenv("TOR_PROXIES", ",".join(cls.proxies)).split(",")
                if p.strip()
            ),
            threads=int(os.getenv("THREAD_WORKERS", "4")),
            processes=int(os.getenv("PROCESS_WORKERS", "2")),
            capacity=int(os.getenv("TASK_CAPACITY", "16")),
            browser_limit=int(os.getenv("BROWSER_LIMIT", "2")),
            timeout=float(os.getenv("REQUEST_TIMEOUT", "60")),
            backend=os.getenv("BROWSER_BACKEND", "selenium"),
            headless=headless == "true",
            chrome_no_sandbox=no_sandbox == "true",
            webgl_vendor=os.getenv("WEBGL_VENDOR") or None,
            webgl_renderer=os.getenv("WEBGL_RENDERER") or None,
        )
