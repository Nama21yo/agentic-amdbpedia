<script lang="ts">
	import { onMount } from 'svelte';
	import {
		BackendUnavailableError,
		DecisionFailedError,
		decideReview,
		listReviewQueue
	} from '$lib/api';
	import type { PredictedMapping, ReviewItem, ReviewStatus } from '$lib/types';
	import { toast } from 'svelte-sonner';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Card } from '$lib/components/ui/card/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Skeleton } from '$lib/components/ui/skeleton/index.js';
	import { Textarea } from '$lib/components/ui/textarea/index.js';
	import * as AlertDialog from '$lib/components/ui/alert-dialog/index.js';
	import MappingEditor from '$lib/components/MappingEditor.svelte';
	import StatusBadge from '$lib/components/StatusBadge.svelte';
	import { cn } from '$lib/utils.js';
	import RefreshCwIcon from '@lucide/svelte/icons/refresh-cw';
	import ChevronRightIcon from '@lucide/svelte/icons/chevron-right';
	import ChevronDownIcon from '@lucide/svelte/icons/chevron-down';
	import InboxIcon from '@lucide/svelte/icons/inbox';
	import LoaderCircleIcon from '@lucide/svelte/icons/loader-circle';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-alert';

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
			console.error('Failed to load the review queue:', err);
			loadError =
				err instanceof BackendUnavailableError
					? 'cross-lingual is not reachable — check that the HTTP server (just run-http) is running.'
					: `Unexpected error while loading the review queue: ${err instanceof Error ? err.message : String(err)}`;
		} finally {
			loading = false;
		}
	}

	onMount(load);

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
			toast.success(
				updated.status === 'published'
					? `Published ${updated.templateName} to the live wiki.`
					: `Marked ${updated.templateName} as ${updated.status.replace('_', ' ')}.`
			);
		} catch (err) {
			if (err instanceof DecisionFailedError) {
				if (err.review) applyServerState(err.review);
				toast.error(`Publish failed: ${err.message}`);
			} else {
				toast.error('Could not record that decision — backend not reachable.');
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
		<h1 class="text-2xl font-semibold tracking-tight">Review Queue</h1>
		<p class="mt-1 text-sm text-muted-foreground">
			Mapping-agent predictions wait here until a reviewer approves, corrects, or rejects them.
			Nothing is written to the live wiki without explicit publish consent per item.
		</p>
	</div>
	<Button variant="outline" size="sm" onclick={load} disabled={loading} class="shrink-0">
		<RefreshCwIcon class={cn('size-3.5', loading && 'animate-spin')} />
		Refresh
	</Button>
</div>

<div class="mb-6 flex flex-wrap gap-1.5">
	{#each filters as f (f.value)}
		<Button
			variant={filter === f.value ? 'default' : 'outline'}
			size="sm"
			class="h-7 rounded-full px-3"
			onclick={() => (filter = f.value)}
		>
			{f.label}
			<span class="tabular-nums opacity-70">
				{f.value === 'all' ? items.length : (counts[f.value] ?? 0)}
			</span>
		</Button>
	{/each}
</div>

{#if loading}
	<div class="space-y-3">
		<Skeleton class="h-20 w-full" />
		<Skeleton class="h-20 w-full" />
		<Skeleton class="h-20 w-full" />
	</div>
{:else if loadError}
	<div
		class="flex items-center gap-2 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning-foreground"
	>
		<TriangleAlertIcon class="size-4 shrink-0" />
		{loadError}
	</div>
{:else if visibleItems.length === 0}
	<div
		class="flex flex-col items-center gap-2 rounded-lg border border-dashed py-12 text-center text-sm text-muted-foreground"
	>
		<InboxIcon class="size-8 opacity-40" />
		Nothing here right now.
	</div>
{:else}
	<ul class="space-y-3">
		{#each visibleItems as item (item.id)}
			{@const isPending = item.status === 'pending_review'}
			{@const isOpen = Boolean(expanded[item.id])}
			<Card class="gap-0 overflow-hidden py-0">
				<button
					type="button"
					class="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-muted/40"
					onclick={() => toggleExpanded(item)}
				>
					<div class="flex items-center gap-3">
						<span class="text-muted-foreground">
							{#if isOpen}
								<ChevronDownIcon class="size-4" />
							{:else}
								<ChevronRightIcon class="size-4" />
							{/if}
						</span>
						<div>
							<p class="text-sm font-medium">{item.templateName}</p>
							<p class="text-xs text-muted-foreground">
								{item.domainClass} · {item.mappings.length} mapping{item.mappings.length === 1
									? ''
									: 's'} · {new Date(item.submittedAt).toLocaleString()}
							</p>
						</div>
					</div>
					<StatusBadge status={item.status} />
				</button>

				{#if isOpen}
					<div class="border-t px-4 py-4">
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
								<Textarea
									bind:value={reasons[item.id]}
									placeholder="Reason (optional) — recorded on the decision log either way"
									rows={2}
								/>

								<Label class="items-start gap-2 text-xs font-normal text-muted-foreground">
									<Checkbox bind:checked={publishFlags[item.id]} class="mt-0.5" />
									<span>
										Also publish to the live wiki on approval
										<span class="text-muted-foreground/70"
											>— a real, outward-facing edit to mappings.dbpedia.org; you'll be asked to
											confirm.</span
										>
									</span>
								</Label>

								<div class="flex justify-end gap-2">
									<Button
										variant="outline"
										class="border-destructive/40 text-destructive hover:bg-destructive/10"
										onclick={() => submit(item, 'rejected')}
										disabled={submitting[item.id]}
									>
										{#if submitting[item.id]}
											<LoaderCircleIcon class="animate-spin" />
										{/if}
										Reject
									</Button>
									<Button onclick={() => onApproveClick(item)} disabled={submitting[item.id]}>
										{#if submitting[item.id]}
											<LoaderCircleIcon class="animate-spin" />
											Working…
										{:else if publishFlags[item.id]}
											Approve & publish…
										{:else}
											Approve
										{/if}
									</Button>
								</div>
							</div>
						{/if}
					</div>
				{/if}
			</Card>
		{/each}
	</ul>
{/if}

{#each items as item (item.id)}
	<AlertDialog.Root
		open={confirmPublishFor === item.id}
		onOpenChange={(open) => {
			if (!open) confirmPublishFor = null;
		}}
	>
		<AlertDialog.Content>
			<AlertDialog.Header>
				<AlertDialog.Title>Publish this mapping live?</AlertDialog.Title>
				<AlertDialog.Description>
					This writes <span class="font-mono text-foreground">{item.templateName}</span> to
					<span class="font-mono text-foreground">mappings.dbpedia.org</span> immediately, using a MediaWiki
					Bot Password — a real edit, not a preview.
				</AlertDialog.Description>
			</AlertDialog.Header>
			{#if drafts[item.id]}
				<ul class="space-y-1 rounded-lg border bg-muted/40 p-2">
					{#each drafts[item.id] as row (row.templateProperty)}
						<li class="font-mono text-xs">
							{row.templateProperty} to
							<span class="text-foreground">{row.ontologyProperty}</span>
						</li>
					{/each}
				</ul>
			{/if}
			<AlertDialog.Footer>
				<AlertDialog.Cancel>Cancel</AlertDialog.Cancel>
				<AlertDialog.Action
					disabled={Boolean(submitting[item.id])}
					onclick={(e) => {
						e.preventDefault();
						submit(item, 'approved');
					}}
				>
					{#if submitting[item.id]}
						<LoaderCircleIcon class="animate-spin" />
					{/if}
					Publish
				</AlertDialog.Action>
			</AlertDialog.Footer>
		</AlertDialog.Content>
	</AlertDialog.Root>
{/each}
