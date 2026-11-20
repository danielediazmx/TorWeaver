from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace

import pytest

from torweaver import Settings, TorWeaverClient


class FakeService:
    def __init__(self):
        self.closed_pages = 0

    def _validate(self, url):
        if not url.startswith("https://"):
            raise ValueError("Invalid URL")

    def fetch(self, url):
        return SimpleNamespace(value="response")

    @contextmanager
    def page(self):
        try:
            yield "proxy", SimpleNamespace(goto=lambda url: None, extract=lambda *a: ["repo"])
        finally:
            self.closed_pages += 1


def test_public_page_cleanup_and_http():
    service = FakeService()
    with TorWeaverClient(Settings(), service=service) as client:
        assert client.get("https://example.com") == "response"
        with pytest.raises(ValueError), client.page("https://example.com"):
            raise ValueError("Extraction failed")
        assert service.closed_pages == 1
    with pytest.raises(RuntimeError):
        client.get("https://example.com")


def test_map_bounds_large_generators_and_preserves_order():
    with TorWeaverClient(Settings(), service=FakeService(), capacity=2) as client:
        assert list(client.map(lambda n: n * 2, iter(range(11)))) == list(range(0, 22, 2))


def test_background_work_can_use_client_while_close_drains():
    started, release = Event(), Event()
    client = TorWeaverClient(Settings(), service=FakeService())

    def workflow():
        started.set()
        release.wait(3)
        with client.page("https://example.com") as page:
            return page.extract("a")

    future = client.submit(workflow)
    assert started.wait(2)
    release.set()
    client.close()
    assert future.result() == ["repo"]
    with pytest.raises(RuntimeError):
        client.submit(lambda: None)


def test_settings_overrides_are_validated():
    with pytest.raises(ValueError):
        TorWeaverClient(Settings(), threads=0)
