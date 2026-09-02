<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		open,
		title,
		confirmLabel = 'Confirm',
		danger = false,
		busy = false,
		onconfirm,
		oncancel,
		children
	}: {
		open: boolean;
		title: string;
		confirmLabel?: string;
		danger?: boolean;
		busy?: boolean;
		onconfirm: () => void;
		oncancel: () => void;
		children: Snippet;
	} = $props();
</script>

{#if open}
	<div class="fixed inset-0 z-40 flex items-center justify-center bg-black/70 p-4">
		<div
			class="w-full max-w-lg rounded-xl border border-neutral-800 bg-neutral-900 p-6 shadow-2xl"
			role="alertdialog"
			aria-modal="true"
			aria-labelledby="confirm-dialog-title"
		>
			<h2 id="confirm-dialog-title" class="text-base font-semibold text-neutral-100">
				{title}
			</h2>
			<div class="mt-3 text-sm text-neutral-400">
				{@render children()}
			</div>
			<div class="mt-6 flex justify-end gap-2">
				<button
					type="button"
					class="rounded-lg border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800"
					onclick={oncancel}
					disabled={busy}
				>
					Cancel
				</button>
				<button
					type="button"
					class={[
						'rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50',
						danger ? 'bg-red-700 hover:bg-red-600' : 'bg-emerald-700 hover:bg-emerald-600'
					]}
					onclick={onconfirm}
					disabled={busy}
				>
					{busy ? 'Working…' : confirmLabel}
				</button>
			</div>
		</div>
	</div>
{/if}
