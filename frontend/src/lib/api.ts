// Typed client for the cross-lingual HTTP API -- the only backend this
// frontend calls. Every endpoint here is documented with its contract; each
// function is labeled PLANNED or EXISTING in its own doc comment. Each
// function fails closed with BackendUnavailableError rather than throwing an
// opaque network error, so callers can render an honest "not connected yet"
// state instead of a crash.
import { CROSS_LINGUAL_URL } from './config';
import type {
	AgentStep,
	CoverageStats,
	MappingCandidate,
	PredictedMapping,
	ReviewItem
} from './types';

export class BackendUnavailableError extends Error {}

/**
 * The backend understood the request but the decision itself failed
 * server-side — most importantly a publish failure (missing MediaWiki
 * credentials, a rejected edit, ...): `mcp_server/http_app.py::decide_review`
 * returns 502 with `{error_type, message, review}`, where `review` is the
 * item's real resulting state (still "approved", never silently
 * "published"). Callers should apply `review` to their local state rather
 * than treating this like `BackendUnavailableError` — the decision itself
 * (approve/reject) went through even when a requested publish didn't.
 */
export class DecisionFailedError extends Error {
	errorType: string;
	review?: ReviewItem;

	constructor(message: string, errorType: string, review?: ReviewItem) {
		super(message);
		this.errorType = errorType;
		this.review = review;
	}
}

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
 * review decision without publishing anything live. A failed publish
 * rejects with `DecisionFailedError`, not `BackendUnavailableError` — see
 * that class's doc comment.
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
	if (!res.ok) {
		const body = await res.json().catch(() => null);
		if (body && typeof body.message === 'string') {
			throw new DecisionFailedError(body.message, body.error_type ?? 'unknown', body.review);
		}
		throw new BackendUnavailableError(`decision failed: ${res.status}`);
	}
	return res.json();
}

/**
 * EXISTING: GET {CROSS_LINGUAL_URL}/v1/coverage (mcp_server/http_app.py).
 *
 * Was originally pointed at agentic-dbpedia's `/api/statistics/summary` --
 * that endpoint never actually existed there (its real routes are
 * `/api/statistics/latest`/`generate`/`runs`, and even those compute a
 * different thing: raw DEF extraction-output triple counts). Repointed at
 * cross-lingual's own review queue, for the same reason every other
 * endpoint here already lives there: agentic-dbpedia is DEF-extraction
 * -only. See `db/session.py::coverage_stats`'s docstring for exactly what
 * "coverage" means computed this way.
 */
export async function getCoverageStats(): Promise<CoverageStats> {
	const res = await safeFetch(`${CROSS_LINGUAL_URL}/v1/coverage`);
	if (!res.ok) throw new BackendUnavailableError(`statistics failed: ${res.status}`);
	return res.json();
}
