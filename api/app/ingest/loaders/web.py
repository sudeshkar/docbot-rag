from collections import deque
from collections.abc import Callable
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx
import trafilatura
from bs4 import BeautifulSoup

from app.domain.types import LoadedDocument, Section
from app.ingest.url_safety import assert_public_url

USER_AGENT = "DocBotCrawler/1.0"
MAX_REDIRECTS = 5
MAX_PAGE_BYTES = 5 * 1024 * 1024
SKIP_SUFFIXES = (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".zip", ".mp4", ".css", ".js")


def _normalize(url: str) -> str:
    return urldefrag(url)[0].rstrip("/")


class SiteCrawler:
    """Breadth-first crawl of a single site.

    BFS with a deque (O(1) pops) and a visited set (O(1) membership) visits each URL once. Redirects
    are followed by hand so every hop passes the SSRF guard, not just the first URL.
    """

    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        url_guard: Callable[[str], None] = assert_public_url,
        timeout: float = 15.0,
    ):
        self.url_guard = url_guard
        self.client = httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT},
        )

    def crawl(self, start_url: str, max_pages: int) -> list[LoadedDocument]:
        start = _normalize(start_url)
        site = urlsplit(start).netloc
        visited = {start}
        queue = deque([start])
        pages: list[LoadedDocument] = []

        while queue and len(pages) < max_pages:
            url = queue.popleft()
            fetched = self._fetch(url)
            if fetched is None:
                continue
            final_url, html = fetched
            page = self._parse(final_url, html)
            if page.sections and page.sections[0].text.strip():
                pages.append(page)
            for link in self._links(final_url, html):
                if urlsplit(link).netloc == site and link not in visited:
                    visited.add(link)
                    queue.append(link)
        return pages

    def fetch_one(self, url: str) -> LoadedDocument | None:
        fetched = self._fetch(_normalize(url))
        return self._parse(*fetched) if fetched else None

    def _fetch(self, url: str) -> tuple[str, str] | None:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                self.url_guard(url)
                resp = self.client.get(url)
            except (httpx.HTTPError, ValueError):
                return None
            if resp.is_redirect and "location" in resp.headers:
                url = urljoin(url, resp.headers["location"])
                continue
            if resp.status_code != 200 or "text/html" not in resp.headers.get("content-type", ""):
                return None
            if len(resp.content) > MAX_PAGE_BYTES:
                return None
            return _normalize(str(resp.url)), resp.text
        return None

    @staticmethod
    def _parse(url: str, html: str) -> LoadedDocument:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        text = trafilatura.extract(html, output_format="markdown", include_tables=True) or ""
        if not text.strip():
            # trafilatura skips very short pages; fall back to visible text without chrome.
            for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
                tag.decompose()
            text = soup.get_text("\n", strip=True)
        return LoadedDocument(title=title[:500], sections=[Section(text=text)], source_url=url)

    @staticmethod
    def _links(base: str, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        out = []
        for a in soup.find_all("a", href=True):
            link = _normalize(urljoin(base + "/", a["href"]))
            if urlsplit(link).scheme in ("http", "https") and not link.lower().endswith(SKIP_SUFFIXES):
                out.append(link)
        return out
