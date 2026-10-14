/**
 * The buttons of the console, as data. `CtrlButton.svelte` is the only component that draws
 * a button; what differs between buttons lives here, in two tables:
 *
 *  - `surfaces`: the backgrounds a button can sit on, each with the border that goes with
 *    it. The background is a single colour; the hover effect is derived from it (see
 *    `colors.controlHoverTint`), so a surface never names a hover colour.
 *  - `presets`: the buttons that appear more than once, or are a fixed part of a control
 *    (the reorder buttons, the dialog's close button). A preset is picked by name,
 *    `<CtrlButton function="reorder.UP">`, and fixes the icon, size, surface, colours and
 *    placement of that button.
 *
 * A button that appears once needs no preset: `<CtrlButton surface="raised" padding="px-2
 * py-0.5">label</CtrlButton>`. Anything a preset fixes can still be overridden on the use,
 * and an override replaces the preset's value for that slot as a whole.
 *
 * Like `colors`, every class here is spelt out in full so that Tailwind finds it.
 */
import IconCaretDownFilled from '@tabler/icons-svelte/icons/caret-down-filled';
import IconCaretUpFilled from '@tabler/icons-svelte/icons/caret-up-filled';
import IconArrowLeft from '@tabler/icons-svelte/icons/arrow-left';
import IconArrowRight from '@tabler/icons-svelte/icons/arrow-right';
import IconMinus from '@tabler/icons-svelte/icons/minus';
import IconPlus from '@tabler/icons-svelte/icons/plus';
import IconX from '@tabler/icons-svelte/icons/x';
import { colors } from '../styles.svelte';

/** Any Tabler icon: they all share one props type. */
export type IconComponent = typeof IconX;

export interface SurfaceStyle {
	background: string;
	border: string;
	/** hover classes of a surface that has its own; the others get `colors.controlHoverTint` */
	hover?: string;
}

const surfaceTable = {
	/** Buttons that sit on the page itself: Style Mapping, show more. */
	quiet: { background: colors.quietControlBackground, border: `border ${colors.border}` },
	/** Buttons that sit on the band or the toolbar: they must stand out from it. */
	raised: { background: colors.raisedControlBackground, border: `border ${colors.border}` },
	/** Buttons inside the "which family draws this glyph?" pop-up. */
	popover: { background: colors.popoverBackground, border: `border ${colors.border}` },
	/** No box of its own: the content is the button (the cell of a glyph grid). */
	bare: { background: 'bg-transparent', border: 'border-0' },
	/** The close button of a dialog: grey, or the darkest background, and red when hovered. */
	close: {
		background: colors.closeButton.rest,
		border: `border ${colors.border}`,
		hover: colors.closeButton.hover
	}
} satisfies Record<string, SurfaceStyle>;

export type Surface = keyof typeof surfaceTable;

/** The background a button is painted on, and the border drawn round it. */
export const surfaces: Record<Surface, SurfaceStyle> = surfaceTable;

/** What a preset can fix; every field is optional and each is one slot of the button. */
export interface ButtonPreset {
	surface?: Surface;
	/** drawn instead of (or before) the text */
	icon?: IconComponent;
	/** px, the width and height of the icon */
	iconSize?: number;
	/** width and height of the box, with the classes that centre the icon in it */
	size?: string;
	/** padding classes: for a button whose box is its content */
	padding?: string;
	fontSize?: string;
	fontWeight?: string;
	textColor?: string;
	/** where it sits in its container (margins, `justify-self-*`) */
	placement?: string;
	/** draw the icon after the text instead of before it */
	iconAfter?: boolean;
	/** accessible name and tooltip of a button that has no text */
	label?: string;
	/** tooltip of a button that has text */
	tooltip?: string;
}

// An icon is a block, so a button that holds nothing else has no line of text to be as tall
// as; these boxes are as tall as the one line (`1lh`) and the border (and padding) that a
// text button would have, and centre the icon in it.

/** A square, each side one line of text and its border. */
const REORDER_BOX = 'inline-flex size-[calc(1lh+2px)] items-center justify-center';

/** One line of text, 2px of padding above and below it, and the border. */
const CLOSE_BOX = 'inline-flex h-[calc(1lh+6px)] items-center justify-center';

const definitions = {
	/** "earlier in the order": the ▲ of a row of the inheritance order. */
	'reorder.UP': {
		surface: 'raised',
		icon: IconCaretUpFilled,
		iconSize: 20,
		size: REORDER_BOX,
		placement: 'ml-4 justify-self-center',
		label: 'earlier in the order'
	},
	/** "later in the order": the ▼. */
	'reorder.DOWN': {
		surface: 'raised',
		icon: IconCaretDownFilled,
		iconSize: 20,
		size: REORDER_BOX,
		placement: 'justify-self-center',
		label: 'later in the order'
	},
	/** "leave out of this group": the − , in the colour of an error. */
	'reorder.REMOVE': {
		surface: 'raised',
		icon: IconMinus,
		iconSize: 20,
		size: REORDER_BOX,
		textColor: colors.textError,
		placement: 'justify-self-center',
		label: 'leave out of this group'
	},
	/** A style type that is left out: click to consider it. */
	'styles.INCLUDE': {
		surface: 'raised',
		icon: IconPlus,
		iconSize: 20,
		size: REORDER_BOX,
		label: 'consider this style'
	},
	/** A style type that is considered: click to leave it out. */
	'styles.EXCLUDE': {
		surface: 'raised',
		icon: IconX,
		iconSize: 20,
		size: REORDER_BOX,
		label: 'leave this style out'
	},
	/** The close button of a dialog (the Style mapping one is the first): red under the pointer. */
	'modal.CLOSE': {
		surface: 'close',
		icon: IconX,
		iconSize: 18,
		size: CLOSE_BOX,
		padding: 'px-2.5',
		label: 'Close'
	},
	/** "← coverage table": the way back, on the band of a sub page. Text comes from the use. */
	'nav.BACK': {
		surface: 'raised',
		icon: IconArrowLeft,
		padding: 'px-2 py-0.5',
		fontSize: 'text-[0.9em]',
		placement: 'inline-flex items-center gap-1.5',
		tooltip: 'back to the table of font families and glyph categories'
	},
	/** "combined result →": on to the next page. Text comes from the use. */
	'nav.FORWARD': {
		surface: 'raised',
		icon: IconArrowRight,
		iconAfter: true,
		padding: 'px-2 py-0.5',
		fontSize: 'text-[0.9em]',
		placement: 'inline-flex items-center gap-1.5',
		tooltip: 'the glyphs of this group as combined from the chosen families'
	},
	/** "show N more" under a long run of glyphs. Text comes from the use. */
	'list.SHOW_MORE': {
		surface: 'quiet',
		padding: 'px-3 py-1'
	}
} as const satisfies Record<string, ButtonPreset>;

export type ButtonFunction = keyof typeof definitions;

export const presets: Record<ButtonFunction, ButtonPreset> = definitions;

/** Used by a button for any slot that neither the use nor its preset sets. */
export const DEFAULT_SURFACE: Surface = 'quiet';
export const DEFAULT_PADDING = 'px-3 py-1';
export const DEFAULT_ICON_SIZE = 16;
