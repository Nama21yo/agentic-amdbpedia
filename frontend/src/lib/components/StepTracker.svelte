<script lang="ts">
	import type { AgentStep } from '$lib/types';

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
					<span
						class={[
							'h-2.5 w-2.5 shrink-0 rounded-full',
							step.status === 'error'
								? 'bg-red-600'
								: step.status === 'done'
									? 'bg-emerald-600'
									: 'animate-pulse bg-blue-600'
						]}
					></span>
					{#if !isLast}
						<span class="mt-1 h-6 w-px bg-neutral-800"></span>
					{/if}
				</span>
				<div class="pt-px text-sm">
					<p class="text-neutral-200">
						{stepLabels[step.node] ?? step.node}
						<span class="text-xs text-neutral-500">({step.status})</span>
					</p>
					{#if step.detail}
						<p class="text-xs text-neutral-500">{step.detail}</p>
					{/if}
				</div>
			</li>
		{/each}
		{#if running}
			<li class="flex items-center gap-3 text-xs text-neutral-500">
				<span class="ml-[3px] h-2 w-2 animate-pulse rounded-full bg-blue-600"></span>
				Waiting for the next step…
			</li>
		{/if}
	</ol>
{/if}
