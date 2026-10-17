<script lang="ts">
	import IconEditBulk from '@tabler/icons-svelte/icons/edit-bulk';
	import BareIconButton from '../button/BareIconButton.svelte';
	import CtrlButton from '../button/CtrlButton.svelte';
	import InlineRename from '../button/InlineRename.svelte';
	import { postStyle, postStyleName, type StyleFileInfo } from '../data/api.ts';
	import { consoleStore } from '../data/console.svelte.ts';
	import Dropdown from '../dropdown/Dropdown.svelte';
	import { ColumnOrder } from '../table/columnOrder.svelte.ts';
	import ReorderableColumns from '../table/ReorderableColumns.svelte';
	import { lockScroll } from './scrollLock.ts';
	import StyleTypesModal from './StyleTypesModal.svelte';
	import { colors } from '../styles.svelte.ts';

	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	const snapshot = $derived(consoleStore.state);
	const map = $derived(snapshot?.styleMap ?? null);
	const families = $derived(Object.keys(map?.families ?? {}));

	let error = $state<string | null>(null);
	let editingStyles = $state(false);

	const order = new ColumnOrder('fc-column-order:style-mapping', () => map?.outputStyles ?? []);
	const columns = $derived(order.ids.map((id) => ({ id })));
	const rows = $derived(families.map((id) => ({ id })));

	let renaming = $state<Record<string, boolean>>({});
	const anyRenaming = $derived(Object.values(renaming).some(Boolean));

	$effect(() => lockScroll());

	/** What a style file is, from the names inside the font (not its file name). */
	function describe(file: StyleFileInfo): string {
		return `${file.family} — ${file.style} (${file.weight}${file.italic ? ', italic' : ''})`;
	}

	function automaticLabel(family: string, style: string): string {
		const entry = map?.entries[style]?.[family];
		if (!entry?.file || entry.overridden) return 'automatic';
		const file = map?.families[family]?.find((item) => item.file === entry.file);
		return file ? `automatic: ${describe(file)}` : 'automatic';
	}

	/** Name an output style (`null`: as the fonts name it); resolves with why it was refused. */
	async function rename(style: string, name: string | null): Promise<string | null> {
		const result = await postStyleName(style, name);
		if (result.ok) await consoleStore.refresh();
		return result.ok ? null : (result.error ?? 'unknown error');
	}

	async function choose(style: string, family: string, value: string): Promise<void> {
		const result = await postStyle(style, family, value === '' ? null : value);
		error = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}
</script>

<!-- the list of styles on top has its own Escape: this one waits until it is gone -->
<svelte:window onkeydown={(event) => event.key === 'Escape' && !editingStyles && onclose()} />

<!-- a click on the dimmed page behind the dialog closes it -->
<button
	type="button"
	class="fixed inset-0 z-20 cursor-default border-0 {colors.modalOverlay}"
	aria-label="close the style mapping"
	onclick={onclose}
></button>

<div
	role="dialog"
	aria-modal="true"
	aria-labelledby="style-mapping-title"
	class="fixed top-[5vh] left-1/2 z-30 flex max-h-[90vh] w-[min(96vw,80rem)] -translate-x-1/2 flex-col rounded border {colors.border} {colors.modalBackground} {colors.floatingShadow}"
>
	<div class="flex items-start justify-between gap-4 border-b px-5 py-3 {colors.border}">
		<h2 id="style-mapping-title" class="m-0 text-[1.2rem] font-semibold">Style Mapping</h2>
		<CtrlButton function="modal.CLOSE" onclick={onclose} />
	</div>

	<div class="overflow-y-auto px-5 py-4">
		<p class="mt-0 max-w-5xl {colors.textSecondary}">
			In the table below, choose the <em>Font Sources</em>, per <em>Font Style</em> from the <em>Font Families</em>
			listed on the left column. This grouping isn't used for glyph inheritance. Rather, because many fonts use
			differing <em>Font Style Names</em> like Oblique & Italic, Book & Regular, Black & SemiBold..., the table
			allows for mapping these differing sources to a single <em>Font Style Type</em>.
			<span class="pt-2 block">Please consider the following when choosing font sources for each style:</span>
		</p>
		<ol class="mt-0 max-w-5xl list-decimal pl-6 {colors.textSecondary}">
			<li>
				A font you pick below is always used over the auto-grouping logic. You may reverse your decision.
			</li>
			<li>
				Only files with a similar slant are grouped automatically (e.g., an italic style is never grouped with
				an upright style).
				<span class="block">Styles are not artificially slanted by this tool.</span>
			</li>
			<li>
				The font weight, by analyzing the styles with identical or aproximate weights, are used to help determine
				the ideal font styles to group together.
			</li>
		</ol>
		{#if error}
			<p class="mt-2 {colors.textError}">{error}</p>
		{/if}

		{#if map === null}
			<p class="mt-4 {colors.textSecondary}">{consoleStore.error ?? 'loading…'}</p>
		{:else if families.length === 0}
			<p class="mt-4 {colors.textSecondary}">
				No family is used by any glyph group yet. Choose families in the coverage table first.
			</p>
		{:else}
			{@const m = map}
			<div class="mt-4 [--select-width:28rem]">
				<ReorderableColumns
					{columns}
					{rows}
					dragDisabled={anyRenaming}
					label={(column) => m.names[column.id] ?? column.id}
					onreorder={(ids) => order.set(ids)}
					bind:locked={order.locked}
					columnBackground={colors.modalBackground}
					aria-label="Font sources by font family and font style"
				>
					{#snippet fixedHeader(lockButton)}
						<div
							class="border px-3 py-1 text-left font-semibold whitespace-nowrap {colors.border} {colors.quietControlBackground}"
						>
							<div class="flex items-center justify-between gap-3">
								Font Family
								<span class="flex items-center gap-2">
									<BareIconButton
										icon={IconEditBulk}
										label="choose which font styles are considered"
										onclick={() => (editingStyles = true)}
									/>
									{@render lockButton()}
								</span>
							</div>
						</div>
					{/snippet}
					{#snippet fixedCell(row)}
						<div
							class="border-r border-b border-l px-3 py-1 align-top font-semibold whitespace-nowrap {colors.border} {colors.modalBackground}"
						>
							{consoleStore.nameOf(row.id)}
						</div>
					{/snippet}
					{#snippet header(column, handle)}
						<div
							use:handle
							class="fc-col-handle border-t border-r border-b text-left font-semibold {colors.border} {colors.quietControlBackground}"
						>
							<InlineRename
								original={column.id}
								custom={m.names[column.id] ?? null}
								onsave={(name) => rename(column.id, name)}
								onreset={() => rename(column.id, null)}
								onediting={(on) => (renaming[column.id] = on)}
							/>
						</div>
					{/snippet}
					{#snippet cell(column, row)}
						{@const entry = m.entries[column.id]?.[row.id]}
						<div class="border-r border-b px-3 py-1 align-top {colors.border}">
							<Dropdown
								class="w-(--select-width)"
								value={entry?.overridden ? (entry.file ?? '') : ''}
								options={[
									{ value: '', label: automaticLabel(row.id, column.id) },
									...(m.families[row.id] ?? []).map((file) => ({
										value: file.file,
										label: describe(file)
									}))
								]}
								onchange={(file) => choose(column.id, row.id, file)}
							/>
							<div
								class="mt-0.5 w-(--select-width) text-[0.8em] {entry?.file
									? colors.textTertiary
									: colors.textError}"
							>
								{entry?.reason ?? ''}
							</div>
						</div>
					{/snippet}
				</ReorderableColumns>
			</div>
		{/if}
	</div>
</div>

{#if editingStyles}
	<StyleTypesModal onclose={() => (editingStyles = false)} />
{/if}
