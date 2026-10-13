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
		fontFamily: string;
		geometry: CellGeometry;
	}

	let { groupId, cells, mode, fontFamily, geometry }: Props = $props();

	const rows = $derived(layoutCells(groupId, cells, mode));
	const slot = $derived(slotWidth(geometry));
</script>

{#if mode === 'wrap'}
	<div class="flex flex-wrap gap-x-0.5 gap-y-3">
		{#each cells as cell (cell.codepoint)}
			<GlyphCell
				codepoint={cell.codepoint}
				present={cell.present}
				{fontFamily}
				{geometry}
			/>
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
						<GlyphCell
							codepoint={cell.codepoint}
							present={cell.present}
							{fontFamily}
							{geometry}
						/>
					{:else}
						<div class="shrink-0" style:width="{slot}px"></div>
					{/if}
				{/each}
			</div>
		{/each}
	</div>
{/if}
