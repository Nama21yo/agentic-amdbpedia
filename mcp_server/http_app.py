"""HTTP layer for the review queue (refs implementation.md 14.1/14.2).

A separate Starlette ASGI app from `mcp_server/server.py`'s stdio-based
FastMCP tool interface — this is the general HTTP surface
`frontend/src/lib/api.ts` and `agentic-dbpedia`'s pipeline actually call.
Run it with `uvicorn mcp_server.http_app:app`.

Every response the frontend reads matches `frontend/src/lib/types.ts`'s
shapes field-for-field (camelCase) via `ReviewItem.to_api_dict()` — not
just "close enough".
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from config import Settings
from db.models import ReviewItem
from db.session import (
    InvalidReviewStatusError,
    ReviewNotFoundError,
    create_engine,
    create_review_item,
    get_review_item,
    init_models,
    list_review_items,
    session_factory,
)
from errors import AssistantValidationError, ClientSafeError
from logging_config import correlation_context, get_correlation_id, log_event

LOGGER = logging.getLogger("dbpedia_mapping_assistant.http")

REQUIRED_CREATE_FIELDS = ("run_id", "template_name", "domain_class", "mappings")


def _error_response(error: ClientSafeError, status_code: int) -> JSONResponse:
    payload = error.to_payload()
    payload["correlation_id"] = get_correlation_id()
    return JSONResponse(payload, status_code=status_code)


def _session_factory_from_state(request: Request) -> async_sessionmaker[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


async def create_review(request: Request) -> JSONResponse:
    with correlation_context():
        try:
            body: Any = await request.json()
        except Exception:
            return _error_response(AssistantValidationError("Request body must be valid JSON"), 400)

        if not isinstance(body, dict):
            return _error_response(
                AssistantValidationError("Request body must be a JSON object"), 400
            )

        missing = [field for field in REQUIRED_CREATE_FIELDS if field not in body]
        if missing:
            return _error_response(
                AssistantValidationError(f"Missing required field(s): {', '.join(missing)}"), 400
            )

        factory = _session_factory_from_state(request)
        async with factory() as session:
            item = await create_review_item(
                session,
                run_id=body["run_id"],
                template_name=body["template_name"],
                domain_class=body["domain_class"],
                mappings=body["mappings"],
            )

        log_event(LOGGER, "http.review_created", review_id=item.id)
        return JSONResponse(item.to_api_dict(), status_code=201)


async def list_reviews(request: Request) -> JSONResponse:
    with correlation_context():
        status = request.query_params.get("status")
        factory = _session_factory_from_state(request)
        async with factory() as session:
            try:
                items = await list_review_items(session, status=status)
            except InvalidReviewStatusError as exc:
                return _error_response(exc, 400)

        return JSONResponse([item.to_api_dict() for item in items])


async def get_review(request: Request) -> JSONResponse:
    with correlation_context():
        review_id = request.path_params["review_id"]
        factory = _session_factory_from_state(request)
        async with factory() as session:
            try:
                item: ReviewItem = await get_review_item(session, review_id)
            except ReviewNotFoundError as exc:
                return _error_response(exc, 404)

        return JSONResponse(item.to_api_dict())


routes = [
    Route("/v1/reviews", create_review, methods=["POST"]),
    Route("/v1/reviews", list_reviews, methods=["GET"]),
    Route("/v1/reviews/{review_id}", get_review, methods=["GET"]),
]


def create_app(*, engine: AsyncEngine | None = None, settings: Settings | None = None) -> Starlette:
    """Build the app with a fresh engine/session factory in app.state, so
    tests can inject an isolated (e.g. in-memory SQLite) engine instead of
    the real configured database."""

    resolved_engine = engine or create_engine(settings=settings)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        await init_models(resolved_engine)
        yield

    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.engine = resolved_engine
    app.state.session_factory = session_factory(resolved_engine)
    return app


app = create_app()
