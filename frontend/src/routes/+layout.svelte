<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';

	let { children } = $props();

	const links = [
		{ href: resolve('/'), label: 'Mapping Assistant' },
		{ href: resolve('/review'), label: 'Review Queue' },
		{ href: resolve('/coverage'), label: 'Coverage' }
	];
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<div class="min-h-screen bg-neutral-950 text-neutral-100">
	<header class="border-b border-neutral-800">
		<nav class="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
			<span class="font-semibold tracking-tight">agentic-amdbpedia</span>
			{#each links as link (link.href)}
				<a
					href={link.href}
					class={[
						'text-sm hover:text-neutral-100',
						page.url.pathname === link.href ? 'text-neutral-100' : 'text-neutral-400'
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
