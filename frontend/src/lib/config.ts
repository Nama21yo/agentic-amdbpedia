// Backend base URLs the frontend talks to. Both are separate services:
//
// - agentic-dbpedia owns DEF-based extraction and coverage stats only.
// - cross-lingual owns everything else: the mapping-agent pipeline
//   (predict/format/validate), the hybrid-search verifier/assistant, and
//   the Postgres-backed review queue (refs implementation.md Phase 2 —
//   this split moved after this frontend was first scaffolded; see
//   README.md's endpoint table).
//
// No auth headers are sent from this client yet — deferred deliberately for
// this internal-tool MVP, see frontend/README.md.
import { env } from '$env/dynamic/public';

export const AGENTIC_DBPEDIA_URL = env.PUBLIC_AGENTIC_DBPEDIA_URL ?? 'http://localhost:8000';
export const CROSS_LINGUAL_URL = env.PUBLIC_CROSS_LINGUAL_URL ?? 'http://localhost:8001';
