from __future__ import annotations

import pytest

from rag.retrieval import NoMatchFound, build_index, search

pytestmark = pytest.mark.integration


def test_low_confidence_returns_no_match() -> None:
    index = build_index()

    results = search(
        "random Latin lorem ipsum out of ontology",
        index=index,
        confidence_threshold=1.0,
    )

    assert results == [NoMatchFound(query="random Latin lorem ipsum out of ontology")]
