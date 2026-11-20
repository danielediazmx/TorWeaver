"""Browser adapters: each session is created and closed in its owning worker."""

from contextlib import AbstractContextManager, contextmanager
from shutil import which
from typing import Protocol
from urllib.parse import urlsplit

from .config import Settings
from .tor import browser_proxy


class BrowserSession(Protocol):
    def title(self, url: str) -> str: ...
    def goto(self, url: str) -> None: ...
    def extract(
        self, selector: str, *, attribute: str | None = None, limit: int | None = None
    ) -> list[str]: ...


class BrowserProvider(Protocol):
    def open(self, proxy: str) -> AbstractContextManager[BrowserSession]: ...


class SeleniumSession:
    def __init__(self, driver):
        self.driver = driver

    def title(self, url: str) -> str:
        self.driver.get(url)
        return self.driver.title

    def goto(self, url: str) -> None:
        self.driver.get(url)

    def extract(
        self, selector: str, *, attribute: str | None = None, limit: int | None = None
    ) -> list[str]:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        if limit is not None and limit < 1:
            raise ValueError("Limit must be positive")
        elements = WebDriverWait(self.driver, self.driver.timeouts.page_load).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
        )
        return [
            (element.get_attribute(attribute) or "") if attribute else element.text.strip()
            for element in elements[:limit]
        ]


class SeleniumProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    @contextmanager
    def open(self, proxy: str):
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service

        options = webdriver.ChromeOptions()
        if self.settings.headless:
            options.add_argument("--headless=new")
        if self.settings.chrome_no_sandbox:
            options.add_argument("--no-sandbox")
        if binary := which("chromium"):
            options.binary_location = binary
        options.add_argument(f"--proxy-server={browser_proxy(proxy)}")
        options.add_argument(
            f"--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE {urlsplit(proxy).hostname}"
        )
        options.add_argument("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
        options.add_argument("--disable-quic")
        options.add_argument("--window-size=1366,768")
        driver_path = which("chromedriver")
        driver = webdriver.Chrome(
            options=options, service=Service(driver_path) if driver_path else Service()
        )
        try:
            driver.set_page_load_timeout(self.settings.timeout)
            driver.set_script_timeout(self.settings.timeout)
            yield SeleniumSession(driver)
        finally:
            driver.quit()


class CamoufoxSession:
    def __init__(self, page):
        self.page = page

    def title(self, url: str) -> str:
        self.page.goto(url, wait_until="domcontentloaded")
        return self.page.title()

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")

    def extract(
        self, selector: str, *, attribute: str | None = None, limit: int | None = None
    ) -> list[str]:
        if limit is not None and limit < 1:
            raise ValueError("Limit must be positive")
        locator = self.page.locator(selector)
        locator.first.wait_for(state="attached")
        # Read one DOM snapshot; href/src properties match Selenium's absolute URLs.
        return locator.evaluate_all(
            """(elements, options) => elements.slice(0, options.limit ?? elements.length)
                .map(element => options.attribute
                    ? String(element[options.attribute] ?? element.getAttribute(options.attribute) ?? '')
                    : element.innerText.trim())""",
            {"attribute": attribute, "limit": limit},
        )


class CamoufoxProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    @contextmanager
    def open(self, proxy: str):
        from camoufox.sync_api import Camoufox

        options = {
            "headless": self.settings.headless,
            "proxy": {"server": browser_proxy(proxy)},
            "block_webrtc": True,
            "firefox_user_prefs": {"network.proxy.socks_remote_dns": True},
        }
        if self.settings.webgl_vendor:
            options["webgl_config"] = (self.settings.webgl_vendor, self.settings.webgl_renderer)
        with Camoufox(**options) as browser:
            page = browser.new_page()
            page.set_default_timeout(self.settings.timeout * 1000)
            page.set_default_navigation_timeout(self.settings.timeout * 1000)
            yield CamoufoxSession(page)
