<script lang="ts">
	import { onMount } from 'svelte';
	import {
		BLOCK_SAMPLES, cellWidths, colors, fetchProof, installFontFaces, PageHeader, pixelCell,
		PROOF_TABLES, ProofTable, Slider, StickyBar, ThemeToggle, Toggle,
		type ProofFont
	} from '#lib';

	const FACE_ELEMENT_ID = 'fc-proof-faces';
	/** em: a miss this large shows as a hairline gap at ordinary sizes (the build's limit) */
	const GAP_EM = 0.01;
	/** device pixels wide a cell starts at, per device pixel ratio */
	const START_CELL_CSS_PX = 15;

	let fonts = $state<ProofFont[]>([]);
	let loadError = $state<string | null>(null);
	let dpr = $state(1);
	let cellWidth = $state(START_CELL_CSS_PX);
	let showEdges = $state(false);
	let useText = $state(false);

	const widths = $derived(cellWidths(dpr));
	const baseCell = $derived(fonts[0]?.cell ?? { width: 0.6, ascent: 0.8, descent: -0.2 });
	const cell = $derived(pixelCell(cellWidth, baseCell));

	onMount(() => {
		const measure = () => {
			const next = window.devicePixelRatio || 1;
			if (next !== dpr) {
				cellWidth = Math.round((cellWidth / dpr) * next);
				dpr = next;
			}
		};
		dpr = window.devicePixelRatio || 1;
		cellWidth = Math.round(START_CELL_CSS_PX * dpr);
		window.addEventListener('resize', measure);
		fetchProof()
			.then((payload) => {
				fonts = payload.fonts;
				installFontFaces(
					FACE_ELEMENT_ID,
					payload.fonts
						.map(
							(font, index) =>
								`@font-face { font-family: "fc-proof-${index}"; src: url("${font.url}"); }`
						)
						.join('\n')
				);
			})
			.catch(() => {
				loadError =
					'This page shows the proof of a build. Start it with: python -m font_composer build --show-proof';
			});
		return () => window.removeEventListener('resize', measure);
	});

	function codepointLabel(codepoint: number): string {
		return `U+${codepoint.toString(16).toUpperCase().padStart(4, '0')}`;
	}
</script>

<svelte:head>
	<title>Build Proof</title>
</svelte:head>

<PageHeader>
	<div class="flex items-center justify-between gap-4">
		<h1 class="m-0 text-[1.6em] font-semibold">Build Proof</h1>
		<ThemeToggle />
	</div>
	<p class="mt-2 mb-0 max-w-5xl {colors.textSecondary}">
		Tables drawn with the box glyphs of the fonts the build just wrote. Where the glyphs of two
		neighbouring cells do not meet, a table shows a gap or a step. The build has also measured every
		line and reports the ones that miss each other below. Cells are a whole number of device pixels,
		as a console draws them; the browser's own text rendering shows hairlines between cells at sizes
		that are not (turn on Browser Text Rendering to see them).
	</p>
</PageHeader>

{#snippet sizeControl()}
	<span class="flex items-center gap-x-3">
		<span>Size</span>
		<Slider
			label="Cell size in device pixels"
			min={widths[0] ?? 8}
			max={widths.at(-1) ?? 48}
			bind:value={cellWidth}
		/>
		<span class="w-[8ch] {colors.textSecondary}">{cell.w}px × {cell.h}px</span>
	</span>
{/snippet}
{#snippet edgesToggle()}
	<Toggle
		label="Show Cell Edges"
		title="draw the edges of each character cell in red"
		checked={showEdges}
		onchange={(enabled) => (showEdges = enabled)}
	/>
{/snippet}
{#snippet textToggle()}
	<Toggle
		label="Browser Text Rendering"
		title="draw the tables as text with the browser's own renderer instead of the font's exact outlines; its anti-aliasing can show a hairline between cells that is not in the font"
		checked={useText}
		onchange={(enabled) => (useText = enabled)}
	/>
{/snippet}

<StickyBar>
	{#snippet full()}
		{@render sizeControl()}
		<span class="ml-auto flex items-center gap-x-6 pl-6">
			{@render edgesToggle()}
			{@render textToggle()}
		</span>
	{/snippet}
	{#snippet menu()}
		{@render sizeControl()}
		{@render edgesToggle()}
		{@render textToggle()}
	{/snippet}
</StickyBar>

<main class="py-6">
	{#if loadError}
		<p class="m-0 {colors.textError}">{loadError}</p>
	{:else if fonts.length === 0}
		<p class="m-0 {colors.textSecondary}">loading…</p>
	{/if}

	{#each fonts as font, index (font.file)}
		<section class="mb-10">
			<h2 class="m-0 text-[1.2em] font-semibold">
				{font.style} <span class="font-normal {colors.textSecondary}">— {font.file}</span>
			</h2>
			{#if font.seams.length === 0}
				<p class="mt-1 mb-0 {colors.textSecondary}">
					Every box line meets its neighbours (to within 0.002 em).
				</p>
			{:else}
				<ul class="mt-1 mb-0 pl-5">
					{#each font.seams as seam, seamIndex (seamIndex)}
						<li class={seam.spread > GAP_EM && !seam.soft ? colors.textError : colors.textSecondary}>
							{seam.spread.toFixed(3)} em apart:
							{#each seam.members as member, memberIndex (memberIndex)}
								{memberIndex > 0 ? ', ' : ''}{codepointLabel(member.codepoint)} ({member.edge})
							{/each}
						</li>
					{/each}
				</ul>
			{/if}
			<div class="mt-4 flex flex-wrap gap-x-10 gap-y-6">
				{#each PROOF_TABLES as table (table.title)}
					<figure class="m-0">
						<figcaption class="mb-1 text-[0.85em] {colors.textSecondary}">{table.title}</figcaption>
						<ProofTable
							lines={table.lines}
							{font}
							family={`fc-proof-${index}`}
							{cell}
							{dpr}
							{showEdges}
							{useText}
						/>
					</figure>
				{/each}
				<figure class="m-0">
					<figcaption class="mb-1 text-[0.85em] {colors.textSecondary}">Block elements</figcaption>
					<ProofTable
						lines={BLOCK_SAMPLES}
						{font}
						family={`fc-proof-${index}`}
						{cell}
						{dpr}
						{showEdges}
						{useText}
					/>
				</figure>
			</div>
		</section>
	{/each}
</main>
