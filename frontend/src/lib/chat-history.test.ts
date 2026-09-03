import { describe, expect, it, beforeEach, afterEach } from 'vitest';
import { tick } from 'svelte';
import { cleanup, render, screen } from '@testing-library/svelte';
import AppSidebar from './components/AppSidebar.svelte';
import {
	sessions,
	active,
	ensureActiveSession,
	touchSession,
	type PipelineTurn
} from './chat.svelte';

describe('chat history reactivity (reproducing the reported sidebar bug)', () => {
	beforeEach(() => {
		// Each test gets a clean slate -- sessions/active are module-level
		// singletons shared across the whole test file otherwise.
		sessions.length = 0;
		active.id = null;
		localStorage.clear();
	});

	afterEach(() => {
		cleanup();
	});

	it('shows a newly created session in the rendered sidebar without a reload', async () => {
		render(AppSidebar, { props: { open: true } });

		// Before any chat: no recency group ("Today"/etc.) and no search
		// box -- both are gated on sessions.length > 0.
		expect(screen.queryByText('Today')).toBeNull();
		expect(screen.queryByPlaceholderText('Search chats…')).toBeNull();

		// Reproduce exactly what +page.svelte's submit() does for the first
		// message of a conversation.
		const session = ensureActiveSession();
		const turn: PipelineTurn = {
			id: 'turn-1',
			kind: 'pipeline',
			input: '{{Infobox bridge\n| ርዝመት = 1,700 ሜትር\n}}',
			steps: [],
			mappings: null,
			running: true
		};
		session.turns.push(turn);
		touchSession(session.id);
		await tick();

		// The sidebar should now group this session under "Today" (it was
		// just touched) with its derived title, with no remount / no reload.
		expect(screen.getByText('Today')).toBeInTheDocument();
		expect(screen.getByText(/Infobox bridge/)).toBeInTheDocument();
	});

	it('updates the session title once the turn completes, live', async () => {
		render(AppSidebar, { props: { open: true } });

		const session = ensureActiveSession();
		const turn: PipelineTurn = {
			id: 'turn-1',
			kind: 'pipeline',
			input: 'አይካኦ_ኮድ',
			steps: [],
			mappings: null,
			running: true
		};
		session.turns.push(turn);
		touchSession(session.id);
		await tick();

		expect(screen.getByText('አይካኦ_ኮድ')).toBeInTheDocument();

		turn.running = false;
		turn.mappings = [
			{ templateProperty: 'አይካኦ_ኮድ', ontologyProperty: 'icaoLocationIdentifier', confidence: 1 }
		];
		touchSession(session.id);
		await tick();

		// Still there (title doesn't change once set), and only one entry.
		expect(screen.getAllByText('አይካኦ_ኮድ')).toHaveLength(1);
	});
});
