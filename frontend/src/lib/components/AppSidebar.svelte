<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { cn } from '$lib/utils.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import SquarePenIcon from '@lucide/svelte/icons/square-pen';
	import SparklesIcon from '@lucide/svelte/icons/sparkles';
	import ListChecksIcon from '@lucide/svelte/icons/list-checks';
	import BarChart3Icon from '@lucide/svelte/icons/bar-chart-3';
	import ExternalLinkIcon from '@lucide/svelte/icons/external-link';

	let { open = $bindable(true) }: { open?: boolean } = $props();

	const links = [
		{ href: resolve('/'), label: 'Mapping Assistant', icon: SparklesIcon },
		{ href: resolve('/review'), label: 'Review Queue', icon: ListChecksIcon },
		{ href: resolve('/coverage'), label: 'Coverage', icon: BarChart3Icon }
	];
</script>

{#if open}
	<button
		type="button"
		class="fixed inset-0 z-30 bg-black/50 md:hidden"
		onclick={() => (open = false)}
		aria-label="Close sidebar"
	></button>
{/if}

<aside
	class={cn(
		'fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground transition-transform md:sticky md:top-0 md:h-svh md:translate-x-0',
		open ? 'translate-x-0' : '-translate-x-full'
	)}
>
	<div class="flex items-center justify-between gap-2 p-3">
		<a href={resolve('/')} class="flex items-center gap-2 rounded-md px-2 py-1.5 font-semibold">
			<span
				class="flex size-6 items-center justify-center rounded-md bg-primary text-xs text-primary-foreground"
			>
				AM
			</span>
			agentic-amdbpedia
		</a>
		<Button
			variant="ghost"
			size="icon"
			class="size-7"
			href={resolve('/')}
			title="New mapping"
			aria-label="New mapping"
		>
			<SquarePenIcon class="size-4" />
		</Button>
	</div>

	<Separator />

	<nav class="flex-1 space-y-1 overflow-y-auto p-2">
		{#each links as link (link.href)}
			{@const active = page.url.pathname === link.href}
			<a
				href={link.href}
				onclick={() => (open = false)}
				class={cn(
					'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
					active
						? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
						: 'text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground'
				)}
			>
				<link.icon class="size-4 shrink-0" />
				{link.label}
			</a>
		{/each}
	</nav>

	<Separator />

	<div class="p-3">
		<a
			href="https://github.com/vercel/ai-chatbot-svelte"
			target="_blank"
			rel="noreferrer"
			class="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-sidebar-foreground/60 hover:text-sidebar-foreground"
		>
			<ExternalLinkIcon class="size-3.5" />
			UI inspired by ai-chatbot-svelte
		</a>
	</div>
</aside>
