<script lang="ts">
	import type { AgentStep } from '$lib/types';
	import { cn } from '$lib/utils.js';
	import CheckCircle2Icon from '@lucide/svelte/icons/check-circle-2';
	import XCircleIcon from '@lucide/svelte/icons/x-circle';
	import LoaderCircleIcon from '@lucide/svelte/icons/loader-circle';
	import CircleIcon from '@lucide/svelte/icons/circle';

	let { steps, running }: { steps: AgentStep[]; running: boolean } = $props();

	const stepLabels: Record<string, string> = {
		extract_infobox_fields: 'Extract infobox fields',
		predict_properties: 'Predict ontology properties',
		format_mapping_syntax: 'Generate mapping XML',
		persist_review_item: 'Save to review queue'
	};
</script>

{#if steps.length > 0}
	<ol class="mt-6 space-y-3">
		{#each steps as step, i (i)}
			{@const isLast = i === steps.length - 1}
			<li class="flex items-start gap-3">
				<span class="flex flex-col items-center">
					{#if step.status === 'error'}
						<XCircleIcon class="size-5 shrink-0 text-destructive" />
					{:else if step.status === 'done'}
						<CheckCircle2Icon class="size-5 shrink-0 text-success" />
					{:else}
						<LoaderCircleIcon class="size-5 shrink-0 animate-spin text-primary" />
					{/if}
					{#if !isLast}
						<span class="mt-1 h-6 w-px bg-border"></span>
					{/if}
				</span>
				<div class="pt-0.5 text-sm">
					<p class="font-medium text-foreground">
						{stepLabels[step.node] ?? step.node}
					</p>
					{#if step.detail}
						<p class="text-xs text-muted-foreground">{step.detail}</p>
					{/if}
				</div>
			</li>
		{/each}
		{#if running}
			<li class="flex items-center gap-3 text-xs text-muted-foreground">
				<CircleIcon class={cn('size-5 shrink-0 fill-current opacity-40', 'animate-pulse')} />
				Waiting for the next step…
			</li>
		{/if}
	</ol>
{/if}
