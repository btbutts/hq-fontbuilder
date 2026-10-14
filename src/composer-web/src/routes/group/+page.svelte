<script lang="ts">
	import { page } from '$app/state';
	import {
		fetchGlyphs,
		postChoose,
		type FitInfo,
		type GlyphsPayload,
		type GroupInfo
	} from '#lib/data/api.js';
	import { consoleStore } from '#lib/data/console.svelte.js';
	import { installFontFaces } from '#lib/glyph/families.js';
	import { clippedCount } from '#lib/glyph/fitDisplay.js';
	import GlyphGrid from '#lib/glyph/GlyphGrid.svelte';
	import PageHeader from '#lib/layout/PageHeader.svelte';
	import { colors } from '#lib/styles.svelte.js';
	import StickyBar from '#lib/layout/StickyBar.svelte';
	import ThemeToggle from '#lib/toggle/ThemeToggle.svelte';
	import { unicodeNames } from '#lib/data/unicodeNames.svelte.js';
	import { FULL_GRID_MAX, geometryFor, PAGE_SIZE } from '#lib/glyph/glyphLayout.js';
	import Toggle from '#lib/toggle/Toggle.svelte';
	import ViewToggles from '#lib/toggle/ViewToggles.svelte';
	import { viewOptions } from '#lib/toggle/viewOptions.svelte.js';

	const GLYPH_EM_PX = 64;
	const FONT_FACE_ELEMENT_ID = 'fc-font-faces';

	const familyLabel = $derived(page.url.searchParams.get('family') ?? '');
	const groupId = $derived(page.url.searchParams.get('group') ?? '');

	$effect(() => {
		void unicodeNames.load(groupId);
	});
	const snapshot = $derived(consoleStore.state);
	const group = $derived(snapshot?.groups.find((entry) => entry.id === groupId));
	const family = $derived(snapshot?.families.find((entry) => entry.label === familyLabel));

	const order = $derived(snapshot?.choices[groupId] ?? []);
	const position = $derived(order.indexOf(familyLabel));
	const base = $derived(snapshot?.base ?? null);

	const geometry = $derived(geometryFor(base, GLYPH_EM_PX));

	const layoutMode = $derived(viewOptions.layoutMode(group?.total ?? 0));

	function clippedIn(file: string): number {
		return clippedCount(Object.values(currentGlyphs?.fit[file] ?? {}));
	}

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
		installFontFaces(FONT_FACE_ELEMENT_ID, fontFaceCss);
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
		fit?: FitInfo;
	}

	function held(file: string): number[] {
		return currentGlyphs?.styles[file] ?? [];
	}

	function visibleCells(file: string, target: GroupInfo): Cell[] {
		const heldPoints = held(file);
		const fits = currentGlyphs?.fit[file] ?? {};
		if (target.total <= FULL_GRID_MAX) {
			const have = new Set(heldPoints);
			return groupCodepoints(target).map((codepoint) => ({
				codepoint,
				present: have.has(codepoint),
				fit: fits[codepoint]
			}));
		}
		return heldPoints
			.slice(0, shownLimits[file] ?? PAGE_SIZE)
			.map((codepoint) => ({ codepoint, present: true, fit: fits[codepoint] }));
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

<PageHeader>
	<div class="flex items-center justify-between gap-4">
		<a href="/" class="underline {colors.textAccent1}">← coverage table</a>
		<ThemeToggle />
	</div>

	{#if snapshot === null}
		<p class="mt-4 mb-0 {colors.textSecondary}">{consoleStore.error ?? 'loading…'}</p>
	{:else if !group || !family}
		<h1 class="mt-4 mb-0 text-[1.4rem] font-semibold">
			unknown family or group: {familyLabel} / {groupId}
		</h1>
	{:else}
		<h1 class="mt-4 mb-1 text-[1.4rem] font-semibold">
			{family.label} — {group.id}{group.atomic ? ' (atomic)' : ''}
		</h1>
		<p class="mt-0 mb-0 max-w-5xl {colors.textSecondary}">
			{group.label}; {group.total} code points; cell of base family
			{base ? base.family : '(none configured)'}. Coverage shown for the family is that of its
			reference style (the upright cut nearest Regular). Families are used in the order they are
			chosen: a glyph comes from the first one that has it, the later ones fill in the rest.
		</p>
		{#if snapshot.uneven[family.label]?.includes(group.id)}
			<p class="mt-2 mb-0 max-w-5xl {colors.textWarning}">
				<span class="block">The styles of this family hold different glyphs of this group; check each one below.</span>
				<span class="block">The build takes each output style's glyphs from the matching style file.</span>
			</p>
		{/if}
	{/if}
</PageHeader>

{#if snapshot !== null && group && family}
	<StickyBar>
		<span class="mr-6">
			<Toggle
				label="use this family for this group"
				checked={position >= 0}
				onchange={(enabled) => change(enabled ? 'add' : 'remove')}
			/>
		</span>
		{#if order.length > 0}
			<a
				class="mr-6 underline {colors.textAccent1}"
				href="/compose?{new URLSearchParams({ group: groupId })}"
				title="the glyphs of this group as combined from the chosen families"
				>combined result →</a
			>
			<button
				type="button"
				class="mr-6 cursor-pointer rounded border px-2 py-0.5 text-[0.9em] {colors.border} {colors.raisedControlBackground}"
				onclick={() => change('clear')}
			>
				clear all families
			</button>
		{/if}
		<span class="text-[0.9em] {chooseError ? colors.textError : colors.textAccent1}">
			{chooseStatus}
		</span>
		<span class="ml-auto flex flex-wrap items-center gap-x-6 gap-y-1 pl-6">
			<ViewToggles groupTotal={group.total} />
		</span>
	</StickyBar>

<!-- All the styles scroll sideways together, so a column stays comparable across them. -->
	<div class="overflow-x-auto pb-4">

	{#each family.styles as style, index (style.file)}
		{@const [present, total] = style.coverage[groupId] ?? [0, group.total]}
		<section class={layoutMode === 'rows' ? 'w-max min-w-full' : ''}>
			<div class="sticky left-0 w-fit max-w-[min(64rem,calc(100vw-4rem))]">
				<h3 class="mt-4 mb-0.5 text-[1rem] font-semibold">{style.file} — {style.style}</h3>
				<p class="mt-0 mb-1.5 text-[0.85em] {colors.textSecondary}">
					weight {style.weight}, {style.italic ? 'italic' : 'upright'}, upm {style.unitsPerEm},
					ascent {style.ascent}, descent {style.descent}, cell advance {style.cellAdvance};
					group coverage {present}/{total}{#if group.total > FULL_GRID_MAX}; only the glyphs
						this style holds are drawn{/if}{#if viewOptions.unfitted && clippedIn(style.file) > 0}; <span
							class="font-semibold {colors.textClipped}"
							>{clippedIn(style.file)} glyph{clippedIn(style.file) === 1 ? '' : 's'} cut off
							by the base cell (red outline)</span
						>{/if}
				</p>
			</div>
			<div class="mt-2 mb-10">
				{#if currentGlyphs === null}
					<p class="m-0 text-[14px] {colors.textSecondary}">{glyphsError ?? 'loading glyphs…'}</p>
				{:else}
					{@const cells = visibleCells(style.file, group)}
					{#if cells.length === 0}
						<p class="m-0 text-[14px] {colors.textError}">this style holds no glyph of this group</p>
					{:else}
						<GlyphGrid
							groupId={group.id}
							{cells}
							mode={layoutMode}
							fontFamily="fc-style-{index}"
							{geometry}
							showFitted={viewOptions.showFitted}
						/>
					{/if}
				{/if}
			</div>
			{#if group.total > FULL_GRID_MAX}
				{@const remaining = held(style.file).length - (shownLimits[style.file] ?? PAGE_SIZE)}
				{#if remaining > 0}
					<button
						type="button"
						class="sticky left-0 mb-8 cursor-pointer rounded border px-3 py-1 {colors.border} {colors.quietControlBackground}"
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
