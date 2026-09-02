<script lang="ts">
	import {
		BackendUnavailableError,
		DecisionFailedError,
		decideReview,
		listReviewQueue
	} from '$lib/api';
	import type { PredictedMapping, ReviewItem, ReviewStatus } from '$lib/types';
	import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
	import MappingEditor from '$lib/components/MappingEditor.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { pushToast } from '$lib/toast.svelte';

	let items = $state<ReviewItem[]>([]);
	let loading = $state(true);
	let loadError = $state<string | null>(null);

	type Filter = 'pending_review' | 'all' | ReviewStatus;
	let filter = $state<Filter>('pending_review');

	// Per-item working state, created lazily the first time a card expands.
	// Kept separate from `items` so cancelling an edit or collapsing a card
	// never mutates what was actually fetched from the server.
	let drafts = $state<Record<string, PredictedMapping[]>>({});
	let reasons = $state<Record<string, string>>({});
	let publishFlags = $state<Record<string, boolean>>({});
	let submitting = $state<Record<string, boolean>>({});
	let expanded = $state<Record<string, boolean>>({});
	let confirmPublishFor = $state<string | null>(null);

	function ensureDraft(item: ReviewItem) {
		if (!drafts[item.id]) drafts[item.id] = structuredClone(item.mappings);
	}

	async function load() {
		loading = true;
		loadError = null;
		try {
			items = await listReviewQueue();
			for (const item of items) {
				if (item.status === 'pending_review') {
					expanded[item.id] = true;
					ensureDraft(item);
				}
			}
		} catch (err) {
			loadError =
				err instanceof BackendUnavailableError
					? 'cross-lingual is not reachable — check that the HTTP server (just run-http) is running.'
					: 'Unexpected error while loading the review queue.';
		} finally {
			loading = false;
		}
	}

	load();

	const counts = $derived(
		items.reduce<Record<string, number>>((acc, item) => {
			acc[item.status] = (acc[item.status] ?? 0) + 1;
			return acc;
		}, {})
	);

	const visibleItems = $derived(
		filter === 'all' ? items : items.filter((item) => item.status === filter)
	);

	function toggleExpanded(item: ReviewItem) {
		expanded[item.id] = !expanded[item.id];
		if (expanded[item.id] && item.status === 'pending_review') ensureDraft(item);
	}

	function mappingsDiffer(a: PredictedMapping[], b: PredictedMapping[]) {
		return JSON.stringify(a) !== JSON.stringify(b);
	}

	function applyServerState(updated: ReviewItem) {
		items = items.map((item) => (item.id === updated.id ? updated : item));
		delete drafts[updated.id];
		delete reasons[updated.id];
		delete publishFlags[updated.id];
	}

	async function submit(item: ReviewItem, decision: 'approved' | 'rejected') {
		submitting[item.id] = true;
		try {
			const draft = drafts[item.id];
			const corrected = draft && mappingsDiffer(draft, item.mappings) ? draft : undefined;
			const updated = await decideReview(item.id, decision, {
				reason: reasons[item.id]?.trim() || undefined,
				correctedMappings: corrected,
				publish: decision === 'approved' && Boolean(publishFlags[item.id])
			});
			applyServerState(updated);
			pushToast(
				updated.status === 'published'
					? `Published ${updated.templateName} to the live wiki.`
					: `Marked ${updated.templateName} as ${updated.status.replace('_', ' ')}.`,
				'success'
			);
		} catch (err) {
			if (err instanceof DecisionFailedError) {
				if (err.review) applyServerState(err.review);
				pushToast(`Publish failed: ${err.message}`, 'error', 8000);
			} else {
				pushToast('Could not record that decision — backend not reachable.', 'error');
			}
		} finally {
			submitting[item.id] = false;
			confirmPublishFor = null;
		}
	}

	function onApproveClick(item: ReviewItem) {
		if (publishFlags[item.id]) {
			confirmPublishFor = item.id;
		} else {
			submit(item, 'approved');
		}
	}

	const filters: { value: Filter; label: string }[] = [
		{ value: 'pending_review', label: 'Pending' },
		{ value: 'approved', label: 'Approved' },
		{ value: 'published', label: 'Published' },
		{ value: 'rejected', label: 'Rejected' },
		{ value: 'all', label: 'All' }
	];
</script>

<div class="mb-6 flex items-start justify-between gap-4">
	<div>
		<h1 class="mb-1 text-xl font-semibold">Review Queue</h1>
		<p class="text-sm text-neutral-400">
			Mapping-agent predictions wait here until a reviewer approves, corrects, or rejects them.
			Nothing is written to the live wiki without explicit publish consent per item.
		</p>
	</div>
	<button
		type="button"
		class="shrink-0 rounded-lg border border-neutral-800 px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-900"
		onclick={load}
		disabled={loading}
	>
		{loading ? 'Refreshing…' : '↻ Refresh'}
	</button>
</div>

<div class="mb-6 flex flex-wrap gap-1.5">
	{#each filters as f (f.value)}
		<button
			type="button"
			class={[
				'rounded-full border px-3 py-1 text-xs font-medium',
				filter === f.value
					? 'border-blue-700 bg-blue-950/60 text-blue-300'
					: 'border-neutral-800 text-neutral-400 hover:border-neutral-700 hover:text-neutral-200'
			]}
			onclick={() => (filter = f.value)}
		>
			{f.label}
			<span class="ml-1 tabular-nums opacity-70">
				{f.value === 'all' ? items.length : (counts[f.value] ?? 0)}
			</span>
		</button>
	{/each}
</div>

{#if loading}
	<div class="space-y-3">
		<div class="h-20 animate-pulse rounded-lg border border-neutral-800 bg-neutral-900/40"></div>
		<div class="h-20 animate-pulse rounded-lg border border-neutral-800 bg-neutral-900/40"></div>
		<div class="h-20 animate-pulse rounded-lg border border-neutral-800 bg-neutral-900/40"></div>
	</div>
{:else if loadError}
	<p class="rounded-lg border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm text-amber-300">
		{loadError}
	</p>
{:else if visibleItems.length === 0}
	<p
		class="rounded-lg border border-dashed border-neutral-800 px-4 py-8 text-center text-sm text-neutral-500"
	>
		Nothing here right now.
	</p>
{:else}
	<ul class="space-y-3">
		{#each visibleItems as item (item.id)}
			{@const isPending = item.status === 'pending_review'}
			{@const isOpen = Boolean(expanded[item.id])}
			<li class="rounded-lg border border-neutral-800 bg-neutral-900/40">
				<button
					type="button"
					class="flex w-full items-center justify-between gap-4 px-4 py-3 text-left"
					onclick={() => toggleExpanded(item)}
				>
					<div class="flex items-center gap-3">
						<span class="text-neutral-600">{isOpen ? '▾' : '▸'}</span>
						<div>
							<p class="text-sm font-medium text-neutral-100">{item.templateName}</p>
							<p class="text-xs text-neutral-500">
								{item.domainClass} · {item.mappings.length} mapping{item.mappings.length === 1
									? ''
									: 's'} · {new Date(item.submittedAt).toLocaleString()}
							</p>
						</div>
					</div>
					<StatusBadge status={item.status} />
				</button>

				{#if isOpen}
					<div class="border-t border-neutral-800 px-4 py-4">
						{#if isPending && drafts[item.id]}
							<MappingEditor
								bind:mappings={drafts[item.id]}
								original={item.mappings}
								domainClass={item.domainClass}
							/>
						{:else}
							<MappingEditor
								mappings={item.mappings}
								original={item.mappings}
								domainClass={item.domainClass}
								readonly
							/>
						{/if}

						{#if isPending}
							<div class="mt-4 flex flex-col gap-3">
								<textarea
									bind:value={reasons[item.id]}
									placeholder="Reason (optional) — recorded on the decision log either way"
									rows="2"
									class="w-full rounded-lg border border-neutral-800 bg-neutral-950/60 p-2 text-sm placeholder:text-neutral-600"
								></textarea>

								<label class="flex items-start gap-2 text-xs text-neutral-400">
									<input
										type="checkbox"
										bind:checked={publishFlags[item.id]}
										class="mt-0.5 accent-emerald-600"
									/>
									<span>
										Also publish to the live wiki on approval
										<span class="text-neutral-600"
											>— a real, outward-facing edit to mappings.dbpedia.org; you'll be asked to
											confirm.</span
										>
									</span>
								</label>

								<div class="flex justify-end gap-2">
									<button
										type="button"
										class="rounded-lg border border-red-900 px-4 py-2 text-sm text-red-300 hover:bg-red-950/50 disabled:opacity-50"
										onclick={() => submit(item, 'rejected')}
										disabled={submitting[item.id]}
									>
										{submitting[item.id] ? 'Working…' : 'Reject'}
									</button>
									<button
										type="button"
										class="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
										onclick={() => onApproveClick(item)}
										disabled={submitting[item.id]}
									>
										{submitting[item.id]
											? 'Working…'
											: publishFlags[item.id]
												? 'Approve & publish…'
												: 'Approve'}
									</button>
								</div>
							</div>
						{/if}
					</div>
				{/if}
			</li>
		{/each}
	</ul>
{/if}

{#each items as item (item.id)}
	{#if confirmPublishFor === item.id && drafts[item.id]}
		<ConfirmDialog
			open={true}
			title="Publish this mapping live?"
			confirmLabel="Publish"
			busy={Boolean(submitting[item.id])}
			onconfirm={() => submit(item, 'approved')}
			oncancel={() => (confirmPublishFor = null)}
		>
			<p>
				This writes <span class="font-mono text-neutral-300">{item.templateName}</span> to
				<span class="font-mono text-neutral-300">mappings.dbpedia.org</span> immediately, using a MediaWiki
				Bot Password — a real edit, not a preview.
			</p>
			<ul class="mt-3 space-y-1 rounded-lg border border-neutral-800 bg-neutral-950/60 p-2">
				{#each drafts[item.id] as row (row.templateProperty)}
					<li class="font-mono text-xs text-neutral-300">
						{row.templateProperty} → <span class="text-neutral-100">{row.ontologyProperty}</span>
					</li>
				{/each}
			</ul>
		</ConfirmDialog>
	{/if}
{/each}
