<script lang="ts">
	import { resolve } from '$app/paths';
	import { BackendUnavailableError, findSemanticMatch, previewMapping } from '$lib/api';
	import {
		type PipelineTurn,
		type AnswerTurn,
		currentSession,
		ensureActiveSession,
		touchSession
	} from '$lib/chat.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Textarea } from '$lib/components/ui/textarea/index.js';
	import {
		Table,
		TableBody,
		TableCell,
		TableHead,
		TableHeader,
		TableRow
	} from '$lib/components/ui/table/index.js';
	import ConfidencePill from '$lib/components/ConfidencePill.svelte';
	import StepTracker from '$lib/components/StepTracker.svelte';
	import ThinkingIndicator from '$lib/components/ThinkingIndicator.svelte';
	import logo from '$lib/assets/dbpedia-am-logo.png';
	import Fa from 'svelte-fa';
	import { faArrowUp, faArrowRight, faCircleCheck } from '@fortawesome/free-solid-svg-icons';

	let input = $state('');
	let targetClass = $state('');
	let busy = $state(false);
	let scrollAnchor: HTMLDivElement | undefined = $state();

	const turns = $derived(currentSession()?.turns ?? []);

	function looksLikeInfobox(text: string): boolean {
		return /\{\{\s*infobox/i.test(text) || text.trim().startsWith('{{');
	}

	function scrollToBottom() {
		requestAnimationFrame(() => scrollAnchor?.scrollIntoView({ behavior: 'smooth', block: 'end' }));
	}

	async function submit(text?: string) {
		const value = (text ?? input).trim();
		if (!value || busy) return;
		input = '';
		busy = true;

		const session = ensureActiveSession();
		const id = crypto.randomUUID();
		const wantsClass = targetClass.trim() || undefined;

		if (looksLikeInfobox(value)) {
			session.turns.push({
				id,
				kind: 'pipeline',
				input: value,
				targetClass: wantsClass,
				steps: [],
				mappings: null,
				running: true
			});
			// `session` is an element of the `sessions` $state array, and
			// Svelte 5 wraps a plain object in its own reactive proxy the
			// moment it's inserted into a $state container -- that proxy,
			// not the object literal above, is what the template actually
			// reads. Re-reading the just-pushed element by reference here
			// (rather than continuing to mutate the object literal) is what
			// makes every mutation below actually reach the DOM; mutating
			// the pre-push literal directly is silently invisible to Svelte
			// (confirmed live: the "Thinking…" indicator never clears,
			// steps/mappings never appear, because turn.steps/turn.mappings
			// assignments were landing on a detached object nothing was
			// still watching).
			const turn = session.turns[session.turns.length - 1] as PipelineTurn;
			touchSession(session.id);
			scrollToBottom();
			try {
				for await (const event of previewMapping(value, wantsClass)) {
					if ('mappings' in event) {
						turn.mappings = event.mappings;
						turn.mappingWikitext = event.mappingWikitext;
						turn.xmlRules = event.xmlRules;
					} else {
						turn.steps = [...turn.steps, event];
					}
					scrollToBottom();
				}
			} catch (err) {
				console.error('Mapping pipeline failed:', err);
				turn.error =
					err instanceof BackendUnavailableError
						? 'cross-lingual is not reachable — check that the HTTP server (just run-http) is running.'
						: `Unexpected error: ${err instanceof Error ? err.message : String(err)}`;
			} finally {
				turn.running = false;
				touchSession(session.id);
			}
		} else {
			session.turns.push({
				id,
				kind: 'answer',
				input: value,
				targetClass: wantsClass,
				matches: null,
				noMatch: false,
				running: true
			});
			// See the comment above the pipeline branch's push -- same fix,
			// same reason.
			const turn = session.turns[session.turns.length - 1] as AnswerTurn;
			touchSession(session.id);
			scrollToBottom();
			try {
				const result = await findSemanticMatch(value, wantsClass);
				if (result.status === 'no_match') {
					turn.noMatch = true;
				} else {
					turn.matches = result.matches;
				}
			} catch (err) {
				console.error('Assistant lookup failed:', err);
				turn.error =
					err instanceof BackendUnavailableError
						? 'cross-lingual is not reachable — check that the HTTP server (just run-http) is running.'
						: `Unexpected error: ${err instanceof Error ? err.message : String(err)}`;
			} finally {
				turn.running = false;
				touchSession(session.id);
			}
		}

		busy = false;
		scrollToBottom();
	}

	function onKeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			submit();
		}
	}

	const examples = [
		{
			label: 'Paste an infobox to map',
			value: `{{Infobox bridge\n| ስም = ደደሳ ድልድይ\n| ርዝመት = 1,700 ሜትር\n}}`
		},
		{ label: 'Ask what a field maps to', value: 'አይካኦ_ኮድ' }
	];
</script>

<div class="mx-auto flex h-full max-w-3xl flex-col">
	<div class="flex-1 overflow-y-auto px-4 py-6 md:px-8">
		{#if turns.length === 0}
			<div class="flex h-full flex-col items-center justify-center gap-6 text-center">
				<img src={logo} alt="Amharic DBpedia" class="size-16 object-contain" />
				<div>
					<h1 class="text-2xl font-semibold tracking-tight">Amharic → DBpedia Mapping Assistant</h1>
					<p class="mt-2 text-sm text-muted-foreground">
						Paste an infobox to prepare a draft mapping, or ask about a single field. Nothing is
						published until a reviewer approves it on the
						<a href={resolve('/review')} class="text-primary underline underline-offset-4"
							>Review Queue</a
						>.
					</p>
				</div>
				<div class="flex flex-wrap justify-center gap-2">
					{#each examples as example (example.label)}
						<button
							type="button"
							class="rounded-full border px-3.5 py-1.5 text-sm hover:border-primary/50 hover:bg-accent"
							onclick={() => submit(example.value)}
						>
							{example.label}
						</button>
					{/each}
				</div>
			</div>
		{:else}
			<div class="flex flex-col gap-6">
				{#each turns as turn (turn.id)}
					<div class="flex justify-end">
						<div class="max-w-[85%]">
							<pre
								class="rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm whitespace-pre-wrap text-primary-foreground">{turn.input}</pre>
							{#if turn.targetClass}
								<p class="mt-1 pr-1 text-right text-xs text-muted-foreground">
									class: {turn.targetClass}
								</p>
							{/if}
						</div>
					</div>

					<div class="flex flex-col gap-3">
						{#if turn.kind === 'pipeline'}
							{#if turn.running && turn.steps.length === 0}
								<ThinkingIndicator label="Extracting and predicting" />
							{/if}
							<StepTracker steps={turn.steps} />
							{#if turn.mappings && turn.mappings.length > 0}
								<div class="overflow-hidden rounded-lg border">
									<Table>
										<TableHeader>
											<TableRow class="hover:bg-transparent">
												<TableHead>Template property</TableHead>
												<TableHead>Ontology property</TableHead>
												<TableHead>Confidence</TableHead>
											</TableRow>
										</TableHeader>
										<TableBody>
											{#each turn.mappings as mapping (mapping.templateProperty)}
												<TableRow>
													<TableCell class="font-mono">{mapping.templateProperty}</TableCell>
													<TableCell class="font-mono">{mapping.ontologyProperty}</TableCell>
													<TableCell><ConfidencePill confidence={mapping.confidence} /></TableCell>
												</TableRow>
											{/each}
										</TableBody>
									</Table>
								</div>
								{#if turn.mappingWikitext}
									<details class="rounded-lg border">
										<summary
											class="cursor-pointer px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
										>
											View mapping wikitext
										</summary>
										<pre
											class="overflow-x-auto border-t bg-muted/40 px-3 py-2.5 font-mono text-xs whitespace-pre-wrap">{turn.mappingWikitext}</pre>
									</details>
								{/if}
								{#if turn.xmlRules}
									<details class="rounded-lg border">
										<summary
											class="cursor-pointer px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground"
										>
											View mapping XML
										</summary>
										<pre
											class="overflow-x-auto border-t bg-muted/40 px-3 py-2.5 font-mono text-xs whitespace-pre-wrap">{turn.xmlRules}</pre>
									</details>
								{/if}
								<a
									href={resolve('/review')}
									class="flex w-fit items-center gap-2 rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm font-medium text-success"
								>
									<Fa icon={faCircleCheck} class="size-3.5 shrink-0" />
									Sent to the Review Queue
									<Fa icon={faArrowRight} class="size-3 shrink-0" />
								</a>
							{:else if turn.mappings}
								<p class="text-sm text-muted-foreground">
									No properties were confidently mapped from that infobox.
								</p>
							{/if}
						{:else if turn.kind === 'answer'}
							{#if turn.running}
								<ThinkingIndicator label="Searching the ontology" />
							{:else if turn.noMatch}
								<p class="text-sm">No confident match found in the ontology for that term.</p>
							{:else if turn.matches}
								<ul class="flex flex-wrap gap-1.5">
									{#each turn.matches as match (match.property)}
										<li class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm">
											<span class="font-mono">{match.property}</span>
											<ConfidencePill confidence={match.score} />
										</li>
									{/each}
								</ul>
							{/if}
						{/if}

						{#if turn.error}
							<p
								class="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm text-warning-foreground"
							>
								{turn.error}
							</p>
						{/if}
					</div>
				{/each}
			</div>
		{/if}
		<div bind:this={scrollAnchor}></div>
	</div>

	<div class="shrink-0 px-4 pb-4 md:px-8">
		<div class="rounded-2xl border bg-card shadow-sm">
			{#if targetClass}
				<div class="flex items-center gap-1.5 px-3 pt-2.5">
					<span class="text-xs text-muted-foreground">Target class:</span>
					<span
						class="rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground"
					>
						{targetClass}
					</span>
					<button
						type="button"
						class="text-xs text-muted-foreground hover:text-foreground"
						onclick={() => (targetClass = '')}
					>
						clear
					</button>
				</div>
			{/if}
			<div class="flex items-end gap-2 p-2">
				<Textarea
					bind:value={input}
					onkeydown={onKeydown}
					placeholder="Paste an infobox, or ask about a field…"
					rows={1}
					class="max-h-48 min-h-9 resize-none border-none bg-transparent px-2 py-1.5 shadow-none focus-visible:ring-0"
				/>
				<Button
					size="icon"
					class="mb-0.5 size-8 shrink-0 rounded-full"
					disabled={busy || !input.trim()}
					onclick={() => submit()}
					aria-label="Send"
				>
					<Fa icon={faArrowUp} class="size-3.5" />
				</Button>
			</div>
			{#if !targetClass}
				<div class="px-3 pb-2">
					<Input
						bind:value={targetClass}
						placeholder="Target class (optional, e.g. Bridge)"
						class="h-6 border-none bg-transparent px-0 text-xs shadow-none focus-visible:ring-0"
					/>
				</div>
			{/if}
		</div>
	</div>
</div>
