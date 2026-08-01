"""Wait for Qdrant REST and gRPC endpoints to become ready."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


def qdrant_rest_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/healthz", timeout=2) as response:
            status: object = getattr(response, "status", 0)
            return status == 200
    except (OSError, urllib.error.URLError):
        return False


def qdrant_grpc_ready(url: str, grpc_port: int) -> bool:
    host = urllib.parse.urlparse(url).hostname or "localhost"
    try:
        with socket.create_connection((host, grpc_port), timeout=2):
            return True
    except OSError:
        return False


def qdrant_cloud_ready(url: str, api_key: str | None) -> bool:
    try:
        from qdrant_client import QdrantClient

        rest_client = QdrantClient(
            url=url,
            api_key=api_key,
            timeout=5,
            check_compatibility=False,
        )
        grpc_client = QdrantClient(
            url=url,
            api_key=api_key,
            prefer_grpc=True,
            timeout=5,
            check_compatibility=False,
        )
        rest_client.get_collections()
        grpc_client.get_collections()
        return True
    except Exception:
        return False


def wait_for_qdrant(
    url: str,
    grpc_port: int,
    timeout_seconds: float,
    api_key: str | None = None,
) -> None:
    hostname = urllib.parse.urlparse(url).hostname or "localhost"
    cloud_endpoint = hostname not in {"localhost", "127.0.0.1", "::1"}
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if cloud_endpoint and qdrant_cloud_ready(url, api_key):
            return
        if not cloud_endpoint and qdrant_rest_ready(url) and qdrant_grpc_ready(url, grpc_port):
            return
        time.sleep(1)

    raise TimeoutError(
        f"Qdrant did not become ready at {url} and gRPC port {grpc_port} "
        f"within {timeout_seconds:.0f}s"
    )


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description=Path(__file__).name)
    parser.add_argument("--url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    parser.add_argument("--api-key", default=os.environ.get("QDRANT_API_KEY"))
    parser.add_argument("--grpc-port", type=int, default=6334)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)

    try:
        wait_for_qdrant(args.url, args.grpc_port, args.timeout, args.api_key)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Qdrant is ready at {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
