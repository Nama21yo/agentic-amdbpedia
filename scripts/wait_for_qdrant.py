"""Wait for Qdrant REST and gRPC endpoints to become ready."""

from __future__ import annotations

import argparse
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


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


def wait_for_qdrant(url: str, grpc_port: int, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if qdrant_rest_ready(url) and qdrant_grpc_ready(url, grpc_port):
            return
        time.sleep(1)

    raise TimeoutError(
        f"Qdrant did not become ready at {url} and gRPC port {grpc_port} "
        f"within {timeout_seconds:.0f}s"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=Path(__file__).name)
    parser.add_argument("--url", default="http://localhost:6333")
    parser.add_argument("--grpc-port", type=int, default=6334)
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args(argv)

    try:
        wait_for_qdrant(args.url, args.grpc_port, args.timeout)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Qdrant is ready at {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
