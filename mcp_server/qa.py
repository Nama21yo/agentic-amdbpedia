"""Load DEF output into Tentris and verify a triple via SPARQL (refs 15.1).

Runs `dicegroup/tentris_server` (a tensor-based triple store — hypertrie
data structure, worst-case-optimal joins) as a throwaway Docker container
per verification call: loads the given `.nt` file at container startup
(`tentris_server -f <file>`), waits for the HTTP endpoint to come up, runs
one query, then stops the container.

Deliberately not an `ASK` query, despite the milestone's original wording:
the actually-available `dicegroup/tentris_server` image (both `1.1.3` and
`latest`/`1.0.7`) reliably segfaults (SIGSEGV, verified directly, twice, on
two different tags) on any `ASK` query, while `SELECT ... LIMIT 1` against
the exact same data and server is completely stable and returns the
standard SPARQL JSON results format. `SELECT ... LIMIT 1` with a fully
-ground triple pattern (no variables) is exactly equivalent to `ASK` for
this module's purpose — a non-empty `bindings` list means the triple
exists — so this substitution costs nothing but the ability to say
literally "runs an ASK query", while avoiding a reproducible crash in the
one Tentris build this module can actually run against.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Protocol

from errors import ClientSafeError
from logging_config import log_event

LOGGER = logging.getLogger("dbpedia_mapping_assistant.qa")

DEFAULT_IMAGE = "dicegroup/tentris_server:latest"
DEFAULT_CONTAINER_PORT = 9080
DEFAULT_STARTUP_TIMEOUT = 30.0
DEFAULT_QUERY_TIMEOUT = 10.0


class QAError(ClientSafeError):
    """Raised when a Tentris-backed verification could not be completed."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_type="qa_unavailable")


class TentrisProcess(Protocol):
    """A running (or about to be running) Tentris instance, addressable at
    `base_url`. `TentrisContainer` is the real, Docker-backed
    implementation; tests inject a fake that skips Docker entirely."""

    base_url: str

    def __enter__(self) -> TentrisProcess: ...
    def __exit__(self, *exc_info: object) -> None: ...


class TentrisContainer:
    """The real implementation: a throwaway `docker run` per verification.

    Never assumes a long-running `tentris` docker-compose service is
    already up — this starts and stops its own container each time,
    matching the milestone's own "starts/reuses tentris_server" wording.
    """

    def __init__(
        self,
        nt_file_path: Path,
        *,
        image: str = DEFAULT_IMAGE,
        host_port: int = 0,
        startup_timeout: float = DEFAULT_STARTUP_TIMEOUT,
    ) -> None:
        self.nt_file_path = nt_file_path
        self.image = image
        self.host_port = host_port
        self.startup_timeout = startup_timeout
        self._container_id: str | None = None
        self.base_url = ""

    def __enter__(self) -> TentrisContainer:
        nt_dir = self.nt_file_path.resolve().parent
        nt_filename = self.nt_file_path.name
        port_mapping = (
            f"{self.host_port}:{DEFAULT_CONTAINER_PORT}"
            if self.host_port
            else str(DEFAULT_CONTAINER_PORT)
        )
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-p",
                port_mapping,
                "-v",
                f"{nt_dir}:/data:ro",
                self.image,
                "-f",
                f"/data/{nt_filename}",
                "-p",
                str(DEFAULT_CONTAINER_PORT),
                "--logfile=false",
            ],
            capture_output=True,
            text=True,
            timeout=self.startup_timeout,
        )
        if result.returncode != 0:
            raise QAError(f"Could not start Tentris container: {result.stderr.strip()}")

        self._container_id = result.stdout.strip()
        published_port = self._resolve_published_port()
        self.base_url = f"http://localhost:{published_port}"
        self._wait_until_ready()
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._container_id:
            subprocess.run(
                ["docker", "stop", self._container_id],
                capture_output=True,
                timeout=self.startup_timeout,
            )

    def _resolve_published_port(self) -> int:
        assert self._container_id is not None
        result = subprocess.run(
            ["docker", "port", self._container_id, str(DEFAULT_CONTAINER_PORT)],
            capture_output=True,
            text=True,
            timeout=self.startup_timeout,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise QAError("Could not resolve the published Tentris container port")
        # docker port prints e.g. "0.0.0.0:54321" -- take the port after the colon.
        return int(result.stdout.strip().splitlines()[0].rsplit(":", 1)[-1])

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + self.startup_timeout
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                query_sparql(self.base_url, "SELECT * WHERE { ?s ?p ?o } LIMIT 1")
                return
            except QAError as exc:
                last_error = exc
                time.sleep(0.5)
        raise QAError(f"Tentris did not become ready in time: {last_error}")


def query_sparql(
    base_url: str, query: str, *, timeout: float = DEFAULT_QUERY_TIMEOUT
) -> dict[str, object]:
    """Run one SPARQL query against a running Tentris instance's HTTP endpoint."""

    url = f"{base_url.rstrip('/')}/sparql?{urllib.parse.urlencode({'query': query})}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 - fixed localhost base_url
            body = response.read()
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise QAError(f"Tentris query failed: {exc.__class__.__name__}") from exc
    try:
        payload: dict[str, object] = json.loads(body)
    except json.JSONDecodeError as exc:
        raise QAError("Tentris returned a non-JSON response") from exc
    return payload


def _sparql_term(value: str) -> str:
    """Format a subject/predicate/object as a SPARQL term: a URI in angle
    brackets if it looks like one, otherwise a quoted string literal."""

    if value.startswith(("http://", "https://")):
        return f"<{value}>"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def verify_extraction(
    nt_file_path: Path,
    subject: str,
    predicate: str,
    expected_object: str,
    *,
    process: TentrisProcess | None = None,
) -> bool:
    """Load `nt_file_path` into Tentris and check whether the given triple
    is actually present in it. Returns the honest boolean either way —
    never raises just because the triple is absent, only on a genuine
    infrastructure failure (Tentris wouldn't start, the query itself
    errored).

    `process` overrides the real Docker-backed TentrisContainer — used by
    tests running against a fake that never touches Docker, and available
    for a caller that wants to reuse an already-running instance across
    multiple checks instead of paying container-startup cost per call.
    """

    query = (
        "SELECT * WHERE { "
        f"{_sparql_term(subject)} {_sparql_term(predicate)} {_sparql_term(expected_object)} "
        "} LIMIT 1"
    )

    owns_process = process is None
    resolved_process = process or TentrisContainer(nt_file_path)
    with resolved_process as running:
        result = query_sparql(running.base_url, query)

    results = result.get("results")
    bindings = results.get("bindings", []) if isinstance(results, dict) else []
    found = len(bindings) > 0

    log_event(
        LOGGER,
        "qa.verify_completed",
        found=found,
        managed_own_container=owns_process,
    )
    return found
