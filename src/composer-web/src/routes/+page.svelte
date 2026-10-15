<script lang="ts">
	import CtrlButton from '#lib/button/CtrlButton.svelte';
	import { consoleStore } from '#lib/data/console.svelte.ts';
	import StyleMappingModal from '#lib/modal/StyleMappingModal.svelte';
	import { colors } from '#lib/styles.svelte.ts';
	import ThemeToggle from '#lib/toggle/ThemeToggle.svelte';
	import { tip } from '#lib/tooltip/tooltip.ts';
	import GlyphFontFamilyTable from './GlyphFontFamilyTable.svelte';

	let showStyleMapping = $state(false);

	const snapshot = $derived(consoleStore.state);

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
<p class="mt-0 max-w-5xl {colors.textSecondary}">
	Coverage by glyph group and family, measured on each family's reference style (the upright
	cut nearest Regular). Click a cell to inspect the group's glyphs for that family and to add
	the family to the group's inheritance order. Atomic groups count as sourced only at 100% and
	come from one family. A ≠ marks a group on which the family's styles hold different glyphs.
</p>

{#if snapshot?.configError}
	<p class="mt-4 max-w-5xl rounded border px-3 py-2 {colors.errorBoxBorder} {colors.errorBoxBackground} {colors.textError}">
		The configuration file does not parse, so the last good configuration is still in force and
		nothing will be saved until it is fixed: {snapshot.configError}
	</p>
{/if}

{#if snapshot === null}
	<p class="mt-4 {colors.textSecondary}">{consoleStore.error ?? 'loading…'}</p>
{:else}
	<GlyphFontFamilyTable {snapshot} />

	<h2 class="mt-8 text-[1.1rem] font-semibold">Composition so far</h2>
	<p class="mt-0 max-w-5xl {colors.textSecondary}">
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
			{#each snapshot.summary as entry (entry.group)}
				<tr>
					<td class="border px-3 py-1 font-mono whitespace-nowrap {colors.border}">
						{#if entry.order.length}
							<a
								href={composeHref(entry.group)}
								class="underline {colors.textAccent1}"
								{...tip(undefined, `show the combined glyphs of ${entry.group}`)}>{entry.group}</a
							>
						{:else}
							{entry.group}
						{/if}
					</td>
					<td class="border px-3 py-1 {colors.border}">
						{#if entry.order.length}
							{entry.order.map((label) => consoleStore.nameOf(label)).join(', ')}
							<span class="ml-2 text-[0.85em] {colors.textTertiary}"
								>{entry.covered}/{entry.total} code points</span
							>
						{:else}
							<span class={colors.textError}>
								{entry.candidates.length
									? `unsourced — full coverage: ${entry.candidates.map((label) => consoleStore.nameOf(label)).join(', ')}`
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
