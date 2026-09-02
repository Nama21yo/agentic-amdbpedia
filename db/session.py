"""Async SQLAlchemy engine/session setup and review-queue CRUD.

No Alembic migrations for this MVP scope — `init_models()` is a plain
`create_all()`, matching the "contributor and maintainer are the same
role, keep it simple" approach already established for this phase (refs
implementation.md 14.1).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import DEFAULT_DATABASE_URL, Settings
from db.models import REVIEW_STATUSES, Base, ReviewItem
from errors import ClientSafeError


class ReviewNotFoundError(ClientSafeError):
    """Raised when a review item id doesn't exist."""

    def __init__(self, review_id: str) -> None:
        super().__init__(message=f"Review item {review_id!r} not found", error_type="not_found")


class InvalidReviewStatusError(ClientSafeError):
    """Raised when a caller requests a status this repo doesn't recognize."""

    def __init__(self, status: str) -> None:
        super().__init__(
            message=f"Unknown review status {status!r}; expected one of {REVIEW_STATUSES}",
            error_type="validation",
        )


def resolve_database_url(settings: Settings | None = None) -> str:
    if settings is not None:
        return settings.database_url
    return DEFAULT_DATABASE_URL


def create_engine(
    database_url: str | None = None, *, settings: Settings | None = None
) -> AsyncEngine:
    return create_async_engine(database_url or resolve_database_url(settings))


def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_models(engine: AsyncEngine) -> None:
    """Create every table that doesn't already exist. Safe to call every
    startup — a no-op once the schema is in place."""

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def create_review_item(
    session: AsyncSession,
    *,
    run_id: str,
    template_name: str,
    domain_class: str,
    mappings: list[dict[str, Any]],
) -> ReviewItem:
    item = ReviewItem(
        run_id=run_id,
        template_name=template_name,
        domain_class=domain_class,
        mappings=mappings,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


async def list_review_items(
    session: AsyncSession, *, status: str | None = None
) -> list[ReviewItem]:
    if status is not None and status not in REVIEW_STATUSES:
        raise InvalidReviewStatusError(status)

    query = select(ReviewItem).order_by(ReviewItem.submitted_at)
    if status is not None:
        query = query.where(ReviewItem.status == status)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_review_item(session: AsyncSession, review_id: str) -> ReviewItem:
    item = await session.get(ReviewItem, review_id)
    if item is None:
        raise ReviewNotFoundError(review_id)
    return item


async def set_review_status(session: AsyncSession, review_id: str, status: str) -> ReviewItem:
    if status not in REVIEW_STATUSES:
        raise InvalidReviewStatusError(status)

    item = await get_review_item(session, review_id)
    item.status = status
    await session.commit()
    await session.refresh(item)
    return item


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """A single-use async session, for Starlette route handlers that want
    `async with session_scope(factory) as session:`-style usage."""

    async with factory() as session:
        yield session
