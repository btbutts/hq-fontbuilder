/** A cell in em, as the page receives it: the advance, and the ascent and descent from the baseline. */
export interface Cell {
	width: number;
	ascent: number;
	descent: number;
}

/** The same font in its own units. */
export interface Units {
	upm: number;
	advance: number;
	ascent: number;
	descent: number;
}

/** A cell in whole device pixels: what a console gives every character. */
export interface PixelCell {
	w: number;
	h: number;
}

/** CSS pixels: the smallest and the largest cell the page draws. */
export const MIN_CELL_CSS_PX = 8;
export const MAX_CELL_CSS_PX = 48;

/** The cell widths offered, in whole device pixels. */
export function cellWidths(dpr: number): number[] {
	const widths: number[] = [];
	for (let w = Math.round(MIN_CELL_CSS_PX * dpr); w <= Math.round(MAX_CELL_CSS_PX * dpr); w += 1) {
		widths.push(w);
	}
	return widths;
}

/** The whole-pixel cell of a width: the height the font's cell has at that width, rounded. */
export function pixelCell(width: number, cell: Cell): PixelCell {
	return { w: width, h: Math.round((width * (cell.ascent - cell.descent)) / cell.width) };
}

/** The font size (CSS px) at which a character's advance is exactly `width` device pixels. */
export function textFontSize(width: number, dpr: number, cell: Cell): number {
	return width / (cell.width * dpr);
}

export interface Placement {
	/** CSS px from the left of the table to the cell */
	x: number;
	/** CSS px from the top of the table to the baseline of the row */
	baseline: number;
	/** CSS px per font unit, across and up */
	sx: number;
	sy: number;
}

/**
 * Where a glyph of font units goes in the table and by how much it is scaled: its advance
 * becomes the cell's width and its ascent plus descent the cell's height, so that
 * the cell edges fall on whole device pixels.
 */
export function glyphTransform(
	column: number,
	row: number,
	cell: PixelCell,
	units: Units,
	dpr: number
): Placement {
	const width = cell.w / dpr;
	const height = cell.h / dpr;
	const sx = width / units.advance;
	const sy = height / (units.ascent - units.descent);
	return { x: column * width, baseline: row * height + units.ascent * sy, sx, sy };
}

export interface EdgeRules {
	/** CSS px of the left side of each vertical rule */
	vertical: number[];
	horizontal: number[];
	/** one device pixel, in CSS px */
	thickness: number;
}

/**
 * The rules that mark the edges of the cells of a table. The last of each is drawn inside
 * the table (one device pixel before the end), where it is not cut off.
 */
export function edgeRules(columns: number, rows: number, cell: PixelCell, dpr: number): EdgeRules {
	const thickness = 1 / dpr;
	const along = (count: number, size: number): number[] =>
		Array.from({ length: count + 1 }, (_, index) =>
			index === count ? (count * size) / dpr - thickness : (index * size) / dpr
		);
	return { vertical: along(columns, cell.w), horizontal: along(rows, cell.h), thickness };
}
