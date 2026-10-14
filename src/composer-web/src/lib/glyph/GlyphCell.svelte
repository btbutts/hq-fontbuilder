<script lang="ts">
	import type { FitInfo } from '../data/api';
	import { describeFit } from './fitDisplay';
	import { slotWidth, type CellGeometry } from './glyphLayout';
	import { colors } from '../styles.svelte';
	import { tip } from '../tooltip/tooltip';
	import { unicodeNames } from '../data/unicodeNames.svelte';

	interface Props {
		codepoint: number;
		fontFamily: string;
		/** false when the font has no glyph for the code point: nothing is drawn */
		present: boolean;
		geometry: CellGeometry;
		/**
		 * colour of the family the glyph is taken from (an entry of `colors.family`: a text
		 * colour class); drawn as a bar under the cell and as the edge of the markers
		 */
		accent?: string;
		/** pinned by the user over the inheritance order (filled dot) */
		pinned?: boolean;
		/** more than one family could draw it (ring), so the cell can be clicked */
		choosable?: boolean;
		/** how the glyph relates to the base cell; ink that is cut off outlines the cell red */
		fit?: FitInfo;
		/** draw the glyph as it will be fitted (the correction applied) */
		showFitted?: boolean;
		/** an extra line for the tooltip (e.g. that the cell can be clicked) */
		hint?: string;
	}

	let {
		codepoint,
		fontFamily,
		present,
		geometry,
		accent,
		pinned,
		choosable,
		fit,
		showFitted = false,
		hint
	}: Props = $props();

	const width = $derived(Math.round(geometry.cellW * geometry.emPx));
	const height = $derived(Math.round(geometry.cellH * geometry.emPx));
	const baseline = $derived(geometry.ascent * geometry.emPx);
	const slot = $derived(slotWidth(geometry));
	// red only for the original outline of a glyph the cell cuts off
	const cutOff = $derived(fit?.clipped === true && !showFitted);
	// a connector's deliberate overshoot is cut at the cell edge in the fitted view
	const cutAtCell = $derived(showFitted && fit?.clip === true);
	// x' = sx*x + dx, y' = sy*y + dy (em, y up) as an SVG matrix about the text origin
	const matrix = $derived(
		showFitted && fit
			? `matrix(${fit.sx} 0 0 ${fit.sy} ${fit.dx * geometry.emPx} ${(1 - fit.sy) * baseline - fit.dy * geometry.emPx})`
			: undefined
	);
	const code = $derived(`U+${codepoint.toString(16).toUpperCase().padStart(4, '0')}`);
	const name = $derived(unicodeNames.nameOf(codepoint));
	const tipLines = $derived(
		[
			name ? code : null,
			present ? null : 'no glyph in this font',
			present ? describeFit(fit, showFitted) : null,
			hint ?? null
		]
			.filter((line): line is string => line !== null)
			.join('\n')
	);
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
	{...tip(name ?? code, tipLines)}
>
	<svg
		{width}
		{height}
		viewBox="0 0 {width} {height}"
		class="block {cutAtCell ? 'overflow-hidden' : 'overflow-visible'} {present
			? colors.glyphBoxBackground
			: colors.glyphBoxMissing}"
		role="img"
		aria-label="U+{codepoint.toString(16).toUpperCase().padStart(4, '0')}"
	>
		{#if present}
			<text
				x="0"
				y={baseline}
				font-family={fontFamily}
				font-size={geometry.emPx}
				class={colors.glyphInk}
				transform={matrix}
				style="font-variant-ligatures: none; font-kerning: none"
				>{String.fromCodePoint(codepoint)}</text
			>
		{/if}
		<line
			x1="-3"
			x2={width + 3}
			y1={baseline}
			y2={baseline}
			class={colors.glyphBaselineAccent}
			stroke-width="1"
			stroke-dasharray="3 2"
		/>
		<rect
			x="0.5"
			y="0.5"
			width={width - 1}
			height={height - 1}
			fill="none"
			class={cutOff ? colors.glyphBoxClippedOutline : colors.glyphBoxOutline}
			stroke-width={cutOff ? 2 : 1}
		/>
		{#if pinned}
			<circle cx={width - 6} cy="6" r="3.5" class="fill-current {accent ?? colors.textAccent1}" />
		{:else if choosable}
			<circle
				cx={width - 6}
				cy="6"
				r="3"
				class="stroke-current {accent ?? colors.textAccent1} {colors.glyphMarkerRingFill}"
				stroke-width="1.5"
			/>
		{/if}
	</svg>
	<span
		class="mt-0.5 h-0.75 rounded-sm {accent ? `bg-current ${accent}` : ''}"
		style:width="{width}px"
	></span>
	<span class="mt-1 font-mono text-[10px] leading-none whitespace-nowrap {colors.textTertiary}"
		>U+{codepoint.toString(16).toUpperCase().padStart(4, '0')}</span
	>
</div>
