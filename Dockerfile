FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HEADLESS=true \
    CHROME_NO_SANDBOX=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium chromium-driver ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app

# Browser binaries do not depend on application code or README changes.
FROM runtime AS fingerprint-runtime
COPY pyproject.toml /opt/torweaver/pyproject.toml
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && python -c "import subprocess, tomllib; p = tomllib.load(open('/opt/torweaver/pyproject.toml', 'rb'))['project']; subprocess.check_call(['python', '-m', 'pip', 'install', '--no-cache-dir', *p['dependencies'], *p['optional-dependencies']['fingerprint']])" \
    && python -m playwright install-deps firefox \
    && rm -rf /var/lib/apt/lists/*
USER app
RUN python -m camoufox fetch

FROM runtime AS examples
COPY pyproject.toml requirements.txt readme.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
COPY examples ./examples
COPY runner.py ./
USER app
CMD ["python", "examples/reusable_client.py"]

FROM fingerprint-runtime AS fingerprint
USER root
COPY pyproject.toml requirements.txt readme.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir .
COPY examples ./examples
COPY runner.py ./
USER app
ENV BROWSER_BACKEND=camoufox
CMD ["python", "examples/reusable_client.py"]

FROM fingerprint AS fingerprint-dev
USER root
RUN python -m pip install --no-cache-dir 'watchfiles>=1.1,<2'
COPY docker/dev/watch.py /opt/torweaver/watch.py
USER app
ENV PYTHONPATH=/app/src \
    WATCHFILES_FORCE_POLLING=true \
    WATCHFILES_POLL_DELAY_MS=500
CMD ["python", "/opt/torweaver/watch.py"]
