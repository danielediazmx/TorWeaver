# TorWeaver

**Parallel HTTP requests and browser automation through Tor SOCKS proxies.**

Give your web workflows one Python API for Tor-routed HTTP requests, isolated
browser sessions, and bounded parallel jobs. Use Requests, Camoufox, or Chrome via Selenium, keep your
application logic in your own project, and iterate with a live-reloading Docker
setup.

**Tor is the transport layer.** Requests makes HTTP requests without a browser;
Camoufox and Chrome provide browser sessions. Each connects to a Tor SOCKS proxy,
and the destination sees the Tor exit relay's IP. TorWeaver does not install,
launch, or control the Tor Browser application.

```python
from torweaver import TorWeaverClient

with TorWeaverClient(threads=4, browser_limit=2) as client:
    with client.page("https://example.com") as page:
        links = page.extract("a[href]", attribute="href", limit=10)
        print(links)
```

**Python 3.11+ · Selenium · Optional Camoufox · Docker Compose · Local execution**

[Quick start](#quick-start) · [Python API](#python-api) ·
[AI integration](#use-it-as-an-ai-agent-tool) ·
[Live development](#live-development-with-camoufox) ·
[Technical reference](docs/reference.md)

## Why TorWeaver?

Combining proxies, browser lifecycles, worker pools, and resource limits often
means rebuilding the same infrastructure in every project. TorWeaver puts those
pieces behind one reusable client.

- **Tor routing built in.** HTTP requests and browser sessions use configured Tor
  endpoints. Failed endpoints raise errors instead of falling back to direct access.
- **Parallel work with limits.** Submit background jobs, wait when needed, and
  process collections without an unbounded task queue.
- **Two browser backends.** Use Chrome through Selenium, or optional Camoufox with
  generated browser fingerprint profiles, through the same page API.
- **Shared resource budgets.** Services using one client share its browser limit,
  Tor endpoint leases, and executor capacity.
- **Fast local iteration.** A persistent Docker development container reruns your
  example when you save Python changes.
- **Bring your own application.** Return ordinary Python values to your scraper,
  research pipeline, data collector, or agent tool.

## Quick start

Clone or download this repository and open a terminal in its root directory.
With Docker and Docker Compose available, run:

```sh
docker compose --profile examples run --build --rm examples
```

This builds the Chromium example image, starts two Tor instances, waits for their
healthchecks, and prints links extracted from an example page. No host Python or
browser installation is required. Initial builds and Tor bootstrap take time.

Verify the HTTP route separately; the response should contain `IsTor: true`:

```sh
docker compose --profile examples run --rm examples python runner.py --mode http https://check.torproject.org/api/ip
```

Try the same browser example with Camoufox:

```sh
docker compose --profile camoufox run --build --rm examples-camoufox
```

The optional image downloads its browser during the build. These are disposable
runs; their Tor services remain active until `docker compose down`.

## Install in your own Python project

Use Python 3.11 or newer; Python 3.12 is recommended for optional browser packages.
From the repository root, inside your project's virtual environment:

```sh
python -m pip install .
```

For editable development, use `python -m pip install -e .`. To install into another
project's environment, pass the path to this checkout instead of `.`.

Start the supplied Tor endpoints before using the client from the host:

```sh
docker compose up -d --build --wait --wait-timeout 420
```

The default Selenium backend requires Chrome/Chromium. An installed chromedriver
is used when available; otherwise Selenium Manager resolves the driver.

**Naming:** Project and distribution: `torweaver`. Public client:
`from torweaver import TorWeaverClient`. Command: `torweaver` or
`python -m torweaver`. This project has not published a PyPI release;
install from this checkout or a locally built wheel.

Existing local integrations should follow the [migration guide](docs/migration.md).

## Python API

### HTTP without launching a browser

```python
from torweaver import TorWeaverClient

with TorWeaverClient() as client:
    html = client.get("https://example.com")
```

### Background jobs

```python
from torweaver import TorWeaverClient

with TorWeaverClient(threads=4, capacity=16) as client:
    job = client.submit(client.get, "https://example.com")
    # Continue doing other work, then collect the result.
    html = job.result()
```

### Multiple inputs

```python
from torweaver import TorWeaverClient

urls = ["https://example.com", "https://example.org"]

with TorWeaverClient(threads=4, capacity=16) as client:
    pages = list(client.map(client.get, urls))
```

`map()` returns results in input order and admits bounded batches. `submit()`
returns a standard `Future`; overload is reported immediately. Client exit waits
for scheduled jobs. Keep page sessions inside their `with` block and on their
owning worker. For CPU jobs, use module-level pickleable functions with
`submit(..., process=True)` under a `__main__` guard.

## Use it as an AI agent tool

Wrap the client in a normal Python function and register that function with your
agent framework's tool interface. Your model chooses when to call the tool; the
library handles browser execution and returns data your application can serialize.

```python
from torweaver import TorWeaverClient


def read_page(client: TorWeaverClient, url: str) -> dict:
    """Read selected text from a web page through Tor."""
    with client.page(url) as page:
        paragraphs = page.extract("h1, h2, p", limit=20)
    return {"url": url, "text": "\n".join(paragraphs)[:8000]}


with TorWeaverClient(browser_limit=2) as client:
    # Register a wrapper around read_page(client, url) in your agent application.
    result = client.submit(read_page, client, "https://example.com").result()
    print(result)
```

This is a framework-neutral integration pattern, not a bundled autonomous agent.
The current project has no LLM client, MCP server, or native framework connectors.
Selector-based extraction does not infer a page's meaning. If you feed page content
to an LLM, treat it as untrusted input rather than agent instructions.

## Live development with Camoufox

```sh
# Start a persistent development container.
docker compose --profile dev up -d --build camoufox-dev

# Follow output while editing Python files on the host.
docker compose --profile dev logs -f camoufox-dev
```

Save changes in `src/`, `examples/`, or `runner.py`. The watcher restarts the example
using your mounted source without rebuilding the image or recreating the container.
The container stays running after the example finishes or fails. Browser sessions
are recreated on each rerun; active runs have a shutdown grace period.

```sh
# Run an additional example inside the active container.
docker compose --profile dev exec camoufox-dev python examples/parallel_tasks.py

# Stop without deleting the development container.
docker compose --profile dev stop camoufox-dev

# Resume the existing container.
docker compose --profile dev start camoufox-dev
```

Dependency or Dockerfile changes require a rebuild. See the
[technical reference](docs/reference.md) to choose another watched command,
configure endpoints, or run without Docker.

## How it fits together

```text
Your Python application or AI tool
                |
          TorWeaverClient
                |
     Bounded executor + shared browser budget
                |
 Requests / Camoufox / Chrome via Selenium
                |
      Exclusive Tor SOCKS endpoint lease
                |
     Tor network -> exit relay -> destination
```

Each client owns its resources; there are no global service singletons. Worker,
queue, and browser limits are explicit. Independent Tor containers can still
choose the same exit IP. By default, two endpoints limit Tor-backed concurrency
to at most two jobs even if additional workers are configured.
Tor routes each connection; it does not assign an IP to the browser or guarantee
a fresh exit IP per request. Browser fingerprint profiles belong to the browser
backend, independently of Tor's network routing.

## Related projects

This project builds on an existing browser automation ecosystem:

| Project | Focus | TorWeaver's role |
| --- | --- | --- |
| [Browser Use](https://github.com/browser-use/browser-use) | Browser automation driven by AI agents | A Python execution layer you can expose through your own agent tools |
| [Crawl4AI](https://github.com/unclecode/crawl4ai) | Web crawling and extraction for AI workflows | Tor-routed HTTP and browser workflows with explicit resource budgets |
| [Camoufox](https://github.com/daijro/camoufox) | Browser fingerprint management and automation | An optional backend used by this library |

These projects overlap with parts of the problem. TorWeaver's focus is the
combination of Tor endpoint leasing, bounded execution, interchangeable browser
adapters, and a small reusable Python client. No native integration with Browser
Use or Crawl4AI is currently provided.

## Project structure

```text
src/torweaver/
  client.py       Public TorWeaverClient API
  execution.py    Bounded thread and process pools
  browsers.py     Browser interface and Selenium/Camoufox adapters
  tor.py          Endpoint leases, HTTP transport, optional Tor control
  service.py      Shared browser and transport workflows
  config.py       Validated settings
  bootstrap.py    Dependency composition
  cli.py          Command-line examples
examples/         Small runnable workflows
docker/          Tor configuration and development watcher
tests/           Offline tests
docs/reference.md  Detailed setup and API behavior
Dockerfile       Example and development images
docker-compose.yml  Tor and application services
```

## Status and limits

This is an early-stage library. Offline tests and Docker examples have been run,
including Chromium, Camoufox, HTTP Tor verification, and development reloads.
There are no published performance benchmarks or guarantees of anonymity,
undetectability, or successful access to every website. Camoufox's WebGL profiles
change browser-visible identity; they do not emulate a physical GPU.

Tor Browser is a separate application and is not a dependency of this project.
Strict network isolation
requires deployment-level egress controls. The example Chromium container disables
Chrome's sandbox for compatibility with Docker's default restrictions; host use
keeps it enabled unless explicitly overridden. Resource budgets are per client
and process, not distributed quotas. Dependency ranges are not a lockfile.

## Contributing

Bug reports with a minimal reproducer, backend, Python version, and Docker/host
setup are welcome. Improvements to backend parity, cleanup behavior, documentation,
and framework integration examples are especially useful.

Run the offline checks from the repository root:

```sh
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check src tests examples docker/dev
```

If TorWeaver saves you from rebuilding this infrastructure, consider starring the
repository so other developers can find it.
