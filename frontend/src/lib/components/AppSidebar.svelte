<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { cn } from '$lib/utils.js';
	import { sessions, active, startNewChat, selectSession, deleteSession } from '$lib/chat.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import logo from '$lib/assets/dbpedia-am-logo.png';
	import Fa from 'svelte-fa';
	import { faPlus, faListCheck, faChartSimple, faTrash } from '@fortawesome/free-solid-svg-icons';

	let { open = $bindable(true) }: { open?: boolean } = $props();

	const links = [
		{ href: resolve('/review'), label: 'Review Queue', icon: faListCheck },
		{ href: resolve('/coverage'), label: 'Coverage', icon: faChartSimple }
	];

	const isChatRoute = $derived(page.url.pathname === resolve('/'));

	function relativeTime(ms: number): string {
		const diff = Date.now() - ms;
		const minute = 60_000;
		const hour = 60 * minute;
		const day = 24 * hour;
		if (diff < minute) return 'just now';
		if (diff < hour) return `${Math.floor(diff / minute)}m ago`;
		if (diff < day) return `${Math.floor(diff / hour)}h ago`;
		if (diff < 7 * day) return `${Math.floor(diff / day)}d ago`;
		return new Date(ms).toLocaleDateString();
	}
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
		'fixed inset-y-0 left-0 z-40 flex w-72 shrink-0 flex-col border-r bg-sidebar text-sidebar-foreground transition-transform md:relative md:translate-x-0',
		open ? 'translate-x-0' : '-translate-x-full'
	)}
>
	<div class="flex items-center gap-2.5 p-3.5">
		<img src={logo} alt="Amharic DBpedia" class="size-8 shrink-0 object-contain" />
		<div class="min-w-0">
			<p class="truncate text-sm font-semibold tracking-tight">agentic-amdbpedia</p>
			<p class="truncate text-xs text-sidebar-foreground/55">Amharic → DBpedia mapping</p>
		</div>
	</div>

	<div class="px-2.5">
		<Button
			variant="outline"
			class="w-full justify-start gap-2 bg-transparent"
			href={resolve('/')}
			onclick={() => {
				startNewChat();
				open = false;
			}}
		>
			<Fa icon={faPlus} class="size-3.5" />
			New chat
		</Button>
	</div>

	<Separator class="my-3" />

	<nav class="space-y-1 px-2.5">
		{#each links as link (link.href)}
			{@const isActive = page.url.pathname === link.href}
			<a
				href={link.href}
				onclick={() => (open = false)}
				class={cn(
					'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
					isActive
						? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
						: 'text-sidebar-foreground/80 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground'
				)}
			>
				<Fa icon={link.icon} class="size-3.5 shrink-0" />
				{link.label}
			</a>
		{/each}
	</nav>

	{#if sessions.length > 0}
		<Separator class="my-3" />

		<p class="px-4 pb-1.5 text-xs font-medium tracking-wide text-sidebar-foreground/50 uppercase">
			Chats
		</p>
		<div class="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2.5 pb-3">
			{#each sessions as session (session.id)}
				{@const isActive = isChatRoute && active.id === session.id}
				<div
					class={cn(
						'group flex items-center rounded-md',
						isActive
							? 'bg-sidebar-accent text-sidebar-accent-foreground'
							: 'hover:bg-sidebar-accent/60'
					)}
				>
					<a
						href={resolve('/')}
						onclick={() => {
							selectSession(session.id);
							open = false;
						}}
						class="min-w-0 flex-1 px-2.5 py-2 text-sm"
					>
						<p class="truncate">{session.title}</p>
						<p class="text-xs text-sidebar-foreground/45">{relativeTime(session.updatedAt)}</p>
					</a>
					<button
						type="button"
						class="mr-1.5 shrink-0 rounded p-1.5 text-sidebar-foreground/40 opacity-0 group-hover:opacity-100 hover:text-destructive"
						onclick={() => deleteSession(session.id)}
						aria-label="Delete chat"
						title="Delete chat"
					>
						<Fa icon={faTrash} class="size-3" />
					</button>
				</div>
			{/each}
		</div>
	{:else}
		<div class="flex-1"></div>
	{/if}
</aside>
