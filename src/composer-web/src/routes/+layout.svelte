<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import { consoleStore } from '#lib/data/console.svelte.js';
	import { colors } from '#lib/styles.svelte.js';
	import Tooltip from '#lib/tooltip/Tooltip.svelte';

	let { children } = $props();

	// The page's background, text and colour scheme belong to <html>, so that they also
	// reach the area behind an overscrolled page and the browser's own widgets.
	const rootClasses = `${colors.pageBackground} ${colors.textPrimary} ${colors.colorScheme}`
		.split(' ')
		.filter((name) => name !== '');

	$effect.pre(() => {
		document.documentElement.classList.add(...rootClasses);
	});

	onMount(() => consoleStore.startPolling());
</script>

<!-- --page-gutter is the margin round every page; PageHeader and StickyBar bleed into it. -->
<div class="m-(--page-gutter) font-sans text-[15px]/[1.45]" style="--page-gutter: 2rem">
	{@render children()}
</div>

<Tooltip />
