<script lang="ts">
	import type { ReviewStatus } from '$lib/types';
	import { Badge, type BadgeVariant } from '$lib/components/ui/badge/index.js';

	let { status }: { status: ReviewStatus } = $props();

	const variants: Record<ReviewStatus, BadgeVariant> = {
		pending_review: 'warning',
		approved: 'success',
		rejected: 'destructive',
		published: 'default'
	};

	const labels: Record<ReviewStatus, string> = {
		pending_review: 'Pending review',
		approved: 'Approved',
		rejected: 'Rejected',
		published: 'Published'
	};
</script>

<Badge variant={variants[status]}>{labels[status]}</Badge>
