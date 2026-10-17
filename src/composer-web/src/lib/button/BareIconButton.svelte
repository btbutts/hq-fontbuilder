<script lang="ts">
	import { colors } from '../styles.svelte.ts';
	import { tip } from '../tooltip/tooltip.ts';
	import type { IconComponent } from './presets.ts';

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
		/** for a button that opens a pop-up: whether it is open */
		expanded?: boolean;
		/** text colour classes (rest and hover), instead of `colors.bareIconButton` */
		colorClasses?: string;
	}

	let { icon: Icon, label, onclick, size = 18, expanded, colorClasses }: Props = $props();
</script>

<button
	type="button"
	class="inline-flex shrink-0 cursor-pointer items-center justify-center rounded-sm p-0 focus-visible:outline-2 focus-visible:outline-offset-1 {colorClasses ?? colors.bareIconButton} {colors.focusOutline}"
	aria-label={label}
	aria-haspopup={expanded === undefined ? undefined : 'true'}
	aria-expanded={expanded}
	{...tip(undefined, label)}
	{onclick}
>
	<Icon {size} stroke={2} class="block" />
</button>
