// Chat history, persisted client-side. There's no backend "conversations"
// table to back this with (review_items is a different concept -- a
// mapping submitted for approval, not a chat turn), so this is deliberately
// localStorage-only: per-browser, not shared across devices or reviewers.
// Good enough for "the thread I was just looking at is still there after I
// navigate away and back" without inventing backend storage this app
// doesn't otherwise need.
import { browser } from '$app/environment';
import type { AgentStep, MappingCandidate, PredictedMapping } from './types';

export interface PipelineTurn {
	id: string;
	kind: 'pipeline';
	input: string;
	targetClass?: string;
	steps: AgentStep[];
	mappings: PredictedMapping[] | null;
	mappingWikitext?: string;
	xmlRules?: string;
	running: boolean;
	error?: string;
}

export interface AnswerTurn {
	id: string;
	kind: 'answer';
	input: string;
	targetClass?: string;
	matches: MappingCandidate[] | null;
	noMatch: boolean;
	running: boolean;
	error?: string;
}

export type Turn = PipelineTurn | AnswerTurn;

export interface ChatSession {
	id: string;
	title: string;
	turns: Turn[];
	updatedAt: number;
}

const STORAGE_KEY = 'amdbpedia:chat-sessions:v1';
const MAX_SESSIONS = 50;

function loadSessions(): ChatSession[] {
	if (!browser) return [];
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return [];
		const parsed = JSON.parse(raw);
		return Array.isArray(parsed) ? parsed : [];
	} catch (err) {
		console.error('Failed to load chat history from localStorage:', err);
		return [];
	}
}

export const sessions = $state<ChatSession[]>(loadSessions());
export const active = $state<{ id: string | null }>({ id: sessions[0]?.id ?? null });

function persist() {
	if (!browser) return;
	try {
		localStorage.setItem(STORAGE_KEY, JSON.stringify($state.snapshot(sessions)));
	} catch (err) {
		// Private browsing / storage quota / disabled site data -- a chat
		// still works for the session, it just won't survive a reload.
		console.error('Failed to persist chat history to localStorage:', err);
	}
}

export function deriveTitle(text: string): string {
	const oneLine = text.replace(/\s+/g, ' ').trim();
	if (!oneLine) return 'New chat';
	return oneLine.length > 48 ? oneLine.slice(0, 48) + '…' : oneLine;
}

export function newSession(): string {
	const id = crypto.randomUUID();
	sessions.unshift({ id, title: 'New chat', turns: [], updatedAt: Date.now() });
	if (sessions.length > MAX_SESSIONS) sessions.length = MAX_SESSIONS;
	active.id = id;
	persist();
	return id;
}

export function ensureActiveSession(): ChatSession {
	const existing = sessions.find((s) => s.id === active.id);
	if (existing) return existing;
	newSession();
	return sessions[0];
}

export function currentSession(): ChatSession | undefined {
	return sessions.find((s) => s.id === active.id);
}

export function selectSession(id: string) {
	active.id = id;
}

/** Used by the sidebar's "New chat" button: only actually creates a new
 * (empty) session if the current one already has content, so repeated
 * clicks don't pile up empty "New chat" placeholders in the history. */
export function startNewChat(): string {
	const existing = currentSession();
	if (!existing || existing.turns.length > 0) return newSession();
	return existing.id;
}

export function touchSession(id: string) {
	const index = sessions.findIndex((s) => s.id === id);
	if (index === -1) return;
	const session = sessions[index];
	session.updatedAt = Date.now();
	if (session.title === 'New chat' && session.turns.length > 0) {
		session.title = deriveTitle(session.turns[0].input);
	}
	// Most-recently-touched floats to the top, matching every chat product's
	// history ordering.
	if (index > 0) {
		sessions.splice(index, 1);
		sessions.unshift(session);
	}
	persist();
}

export function deleteSession(id: string) {
	const index = sessions.findIndex((s) => s.id === id);
	if (index === -1) return;
	sessions.splice(index, 1);
	if (active.id === id) active.id = sessions[0]?.id ?? null;
	persist();
}
