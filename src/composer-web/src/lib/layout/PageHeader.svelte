<script lang="ts">
	import type { Snippet } from 'svelte';
	import { colors } from '../styles.svelte.ts';

	interface Props {
		children: Snippet;
	}

	let { children }: Props = $props();
</script>

<!--
	The darker band at the top of a sub page: it reaches both edges of the viewport and the top
	of it (the layout's margin is pulled back in), and it is the same colour as the StickyBar
	that follows it, so the two read as one block until the bar sticks.
-->
<header
	class="-mx-(--page-gutter) -mt-(--page-gutter) px-(--page-gutter) pt-(--page-gutter) pb-4 {colors.bandBackground}"
>
	{@render children()}
</header>
