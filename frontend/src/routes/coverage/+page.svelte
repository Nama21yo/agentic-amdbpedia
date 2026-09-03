<script lang="ts">
	import { onMount } from 'svelte';
	import { BackendUnavailableError, getCoverageStats } from '$lib/api';
	import type { CoverageStats } from '$lib/types';
	import { Card, CardDescription, CardHeader, CardTitle } from '$lib/components/ui/card/index.js';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';

	let stats = $state<CoverageStats | null>(null);
	let error = $state<string | null>(null);

	async function load() {
		try {
			stats = await getCoverageStats();
		} catch (err) {
			error =
				err instanceof BackendUnavailableError
					? 'cross-lingual is not reachable — check that the HTTP server (just run-http) is running.'
					: 'Unexpected error while loading coverage stats.';
		}
	}

	onMount(load);
</script>

<div class="mb-8">
	<h1 class="text-2xl font-semibold tracking-tight">Extraction Coverage</h1>
	<p class="mt-1 text-sm text-muted-foreground">
		Of the infobox templates this pipeline has processed, how many have a mapping actually published
		to the live wiki.
	</p>
</div>

{#if error}
	<div
		class="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning-foreground"
	>
		<TriangleAlertIcon class="size-4 shrink-0" />
		{error}
	</div>
{:else if !stats}
	<div class="grid grid-cols-3 gap-4">
		<Skeleton class="h-24 w-full" />
		<Skeleton class="h-24 w-full" />
		<Skeleton class="h-24 w-full" />
	</div>
{:else}
	<div class="grid grid-cols-3 gap-4">
		<Card>
			<CardHeader>
				<CardDescription>Templates</CardDescription>
				<CardTitle class="text-2xl tabular-nums">{stats.totalTemplates}</CardTitle>
			</CardHeader>
		</Card>
		<Card>
			<CardHeader>
				<CardDescription>Mapped</CardDescription>
				<CardTitle class="text-2xl tabular-nums">{stats.mappedTemplates}</CardTitle>
			</CardHeader>
		</Card>
		<Card>
			<CardHeader>
				<CardDescription>Coverage</CardDescription>
				<CardTitle class="text-2xl tabular-nums">{stats.coveragePercent.toFixed(1)}%</CardTitle>
			</CardHeader>
		</Card>
	</div>
{/if}
