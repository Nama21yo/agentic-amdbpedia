<script lang="ts">
	import { resolve } from '$app/paths';
	import { BackendUnavailableError, findSemanticMatch, previewMapping } from '$lib/api';
	import ConfidencePill from '$lib/components/ConfidencePill.svelte';
	import StepTracker from '$lib/components/StepTracker.svelte';
	import { pushToast } from '$lib/toast.svelte';
	import type { AgentStep, ChatMessage, PredictedMapping } from '$lib/types';

	let infobox = $state(`{{Infobox bridge\n| ስም = ...\n| ርዝመት = 1,700 ሜትር\n}}`);
	let targetClass = $state('');
	let steps = $state<AgentStep[]>([]);
	let mappings = $state<PredictedMapping[]>([]);
	let running = $state(false);
	let error = $state<string | null>(null);
	let done = $state(false);

	async function runPreview() {
		if (!infobox.trim()) return;
		running = true;
		error = null;
		done = false;
		steps = [];
		mappings = [];
		try {
			for await (const event of previewMapping(infobox, targetClass || undefined)) {
				if ('mappings' in event) {
					mappings = event.mappings;
					done = true;
				} else {
					steps = [...steps, event];
				}
			}
		} catch (err) {
			error =
				err instanceof BackendUnavailableError
					? 'cross-lingual is not reachable — check that the HTTP server (just run-http) is running.'
					: 'Unexpected error while running the mapping agent.';
			pushToast(error, 'error');
		} finally {
			running = false;
		}
	}

	let chatInput = $state('');
	let chatMessages = $state<ChatMessage[]>([]);
	let chatBusy = $state(false);

	async function askAssistant() {
		if (!chatInput.trim()) return;
		const question = chatInput;
		chatMessages = [...chatMessages, { role: 'user', content: question }];
		chatInput = '';
		chatBusy = true;
		try {
			const result = await findSemanticMatch(question, targetClass || undefined);
			const reply =
				result.status === 'no_match'
					? 'No confident match found in the ontology for that term.'
					: result.matches.map((m) => `${m.property} (${Math.round(m.score * 100)}%)`).join(', ');
			chatMessages = [...chatMessages, { role: 'assistant', content: reply }];
		} catch (err) {
			const reply =
				err instanceof BackendUnavailableError
					? 'cross-lingual is not reachable yet — this answers live once its HTTP endpoint is implemented.'
					: 'Unexpected error while asking the assistant.';
			chatMessages = [...chatMessages, { role: 'assistant', content: reply }];
		} finally {
			chatBusy = false;
		}
	}
</script>

<h1 class="mb-1 text-xl font-semibold">Mapping Assistant</h1>
<p class="mb-6 text-sm text-neutral-400">
	Paste an Amharic infobox and prepare a draft DBpedia mapping. Nothing here is published until a
	reviewer approves it — and opts in to publishing — on the
	<a
		href={resolve('/review')}
		class="text-blue-400 underline underline-offset-2 hover:text-blue-300">Review Queue</a
	>.
</p>

<div class="grid gap-8 md:grid-cols-2">
	<section class="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
		<label class="mb-1 block text-sm text-neutral-400" for="infobox">Infobox wikitext</label>
		<textarea
			id="infobox"
			bind:value={infobox}
			rows="10"
			class="w-full rounded-lg border border-neutral-800 bg-neutral-950/60 p-3 font-mono text-sm focus:border-blue-700 focus:outline-none"
		></textarea>

		<label class="mt-4 mb-1 block text-sm text-neutral-400" for="target-class">
			Target class (optional)
		</label>
		<input
			id="target-class"
			bind:value={targetClass}
			placeholder="e.g. Bridge"
			class="w-full rounded-lg border border-neutral-800 bg-neutral-950/60 p-2 text-sm focus:border-blue-700 focus:outline-none"
		/>

		<button
			class="mt-4 rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
			onclick={runPreview}
			disabled={running || !infobox.trim()}
		>
			{running ? 'Running…' : 'Prepare mapping'}
		</button>

		{#if error}
			<p
				class="mt-4 rounded-lg border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm text-amber-300"
			>
				{error}
			</p>
		{/if}

		<StepTracker {steps} {running} />

		{#if mappings.length > 0}
			<div class="mt-6 overflow-x-auto rounded-lg border border-neutral-800">
				<table class="w-full text-left text-sm">
					<thead class="bg-neutral-900/80 text-neutral-400">
						<tr>
							<th class="px-3 py-2 font-medium">Template property</th>
							<th class="px-3 py-2 font-medium">Ontology property</th>
							<th class="px-3 py-2 font-medium">Confidence</th>
						</tr>
					</thead>
					<tbody>
						{#each mappings as mapping (mapping.templateProperty)}
							<tr class="border-t border-neutral-800">
								<td class="px-3 py-2 font-mono text-neutral-300">{mapping.templateProperty}</td>
								<td class="px-3 py-2 font-mono text-neutral-100">{mapping.ontologyProperty}</td>
								<td class="px-3 py-2"><ConfidencePill confidence={mapping.confidence} /></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			{#if done}
				<a
					href={resolve('/review')}
					class="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-emerald-800 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-300 hover:bg-emerald-950/70"
				>
					✓ Sent to the Review Queue — review and correct it now →
				</a>
			{/if}
		{/if}
	</section>

	<section class="rounded-xl border border-neutral-800 bg-neutral-900/40 p-5">
		<h2 class="mb-2 text-sm text-neutral-400">Ask the assistant</h2>
		<p class="mb-3 text-xs text-neutral-600">
			Quick lookup against the same retrieval index — doesn't submit anything for review.
		</p>
		<div
			class="h-64 space-y-2 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-950/60 p-3 text-sm"
		>
			{#if chatMessages.length === 0}
				<p class="text-neutral-600">e.g. "what about ቁመት instead?"</p>
			{/if}
			{#each chatMessages as message, i (i)}
				<p class={message.role === 'user' ? 'text-neutral-100' : 'text-emerald-400'}>
					<span class="text-neutral-500">{message.role === 'user' ? 'you' : 'assistant'}:</span>
					{message.content}
				</p>
			{/each}
			{#if chatBusy}
				<p class="text-neutral-500">assistant: …</p>
			{/if}
		</div>
		<form
			class="mt-2 flex gap-2"
			onsubmit={(event) => {
				event.preventDefault();
				askAssistant();
			}}
		>
			<input
				bind:value={chatInput}
				placeholder="e.g. what about ቁመት instead?"
				class="flex-1 rounded-lg border border-neutral-800 bg-neutral-950/60 p-2 text-sm focus:border-blue-700 focus:outline-none"
			/>
			<button
				type="submit"
				disabled={chatBusy || !chatInput.trim()}
				class="rounded-lg bg-neutral-800 px-3 py-2 text-sm hover:bg-neutral-700 disabled:opacity-50"
			>
				Ask
			</button>
		</form>
	</section>
</div>
