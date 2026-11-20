# Migrating to TorWeaver 0.2

This release makes network transport and client names explicit. Tor is used through
SOCKS proxies. HTTP uses Requests. Browser sessions use Camoufox or Chrome through
Selenium. No workflow installs or launches the Tor Browser application.

## Python imports and installation

The earlier local API used `from multitor import TorBrowser`. Replace it with:

```python
from torweaver import Settings, TaskExecutor, TorWeaverClient

with TorWeaverClient() as client:
    text = client.get("https://example.com")
```

The import package and distribution are now `torweaver`; the public client is
`TorWeaverClient`. Earlier class and module names are not compatibility aliases.
Use a virtual environment, uninstall the old local `multithread-tor-browser`
distribution if installed there, and install this checkout:

```sh
python -m pip uninstall multithread-tor-browser
python -m pip install -e ".[dev]"
python -m torweaver --help
```

The CLI command is now `torweaver`; `python -m torweaver` and `python runner.py`
are equivalent entry points. Wheels are named `torweaver-0.2.0-py3-none-any.whl`.
No PyPI release is implied by the rename.

## Docker and the checkout directory

Compose now explicitly names the project `torweaver`, so resource names do not
depend on the checkout directory name. Existing development containers and the
Tor services from the former Compose project were stopped and replaced during
this migration. No persistent data volumes were removed.

```sh
docker compose --profile dev up -d --build camoufox-dev
docker compose --profile dev logs -f camoufox-dev
```

The local directory can keep its current name; it does not affect Python imports,
the CLI, or the Compose project name. For the public GitHub repository, `torweaver`
is the recommended name. If moving the checkout, stop its Compose services first,
move it, then run `up -d` from the new directory to recreate the bind mounts.
Recreate a host virtual environment and reinstall the package if its checkout path
changes; virtual environments and editable installs can contain absolute paths.

Endpoint settings, backend selection, HTTP behavior, concurrency limits, and live
reload behavior retain their existing semantics. The rename does not add automatic
IP rotation, a different IP per endpoint, CAPTCHA solving, or new browser engines.
