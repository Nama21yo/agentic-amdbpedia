// Backend base URLs the frontend talks to. Both are separate services:
//
// - agentic-dbpedia owns the mapping-agent pipeline (predict/format/validate)
//   and, eventually, the Postgres-backed review queue and coverage stats.
// - cross-lingual owns the hybrid-search verifier/assistant.
//
// No auth headers are sent from this client yet — deferred deliberately for
// this internal-tool MVP, see frontend/README.md.
import { env } from '$env/dynamic/public';

export const AGENTIC_DBPEDIA_URL = env.PUBLIC_AGENTIC_DBPEDIA_URL ?? 'http://localhost:8000';
export const CROSS_LINGUAL_URL = env.PUBLIC_CROSS_LINGUAL_URL ?? 'http://localhost:8001';
