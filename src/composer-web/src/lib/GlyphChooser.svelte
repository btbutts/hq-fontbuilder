<script lang="ts">
	import GlyphCell from './GlyphCell.svelte';
	import type { CellGeometry } from './glyphLayout';

	export interface Candidate {
		family: string;
		/** CSS font-family name the family's reference style is loaded under */
		cssName: string;
		color: string;
		/** position in the inheritance order, 1 for the first choice */
		rank: number;
	}

	interface Props {
		codepoint: number;
		candidates: Candidate[];
		/** the family that currently draws the glyph */
		current: string;
		/** true when the user pinned the glyph, over the inheritance order */
		pinned: boolean;
		geometry: CellGeometry;
		/** where the clicked cell is, in viewport pixels */
		anchor: { left: number; top: number; bottom: number };
		onchoose: (family: string | null) => void;
		onclose: () => void;
	}

	let { codepoint, candidates, current, pinned, geometry, anchor, onchoose, onclose }: Props =
		$props();

	const POPOVER_WIDTH = 420;
	const POPOVER_HEIGHT = 260;

	const code = $derived(codepoint.toString(16).toUpperCase().padStart(4, '0'));
	const left = $derived(
		Math.max(8, Math.min(anchor.left, (globalThis.innerWidth ?? 1200) - POPOVER_WIDTH - 8))
	);
	const below = $derived(anchor.bottom + POPOVER_HEIGHT < (globalThis.innerHeight ?? 800));
	const top = $derived(below ? anchor.bottom + 6 : Math.max(8, anchor.top - POPOVER_HEIGHT - 6));
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && onclose()} />

<!-- a click anywhere else closes the pop-out -->
<button
	type="button"
	class="fixed inset-0 z-20 cursor-default border-0 bg-transparent"
	aria-label="close"
	onclick={onclose}
></button>

<div
	role="dialog"
	aria-label="Choose the glyph for U+{code}"
	class="fixed z-30 max-w-[min(90vw,420px)] rounded border border-[#b9b9bd] bg-white p-3 shadow-xl"
	style:left="{left}px"
	style:top="{top}px"
>
	<p class="m-0 mb-2 text-[0.9em] text-[#333]">
		<span class="font-mono font-semibold">U+{code}</span> — which family draws this glyph?
	</p>
	<div class="flex flex-wrap gap-2">
		{#each candidates as candidate (candidate.family)}
			<button
				type="button"
				class="cursor-pointer rounded border bg-white p-1.5 text-center hover:bg-[#eef3f7] {candidate.family === current
					? 'border-2 border-[#1b4965]'
					: 'border-[#b9b9bd]'}"
				onclick={() => onchoose(candidate.family)}
			>
				<GlyphCell
					{codepoint}
					present
					fontFamily={candidate.cssName}
					{geometry}
					accent={candidate.color}
				/>
				<span class="mt-1 block max-w-30 truncate text-[0.8em]" title={candidate.family}>
					{candidate.rank}. {candidate.family}{candidate.family === current ? ' ✓' : ''}
				</span>
			</button>
		{/each}
	</div>
	{#if pinned}
		<button
			type="button"
			class="mt-3 cursor-pointer rounded border border-[#b9b9bd] bg-[#f0f0f4] px-2 py-1 text-[0.85em]"
			onclick={() => onchoose(null)}
		>
			use the inheritance order again
		</button>
	{/if}
</div>
