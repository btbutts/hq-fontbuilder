<script lang="ts">
	import { colors } from '../styles.svelte.ts';

	interface Props {
		label?: string;
	}

	let { label = 'Loading Fonts' }: Props = $props();

	// Fonts that arrive at once are never preceded by a flash of the loader.
	const SHOW_AFTER_MS = 150;
	let shown = $state(false);

	$effect(() => {
		const timer = setTimeout(() => (shown = true), SHOW_AFTER_MS);
		return () => clearTimeout(timer);
	});

	// Fills the viewport from this element's top to its bottom edge; the layout's bottom
	// margin is pulled back so that the page does not scroll.
	let root = $state<HTMLElement>();
	let height = $state(0);

	function measure(): void {
		if (root) height = Math.max(0, Math.floor(globalThis.innerHeight - root.getBoundingClientRect().top));
	}

	$effect(() => {
		measure();
		globalThis.addEventListener('resize', measure);
		return () => globalThis.removeEventListener('resize', measure);
	});
</script>

<div
	bind:this={root}
	role="status"
	class="-mb-(--page-gutter) flex flex-col items-center justify-center gap-3 {colors.textSecondary}"
	style:height="{height}px"
>
	{#if shown}
		<div class="font-loader" aria-hidden="true"></div>
		<span class="text-[0.9em]">{label}</span>
	{/if}
</div>

<style>
	/* three dots that bounce one after the other, then rest before the next round */
	.font-loader {
		width: 60px;
		aspect-ratio: 2;
		--dot: no-repeat radial-gradient(circle closest-side, currentColor 90%, #0000);
		background:
			var(--dot) 0% 50%,
			var(--dot) 50% 50%,
			var(--dot) 100% 50%;
		background-size: calc(100% / 3) 50%;
		animation: bounce 1.5s infinite linear;
	}

	@keyframes bounce {
		0%,
		66.67%,
		100% {
			background-position: 0% 50%, 50% 50%, 100% 50%;
		}
		13.33% {
			background-position: 0% 0%, 50% 50%, 100% 50%;
		}
		26.67% {
			background-position: 0% 100%, 50% 0%, 100% 50%;
		}
		40% {
			background-position: 0% 50%, 50% 100%, 100% 0%;
		}
		53.33% {
			background-position: 0% 50%, 50% 50%, 100% 100%;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.font-loader {
			animation: none;
		}
	}
</style>
