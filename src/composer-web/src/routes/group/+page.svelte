<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import {
		clippedCount, colors, ConfirmModal, consoleStore, CtrlButton, emphasis, fetchFit,
		fetchGlyphs, FontLoader, FULL_GRID_MAX, geometryFor, GlyphGrid, installFontFaces,
		overlayStore,
		PAGE_SIZE, PageHeader, postChoose, StickyBar, ThemeToggle, tip, Toggle, unicodeNames,
		viewOptions, ViewToggles,
		type FitInfo, type GlyphsPayload, type GroupInfo
	} from '#lib';
	import IconHelpCircleFilled from '@tabler/icons-svelte/icons/help-circle-filled';

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

	const order = $derived(group ? overlayStore.orderOf(group, snapshot) : []);
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

	// Nothing of the styles is drawn until their glyph lists are here and their font files
	// are loaded; the page shows one loader meanwhile.
	let loadedFonts = $state('');
	const fontsKey = $derived(`${familyLabel}|${groupId}`);

	$effect(() => {
		const key = fontsKey;
		const styles = family?.styles;
		if (!styles || currentGlyphs === null || loadedFonts === key) return;
		let cancelled = false;
		Promise.allSettled(
			styles.map((style, index) =>
				document.fonts.load(
					`${GLYPH_EM_PX}px "fc-style-${index}"`,
					String.fromCodePoint(held(style.file)[0] ?? 0x20)
				)
			)
		).then(() => {
			if (!cancelled) loadedFonts = key;
		});
		return () => {
			cancelled = true;
		};
	});

	const stylesReady = $derived(
		loadedFonts === fontsKey &&
			currentGlyphs !== null &&
			(group === undefined ||
				group.total <= FULL_GRID_MAX ||
				(family?.styles ?? []).every((style) => readyLimit[style.file] !== undefined))
	);

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
		const result = await postChoose(
			groupId,
			action,
			action === 'clear' ? null : familyLabel,
			group?.overlay ? order : undefined
		);
		chooseError = result.ok ? null : (result.error ?? 'unknown error');
		if (result.ok && group?.overlay && result.order) overlayStore.setOrder(groupId, result.order);
		await consoleStore.refresh();
	}

	// The title line shows a short status, so that it never grows taller; the details are its tooltip.
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
		<CtrlButton function="nav.BACK" onclick={() => goto('/', { reset: false })}>Coverage Table</CtrlButton>
		<div class="flex items-center gap-4">
			<ThemeToggle />
			{#if snapshot !== null && group && family && order.length > 0}
				<CtrlButton
					function="nav.FORWARD"
					onclick={() => goto(`/compose?${new URLSearchParams({ group: groupId })}`)}
				>
					Combined Result
				</CtrlButton>
			{/if}
		</div>
	</div>

	{#if snapshot === null}
		<p class="mt-4 mb-0 {colors.textSecondary}">{consoleStore.error ?? 'loading…'}</p>
	{:else if !group || !family}
		<h1 class="mt-4 mb-0 text-[1.4rem] font-semibold">
			unknown family or group: {familyLabel} / {groupId}
		</h1>
	{:else}
		{@const words = family.displayName.split(/\s+/)}
		{@const nameFirst = words[0]}
		{@const nameLast = words.length > 1 ? words[words.length - 1] : ''}
		{@const nameMiddle = words.slice(1, -1).join(' ')}
		{@const categoryName = `— ${group.label}${group.atomic ? ' (atomic)' : ''}`}
		<!--
			The status stands right of the title, on the title's line, and the line never wraps, so
			the circle never moves. When the line is too narrow, things give way in this order:

			1. the status text: the status is a row that wraps inside a box one line tall, so its text
			   drops into the hidden second line as a whole and only the circle stays;
			2. the middle of the family name ("Nerd Font" of "FiraMono Nerd Font Mono") is cut from
			   its end and ends in an ellipsis; the first and last words, the dash and the group
			   name are never cut;
			3. only then the first word, from its end.

			Every shrinking part has a shrink factor, and an item with any shrink at all is
			cut at the first pixel it is short of, so the parts that must not give way yet have
			factor 0 or a near-zero one next to the part that is to go first (1000). The title
			itself does not shrink; it is only capped so that the gap and the circle fit beside it.

			The box is set in the title's font size (1.4rem) so that the circle is as tall as the
			title's text is large: the icon is 1.2em, and the circle is 20 of its 24 units, so the
			circle is 1em. The status text is set back to the 13.5px it has always had (0.9 of the
			page's 15px).
		-->
		<div class="mt-4 mb-1 flex items-center gap-x-4">
			<h1
				class="m-0 flex max-w-[calc(100%-1rem-1.2em)] min-w-0 shrink-0 gap-x-[0.3em] text-[1.4rem] font-semibold whitespace-nowrap"
				{...tip(undefined, `${family.displayName} ${categoryName}`)}
			>
				<span class="min-w-0 shrink-[0.001] truncate">{nameFirst}</span>
				{#if nameMiddle}
					<span class="min-w-[1.6em] shrink-[1000] truncate">{nameMiddle}</span>
				{/if}
				{#if nameLast}
					<span class="shrink-0">{nameLast}</span>
				{/if}
				<span class="shrink-0">{categoryName}</span>
			</h1>
			<span
				class="flex h-[1lh] min-w-[1.2em] shrink-[1000] flex-wrap items-center gap-x-1.5 gap-y-4 overflow-hidden text-[1.4rem] whitespace-nowrap {chooseError
					? colors.textError
					: colors.textAccent1}"
				{...tip(undefined, statusDetails)}
			>
				<!-- each is the box's full height, so that the first line is centred in it whether or not a second one wraps -->
				<span class="flex h-full items-center">
					<IconHelpCircleFilled class="size-[1.2em] shrink-0" aria-hidden="true" />
				</span>
				<span class="flex h-full items-center text-[13.5px]">{statusText}</span>
			</span>
		</div>
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
	{#snippet useToggle()}
		<Toggle
			label="Use this Font Family for the {group.label} Group"
			checked={position >= 0}
			onchange={(enabled) => change(enabled ? 'add' : 'remove')}
		/>
	{/snippet}
	{#snippet clearAll()}
		{#if order.length > 0}
			<CtrlButton
				surface="raised"
				padding="px-2 py-0.5"
				fontSize="text-[0.9em]"
				tooltip="remove every font from the Inheritance Order of this glyph category (asks first)"
				onclick={() => (confirmClear = true)}
			>
				Clear All Families
			</CtrlButton>
		{/if}
	{/snippet}

	<!-- too narrow for all of it: the switches go behind the menu button, Clear All stays -->
	<StickyBar>
		{#snippet full()}
			<span class="mr-6 flex">{@render useToggle()}</span>
			{@render clearAll()}
			<span class="ml-auto flex items-center gap-x-6 pl-6">
				<ViewToggles groupTotal={group.total} />
			</span>
		{/snippet}
		{#snippet compact()}
			{@render clearAll()}
		{/snippet}
		{#snippet menu()}
			{@render useToggle()}
			<ViewToggles groupTotal={group.total} />
		{/snippet}
	</StickyBar>

	{#if glyphsError !== null && currentGlyphs === null}
		<p class="mt-4 text-[14px] {colors.textError}">{glyphsError}</p>
	{:else if !stylesReady}
		<FontLoader />
	{:else}
<!-- All the styles scroll sideways together, so a column stays comparable across them. -->
	<div class="overflow-x-auto pb-4">

	{#each family.styles as style, index (style.file)}
		{@const present = currentGlyphs?.styles[style.file]?.length ?? 0}
		{@const total = group.total}
		{@const cells = visibleCells(style.file, group)}
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
				{#if cells.length === 0}
					<p class="m-0 text-[14px] {colors.textError}">this style holds no glyph of this group</p>
				{:else}
					<GlyphGrid
						namedRows={group.rows}
						{cells}
						mode={layoutMode}
						fontFamily="fc-style-{index}"
						{geometry}
						showFitted={viewOptions.showFitted}
					/>
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
