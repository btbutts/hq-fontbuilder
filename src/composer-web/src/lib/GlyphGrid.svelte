<script lang="ts">
	import GlyphCell from './GlyphCell.svelte';
	import {
		layoutCells,
		slotWidth,
		type CellGeometry,
		type LayoutCell,
		type LayoutMode
	} from './glyphLayout';

	interface Props {
		groupId: string;
		cells: LayoutCell[];
		mode: LayoutMode;
		/** font family for cells that do not carry their own */
		fontFamily: string;
		geometry: CellGeometry;
		/** called with the cell and its element when a choosable cell is clicked */
		onpick?: (cell: LayoutCell, element: HTMLElement) => void;
	}

	let { groupId, cells, mode, fontFamily, geometry, onpick }: Props = $props();

	const rows = $derived(layoutCells(groupId, cells, mode));
	const slot = $derived(slotWidth(geometry));
</script>

{#snippet cellView(cell: LayoutCell)}
	{#if onpick && (cell.alternatives ?? 0) > 1}
		<button
			type="button"
			class="shrink-0 cursor-pointer rounded border-0 bg-transparent p-0 hover:bg-[#eef3f7] focus-visible:outline-2 focus-visible:outline-[#1b4965]"
			title="U+{cell.codepoint.toString(16).toUpperCase().padStart(4, '0')}: {cell.alternatives} families have this glyph — click to choose"
			onclick={(event) => onpick(cell, event.currentTarget)}
		>
			<GlyphCell
				codepoint={cell.codepoint}
				present={cell.present}
				fontFamily={cell.fontFamily ?? fontFamily}
				{geometry}
				accent={cell.accent}
				pinned={cell.pinned}
				choosable
			/>
		</button>
	{:else}
		<GlyphCell
			codepoint={cell.codepoint}
			present={cell.present}
			fontFamily={cell.fontFamily ?? fontFamily}
			{geometry}
			accent={cell.accent}
			pinned={cell.pinned}
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
					class="shrink-0 pr-2 pt-1 text-right font-mono text-[11px] whitespace-nowrap text-[#555]"
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
