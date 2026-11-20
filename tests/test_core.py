import unittest
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace

from torweaver.config import Settings
from torweaver.execution import TaskExecutor
from torweaver.service import AutomationService
from torweaver.tor import TorPool, browser_proxy


def square(value):
    return value * value


class CoreTests(unittest.TestCase):
    def test_process_and_thread_results(self):
        with TaskExecutor() as executor:
            self.assertEqual(executor.submit(square, 5).result(10), 25)
            self.assertEqual(executor.submit(square, 6, process=True).result(30), 36)

    def test_capacity_cancel_and_shutdown(self):
        started, release = Event(), Event()

        def block():
            started.set()
            release.wait(5)

        executor = TaskExecutor(threads=1, capacity=2)
        try:
            running = executor.submit(block)
            self.assertTrue(started.wait(2))
            queued = executor.submit(square, 2)
            with self.assertRaisesRegex(RuntimeError, "capacity"):
                executor.submit(square, 3)
            self.assertTrue(queued.cancel())
            replacement = executor.submit(square, 4)
            release.set()
            running.result(5)
            self.assertEqual(replacement.result(5), 16)
        finally:
            release.set()
            executor.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            executor.submit(square, 1)

    def test_failed_lease_is_reusable_and_exclusive(self):
        pool = TorPool(("socks5h://localhost:9050",))
        with self.assertRaisesRegex(ValueError, "failure"), pool.lease():
            with self.assertRaises(TimeoutError), pool.lease(timeout=0.01):
                pass
            raise ValueError("failure")
        with pool.lease(timeout=0.01) as proxy:
            self.assertTrue(proxy.startswith("socks5h"))

    def test_browser_cleanup_after_failure(self):
        class Provider:
            closed = 0

            @contextmanager
            def open(self, proxy):
                try:
                    yield SimpleNamespace(title=lambda url: (_ for _ in ()).throw(ValueError()))
                finally:
                    self.closed += 1

        provider = Provider()
        service = AutomationService(
            TorPool(Settings().proxies), None, provider, browser_limit=1, timeout=0.1
        )
        for _ in range(2):
            with self.assertRaises(ValueError):
                service.browse("https://example.com")
        self.assertEqual(provider.closed, 2)

    def test_configuration_rejects_direct_proxy_and_bad_limits(self):
        for kwargs in (
            {"proxies": ()},
            {"proxies": ("http://localhost:9050",)},
            {"threads": 0},
            {"webgl_vendor": "incomplete"},
            {"backend": "unknown"},
        ):
            with self.assertRaises(ValueError):
                Settings(**kwargs)
        self.assertEqual(browser_proxy("socks5h://localhost:9050"), "socks5://localhost:9050")

    def test_http_service_and_invalid_url(self):
        class Http:
            def get(self, url, proxy, timeout):
                return SimpleNamespace(text="through Tor")

        service = AutomationService(TorPool(Settings().proxies), Http(), None)
        self.assertEqual(service.fetch("https://example.com").value, "through Tor")
        with self.assertRaises(ValueError):
            service.fetch("file:///secret")


if __name__ == "__main__":
    unittest.main()
