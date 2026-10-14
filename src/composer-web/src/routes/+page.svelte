<script lang="ts">
	import { consoleStore } from '#lib/data/console.svelte.js';
	import StyleMappingModal from '#lib/modal/StyleMappingModal.svelte';
	import { colors } from '#lib/styles.svelte.js';
	import ThemeToggle from '#lib/toggle/ThemeToggle.svelte';
	import { tip } from '#lib/tooltip/tooltip.js';

	let showStyleMapping = $state(false);

	const snapshot = $derived(consoleStore.state);

	// A coverage cell has three tones (all glyphs, some, none) and two states: at rest, and
	// "marked" (the family is in the group's inheritance order). The pointer gives a cell
	// its marked colour and grows it over its neighbours. The colours are the glyphCell*
	// entries of `colors`.
	function cellClasses(present: number, total: number, marked: boolean): string {
		const tone =
			present === 0
				? colors.glyphCellNone
				: present === total
					? colors.glyphCellFull
					: colors.glyphCellPartial;
		return `${marked ? tone.selected : tone.rest} ${tone.hover} ${tone.text}`;
	}

	function groupHref(familyLabel: string, groupId: string): string {
		const params = new URLSearchParams({ family: familyLabel, group: groupId });
		return `/group?${params}`;
	}

	function composeHref(groupId: string): string {
		return `/compose?${new URLSearchParams({ group: groupId })}`;
	}
</script>

<div class="flex flex-wrap items-start justify-between gap-x-8 gap-y-3">
	<div class="min-w-0 flex-1 basis-[28rem]">
		<h1 class="mb-1 text-[1.4rem] font-semibold">font-composer</h1>
		<p class="mt-0 max-w-5xl {colors.textSecondary}">
			Coverage by glyph group and family, measured on each family's reference style (the upright
			cut nearest Regular). Click a cell to inspect the group's glyphs for that family and to add
			the family to the group's inheritance order. Atomic groups count as sourced only at 100% and
			come from one family. A ≠ marks a group on which the family's styles hold different glyphs.
		</p>
	</div>
	<div class="flex shrink-0 flex-col items-end gap-3">
		<ThemeToggle />
		<button
			type="button"
			class="cursor-pointer rounded border px-3 py-1.5 font-medium {colors.border} {colors.quietControlBackground} {colors.textPrimary} {colors.hoverBackground}"
			onclick={() => (showStyleMapping = true)}
		>
			Style Mapping
		</button>
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
	<table class="mt-4 border-collapse">
		<thead>
			<tr>
				<th class="border px-2 py-1 font-semibold whitespace-nowrap {colors.border} {colors.quietControlBackground}">group</th>
				{#each snapshot.families as family (family.label)}
					<th class="border px-2 py-1 font-semibold whitespace-nowrap {colors.border} {colors.quietControlBackground}">
						{family.label}{family.errors.length ? ' ⚠' : ''}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each snapshot.groups as group (group.id)}
				<tr>
					<td class="border px-2 py-1 text-left font-mono whitespace-nowrap {colors.border}">
						{group.id}{#if group.atomic}<span class="text-[0.8em] {colors.textAccent2}"> atomic</span>{/if}
					</td>
					{#each snapshot.families as family (family.label)}
						{@const [present, total] = snapshot.coverage[family.label]?.[group.id] ?? [0, group.total]}
						{@const position = (snapshot.choices[group.id] ?? []).indexOf(family.label)}
						{@const uneven = snapshot.uneven[family.label]?.includes(group.id) ?? false}
						<td class="border p-0 text-center whitespace-nowrap {colors.border}">
							<a
								href={groupHref(family.label, group.id)}
								class="relative block px-2 py-1 no-underline transition-[box-shadow,background-color,transform] duration-150 ease-out hover:z-10 hover:scale-[1.03] focus-visible:z-10 focus-visible:scale-[1.03] motion-reduce:transition-none motion-reduce:hover:scale-100 {cellClasses(present, total, position >= 0)} {position >= 0 ? 'font-semibold' : ''}"
								{...tip(
									`${family.label} — ${group.label}`,
									[
										`${present} of ${total} code points`,
										position >= 0 ? `number ${position + 1} in the inheritance order` : null,
										uneven ? 'its styles hold different glyphs of this group' : null
									]
										.filter((line) => line !== null)
										.join('\n')
								)}
							>
								{present}/{total}{uneven ? ' ≠' : ''}{#if position >= 0}<sup class="ml-0.5 text-[0.7em] opacity-80">{position + 1}</sup>{/if}
							</a>
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>

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
							<a href={composeHref(entry.group)} class="underline {colors.textAccent1}"
								title="show the combined glyphs of {entry.group}">{entry.group}</a
							>
						{:else}
							{entry.group}
						{/if}
					</td>
					<td class="border px-3 py-1 {colors.border}">
						{#if entry.order.length}
							{entry.order.join(', ')}
							<span class="ml-2 text-[0.85em] {colors.textTertiary}"
								>{entry.covered}/{entry.total} code points</span
							>
						{:else}
							<span class={colors.textError}>
								{entry.candidates.length
									? `unsourced — full coverage: ${entry.candidates.join(', ')}`
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
