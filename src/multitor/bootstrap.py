"""Composition root: dependency selection stays outside application services."""

from .browsers import CamoufoxProvider, SeleniumProvider
from .config import Settings
from .service import AutomationService
from .tor import TorHttpClient, TorPool


def build_service(settings: Settings) -> AutomationService:
    provider = CamoufoxProvider if settings.backend == "camoufox" else SeleniumProvider
    return AutomationService(
        TorPool(settings.proxies),
        TorHttpClient(),
        provider(settings),
        settings.browser_limit,
        settings.timeout,
    )
