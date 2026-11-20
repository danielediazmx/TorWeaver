"""Application code stays outside the library. Start Tor before running."""

from torweaver import TorWeaverClient


def extract_links(client: TorWeaverClient, url: str) -> list[str]:
    with client.page(url) as page:
        return page.extract("a[href]", attribute="href", limit=10)


if __name__ == "__main__":
    with TorWeaverClient(threads=4, browser_limit=2) as client:
        job = client.submit(extract_links, client, "https://example.com")
        print(job.result())
