<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import Toaster from '$lib/components/Toaster.svelte';

	let { children } = $props();

	const links = [
		{ href: resolve('/'), label: 'Mapping Assistant' },
		{ href: resolve('/review'), label: 'Review Queue' },
		{ href: resolve('/coverage'), label: 'Coverage' }
	];
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<Toaster />

<div class="min-h-screen bg-neutral-950 text-neutral-100">
	<header class="border-b border-neutral-800 bg-neutral-950/80 backdrop-blur">
		<nav class="mx-auto flex max-w-5xl items-center gap-1 px-6 py-4">
			<span class="mr-6 font-semibold tracking-tight">agentic-amdbpedia</span>
			{#each links as link (link.href)}
				{@const active = page.url.pathname === link.href}
				<a
					href={link.href}
					class={[
						'rounded-lg px-3 py-1.5 text-sm transition-colors',
						active
							? 'bg-neutral-900 text-neutral-100'
							: 'text-neutral-400 hover:bg-neutral-900/60 hover:text-neutral-100'
					]}
				>
					{link.label}
				</a>
			{/each}
		</nav>
	</header>
	<main class="mx-auto max-w-5xl px-6 py-8">
		{@render children()}
	</main>
</div>
