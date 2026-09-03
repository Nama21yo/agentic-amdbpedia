<script lang="ts">
	import { BackendUnavailableError, findSemanticMatch } from '$lib/api';
	import type { MappingCandidate, PredictedMapping } from '$lib/types';
	import ConfidencePill from './ConfidencePill.svelte';

	let {
		mappings = $bindable(),
		original,
		domainClass,
		readonly = false
	}: {
		mappings: PredictedMapping[];
		original: PredictedMapping[];
		domainClass: string;
		readonly?: boolean;
	} = $props();

	function originalFor(templateProperty: string) {
		return original.find((row) => row.templateProperty === templateProperty);
	}

	const removedOriginals = $derived(
		original.filter((row) => !mappings.some((m) => m.templateProperty === row.templateProperty))
	);

	function isEdited(row: PredictedMapping) {
		const source = originalFor(row.templateProperty);
		return source !== undefined && source.ontologyProperty !== row.ontologyProperty;
	}

	function isNew(row: PredictedMapping) {
		return originalFor(row.templateProperty) === undefined;
	}

	function resetRow(index: number) {
		const source = originalFor(mappings[index].templateProperty);
		if (!source) return;
		mappings[index] = { ...source };
	}

	function removeRow(index: number) {
		mappings.splice(index, 1);
	}

	function restoreRow(row: PredictedMapping) {
		mappings.push({ ...row });
	}

	function applyOntologyEdit(index: number, value: string) {
		mappings[index].ontologyProperty = value;
		mappings[index].confidence = 1;
	}

	// Per-row "find a match" panel -- reuses the same retrieval endpoint the
	// Mapping Assistant chat panel uses, so a correction is picked from real
	// grounded candidates instead of freehand-typed and possibly misspelled.
	let suggestOpenIndex = $state<number | null>(null);
	let suggestQuery = $state('');
	let suggestResults = $state<MappingCandidate[] | null>(null);
	let suggestLoading = $state(false);
	let suggestError = $state<string | null>(null);

	function openSuggest(index: number) {
		suggestOpenIndex = suggestOpenIndex === index ? null : index;
		suggestQuery = mappings[index].templateProperty;
		suggestResults = null;
		suggestError = null;
		if (suggestOpenIndex !== null) runSuggest();
	}

	async function runSuggest() {
		if (!suggestQuery.trim()) return;
		suggestLoading = true;
		suggestError = null;
		try {
			const result = await findSemanticMatch(suggestQuery, domainClass || undefined);
			suggestResults = result.status === 'no_match' ? [] : result.matches;
		} catch (err) {
			suggestError =
				err instanceof BackendUnavailableError
					? 'Retrieval backend not reachable right now.'
					: 'Search failed unexpectedly.';
		} finally {
			suggestLoading = false;
		}
	}

	function applySuggestion(index: number, candidate: MappingCandidate) {
		applyOntologyEdit(index, candidate.property);
		suggestOpenIndex = null;
	}

	let newTemplateProperty = $state('');
	let newOntologyProperty = $state('');

	function addRow() {
		if (!newTemplateProperty.trim() || !newOntologyProperty.trim()) return;
		mappings.push({
			templateProperty: newTemplateProperty.trim(),
			ontologyProperty: newOntologyProperty.trim(),
			confidence: 1
		});
		newTemplateProperty = '';
		newOntologyProperty = '';
	}
</script>

<div class="overflow-x-auto rounded-lg border border-neutral-800">
	<table class="w-full text-left text-sm">
		<thead class="bg-neutral-900/80 text-neutral-400">
			<tr>
				<th class="px-3 py-2 font-medium">Template property</th>
				<th class="px-3 py-2 font-medium">Ontology property</th>
				<th class="px-3 py-2 font-medium">Confidence</th>
				{#if !readonly}
					<th class="px-3 py-2 font-medium"><span class="sr-only">Actions</span></th>
				{/if}
			</tr>
		</thead>
		<tbody>
			{#each mappings as row, index (index)}
				<tr class="border-t border-neutral-800 align-top">
					<td class="px-3 py-2 font-mono text-neutral-300">
						{#if readonly}
							{row.templateProperty}
						{:else}
							<input
								bind:value={row.templateProperty}
								class="w-full rounded border border-transparent bg-transparent px-1 py-0.5 font-mono focus:border-neutral-700 focus:bg-neutral-900 focus:outline-none"
							/>
						{/if}
					</td>
					<td class="px-3 py-2">
						{#if readonly}
							<span class="font-mono text-neutral-200">{row.ontologyProperty}</span>
						{:else}
							<div class="flex items-center gap-1.5">
								<input
									value={row.ontologyProperty}
									oninput={(e) => applyOntologyEdit(index, e.currentTarget.value)}
									class={[
										'w-full rounded border bg-neutral-950/60 px-2 py-1 font-mono text-neutral-100 focus:border-blue-700 focus:outline-none',
										isEdited(row) ? 'border-amber-700' : 'border-neutral-800'
									]}
								/>
								<button
									type="button"
									class="shrink-0 rounded border border-neutral-800 px-2 py-1 text-xs text-neutral-400 hover:border-neutral-600 hover:text-neutral-200"
									onclick={() => openSuggest(index)}
									title="Search real ontology candidates"
								>
									Suggest
								</button>
							</div>
							{#if isEdited(row)}
								<span class="mt-1 inline-flex items-center gap-1 text-xs text-amber-500">
									edited from <span class="font-mono"
										>{originalFor(row.templateProperty)?.ontologyProperty}</span
									>
									<button
										type="button"
										class="underline hover:text-amber-300"
										onclick={() => resetRow(index)}
									>
										reset
									</button>
								</span>
							{:else if isNew(row)}
								<span class="mt-1 inline-block text-xs text-blue-400">added by reviewer</span>
							{/if}

							{#if suggestOpenIndex === index}
								<div class="mt-2 rounded-lg border border-neutral-800 bg-neutral-950 p-2">
									<form
										class="flex gap-1.5"
										onsubmit={(e) => {
											e.preventDefault();
											runSuggest();
										}}
									>
										<input
											bind:value={suggestQuery}
											placeholder="Amharic field or English hint"
											class="flex-1 rounded border border-neutral-800 bg-neutral-900 px-2 py-1 text-xs"
										/>
										<button
											type="submit"
											class="rounded bg-neutral-800 px-2 py-1 text-xs hover:bg-neutral-700"
											disabled={suggestLoading}
										>
											{suggestLoading ? '…' : 'Search'}
										</button>
									</form>
									{#if suggestError}
										<p class="mt-1.5 text-xs text-amber-400">{suggestError}</p>
									{:else if suggestResults && suggestResults.length === 0}
										<p class="mt-1.5 text-xs text-neutral-500">No confident match found.</p>
									{:else if suggestResults}
										<ul class="mt-1.5 flex flex-wrap gap-1.5">
											{#each suggestResults as candidate (candidate.property)}
												<li>
													<button
														type="button"
														class="rounded-full border border-neutral-700 bg-neutral-900 px-2 py-1 text-xs text-neutral-200 hover:border-blue-600 hover:text-blue-300"
														onclick={() => applySuggestion(index, candidate)}
													>
														<span class="font-mono">{candidate.property}</span>
														<span class="text-neutral-500">
															{Math.round(candidate.score * 100)}%
														</span>
													</button>
												</li>
											{/each}
										</ul>
									{/if}
								</div>
							{/if}
						{/if}
					</td>
					<td class="px-3 py-2">
						<ConfidencePill confidence={row.confidence} />
					</td>
					{#if !readonly}
						<td class="px-3 py-2 text-right">
							<button
								type="button"
								class="rounded border border-neutral-800 px-2 py-1 text-xs text-neutral-500 hover:border-red-800 hover:text-red-400"
								onclick={() => removeRow(index)}
								title="Remove this mapping"
							>
								Remove
							</button>
						</td>
					{/if}
				</tr>
			{/each}

			{#if !readonly}
				<tr class="border-t border-neutral-800 bg-neutral-900/40">
					<td class="px-3 py-2">
						<input
							bind:value={newTemplateProperty}
							placeholder="new template property"
							class="w-full rounded border border-dashed border-neutral-800 bg-transparent px-2 py-1 font-mono text-xs placeholder:text-neutral-600 focus:border-neutral-600 focus:outline-none"
						/>
					</td>
					<td class="px-3 py-2">
						<input
							bind:value={newOntologyProperty}
							placeholder="new ontology property"
							class="w-full rounded border border-dashed border-neutral-800 bg-transparent px-2 py-1 font-mono text-xs placeholder:text-neutral-600 focus:border-neutral-600 focus:outline-none"
						/>
					</td>
					<td class="px-3 py-2 text-xs text-neutral-600">—</td>
					<td class="px-3 py-2 text-right">
						<button
							type="button"
							class="rounded border border-neutral-700 px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-800 disabled:opacity-40"
							disabled={!newTemplateProperty.trim() || !newOntologyProperty.trim()}
							onclick={addRow}
						>
							+ Add
						</button>
					</td>
				</tr>
			{/if}
		</tbody>
	</table>
</div>

{#if !readonly && removedOriginals.length > 0}
	<div class="mt-2 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
		<span>Removed from the model's prediction:</span>
		{#each removedOriginals as row (row.templateProperty)}
			<button
				type="button"
				class="rounded-full border border-neutral-800 px-2 py-1 font-mono text-neutral-400 hover:border-neutral-600 hover:text-neutral-200"
				onclick={() => restoreRow(row)}
			>
				Restore: {row.templateProperty} to {row.ontologyProperty}
			</button>
		{/each}
	</div>
{/if}
