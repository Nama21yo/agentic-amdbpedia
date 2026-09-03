import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import ChatPage from '../routes/+page.svelte';
import { sessions, active } from './chat.svelte';
import * as api from './api';
import type { AgentStep, MappingSyntax, PredictedMapping, ReviewItem } from './types';

const REVIEW_ITEM_ID = 'review-123';

// Simulate exactly what previewMapping() yields: an async generator of step
// events followed by a final result event -- the real backend contract, not
// a mock of unrelated shape.
async function* fakeStream(): AsyncGenerator<
	| AgentStep
	| ({ node: 'result'; mappings: PredictedMapping[]; reviewItemId: string | null } & MappingSyntax)
> {
	yield { node: 'extract_infobox_fields', status: 'done', detail: 'Extracting' };
	yield { node: 'predict_properties', status: 'done', detail: 'Predicting' };
	yield {
		node: 'result',
		mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }],
		mappingWikitext:
			'{{TemplateMapping\n | mapToClass = Bridge\n | mappings =\n  {{PropertyMapping | templateProperty = ርዝመት | ontologyProperty = length }}\n}}',
		xmlRules: '<TemplateMapping mapToClass="dbo:Bridge">...</TemplateMapping>',
		reviewItemId: REVIEW_ITEM_ID
	};
}

async function submitBridgeInfobox() {
	render(ChatPage);

	const textarea = screen.getByPlaceholderText(/Paste an infobox/i) as HTMLTextAreaElement;
	textarea.value = '{{Infobox bridge\n| ርዝመት = 1,700 ሜትር\n}}';
	textarea.dispatchEvent(new Event('input', { bubbles: true }));

	await waitFor(() => {
		expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled();
	});
	screen.getByRole('button', { name: /send/i }).click();
}

describe('mutating a turn after push (reproducing "chat doesn\'t show the reply")', () => {
	beforeEach(() => {
		sessions.length = 0;
		active.id = null;
	});

	afterEach(() => {
		cleanup();
		vi.restoreAllMocks();
	});

	it('renders the step tracker and result table as the SSE stream progresses', async () => {
		vi.spyOn(api, 'previewMapping').mockReturnValue(fakeStream());

		await submitBridgeInfobox();

		// This is the actual reported symptom: does the assistant's reply --
		// the step rows and the final result table -- ever show up in the
		// DOM once the (mocked but real-shaped) SSE stream finishes?
		await waitFor(() => {
			expect(screen.getByText('Extract infobox fields')).toBeInTheDocument();
		});
		await waitFor(() => {
			expect(screen.getByText('length')).toBeInTheDocument();
		});

		// The backend always computes real mapping wikitext AND XML
		// alongside `mappings` (mcp_server/pipeline.py's
		// format_mapping_syntax node) -- confirmed live that neither ever
		// reached the UI at all before this was wired up (SSE event ->
		// PipelineTurn -> template both dropped it).
		await waitFor(() => {
			expect(screen.getByText('View mapping wikitext')).toBeInTheDocument();
			expect(screen.getByText(/mapToClass = Bridge/)).toBeInTheDocument();
			expect(screen.getByText('View mapping XML')).toBeInTheDocument();
			expect(screen.getByText(/<TemplateMapping/)).toBeInTheDocument();
		});
	});

	it('approves the review item created by this turn, without leaving the chat', async () => {
		vi.spyOn(api, 'previewMapping').mockReturnValue(fakeStream());
		const decideReviewSpy = vi.spyOn(api, 'decideReview').mockResolvedValue({
			id: REVIEW_ITEM_ID,
			templateName: 'Infobox bridge',
			domainClass: 'Bridge',
			status: 'approved',
			submittedAt: '2026-01-01T00:00:00Z',
			mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }]
		} satisfies ReviewItem);

		await submitBridgeInfobox();

		const approveButton = await screen.findByRole('button', { name: /approve/i });
		approveButton.click();

		await waitFor(() => {
			expect(decideReviewSpy).toHaveBeenCalledWith(REVIEW_ITEM_ID, 'approved');
		});
		// The approve/reject buttons are replaced by a status badge once the
		// decision lands -- decided in-chat, not merely submitted-and-forgotten.
		await waitFor(() => {
			expect(screen.getByText('Approved')).toBeInTheDocument();
			expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument();
			expect(screen.queryByRole('button', { name: /reject/i })).not.toBeInTheDocument();
		});
	});
});
