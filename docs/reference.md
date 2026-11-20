# TorWeaver technical reference

Detailed setup, configuration, lifecycle semantics, and extension points.

## Network transport and application clients

TorWeaver uses Tor daemon SOCKS endpoints as its transport layer. It does not use
the Tor Browser application. `TorWeaverClient.get()` uses Requests without a
browser; `TorWeaverClient.page()` uses Camoufox or Chrome controlled by Selenium.
Those clients connect through Tor to a destination that sees the exit relay IP.
Tor chooses exit relays, and multiple SOCKS endpoints may share an exit IP.
Neither endpoint leasing nor NEWNYM guarantees a new IP for every request.
Fingerprint generation and WebGL settings are browser backend features, separate
from Tor routing. See [migration notes](migration.md) for the public API rename.

## Reuse as a library in another project

Install this package into the consuming project's virtual environment:

```powershell
python -m pip install "path/to/torweaver"
# For editable development instead:
python -m pip install -e "path/to/torweaver"
```

The public entry point is `TorWeaverClient`. All workflows using one client share its
Tor endpoint pool, browser budget, and executor. Infrastructure setup is internal:

```python
from torweaver import TorWeaverClient

with TorWeaverClient(threads=4, browser_limit=2) as client:
    with client.page("https://example.com") as page:
        links = page.extract("a[href]", attribute="href", limit=10)
        print(links)

    text = client.get("https://example.com")
    job = client.submit(client.get, "https://example.com")
    print(job.result())
```

`page.goto(url)` navigates within the same session. `page.extract(selector)` waits
for at least one matching element and returns its text; `attribute="href"` returns
link URLs. Missing matches raise the backend timeout rather than silently returning
an empty list. `limit` must be positive when supplied. Sessions belong to the worker
that opens them and must stay inside the `with client.page(...)` block.

For multiple inputs, `list(client.map(workflow, inputs))` performs bounded parallel
work and returns results in input order. The iterator admits one capacity-sized
batch at a time; it supports generators larger than the task queue. Separate submit
calls share that budget and can still reject admission when full. Do not nest map
or blocking waits on jobs from the same executor inside its workers.

Define business workflows in the consuming project:

```python
def top_repositories(client):
    url = "https://github.com/search?q=stars%3A%3E1&type=repositories&s=stars&o=desc"
    with client.page(url) as page:
        return page.extract("div.search-title a[href]", attribute="href", limit=10)


with TorWeaverClient() as client:
    job = client.submit(top_repositories, client)
    repositories = job.result()
```

The GitHub selector is illustrative and has not been verified against its live DOM.
GitHub-specific parsing, persistence, and selectors belong to the consuming project,
not this library. Switching `TorWeaverClient(backend="camoufox")` uses the same API after
installing the fingerprint extra and browser binary. No browser or Tor container
starts at import time. Start the supplied Compose stack separately; installation
does not install Docker or provision network services automatically.

`TorWeaverClient` reads environment variables but does not load `.env` implicitly.
Pass `Settings` or keyword overrides for explicit configuration, or call
`dotenv.load_dotenv()` in your application. Close page scopes before the owning
client; close the client from the owning thread. Client exit drains queued jobs
before disabling their page/HTTP operations. Services can accept an injected
`TorWeaverClient` instance so that multiple application services share one budget.

Build a distributable wheel without copying project folders:

```powershell
python -m pip wheel --no-deps . --wheel-dir dist
# In another project's environment, install the generated wheel:
python -m pip install path/to/torweaver-0.2.0-py3-none-any.whl
```

The package is local; it has not been published to PyPI.
Its distribution, import package, and command are named `torweaver`; the public
client is `TorWeaverClient`. Compose also uses the explicit project name
`torweaver`, independent of the checkout directory.

## Requirements and quick start

Docker Desktop's Linux engine can run both disposable examples and persistent
development sessions without a host Python installation.

### Persistent Camoufox development with automatic reload

```powershell
# Keep the development container running in the background.
docker compose --profile dev up -d --build camoufox-dev

# Follow output; Ctrl+C stops log following, not the container.
docker compose --profile dev logs -f camoufox-dev

# Run another example manually in the running container.
docker compose --profile dev exec camoufox-dev python examples/parallel_tasks.py

# Stop development without deleting the container.
docker compose --profile dev stop camoufox-dev

# Start the existing container again.
docker compose --profile dev start camoufox-dev
```

Edit Python files in `src/`, `examples/`, or `runner.py` on the host and save them.
Read-only bind mounts make those edits immediately visible inside the container,
and `PYTHONPATH=/app/src` imports your live library source. A persistent watcher
reruns the example on save, even when the previous run finished or failed. The
container stays alive between runs. Read-only mounts prevent the container from
overwriting your source; you can still edit it normally on the host.

Polling is enabled for reliable Windows/Docker Desktop file detection. Changes
restart the example process; browser sessions and in-memory state are recreated.
An active run has up to 90 seconds to shut down before it is forcibly terminated.
This is automatic rerunning, not in-place mutation of an active browser session.

To choose another watched command in PowerShell:

```powershell
$env:CAMOUFOX_DEV_COMMAND = "python examples/parallel_tasks.py"
docker compose --profile dev up -d camoufox-dev
```

Changing the command recreates the service. Python source edits need no rebuild.
Dependency changes, Dockerfile changes, or watcher implementation changes require
`up -d --build`. For Compose environment changes, run `up -d` again. `docker compose
down` removes the containers, while `stop` preserves them. The earlier `run --rm`
commands remain useful for disposable single executions.

The watcher uses [watchfiles](https://watchfiles.helpmanual.io/api/run_process/).

### Disposable example runs

With Docker Desktop's Linux engine running, execute from this project's root:

```powershell
# Browser example: build the image and wait for both Tor services.
docker compose --profile examples run --build --rm examples

# Thread/process example using the same image.
docker compose --profile examples run --rm examples python examples/parallel_tasks.py

# Verify HTTP traffic goes through Tor (look for IsTor: true).
docker compose --profile examples run --rm examples python runner.py --mode http https://check.torproject.org/api/ip

# Optional Camoufox image, including its downloaded browser.
docker compose --profile camoufox run --build --rm examples-camoufox

# Stop the Tor services after running examples.
docker compose down
```

No host Python or Chrome installation is required for this path. The example exits
after printing results; Tor containers remain running until stopped. Bootstrap can
take several minutes. Add `--build` after changing source code. The Camoufox target
requires an additional browser download during its build. The optional extra pins
Playwright to the 1.51 release series to match Camoufox 0.4.x's browser protocol.
Even the CPU-only example
waits for Tor because it shares the example service's dependency configuration.

The image installs matching Debian Chromium and chromedriver packages and runs as
a non-root user, with init enabled, dropped capabilities and 1 GB of shared memory.
It explicitly sets `CHROME_NO_SANDBOX=true` for compatibility with Docker's default
restrictions. Host execution retains the sandbox by default. Production deployments
should configure an appropriate browser sandbox for untrusted content.

Compose supplies `socks5h://tor-1:9050,socks5h://tor-2:9050` inside the example
containers. Host loopback endpoints do not work inside these containers. The host
`.env` is excluded from the build and is not injected into these services.

### Run from the host

Use Python 3.11 or newer (3.12 recommended for optional browser packages), Docker
Desktop with Linux containers, and Chrome for the Selenium backend. Selenium
Manager resolves the driver and may need network access on first startup.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
docker compose up -d --build --wait --wait-timeout 420
python runner.py --mode http https://check.torproject.org/api/ip
python runner.py --mode browser https://example.com
python examples/parallel_tasks.py
python -m pytest
```

The HTTP check should return JSON containing `IsTor: true`. Bootstrap can take
several minutes. Inspect `docker compose logs tor-1 tor-2` if readiness fails.
Stop with `docker compose down`. This host quick start runs the application locally;
the optional example profiles run it in containers. SOCKS ports bind to host loopback only.
Each healthcheck performs an HTTPS request through Tor; it checks exit connectivity,
not just whether a TCP port is open. No control ports or Docker socket are exposed.

## Execution model

```python
from torweaver import TaskExecutor
from torweaver.bootstrap import build_service
from torweaver.config import Settings

service = build_service(Settings.from_env())
with TaskExecutor(threads=4, processes=2, capacity=16) as executor:
    job = executor.submit(service.browse, "https://example.com")
    # Do other work while the task runs.
    result = job.result(timeout=120)
    print(result.value)
```

`submit()` returns a standard `concurrent.futures.Future`. Calling `result()` waits;
retaining it and continuing does not. Background exceptions are logged even if the
caller never reads the result. The capacity budget covers running and queued jobs
across both pools; overload fails immediately instead of growing memory without a
bound. `cancel()` stops queued jobs only. Context exit waits for outstanding work.
`close(wait=False, cancel_pending=True)` returns without draining running work, but
Python still waits for active executor workers at interpreter exit. This is not a
durable detached job queue. A `Future.result(timeout=...)` timeout does not kill
the job. Thread tasks cannot be forcibly stopped; browser startup/shutdown can
outlast navigation timeouts. HTTP timeouts apply to connection/read operations,
not a hard total deadline. Ctrl+C drains active jobs during context cleanup.

Use threads for browser and HTTP I/O. Use `process=True` for CPU functions defined
at module scope, under an `if __name__ == "__main__":` guard (see the example).
Process functions and arguments must be pickleable. Do not send services, browser
instances, locks, or bound automation methods to the process pool. The spawn start
method supports Windows and avoids inheriting browser state. Concurrency budgets
and Tor leases are local to one application process; multiple application
instances need separate endpoints or an external coordination layer.

## Browsers and WebGL

Selenium is the default Chrome adapter. Each job owns a fresh session in the worker
that uses it, with page/script timeouts and guaranteed cleanup after normal errors.
It preserves Chrome's native graphics configuration. The sandbox stays enabled
unless `CHROME_NO_SANDBOX=true` is explicitly configured (as in the example image).

The optional Camoufox adapter provides generated fingerprint profiles, including
WebGL vendor/renderer identity. This simulates the browser-visible graphics
identity; it does not emulate a physical GPU or guarantee bypassing bot detection.

```powershell
python -m pip install -e ".[fingerprint]"
python -m camoufox fetch
$env:BROWSER_BACKEND = "camoufox"
python runner.py --mode browser https://example.com
```

By default Camoufox selects a supported WebGL profile. To select one explicitly,
set both `WEBGL_VENDOR` and `WEBGL_RENDERER` to a supported pair from its dataset.
Invalid profiles fail visibly. There is no silent fallback to another browser.
See [Camoufox usage](https://camoufox.com/python/usage/) and
[Selenium browser options](https://www.selenium.dev/documentation/webdriver/browsers/chrome/).
Browser binaries and optional native dependencies are installed separately.

## Tor and networking

Requests uses `socks5h` so target DNS resolution goes through the proxy, and ignores
ambient HTTP proxy environment variables. Browser adapters translate this to their
`socks5` syntax, restrict DNS behavior, and disable non-proxied WebRTC behavior.
An unavailable Tor endpoint raises an error; the application never retries directly.
This project does not launch Tor Browser. Browser automation through SOCKS is not
a complete network isolation boundary. For strict egress guarantees enforce a firewall or
container network policy and validate DNS/WebRTC behavior in your deployment.

`TorPool` leases one endpoint exclusively per job and always returns it on failure.
Effective Tor job concurrency is limited by endpoint count (two by default), plus
thread and browser limits. Add independent Compose services and append their host
ports to `TOR_PROXIES` to scale. Independent Tor instances can still choose the same
exit IP. Browser sessions never share mutable driver instances or profile folders.

`TorController` is an optional authenticated NEWNYM adapter for deployments that
explicitly configure a control port. Call it only under an exclusive idle endpoint
lease; never interrupt active sessions. It reports cooldowns and errors rather
than sleeping or restarting containers. NEWNYM affects new circuits and does not
guarantee a different exit IP. The default stack intentionally needs no passwords
and does not enable control access. It does not restart containers from application
code or require privileged Docker access.

## Configuration

Copy `.env.example` to `.env`; the CLI loads it without overriding existing process
environment variables. Library users can call `dotenv.load_dotenv()` explicitly.

| Variable | Default | Purpose |
| --- | --- | --- |
| TOR_PROXIES | Two loopback SOCKS endpoints | Comma-separated socks5h URLs |
| THREAD_WORKERS | 4 | I/O worker count |
| PROCESS_WORKERS | 2 | CPU worker count |
| TASK_CAPACITY | 16 | Total queued + running tasks |
| BROWSER_LIMIT | 2 | Concurrent browser sessions |
| REQUEST_TIMEOUT | 60 | HTTP, navigation, and resource acquisition seconds |
| BROWSER_BACKEND | selenium | selenium or camoufox |
| HEADLESS | true | true or false |
| CHROME_NO_SANDBOX | false | Explicit Chrome sandbox opt-out; true in the example container |
| WEBGL_VENDOR / WEBGL_RENDERER | empty | Optional supported Camoufox GPU pair |

The CLI accepts any number of URLs, admits bounded chunks, emits JSON results in
completion order within each chunk, and exits 1 if any request fails. It does not
retry automatically, avoiding unintended replay of application operations.

## Project structure and extension points

```text
src/torweaver/
  client.py       Public TorWeaverClient library facade
  config.py       Immutable, validated settings
  execution.py    Bounded thread/process orchestration and Future lifecycle
  tor.py          Endpoint leasing, HTTP transport, optional circuit control
  browsers.py     Browser protocols and Selenium/Camoufox adapters
  service.py      Generic fetch/browse use cases and browser resource budget
  bootstrap.py    Composition root for dependency injection
  cli.py          Minimal runnable application
examples/         Thread and process usage
Dockerfile        Example image and optional Camoufox build target
.dockerignore     Excludes local environments, secrets, and generated artifacts
tests/           Offline concurrency, failure, cleanup, and configuration tests
docker/tor/      Unprivileged Tor image and configuration
docker-compose.yml  Independent Tor endpoints
runner.py        Compatibility CLI entry point
```

The application service depends on small `HttpClient` and `BrowserProvider`
protocols, rather than concrete implementations. Add a backend by implementing
`open(proxy)` as a context manager yielding a session with `goto(url)`,
`extract(selector, attribute=..., limit=...)`, and `title(url)`, then wire
it at the composition root. Inject fakes for offline tests. Add your own workflows
above these services instead of embedding business rules in the infrastructure.
Configuration, scheduling, transport, resource ownership, and application use cases
have distinct responsibilities; there are no global singleton service instances.

Dependencies use compatible version ranges, not a reproducible lockfile. Resolve
and freeze a tested environment before production deployment. Offline unit tests
do not certify live Tor availability, external site behavior, or fingerprint
undetectability. Browser downloads, container builds, and live checks are separate
integration steps.

## Validation in the development environment

Ten offline tests passed, along with lint checks, CLI help, wheel packaging and
installation, and Compose configuration validation. The example image was built
and executed with Chromium over Tor, the thread/process example returned 49 and
144, and the HTTP example returned IsTor: true from the Tor Project endpoint.
The Camoufox image was also built and successfully ran the link extraction example
with the pinned Playwright dependency.
The persistent development service was started, confirmed to import from the
mounted `/app/src` directory, and detected a host file modification and reran the
example while retaining the same container ID.
