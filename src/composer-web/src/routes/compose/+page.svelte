<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		fetchComposition,
		postChoose,
		postGlyph,
		type ChooseAction,
		type Composition,
		type ResolvedGlyph
	} from '#lib/data/api.js';
	import CtrlButton from '#lib/button/CtrlButton.svelte';
	import { consoleStore } from '#lib/data/console.svelte.js';
	import Dropdown from '#lib/dropdown/Dropdown.svelte';
	import { familyColor, familyCssName, fontFaceRules, installFontFaces } from '#lib/glyph/families.js';
	import GlyphChooser, { type Candidate } from '#lib/glyph/GlyphChooser.svelte';
	import { clippedCount } from '#lib/glyph/fitDisplay.js';
	import GlyphGrid from '#lib/glyph/GlyphGrid.svelte';
	import PageHeader from '#lib/layout/PageHeader.svelte';
	import { colors } from '#lib/styles.svelte.js';
	import StickyBar from '#lib/layout/StickyBar.svelte';
	import ThemeToggle from '#lib/toggle/ThemeToggle.svelte';
	import { unicodeNames } from '#lib/data/unicodeNames.svelte.js';
	import { FULL_GRID_MAX, geometryFor, PAGE_SIZE, type LayoutCell } from '#lib/glyph/glyphLayout.js';
	import ViewToggles from '#lib/toggle/ViewToggles.svelte';
	import { viewOptions } from '#lib/toggle/viewOptions.svelte.js';

	const GLYPH_EM_PX = 64;
	const FONT_FACE_ELEMENT_ID = 'fc-font-faces';

	const groupId = $derived(page.url.searchParams.get('group') ?? '');

	$effect(() => {
		void unicodeNames.load(groupId);
	});
	const snapshot = $derived(consoleStore.state);
	const group = $derived(snapshot?.groups.find((entry) => entry.id === groupId));
	const geometry = $derived(geometryFor(snapshot?.base ?? null, GLYPH_EM_PX));

	let composition = $state<Composition | null>(null);
	let loadError = $state<string | null>(null);
	const current = $derived(
		composition !== null && composition.group === groupId ? composition : null
	);

	// Refetched when the group changes, and whenever the console's version moves (a choice
	// made here or elsewhere, a font added, the configuration edited by hand).
	$effect(() => {
		const requested = groupId;
		void snapshot?.version;
		if (!requested) return;
		let cancelled = false;
		fetchComposition(requested)
			.then((payload) => {
				if (cancelled) return;
				composition = payload;
				loadError = null;
			})
			.catch((cause: unknown) => {
				if (!cancelled) loadError = cause instanceof Error ? cause.message : String(cause);
			});
		return () => {
			cancelled = true;
		};
	});

	$effect(() => {
		installFontFaces(
			FONT_FACE_ELEMENT_ID,
			current ? fontFaceRules(current.order, current.fonts) : ''
		);
	});

	const clippedTotal = $derived(clippedCount((current?.glyphs ?? []).map((glyph) => glyph.fit)));
	const large = $derived((group?.total ?? 0) > FULL_GRID_MAX);
	const layoutMode = $derived(viewOptions.layoutMode(group?.total ?? 0));

	const bySource = $derived(
		new Map<number, ResolvedGlyph>((current?.glyphs ?? []).map((glyph) => [glyph.codepoint, glyph]))
	);

	function toCell(glyph: ResolvedGlyph | undefined, codepoint: number): LayoutCell {
		if (!glyph || !current) return { codepoint, present: false };
		const index = current.order.indexOf(glyph.source);
		return {
			codepoint,
			present: true,
			fontFamily: familyCssName(index),
			accent: familyColor(index),
			pinned: glyph.overridden === true,
			alternatives: glyph.candidates?.length ?? 1,
			fit: glyph.fit
		};
	}

	let shown = $state(PAGE_SIZE);

	const cells = $derived.by<LayoutCell[]>(() => {
		if (!current || !group) return [];
		if (!large) {
			const points: number[] = [];
			for (const [low, high] of group.ranges) {
				for (let cp = low; cp <= high; cp += 1) points.push(cp);
			}
			return points.map((cp) => toCell(bySource.get(cp), cp));
		}
		return current.glyphs.slice(0, shown).map((glyph) => toCell(glyph, glyph.codepoint));
	});

	// ---- order controls

	let actionError = $state<string | null>(null);

	async function change(action: ChooseAction, family: string | null): Promise<void> {
		const result = await postChoose(groupId, action, family);
		actionError = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}

	const unusedFamilies = $derived(
		(snapshot?.families ?? [])
			.map((family) => family.label)
			.filter((label) => !(current?.order ?? []).includes(label))
	);

	// ---- the pop-out for choosing one glyph

	let chooser = $state.raw<{ codepoint: number; anchor: HTMLElement } | null>(null);

	function openChooser(cell: LayoutCell, element: HTMLElement): void {
		chooser = { codepoint: cell.codepoint, anchor: element };
	}

	const chooserGlyph = $derived(chooser ? bySource.get(chooser.codepoint) : undefined);
	const candidates = $derived<Candidate[]>(
		(chooserGlyph?.candidates ?? []).map((family) => {
			const index = current?.order.indexOf(family) ?? 0;
			return {
				family,
				label: current?.familyNames[family] ?? family,
				cssName: familyCssName(index),
				color: familyColor(index)
			};
		})
	);

	async function choose(family: string | null): Promise<void> {
		if (!chooser) return;
		const result = await postGlyph(chooser.codepoint, family);
		actionError = result.ok ? null : (result.error ?? 'unknown error');
		chooser = null;
		await consoleStore.refresh();
	}

	function hex(codepoint: number): string {
		return `U+${codepoint.toString(16).toUpperCase().padStart(4, '0')}`;
	}
</script>

<PageHeader>
	<div class="flex items-center justify-between gap-4">
		<CtrlButton function="nav.BACK" onclick={() => goto('/')}>coverage table</CtrlButton>
		<ThemeToggle />
	</div>

	{#if snapshot === null}
		<p class="mt-4 mb-0 {colors.textSecondary}">{consoleStore.error ?? 'loading…'}</p>
	{:else if !group}
		<h1 class="mt-4 mb-0 text-[1.4rem] font-semibold">unknown group: {groupId}</h1>
	{:else if current === null}
		<p class="mt-4 mb-0 {colors.textSecondary}">{loadError ?? 'loading…'}</p>
	{:else}
		<h1 class="mt-4 mb-1 text-[1.4rem] font-semibold">
			{group.id}{group.atomic ? ' (atomic)' : ''} — combined result
		</h1>
		<p class="mt-0 mb-0 max-w-5xl {colors.textSecondary}">
			{group.label}; {group.total - current.missing} of {group.total} code points have a glyph.
			{#if group.atomic}
				An atomic group comes from one family, so its glyphs cannot be mixed.
			{:else}
				A glyph is taken from the first family of the inheritance order that has it. A ring in
				the corner of a cell marks a glyph that more than one family has; click it to choose
				which family draws it. A filled dot marks a glyph you pinned.
			{/if}
		</p>

		<h2 class="mt-5 mb-1 text-[1rem] font-semibold">Font inheritance order</h2>
		{#if current.order.length === 0}
			<p class="mt-0 mb-0 {colors.textError}">
				No family is chosen for this group. Open a family from the coverage table to add it.
			</p>
		{/if}
		<!--
			One grid for the whole list; every row is a subgrid of it, so the columns line up
			across rows (names are the widest column, the counts start after the longest name, the
			buttons share their columns) without drawing a table.
		-->
		<ol class="m-0 grid w-fit list-none grid-cols-[repeat(7,auto)] gap-x-2 p-0">
			{#each current.order as family, index (family)}
				<li class="col-span-full grid grid-cols-subgrid items-center py-0.5">
					<span
						class="inline-block h-3 w-3 rounded-sm bg-current {familyColor(index)}"
						aria-hidden="true"
					></span>
					<span class="text-right {colors.textTertiary}">{index + 1}.</span>
					<span class="font-medium">{consoleStore.nameOf(family)}</span>
					<span class="pl-4 text-[0.85em] whitespace-nowrap {colors.textTertiary}">
						{current.contributions[family] ?? 0} glyph{current.contributions[family] === 1
							? ''
							: 's'} used
					</span>
					<CtrlButton
						function="reorder.UP"
						disabled={index === 0}
						onclick={() => change('up', family)}
					/>
					<CtrlButton
						function="reorder.DOWN"
						disabled={index === current.order.length - 1}
						onclick={() => change('down', family)}
					/>
					<CtrlButton function="reorder.REMOVE" onclick={() => change('remove', family)} />
				</li>
			{/each}
		</ol>
		{#if unusedFamilies.length > 0 && !(group.atomic && current.order.length > 0)}
			<label class="mt-2 inline-block text-[0.9em]">
				add a family at the end:
				<Dropdown
					class="ml-1"
					surface="raised"
					momentary
					value=""
					options={[
						{ value: '', label: 'choose…' },
						...unusedFamilies.map((family) => ({
							value: family,
							label: consoleStore.nameOf(family)
						}))
					]}
					onchange={(family) => {
						if (family) void change('add', family);
					}}
				/>
			</label>
		{/if}
		{#if actionError}
			<p class="mt-2 mb-0 {colors.textError}">{actionError}</p>
		{/if}
		{#if current.invalidOverrides.length > 0}
			<div
				class="mt-3 max-w-5xl rounded border px-3 py-2 text-[0.9em] {colors.warningBoxBorder} {colors.warningBoxBackground}"
			>
				Some pinned glyphs in the configuration cannot be honoured and are ignored:
				<ul class="m-0 pl-5">
					{#each current.invalidOverrides as item (item.codepoint)}
						<li><span class="font-mono">{hex(item.codepoint)}</span> → {consoleStore.nameOf(item.family)}: {item.reason}</li>
					{/each}
				</ul>
			</div>
		{/if}
	{/if}
</PageHeader>

{#if snapshot !== null && group && current !== null}
	<StickyBar>
		<span class="text-[0.9em] {colors.textSecondary}">
			Glyphs are drawn from each family's reference style (the upright cut nearest Regular).
			{#if viewOptions.unfitted && clippedTotal > 0}
				<span class="font-semibold {colors.textClipped}"
					>{clippedTotal} glyph{clippedTotal === 1 ? ' is' : 's are'} cut off by the base cell
					(red outline).</span
				>
			{/if}
		</span>
		<span class="ml-auto flex flex-wrap items-center gap-x-6 gap-y-1 pl-6">
			<ViewToggles groupTotal={group.total} />
		</span>
	</StickyBar>

	<div class="overflow-x-auto py-4">
		{#if cells.length === 0}
			<p class="m-0 {colors.textError}">no family of this group has a glyph in it</p>
		{:else}
			<GlyphGrid
				groupId={group.id}
				{cells}
				mode={layoutMode}
				fontFamily={familyCssName(0)}
				{geometry}
				showFitted={viewOptions.showFitted}
				onpick={group.atomic ? undefined : openChooser}
			/>
			{#if large && current.glyphs.length > shown}
				<CtrlButton function="list.SHOW_MORE" class="mt-4" onclick={() => (shown += PAGE_SIZE)}>
					show {Math.min(PAGE_SIZE, current.glyphs.length - shown)} more ({current.glyphs.length -
						shown} not shown)
				</CtrlButton>
			{/if}
		{/if}
	</div>
{/if}

{#if chooser && chooserGlyph && candidates.length > 0}
	<!-- keyed, so that another glyph's pop-up is a new one placed next to its own cell -->
	{#key chooser.codepoint}
		<GlyphChooser
			codepoint={chooser.codepoint}
			{candidates}
			current={chooserGlyph.source}
			pinned={chooserGlyph.overridden === true}
			{geometry}
			anchor={chooser.anchor}
			onchoose={choose}
			onclose={() => (chooser = null)}
		/>
	{/key}
{/if}
