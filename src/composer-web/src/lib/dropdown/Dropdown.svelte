<script lang="ts">
	import IconChevronDown from '@tabler/icons-svelte/icons/chevron-down';
	import { colors } from '../styles.svelte';

	export interface DropdownOption {
		value: string;
		label: string;
	}

	interface Props {
		value: string;
		options: DropdownOption[];
		/** called with the value of the option the user picked */
		onchange: (value: string) => void;
		/** `input` inside a dialog, `raised` on the band or the toolbar */
		surface?: 'input' | 'raised';
		/**
		 * true for a drop-down that is a menu rather than a setting: after a pick it shows
		 * `value` again (the placeholder option) instead of the pick
		 */
		momentary?: boolean;
		/** width, margins: the classes of the whole drop-down */
		class?: string;
	}

	let {
		value,
		options,
		onchange,
		surface = 'input',
		momentary = false,
		class: placement = ''
	}: Props = $props();

	const background = $derived(
		surface === 'raised' ? colors.raisedControlBackground : colors.inputBackground
	);

	// The browser draws its focus ring round a select after a mouse click as well (a select
	// always counts as "focus-visible"), and it stays until something else is clicked. A mouse
	// user gets no ring and, once a pick is made, no focus; a keyboard user keeps the ring.
	let pointerFocus = $state(false);
</script>

<!--
	A native <select> (keyboard, type-to-find and the system's own list of options all come
	with it) whose arrow is replaced by a Tabler icon drawn over its right end. The label's
	inset from the border (pl-2) and the arrow's (right-1.5 with a 16px icon, whose drawing
	has 4px of empty margin) are the same 8px, so the two sit alike in the box. pr-7 keeps
	the longest label clear of the icon.

	leading-[calc(1em+4.5px)] is the line height the browser's own select had, so that
	replacing the native arrow does not make the drop-down taller (1em + 4.5px + the 4px of
	padding and 2px of border is the 25.5px of a 15px select).
-->
<span class="relative inline-block {placement}">
	<select
		class="block w-full cursor-pointer appearance-none rounded border py-0.5 pr-7 pl-2 leading-[calc(1em+4.5px)] {colors.border} {background} {colors.textPrimary} {pointerFocus
			? 'outline-none'
			: ''}"
		{value}
		onpointerdown={() => (pointerFocus = true)}
		onkeydown={(event) => {
			// Escape closes the list of a drop-down that was opened with the mouse: done with it
			if (pointerFocus && event.key === 'Escape') event.currentTarget.blur();
			else pointerFocus = false;
		}}
		onblur={() => (pointerFocus = false)}
		onchange={(event) => {
			const select = event.currentTarget;
			const picked = select.value;
			if (momentary) select.value = value;
			if (pointerFocus) select.blur();
			onchange(picked);
		}}
	>
		{#each options as option (option.value)}
			<option value={option.value}>{option.label}</option>
		{/each}
	</select>
	<IconChevronDown
		size={16}
		stroke={2}
		class="pointer-events-none absolute top-1/2 right-1.5 -translate-y-1/2 {colors.textPrimary}"
	/>
</span>
