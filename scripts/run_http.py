"""Start the HTTP server, walking forward to the next port if the preferred
one is already taken.

`just run-http` used to hardcode `--port 8001` directly on the `uvicorn`
invocation, so a stale server process still holding that port (a leftover
terminal, an earlier Claude Code session, ...) made every subsequent
`just run-http` fail outright with "address already in use" instead of
just starting somewhere else -- confirmed live. This probes the preferred
port first and, only if it's genuinely busy, tries the next ones in order
until it finds one free, then starts uvicorn there.

Uses `uvicorn.run("mcp_server.http_app:create_app", factory=True, ...)` --
the string-import + `factory=True` form defers `create_app()` (and the
`Settings()`/`GROQ_API_KEY` construction inside it) to the moment startup
actually runs, the same lazy-construction property the CLI's own
`--factory` flag gives `mcp_server/http_app.py`'s own docstring already
depends on. Do not replace this with an eager `from mcp_server.http_app
import create_app; uvicorn.run(create_app())` -- that reintroduces the
exact import-time-Settings() bug fixed earlier (breaks any environment,
like CI, that doesn't already have a populated `.env`/`GROQ_API_KEY`).
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

# Running as `python scripts/run_http.py` puts this file's own directory
# (scripts/, not the project root) at sys.path[0], so `mcp_server` isn't
# importable by uvicorn.run()'s string-based lookup below without this --
# confirmed live: it fails with "ModuleNotFoundError: No module named
# 'mcp_server'" without it. Same fix already used by
# scripts/refresh_wiki_cache.py and scripts/export_training_examples.py
# for the identical reason.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8001
MAX_PORT_ATTEMPTS = 20


def _is_port_free(host: str, port: int) -> bool:
    """Best-effort check: bind-and-release, matching the standard
    "find a free port" idiom. Inherently a check-then-use race (something
    else could grab the port between this check and uvicorn's own bind) --
    acceptable for local dev tooling, not a guarantee."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
        return True


def find_free_port(host: str, preferred: int, *, max_attempts: int = MAX_PORT_ATTEMPTS) -> int:
    """The preferred port if it's free, otherwise the next free one at
    `preferred + 1`, `preferred + 2`, ... Raises if none of the next
    `max_attempts` ports are free either -- silently scanning forever (or
    picking something wildly far from the preferred port) would be more
    confusing than just telling the caller to free one up."""

    for offset in range(max_attempts):
        candidate = preferred + offset
        if _is_port_free(host, candidate):
            return candidate

    raise SystemExit(
        f"No free port found in {preferred}-{preferred + max_attempts - 1} on {host}. "
        "Stop whatever's holding them, or pass --port to try a different range."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    port = find_free_port(args.host, args.port)
    if port != args.port:
        print(
            f"Port {args.port} is already in use -- starting on {port} instead. "
            f"Update PUBLIC_CROSS_LINGUAL_URL in frontend/.env to match if the "
            f"frontend needs to reach this instance.",
            file=sys.stderr,
        )

    uvicorn.run("mcp_server.http_app:create_app", factory=True, host=args.host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
