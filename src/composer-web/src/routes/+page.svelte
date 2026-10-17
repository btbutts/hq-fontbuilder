<script lang="ts">
	import { afterNavigate, beforeNavigate } from '$app/navigation';
	import { tick } from 'svelte';
	import IconEqualNot from '@tabler/icons-svelte/icons/equal-not';
	import CtrlButton from '#lib/button/CtrlButton.svelte';
	import PeekButton from '#lib/button/PeekButton.svelte';
	import { consoleStore } from '#lib/data/console.svelte.ts';
	import { recalledScroll, rememberScroll } from '#lib/data/mainScroll.ts';
	import { overlayStore } from '#lib/data/overlay.svelte.ts';
	import SelectGlyphCategories from '#lib/modal/SelectGlyphCategories.svelte';
	import StyleMappingModal from '#lib/modal/StyleMappingModal.svelte';
	import { colors } from '#lib/styles.svelte.ts';
	import ThemeToggle from '#lib/toggle/ThemeToggle.svelte';
	import { tip } from '#lib/tooltip/tooltip.ts';
	import GlyphFontFamilyTable from './GlyphFontFamilyTable.svelte';

	let showStyleMapping = $state(false);
	let notesOpen = $state(false);

	const snapshot = $derived(consoleStore.state);

	// Leaving for a category's page and coming back (the button, or the browser's back)
	// returns to where the long table was left, down the page and along the table.
	function tableScroller(): HTMLElement | null {
		return document.querySelector<HTMLElement>('.fc-col-scroller');
	}

	beforeNavigate(() => {
		rememberScroll({
			x: window.scrollX,
			y: window.scrollY,
			tableLeft: tableScroller()?.scrollLeft ?? 0
		});
	});

	function restoreScroll(): void {
		const place = recalledScroll();
		const scroller = tableScroller();
		if (scroller) scroller.scrollLeft = place.tableLeft;
		window.scrollTo(place.x, place.y);
	}

	let restored = false;
	$effect(() => {
		if (snapshot === null || restored) return;
		restored = true;
		void tick().then(restoreScroll);
	});

	afterNavigate(() => requestAnimationFrame(restoreScroll));
	let showCategories = $state(false);

	const shownSummary = $derived(
		(snapshot?.summary ?? []).filter((entry) => !overlayStore.isExcluded(entry.group))
	);

	function groupOf(id: string) {
		return snapshot?.groups.find((group) => group.id === id);
	}

	function composeHref(groupId: string): string {
		return `/compose?${new URLSearchParams({ group: groupId })}`;
	}
</script>

<!--
	The title and the controls remain locked to one line, regardless of viewport width and
	they are not permitted to wrap. The description is its own element below, so it can run
	span underneath them when the viewport width is narrowed.
-->
<div class="mb-1 flex items-center justify-between gap-x-6">
	<h1 class="m-0 text-[1.4rem] font-semibold">font-composer</h1>
	<div class="flex shrink-0 items-center gap-4">
		<ThemeToggle />
		<CtrlButton
			padding="px-2 py-0.5"
			fontSize="text-[0.9em]"
			onclick={() => (showStyleMapping = true)}
		>
			Style Mapping
		</CtrlButton>
	</div>
</div>
<div class="{colors.textSecondary}">
	<p class="mt-0 max-w-5xl pb-1">
		<PeekButton bind:open={notesOpen} controls="table-notes">
			The table below shows the composition of each Glyph Category for the respective Font Families.
		</PeekButton>
	</p>
	<div
		id="table-notes"
		class="grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none
			{notesOpen ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}"
		inert={!notesOpen}
	>
		<ul class="min-h-0 list-disc list-outside space-x-2 overflow-hidden pl-9">
			<li>
				Click a cell to inspect the glyphs of that Glyph Category for the Font Family; double-click
				it to add the Font Family to the Glyph Category's inheritance order, or to remove it when
				it is already in it.
			</li>
			<li>Atomic Glyph Categories are counted as sourced only at 100% coverage and come from one Font Family.</li>
			<li>
				<span>A <IconEqualNot size="1em" class="inline-block align-[-0.15em]" /> signifies a </span>
				<span>Glyph Category of the respective Font Family's style(s) hold differing glyphs.</span>
			</li>
		</ul>
	</div>
</div>

{#if snapshot?.configError}
	<p class="mt-4 max-w-5xl rounded border px-3 py-2 {colors.errorBoxBorder} {colors.errorBoxBackground} {colors.textError}">
		The configuration file does not parse, so the last good configuration is still in force and
		nothing will be saved until it is fixed: {snapshot.configError}
	</p>
{/if}

{#if snapshot === null}
	<p class="mt-4 {colors.textSecondary}">{consoleStore.error ?? 'loading…'}</p>
{:else}
	<GlyphFontFamilyTable {snapshot} oneditcategories={() => (showCategories = true)} />
	{#if snapshot.groups.length === 0}
		<p class="mt-4 {colors.textSecondary}">
			{snapshot.catalogReady
				? 'No font has glyphs yet: put font files in the fonts directory.'
				: 'The Unicode block list (Blocks.txt) is not available, so there are no glyph categories.'}
		</p>
	{/if}

	<h2 class="mt-8 text-[1.1rem] font-semibold">Composition so far</h2>
	<p class="mt-0 mb-4 max-w-5xl {colors.textSecondary}">
		Each group takes a glyph from the first family of its inheritance order that has one; the
		following families fill in what is missing. Click a category to see the combined result and
		to pick single glyphs.
	</p>
	<table class="border-collapse">
		<thead>
			<tr>
				<th class="border px-3 py-1 text-left font-semibold {colors.border} {colors.quietControlBackground}">
					Glyph Categories
				</th>
				<th class="border px-3 py-1 text-left font-semibold {colors.border} {colors.quietControlBackground}">
					Font Inheritance Order
				</th>
			</tr>
		</thead>
		<tbody>
			{#each shownSummary as entry (entry.group)}
				{@const group = groupOf(entry.group)}
				{@const order = group ? overlayStore.orderOf(group, snapshot) : entry.order}
				{@const label = group?.label ?? entry.group}
				<tr>
					<td class="border px-3 py-1 font-mono whitespace-nowrap {colors.border}">
						{#if order.length || entry.covered > 0}
							<a
								href={composeHref(entry.group)}
								class="underline {colors.textAccent1}"
								{...tip(undefined, `show the combined glyphs of ${label}`)}>{label}</a
							>
						{:else}
							{label}
						{/if}
					</td>
					<td class="border px-3 py-1 {colors.border}">
						{#if order.length}
							{order.map((name) => consoleStore.nameOf(name)).join(', ')}
							<span class="ml-2 text-[0.85em] {colors.textTertiary}"
								>{entry.covered}/{entry.total} code points</span
							>
						{:else if entry.covered > 0}
							{Object.keys(entry.sources).map((name) => consoleStore.nameOf(name)).join(', ')}
							<span class="ml-2 text-[0.85em] {colors.textTertiary}"
								>{entry.covered}/{entry.total} code points</span
							>
						{:else}
							<span class={colors.textError}>
								{entry.candidates.length
									? `unsourced — full coverage: ${entry.candidates.map((name) => consoleStore.nameOf(name)).join(', ')}`
									: 'unsourced — no family covers this group fully'}
							</span>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>

	<h2 class="mt-8 text-[1.1rem] font-semibold">Problem fonts</h2>
	<ul>
		{#each snapshot.problems as problem (problem.path)}
			<li class="font-mono text-[0.9em] {colors.textError}">{problem.path}: {problem.reason}</li>
		{:else}
			<li class={colors.textTertiary}>none</li>
		{/each}
	</ul>
{/if}

{#if showStyleMapping}
	<StyleMappingModal onclose={() => (showStyleMapping = false)} />
{/if}

{#if showCategories}
	<SelectGlyphCategories onclose={() => (showCategories = false)} />
{/if}
