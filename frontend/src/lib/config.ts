// Base URL for the cross-lingual HTTP API this frontend talks to --
// mcp_server/http_app.py, run with `uvicorn mcp_server.http_app:app`. This
// is the only backend the frontend calls: agentic-dbpedia is
// DEF-extraction-only and, as of the coverage endpoint's move into
// cross-lingual (db/session.py::coverage_stats), this frontend has no
// remaining dependency on it at all.
//
// No auth headers are sent from this client yet — deferred deliberately for
// this internal-tool MVP, see frontend/README.md.
import { env } from '$env/dynamic/public';

export const CROSS_LINGUAL_URL = env.PUBLIC_CROSS_LINGUAL_URL ?? 'http://localhost:8001';
