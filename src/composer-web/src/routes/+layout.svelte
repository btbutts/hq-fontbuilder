<script lang="ts">
	import { onMount } from 'svelte';
	import '../app.css';
	import { consoleStore } from '#lib/console.svelte.js';

	let { children } = $props();

	onMount(() => consoleStore.startPolling());
</script>

<div class="m-8 font-sans text-[15px]/[1.45] text-[#1c1c1e]">
	{@render children()}
</div>
