import httpx
import pytest

from app.ingest.loaders.web import SiteCrawler
from app.ingest.url_safety import UnsafeUrl, assert_public_url


# --- SSRF guard ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost:8000/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/",
        "http://[::1]/",
        "file:///etc/passwd",
        "ftp://example.com/",
        "http://user:pass@example.com/",
    ],
)
def test_blocks_unsafe_urls(url):
    with pytest.raises(UnsafeUrl):
        assert_public_url(url)


def test_allows_public_ip_literal():
    assert_public_url("https://93.184.216.34/docs")  # no DNS needed for a literal


# --- crawler (network mocked) ----------------------------------------------------------

SITE = {
    "https://docs.test/": '<html><title>Home</title><body><p>Welcome to the docs home page.</p>'
                          '<a href="/a">A</a><a href="/b#frag">B</a><a href="https://other.test/x">ext</a>'
                          '<a href="/file.pdf">pdf</a></body></html>',
    "https://docs.test/a": '<html><title>A</title><body><p>Page A explains refunds in detail.</p>'
                           '<a href="/">home</a><a href="/b">B</a></body></html>',
    "https://docs.test/b": '<html><title>B</title><body><p>Page B explains shipping options.</p></body></html>',
}


def handler(request: httpx.Request):
    url = str(request.url).rstrip("/")  # servers treat "" and "/" paths the same
    if url == "https://docs.test/redirect":
        return httpx.Response(302, headers={"location": "http://127.0.0.1/secret"})
    site = {k.rstrip("/"): v for k, v in SITE.items()}
    if url in site:
        return httpx.Response(200, html=site[url])
    return httpx.Response(404)


def crawler(**kw):
    return SiteCrawler(transport=httpx.MockTransport(handler), url_guard=lambda u: None, **kw)


def test_crawl_stays_on_site_dedupes_and_skips_assets():
    pages = crawler().crawl("https://docs.test/", max_pages=10)
    assert [p.source_url for p in pages] == ["https://docs.test", "https://docs.test/a", "https://docs.test/b"]
    assert pages[1].title == "A"
    assert "refunds" in pages[1].sections[0].text


def test_crawl_respects_max_pages():
    assert len(crawler().crawl("https://docs.test/", max_pages=2)) == 2


def test_crawl_checks_redirect_targets_against_guard():
    def guard(url):
        if "127.0.0.1" in url:
            raise UnsafeUrl(url)

    c = SiteCrawler(transport=httpx.MockTransport(handler), url_guard=guard)
    assert c.crawl("https://docs.test/redirect", max_pages=5) == []
