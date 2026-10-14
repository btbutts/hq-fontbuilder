<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import ConfirmModal from '#lib/modal/ConfirmModal.svelte';
	import IconHelpCircleFilled from '@tabler/icons-svelte/icons/help-circle-filled';
	import {
		fetchFit,
		fetchGlyphs,
		postChoose,
		type FitInfo,
		type GlyphsPayload,
		type GroupInfo
	} from '#lib/data/api.js';
	import { consoleStore } from '#lib/data/console.svelte.js';
	import CtrlButton from '#lib/button/CtrlButton.svelte';
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
	import { emphasis, tip } from '#lib/tooltip/tooltip.js';

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

	// A group too large to fit whole is fitted a page at a time: `fitsOf` is what has been
	// asked for so far, and what the page draws and counts. Showing more glyphs, or
	// switching the preview, only ever adds to it.
	function fitsOf(file: string): Record<string, FitInfo> {
		return group && group.total > FULL_GRID_MAX
			? (lazyFit[file] ?? {})
			: (currentGlyphs?.fit[file] ?? {});
	}

	function clippedIn(file: string): number {
		return clippedCount(Object.values(fitsOf(file)));
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

	// A group too large to fit whole (nerd-icons) is fitted a page at a time. A page of glyphs
	// is drawn only once its font is loaded and its fits are here: nothing is drawn before
	// (no empty boxes, no glyphs that jump into place), and a style that has not been
	// fitted yet shows only its heading, like every other group while it loads.
	// `readyLimit` is how many of a style's glyphs are drawn, and only ever grows.
	let lazyFit = $state<Record<string, Record<string, FitInfo>>>({});
	let readyLimit = $state<Record<string, number>>({});
	let askedLimit = new Map<string, number>();
	let lazyKey = '';

	$effect(() => {
		if (!group || !family || currentGlyphs === null || group.total <= FULL_GRID_MAX) return;
		const key = `${familyLabel}|${groupId}|${libraryVersion}`;
		if (key !== lazyKey) {
			lazyKey = key;
			lazyFit = {};
			readyLimit = {};
			askedLimit = new Map();
		}
		family.styles.forEach((style, index) => {
			const limit = shownLimits[style.file] ?? PAGE_SIZE;
			const done = askedLimit.get(style.file) ?? 0;
			if (limit <= done) return;
			const held_ = held(style.file);
			const wanted = held_.slice(done, limit);
			askedLimit.set(style.file, limit);
			if (wanted.length === 0) {
				readyLimit[style.file] = limit;
				return;
			}
			const face = `64px "fc-style-${index}"`;
			Promise.all([
				fetchFit(familyLabel, groupId, style.file, wanted).catch(() => null),
				document.fonts.load(face, String.fromCodePoint(wanted[0])).catch(() => [])
			]).then(([payload]) => {
				if (key !== lazyKey) return;
				if (payload) lazyFit[style.file] = { ...lazyFit[style.file], ...payload.fit };
				readyLimit[style.file] = Math.max(readyLimit[style.file] ?? 0, limit);
			});
		});
	});

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
		const fits = fitsOf(file);
		if (target.total <= FULL_GRID_MAX) {
			const have = new Set(heldPoints);
			return groupCodepoints(target).map((codepoint) => ({
				codepoint,
				present: have.has(codepoint),
				fit: fits[codepoint]
			}));
		}
		const drawn = Math.min(shownLimits[file] ?? PAGE_SIZE, readyLimit[file] ?? 0);
		return heldPoints
			.slice(0, drawn)
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
	let confirmClear = $state(false);

	async function change(action: 'add' | 'remove' | 'clear'): Promise<void> {
		const result = await postChoose(groupId, action, action === 'clear' ? null : familyLabel);
		chooseError = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}

	// The toolbar shows a short status, so that it never grows taller; the details are its tooltip.
	const familyName = $derived(family?.displayName ?? familyLabel);
	const orderNames = $derived(order.map((label) => consoleStore.nameOf(label)));

	const statusText = $derived(
		chooseError !== null
			? 'Could not save'
			: position >= 0
				? `Inheritance Position: ${position + 1} of ${order.length}`
				: 'Not Inherited'
	);

	const statusDetails = $derived.by(() => {
		if (chooseError !== null) return chooseError;
		if (position >= 0) {
			const names = orderNames.map((name, index) =>
				index === position ? emphasis(name) : name
			);
			return [
				`${familyName} is at position ${position + 1} of ${order.length} in the ${groupId} Inheritance Order:`,
				names.join(', ')
			].join('\n');
		}
		const lines = [`${familyName} is not yet in the Inheritance Order for ${groupId}.`];
		if (order.length === 0) {
			lines.push('Selecting it will add it at position 1.');
		} else {
			lines.push(
				`Selecting it will add it at position ${order.length + 1} after:`,
				[...orderNames, emphasis(familyName)].join(', ')
			);
		}
		return lines.join('\n');
	});
</script>

<PageHeader>
	<div class="flex items-center justify-between gap-4">
		<CtrlButton function="nav.BACK" onclick={() => goto('/')}>coverage table</CtrlButton>
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
			{family.displayName} — {group.id}{group.atomic ? ' (atomic)' : ''}
		</h1>
		<p class="mt-0 mb-0 max-w-5xl {colors.textSecondary}">
			{group.label}; {group.total} code points; cell of base family
			{base ? consoleStore.nameOf(base.family) : '(none configured)'}. Coverage shown for the family is that of its
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
		<span class="mr-6 flex">
			<Toggle
				label="Use this Font Family for the {group.id} Group"
				checked={position >= 0}
				onchange={(enabled) => change(enabled ? 'add' : 'remove')}
			/>
		</span>
		{#if order.length > 0}
			<CtrlButton
				function="nav.FORWARD"
				class="mr-6"
				onclick={() => goto(`/compose?${new URLSearchParams({ group: groupId })}`)}
			>
				combined result
			</CtrlButton>
			<CtrlButton
				surface="raised"
				padding="px-2 py-0.5"
				fontSize="text-[0.9em]"
				class="mr-6"
				tooltip="remove every font from the Inheritance Order of this glyph category (asks first)"
				onclick={() => (confirmClear = true)}
			>
				Clear All Families
			</CtrlButton>
		{/if}
		<span
			class="inline-flex items-center gap-1 text-[0.9em] whitespace-nowrap {chooseError
				? colors.textError
				: colors.textAccent1}"
			{...tip(undefined, statusDetails)}
		>
			{statusText}
			<!-- the circle is 20 of the icon's 24 units: scaled so that it is as tall as the button beside it -->
			<IconHelpCircleFilled
				class="-my-[2.5px] size-[calc((1lh+6px)*1.2)] shrink-0"
				aria-hidden="true"
			/>
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
				{#if currentGlyphs === null || (group.total > FULL_GRID_MAX && readyLimit[style.file] === undefined)}
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
					<CtrlButton
						function="list.SHOW_MORE"
						class="sticky left-0 mb-8"
						onclick={() => showMore(style.file)}
					>
						Show {Math.min(PAGE_SIZE, remaining)} More ({remaining} Remaining)
					</CtrlButton>
				{/if}
			{/if}
		</section>
	{/each}
	</div>
{/if}

{#if confirmClear}
	<ConfirmModal
		title="Clear All Families"
		message="This removes every font from the {groupId} Inheritance Order. Fonts can be added again afterwards from the coverage table."
		confirmLabel="Confirm"
		onconfirm={() => {
			confirmClear = false;
			void change('clear');
		}}
		oncancel={() => (confirmClear = false)}
	/>
{/if}
