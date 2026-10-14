<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { HTMLButtonAttributes } from 'svelte/elements';
	import { colors } from '../styles.svelte';
	import { tip } from '../tooltip/tooltip';
	import {
		DEFAULT_ICON_SIZE,
		DEFAULT_PADDING,
		DEFAULT_SURFACE,
		presets,
		surfaces,
		type ButtonFunction,
		type Surface
	} from './presets';

	/**
	 * The one button of the console.
	 *
	 *     <CtrlButton function="reorder.UP" disabled={first} onclick={up} />
	 *     <CtrlButton surface="raised" padding="px-2 py-0.5" fontSize="text-[0.9em]">clear</CtrlButton>
	 *
	 * `function` picks a preset from `presets.ts`; every other prop overrides one slot of
	 * it. A slot is one string that is used whole: the component picks `use ?? preset ??
	 * default` per slot instead of concatenating classes, because two Tailwind classes that
	 * set the same property (`px-2`, `px-3`) are decided by their order in the stylesheet,
	 * not by their order in the attribute.
	 *
	 * Everything is listed here once: `surface`, `border`, `size`, `padding`, `fontSize`,
	 * `fontWeight`, `textColor`, `hover`; `class` is for placement only (margins, sticky,
	 * grid alignment). The background is one colour, and the hover effect is a veil over it
	 * (`colors.controlHoverTint`); give `hover` Tailwind classes to use a colour of your own.
	 */
	interface Props extends Omit<HTMLButtonAttributes, 'class' | 'children'> {
		/** a preset of `presets.ts`, e.g. `reorder.UP` */
		function?: ButtonFunction;
		/** accessible name and tooltip of a button without text; the preset has one */
		label?: string;
		/** tooltip text, instead of `label` */
		tooltip?: string;
		/** `quiet`, `raised`, `popover` or `bare`: the background and its border */
		surface?: Surface;
		/** border classes, instead of the surface's (e.g. a thicker, coloured border) */
		border?: string;
		/** width and height classes, for a button that is a fixed box (icons) */
		size?: string;
		/** padding classes, for a button whose box is its content */
		padding?: string;
		/** font-size class, e.g. `text-[0.9em]` */
		fontSize?: string;
		/** font-weight class, e.g. `font-medium` */
		fontWeight?: string;
		/** text colour class; the icon takes it too */
		textColor?: string;
		/** hover classes, instead of the tint over the surface */
		hover?: string;
		/** px, the width and height of the preset's icon */
		iconSize?: number;
		/** placement and layout: margins, `sticky`, `justify-self-*`, `flex-col`; added to the preset's */
		class?: string;
		children?: Snippet;
	}

	let {
		function: name,
		label,
		tooltip,
		surface,
		border,
		size,
		padding,
		fontSize,
		fontWeight,
		textColor,
		hover,
		iconSize,
		class: placement,
		type = 'button',
		children,
		...rest
	}: Props = $props();

	const preset = $derived(name ? presets[name] : undefined);
	const Icon = $derived(preset?.icon);
	const iconSizePx = $derived(iconSize ?? preset?.iconSize ?? DEFAULT_ICON_SIZE);
	const background = $derived(surfaces[surface ?? preset?.surface ?? DEFAULT_SURFACE]);
	// A button with an icon and no text has to say what it is, to screen readers and the pointer.
	const iconOnly = $derived(Icon !== undefined && children === undefined);
	const title = $derived(tooltip ?? preset?.tooltip ?? (iconOnly ? (label ?? preset?.label) : undefined));

	const box = $derived(size ?? preset?.size);

	const classes = $derived(
		[
			'cursor-pointer rounded disabled:opacity-30',
			background.background,
			border ?? background.border,
			box,
			// a fixed box has no padding of its own; any other box is sized by its content
			padding ?? preset?.padding ?? (box === undefined ? DEFAULT_PADDING : undefined),
			fontSize ?? preset?.fontSize,
			fontWeight ?? preset?.fontWeight,
			textColor ?? preset?.textColor,
			hover ?? background.hover ?? colors.controlHoverTint,
			// unlike the slots, `class` adds to the preset's placement instead of replacing it
			preset?.placement,
			placement
		]
			.filter((part) => part !== undefined && part !== '')
			.join(' ')
	);
</script>

<button
	{type}
	{...rest}
	class={classes}
	aria-label={iconOnly ? (label ?? preset?.label) : undefined}
	{...tip(undefined, title)}
>
	{#if Icon && !preset?.iconAfter}
		<Icon size={iconSizePx} stroke={2} class="shrink-0 align-middle" />
	{/if}
	{@render children?.()}
	{#if Icon && preset?.iconAfter}
		<Icon size={iconSizePx} stroke={2} class="shrink-0 align-middle" />
	{/if}
</button>
