"""Tor network transport: SOCKS endpoint leases, Requests, and circuit control.

An endpoint is a Tor daemon's SOCKS listener, not an exit IP allocation.
Tor chooses the exit relay; separate endpoints may use the same exit relay.
"""

from contextlib import contextmanager
from queue import Empty, Queue
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit


class TorPool:
    """A lease prevents concurrent jobs in this application sharing an endpoint."""

    def __init__(self, proxies: tuple[str, ...]):
        if not proxies or len(set(proxies)) != len(proxies):
            raise ValueError("Provide distinct Tor endpoints")
        self._available = Queue()
        for proxy in proxies:
            self._available.put(proxy)

    @contextmanager
    def lease(self, timeout: float = 60):
        try:
            proxy = self._available.get(timeout=timeout)
        except Empty as exc:
            raise TimeoutError("No Tor endpoint became available") from exc
        try:
            yield proxy
        finally:
            self._available.put(proxy)


class TorHttpClient:
    def get(self, url: str, proxy: str, timeout: float):
        import requests

        with requests.Session() as session:
            session.trust_env = False
            response = session.get(url, proxies={"http": proxy, "https": proxy}, timeout=timeout)
            response.raise_for_status()
            return response


class TorController:
    """Optional control adapter; NEWNYM never guarantees a different exit IP.

    Use only while the endpoint is idle. One controller per endpoint per app.
    Control ports are intentionally not exposed by the default Compose stack.
    """

    def __init__(self, host: str, port: int, password: str):
        self.host, self.port, self.password = host, port, password
        self._lock = Lock()
        self._last_rotation = float("-inf")

    def new_identity(self):
        from stem import Signal
        from stem.control import Controller

        with self._lock, Controller.from_port(address=self.host, port=self.port) as control:
            control.authenticate(password=self.password)
            delay = max(control.get_newnym_wait(), 10 - (monotonic() - self._last_rotation))
            if delay > 0:
                raise RuntimeError(f"Tor rotation cooldown: retry after {delay:.1f} seconds")
            control.signal(Signal.NEWNYM)
            self._last_rotation = monotonic()


def browser_proxy(proxy: str) -> str:
    """Browser engines use socks5; requests uses socks5h for remote DNS."""
    parsed = urlsplit(proxy)
    if parsed.scheme != "socks5h":
        raise ValueError("A remote-DNS Tor proxy is required")
    return parsed._replace(scheme="socks5").geturl()
