<script lang="ts">
	import { colors } from '../styles.svelte';
	import { tip } from '../tooltip/tooltip';
	import type { IconComponent } from './presets';

	/**
	 * A button that is only an icon: no box, border or background (the pencil of a header
	 * cell). `label` is its accessible name and its tooltip.
	 *
	 *     <BareIconButton icon={IconPencil} label="Rename" onclick={begin} />
	 */
	interface Props {
		icon: IconComponent;
		label: string;
		onclick: () => void;
		/** px, the width and height of the icon */
		size?: number;
	}

	let { icon: Icon, label, onclick, size = 18 }: Props = $props();
</script>

<button
	type="button"
	class="inline-flex shrink-0 cursor-pointer items-center justify-center rounded-sm p-0 focus-visible:outline-2 focus-visible:outline-offset-1 {colors.bareIconButton} {colors.focusOutline}"
	aria-label={label}
	{...tip(undefined, label)}
	{onclick}
>
	<Icon {size} stroke={2} class="block" />
</button>
