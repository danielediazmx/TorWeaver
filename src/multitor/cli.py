"""Small runnable example without project-specific scraping logic."""

import argparse
import json
import logging
from concurrent.futures import as_completed
from dataclasses import asdict

from .bootstrap import build_service
from .config import Settings
from .execution import TaskExecutor


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description="Parallel HTTP and browser requests over Tor")
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--mode", choices=["http", "browser"], default="http")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    service = build_service(settings)
    action = service.fetch if args.mode == "http" else service.browse
    failed = False
    try:
        with TaskExecutor(settings.threads, settings.processes, settings.capacity) as executor:
            # Chunk admission so arbitrary input never overflows the bounded executor.
            for offset in range(0, len(args.urls), settings.capacity):
                futures = [
                    executor.submit(action, url)
                    for url in args.urls[offset : offset + settings.capacity]
                ]
                for future in as_completed(futures):
                    try:
                        print(json.dumps(asdict(future.result()), ensure_ascii=True))
                    except Exception:
                        logging.getLogger(__name__).exception("Request failed")
                        failed = True
    except KeyboardInterrupt:
        return 130
    return 1 if failed else 0
