from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.applications import Starlette
from starlette.testclient import TestClient

from db.session import (
    InvalidReviewStatusError,
    ReviewNotFoundError,
    create_review_item,
    get_review_item,
    init_models,
    list_review_items,
    session_factory,
    set_review_status,
)
from mcp_server.http_app import create_app
from rag.training_log import read_examples

SAMPLE_MAPPINGS = [
    {"templateProperty": "አይካኦ_ኮድ", "ontologyProperty": "icaoLocationIdentifier", "confidence": 0.9}
]


def _in_memory_engine() -> AsyncEngine:
    return create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )


def _make_app(*, training_log_path: Path | None = None) -> Starlette:
    return create_app(engine=_in_memory_engine(), training_log_path=training_log_path)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    # StaticPool: a single shared connection, so SQLite's :memory: database
    # survives across the multiple separate sessions these tests open --
    # otherwise each new connection would see its own empty database.
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    await init_models(test_engine)
    yield test_engine
    await test_engine.dispose()


@pytest.mark.asyncio
async def test_create_review_item_persists_a_row(engine: AsyncEngine) -> None:
    factory = session_factory(engine)
    async with factory() as session:
        item = await create_review_item(
            session,
            run_id="run-1",
            template_name="Infobox airport",
            domain_class="Airport",
            mappings=SAMPLE_MAPPINGS,
        )

    assert item.id
    assert item.status == "pending_review"
    assert item.run_id == "run-1"


@pytest.mark.asyncio
async def test_list_review_items_returns_created_rows_oldest_first(engine: AsyncEngine) -> None:
    factory = session_factory(engine)
    async with factory() as session:
        await create_review_item(
            session, run_id="r1", template_name="A", domain_class="Airport", mappings=[]
        )
        await create_review_item(
            session, run_id="r2", template_name="B", domain_class="Dam", mappings=[]
        )

    async with factory() as session:
        items = await list_review_items(session)

    assert [item.template_name for item in items] == ["A", "B"]


@pytest.mark.asyncio
async def test_list_review_items_filters_by_status(engine: AsyncEngine) -> None:
    factory = session_factory(engine)
    async with factory() as session:
        created = await create_review_item(
            session, run_id="r1", template_name="A", domain_class="Airport", mappings=[]
        )
        await create_review_item(
            session, run_id="r2", template_name="B", domain_class="Dam", mappings=[]
        )
        await set_review_status(session, created.id, "approved")

    async with factory() as session:
        approved = await list_review_items(session, status="approved")
        pending = await list_review_items(session, status="pending_review")

    assert [item.template_name for item in approved] == ["A"]
    assert [item.template_name for item in pending] == ["B"]


@pytest.mark.asyncio
async def test_list_review_items_rejects_an_unknown_status(engine: AsyncEngine) -> None:
    factory = session_factory(engine)
    async with factory() as session:
        with pytest.raises(InvalidReviewStatusError):
            await list_review_items(session, status="not_a_real_status")


@pytest.mark.asyncio
async def test_get_review_item_raises_not_found_for_a_missing_id(engine: AsyncEngine) -> None:
    factory = session_factory(engine)
    async with factory() as session:
        with pytest.raises(ReviewNotFoundError):
            await get_review_item(session, "does-not-exist")


@pytest.mark.asyncio
async def test_set_review_status_transitions_and_persists(engine: AsyncEngine) -> None:
    factory = session_factory(engine)
    async with factory() as session:
        created = await create_review_item(
            session, run_id="r1", template_name="A", domain_class="Airport", mappings=[]
        )

    async with factory() as session:
        updated = await set_review_status(session, created.id, "approved")

    assert updated.status == "approved"

    async with factory() as session:
        refetched = await get_review_item(session, created.id)
    assert refetched.status == "approved"


def test_post_v1_reviews_creates_a_row_and_returns_frontend_shaped_json() -> None:
    app = _make_app()

    with TestClient(app) as client:
        response = client.post(
            "/v1/reviews",
            json={
                "run_id": "run-1",
                "template_name": "Infobox airport",
                "domain_class": "Airport",
                "mappings": SAMPLE_MAPPINGS,
            },
        )

        assert response.status_code == 201
        body = response.json()
        # Exactly frontend/src/lib/types.ts::ReviewItem's field set --
        # camelCase, no run_id leaking through (that's DB-internal only).
        assert set(body.keys()) == {
            "id",
            "templateName",
            "domainClass",
            "status",
            "submittedAt",
            "mappings",
        }
        assert body["templateName"] == "Infobox airport"
        assert body["domainClass"] == "Airport"
        assert body["status"] == "pending_review"
        assert body["mappings"] == SAMPLE_MAPPINGS


def test_post_v1_reviews_rejects_missing_required_fields() -> None:
    app = _make_app()

    with TestClient(app) as client:
        response = client.post("/v1/reviews", json={"run_id": "run-1"})

        assert response.status_code == 400
        assert response.json()["error_type"] == "validation"


def test_get_v1_reviews_lists_created_items() -> None:
    app = _make_app()

    with TestClient(app) as client:
        client.post(
            "/v1/reviews",
            json={
                "run_id": "run-1",
                "template_name": "A",
                "domain_class": "Airport",
                "mappings": [],
            },
        )

        response = client.get("/v1/reviews")

        assert response.status_code == 200
        items = response.json()
        assert len(items) == 1
        assert items[0]["templateName"] == "A"


def test_get_v1_reviews_by_id_returns_404_for_missing_review() -> None:
    app = _make_app()

    with TestClient(app) as client:
        response = client.get("/v1/reviews/does-not-exist")

        assert response.status_code == 404
        assert response.json()["error_type"] == "not_found"


def test_decide_review_approves_without_a_correction_and_logs_no_correction(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "training_examples.jsonl"
    app = _make_app(training_log_path=log_path)

    with TestClient(app) as client:
        created = client.post(
            "/v1/reviews",
            json={
                "run_id": "run-1",
                "template_name": "Infobox airport",
                "domain_class": "Airport",
                "mappings": SAMPLE_MAPPINGS,
            },
        ).json()

        response = client.post(
            f"/v1/reviews/{created['id']}/decision", json={"decision": "approved"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["mappings"] == SAMPLE_MAPPINGS

    examples = read_examples(log_path)
    assert len(examples) == 1
    assert examples[0].was_correction is False
    assert examples[0].property_class == "icaoLocationIdentifier"
    assert examples[0].run_id == "run-1"


def test_decide_review_with_a_correction_logs_was_correction_true(tmp_path: Path) -> None:
    """The stated 14.2 acceptance criterion: approving a corrected mapping
    logs was_correction: true."""

    log_path = tmp_path / "training_examples.jsonl"
    app = _make_app(training_log_path=log_path)

    with TestClient(app) as client:
        created = client.post(
            "/v1/reviews",
            json={
                "run_id": "run-1",
                "template_name": "Infobox airport",
                "domain_class": "Airport",
                "mappings": SAMPLE_MAPPINGS,
            },
        ).json()

        corrected = [
            {
                "templateProperty": "አይካኦ_ኮድ",
                "ontologyProperty": "iataLocationIdentifier",  # human corrected this
                "confidence": 0.9,
            }
        ]
        response = client.post(
            f"/v1/reviews/{created['id']}/decision",
            json={"decision": "approved", "corrected_mappings": corrected},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["mappings"] == corrected

    examples = read_examples(log_path)
    assert len(examples) == 1
    assert examples[0].was_correction is True
    assert examples[0].model_predicted == "icaoLocationIdentifier"
    assert examples[0].property_class == "iataLocationIdentifier"


def test_decide_review_rejection_still_logs_a_training_example(tmp_path: Path) -> None:
    """13.1's design point: every decision becomes training data whether or
    not it later gets published."""

    log_path = tmp_path / "training_examples.jsonl"
    app = _make_app(training_log_path=log_path)

    with TestClient(app) as client:
        created = client.post(
            "/v1/reviews",
            json={
                "run_id": "run-1",
                "template_name": "Infobox airport",
                "domain_class": "Airport",
                "mappings": SAMPLE_MAPPINGS,
            },
        ).json()

        response = client.post(
            f"/v1/reviews/{created['id']}/decision", json={"decision": "rejected"}
        )

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    assert len(read_examples(log_path)) == 1


def test_decide_review_rejects_an_unknown_decision_value(tmp_path: Path) -> None:
    app = _make_app(training_log_path=tmp_path / "training_examples.jsonl")

    with TestClient(app) as client:
        created = client.post(
            "/v1/reviews",
            json={
                "run_id": "run-1",
                "template_name": "A",
                "domain_class": "Airport",
                "mappings": SAMPLE_MAPPINGS,
            },
        ).json()

        response = client.post(f"/v1/reviews/{created['id']}/decision", json={"decision": "maybe"})

        assert response.status_code == 400
        assert response.json()["error_type"] == "validation"


def test_decide_review_returns_404_for_a_missing_review(tmp_path: Path) -> None:
    app = _make_app(training_log_path=tmp_path / "training_examples.jsonl")

    with TestClient(app) as client:
        response = client.post("/v1/reviews/does-not-exist/decision", json={"decision": "approved"})

        assert response.status_code == 404
        assert response.json()["error_type"] == "not_found"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_review_queue_works_against_a_real_postgres_instance() -> None:
    """Verified against docker-compose's real postgres service, not just
    SQLite — SQLite and Postgres can silently disagree on JSON column
    handling, so this is a real, not hypothetical, compatibility check."""

    real_engine = create_async_engine(
        "postgresql+asyncpg://mapping_assistant:mapping_assistant@localhost:5435/mapping_assistant"
    )
    try:
        await init_models(real_engine)
        factory = session_factory(real_engine)
        async with factory() as session:
            item = await create_review_item(
                session,
                run_id="pg-run-1",
                template_name="Infobox airport (postgres)",
                domain_class="Airport",
                mappings=SAMPLE_MAPPINGS,
            )
            fetched = await get_review_item(session, item.id)
            assert fetched.mappings == SAMPLE_MAPPINGS
            assert fetched.template_name == "Infobox airport (postgres)"

            # Clean up after ourselves -- this hits a real, possibly shared
            # Postgres instance, not a throwaway per-test database.
            await session.delete(fetched)
            await session.commit()
    finally:
        await real_engine.dispose()
