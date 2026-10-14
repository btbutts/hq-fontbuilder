<script lang="ts">
	import type { Snippet } from 'svelte';
	import { colors } from '../styles.svelte';

	interface Props {
		children: Snippet;
	}

	let { children }: Props = $props();
</script>

<!-- The toolbar that stays at the top of the viewport: edge to edge, like the PageHeader. -->
<div
	class="sticky top-0 z-10 -mx-(--page-gutter) flex flex-wrap items-center gap-y-1 border-b px-(--page-gutter) py-2.5 {colors.border} {colors.bandBackground}"
>
	{@render children()}
</div>
