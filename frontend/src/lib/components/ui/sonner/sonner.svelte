<script lang="ts">
	import { mode } from 'mode-watcher';
	import { Toaster as Sonner, type ToasterProps as SonnerProps } from 'svelte-sonner';

	let { ...restProps }: SonnerProps = $props();
</script>

<Sonner
	theme={mode.current}
	class="toaster group"
	style="--normal-bg: var(--popover); --normal-text: var(--popover-foreground); --normal-border: var(--border); --success-bg: var(--popover); --success-text: var(--success); --success-border: var(--success); --error-bg: var(--popover); --error-text: var(--destructive); --error-border: var(--destructive); --border-radius: var(--radius-lg);"
	toastOptions={{ class: 'shadow-lg font-medium' }}
	{...restProps}
/>
