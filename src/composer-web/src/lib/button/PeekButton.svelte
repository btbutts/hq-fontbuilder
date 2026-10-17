<script lang="ts">
	import IconArrowBadgeDown from '@tabler/icons-svelte/icons/arrow-badge-down-filled';
	import IconArrowBadgeRight from '@tabler/icons-svelte/icons/arrow-badge-right-filled';
	import { tick, type Snippet } from 'svelte';
	import { colors } from '../styles.svelte.ts';

	/**
	 * A line of text with an arrow before it that opens and closes the element it controls.
	 *
	 *     <PeekButton bind:open controls="notes">What the table shows</PeekButton>
	 *     <div id="notes" inert={!open}>...</div>
	 *
	 * The button only holds the state and the arrow; the controlled element shows and hides
	 * itself from `open` (give its transition the same 200 ms as `TURN_MS`).
	 */
	interface Props {
		/** whether the controlled element is open; flips at the start of the arrow's turn */
		open?: boolean;
		/** id of the controlled element */
		controls: string;
		children: Snippet;
	}

	let { open = $bindable(false), controls, children }: Props = $props();

	const TURN_MS = 200;

	// `arrow` follows `open` once the turn has finished: right turns clockwise into down,
	// down turns counter-clockwise back into right.
	let arrow = $state<'right' | 'down'>(open ? 'down' : 'right');
	let arrowEl = $state<HTMLElement>();
	let turning = false;

	async function peek(): Promise<void> {
		if (turning) return;
		turning = true;
		const opening = !open;
		open = opening;
		const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
		const turn = arrowEl?.animate(
			{ rotate: ['0deg', opening ? '90deg' : '-90deg'] },
			{ duration: reduceMotion ? 0 : TURN_MS, easing: 'ease-out', fill: 'forwards' }
		);
		try {
			await turn?.finished;
			arrow = opening ? 'down' : 'right';
			await tick();
		} finally {
			turn?.cancel();
			turning = false;
		}
	}
</script>

<button
	type="button"
	class="group flex cursor-pointer items-start gap-1 border-0 bg-transparent p-0 text-left"
	aria-expanded={open}
	aria-controls={controls}
	onclick={peek}
>
	<span
		bind:this={arrowEl}
		class="inline-flex h-[1lh] shrink-0 items-center transition-colors duration-150 {colors.disclosureIcon.rest} {colors.disclosureIcon.hover}"
	>
		{#if arrow === 'down'}
			<IconArrowBadgeDown size="1.25em" />
		{:else}
			<IconArrowBadgeRight size="1.25em" />
		{/if}
	</span>
	<span>{@render children()}</span>
</button>
