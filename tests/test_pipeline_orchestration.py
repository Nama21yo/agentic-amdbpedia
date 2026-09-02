from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool

from db.session import init_models, list_review_items, session_factory
from mcp_server.pipeline import PipelineResult, run_mapping_pipeline
from rag.ontology import AmharicMappingIndex
from rag.predict import PredictionResult
from rag.retrieval import NoMatchFound, SearchResult

BRIDGE_WIKITEXT = """{{መረጃሳጥን ድልድይ
| ስም = ደደሳ ድልድይ
| ርዝመት = 1,700 ሜትር
}}"""


def _empty_mapping_index() -> AmharicMappingIndex:
    return AmharicMappingIndex({})


class FakePrediction:
    def __init__(self, property_name: str, score: float) -> None:
        self.property = property_name
        self.used_llm = False
        self.candidates = [property_name]
        self.top_retrieval_result = SearchResult(
            property=property_name, ontology_class="Bridge", score=score, payload={}
        )
        self.reason = ""


def _fake_predict_property(amharic_property: str, **kwargs: Any) -> Any:
    known = {
        "ርዝመት": "length",
        "ስም": "name",
    }
    if amharic_property not in known:
        return NoMatchFound(query=amharic_property)
    fake = FakePrediction(known[amharic_property], 1.0)
    return PredictionResult(
        property=fake.property,
        used_llm=False,
        candidates=fake.candidates,
        top_retrieval_result=fake.top_retrieval_result,
    )


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    await init_models(test_engine)
    yield test_engine
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_full_pipeline_end_to_end_produces_a_pending_review_row_with_length_predicted(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stated 16.2 acceptance criterion, run against a real (SQLite)
    database end to end -- only the retriever/predictor is faked, for
    speed (the real one needs the ~2,948-property embedding index)."""

    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)

    async with factory() as session:
        result = await run_mapping_pipeline(
            BRIDGE_WIKITEXT,
            domain_class="Bridge",
            session=session,
            mapping_index=_empty_mapping_index(),
        )

    assert isinstance(result, PipelineResult)
    assert result.template_name == "መረጃሳጥን ድልድይ"
    length_mapping = next(m for m in result.mappings if m["templateProperty"] == "ርዝመት")
    assert length_mapping["ontologyProperty"] == "length"
    assert result.review_item_id is not None

    async with factory() as session:
        items = await list_review_items(session, status="pending_review")
    assert len(items) == 1
    assert items[0].id == result.review_item_id
    stored_length = next(m for m in items[0].mappings if m["templateProperty"] == "ርዝመት")
    assert stored_length["ontologyProperty"] == "length"


@pytest.mark.asyncio
async def test_pipeline_generates_valid_xml_and_wikitext(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)

    async with factory() as session:
        result = await run_mapping_pipeline(
            BRIDGE_WIKITEXT,
            domain_class="Bridge",
            session=session,
            mapping_index=_empty_mapping_index(),
        )

    assert '<TemplateMapping mapToClass="dbo:Bridge">' in result.xml_rules
    assert "<ontologyProperty>length</ontologyProperty>" in result.xml_rules
    assert "{{TemplateMapping" in result.mapping_wikitext
    assert "{{PropertyMapping | templateProperty = ርዝመት | ontologyProperty = length }}" in (
        result.mapping_wikitext
    )


@pytest.mark.asyncio
async def test_pipeline_skips_fields_already_in_the_mapping_index(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)

    from rag.ontology import ExistingTemplateMapping

    already_mapped_index = AmharicMappingIndex(
        {"ስም": ExistingTemplateMapping(template_property="ስም", ontology_property="foaf:name")}
    )

    async with factory() as session:
        result = await run_mapping_pipeline(
            BRIDGE_WIKITEXT,
            domain_class="Bridge",
            session=session,
            mapping_index=already_mapped_index,
        )

    template_properties = {m["templateProperty"] for m in result.mappings}
    assert "ስም" not in template_properties
    assert "ርዝመት" in template_properties
    assert any("Skipped 1 field" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_pipeline_handles_wikitext_with_no_infobox(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)

    async with factory() as session:
        result = await run_mapping_pipeline(
            "just some prose, no templates at all",
            domain_class="Bridge",
            session=session,
            mapping_index=_empty_mapping_index(),
        )

    assert result.mappings == []
    assert result.review_item_id is None
    assert any("No infobox" in warning for warning in result.warnings)

    async with factory() as session:
        items = await list_review_items(session)
    assert items == []


@pytest.mark.asyncio
async def test_pipeline_handles_fields_with_no_retrieval_candidates(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)

    async with factory() as session:
        result = await run_mapping_pipeline(
            "{{Infobox bridge | ያልታወቀ_መስክ = something}}",
            domain_class="Bridge",
            session=session,
            mapping_index=_empty_mapping_index(),
        )

    assert result.mappings == []
    assert any("No retrieval candidates" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_pipeline_uses_a_provided_run_id(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)

    async with factory() as session:
        result = await run_mapping_pipeline(
            BRIDGE_WIKITEXT,
            domain_class="Bridge",
            session=session,
            run_id="my-fixed-run-id",
            mapping_index=_empty_mapping_index(),
        )

    assert result.run_id == "my-fixed-run-id"


@pytest.mark.asyncio
async def test_pipeline_respects_a_deliberately_empty_mapping_index(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: AmharicMappingIndex defines __len__, so an empty
    (but explicitly given, valid) index is falsy in Python -- a naive
    `mapping_index or default()` fallback would silently discard it and
    load the real default cache instead, found via a live smoke test
    against real data before this test was written to lock in the fix."""

    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)
    empty_index = _empty_mapping_index()
    assert len(empty_index) == 0
    assert not empty_index  # confirms the falsy-empty-object premise

    async with factory() as session:
        result = await run_mapping_pipeline(
            BRIDGE_WIKITEXT, domain_class="Bridge", session=session, mapping_index=empty_index
        )

    # ስም would be filtered out if the real default cache were used instead
    # (it's a genuinely published mapping there) -- with the deliberately
    # empty index respected, nothing gets filtered.
    template_properties = {m["templateProperty"] for m in result.mappings}
    assert "ስም" in template_properties
    assert not any("Skipped" in warning for warning in result.warnings)


@pytest.mark.asyncio
async def test_pipeline_generates_a_run_id_when_not_given(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("mcp_server.pipeline.predict_property", _fake_predict_property)
    factory = session_factory(engine)

    async with factory() as session:
        result = await run_mapping_pipeline(
            BRIDGE_WIKITEXT,
            domain_class="Bridge",
            session=session,
            mapping_index=_empty_mapping_index(),
        )

    assert result.run_id
