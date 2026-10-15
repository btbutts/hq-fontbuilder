/**
 * The look of the console: every colour of the site is defined here, and nowhere else.
 *
 * `colors` maps a purpose ("the page background", "the text of a link") to the Tailwind
 * classes that paint it in light mode, followed by the `dark:` classes that paint it in
 * dark mode. A component never writes a colour; it uses the purpose:
 *
 *     <div class="p-4 {colors.pageBackground} {colors.textPrimary}">
 *
 * To change a colour, find its purpose below and edit the light value, the dark value, or
 * both. A value is anything Tailwind accepts: a Tailwind palette colour (`bg-neutral-900`),
 * a hex colour (`bg-[#191a1b]`), `rgb(...)` (`bg-[rgb(25_26_27)]`), a named colour ...
 *
 * Rules that keep this file honest:
 *  - Every class below is spelt out in full. Tailwind finds the classes it must generate by
 *    reading the source text, so a class built from pieces at run time would not exist.
 *  - One purpose, one entry: two purposes that happen to share a colour today still have
 *    their own entries, so that either can change alone.
 *  - A few entries repeat a colour inside the same string on purpose (a coverage cell and
 *    the ring it grows on hover are the same colour); each of those says so.
 *
 * The one stylesheet that remains, `app.css`, only loads Tailwind and tells it that
 * `dark:` follows the `dark` class on <html>, which `theme` below toggles.
 */

const THEME_STORAGE_KEY = 'fc-theme';

function initialDark(): boolean {
	if (typeof document === 'undefined') return false;
	return document.documentElement.classList.contains('dark');
}

/**
 * Light or dark theme. The first choice follows the system; after that the user's switch
 * wins and is remembered by the browser. app.html applies it before first paint; this
 * keeps the switch and the `dark` class on <html> (which makes every `dark:` class in
 * `colors` apply) in step afterwards.
 */
class Theme {
	dark = $state(initialDark());

	set(dark: boolean): void {
		this.dark = dark;
		document.documentElement.classList.toggle('dark', dark);
		try {
			localStorage.setItem(THEME_STORAGE_KEY, dark ? 'dark' : 'light');
		} catch {
			// private window or blocked storage: the choice just lasts for this page
		}
	}

	toggle(): void {
		this.set(!this.dark);
	}
}

export const theme = new Theme();

/** The blur at `floating.blur` = 1, in px: the setting is a fraction of this. */
const MAX_BLUR_PX = 40;

/**
 * How the floating surfaces look: tooltips, the glyph chooser pop-up and the toolbar's menu
 * (not the dialogs: Style mapping, Pick font styles, Clear all families). One place, one
 * setting for all of them, which is why it is not in `colors`: that table holds the colour
 * of each purpose, this holds what they share.
 *
 *     <div class="{floating.radius} {colors.popoverTint}" style={floating.style}>
 *
 * `transparency` 0..1 is how much of what is behind shows through the surface's own colour
 * (`colors.tooltipTint`, `colors.popoverTint`); `blur` 0..1 is how much of that is blurred,
 * as a fraction of 40px; `radius` is the corner radius, a Tailwind class. Change them at
 * run time too (`floating.blur = 0.3`): the surfaces follow.
 */
class FloatingSurface {
	transparency = $state(0.25);
	blur = $state(0.25);
	radius = 'rounded-lg';

	/** Inline style that paints the tint at the chosen opacity and blurs what is behind. */
	get style(): string {
		const opacity = Math.round((1 - this.transparency) * 100);
		const filter = `blur(${(this.blur * MAX_BLUR_PX).toFixed(1)}px)`;
		return (
			`background-color: color-mix(in srgb, var(--floating-tint) ${opacity}%, transparent);` +
			` backdrop-filter: ${filter}; -webkit-backdrop-filter: ${filter};`
		);
	}
}

export const floating = new FloatingSurface();

export const colors = {
	// ---- page ---------------------------------------------------------------------------

	/** Colour scheme of the browser's own widgets (scrollbars, the open list of a drop-down).
	 *  Not a colour of ours, but it has to follow the theme as well. Applied to <html>. */
	colorScheme: 'scheme-light dark:scheme-dark',

	/** Background of the whole page, and of everything that has no background of its own.
	 *  Applied to <html>, so it also paints the area behind an overscrolled page. */
	pageBackground: 'bg-[#ffffff] dark:bg-[#191a1b]',

	/** The deeper band at the top of a sub page and the toolbar that sticks under it; the
	 *  tooltip box. Darker than the page in dark mode, a shade off white in light mode. */
	bandBackground: 'bg-[#fafafa] dark:bg-[#121314]',

	/** Panel of the Style mapping dialog. */
	modalBackground: 'bg-[#ffffff] dark:bg-[#191a1b]',

	/** The dimmed page behind the Style mapping dialog. */
	modalOverlay: 'bg-[rgb(0_0_0/0.35)] dark:bg-[rgb(0_0_0/0.6)]',

	/** Shadow under the Style mapping dialog and under tooltips. */
	floatingShadow:
		'shadow-[0_8px_24px_rgb(0_0_0/0.22)] dark:shadow-[0_8px_24px_rgb(0_0_0/0.6)]',

	/** Background of the "which family draws this glyph?" pop-up and of the tiles in it. */
	popoverBackground: 'bg-[#ffffff] dark:bg-[#121314]',

	/** Shadow under that pop-up. */
	popoverShadow:
		'shadow-[0_20px_25px_-5px_rgb(0_0_0/0.1),0_8px_10px_-6px_rgb(0_0_0/0.1)] dark:shadow-[0_20px_25px_-5px_rgb(0_0_0/0.1),0_8px_10px_-6px_rgb(0_0_0/0.1)]',

	/** The colours of the tooltip box and of the pop-ups (the glyph chooser, the toolbar's menu)
	 *  before `floating` makes them see-through: not a background by itself, but the colour
	 *  `floating.style` mixes with what is behind. */
	tooltipTint: '[--floating-tint:#fafafa] dark:[--floating-tint:#121314]',
	popoverTint: '[--floating-tint:#ffffff] dark:[--floating-tint:#121314]',

	// ---- lines and controls -------------------------------------------------------------

	/** Colour of every border: table cells, buttons, drop-downs, panels, the toolbar's
	 *  bottom edge. */
	border: 'border-[#b9b9bd] dark:border-[#3b3d40]',

	/** Table header cells, and quiet buttons that sit on the page itself (Style mapping…,
	 *  Close, show more …). */
	quietControlBackground: 'bg-[#f0f0f4] dark:bg-[#212223]',

	/**
	 * What a button does to its own background under the pointer, whatever that background is:
	 * a flat veil of black in light mode (it darkens) and of white in dark mode (it lightens),
	 * painted over the background colour and under the text and icon. A button therefore needs
	 * one background colour only. The two `0.1` are the strength of the veil; change them
	 * together. Not applied to a disabled button.
	 */
	controlHoverTint:
		'enabled:hover:bg-[linear-gradient(rgb(0_0_0/0.1),rgb(0_0_0/0.1))] dark:enabled:hover:bg-[linear-gradient(rgb(255_255_255/0.1),rgb(255_255_255/0.1))]',

	/**
	 * The close button of a dialog. At rest it is the quiet grey in light mode and the darkest
	 * background of the theme in dark mode; under the pointer it turns red, the red of
	 * `buttonAccent` (kept as its own entry so that either can change alone). The two hover
	 * colours replace `controlHoverTint`, which a surface with its own hover leaves out. In light
	 * mode the icon turns white on the red; dark mode keeps its icon colour (`textPrimary`).
	 */
	closeButton: {
		rest: 'bg-[#f0f0f4] dark:bg-[#121314]',
		hover:
			'enabled:hover:bg-[#b02e2e] enabled:hover:text-white dark:enabled:hover:bg-[#d63838] dark:enabled:hover:text-[#cccccc]'
	},

	/** Buttons and drop-downs that sit on the dark band / toolbar (the reorder buttons, "add a
	 *  family", "clear all families"); lighter than the band so they stand out from it. */
	raisedControlBackground: 'bg-[#ffffff] dark:bg-[#191a1b]',

	/** Drop-downs inside the Style mapping dialog. */
	inputBackground: 'bg-[#ffffff] dark:bg-[#121314]',

	/**
	 * An icon that is the whole button, with no box or background of its own (the pencil that
	 * renames a style, and the save and undo icons that replace it while a name is typed).
	 * Quiet at rest, stronger under the pointer.
	 */
	bareIconButton:
		'text-[#555555] hover:text-[#1c1c1e] dark:text-[#e6e6e6] dark:hover:text-[#ffffff]',

	/** The toolbar's menu button: like `bareIconButton` at rest, the red of `textAccent2` under
	 *  the pointer. */
	menuIconButton:
		'text-[#555555] hover:text-[#b02e2e] dark:text-[#e6e6e6] dark:hover:text-[#d63838]',

	/** Outline drawn round a glyph cell that has keyboard focus. */
	focusOutline: 'focus-visible:outline-[#1b4965] dark:focus-visible:outline-[#0c5f9a]',

	/** Fill of every switch (the light/dark, "Preview Unfitted Glyphs", "Enable Glyph
	 *  Wrapping" and "Use this Font Family for the … Group" toggles) while it is on. */
	buttonAccent: 'bg-[#b02e2e] dark:bg-[#d63838]',

	/** Track of a switch while it is off. */
	toggleOff: 'bg-[#b9b9bd] dark:bg-[#3b3d40]',

	/** The round knob of a switch, and its shadow. */
	toggleKnob: 'bg-[#ffffff] dark:bg-[#121314]',
	toggleKnobShadow:
		'shadow-[0_1px_3px_0_rgb(0_0_0/0.1),0_1px_2px_-1px_rgb(0_0_0/0.1)]',

	// ---- text ---------------------------------------------------------------------------

	/** Body text, headings, tooltip titles; also the base colour of <html>. */
	textPrimary: 'text-[#1c1c1e] dark:text-[#cccccc]',

	/** Explanations under a heading, loading messages, tooltip detail lines, row labels. */
	textSecondary: 'text-[#555555] dark:text-[#a9aaab]',

	/** Fine print: code point captions under a glyph, "N code points", "none". */
	textTertiary: 'text-[#777777] dark:text-[#85868a]',

	/** Links (← coverage table, combined result →, a category name in "Composition so far")
	 *  and status text that is meant to be read as part of a link row. Blue in both themes. */
	textAccent1: 'text-[#1b4965] dark:text-[#1289de]',

	/** The red of the word "atomic" beside box-drawing and block-elements. Same colours as
	 *  `buttonAccent`. */
	textAccent2: 'text-[#b02e2e] dark:text-[#d63838]',

	/** Error messages, unsourced groups, problem fonts, the "leave out of this group" button. */
	textError: 'text-[#b02e2e] dark:text-[#d63838]',

	/** Cautions: "the styles of this family hold different glyphs of this group". */
	textWarning: 'text-[#9c7c00] dark:text-[#e6c56a]',

	/** The count of glyphs the base cell cuts off ("N glyphs are cut off"). */
	textClipped: 'text-[#c62828] dark:text-[#ff6b6b]',

	// ---- message boxes ------------------------------------------------------------------

	/** The box that reports a configuration file which does not parse. Its text is
	 *  `textError`. */
	errorBoxBorder: 'border-[#b02e2e] dark:border-[#ff8f86]',
	errorBoxBackground: 'bg-[#fdecec] dark:bg-[#381d1d]',

	/** The box that lists pinned glyphs that cannot be honoured. */
	warningBoxBorder: 'border-[#9c7c00] dark:border-[#e6c56a]',
	warningBoxBackground: 'bg-[#fff8e1] dark:bg-[#30270e]',

	// ---- a drawn glyph ------------------------------------------------------------------

	/** The glyph itself (SVG text). */
	glyphInk: 'fill-[#1c1c1e] dark:fill-[#e6e6e6]',

	/** The dashed line every glyph rests on (the baseline). */
	glyphBaselineAccent: 'stroke-[#d24a4a] dark:stroke-[#e0625d]',

	/** Background of a glyph's cell, and the outline of the cell. */
	glyphBoxBackground: 'bg-[#ffffff] dark:bg-[#121314]',
	glyphBoxOutline: 'stroke-[#b9b9bd] dark:stroke-[#3b3d40]',

	/** Outline of a cell whose glyph the base cell cuts off (shown for unfitted glyphs). */
	glyphBoxClippedOutline: 'stroke-[#c62828] dark:stroke-[#d63838]',

	/** Hatching of a cell whose font has no glyph for the code point. */
	glyphBoxMissing:
		'bg-[repeating-linear-gradient(135deg,#f3f3f6_0_4px,#e2e2e8_4px_5px)] dark:bg-[repeating-linear-gradient(135deg,#1a1b1c_0_4px,#2b2d2f_4px_5px)]',

	/** The ring marker's inside (a glyph more than one family has; click it). Its edge takes
	 *  the colour of the family that draws the glyph, see `family`. */
	glyphMarkerRingFill: 'fill-[#ffffff] dark:fill-[#121314]',

	/** Border of the tile of the family that currently draws the glyph, in the pop-up. */
	glyphChoiceCurrentBorder: 'border-[#1b4965] dark:border-[#0c5f9a]',

	// ---- the coverage table of the main page --------------------------------------------
	//
	// A cell has a tone (all the group's code points, some of them, none) and a state:
	//   rest      the family is not in the group's inheritance order;
	//   selected  the family is in it (one or two shades darker in light mode, lighter in
	//             dark mode);
	//   hover     under the pointer: it takes the selected colour and grows over its
	//             neighbours as a 4px ring of that same colour. The ring repeats the
	//             selected colour: change `selected` and `hover` together.
	// `text` is the colour of the numbers in the cell.

	/** Cells of a family that holds every code point of the group (green / olive). */
	glyphCellFull: {
		rest: 'bg-[#d8f3dc] dark:bg-[#643C96]',
		selected: 'bg-[#b4e4be] dark:bg-[#503078]',
		hover:
			'hover:bg-[#b4e4be] hover:shadow-[0_0_0_4px_#b4e4be,0_4px_10px_rgb(0_0_0/0.25)] dark:hover:bg-[#503078] dark:hover:shadow-[0_0_0_4px_#503078,0_4px_10px_rgb(0_0_0/0.25)]',
		text: 'text-[#1f5a40] dark:text-[#ebebeb]'
	},

	/** Cells of a family that holds some code points of the group (yellow / blue). */
	glyphCellPartial: {
		rest: 'bg-[#fff3cd] dark:bg-[#0c5f9a]',
		selected: 'bg-[#ffe699] dark:bg-[#08426b]',
		hover:
			'hover:bg-[#ffe699] hover:shadow-[0_0_0_4px_#ffe699,0_4px_10px_rgb(0_0_0/0.25)] dark:hover:bg-[#08426b] dark:hover:shadow-[0_0_0_4px_#08426b,0_4px_10px_rgb(0_0_0/0.25)]',
		text: 'text-[#6f5600] dark:text-[#ebebeb]'
	},

	/** Cells of a family that holds none of the group's code points (grey). */
	glyphCellNone: {
		rest: 'bg-[#ececf0] dark:bg-[#1e1f20]',
		selected: 'bg-[#d9d9df] dark:bg-[#2c2e30]',
		hover:
			'hover:bg-[#d9d9df] hover:shadow-[0_0_0_4px_#d9d9df,0_4px_10px_rgb(0_0_0/0.25)] dark:hover:bg-[#2c2e30] dark:hover:shadow-[0_0_0_4px_#2c2e30,0_4px_10px_rgb(0_0_0/0.25)]',
		text: 'text-[#77777d] dark:text-[#7d7f82]'
	},

	// ---- families -----------------------------------------------------------------------

	/**
	 * One colour per position in an inheritance order (the first family, the second ...; the
	 * ninth starts over). Used for the swatch in "Font inheritance order", the bar under a
	 * glyph's cell, and the pinned / choosable markers. Each entry sets the *text* colour,
	 * so one entry serves them all: use `bg-current`, `fill-current` or `stroke-current`
	 * next to it. The first is the link blue of `textAccent1`.
	 */
	family: [
		'text-[#1b4965] dark:text-[#1289de]',
		'text-[#c1440e] dark:text-[#ff9e6b]',
		'text-[#2d6a4f] dark:text-[#7fd6a0]',
		'text-[#7b2cbf] dark:text-[#c79bff]',
		'text-[#9a6b00] dark:text-[#e6c56a]',
		'text-[#0077b6] dark:text-[#6bc2f2]',
		'text-[#b5179e] dark:text-[#ff8fd8]',
		'text-[#5f6c37] dark:text-[#b5c77a]'
	]
} as const;
