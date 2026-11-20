"""Keep the development container alive and rerun application code on save."""

import logging
import os

from watchfiles import PythonFilter, run_process


def changed(files):
    names = ", ".join(sorted(path for _, path in files))
    logging.getLogger("development").info("Code changed; restarting example: %s", names)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    command = os.getenv("DEV_COMMAND", "python examples/reusable_client.py")
    logging.getLogger("development").info(
        "Watching src/, examples/, runner.py. Command: %s. Waiting for edits after each run.",
        command,
    )
    run_process(
        "/app/src",
        "/app/examples",
        "/app/runner.py",
        target=command,
        target_type="command",
        watch_filter=PythonFilter(),
        callback=changed,
        debounce=500,
        sigint_timeout=90,
    )
