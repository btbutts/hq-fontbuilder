<script lang="ts">
	import type { ComposerState, FamilyInfo } from '#lib/data/api.ts';
	import { colors } from '#lib/styles.svelte.ts';
	import { ColumnOrder } from '#lib/table/columnOrder.svelte.ts';
	import ReorderableColumns from '#lib/table/ReorderableColumns.svelte';
	import { tip } from '#lib/tooltip/tooltip.ts';

	interface Props {
		snapshot: ComposerState;
	}

	let { snapshot }: Props = $props();

	interface FamilyColumn {
		id: string;
		family: FamilyInfo;
	}

	const order = new ColumnOrder('fc-column-order:coverage', () =>
		snapshot.families.map((family) => family.label)
	);

	const columns = $derived.by<FamilyColumn[]>(() => {
		const byLabel = new Map(snapshot.families.map((family) => [family.label, family]));
		return order.ids.flatMap((label) => {
			const family = byLabel.get(label);
			return family ? [{ id: label, family }] : [];
		});
	});

	// A font cell has three tones (all glyphs, partial, none) and two states: at-rest, and
	// "selected" (meaning it is in the glyph category inheritance order). Hovering also
	// renders its selected color and slightly expands it over its neighbours.
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
</script>

<div class="mt-4">
	<ReorderableColumns
		{columns}
		rows={snapshot.groups}
		label={(column) => column.family.displayName}
		onreorder={(ids) => order.set(ids)}
		aria-label="Glyph coverage by group and font family"
	>
		{#snippet fixedHeader()}
			<div class="border px-2 py-1 text-center font-semibold whitespace-nowrap {colors.border} {colors.quietControlBackground}">
				Group
			</div>
		{/snippet}
		{#snippet fixedCell(group)}
			<div class="border-r border-b border-l px-2 py-1 text-left font-mono whitespace-nowrap {colors.border} {colors.pageBackground}">
				{group.id}{#if group.atomic}<span class="text-[0.8em] {colors.textAccent2}"> atomic</span>{/if}
			</div>
		{/snippet}
		{#snippet header({ family }, handle)}
			<div
				use:handle
				aria-label="{family.displayName}: drag to move this column"
				class="fc-col-handle border-t border-r border-b px-2 py-1 text-center font-semibold whitespace-nowrap {colors.border} {colors.quietControlBackground}"
			>
				{family.displayName}{family.errors.length ? ' ⚠' : ''}
			</div>
		{/snippet}
		{#snippet cell({ family }, group)}
			{@const [present, total] = snapshot.coverage[family.label]?.[group.id] ?? [0, group.total]}
			{@const position = (snapshot.choices[group.id] ?? []).indexOf(family.label)}
			{@const uneven = snapshot.uneven[family.label]?.includes(group.id) ?? false}
			<div class="border-r border-b p-0 text-center whitespace-nowrap {colors.border}">
				<a
					href={groupHref(family.label, group.id)}
					class="relative block px-2 py-1 no-underline transition-[box-shadow,background-color,transform] duration-150 ease-out hover:z-10 hover:scale-[1.03] focus-visible:z-10 focus-visible:scale-[1.03] motion-reduce:transition-none motion-reduce:hover:scale-100 {cellClasses(present, total, position >= 0)} {position >= 0 ? 'font-semibold' : ''}"
					{...tip(
						`${family.displayName} — ${group.label}`,
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
			</div>
		{/snippet}
	</ReorderableColumns>
</div>
