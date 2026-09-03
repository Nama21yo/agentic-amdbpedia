import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';

vi.mock('$app/environment', () => ({
	browser: true,
	dev: true,
	building: false,
	version: 'test'
}));

vi.mock('$env/dynamic/public', () => ({ env: {} }));

// localStorage isn't implemented by jsdom by default in a way that
// survives between imports of the same module in one test file the way a
// real browser's would -- a tiny in-memory polyfill is enough for what
// chat.svelte.ts needs (getItem/setItem/removeItem).
class MemoryStorage {
	private store = new Map<string, string>();
	getItem(key: string) {
		return this.store.has(key) ? this.store.get(key)! : null;
	}
	setItem(key: string, value: string) {
		this.store.set(key, value);
	}
	removeItem(key: string) {
		this.store.delete(key);
	}
	clear() {
		this.store.clear();
	}
}

if (!('localStorage' in globalThis) || !globalThis.localStorage) {
	Object.defineProperty(globalThis, 'localStorage', { value: new MemoryStorage() });
}

// jsdom doesn't implement scrollIntoView at all.
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
	Element.prototype.scrollIntoView = () => {};
}
