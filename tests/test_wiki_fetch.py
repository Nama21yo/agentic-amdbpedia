from __future__ import annotations

import pytest

from mcp_server.wiki_fetch import (
    WikipediaFetchError,
    fetch_article_wikitext,
    parse_article_url,
)

GERD_WIKITEXT = "{{መረጃሳጥን ግድብ\n| ስም = ታላቁ ግድብ\n| ወንዝ = አባይ ወንዝ\n}}\n\n'''ታላቁ ግድብ''' ...\n"


def test_parse_article_url_handles_the_wiki_path_form() -> None:
    base_url, title = parse_article_url("https://am.wikipedia.org/wiki/ታላቁ_የኢትዮጵያ_ሕዳሴ_ግድብ")

    assert base_url == "https://am.wikipedia.org"
    assert title == "ታላቁ_የኢትዮጵያ_ሕዳሴ_ግድብ"


def test_parse_article_url_handles_the_index_php_query_form() -> None:
    base_url, title = parse_article_url(
        "https://am.wikipedia.org/w/index.php?title=ታላቁ_የኢትዮጵያ_ሕዳሴ_ግድብ&action=view"
    )

    assert base_url == "https://am.wikipedia.org"
    assert title == "ታላቁ_የኢትዮጵያ_ሕዳሴ_ግድብ"


def test_parse_article_url_accepts_any_wikipedia_language_edition() -> None:
    base_url, title = parse_article_url("https://en.wikipedia.org/wiki/Ethiopia")

    assert base_url == "https://en.wikipedia.org"
    assert title == "Ethiopia"


@pytest.mark.parametrize(
    "url",
    [
        "https://mappings.dbpedia.org/wiki/Something",  # real wiki, wrong host
        "https://evil.example.com/wikipedia.org/wiki/Trick",  # not actually wikipedia.org
        "https://wikipedia.org.evil.example.com/wiki/Trick",  # suffix trick
        "ftp://am.wikipedia.org/wiki/Title",  # not http(s)
        "not a url at all",
        "",
    ],
)
def test_parse_article_url_rejects_non_wikipedia_hosts(url: str) -> None:
    with pytest.raises(WikipediaFetchError):
        parse_article_url(url)


def test_parse_article_url_rejects_a_link_with_no_title() -> None:
    with pytest.raises(WikipediaFetchError, match="title"):
        parse_article_url("https://am.wikipedia.org/w/index.php?action=view")


def test_fetch_article_wikitext_returns_title_and_wikitext() -> None:
    captured: dict[str, str] = {}

    def fake_fetch(url: str) -> bytes:
        captured["url"] = url
        return GERD_WIKITEXT.encode("utf-8")

    title, wikitext = fetch_article_wikitext(
        "https://am.wikipedia.org/wiki/ታላቁ_የኢትዮጵያ_ሕዳሴ_ግድብ", fetch=fake_fetch
    )

    assert title == "ታላቁ_የኢትዮጵያ_ሕዳሴ_ግድብ"
    assert wikitext == GERD_WIKITEXT
    assert "action=raw" in captured["url"]
    assert "am.wikipedia.org" in captured["url"]


def test_fetch_article_wikitext_wraps_a_fetch_failure() -> None:
    def failing_fetch(url: str) -> bytes:
        raise WikipediaFetchError("HTTP 404: Not Found")

    with pytest.raises(WikipediaFetchError):
        fetch_article_wikitext("https://am.wikipedia.org/wiki/DoesNotExist", fetch=failing_fetch)


def test_fetch_article_wikitext_rejects_empty_body() -> None:
    def empty_fetch(url: str) -> bytes:
        return b""

    with pytest.raises(WikipediaFetchError, match="empty"):
        fetch_article_wikitext("https://am.wikipedia.org/wiki/Blank", fetch=empty_fetch)


def test_fetch_article_wikitext_rejects_non_utf8_body() -> None:
    def bad_encoding_fetch(url: str) -> bytes:
        return b"\xff\xfe not utf-8"

    with pytest.raises(WikipediaFetchError, match="UTF-8"):
        fetch_article_wikitext("https://am.wikipedia.org/wiki/Bad", fetch=bad_encoding_fetch)
