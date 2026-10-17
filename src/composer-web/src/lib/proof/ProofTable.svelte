<script lang="ts">
	import type { ProofFont } from '../data/api.ts';
	import { edgeRules, glyphTransform, textFontSize, type PixelCell } from './cellGrid.ts';

	interface Props {
		lines: string[];
		font: ProofFont;
		/** the CSS font-family the font was installed under */
		family: string;
		/** the cell, in whole device pixels */
		cell: PixelCell;
		dpr: number;
		showEdges: boolean;
		/** draw with the browser's text renderer instead of the exact outlines */
		useText: boolean;
	}

	let { lines, font, family, cell, dpr, showEdges, useText }: Props = $props();

	const rows = $derived(lines.map((line) => [...line]));
	const columns = $derived(Math.max(0, ...rows.map((row) => row.length)));
	const width = $derived((columns * cell.w) / dpr);
	const height = $derived((rows.length * cell.h) / dpr);
	const rules = $derived(edgeRules(columns, rows.length, cell, dpr));
	const textSize = $derived(textFontSize(cell.w, dpr, font.cell));

	const glyphs = $derived(
		rows.flatMap((row, rowIndex) =>
			row.flatMap((char, column) => {
				const outline = font.outlines[String(char.codePointAt(0))];
				if (outline === undefined) return [];
				const place = glyphTransform(column, rowIndex, cell, font.units, dpr);
				return [
					{
						path: outline,
						transform: `translate(${place.x} ${place.baseline}) scale(${place.sx} ${-place.sy})`
					}
				];
			})
		)
	);
</script>

<!--
	A table drawn in cells of whole device pixels. By default each glyph is its outline from the
	written font, scaled so that its advance and its line height are exactly the cell: a table
	then joins wherever the font's glyphs do. With `useText` the browser draws the font as text
	instead, which at some sizes shows a hairline at the cell edges that is its own
	anti-aliasing and not the font.
-->
<div class="relative" style="width: {width}px; height: {height}px">
	{#if useText}
		<pre
			class="m-0"
			style="font-family: {family}; font-size: {textSize}px; line-height: {cell.h /
				dpr}px; letter-spacing: 0; font-kerning: none; font-variant-ligatures: none;">{lines.join(
				'\n'
			)}</pre>
	{:else}
		<svg {width} {height} class="block overflow-visible" aria-hidden="true">
			{#each glyphs as glyph, index (index)}
				<path d={glyph.path} transform={glyph.transform} fill="currentColor" />
			{/each}
		</svg>
	{/if}
	{#if showEdges}
		<svg {width} {height} class="pointer-events-none absolute top-0 left-0 overflow-visible" aria-hidden="true">
			{#each rules.vertical as x (x)}
				<rect {x} y="0" width={rules.thickness} {height} fill="#d63030" fill-opacity="0.6" shape-rendering="crispEdges" />
			{/each}
			{#each rules.horizontal as y (y)}
				<rect x="0" {y} {width} height={rules.thickness} fill="#d63030" fill-opacity="0.6" shape-rendering="crispEdges" />
			{/each}
		</svg>
	{/if}
</div>
