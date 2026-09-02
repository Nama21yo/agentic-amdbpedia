"""Refresh cached MediaWiki exports from mappings.dbpedia.org (refs 12.1).

Pulls the `OntologyClass:`/`OntologyProperty:` namespaces (200/202) into
`data/wiki_cache/ontology.xml` and the `Mapping am:*` namespace (390) into
`data/wiki_cache/mapping_am.xml`, in exactly the `<mediawiki><page>...`
shape `rag/ontology.py`'s parsers already expect — refreshing never
requires touching the parsers. Namespace IDs, `allpages`/`export` API
shapes, and the unauthenticated 50-title `export` batch limit were all
verified live against the real wiki before writing this.

On any fetch failure, the existing cached file is left byte-identical to
before the run (write-to-temp-then-atomic-rename, and the write only
happens once every page has been fetched successfully) rather than
truncated or partially overwritten.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logging_config import log_event

LOGGER = logging.getLogger("dbpedia_mapping_assistant.refresh_wiki_cache")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ONTOLOGY_XML = PROJECT_ROOT / "data" / "wiki_cache" / "ontology.xml"
DEFAULT_MAPPING_AM_XML = PROJECT_ROOT / "data" / "wiki_cache" / "mapping_am.xml"

DEFAULT_BASE_URL = "https://mappings.dbpedia.org"
ONTOLOGY_CLASS_NAMESPACE = 200
ONTOLOGY_PROPERTY_NAMESPACE = 202
MAPPING_AM_NAMESPACE = 390

DEFAULT_TIMEOUT = 30.0
# The live API rejects more than 50 titles per unauthenticated export call
# ("toomanyvalues", limit 50) — verified against the real wiki.
DEFAULT_EXPORT_BATCH_SIZE = 50
DEFAULT_LIST_LIMIT = 500  # the live "max" aplimit resolves to for anon requests


class WikiFetchError(RuntimeError):
    """Raised when the live MediaWiki export could not be completed."""


Fetcher = Callable[[str, dict[str, str]], bytes]


def http_get(url: str, params: dict[str, str], *, timeout: float = DEFAULT_TIMEOUT) -> bytes:
    """Default Fetcher: a plain GET with no auth, matching the anonymous
    read-only access this script needs."""

    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}?{query}",
        headers={"User-Agent": "cross-lingual-mapping-assistant/refresh-wiki-cache"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed https base_url
            body: bytes = response.read()
            return body
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise WikiFetchError(f"Request to {url} failed: {exc}") from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def list_namespace_titles(
    base_url: str,
    namespace: int,
    *,
    fetch: Fetcher = http_get,
    limit: int = DEFAULT_LIST_LIMIT,
) -> list[str]:
    """Enumerate every page title in a namespace via action=query&list=allpages."""

    api_url = f"{base_url.rstrip('/')}/api.php"
    titles: list[str] = []
    apcontinue: str | None = None

    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "apnamespace": str(namespace),
            "aplimit": str(limit),
            "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue

        try:
            body = fetch(api_url, params)
            payload = json.loads(body)
        except (WikiFetchError, json.JSONDecodeError) as exc:
            raise WikiFetchError(f"Could not list namespace {namespace} pages: {exc}") from exc

        if "error" in payload:
            raise WikiFetchError(
                f"MediaWiki API error listing namespace {namespace}: {payload['error']}"
            )

        pages = payload.get("query", {}).get("allpages", [])
        titles.extend(page["title"] for page in pages if "title" in page)

        apcontinue = payload.get("continue", {}).get("apcontinue")
        if not apcontinue:
            return titles


def export_titles(
    base_url: str,
    titles: list[str],
    *,
    fetch: Fetcher = http_get,
    batch_size: int = DEFAULT_EXPORT_BATCH_SIZE,
) -> list[ET.Element]:
    """Fetch `<page>` elements for the given titles via action=query&export,
    batched under the live API's unauthenticated 50-title limit."""

    api_url = f"{base_url.rstrip('/')}/api.php"
    pages: list[ET.Element] = []

    for start in range(0, len(titles), batch_size):
        batch = titles[start : start + batch_size]
        params = {
            "action": "query",
            "export": "1",
            "exportnowrap": "1",
            "titles": "|".join(batch),
        }
        try:
            body = fetch(api_url, params)
            root = ET.fromstring(body)  # noqa: S314 - trusted, fixed HTTPS base_url
        except (WikiFetchError, ET.ParseError) as exc:
            raise WikiFetchError(
                f"Could not export batch {start}-{start + len(batch)}: {exc}"
            ) from exc

        pages.extend(element for element in root if _local_name(element.tag) == "page")

    return pages


def _write_merged_export(pages: list[ET.Element], destination: Path) -> None:
    """Write a `<mediawiki><page>...</mediawiki>` document, matching the
    shape `rag/ontology.py`'s parsers already expect. Writes to a temp file
    and renames atomically so an interrupted write never truncates the
    previous good cache."""

    root = ET.Element("mediawiki")
    for page in pages:
        root.append(page)

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_name(destination.name + ".tmp")
    ET.ElementTree(root).write(tmp_path, encoding="unicode", xml_declaration=False)
    tmp_path.replace(destination)


def _refresh(
    *,
    namespaces: list[int],
    base_url: str,
    destination: Path,
    fetch: Fetcher,
    event_prefix: str,
) -> int:
    try:
        titles: list[str] = []
        for namespace in namespaces:
            titles.extend(list_namespace_titles(base_url, namespace, fetch=fetch))
        pages = export_titles(base_url, titles, fetch=fetch)
    except WikiFetchError as exc:
        log_event(LOGGER, f"refresh.{event_prefix}_failed", error=str(exc))
        return 0

    _write_merged_export(pages, destination)
    log_event(LOGGER, f"refresh.{event_prefix}_completed", page_count=len(pages))
    return len(pages)


def refresh_ontology(
    *,
    base_url: str = DEFAULT_BASE_URL,
    destination: Path = DEFAULT_ONTOLOGY_XML,
    fetch: Fetcher = http_get,
) -> int:
    """Refresh data/wiki_cache/ontology.xml from the live wiki.

    Returns the number of pages written, or 0 (leaving `destination`
    untouched) on any fetch failure.
    """

    return _refresh(
        namespaces=[ONTOLOGY_CLASS_NAMESPACE, ONTOLOGY_PROPERTY_NAMESPACE],
        base_url=base_url,
        destination=destination,
        fetch=fetch,
        event_prefix="ontology",
    )


def refresh_mappings(
    *,
    base_url: str = DEFAULT_BASE_URL,
    destination: Path = DEFAULT_MAPPING_AM_XML,
    fetch: Fetcher = http_get,
) -> int:
    """Refresh data/wiki_cache/mapping_am.xml from the live wiki."""

    return _refresh(
        namespaces=[MAPPING_AM_NAMESPACE],
        base_url=base_url,
        destination=destination,
        fetch=fetch,
        event_prefix="mappings",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=["ontology", "mappings", "both"], default="both")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args(argv)

    exit_code = 0
    if args.target in {"ontology", "both"}:
        count = refresh_ontology(base_url=args.base_url)
        if count:
            print(f"Refreshed {count} ontology pages")
        else:
            print("Ontology refresh failed; cache left untouched", file=sys.stderr)
            exit_code = 1
    if args.target in {"mappings", "both"}:
        count = refresh_mappings(base_url=args.base_url)
        if count:
            print(f"Refreshed {count} mapping pages")
        else:
            print("Mapping refresh failed; cache left untouched", file=sys.stderr)
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
