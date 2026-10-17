<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/state';
	import '../app.css';
	import {
		colors, consoleStore, Tooltip
	} from '#lib';

	let { children } = $props();

	// The page's background, text and colour scheme belong to <html>, so that they also
	// reach the area behind an overscrolled page and the browser's own widgets.
	const rootClasses = `${colors.pageBackground} ${colors.textPrimary} ${colors.colorScheme}`
		.split(' ')
		.filter((name) => name !== '');

	$effect.pre(() => {
		document.documentElement.classList.add(...rootClasses);
	});

	// the build proof is served without the console's API: nothing to poll there
	onMount(() => (page.url.pathname.startsWith('/buildProof') ? undefined : consoleStore.startPolling()));
</script>

<!-- --page-gutter is the margin round every page; PageHeader and StickyBar bleed into it. -->
<div class="m-(--page-gutter) font-sans text-[15px]/[1.45]" style="--page-gutter: 2rem">
	{@render children()}
</div>

<Tooltip />
