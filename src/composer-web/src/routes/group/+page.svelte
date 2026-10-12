<script lang="ts">
	import { page } from '$app/state';
	import { postChoose, type GroupInfo } from '#lib/api.js';
	import { consoleStore } from '#lib/console.svelte.js';
	import GlyphCell from '#lib/GlyphCell.svelte';

	const GLYPH_EM_PX = 48;
	const FONT_FACE_ELEMENT_ID = 'fc-font-faces';

	const familyLabel = $derived(page.url.searchParams.get('family') ?? '');
	const groupId = $derived(page.url.searchParams.get('group') ?? '');
	const snapshot = $derived(consoleStore.state);
	const group = $derived(snapshot?.groups.find((entry) => entry.id === groupId));
	const family = $derived(snapshot?.families.find((entry) => entry.label === familyLabel));

	const chosen = $derived(snapshot?.choices[groupId] ?? null);
	const base = $derived(snapshot?.base ?? null);

	// Cell geometry as em ratios of the base family's cell; defaults match the
	// historical page when no base family is configured.
	const cellW = $derived(base ? base.cellAdvance / base.unitsPerEm : 0.6);
	const cellH = $derived(base ? (base.ascent - base.descent) / base.unitsPerEm : 1.2);
	const ascentRatio = $derived(base ? base.ascent / base.unitsPerEm : 0.93);

	const fontFaceCss = $derived(
		family
			? family.styles
					.map(
						(style, index) =>
							`@font-face {\n  font-family: "fc-style-${index}";\n` +
							`  src: url("/fonts/${encodeURIComponent(family.label)}/` +
							`${encodeURIComponent(style.file)}");\n}`
					)
					.join('\n')
			: ''
	);

	$effect(() => {
		let styleEl = document.getElementById(FONT_FACE_ELEMENT_ID);
		if (!styleEl) {
			styleEl = document.createElement('style');
			styleEl.id = FONT_FACE_ELEMENT_ID;
			document.head.appendChild(styleEl);
		}
		styleEl.textContent = fontFaceCss;
	});

	function groupCodepoints(target: GroupInfo): number[] {
		const points: number[] = [];
		for (const [low, high] of target.ranges) {
			for (let cp = low; cp <= high; cp += 1) points.push(cp);
		}
		return points;
	}

	let chooseError = $state<string | null>(null);

	async function choose(familyToChoose: string | null): Promise<void> {
		const result = await postChoose(groupId, familyToChoose);
		chooseError = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}

	const chooseStatus = $derived(
		chooseError ??
			(chosen === null
				? 'no family chosen for this group'
				: chosen === familyLabel
					? 'this family is the chosen source'
					: `currently sourced from ${chosen} — choosing here replaces it`)
	);
</script>

<p><a href="/" class="text-[#1b4965] underline">← coverage table</a></p>

{#if snapshot === null}
	<p class="mt-4 text-[#555]">{consoleStore.error ?? 'loading…'}</p>
{:else if !group || !family}
	<h1 class="mb-1 text-[1.4rem] font-semibold">
		unknown family or group: {familyLabel} / {groupId}
	</h1>
{:else}
	<h1 class="mb-1 text-[1.4rem] font-semibold">
		{family.label} — {group.id}{group.atomic ? ' (atomic)' : ''}
	</h1>
	<p class="mt-0 max-w-5xl text-[#555]">
		{group.label}; {group.total} code points; cell of base family
		{base ? base.family : '(none configured)'}.
	</p>

	<div class="sticky top-0 z-10 border-b border-[#b9b9bd] bg-[#fafafa] py-2.5">
		<label class="mr-6 cursor-pointer">
			<input
				type="radio"
				name="choose"
				checked={chosen === familyLabel}
				onchange={() => choose(familyLabel)}
			/>
			use this family for this group
		</label>
		<label class="mr-6 cursor-pointer">
			<input type="radio" name="choose" checked={chosen === null} onchange={() => choose(null)} />
			no source chosen
		</label>
		<span class="text-[0.9em]" class:text-[#1b4965]={!chooseError} class:text-[#b02e2e]={!!chooseError}>
			{chooseStatus}
		</span>
	</div>

	{#each family.styles as style, index (style.file)}
		{@const [present, total] = style.coverage[groupId] ?? [0, group.total]}
		<section>
			<h3 class="mt-4 mb-0.5 text-[1rem] font-semibold">{style.file} — {style.style}</h3>
			<p class="mt-0 mb-1.5 text-[0.85em] text-[#666]">
				weight {style.weight}, {style.italic ? 'italic' : 'upright'}, upm {style.unitsPerEm},
				ascent {style.ascent}, descent {style.descent}, cell advance {style.cellAdvance};
				group coverage {present}/{total}
			</p>
			<div
				class="mt-2 mb-12 flex flex-wrap gap-0.5"
				style:font-size="{GLYPH_EM_PX}px"
				style:--cell-w={cellW}
				style:--cell-h={cellH}
				style:--ascent={ascentRatio}
			>
				{#each groupCodepoints(group) as cp (cp)}
					<GlyphCell codepoint={cp} fontFamily="fc-style-{index}" />
				{/each}
			</div>
		</section>
	{/each}
{/if}
