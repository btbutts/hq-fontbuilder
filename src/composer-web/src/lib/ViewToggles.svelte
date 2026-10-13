<script lang="ts">
	import { FULL_GRID_MAX } from './glyphLayout';
	import Toggle from './Toggle.svelte';
	import { viewOptions } from './viewOptions.svelte';

	interface Props {
		/** code points in the group: a group too large to draw whole always wraps */
		groupTotal: number;
	}

	let { groupTotal }: Props = $props();

	const alwaysWraps = $derived(groupTotal > FULL_GRID_MAX);
</script>

<Toggle
	label="Preview unfitted glyphs"
	title="show the glyphs as the donor font draws them, outlined red where the base cell cuts them off"
	checked={viewOptions.unfitted}
	onchange={(enabled) => (viewOptions.unfitted = enabled)}
/>
<Toggle
	label="Enable glyph wrapping"
	title={alwaysWraps
		? 'this group is always shown as a wrapping run'
		: 'one wrapping run of cells instead of stacked rows'}
	checked={viewOptions.layoutMode(groupTotal) === 'wrap'}
	disabled={alwaysWraps}
	onchange={(enabled) => viewOptions.setWrap(enabled)}
/>
