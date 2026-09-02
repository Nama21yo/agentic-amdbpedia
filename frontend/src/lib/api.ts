// Typed client for the two backends this frontend calls. Every endpoint here
// is documented with its contract; each function is labeled PLANNED or
// EXISTING in its own doc comment. Each function fails closed with
// BackendUnavailableError rather than throwing an opaque network error, so
// callers can render an honest "not connected yet" state instead of a
// crash.
import { AGENTIC_DBPEDIA_URL, CROSS_LINGUAL_URL } from './config';
import type {
	AgentStep,
	CoverageStats,
	MappingCandidate,
	PredictedMapping,
	ReviewItem
} from './types';

export class BackendUnavailableError extends Error {}

async function safeFetch(input: string, init?: RequestInit): Promise<Response> {
	try {
		return await fetch(input, init);
	} catch (cause) {
		throw new BackendUnavailableError(`Could not reach ${input}`, { cause });
	}
}

type PreviewEvent = AgentStep | { node: 'result'; mappings: PredictedMapping[] };

/**
 * EXISTING: POST {CROSS_LINGUAL_URL}/v1/preview — text/event-stream
 * (mcp_server/http_app.py, refs implementation.md 16.3). Streams the
 * mapping pipeline's (16.2) progress for a pasted infobox. Each SSE
 * `data:` line is one JSON-encoded step; the final event carries
 * `node: "result"` with the predicted mappings. `targetClass` defaults to
 * `"Thing"` server-side when omitted.
 *
 * Was originally pointed at agentic-dbpedia (`AGENTIC_DBPEDIA_URL`) — that
 * predates this session settling on cross-lingual owning the full
 * pipeline (agentic-dbpedia is DEF-extraction-only); repointed here for
 * the same reason 14.1 already repointed `listReviewQueue`/`decideReview`.
 */
export async function* previewMapping(
	infobox: string,
	targetClass?: string
): AsyncGenerator<PreviewEvent> {
	const res = await safeFetch(`${CROSS_LINGUAL_URL}/v1/preview`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ infobox, target_class: targetClass })
	});
	if (!res.ok || !res.body) {
		throw new BackendUnavailableError(`preview failed: ${res.status}`);
	}

	const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
	let buffer = '';
	while (true) {
		const { value, done } = await reader.read();
		if (done) break;
		buffer += value;
		const events = buffer.split('\n\n');
		buffer = events.pop() ?? '';
		for (const chunk of events) {
			const dataLine = chunk.split('\n').find((line) => line.startsWith('data:'));
			if (!dataLine) continue;
			yield JSON.parse(dataLine.slice('data:'.length).trim()) as PreviewEvent;
		}
	}
}

/**
 * EXISTING: POST {CROSS_LINGUAL_URL}/v1/find-semantic-match
 * (mcp_server/http_app.py, refs implementation.md 16.3) — the same
 * find_semantic_match tool already exposed over MCP, mirrored over HTTP so
 * this frontend (and agentic-dbpedia's pipeline) can call it directly.
 */
export async function findSemanticMatch(
	amharicProperty: string,
	targetClass?: string
): Promise<{ status: 'ok' | 'no_match'; matches: MappingCandidate[] }> {
	const res = await safeFetch(`${CROSS_LINGUAL_URL}/v1/find-semantic-match`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ amharic_property: amharicProperty, target_class: targetClass })
	});
	if (!res.ok) throw new BackendUnavailableError(`find_semantic_match failed: ${res.status}`);
	return res.json();
}

/**
 * EXISTING: GET {CROSS_LINGUAL_URL}/v1/reviews — the Postgres-backed queue
 * (mcp_server/http_app.py, refs implementation.md 14.1). Run it with
 * `uvicorn mcp_server.http_app:app` alongside the MCP stdio server.
 */
export async function listReviewQueue(): Promise<ReviewItem[]> {
	const res = await safeFetch(`${CROSS_LINGUAL_URL}/v1/reviews`);
	if (!res.ok) throw new BackendUnavailableError(`reviews failed: ${res.status}`);
	return res.json();
}

/**
 * EXISTING: POST {CROSS_LINGUAL_URL}/v1/reviews/{id}/decision
 * (mcp_server/http_app.py, refs implementation.md 14.2/14.3).
 *
 * `correctedMappings`, when given, replaces the review item's predicted
 * mappings with a reviewer-edited version before logging the decision as
 * training data. `publish: true` (only meaningful alongside
 * `decision: "approved"`) is this call's explicit consent to actually
 * write the mapping to the live MediaWiki — a real, outward-facing,
 * hard-to-reverse action — and flips status to "published" on success
 * instead of "approved"; leave it `false`/omitted to just record the
 * review decision without publishing anything live.
 */
export async function decideReview(
	id: string,
	decision: 'approved' | 'rejected',
	options?: { reason?: string; correctedMappings?: PredictedMapping[]; publish?: boolean }
): Promise<ReviewItem> {
	const res = await safeFetch(`${CROSS_LINGUAL_URL}/v1/reviews/${id}/decision`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({
			decision,
			reason: options?.reason,
			corrected_mappings: options?.correctedMappings,
			publish: options?.publish
		})
	});
	if (!res.ok) throw new BackendUnavailableError(`decision failed: ${res.status}`);
	return res.json();
}

/** EXISTING on the backend already (agentic-dbpedia's statistics service). */
export async function getCoverageStats(): Promise<CoverageStats> {
	const res = await safeFetch(`${AGENTIC_DBPEDIA_URL}/api/statistics/summary`);
	if (!res.ok) throw new BackendUnavailableError(`statistics failed: ${res.status}`);
	return res.json();
}
