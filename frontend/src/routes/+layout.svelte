<script lang="ts">
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import { ModeWatcher } from 'mode-watcher';
	import { Toaster } from '$lib/components/ui/sonner/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import AppSidebar from '$lib/components/AppSidebar.svelte';
	import ModeToggle from '$lib/components/ModeToggle.svelte';
	import MenuIcon from '@lucide/svelte/icons/menu';

	let { children } = $props();

	let sidebarOpen = $state(false);
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<ModeWatcher />
<Toaster richColors position="top-center" />

<div class="flex min-h-svh">
	<AppSidebar bind:open={sidebarOpen} />

	<div class="flex min-w-0 flex-1 flex-col">
		<header
			class="sticky top-0 z-20 flex items-center gap-2 border-b bg-background/80 px-3 py-2 backdrop-blur md:px-6"
		>
			<Button
				variant="ghost"
				size="icon"
				class="size-8 md:hidden"
				onclick={() => (sidebarOpen = !sidebarOpen)}
				aria-label="Toggle sidebar"
			>
				<MenuIcon class="size-4" />
			</Button>
			<div class="flex-1"></div>
			<ModeToggle />
		</header>
		<main class="mx-auto w-full max-w-5xl flex-1 px-4 py-6 md:px-8 md:py-10">
			{@render children()}
		</main>
	</div>
</div>
