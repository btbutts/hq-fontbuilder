<script lang="ts">
	import CtrlButton from '../button/CtrlButton.svelte';
	import { postStyleConsolidate, postStyleType } from '../data/api';
	import { consoleStore } from '../data/console.svelte';
	import { colors } from '../styles.svelte';
	import Toggle from '../toggle/Toggle.svelte';
	import { lockScroll } from './scrollLock';

	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	const styleTypes = $derived(consoleStore.state?.styleTypes ?? null);
	const types = $derived(styleTypes?.options ?? []);
	let error = $state<string | null>(null);

	$effect(() => lockScroll());

	async function consolidate(enabled: boolean): Promise<void> {
		const result = await postStyleConsolidate(enabled);
		error = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}

	async function toggle(name: string, included: boolean): Promise<void> {
		const result = await postStyleType(name, included);
		error = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && onclose()} />

<!-- a click on the dimmed page behind the dialog closes it -->
<button
	type="button"
	class="fixed inset-0 z-40 cursor-default border-0 {colors.modalOverlay}"
	aria-label="close the list of font styles"
	onclick={onclose}
></button>

<div
	role="dialog"
	aria-modal="true"
	aria-labelledby="style-types-title"
	class="fixed top-[12vh] left-1/2 z-50 flex max-h-[76vh] w-[min(96vw,30rem)] -translate-x-1/2 flex-col rounded border {colors.border} {colors.modalBackground} {colors.floatingShadow}"
>
	<div class="flex items-start justify-between gap-4 border-b px-5 py-3 {colors.border}">
		<h2 id="style-types-title" class="m-0 text-[1.2rem] font-semibold">Pick Font Styles</h2>
		<CtrlButton function="modal.CLOSE" onclick={onclose} />
	</div>

	<div class="overflow-y-auto px-5 py-4">
		<p class="mt-0 mb-4 {colors.textSecondary}">
			These are the styles your fonts hold. Only the ones you include get a column in the style
			mapping and are built; Regular and Bold are included to begin with.
		</p>
		<div class="mb-4">
			<Toggle
				label="Consolidate Similar Font Styles"
				title="list styles that are the same by weight and slant (Heavy and Black, Book and Regular) as one entry; the style mapping matches files the same way either way"
				checked={styleTypes?.consolidate ?? true}
				onchange={consolidate}
			/>
		</div>

		{#if error}
			<p class="mt-2 {colors.textError}">{error}</p>
		{/if}

		{#if types.length === 0}
			<p class="mb-0 {colors.textSecondary}">
				{consoleStore.error ?? 'No style found: put font files in the fonts directory.'}
			</p>
		{:else}
			<ul class="m-0 grid list-none grid-cols-[auto_auto_1fr] items-center gap-x-3 gap-y-1.5 p-0">
				{#each types as type (type.name)}
					<li class="col-span-full grid grid-cols-subgrid items-center">
						<CtrlButton
							function={type.included ? 'styles.EXCLUDE' : 'styles.INCLUDE'}
							onclick={() => toggle(type.name, !type.included)}
						/>
						<span class={type.included ? 'font-medium' : colors.textTertiary}>
							{type.name}
						</span>
						<span class="text-[0.85em] {colors.textTertiary}">
							{type.similar.join(', ')}
						</span>
					</li>
				{/each}
			</ul>
		{/if}
	</div>
</div>
