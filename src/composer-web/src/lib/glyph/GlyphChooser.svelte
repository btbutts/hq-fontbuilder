<script lang="ts">
	import { onMount } from 'svelte';
	import CtrlButton from '../button/CtrlButton.svelte';
	import GlyphCell from './GlyphCell.svelte';
	import { chooserGrid, type CellGeometry } from './glyphLayout';
	import { colors } from '../styles.svelte';
	import { unicodeNames } from '../data/unicodeNames.svelte';

	export interface Candidate {
		family: string;
		/** the family name the font file carries ("FiraMono Nerd Font"), shown under the glyph */
		label: string;
		/** CSS font-family name the family's reference style is loaded under */
		cssName: string;
		/** the family's colour: an entry of `colors.family` */
		color: string;
	}

	interface Props {
		codepoint: number;
		candidates: Candidate[];
		/** the family that currently draws the glyph */
		current: string;
		/** true when the user pinned the glyph, over the inheritance order */
		pinned: boolean;
		geometry: CellGeometry;
		/** the clicked cell: the pop-up stays next to it while the page scrolls */
		anchor: HTMLElement;
		onchoose: (family: string | null) => void;
		onclose: () => void;
	}

	let { codepoint, candidates, current, pinned, geometry, anchor, onchoose, onclose }: Props =
		$props();

	// Every tile is the same size, whatever the length of the family name under the glyph.
	const TILE_WIDTH = 136;
	const TILE_GAP = 8;
	const PADDING = 12;
	const MIN_WIDTH = 288;
	const ROW_HEIGHT = 150;
	const HEADER_HEIGHT = 64;
	const RESET_HEIGHT = 44;

	const code = $derived(codepoint.toString(16).toUpperCase().padStart(4, '0'));
	const name = $derived(unicodeNames.nameOf(codepoint));
	const grid = $derived(chooserGrid(candidates.length));
	const width = $derived(
		Math.max(MIN_WIDTH, grid.columns * TILE_WIDTH + (grid.columns - 1) * TILE_GAP + 2 * PADDING + 2)
	);
	const height = $derived(
		HEADER_HEIGHT + grid.rows * ROW_HEIGHT + (pinned ? RESET_HEIGHT : 0) + 2 * PADDING
	);

	const GAP = 6;
	const MARGIN = 8;

	// The pop-up is placed in document coordinates, so the browser scrolls it with the page
	// by itself; a scroll of anything inside the page (the sideways scroll of the glyph
	// grid) measures the cell again. It opens below the cell, or above when there is no room,
	// and keeps that side while the page moves.
	let place = $state({ left: 0, top: 0 });
	let below = true;
	let dialog = $state<HTMLElement | null>(null);

	function measure(): void {
		if (!anchor.isConnected) return;
		const rect = anchor.getBoundingClientRect();
		const viewportLeft = Math.max(
			MARGIN,
			Math.min(rect.left, globalThis.innerWidth - width - MARGIN)
		);
		place = {
			left: viewportLeft + globalThis.scrollX,
			top: (below ? rect.bottom + GAP : rect.top - height - GAP) + globalThis.scrollY
		};
	}

	onMount(() => {
		const rect = anchor.getBoundingClientRect();
		below = rect.bottom + height + GAP < globalThis.innerHeight || rect.top - height - GAP < MARGIN;
		measure();
	});

	$effect(() => {
		measure(); // reads width and height, so it also runs again when they change
		globalThis.addEventListener('scroll', measure, { capture: true, passive: true });
		globalThis.addEventListener('resize', measure);
		return () => {
			globalThis.removeEventListener('scroll', measure, { capture: true });
			globalThis.removeEventListener('resize', measure);
		};
	});

	// A press anywhere outside closes the pop-up and then goes on to whatever was pressed,
	// so a glyph can be clicked straight away to open its own pop-up.
	function pressed(event: PointerEvent): void {
		if (dialog && event.target instanceof Node && !dialog.contains(event.target)) onclose();
	}
</script>

<svelte:window
	onkeydown={(event) => event.key === 'Escape' && onclose()}
	onpointerdowncapture={pressed}
/>

<div
	bind:this={dialog}
	role="dialog"
	aria-label="Choose the glyph for U+{code}"
	class="absolute z-30 max-w-[96vw] rounded border p-3 {colors.border} {colors.popoverBackground} {colors.popoverShadow}"
	style:left="{place.left}px"
	style:top="{place.top}px"
	style:width="{width}px"
>
	{#if name}
		<p class="m-0 text-[0.95em] font-semibold {colors.textPrimary}">{name}</p>
	{/if}
	<p class="m-0 mb-2 text-[0.9em] {colors.textPrimary}">
		<span class="font-mono font-semibold">U+{code}</span> — which family draws this glyph?
	</p>
	<div
		class="grid auto-rows-fr justify-start gap-2"
		style:grid-template-columns="repeat({grid.columns}, {TILE_WIDTH}px)"
	>
		{#each candidates as candidate (candidate.family)}
			<CtrlButton
				surface="popover"
				padding="px-1.5 py-1.5"
				border={candidate.family === current
					? `border-2 ${colors.glyphChoiceCurrentBorder}`
					: `border ${colors.border}`}
				class="flex flex-col items-center text-center"
				tooltip={candidate.family === current ? `${candidate.label} draws it now` : candidate.label}
				onclick={() => onchoose(candidate.family)}
			>
				<GlyphCell
					{codepoint}
					present
					fontFamily={candidate.cssName}
					{geometry}
					accent={candidate.color}
					tooltip={false}
				/>
				<span class="mt-1 block text-[0.8em] leading-tight">
					{candidate.label}{candidate.family === current ? ' ✓' : ''}
				</span>
			</CtrlButton>
		{/each}
	</div>
	{#if pinned}
		<div class="mt-3 flex justify-center">
			<CtrlButton padding="px-2 py-1" fontSize="text-[0.85em]" onclick={() => onchoose(null)}>
				use the inheritance order again
			</CtrlButton>
		</div>
	{/if}
</div>
