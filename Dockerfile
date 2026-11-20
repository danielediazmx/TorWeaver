FROM python:3.12-slim-bookworm AS examples

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADLESS=true \
    CHROME_NO_SANDBOX=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
COPY examples ./examples
COPY runner.py ./
USER app
CMD ["python", "examples/reusable_client.py"]

FROM examples AS fingerprint
USER root
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && python -m pip install --no-cache-dir '.[fingerprint]' \
    && python -m playwright install-deps firefox \
    && rm -rf /var/lib/apt/lists/*
USER app
RUN python -m camoufox fetch
ENV BROWSER_BACKEND=camoufox

FROM fingerprint AS fingerprint-dev
USER root
RUN python -m pip install --no-cache-dir 'watchfiles>=1.1,<2'
COPY docker/dev/watch.py /opt/multitor/watch.py
USER app
ENV PYTHONPATH=/app/src \
    WATCHFILES_FORCE_POLLING=true \
    WATCHFILES_POLL_DELAY_MS=500
CMD ["python", "/opt/multitor/watch.py"]
