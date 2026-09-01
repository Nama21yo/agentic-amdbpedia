<script lang="ts">
	import { BackendUnavailableError, findSemanticMatch, previewMapping } from '$lib/api';
	import type { ChatMessage, PredictedMapping } from '$lib/types';

	let infobox = $state(`{{Infobox bridge\n| ስም = ...\n| ርዝመት = 1,700 ሜትር\n}}`);
	let targetClass = $state('');
	let steps = $state<Array<{ node: string; status: string; detail?: string }>>([]);
	let mappings = $state<PredictedMapping[]>([]);
	let running = $state(false);
	let error = $state<string | null>(null);

	async function runPreview() {
		running = true;
		error = null;
		steps = [];
		mappings = [];
		try {
			for await (const event of previewMapping(infobox, targetClass || undefined)) {
				if ('mappings' in event) {
					mappings = event.mappings;
				} else {
					steps = [...steps, event];
				}
			}
		} catch (err) {
			error =
				err instanceof BackendUnavailableError
					? 'agentic-dbpedia is not reachable yet — this streams live once /api/v2/agent/preview is implemented.'
					: 'Unexpected error while running the mapping agent.';
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
	maintainer approves it on the Review Queue.
</p>

<div class="grid gap-8 md:grid-cols-2">
	<section>
		<label class="mb-1 block text-sm text-neutral-400" for="infobox">Infobox wikitext</label>
		<textarea
			id="infobox"
			bind:value={infobox}
			rows="10"
			class="w-full rounded border border-neutral-800 bg-neutral-900 p-3 font-mono text-sm"
		></textarea>

		<label class="mt-4 mb-1 block text-sm text-neutral-400" for="target-class">
			Target class (optional)
		</label>
		<input
			id="target-class"
			bind:value={targetClass}
			placeholder="e.g. Bridge"
			class="w-full rounded border border-neutral-800 bg-neutral-900 p-2 text-sm"
		/>

		<button
			class="mt-4 rounded bg-blue-700 px-4 py-2 text-sm font-medium hover:bg-blue-600 disabled:opacity-50"
			onclick={runPreview}
			disabled={running}
		>
			{running ? 'Running…' : 'Prepare mapping'}
		</button>

		{#if error}
			<p
				class="mt-4 rounded border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm text-amber-300"
			>
				{error}
			</p>
		{/if}

		{#if steps.length > 0}
			<ol class="mt-6 space-y-1 text-sm text-neutral-400">
				{#each steps as step, i (i)}
					<li>→ {step.node} — {step.status}{step.detail ? `: ${step.detail}` : ''}</li>
				{/each}
			</ol>
		{/if}

		{#if mappings.length > 0}
			<table class="mt-6 w-full text-left text-sm">
				<thead class="text-neutral-400">
					<tr>
						<th class="pb-2">Template property</th>
						<th class="pb-2">Ontology property</th>
						<th class="pb-2">Confidence</th>
					</tr>
				</thead>
				<tbody>
					{#each mappings as mapping (mapping.templateProperty)}
						<tr class="border-t border-neutral-800">
							<td class="py-2">{mapping.templateProperty}</td>
							<td class="py-2">{mapping.ontologyProperty}</td>
							<td class="py-2">{Math.round(mapping.confidence * 100)}%</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</section>

	<section>
		<h2 class="mb-2 text-sm text-neutral-400">Ask the assistant</h2>
		<div
			class="h-64 space-y-2 overflow-y-auto rounded border border-neutral-800 bg-neutral-900 p-3 text-sm"
		>
			{#each chatMessages as message, i (i)}
				<p class={message.role === 'user' ? 'text-neutral-100' : 'text-emerald-400'}>
					<span class="text-neutral-500">{message.role === 'user' ? 'you' : 'assistant'}:</span>
					{message.content}
				</p>
			{/each}
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
				class="flex-1 rounded border border-neutral-800 bg-neutral-900 p-2 text-sm"
			/>
			<button
				type="submit"
				disabled={chatBusy}
				class="rounded bg-neutral-800 px-3 py-2 text-sm hover:bg-neutral-700 disabled:opacity-50"
			>
				Ask
			</button>
		</form>
	</section>
</div>
