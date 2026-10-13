<script lang="ts">
	import { page } from '$app/state';
	import { fetchGlyphs, postChoose, type GlyphsPayload, type GroupInfo } from '#lib/api.js';
	import { consoleStore } from '#lib/console.svelte.js';
	import GlyphGrid from '#lib/GlyphGrid.svelte';
	import { geometryFor, type LayoutMode } from '#lib/glyphLayout.js';

	const GLYPH_EM_PX = 64;
	const WRAP_STORAGE_KEY = 'fc-glyph-wrap';
	const FONT_FACE_ELEMENT_ID = 'fc-font-faces';
	// A group up to this size is drawn whole, absent code points as hatched cells. A larger
	// one (Nerd Font private use is ~72,000 code points) would be hundreds of thousands of
	// DOM nodes, so only the glyphs a style holds are drawn, a page at a time.
	const FULL_GRID_MAX = 512;
	const PAGE_SIZE = 256;

	const familyLabel = $derived(page.url.searchParams.get('family') ?? '');
	const groupId = $derived(page.url.searchParams.get('group') ?? '');
	const snapshot = $derived(consoleStore.state);
	const group = $derived(snapshot?.groups.find((entry) => entry.id === groupId));
	const family = $derived(snapshot?.families.find((entry) => entry.label === familyLabel));

	const order = $derived(snapshot?.choices[groupId] ?? []);
	const position = $derived(order.indexOf(familyLabel));
	const base = $derived(snapshot?.base ?? null);

	const geometry = $derived(geometryFor(base, GLYPH_EM_PX));

	// Rows (stacked, scrolls sideways) is the default; the toggle brings back the single
	// wrapping run. The choice is remembered by the browser, never by the server.
	function readWrapPreference(): boolean {
		try {
			return localStorage.getItem(WRAP_STORAGE_KEY) === '1';
		} catch {
			return false;
		}
	}

	let wrapGlyphs = $state(readWrapPreference());

	function setWrapGlyphs(enabled: boolean): void {
		wrapGlyphs = enabled;
		try {
			localStorage.setItem(WRAP_STORAGE_KEY, enabled ? '1' : '0');
		} catch {
			// private window or blocked storage: the choice just lasts for this page
		}
	}

	// A group too large to draw whole (private use) is a sparse list of the glyphs a style
	// holds; rows of 16 would be mostly holes, so it always wraps.
	const layoutMode = $derived<LayoutMode>(
		wrapGlyphs || (group !== undefined && group.total > FULL_GRID_MAX) ? 'wrap' : 'rows'
	);

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

	// What each style file holds of this group; refetched when the library changes.
	let glyphs = $state<GlyphsPayload | null>(null);
	let glyphsError = $state<string | null>(null);
	const currentGlyphs = $derived(
		glyphs !== null && glyphs.family === familyLabel && glyphs.group === groupId ? glyphs : null
	);
	const libraryVersion = $derived(snapshot?.version);

	$effect(() => {
		const requestFamily = familyLabel;
		const requestGroup = groupId;
		void libraryVersion;
		if (!requestFamily || !requestGroup) return;
		let cancelled = false;
		fetchGlyphs(requestFamily, requestGroup)
			.then((payload) => {
				if (cancelled) return;
				glyphs = payload;
				glyphsError = null;
			})
			.catch((cause: unknown) => {
				if (!cancelled) glyphsError = cause instanceof Error ? cause.message : String(cause);
			});
		return () => {
			cancelled = true;
		};
	});

	let shownLimits = $state<Record<string, number>>({});

	interface Cell {
		codepoint: number;
		present: boolean;
	}

	function held(file: string): number[] {
		return currentGlyphs?.styles[file] ?? [];
	}

	function visibleCells(file: string, target: GroupInfo): Cell[] {
		const heldPoints = held(file);
		if (target.total <= FULL_GRID_MAX) {
			const have = new Set(heldPoints);
			return groupCodepoints(target).map((codepoint) => ({
				codepoint,
				present: have.has(codepoint)
			}));
		}
		return heldPoints
			.slice(0, shownLimits[file] ?? PAGE_SIZE)
			.map((codepoint) => ({ codepoint, present: true }));
	}

	function showMore(file: string): void {
		shownLimits[file] = (shownLimits[file] ?? PAGE_SIZE) + PAGE_SIZE;
	}

	function groupCodepoints(target: GroupInfo): number[] {
		const points: number[] = [];
		for (const [low, high] of target.ranges) {
			for (let cp = low; cp <= high; cp += 1) points.push(cp);
		}
		return points;
	}

	let chooseError = $state<string | null>(null);

	async function change(action: 'add' | 'remove' | 'clear'): Promise<void> {
		const result = await postChoose(groupId, action, action === 'clear' ? null : familyLabel);
		chooseError = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}

	const chooseStatus = $derived(
		chooseError ??
			(order.length === 0
				? 'no family is chosen for this group yet'
				: position >= 0
					? `number ${position + 1} of ${order.length} in the inheritance order: ${order.join(', ')}`
					: `not used here; choosing it makes it number ${order.length + 1} after ${order.join(', ')}`)
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
		{base ? base.family : '(none configured)'}. Coverage shown for the family is that of its
		reference style (the upright cut nearest Regular). Families are used in the order they are
		chosen: a glyph comes from the first one that has it, the later ones fill in the rest.
	</p>
	{#if snapshot.uneven[family.label]?.includes(group.id)}
		<p class="mt-0 max-w-5xl text-[#9c7c00]">
			The styles of this family hold different glyphs of this group; check each one below.
			The build takes each output style's glyphs from the matching style file.
		</p>
	{/if}

	<div
		class="sticky top-0 z-10 flex flex-wrap items-center gap-y-1 border-b border-[#b9b9bd] bg-[#fafafa] py-2.5"
	>
		<label class="mr-6 cursor-pointer">
			<input
				type="checkbox"
				checked={position >= 0}
				onchange={(event) => change(event.currentTarget.checked ? 'add' : 'remove')}
			/>
			use this family for this group
		</label>
		{#if order.length > 0}
			<a
				class="mr-6 text-[#1b4965] underline"
				href="/compose?{new URLSearchParams({ group: groupId })}"
				title="the glyphs of this group as combined from the chosen families"
				>combined result →</a
			>
			<button
				type="button"
				class="mr-6 cursor-pointer rounded border border-[#b9b9bd] bg-white px-2 py-0.5 text-[0.9em]"
				onclick={() => change('clear')}
			>
				clear all families
			</button>
		{/if}
		<span class="text-[0.9em]" class:text-[#1b4965]={!chooseError} class:text-[#b02e2e]={!!chooseError}>
			{chooseStatus}
		</span>
		<label
			class="ml-auto cursor-pointer pl-6 {group.total > FULL_GRID_MAX
				? 'cursor-not-allowed text-[#999]'
				: ''}"
			title={group.total > FULL_GRID_MAX
				? 'this group is always shown as a wrapping run'
				: 'one wrapping run of cells instead of stacked rows'}
		>
			<input
				type="checkbox"
				checked={layoutMode === 'wrap'}
				disabled={group.total > FULL_GRID_MAX}
				onchange={(event) => setWrapGlyphs(event.currentTarget.checked)}
			/>
			Enable glyph wrapping
		</label>
	</div>

	<!-- All the styles scroll sideways together, so a column stays comparable across them. -->
	<div class="overflow-x-auto pb-4">

	{#each family.styles as style, index (style.file)}
		{@const [present, total] = style.coverage[groupId] ?? [0, group.total]}
		<section class={layoutMode === 'rows' ? 'w-max min-w-full' : ''}>
			<div class="sticky left-0 w-fit max-w-[min(64rem,calc(100vw-4rem))]">
				<h3 class="mt-4 mb-0.5 text-[1rem] font-semibold">{style.file} — {style.style}</h3>
				<p class="mt-0 mb-1.5 text-[0.85em] text-[#666]">
					weight {style.weight}, {style.italic ? 'italic' : 'upright'}, upm {style.unitsPerEm},
					ascent {style.ascent}, descent {style.descent}, cell advance {style.cellAdvance};
					group coverage {present}/{total}{#if group.total > FULL_GRID_MAX}; only the glyphs
						this style holds are drawn{/if}
				</p>
			</div>
			<div class="mt-2 mb-10">
				{#if currentGlyphs === null}
					<p class="m-0 text-[14px] text-[#555]">{glyphsError ?? 'loading glyphs…'}</p>
				{:else}
					{@const cells = visibleCells(style.file, group)}
					{#if cells.length === 0}
						<p class="m-0 text-[14px] text-[#b02e2e]">this style holds no glyph of this group</p>
					{:else}
						<GlyphGrid
							groupId={group.id}
							{cells}
							mode={layoutMode}
							fontFamily="fc-style-{index}"
							{geometry}
						/>
					{/if}
				{/if}
			</div>
			{#if group.total > FULL_GRID_MAX}
				{@const remaining = held(style.file).length - (shownLimits[style.file] ?? PAGE_SIZE)}
				{#if remaining > 0}
					<button
						type="button"
						class="sticky left-0 mb-8 cursor-pointer rounded border border-[#b9b9bd] bg-[#f0f0f4] px-3 py-1"
						onclick={() => showMore(style.file)}
					>
						show {Math.min(PAGE_SIZE, remaining)} more ({remaining} not shown)
					</button>
				{/if}
			{/if}
		</section>
	{/each}
	</div>
{/if}
