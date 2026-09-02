<script lang="ts">
	import type { ReviewStatus } from '$lib/types';

	let { status }: { status: ReviewStatus } = $props();

	const styles: Record<ReviewStatus, string> = {
		pending_review: 'border-amber-800 bg-amber-950/50 text-amber-300',
		approved: 'border-emerald-800 bg-emerald-950/50 text-emerald-300',
		rejected: 'border-red-800 bg-red-950/50 text-red-300',
		published: 'border-sky-800 bg-sky-950/50 text-sky-300'
	};

	const labels: Record<ReviewStatus, string> = {
		pending_review: 'Pending review',
		approved: 'Approved',
		rejected: 'Rejected',
		published: 'Published'
	};
</script>

<span
	class={[
		'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
		styles[status]
	]}
>
	{labels[status]}
</span>
