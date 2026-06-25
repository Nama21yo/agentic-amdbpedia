from __future__ import annotations

import socket
import urllib.parse
import urllib.request

import pytest

pytestmark = pytest.mark.integration

QDRANT_URL = "http://localhost:6333"
QDRANT_GRPC_PORT = 6334


def test_qdrant_rest_health_endpoint_responds() -> None:
    with urllib.request.urlopen(f"{QDRANT_URL}/healthz", timeout=3) as response:
        assert response.status == 200


def test_qdrant_collections_endpoint_responds() -> None:
    with urllib.request.urlopen(f"{QDRANT_URL}/collections", timeout=3) as response:
        assert response.status == 200


def test_qdrant_grpc_port_is_open() -> None:
    host = urllib.parse.urlparse(QDRANT_URL).hostname
    assert host is not None
    with socket.create_connection((host, QDRANT_GRPC_PORT), timeout=3):
        pass
