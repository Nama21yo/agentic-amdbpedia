// Tiny global toast store (Svelte 5 runes) so every page can surface
// success/error feedback the same way instead of each hand-rolling its own
// inline banner. Auto-dismisses; `Toaster.svelte` (mounted once in
// +layout.svelte) renders whatever's in `toasts`.
export interface Toast {
	id: number;
	kind: 'success' | 'error' | 'info';
	message: string;
}

let nextId = 0;
export const toasts = $state<Toast[]>([]);

export function pushToast(message: string, kind: Toast['kind'] = 'info', durationMs = 5000) {
	const id = nextId++;
	toasts.push({ id, kind, message });
	setTimeout(() => dismissToast(id), durationMs);
	return id;
}

export function dismissToast(id: number) {
	const index = toasts.findIndex((toast) => toast.id === id);
	if (index !== -1) toasts.splice(index, 1);
}
