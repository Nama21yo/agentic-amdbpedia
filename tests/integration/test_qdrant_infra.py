from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from config import Settings

pytestmark = pytest.mark.integration


def configured_client(*, prefer_grpc: bool = False) -> QdrantClient:
    settings = Settings()
    return QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        prefer_grpc=prefer_grpc,
        timeout=10,
        check_compatibility=False,
    )


def test_qdrant_rest_health_endpoint_responds() -> None:
    assert configured_client().get_collections() is not None


def test_qdrant_collections_endpoint_responds() -> None:
    assert configured_client().collection_exists("dbpedia_ontology_properties")


def test_qdrant_grpc_port_is_open() -> None:
    assert configured_client(prefer_grpc=True).get_collections() is not None
