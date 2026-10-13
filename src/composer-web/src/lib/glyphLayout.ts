/**
 * How the code points of a glyph group are arranged on the group page.
 *
 * Two modes, both built by `layoutCells` and drawn by GlyphGrid.svelte:
 *
 * - `rows` (the default): one row per natural subdivision, left aligned and never
 *   wrapped, so a column means the same thing in every row and in every style. A group
 *   with named rows (`alnum`: digits, capitals, lower case) uses them; any other group
 *   is cut into rows of 16 by code point, the layout of the Unicode charts (the column
 *   is the last hex digit, a row is `U+25A_`), with a spacer where the group has a hole.
 * - `wrap`: every cell in one run that wraps at the width of the window.
 *
 * Pure functions, no DOM: `glyphLayout.test.ts` exercises them with `node --test`.
 */

export interface LayoutCell {
	codepoint: number;
	present: boolean;
	/** CSS font family to draw this cell with, when it differs from the grid's */
	fontFamily?: string;
	/** colour that marks the family the glyph comes from */
	accent?: string;
	/** the glyph was pinned to its family by the user, over the inheritance order */
	pinned?: boolean;
	/** how many families could draw this glyph; above 1 the cell can be clicked to choose */
	alternatives?: number;
}

export interface LayoutRow {
	/** gutter label, or null when the mode shows none */
	label: string | null;
	/** cells in column order; null keeps a column empty so the others stay aligned */
	cells: (LayoutCell | null)[];
}

export type LayoutMode = 'rows' | 'wrap';

/** Cell geometry in em of the base family, and the size one em is drawn at. */
export interface CellGeometry {
	emPx: number;
	cellW: number;
	cellH: number;
	ascent: number;
}

/** The cell of the base family (or a plausible default) as a geometry at `emPx`. */
export function geometryFor(
	base: { cellAdvance: number; unitsPerEm: number; ascent: number; descent: number } | null,
	emPx: number
): CellGeometry {
	if (!base) return { emPx, cellW: 0.6, cellH: 1.2, ascent: 0.93 };
	return {
		emPx,
		cellW: base.cellAdvance / base.unitsPerEm,
		cellH: (base.ascent - base.descent) / base.unitsPerEm,
		ascent: base.ascent / base.unitsPerEm
	};
}

// The code label ("U+0030", 10px mono) is wider than a narrow cell, so every glyph gets a
// slot at least this wide, with the cell box centred in it.
const MIN_SLOT_PX = 46;
const SLOT_PADDING_PX = 10;

/** Width in px of the slot one glyph (cell box plus its label) occupies. */
export function slotWidth(geometry: CellGeometry): number {
	return Math.max(MIN_SLOT_PX, Math.round(geometry.cellW * geometry.emPx) + SLOT_PADDING_PX);
}

interface NamedRow {
	label: string;
	low: number;
	high: number;
}

/** Groups whose natural rows are not 16 code points wide. */
const NAMED_ROWS: Record<string, NamedRow[]> = {
	alnum: [
		{ label: '0–9', low: 0x30, high: 0x39 },
		{ label: 'A–Z', low: 0x41, high: 0x5a },
		{ label: 'a–z', low: 0x61, high: 0x7a }
	]
};

const ROW_WIDTH = 16;

function hex(codepoint: number): string {
	return codepoint.toString(16).toUpperCase().padStart(4, '0');
}

function hexRows(cells: LayoutCell[]): LayoutRow[] {
	const byRow = new Map<number, (LayoutCell | null)[]>();
	for (const cell of cells) {
		const row = Math.floor(cell.codepoint / ROW_WIDTH);
		let slots = byRow.get(row);
		if (!slots) {
			slots = new Array<LayoutCell | null>(ROW_WIDTH).fill(null);
			byRow.set(row, slots);
		}
		slots[cell.codepoint % ROW_WIDTH] = cell;
	}
	return [...byRow.entries()]
		.sort(([a], [b]) => a - b)
		.map(([row, slots]) => {
			let end = slots.length;
			while (end > 0 && slots[end - 1] === null) end -= 1;
			return { label: `U+${hex(row * ROW_WIDTH).slice(0, -1)}_`, cells: slots.slice(0, end) };
		});
}

function namedRows(rows: NamedRow[], cells: LayoutCell[]): LayoutRow[] {
	return rows
		.map((row) => ({
			label: row.label,
			cells: cells.filter((cell) => cell.codepoint >= row.low && cell.codepoint <= row.high)
		}))
		.filter((row) => row.cells.length > 0);
}

/** Arrange `cells` (in code point order) for a group in the given mode. */
export function layoutCells(groupId: string, cells: LayoutCell[], mode: LayoutMode): LayoutRow[] {
	if (mode === 'wrap') return [{ label: null, cells }];
	const named = NAMED_ROWS[groupId];
	return named ? namedRows(named, cells) : hexRows(cells);
}
