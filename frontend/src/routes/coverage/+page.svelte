<script lang="ts">
	import { BackendUnavailableError, getCoverageStats } from '$lib/api';
	import type { CoverageStats } from '$lib/types';

	let stats = $state<CoverageStats | null>(null);
	let error = $state<string | null>(null);

	async function load() {
		try {
			stats = await getCoverageStats();
		} catch (err) {
			error =
				err instanceof BackendUnavailableError
					? 'agentic-dbpedia is not reachable yet — this populates once /api/statistics/summary is running.'
					: 'Unexpected error while loading coverage stats.';
		}
	}

	load();
</script>

<h1 class="mb-1 text-xl font-semibold">Extraction Coverage</h1>
<p class="mb-6 text-sm text-neutral-400">
	How much of Amharic Wikipedia's infobox data has a validated DBpedia mapping.
</p>

{#if error}
	<p class="rounded border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm text-amber-300">
		{error}
	</p>
{:else if !stats}
	<p class="text-neutral-400">Loading…</p>
{:else}
	<dl class="grid grid-cols-3 gap-4">
		<div class="rounded border border-neutral-800 p-4">
			<dt class="text-sm text-neutral-400">Templates</dt>
			<dd class="text-2xl font-semibold">{stats.totalTemplates}</dd>
		</div>
		<div class="rounded border border-neutral-800 p-4">
			<dt class="text-sm text-neutral-400">Mapped</dt>
			<dd class="text-2xl font-semibold">{stats.mappedTemplates}</dd>
		</div>
		<div class="rounded border border-neutral-800 p-4">
			<dt class="text-sm text-neutral-400">Coverage</dt>
			<dd class="text-2xl font-semibold">{stats.coveragePercent.toFixed(1)}%</dd>
		</div>
	</dl>
{/if}
