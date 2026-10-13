<script lang="ts">
	import { page } from '$app/state';
	import {
		fetchComposition,
		postChoose,
		postGlyph,
		type ChooseAction,
		type Composition,
		type ResolvedGlyph
	} from '#lib/api.js';
	import { consoleStore } from '#lib/console.svelte.js';
	import { familyColor, familyCssName, fontFaceRules, installFontFaces } from '#lib/families.js';
	import GlyphChooser, { type Candidate } from '#lib/GlyphChooser.svelte';
	import GlyphGrid from '#lib/GlyphGrid.svelte';
	import { geometryFor, type LayoutCell, type LayoutMode } from '#lib/glyphLayout.js';

	const GLYPH_EM_PX = 64;
	const FONT_FACE_ELEMENT_ID = 'fc-font-faces';
	const WRAP_STORAGE_KEY = 'fc-glyph-wrap';
	// Same limits as the group page: a group this large (Nerd Font private use) is drawn
	// as the list of glyphs that have a source, a page at a time.
	const FULL_GRID_MAX = 512;
	const PAGE_SIZE = 256;

	const groupId = $derived(page.url.searchParams.get('group') ?? '');
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
			// the choice just lasts for this page
		}
	}

	const large = $derived((group?.total ?? 0) > FULL_GRID_MAX);
	const layoutMode = $derived<LayoutMode>(wrapGlyphs || large ? 'wrap' : 'rows');

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
			alternatives: glyph.candidates?.length ?? 1
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

	let chooser = $state<{
		codepoint: number;
		anchor: { left: number; top: number; bottom: number };
	} | null>(null);

	function openChooser(cell: LayoutCell, element: HTMLElement): void {
		const rect = element.getBoundingClientRect();
		chooser = {
			codepoint: cell.codepoint,
			anchor: { left: rect.left, top: rect.top, bottom: rect.bottom }
		};
	}

	const chooserGlyph = $derived(chooser ? bySource.get(chooser.codepoint) : undefined);
	const candidates = $derived<Candidate[]>(
		(chooserGlyph?.candidates ?? []).map((family) => {
			const index = current?.order.indexOf(family) ?? 0;
			return {
				family,
				cssName: familyCssName(index),
				color: familyColor(index),
				rank: index + 1
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

<p><a href="/" class="text-[#1b4965] underline">← coverage table</a></p>

{#if snapshot === null}
	<p class="mt-4 text-[#555]">{consoleStore.error ?? 'loading…'}</p>
{:else if !group}
	<h1 class="mb-1 text-[1.4rem] font-semibold">unknown group: {groupId}</h1>
{:else if current === null}
	<p class="mt-4 text-[#555]">{loadError ?? 'loading…'}</p>
{:else}
	<h1 class="mb-1 text-[1.4rem] font-semibold">
		{group.id}{group.atomic ? ' (atomic)' : ''} — combined result
	</h1>
	<p class="mt-0 max-w-5xl text-[#555]">
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
		<p class="mt-0 text-[#b02e2e]">
			No family is chosen for this group. Open a family from the coverage table to add it.
		</p>
	{/if}
	<ol class="m-0 list-none p-0">
		{#each current.order as family, index (family)}
			<li class="flex items-center gap-2 py-0.5">
				<span
					class="inline-block h-3 w-3 rounded-sm"
					style:background={familyColor(index)}
					aria-hidden="true"
				></span>
				<span class="w-5 text-right text-[#777]">{index + 1}.</span>
				<span class="font-medium">{family}</span>
				<span class="text-[0.85em] text-[#777]">
					{current.contributions[family] ?? 0} glyph{current.contributions[family] === 1
						? ''
						: 's'} used
				</span>
				<button
					type="button"
					class="cursor-pointer rounded border border-[#b9b9bd] bg-white px-1.5 disabled:opacity-30"
					title="earlier in the order"
					disabled={index === 0}
					onclick={() => change('up', family)}>▲</button
				>
				<button
					type="button"
					class="cursor-pointer rounded border border-[#b9b9bd] bg-white px-1.5 disabled:opacity-30"
					title="later in the order"
					disabled={index === current.order.length - 1}
					onclick={() => change('down', family)}>▼</button
				>
				<button
					type="button"
					class="cursor-pointer rounded border border-[#b9b9bd] bg-white px-1.5 text-[#b02e2e]"
					title="leave out of this group"
					onclick={() => change('remove', family)}>✕</button
				>
			</li>
		{/each}
	</ol>
	{#if unusedFamilies.length > 0 && !(group.atomic && current.order.length > 0)}
		<label class="mt-2 inline-block text-[0.9em]">
			add a family at the end:
			<select
				class="ml-1 rounded border border-[#b9b9bd] bg-white px-1 py-0.5"
				onchange={(event) => {
					const family = event.currentTarget.value;
					event.currentTarget.value = '';
					if (family) void change('add', family);
				}}
			>
				<option value="">choose…</option>
				{#each unusedFamilies as family (family)}
					<option value={family}>{family}</option>
				{/each}
			</select>
		</label>
	{/if}
	{#if actionError}
		<p class="mt-2 mb-0 text-[#b02e2e]">{actionError}</p>
	{/if}
	{#if current.invalidOverrides.length > 0}
		<div class="mt-3 max-w-5xl rounded border border-[#9c7c00] bg-[#fff8e1] px-3 py-2 text-[0.9em]">
			Some pinned glyphs in the configuration cannot be honoured and are ignored:
			<ul class="m-0 pl-5">
				{#each current.invalidOverrides as item (item.codepoint)}
					<li><span class="font-mono">{hex(item.codepoint)}</span> → {item.family}: {item.reason}</li>
				{/each}
			</ul>
		</div>
	{/if}

	<div
		class="sticky top-0 z-10 mt-4 flex items-center border-b border-[#b9b9bd] bg-[#fafafa] py-2"
	>
		<span class="text-[0.9em] text-[#555]">
			Glyphs are drawn from each family's reference style (the upright cut nearest Regular).
		</span>
		<label
			class="ml-auto cursor-pointer pl-6 {large ? 'cursor-not-allowed text-[#999]' : ''}"
			title={large
				? 'this group is always shown as a wrapping run'
				: 'one wrapping run of cells instead of stacked rows'}
		>
			<input
				type="checkbox"
				checked={layoutMode === 'wrap'}
				disabled={large}
				onchange={(event) => setWrapGlyphs(event.currentTarget.checked)}
			/>
			Enable glyph wrapping
		</label>
	</div>

	<div class="overflow-x-auto py-4">
		{#if cells.length === 0}
			<p class="m-0 text-[#b02e2e]">no family of this group has a glyph in it</p>
		{:else}
			<GlyphGrid
				groupId={group.id}
				{cells}
				mode={layoutMode}
				fontFamily={familyCssName(0)}
				{geometry}
				onpick={group.atomic ? undefined : openChooser}
			/>
			{#if large && current.glyphs.length > shown}
				<button
					type="button"
					class="mt-4 cursor-pointer rounded border border-[#b9b9bd] bg-[#f0f0f4] px-3 py-1"
					onclick={() => (shown += PAGE_SIZE)}
				>
					show {Math.min(PAGE_SIZE, current.glyphs.length - shown)} more ({current.glyphs.length -
						shown} not shown)
				</button>
			{/if}
		{/if}
	</div>
{/if}

{#if chooser && chooserGlyph && candidates.length > 0}
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
{/if}
