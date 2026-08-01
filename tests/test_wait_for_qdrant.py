from __future__ import annotations

import pytest

from scripts import wait_for_qdrant


def test_cloud_endpoint_uses_authenticated_qdrant_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def cloud_ready(url: str, api_key: str | None) -> bool:
        calls.append((url, api_key))
        return True

    monkeypatch.setattr(wait_for_qdrant, "qdrant_cloud_ready", cloud_ready)
    monkeypatch.setattr(
        wait_for_qdrant,
        "qdrant_rest_ready",
        lambda _url: pytest.fail("cloud readiness must not use unauthenticated REST"),
    )

    wait_for_qdrant.wait_for_qdrant(
        "https://cluster.example.qdrant.io",
        grpc_port=6334,
        timeout_seconds=1,
        api_key="secret",
    )

    assert calls == [("https://cluster.example.qdrant.io", "secret")]


def test_local_endpoint_keeps_rest_and_grpc_health_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wait_for_qdrant, "qdrant_rest_ready", lambda _url: True)
    monkeypatch.setattr(
        wait_for_qdrant,
        "qdrant_grpc_ready",
        lambda _url, _port: True,
    )
    monkeypatch.setattr(
        wait_for_qdrant,
        "qdrant_cloud_ready",
        lambda _url, _api_key: pytest.fail("local readiness must not use cloud clients"),
    )

    wait_for_qdrant.wait_for_qdrant(
        "http://localhost:6333",
        grpc_port=6334,
        timeout_seconds=1,
    )
