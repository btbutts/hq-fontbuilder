import { ARM_GLYPHS } from './armGlyphs.ts';

/** 0: no line, 1: light, 2: heavy. */
export type Weight = 0 | 1 | 2;

export interface TableSpec {
	rows: number;
	cols: number;
	/** how many characters of line lie between two junctions */
	fill: number;
	/** the horizontal line `col` of the line boundary `row` (0..rows, 0..cols-1) */
	h: (row: number, col: number) => Weight;
	/** the vertical line `row` of the junction column `col` (0..rows-1, 0..cols) */
	v: (row: number, col: number) => Weight;
}

const HORIZONTAL = [' ', '─', '━'];
const VERTICAL = [' ', '│', '┃'];

export function uniform(weight: Weight): () => Weight {
	return () => weight;
}

function junction(spec: TableSpec, row: number, col: number): string {
	const left = col > 0 ? spec.h(row, col - 1) : 0;
	const right = col < spec.cols ? spec.h(row, col) : 0;
	const up = row > 0 ? spec.v(row - 1, col) : 0;
	const down = row < spec.rows ? spec.v(row, col) : 0;
	const glyph = ARM_GLYPHS[`${left}${right}${up}${down}`];
	return glyph === undefined ? ' ' : String.fromCodePoint(glyph);
}

/** The lines of a table of box glyphs: one junction per crossing, joined by the lines between. */
export function drawTable(spec: TableSpec): string[] {
	const lines: string[] = [];
	for (let row = 0; row <= spec.rows; row += 1) {
		let boundary = '';
		for (let col = 0; col <= spec.cols; col += 1) {
			boundary += junction(spec, row, col);
			if (col < spec.cols) boundary += (HORIZONTAL[spec.h(row, col)] ?? ' ').repeat(spec.fill);
		}
		lines.push(boundary);
		if (row === spec.rows) break;
		let between = '';
		for (let col = 0; col <= spec.cols; col += 1) {
			between += VERTICAL[spec.v(row, col)] ?? ' ';
			if (col < spec.cols) between += ' '.repeat(spec.fill);
		}
		lines.push(between);
	}
	return lines;
}

/** A table of double lines. */
export function doubleTable(rows: number, cols: number, fill: number): string[] {
	const edge = (row: number, left: string, middle: string, right: string): string => {
		let line = '';
		for (let col = 0; col <= cols; col += 1) {
			line += col === 0 ? left : col === cols ? right : middle;
			if (col < cols) line += '═'.repeat(fill);
		}
		return row >= 0 ? line : '';
	};
	const lines: string[] = [];
	for (let row = 0; row <= rows; row += 1) {
		lines.push(
			row === 0 ? edge(row, '╔', '╦', '╗') : row === rows ? edge(row, '╚', '╩', '╝') : edge(row, '╠', '╬', '╣')
		);
		if (row < rows) lines.push(('║' + ' '.repeat(fill)).repeat(cols) + '║');
	}
	return lines;
}

const ROWS = 4;
const COLS = 4;
const FILL = 2;

function table(h: TableSpec['h'], v: TableSpec['v']): string[] {
	return drawTable({ rows: ROWS, cols: COLS, fill: FILL, h, v });
}

/**
 * A table whose first (or last) half is heavy and whose other half is light, along rows or
 * columns. The line in the middle stays light, so the halves meet in the mixed junctions.
 * Lines lie on the boundaries 0..4 and between them are the segments 0..3.
 */
function halves(heavyFirst: boolean, along: 'row' | 'col'): TableSpec {
	const middle = ROWS / 2;
	const onBoundary = (position: number): Weight =>
		(heavyFirst ? position < middle : position > middle) ? 2 : 1;
	const onSegment = (position: number): Weight =>
		(heavyFirst ? position < middle : position >= middle) ? 2 : 1;
	return along === 'row'
		? { rows: ROWS, cols: COLS, fill: FILL, h: (row) => onBoundary(row), v: (row) => onSegment(row) }
		: { rows: ROWS, cols: COLS, fill: FILL, h: (_row, col) => onSegment(col), v: (_row, col) => onBoundary(col) };
}

function rounded(): string[] {
	const lines = table(uniform(1), uniform(1));
	const first = lines[0] ?? '';
	const last = lines.at(-1) ?? '';
	lines[0] = '╭' + first.slice(1, -1) + '╮';
	lines[lines.length - 1] = '╰' + last.slice(1, -1) + '╯';
	return lines;
}

function mixed(heavyFirst: boolean, along: 'row' | 'col'): string[] {
	return drawTable(halves(heavyFirst, along));
}

/** The tables of the proof: what has to join for a box to look like one drawing. */
export const PROOF_TABLES: { title: string; lines: string[] }[] = [
	{ title: 'Thin', lines: table(uniform(1), uniform(1)) },
	{ title: 'Thick', lines: table(uniform(2), uniform(2)) },
	{ title: 'Thick top, thin bottom', lines: mixed(true, 'row') },
	{ title: 'Thin top, thick bottom', lines: mixed(false, 'row') },
	{ title: 'Thick left, thin right', lines: mixed(true, 'col') },
	{ title: 'Thin left, thick right', lines: mixed(false, 'col') },
	{ title: 'Double', lines: doubleTable(ROWS, COLS, FILL) },
	{ title: 'Rounded corners', lines: rounded() }
];

/** Halves and quarters of Block Elements: each pair meets in the middle of the cell. */
export const BLOCK_SAMPLES: string[] = [
	'████ ▀▀▀▀ ▄▄▄▄',
	'▌▐▌▐ ▘▝▘▝ ▖▗▖▗',
	'▛▜▛▜ ▙▟▙▟ ▚▞▚▞',
	'░░░░ ▒▒▒▒ ▓▓▓▓'
];
