"""Support python -m torweaver without starting services at import time."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
