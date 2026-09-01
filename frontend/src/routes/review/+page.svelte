<script lang="ts">
	import { BackendUnavailableError, decideReview, listReviewQueue } from '$lib/api';
	import type { ReviewItem } from '$lib/types';

	let items = $state<ReviewItem[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);

	async function load() {
		loading = true;
		error = null;
		try {
			items = await listReviewQueue();
		} catch (err) {
			error =
				err instanceof BackendUnavailableError
					? 'agentic-dbpedia is not reachable yet — this table populates once the review-queue endpoint is implemented.'
					: 'Unexpected error while loading the review queue.';
		} finally {
			loading = false;
		}
	}

	load();

	async function decide(id: string, decision: 'approved' | 'rejected') {
		try {
			await decideReview(id, decision);
			items = items.map((item) => (item.id === id ? { ...item, status: decision } : item));
		} catch {
			error = 'Could not record that decision — backend not reachable.';
		}
	}
</script>

<h1 class="mb-1 text-xl font-semibold">Review Queue</h1>
<p class="mb-6 text-sm text-neutral-400">
	Mapping-agent predictions wait here until a maintainer approves or rejects them. Approval is the
	only path to publishing on the Mappings Wiki.
</p>

{#if loading}
	<p class="text-neutral-400">Loading…</p>
{:else if error}
	<p class="rounded border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm text-amber-300">
		{error}
	</p>
{:else if items.length === 0}
	<p class="text-neutral-400">Nothing pending review.</p>
{:else}
	<table class="w-full text-left text-sm">
		<thead class="text-neutral-400">
			<tr>
				<th class="pb-2">Template</th>
				<th class="pb-2">Class</th>
				<th class="pb-2">Status</th>
				<th class="pb-2">Submitted</th>
				<th class="pb-2"></th>
			</tr>
		</thead>
		<tbody>
			{#each items as item (item.id)}
				<tr class="border-t border-neutral-800">
					<td class="py-2">{item.templateName}</td>
					<td class="py-2">{item.domainClass}</td>
					<td class="py-2">{item.status}</td>
					<td class="py-2 text-neutral-400">{new Date(item.submittedAt).toLocaleString()}</td>
					<td class="py-2">
						{#if item.status === 'pending_review'}
							<button
								class="mr-2 rounded bg-emerald-700 px-2 py-1 text-xs hover:bg-emerald-600"
								onclick={() => decide(item.id, 'approved')}
							>
								Approve
							</button>
							<button
								class="rounded bg-red-800 px-2 py-1 text-xs hover:bg-red-700"
								onclick={() => decide(item.id, 'rejected')}
							>
								Reject
							</button>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
{/if}
