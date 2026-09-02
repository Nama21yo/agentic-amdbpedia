from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from config import Settings
from mcp_server.consent import ConsentRequiredError, require_consent
from mcp_server.publish import (
    MediaWikiCredentialsError,
    PublishError,
    build_mapping_wikitext,
    publish_mapping,
)

SAMPLE_MAPPINGS = [
    {"templateProperty": "አይካኦ_ኮድ", "ontologyProperty": "icaoLocationIdentifier"},
    {"templateProperty": "አያታ_ኮድ", "ontologyProperty": "iataLocationIdentifier"},
]


def _settings(**overrides: Any) -> Settings:
    base = {
        "GROQ_API_KEY": "gsk_test_placeholder",
        "MEDIAWIKI_BOT_USERNAME": "TestBot@publish-bot",
        "MEDIAWIKI_BOT_PASSWORD": "test-bot-password",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


class FakeTransport:
    """Scripts the exact login -> csrf -> edit sequence publish_mapping
    drives, without any network access — publishing to the real wiki is
    never something this test suite attempts (see mcp_server/publish.py's
    module docstring)."""

    def __init__(
        self,
        *,
        login_result: str = "Success",
        edit_result: str = "Success",
        omit_login_token: bool = False,
        omit_csrf_token: bool = False,
    ) -> None:
        self.login_result = login_result
        self.edit_result = edit_result
        self.omit_login_token = omit_login_token
        self.omit_csrf_token = omit_csrf_token
        self.get_calls: list[dict[str, str]] = []
        self.post_calls: list[dict[str, str]] = []

    def get(self, params: dict[str, str]) -> dict[str, Any]:
        self.get_calls.append(params)
        if params["type"] == "login":
            if self.omit_login_token:
                return {"query": {"tokens": {}}}
            return {"query": {"tokens": {"logintoken": "fake-login-token"}}}
        if self.omit_csrf_token:
            return {"query": {"tokens": {}}}
        return {"query": {"tokens": {"csrftoken": "fake-csrf-token"}}}

    def post(self, data: dict[str, str]) -> dict[str, Any]:
        self.post_calls.append(data)
        if data["action"] == "login":
            return {"login": {"result": self.login_result}}
        return {"edit": {"result": self.edit_result, "title": data["title"]}}


def test_publish_is_refused_without_consent() -> None:
    transport = FakeTransport()

    with pytest.raises(ConsentRequiredError):
        require_consent(approved=False)(publish_mapping)(
            "Infobox airport",
            "Airport",
            SAMPLE_MAPPINGS,
            settings=_settings(),
            transport=transport,
        )

    assert transport.get_calls == []
    assert transport.post_calls == []


def test_publish_succeeds_with_consent_and_a_mocked_successful_edit() -> None:
    transport = FakeTransport()

    title = require_consent(approved=True)(publish_mapping)(
        "Infobox airport", "Airport", SAMPLE_MAPPINGS, settings=_settings(), transport=transport
    )

    assert title == "Mapping am:Infobox airport"
    assert transport.post_calls[-1]["action"] == "edit"
    assert transport.post_calls[-1]["token"] == "fake-csrf-token"
    assert transport.post_calls[-1]["bot"] == "1"


def test_publish_follows_the_login_then_csrf_then_edit_sequence() -> None:
    transport = FakeTransport()

    publish_mapping(
        "Infobox airport", "Airport", SAMPLE_MAPPINGS, settings=_settings(), transport=transport
    )

    assert [call["type"] for call in transport.get_calls] == ["login", "csrf"]
    assert [call["action"] for call in transport.post_calls] == ["login", "edit"]
    assert transport.post_calls[0]["lgname"] == "TestBot@publish-bot"
    assert transport.post_calls[0]["lgtoken"] == "fake-login-token"


def test_publish_raises_without_configured_credentials() -> None:
    settings = _settings(MEDIAWIKI_BOT_USERNAME=None, MEDIAWIKI_BOT_PASSWORD=None)

    with pytest.raises(MediaWikiCredentialsError):
        publish_mapping(
            "Infobox airport",
            "Airport",
            SAMPLE_MAPPINGS,
            settings=settings,
            transport=FakeTransport(),
        )


def test_publish_raises_on_a_failed_login() -> None:
    transport = FakeTransport(login_result="Failed")

    with pytest.raises(PublishError, match="login failed"):
        publish_mapping(
            "Infobox airport", "Airport", SAMPLE_MAPPINGS, settings=_settings(), transport=transport
        )


def test_publish_raises_when_no_login_token_is_returned() -> None:
    transport = FakeTransport(omit_login_token=True)

    with pytest.raises(PublishError, match="login token"):
        publish_mapping(
            "Infobox airport", "Airport", SAMPLE_MAPPINGS, settings=_settings(), transport=transport
        )


def test_publish_raises_when_no_csrf_token_is_returned() -> None:
    transport = FakeTransport(omit_csrf_token=True)

    with pytest.raises(PublishError, match="CSRF token"):
        publish_mapping(
            "Infobox airport", "Airport", SAMPLE_MAPPINGS, settings=_settings(), transport=transport
        )


def test_publish_raises_when_the_edit_is_rejected() -> None:
    transport = FakeTransport(edit_result="Failure")

    with pytest.raises(PublishError, match="edit was rejected"):
        publish_mapping(
            "Infobox airport", "Airport", SAMPLE_MAPPINGS, settings=_settings(), transport=transport
        )


def test_build_mapping_wikitext_round_trips_through_the_real_parser(tmp_path: Path) -> None:
    """The stated design goal: publish output and rag/ontology.py's parser
    share the same wikitext format."""

    from rag.ontology import AmharicMappingIndex

    wikitext = build_mapping_wikitext("Airport", SAMPLE_MAPPINGS)

    page_xml = (
        "<mediawiki><page><title>Mapping am:Infobox airport</title>"
        f"<revision><text>{wikitext}</text></revision></page></mediawiki>"
    )
    mapping_path = tmp_path / "mapping_am.xml"
    mapping_path.write_text(page_xml, encoding="utf-8")

    index = AmharicMappingIndex.from_mapping_xml(mapping_path)

    icao = index.lookup("አይካኦ_ኮድ")
    assert icao is not None
    assert icao.ontology_property == "icaoLocationIdentifier"
    iata = index.lookup("አያታ_ኮድ")
    assert iata is not None
    assert iata.ontology_property == "iataLocationIdentifier"
