<script lang="ts">
	import CtrlButton from '../button/CtrlButton.svelte';
	import { postOverlayStore, type GroupInfo } from '../data/api.ts';
	import { consoleStore } from '../data/console.svelte.ts';
	import { overlayStore } from '../data/overlay.svelte.ts';
	import { colors } from '../styles.svelte.ts';
	import Toggle from '../toggle/Toggle.svelte';
	import { tip } from '../tooltip/tooltip.ts';
	import { lockScroll } from './scrollLock.ts';

	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	const snapshot = $derived(consoleStore.state);
	const groups = $derived(snapshot?.groups ?? []);
	let error = $state<string | null>(null);

	$effect(() => lockScroll());

	async function setOverlay(enabled: boolean): Promise<void> {
		overlayStore.setEnabled(enabled);
		await consoleStore.refresh();
	}

	async function setStored(enabled: boolean): Promise<void> {
		const result = await postOverlayStore(enabled, overlayStore.orders);
		error = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}

	function fontsText(group: GroupInfo): string {
		return `${group.fonts.length} of ${snapshot?.fontCount ?? 0} Fonts have Glyphs in this Category`;
	}

	function fontsTip(group: GroupInfo): string {
		return group.fonts.map((font) => `${font.name}: ${font.count}`).join('\n');
	}
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && onclose()} />

<!-- a click on the dimmed page behind the dialog closes it -->
<button
	type="button"
	class="fixed inset-0 z-40 cursor-default border-0 {colors.modalOverlay}"
	aria-label="close the list of glyph categories"
	onclick={onclose}
></button>

<div
	role="dialog"
	aria-modal="true"
	aria-labelledby="glyph-categories-title"
	class="fixed top-[12vh] left-1/2 z-50 flex max-h-[76vh] w-[min(96vw,44rem)] -translate-x-1/2 flex-col rounded border {colors.border} {colors.modalBackground} {colors.floatingShadow}"
>
	<div class="flex items-start justify-between gap-4 border-b px-5 py-3 {colors.border}">
		<h2 id="glyph-categories-title" class="m-0 text-[1.2rem] font-semibold">
			Select Glyph Categories
		</h2>
		<CtrlButton function="modal.CLOSE" onclick={onclose} />
	</div>

	<div class="overflow-y-auto px-5 py-4">
		<p class="mt-0 mb-4 {colors.textSecondary}">
			These are the categories your fonts have glyphs in. A category you leave out is only hidden
			from the table: it is still built from whatever its inheritance order says.
		</p>
		<div class="mb-3">
			<Toggle
				label="Use simplified Glyph Category overlay"
				title="show the ASCII letters and digits, the other printable ASCII and Powerline as categories of their own; the configuration file and the built fonts only know the Unicode blocks"
				checked={overlayStore.enabled}
				onchange={setOverlay}
			/>
		</div>
		{#if overlayStore.enabled}
			<div class="mb-4">
				<Toggle
					label="Store Overlay Categories in toml config"
					title="keep the inheritance order of the overlay categories in the configuration file, so another browser shows them too; the build ignores it"
					checked={snapshot?.overlay.stored ?? false}
					onchange={setStored}
				/>
			</div>
		{/if}

		{#if error}
			<p class="mt-2 {colors.textError}">{error}</p>
		{/if}

		{#if groups.length === 0}
			<p class="mb-0 {colors.textSecondary}">
				{#if snapshot && !snapshot.catalogReady}
					The Unicode block list (Blocks.txt) is not available, so there are no categories.
				{:else}
					No font has glyphs yet: put font files in the fonts directory.
				{/if}
			</p>
		{:else}
			<ul class="m-0 grid list-none grid-cols-[auto_1fr_auto] items-center gap-x-3 gap-y-1.5 p-0">
				{#each groups as group (group.id)}
					{@const shown = !overlayStore.isExcluded(group.id)}
					<li class="col-span-full grid grid-cols-subgrid items-center">
						<CtrlButton
							function={shown ? 'styles.EXCLUDE' : 'styles.INCLUDE'}
							label={shown ? 'hide this category' : 'show this category'}
							onclick={() => overlayStore.setExcluded(group.id, shown)}
						/>
						<span class={shown ? 'font-medium' : colors.textTertiary}>
							{group.label}{#if group.overlay}<span class="text-[0.8em] font-normal {colors.textAccent2}"> overlay</span>{/if}
						</span>
						<span
							class="text-[0.85em] {colors.textTertiary}"
							{...tip(group.label, fontsTip(group))}
						>
							{fontsText(group)}
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>
