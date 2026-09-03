import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import ChatPage from '../routes/+page.svelte';
import { sessions, active } from './chat.svelte';
import * as api from './api';
import type { AgentStep, MappingSyntax, PredictedMapping } from './types';

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
		// Simulate exactly what previewMapping() yields: an async generator
		// of step events followed by a final result event -- the real
		// backend contract, not a mock of unrelated shape.
		async function* fakeStream(): AsyncGenerator<
			AgentStep | ({ node: 'result'; mappings: PredictedMapping[] } & MappingSyntax)
		> {
			yield { node: 'extract_infobox_fields', status: 'done', detail: 'Extracting' };
			yield { node: 'predict_properties', status: 'done', detail: 'Predicting' };
			yield {
				node: 'result',
				mappings: [{ templateProperty: 'ርዝመት', ontologyProperty: 'length', confidence: 0.75 }],
				mappingWikitext:
					'{{TemplateMapping\n | mapToClass = Bridge\n | mappings =\n  {{PropertyMapping | templateProperty = ርዝመት | ontologyProperty = length }}\n}}',
				xmlRules: '<TemplateMapping mapToClass="dbo:Bridge">...</TemplateMapping>'
			};
		}
		vi.spyOn(api, 'previewMapping').mockReturnValue(fakeStream());

		render(ChatPage);

		const textarea = screen.getByPlaceholderText(/Paste an infobox/i) as HTMLTextAreaElement;
		textarea.value = '{{Infobox bridge\n| ርዝመት = 1,700 ሜትር\n}}';
		textarea.dispatchEvent(new Event('input', { bubbles: true }));

		await waitFor(() => {
			expect(screen.getByRole('button', { name: /send/i })).not.toBeDisabled();
		});
		screen.getByRole('button', { name: /send/i }).click();

		// This is the actual reported symptom: does the assistant's reply --
		// the step rows and the final result table -- ever show up in the
		// DOM once the (mocked but real-shaped) SSE stream finishes?
		await waitFor(() => {
			expect(screen.getByText('Extract infobox fields')).toBeInTheDocument();
		});
		await waitFor(() => {
			expect(screen.getByText('length')).toBeInTheDocument();
		});

		// The backend always computes real mapping wikitext alongside
		// `mappings` (mcp_server/pipeline.py's format_mapping_syntax node) --
		// confirmed live that it never reached the UI at all before this was
		// wired up (SSE event -> PipelineTurn -> template all dropped it).
		await waitFor(() => {
			expect(screen.getByText('View mapping wikitext')).toBeInTheDocument();
			expect(screen.getByText(/mapToClass = Bridge/)).toBeInTheDocument();
		});
	});
});
