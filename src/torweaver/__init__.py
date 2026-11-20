"""Parallel HTTP and browser automation through Tor SOCKS proxies.

Tor transports traffic. Requests, Camoufox, and Chrome are the clients.
This package does not install or launch the Tor Browser application.
"""

from .client import TorWeaverClient
from .config import Settings
from .execution import TaskExecutor

__all__ = ["Settings", "TaskExecutor", "TorWeaverClient"]
