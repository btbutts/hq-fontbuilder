<script lang="ts">
	import CtrlButton from '../button/CtrlButton.svelte';
	import GlyphCell from './GlyphCell.svelte';
	import {
		layoutCells,
		slotWidth,
		type CellGeometry,
		type LayoutCell,
		type LayoutMode
	} from './glyphLayout.ts';
	import { colors } from '../styles.svelte.ts';
	import type { NamedRow } from '../data/api.ts';

	interface Props {
		/** rows of the group that are not 16 wide */
		namedRows: readonly NamedRow[];
		cells: LayoutCell[];
		mode: LayoutMode;
		/** font family for cells that do not carry their own */
		fontFamily: string;
		geometry: CellGeometry;
		/** draw glyphs with their fit applied, where they have one */
		showFitted?: boolean;
		/** called with the cell and its element when a choosable cell is clicked */
		onpick?: (cell: LayoutCell, element: HTMLElement) => void;
	}

	let { namedRows, cells, mode, fontFamily, geometry, showFitted = false, onpick }: Props = $props();

	const rows = $derived(layoutCells(namedRows, cells, mode));
	const slot = $derived(slotWidth(geometry));
</script>

{#snippet cellView(cell: LayoutCell)}
	{#if onpick && (cell.alternatives ?? 0) > 1}
		<CtrlButton
			surface="bare"
			padding="p-0"
			class="shrink-0 focus-visible:outline-2 {colors.focusOutline}"
			onclick={(event) => onpick(cell, event.currentTarget)}
		>
			<GlyphCell
				codepoint={cell.codepoint}
				present={cell.present}
				fontFamily={cell.fontFamily ?? fontFamily}
				{geometry}
				accent={cell.accent}
				pinned={cell.pinned}
				fit={cell.fit}
				{showFitted}
				hint="{cell.alternatives} families have this glyph: click to choose"
				choosable
			/>
		</CtrlButton>
	{:else}
		<GlyphCell
			codepoint={cell.codepoint}
			present={cell.present}
			fontFamily={cell.fontFamily ?? fontFamily}
			{geometry}
			accent={cell.accent}
			pinned={cell.pinned}
			fit={cell.fit}
			{showFitted}
		/>
	{/if}
{/snippet}

{#if mode === 'wrap'}
	<div class="flex flex-wrap gap-x-0.5 gap-y-3">
		{#each cells as cell (cell.codepoint)}
			{@render cellView(cell)}
		{/each}
	</div>
{:else}
	<!-- never wraps: the scroll container of the page scrolls sideways instead -->
	<div class="flex flex-col gap-y-3">
		{#each rows as row (row.label)}
			<div class="flex flex-nowrap items-start gap-x-0.5">
				<span
					class="shrink-0 pr-2 pt-1 text-right font-mono text-[11px] whitespace-nowrap {colors.textSecondary}"
					style:width="64px"
				>
					{row.label}
				</span>
				{#each row.cells as cell, column (column)}
					{#if cell}
						{@render cellView(cell)}
					{:else}
						<div class="shrink-0" style:width="{slot}px"></div>
					{/if}
				{/each}
			</div>
		{/each}
	</div>
{/if}
