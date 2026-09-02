"""SQLAlchemy models for the review queue (refs implementation.md 14.1).

Replaces the `InMemoryMappingAgentJobStore` concept from `agentic-dbpedia`
with a real, persistent queue. Contributor and maintainer are the same role
for now (per the session's own simplification) — there's no separate
approval permission here, just the `status` state transition itself.

Column types are chosen to work identically on SQLite (fast, dependency
-free unit tests) and Postgres (the real docker-compose service) — no
Postgres-specific types (no native `ENUM`, no `UUID`), so the same model
definitions and migrations-by-`create_all()` work on both without branching.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Every valid state a review item can be in, and the transitions allowed
# between them. Kept as a plain tuple (not a DB-native enum) so it stays
# portable across SQLite and Postgres, and so adding a state later is a
# one-line change, not a migration.
REVIEW_STATUSES = ("pending_review", "approved", "rejected", "published")


class Base(DeclarativeBase):
    pass


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class ReviewItem(Base):
    """One predicted mapping awaiting (or having received) human review.

    `mappings` mirrors `frontend/src/lib/types.ts::PredictedMapping[]`
    exactly: a JSON list of `{templateProperty, ontologyProperty,
    confidence}` objects — the HTTP layer (`mcp_server/http_app.py`)
    serializes this row to JSON matching
    `frontend/src/lib/types.ts::ReviewItem` field-for-field (camelCase),
    with `run_id` kept DB-internal only (it's not part of that frontend
    type, and exists here purely to link back to 13.1's training log).
    """

    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_new_id)
    run_id: Mapped[str] = mapped_column(String, nullable=False)
    template_name: Mapped[str] = mapped_column(String, nullable=False)
    domain_class: Mapped[str] = mapped_column(String, nullable=False)
    mappings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending_review")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    def to_api_dict(self) -> dict[str, Any]:
        """Serialize to exactly `frontend/src/lib/types.ts::ReviewItem`'s shape."""

        return {
            "id": self.id,
            "templateName": self.template_name,
            "domainClass": self.domain_class,
            "status": self.status,
            "submittedAt": self.submitted_at.isoformat(),
            "mappings": self.mappings,
        }
