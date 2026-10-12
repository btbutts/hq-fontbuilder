<script lang="ts">
	interface Props {
		codepoint: number;
		fontFamily: string;
	}

	let { codepoint, fontFamily }: Props = $props();
</script>

<!--
	One glyph drawn at the base family's cell size. The zero-width ::before strut
	(height = ascent, baseline-aligned) pins the baseline; the dashed red line and
	the cell border make overflow and misalignment visible. Glyphs the font has no
	cmap entry for render as the browser's .notdef box — itself a useful signal.
-->
<span
	class="relative inline-block h-[calc(var(--cell-h)*1em)] w-[calc(var(--cell-w)*1em)] overflow-visible border border-[#b9b9bd] bg-white align-top leading-[0] before:inline-block before:h-[calc(var(--ascent)*1em)] before:w-0 before:align-baseline before:content-['']"
>
	<span class="align-baseline leading-[0]" style:font-family={fontFamily}
		>{String.fromCodePoint(codepoint)}</span
	>
	<span
		class="pointer-events-none absolute -right-0.5 -left-0.5 top-[calc(var(--ascent)*1em)] border-t border-dashed border-[#d24a4a]"
	></span>
	<span
		class="pointer-events-none absolute left-0 top-[calc(100%_+_1px)] font-mono text-[9px] leading-normal text-[#999]"
		>U+{codepoint.toString(16).toUpperCase().padStart(4, '0')}</span
	>
</span>
