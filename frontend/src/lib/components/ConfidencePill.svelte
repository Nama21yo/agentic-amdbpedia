<script lang="ts">
	let { confidence }: { confidence: number } = $props();

	const tier = $derived(confidence >= 0.75 ? 'high' : confidence >= 0.4 ? 'medium' : 'low');

	const styles = {
		high: 'border-emerald-800 bg-emerald-950/50 text-emerald-300',
		medium: 'border-amber-800 bg-amber-950/50 text-amber-300',
		low: 'border-red-800 bg-red-950/50 text-red-300'
	} as const;
</script>

<span
	class={[
		'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium tabular-nums',
		styles[tier]
	]}
	title="Retrieval confidence"
>
	{Math.round(confidence * 100)}%
</span>
