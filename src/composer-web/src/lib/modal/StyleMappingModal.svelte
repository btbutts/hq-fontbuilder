<script lang="ts">
	import CtrlButton from '../button/CtrlButton.svelte';
	import { postStyle, type StyleFileInfo } from '../data/api';
	import { consoleStore } from '../data/console.svelte';
	import Dropdown from '../dropdown/Dropdown.svelte';
	import { colors } from '../styles.svelte';

	interface Props {
		onclose: () => void;
	}

	let { onclose }: Props = $props();

	const snapshot = $derived(consoleStore.state);
	const map = $derived(snapshot?.styleMap ?? null);
	const families = $derived(Object.keys(map?.families ?? {}));

	let error = $state<string | null>(null);

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

	async function choose(style: string, family: string, value: string): Promise<void> {
		const result = await postStyle(style, family, value === '' ? null : value);
		error = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && onclose()} />

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
		<h2 id="style-mapping-title" class="m-0 text-[1.2rem] font-semibold">Style mapping</h2>
		<CtrlButton function="modal.CLOSE" onclick={onclose} />
	</div>

	<div class="overflow-auto px-5 py-4">
		<p class="mt-0 max-w-5xl {colors.textSecondary}">
			The combined font is built once per output style. For each output style, each family of the
			inheritance orders contributes the glyphs of one of its style files. Style <em>names</em> differ
			between families (Oblique and Italic, Book and Regular, Demi and SemiBold), so by default a file
			is picked by the numbers every font carries, its weight class and its slant:
		</p>
		<ol class="mt-0 max-w-5xl list-decimal pl-6 {colors.textSecondary}">
			<li>
				a file you pick below (saved as <span class="font-mono">[styles.&lt;Output&gt;]</span> in the
				config) always wins;
			</li>
			<li>
				only files with the same slant are considered: an italic style is never served by an upright
				file, and nothing is slanted artificially;
			</li>
			<li>
				among them the weight equal to the output style's, else the nearest (the lighter one when two
				are equally near).
			</li>
		</ol>
		<p class="mt-0 max-w-5xl {colors.textSecondary}">
			Medium (500) and Black (900) are different weights and are never treated as the same style. The
			output styles themselves are listed in <span class="font-mono">[output] styles</span> of the
			config.
		</p>

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
			<table class="mt-4 border-collapse [--select-width:28rem]">
				<thead>
					<tr>
						<th
							class="border px-3 py-1 text-left font-semibold {colors.border} {colors.quietControlBackground}"
						>
							Font family
						</th>
						{#each map.outputStyles as style (style)}
							<th
								class="border px-3 py-1 text-left font-semibold {colors.border} {colors.quietControlBackground}"
							>
								{style}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each families as family (family)}
						<tr>
							<td class="border px-3 py-1 align-top font-semibold {colors.border}">
								{consoleStore.nameOf(family)}
							</td>
							{#each map.outputStyles as style (style)}
								{@const entry = map.entries[style]?.[family]}
								<td class="border px-3 py-1 align-top {colors.border}">
									<Dropdown
										class="w-(--select-width)"
										value={entry?.overridden ? (entry.file ?? '') : ''}
										options={[
											{ value: '', label: automaticLabel(family, style) },
											...(map.families[family] ?? []).map((file) => ({
												value: file.file,
												label: describe(file)
											}))
										]}
										onchange={(file) => choose(style, family, file)}
									/>
									<div
										class="mt-0.5 w-(--select-width) text-[0.8em] {entry?.file
											? colors.textTertiary
											: colors.textError}"
									>
										{entry?.reason ?? ''}
									</div>
								</td>
							{/each}
						</tr>
					{/each}
				</tbody>
			</table>
		{/if}
	</div>
</div>
