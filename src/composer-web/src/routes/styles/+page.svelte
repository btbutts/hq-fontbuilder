<script lang="ts">
	import { postStyle } from '#lib/api.js';
	import { consoleStore } from '#lib/console.svelte.js';

	const snapshot = $derived(consoleStore.state);
	const map = $derived(snapshot?.styleMap ?? null);
	const families = $derived(Object.keys(map?.families ?? {}));

	let error = $state<string | null>(null);

	async function choose(style: string, family: string, value: string): Promise<void> {
		const result = await postStyle(style, family, value === '' ? null : value);
		error = result.ok ? null : (result.error ?? 'unknown error');
		await consoleStore.refresh();
	}
</script>

<p><a href="/" class="text-[#1b4965] underline">← coverage table</a></p>
<h1 class="mb-1 text-[1.4rem] font-semibold">Style mapping</h1>
<p class="mt-0 max-w-5xl text-[#555]">
	The combined font is built once per output style. For each output style, each family of the
	inheritance orders contributes the glyphs of one of its style files. Style <em>names</em> differ
	between families (Oblique and Italic, Book and Regular, Demi and SemiBold), so by default a file is
	picked by the numbers every font carries, its weight class and its slant:
</p>
<ol class="mt-0 max-w-5xl text-[#555]">
	<li>a file you pick below (saved as <span class="font-mono">[styles.&lt;Output&gt;]</span> in the config) always wins;</li>
	<li>only files with the same slant are considered: an italic style is never served by an upright file, and nothing is slanted artificially;</li>
	<li>among them the weight equal to the output style's, else the nearest (the lighter one when two are equally near).</li>
</ol>
<p class="mt-0 max-w-5xl text-[#555]">
	Medium (500) and Black (900) are different weights and are never treated as the same style. The output
	styles themselves are listed in <span class="font-mono">[output] styles</span> of the config.
</p>

{#if error}
	<p class="mt-2 text-[#b02e2e]">{error}</p>
{/if}

{#if map === null}
	<p class="mt-4 text-[#555]">{consoleStore.error ?? 'loading…'}</p>
{:else if families.length === 0}
	<p class="mt-4 text-[#555]">
		No family is used by any glyph group yet. Choose families in the coverage table first.
	</p>
{:else}
	<table class="mt-4 border-collapse">
		<thead>
			<tr>
				<th class="border border-[#b9b9bd] bg-[#f0f0f4] px-3 py-1 text-left font-semibold">
					Output style
				</th>
				{#each families as family (family)}
					<th class="border border-[#b9b9bd] bg-[#f0f0f4] px-3 py-1 text-left font-semibold">
						{family}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each map.outputStyles as style (style)}
				<tr>
					<td class="border border-[#b9b9bd] px-3 py-1 align-top font-semibold">{style}</td>
					{#each families as family (family)}
						{@const entry = map.entries[style]?.[family]}
						<td class="border border-[#b9b9bd] px-3 py-1 align-top">
							<select
								class="max-w-[22rem] rounded border border-[#b9b9bd] bg-white px-1 py-0.5"
								value={entry?.overridden ? entry.file : ''}
								onchange={(event) => choose(style, family, event.currentTarget.value)}
							>
								<option value="">
									automatic{entry?.file && !entry.overridden ? `: ${entry.file}` : ''}
								</option>
								{#each map.families[family] ?? [] as file (file.file)}
									<option value={file.file}>
										{file.file} — {file.style} ({file.weight}{file.italic ? ', italic' : ''})
									</option>
								{/each}
							</select>
							<div
								class="mt-0.5 max-w-[22rem] text-[0.8em] {entry?.file
									? 'text-[#777]'
									: 'text-[#b02e2e]'}"
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
