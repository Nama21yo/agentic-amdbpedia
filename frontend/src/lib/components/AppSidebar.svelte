<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { cn } from '$lib/utils.js';
	import { requestNewChat } from '$lib/chat.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import Fa from 'svelte-fa';
	import { faPlus, faListCheck, faChartSimple } from '@fortawesome/free-solid-svg-icons';

	let { open = $bindable(true) }: { open?: boolean } = $props();

	const links = [
		{ href: resolve('/review'), label: 'Review Queue', icon: faListCheck },
		{ href: resolve('/coverage'), label: 'Coverage', icon: faChartSimple }
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
		'fixed inset-y-0 left-0 z-40 flex w-64 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground transition-transform md:relative md:translate-x-0',
		open ? 'translate-x-0' : '-translate-x-full'
	)}
>
	<div class="flex items-center gap-2 p-3">
		<span
			class="flex size-7 items-center justify-center rounded-lg bg-primary text-sm font-semibold text-primary-foreground"
		>
			አም
		</span>
		<span class="font-semibold tracking-tight">agentic-amdbpedia</span>
	</div>

	<div class="px-2">
		<Button
			variant="outline"
			class="w-full justify-start gap-2"
			href={resolve('/')}
			onclick={() => {
				requestNewChat();
				open = false;
			}}
		>
			<Fa icon={faPlus} class="size-3.5" />
			New chat
		</Button>
	</div>

	<Separator class="my-3" />

	<nav class="flex-1 space-y-1 px-2">
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
				<Fa icon={link.icon} class="size-3.5 shrink-0" />
				{link.label}
			</a>
		{/each}
	</nav>
</aside>
