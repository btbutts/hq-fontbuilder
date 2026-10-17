<script lang="ts">
	import IconEditBulk from '@tabler/icons-svelte/icons/edit-bulk';
	import IconEqualNot from '@tabler/icons-svelte/icons/equal-not';
	import {
		BareIconButton, colors, ColumnOrder, consoleStore, overlayStore, postChoose,
		ReorderableColumns, tip,
		type ComposerState, type FamilyInfo, type GroupInfo
	} from '#lib';
	import { goto } from '$app/navigation';
	import { onDestroy } from 'svelte';

	interface Props {
		snapshot: ComposerState;
		oneditcategories: () => void;
	}

	let { snapshot, oneditcategories }: Props = $props();

	const rows = $derived(snapshot.groups.filter((group) => !overlayStore.isExcluded(group.id)));

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

	let error = $state<string | null>(null);

	async function toggleFamily(group: GroupInfo, family: FamilyInfo): Promise<void> {
		const order = overlayStore.orderOf(group, snapshot);
		const result = await postChoose(
			group.id,
			order.includes(family.label) ? 'remove' : 'add',
			family.label,
			group.overlay ? order : undefined
		);
		error = result.ok ? null : (result.error ?? 'unknown error');
		if (result.ok && group.overlay && result.order) overlayStore.setOrder(group.id, result.order);
		await consoleStore.refresh();
	}

	// A click opens the cell's page once no second click follows within OPEN_DELAY_MS; a
	// double click instead adds the family to the category's order, or takes it out when it
	// is in it. A keyboard activation (no click count) opens the page at once, and a
	// modified click is left to the browser (a new tab).
	const OPEN_DELAY_MS = 350;
	let pendingOpen: ReturnType<typeof setTimeout> | undefined;

	function cancelPendingOpen(): void {
		clearTimeout(pendingOpen);
		pendingOpen = undefined;
	}

	onDestroy(cancelPendingOpen);

	function onCellClick(event: MouseEvent, group: GroupInfo, family: FamilyInfo): void {
		if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
			return;
		}
		event.preventDefault();
		if (event.detail > 1) return;
		cancelPendingOpen();
		const href = groupHref(family.label, group.id);
		if (event.detail === 0) void goto(href);
		else pendingOpen = setTimeout(() => void goto(href), OPEN_DELAY_MS);
	}

	function onCellDoubleClick(event: MouseEvent, group: GroupInfo, family: FamilyInfo): void {
		event.preventDefault();
		cancelPendingOpen();
		void toggleFamily(group, family);
	}
</script>

<div class="mt-4">
	<ReorderableColumns
		{columns}
		{rows}
		label={(column) => column.family.displayName}
		onreorder={(ids) => order.set(ids)}
		bind:locked={order.locked}
		aria-label="Glyph coverage by group and font family"
	>
		{#snippet fixedHeader(lockButton)}
			<div class="flex items-center justify-between gap-3 border px-2 py-1 font-semibold whitespace-nowrap {colors.border} {colors.quietControlBackground}">
				Group
				<span class="flex items-center gap-2">
					<BareIconButton
						icon={IconEditBulk}
						label="choose which glyph categories are shown"
						onclick={oneditcategories}
					/>
					{@render lockButton()}
				</span>
			</div>
		{/snippet}
		{#snippet fixedCell(group)}
			<div class="border-r border-b border-l px-2 py-1 text-left font-mono whitespace-nowrap {colors.border} {colors.pageBackground}">
				{group.label}{#if group.atomic}<span class="text-[0.8em] {colors.textAccent2}"> atomic</span>{/if}
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
			{@const position = overlayStore.orderOf(group, snapshot).indexOf(family.label)}
			{@const uneven = snapshot.uneven[family.label]?.includes(group.id) ?? false}
			<div class="border-r border-b p-0 text-center whitespace-nowrap {colors.border}">
				<a
					href={groupHref(family.label, group.id)}
					onclick={(event) => onCellClick(event, group, family)}
					ondblclick={(event) => onCellDoubleClick(event, group, family)}
					class="relative block px-2 py-1 no-underline select-none transition-[box-shadow,background-color,transform] duration-150 ease-out hover:z-10 hover:scale-[1.03] focus-visible:z-10 focus-visible:scale-[1.03] motion-reduce:transition-none motion-reduce:hover:scale-100 {cellClasses(present, total, position >= 0)} {position >= 0 ? 'font-semibold' : ''}"
					{...tip(
						`${family.displayName} — ${group.label}`,
						[
							`${present} of ${total} code points`,
							position >= 0
								? `number ${position + 1} in the inheritance order`
								: 'not in the inheritance order',
							'click to open its glyphs',
							position >= 0
								? 'double-click to remove it from the inheritance order'
								: 'double-click to add it to the inheritance order',
							uneven ? 'its styles hold different glyphs of this group' : null
						]
							.filter((line) => line !== null)
							.join('\n')
					)}
				>
					{present}/{total}{#if uneven}<IconEqualNot size="1em" class="ml-[0.25em] inline-block align-[-0.15em]" />{/if}{#if position >= 0}<sup class="ml-0.5 text-[0.7em] opacity-80">{position + 1}</sup>{/if}
				</a>
			</div>
		{/snippet}
	</ReorderableColumns>
</div>
{#if error}
	<p class="mt-2 mb-0 {colors.textError}">{error}</p>
{/if}
