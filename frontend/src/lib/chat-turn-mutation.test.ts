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
	| ({
			node: 'result';
			mappings: PredictedMapping[];
			reviewItemId: string | null;
			warnings?: string[];
			unmappedFields?: { name: string; value: string }[];
	  } & MappingSyntax)
> {
	yield { node: 'extract_infobox_fields', status: 'done', detail: 'Extracting' };
	yield { node: 'predict_properties', status: 'done', detail: 'Predicting' };
	yield {
		node: 'result',
		mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }],
		mappingWikitext:
			'{{TemplateMapping\n | mapToClass = Bridge\n | mappings =\n  {{PropertyMapping | templateProperty = ርዝመት | ontologyProperty = length }}\n}}',
		xmlRules: '<TemplateMapping mapToClass="dbo:Bridge">...</TemplateMapping>',
		reviewItemId: REVIEW_ITEM_ID,
		warnings: ['Skipped 3 field(s) already present in the published Amharic mappings.'],
		unmappedFields: [{ name: 'ካርታ_መግለጫ', value: 'a caption' }]
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

		// Pipeline notes must be visible too -- without them a result with
		// few mappings because most fields are already published reads as
		// broken rather than correct.
		await waitFor(() => {
			expect(
				screen.getByText(/Skipped 3 field\(s\) already present in the published Amharic mappings/)
			).toBeInTheDocument();
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

	it('publishes an approved mapping live from the chat, behind a confirmation dialog', async () => {
		vi.spyOn(api, 'previewMapping').mockReturnValue(fakeStream());
		const decideReviewSpy = vi
			.spyOn(api, 'decideReview')
			.mockResolvedValueOnce({
				id: REVIEW_ITEM_ID,
				templateName: 'Infobox bridge',
				domainClass: 'Bridge',
				status: 'approved',
				submittedAt: '2026-01-01T00:00:00Z',
				mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }]
			} satisfies ReviewItem)
			.mockResolvedValueOnce({
				id: REVIEW_ITEM_ID,
				templateName: 'Infobox bridge',
				domainClass: 'Bridge',
				status: 'published',
				submittedAt: '2026-01-01T00:00:00Z',
				mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }]
			} satisfies ReviewItem);

		await submitBridgeInfobox();

		(await screen.findByRole('button', { name: /approve/i })).click();
		await waitFor(() => {
			expect(screen.getByRole('button', { name: /publish to live wiki/i })).toBeInTheDocument();
		});

		// Clicking Publish opens a confirmation dialog rather than publishing
		// immediately -- a real, outward-facing MediaWiki write is never a
		// bare one-click action, in chat or on /review alike.
		screen.getByRole('button', { name: /publish to live wiki/i }).click();
		expect(await screen.findByText('Publish this mapping live?')).toBeInTheDocument();
		expect(decideReviewSpy).toHaveBeenCalledTimes(1); // not yet -- only the earlier approve call

		screen.getByRole('button', { name: /^publish$/i }).click();

		await waitFor(() => {
			expect(decideReviewSpy).toHaveBeenCalledWith(REVIEW_ITEM_ID, 'approved', { publish: true });
		});
		await waitFor(() => {
			expect(screen.getByText('Published')).toBeInTheDocument();
			expect(
				screen.queryByRole('button', { name: /publish to live wiki/i })
			).not.toBeInTheDocument();
		});
	});

	it('lets the reviewer assign an unmapped field from the chat and carries it on approve', async () => {
		vi.spyOn(api, 'previewMapping').mockReturnValue(fakeStream());
		const findSpy = vi.spyOn(api, 'findSemanticMatch').mockResolvedValue({
			status: 'ok',
			matches: [{ property: 'depiction', class: 'Thing', score: 0.9 }]
		});
		const decideReviewSpy = vi.spyOn(api, 'decideReview').mockResolvedValue({
			id: REVIEW_ITEM_ID,
			templateName: 'Infobox bridge',
			domainClass: 'Bridge',
			status: 'approved',
			submittedAt: '2026-01-01T00:00:00Z',
			mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }]
		} satisfies ReviewItem);

		await submitBridgeInfobox();

		// The field the pipeline couldn't map is offered with an inline search.
		await screen.findByText(/couldn't be mapped automatically/i);
		screen.getByRole('button', { name: /^search$/i }).click();
		await waitFor(() => expect(findSpy).toHaveBeenCalled());

		// Picking a candidate moves the field into the mappings table, tagged.
		(await screen.findByRole('button', { name: /depiction/i })).click();
		await waitFor(() => {
			expect(screen.getByText('added by you')).toBeInTheDocument();
			expect(screen.queryByText(/couldn't be mapped automatically/i)).not.toBeInTheDocument();
		});

		// Approving sends the hand-assigned row alongside the auto one, via the
		// decision endpoint's existing corrected_mappings path.
		screen.getByRole('button', { name: /approve/i }).click();
		await waitFor(() => {
			expect(decideReviewSpy).toHaveBeenCalledWith(REVIEW_ITEM_ID, 'approved', {
				correctedMappings: [
					{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 },
					{
						templateProperty: 'ካርታ_መግለጫ',
						ontologyProperty: 'depiction',
						confidence: 0.9,
						source: 'manual'
					}
				]
			});
		});
	});
});
