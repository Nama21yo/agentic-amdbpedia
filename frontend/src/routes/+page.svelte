<script lang="ts">
	import { resolve } from '$app/paths';
	import { toast } from 'svelte-sonner';
	import { BackendUnavailableError, findSemanticMatch, previewMapping } from '$lib/api';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Card, CardContent, CardHeader, CardTitle } from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
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
	import SendIcon from '@lucide/svelte/icons/send-horizontal';
	import LoaderCircleIcon from '@lucide/svelte/icons/loader-circle';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
	import BotIcon from '@lucide/svelte/icons/bot';
	import type { AgentStep, ChatMessage, PredictedMapping } from '$lib/types';

	let infobox = $state(`{{Infobox bridge\n| ስም = ...\n| ርዝመት = 1,700 ሜትር\n}}`);
	let targetClass = $state('');
	let steps = $state<AgentStep[]>([]);
	let mappings = $state<PredictedMapping[]>([]);
	let running = $state(false);
	let done = $state(false);

	async function runPreview() {
		if (!infobox.trim()) return;
		running = true;
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
			console.error('Mapping agent run failed:', err);
			toast.error(
				err instanceof BackendUnavailableError
					? 'cross-lingual is not reachable — check that the HTTP server (just run-http) is running.'
					: `Unexpected error while running the mapping agent: ${err instanceof Error ? err.message : String(err)}`
			);
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
			console.error('Assistant lookup failed:', err);
			const reply =
				err instanceof BackendUnavailableError
					? 'cross-lingual is not reachable yet — this answers live once its HTTP endpoint is implemented.'
					: `Unexpected error while asking the assistant: ${err instanceof Error ? err.message : String(err)}`;
			chatMessages = [...chatMessages, { role: 'assistant', content: reply }];
		} finally {
			chatBusy = false;
		}
	}
</script>

<div class="mb-8">
	<h1 class="text-2xl font-semibold tracking-tight">Mapping Assistant</h1>
	<p class="mt-1 text-sm text-muted-foreground">
		Paste an Amharic infobox and prepare a draft DBpedia mapping. Nothing here is published until a
		reviewer approves it — and opts in to publishing — on the
		<a href={resolve('/review')} class="text-primary underline underline-offset-4">Review Queue</a>.
	</p>
</div>

<div class="grid gap-6 lg:grid-cols-2">
	<Card>
		<CardHeader>
			<CardTitle>Prepare a mapping</CardTitle>
		</CardHeader>
		<CardContent class="flex flex-col gap-4">
			<div class="flex flex-col gap-1.5">
				<Label for="infobox">Infobox wikitext</Label>
				<Textarea id="infobox" bind:value={infobox} rows={10} class="font-mono text-sm" />
			</div>

			<div class="flex flex-col gap-1.5">
				<Label for="target-class">Target class (optional)</Label>
				<Input id="target-class" bind:value={targetClass} placeholder="e.g. Bridge" />
			</div>

			<Button onclick={runPreview} disabled={running || !infobox.trim()} class="self-start">
				{#if running}
					<LoaderCircleIcon class="animate-spin" />
					Running…
				{:else}
					<SendIcon />
					Prepare mapping
				{/if}
			</Button>

			<StepTracker {steps} {running} />

			{#if mappings.length > 0}
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
							{#each mappings as mapping (mapping.templateProperty)}
								<TableRow>
									<TableCell class="font-mono">{mapping.templateProperty}</TableCell>
									<TableCell class="font-mono">{mapping.ontologyProperty}</TableCell>
									<TableCell><ConfidencePill confidence={mapping.confidence} /></TableCell>
								</TableRow>
							{/each}
						</TableBody>
					</Table>
				</div>
				{#if done}
					<a
						href={resolve('/review')}
						class="flex items-center gap-2 rounded-lg border border-success/40 bg-success/10 px-3 py-2.5 text-sm font-medium text-success"
					>
						<CircleCheckIcon class="size-4 shrink-0" />
						Sent to the Review Queue — review and correct it now
						<ArrowRightIcon class="size-4 shrink-0" />
					</a>
				{/if}
			{/if}
		</CardContent>
	</Card>

	<Card class="flex flex-col">
		<CardHeader>
			<CardTitle>Ask the assistant</CardTitle>
			<p class="text-xs text-muted-foreground">
				Quick lookup against the same retrieval index — doesn't submit anything for review.
			</p>
		</CardHeader>
		<CardContent class="flex flex-1 flex-col gap-3">
			<div class="flex h-72 flex-col gap-3 overflow-y-auto rounded-lg border bg-muted/30 p-3">
				{#if chatMessages.length === 0}
					<div
						class="m-auto flex flex-col items-center gap-2 text-center text-sm text-muted-foreground"
					>
						<BotIcon class="size-8 opacity-40" />
						<p>e.g. "what about ቁመት instead?"</p>
					</div>
				{/if}
				{#each chatMessages as message, i (i)}
					<div class={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
						<div
							class={message.role === 'user'
								? 'max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3 py-2 text-sm text-primary-foreground'
								: 'max-w-[85%] rounded-2xl rounded-bl-sm border bg-background px-3 py-2 text-sm'}
						>
							{message.content}
						</div>
					</div>
				{/each}
				{#if chatBusy}
					<div class="flex justify-start">
						<div
							class="flex items-center gap-1.5 rounded-2xl rounded-bl-sm border bg-background px-3 py-2"
						>
							<LoaderCircleIcon class="size-3.5 animate-spin text-muted-foreground" />
						</div>
					</div>
				{/if}
			</div>
			<form
				class="flex gap-2"
				onsubmit={(event) => {
					event.preventDefault();
					askAssistant();
				}}
			>
				<Input bind:value={chatInput} placeholder="e.g. what about ቁመት instead?" class="flex-1" />
				<Button type="submit" size="icon" disabled={chatBusy || !chatInput.trim()}>
					<SendIcon class="size-4" />
				</Button>
			</form>
		</CardContent>
	</Card>
</div>
