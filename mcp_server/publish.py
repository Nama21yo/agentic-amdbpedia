"""Consent-gated MediaWiki publish (refs implementation.md 14.3).

Publishing a mapping is a real, outward-facing, hard-to-reverse write to
the live mappings.dbpedia.org wiki, under a bot account (Bot Password —
`Special:BotPasswords` — only, never a real user password). `publish_mapping`
itself never checks consent; per `mcp_server.consent`'s own decorator
-factory design, a caller must wrap the call site itself:
`require_consent(approved=user_said_yes)(publish_mapping)(...)`. This
module is never exercised against the real live wiki in tests — every test
here runs against an injected fake transport, matching how
`scripts/refresh_wiki_cache.py` stays testable without live network
access, except here a live call would be a real, irreversible write, so no
"proven live" claim is made or attempted for this one.
"""

from __future__ import annotations

import http.cookiejar
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

from config import Settings
from errors import ClientSafeError
from logging_config import log_event

LOGGER = logging.getLogger("dbpedia_mapping_assistant.publish")

_HEADERS = {"User-Agent": "agentic-amdbpedia/publish"}


class PublishError(ClientSafeError):
    """Raised when a publish attempt fails for any reason (network, auth,
    a rejected edit) — never leaks raw credentials or response bodies."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_type="publish_failed")


class MediaWikiCredentialsError(PublishError):
    def __init__(self) -> None:
        super().__init__("MediaWiki bot credentials are not configured")


class MediaWikiTransport(Protocol):
    """GET/POST against the MediaWiki API, sharing session state (cookies)
    across calls — the login -> csrf-token -> edit sequence needs the same
    authenticated session throughout."""

    def get(self, params: dict[str, str]) -> dict[str, Any]: ...
    def post(self, data: dict[str, str]) -> dict[str, Any]: ...


class RealMediaWikiTransport:
    """The real transport: a cookie-jar-aware urllib opener. Never used in
    tests — see this module's docstring."""

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.api_url = f"{base_url.rstrip('/')}/api.php"
        self.timeout = timeout
        self._cookie_jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._cookie_jar)
        )

    def get(self, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        request = urllib.request.Request(f"{self.api_url}?{query}", headers=_HEADERS)
        return self._call(request)

    def post(self, data: dict[str, str]) -> dict[str, Any]:
        encoded = urllib.parse.urlencode(data).encode("utf-8")
        request = urllib.request.Request(
            self.api_url, data=encoded, headers=_HEADERS, method="POST"
        )
        return self._call(request)

    def _call(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            with self._opener.open(request, timeout=self.timeout) as response:  # noqa: S310
                body = response.read()
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise PublishError(f"MediaWiki API request failed: {exc.__class__.__name__}") from exc
        try:
            payload: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            raise PublishError("MediaWiki API returned a non-JSON response") from exc
        return payload


def build_mapping_wikitext(domain_class: str, mappings: list[dict[str, str]]) -> str:
    """Build the `{{TemplateMapping | mapToClass = ... | mappings = ...}}`
    wikitext `rag/ontology.py`'s `AmharicMappingIndex` already parses —
    publish output and the parser share the exact same format on purpose,
    so a page this function writes is immediately readable by this repo's
    own corpus the next time it refreshes."""

    lines = ["{{TemplateMapping", f" | mapToClass = {domain_class}", " | mappings ="]
    for mapping in mappings:
        lines.append(
            f"  {{{{PropertyMapping | templateProperty = {mapping['templateProperty']}"
            f" | ontologyProperty = {mapping['ontologyProperty']} }}}}"
        )
    lines.append("}}")
    return "\n".join(lines)


def _login(transport: MediaWikiTransport, username: str, password: str) -> None:
    token_response = transport.get(
        {"action": "query", "meta": "tokens", "type": "login", "format": "json"}
    )
    try:
        login_token = token_response["query"]["tokens"]["logintoken"]
    except KeyError as exc:
        raise PublishError("Could not obtain a MediaWiki login token") from exc

    login_response = transport.post(
        {
            "action": "login",
            "lgname": username,
            "lgpassword": password,
            "lgtoken": login_token,
            "format": "json",
        }
    )
    result = login_response.get("login", {}).get("result")
    if result != "Success":
        raise PublishError(f"MediaWiki login failed: {result or 'unknown error'}")


def _csrf_token(transport: MediaWikiTransport) -> str:
    response = transport.get(
        {"action": "query", "meta": "tokens", "type": "csrf", "format": "json"}
    )
    try:
        token: str = response["query"]["tokens"]["csrftoken"]
    except KeyError as exc:
        raise PublishError("Could not obtain a MediaWiki CSRF token") from exc
    return token


def _edit_page(
    transport: MediaWikiTransport, title: str, text: str, summary: str, token: str
) -> None:
    response = transport.post(
        {
            "action": "edit",
            "title": title,
            "text": text,
            "summary": summary,
            "bot": "1",
            "token": token,
            "format": "json",
        }
    )
    result = response.get("edit", {}).get("result")
    if result != "Success":
        raise PublishError(f"MediaWiki edit was rejected: {result or 'unknown error'}")


def publish_mapping(
    template_name: str,
    domain_class: str,
    mappings: list[dict[str, str]],
    *,
    settings: Settings | None = None,
    transport: MediaWikiTransport | None = None,
    summary: str = "Publish via cross-lingual mapping assistant",
) -> str:
    """Log in as the bot, fetch a CSRF token, and edit `Mapping am:<template_name>`.

    Returns the published page title on success. The caller is responsible
    for the consent gate — see this module's docstring — and for flipping
    the review item's status to "published" and firing the eager corpus
    -refresh hook (12.2) afterward; this function only performs the write.
    """

    resolved_settings = settings or Settings()
    if not resolved_settings.mediawiki_bot_username or not resolved_settings.mediawiki_bot_password:
        raise MediaWikiCredentialsError()

    resolved_transport = transport or RealMediaWikiTransport(resolved_settings.mediawiki_base_url)

    _login(
        resolved_transport,
        resolved_settings.mediawiki_bot_username,
        resolved_settings.mediawiki_bot_password,
    )
    token = _csrf_token(resolved_transport)
    title = f"Mapping am:{template_name}"
    wikitext = build_mapping_wikitext(domain_class, mappings)
    _edit_page(resolved_transport, title, wikitext, summary, token)

    log_event(LOGGER, "publish.completed", title=title)
    return title
