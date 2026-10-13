<script lang="ts">
	import { slotWidth, type CellGeometry } from './glyphLayout';

	interface Props {
		codepoint: number;
		fontFamily: string;
		/** false when the font has no glyph for the code point: nothing is drawn */
		present: boolean;
		geometry: CellGeometry;
		/** colour of the family the glyph is taken from; drawn as a bar under the cell */
		accent?: string;
		/** pinned by the user over the inheritance order (filled dot) */
		pinned?: boolean;
		/** more than one family could draw it (ring), so the cell can be clicked */
		choosable?: boolean;
	}

	let { codepoint, fontFamily, present, geometry, accent, pinned, choosable }: Props = $props();

	const width = $derived(Math.round(geometry.cellW * geometry.emPx));
	const height = $derived(Math.round(geometry.cellH * geometry.emPx));
	const baseline = $derived(geometry.ascent * geometry.emPx);
	const slot = $derived(slotWidth(geometry));
</script>

<!--
	One glyph in the base family's cell, drawn as SVG so that the baseline is exactly
	where it is meant to be: an SVG <text> puts its baseline at `y`, whatever the font's
	own ascent and descent are. (The earlier HTML version let the browser's line layout
	place the baseline, and that depends on each donor font's metrics, so glyphs of some
	families sat well below the cell.) The cell border is the cell a console would give
	the glyph; the dashed red line is the baseline, which is `ascent` of the base family
	from the top. The glyph origin is the cell's left edge, as in a terminal, so a donor
	whose advance differs from the cell visibly overflows. A code point the font has no
	glyph for is not drawn at all (a browser would fill it from some other font on the
	system, which would look like the donor had it) and is hatched.
-->
<div
	class="flex shrink-0 flex-col items-center"
	style:width="{slot}px"
	title={present ? undefined : 'no glyph in this font'}
>
	<svg
		{width}
		{height}
		viewBox="0 0 {width} {height}"
		class="block overflow-visible {present
			? 'bg-white'
			: 'bg-[repeating-linear-gradient(135deg,#f3f3f6_0_4px,#e2e2e8_4px_5px)]'}"
		role="img"
		aria-label="U+{codepoint.toString(16).toUpperCase().padStart(4, '0')}"
	>
		{#if present}
			<text
				x="0"
				y={baseline}
				font-family={fontFamily}
				font-size={geometry.emPx}
				fill="#1c1c1e"
				style="font-variant-ligatures: none; font-kerning: none"
				>{String.fromCodePoint(codepoint)}</text
			>
		{/if}
		<line
			x1="-3"
			x2={width + 3}
			y1={baseline}
			y2={baseline}
			stroke="#d24a4a"
			stroke-width="1"
			stroke-dasharray="3 2"
		/>
		<rect x="0.5" y="0.5" width={width - 1} height={height - 1} fill="none" stroke="#b9b9bd" />
		{#if pinned}
			<circle cx={width - 6} cy="6" r="3.5" fill={accent ?? '#1b4965'} />
		{:else if choosable}
			<circle
				cx={width - 6}
				cy="6"
				r="3"
				fill="white"
				stroke={accent ?? '#1b4965'}
				stroke-width="1.5"
			/>
		{/if}
	</svg>
	<span
		class="mt-0.5 h-[3px] rounded-sm"
		style:width="{width}px"
		style:background={accent ?? 'transparent'}
	></span>
	<span class="mt-1 font-mono text-[10px] leading-none whitespace-nowrap text-[#777]"
		>U+{codepoint.toString(16).toUpperCase().padStart(4, '0')}</span
	>
</div>
