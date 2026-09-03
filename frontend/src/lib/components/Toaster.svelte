<script lang="ts">
	import { dismissToast, toasts } from '$lib/toast.svelte';

	const styles = {
		success: 'border-emerald-800 bg-emerald-950/90 text-emerald-300',
		error: 'border-red-800 bg-red-950/90 text-red-300',
		info: 'border-neutral-700 bg-neutral-900/90 text-neutral-200'
	} as const;
</script>

<div class="pointer-events-none fixed inset-x-0 top-4 z-50 flex flex-col items-center gap-2 px-4">
	{#each toasts as toast (toast.id)}
		<div
			class={[
				'pointer-events-auto flex max-w-md items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur',
				styles[toast.kind]
			]}
			role="status"
		>
			<span class="flex-1">{toast.message}</span>
			<button
				type="button"
				class="text-xs text-neutral-500 hover:text-neutral-300"
				onclick={() => dismissToast(toast.id)}
			>
				Dismiss
			</button>
		</div>
	{/each}
</div>
