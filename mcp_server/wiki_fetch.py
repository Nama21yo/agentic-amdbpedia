"""Fetch a Wikipedia article's wikitext by URL (refs the "paste a Wikipedia
link" chat/preview flow).

Deliberately restricted to `*.wikipedia.org` hosts: this fetches whatever
URL a caller supplies over the live HTTP server, so an unrestricted fetch
would be an open SSRF proxy, not a feature. `action=raw` returns the
article's raw wikitext directly (no JSON envelope, no rendered HTML) --
the exact shape `mcp_server.pipeline.extract_first_infobox` already parses.
Fetching the *whole* article and handing it to the existing pipeline
unmodified is enough: `extract_first_infobox` already finds "the first
infobox-like template" within arbitrarily larger wikitext, so there is no
need to special-case "just the infobox part" of the page here.

Same `Fetcher`-parameter shape as `scripts/refresh_wiki_cache.py::http_get`
on purpose -- tests inject a fake instead of touching the real network,
matching how every other real HTTP call in this repo is already tested.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from errors import ClientSafeError

_HEADERS = {"User-Agent": "agentic-amdbpedia/wiki-fetch"}
DEFAULT_TIMEOUT = 15.0

# Matches "wikipedia.org" itself and any subdomain (am.wikipedia.org,
# en.wikipedia.org, ...) -- this project is Amharic-focused, but nothing
# about extract_first_infobox is Amharic-specific, so no reason to reject
# a different language edition's article.
_ALLOWED_HOST_RE = re.compile(r"^([a-z0-9-]+\.)?wikipedia\.org$", re.IGNORECASE)


class WikipediaFetchError(ClientSafeError):
    """Raised for anything that stops a real article's wikitext from being
    fetched: an unsupported/malformed URL, a page that doesn't exist, or a
    real network failure. Always client-safe -- never leaks the raw
    exception or response body."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_type="wikipedia_fetch_failed")


def parse_article_url(url: str) -> tuple[str, str]:
    """Return `(base_url, page_title)` from a real Wikipedia article URL.

    Accepts both the common `/wiki/<Title>` path form and the
    `?title=<Title>` query form (index.php-style links) -- both are real,
    valid ways an Amharic Wikipedia article link actually looks in
    practice, verified live against am.wikipedia.org."""

    try:
        parsed = urllib.parse.urlsplit(url.strip())
    except ValueError as exc:
        raise WikipediaFetchError(f"Not a valid URL: {url!r}") from exc

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise WikipediaFetchError(f"Not a valid URL: {url!r}")
    if not _ALLOWED_HOST_RE.match(parsed.hostname or ""):
        raise WikipediaFetchError(
            f"Only wikipedia.org article links are supported, got host {parsed.hostname!r}"
        )

    base_url = f"{parsed.scheme}://{parsed.netloc}"

    if parsed.path.startswith("/wiki/"):
        title = urllib.parse.unquote(parsed.path[len("/wiki/") :])
    else:
        title = urllib.parse.parse_qs(parsed.query).get("title", [""])[0]

    if not title:
        raise WikipediaFetchError(f"Could not find an article title in {url!r}")

    return base_url, title


Fetcher = Callable[[str], bytes]


def _http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers=_HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:  # noqa: S310 - host allowlisted in parse_article_url
            body: bytes = response.read()
            return body
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise WikipediaFetchError(f"Could not reach {url}: {exc}") from exc


def fetch_article_wikitext(url: str, *, fetch: Fetcher = _http_get) -> tuple[str, str]:
    """Return `(page_title, wikitext)` for a real Wikipedia article URL.

    `fetch` overrides the real HTTP GET -- tests always inject a fake, the
    same pattern `scripts/refresh_wiki_cache.py`'s own fetch functions
    already use."""

    base_url, title = parse_article_url(url)
    raw_url = f"{base_url}/w/index.php?" + urllib.parse.urlencode({"title": title, "action": "raw"})

    body = fetch(raw_url)
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise WikipediaFetchError(f"Article {title!r} was not valid UTF-8") from exc

    if not text.strip():
        raise WikipediaFetchError(f"Article {title!r} appears to be empty or does not exist")

    return title, text
