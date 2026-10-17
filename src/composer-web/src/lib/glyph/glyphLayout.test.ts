import assert from 'node:assert/strict';
import { test } from 'node:test';
import { chooserGrid, layoutCells, type LayoutCell } from './glyphLayout.ts';

const ALNUM_ROWS = [{ label: '0-9', low: 0x30, high: 0x39 }, { label: 'A-Z', low: 0x41, high: 0x5a }, { label: 'a-z', low: 0x61, high: 0x7a }];

function cells(...ranges: [number, number][]): LayoutCell[] {
	const out: LayoutCell[] = [];
	for (const [low, high] of ranges) {
		for (let cp = low; cp <= high; cp += 1) out.push({ codepoint: cp, present: true });
	}
	return out;
}

test('alnum is stacked: digits, capitals, lower case, columns aligned', () => {
	const rows = layoutCells(ALNUM_ROWS, cells([0x30, 0x39], [0x41, 0x5a], [0x61, 0x7a]), 'rows');
	assert.deepEqual(
		rows.map((row) => [row.label, row.cells.length]),
		[
			['0-9', 10],
			['A-Z', 26],
			['a-z', 26]
		]
	);
	assert.equal(rows[0]?.cells[0]?.codepoint, 0x30);
	assert.equal(rows[1]?.cells[0]?.codepoint, 0x41);
	assert.equal(rows[2]?.cells[0]?.codepoint, 0x61);
});

test('wrap mode is one unlabelled run', () => {
	const all = cells([0x30, 0x39], [0x41, 0x5a]);
	const rows = layoutCells(ALNUM_ROWS, all, 'wrap');
	assert.equal(rows.length, 1);
	assert.equal(rows[0]?.label, null);
	assert.equal(rows[0]?.cells.length, 36);
});

test('other groups are cut in rows of 16 by code point, holes kept as spacers', () => {
	// Box drawing starts on a row boundary; U+25A0 block misses its first two code points.
	const rows = layoutCells([], cells([0x25a2, 0x25bf]), 'rows');
	assert.deepEqual(
		rows.map((row) => row.label),
		['U+25A_', 'U+25B_']
	);
	assert.equal(rows[0]?.cells.length, 16);
	assert.equal(rows[0]?.cells[0], null);
	assert.equal(rows[0]?.cells[1], null);
	assert.equal(rows[0]?.cells[2]?.codepoint, 0x25a2);
	// the column of a code point is its last hex digit, in every row
	assert.equal(rows[1]?.cells[0]?.codepoint, 0x25b0);
});

test('trailing holes are trimmed and five-digit code points keep their row label', () => {
	const rows = layoutCells([], cells([0xf0000, 0xf0002]), 'rows');
	assert.deepEqual(rows[0]?.label, 'U+F000_');
	assert.equal(rows[0]?.cells.length, 3);
});

test('the chooser grid: one row to three, then as square as it goes, five at most per row', () => {
	const shape = (count: number): string => {
		const { columns, rows } = chooserGrid(count);
		return `${columns}x${rows}`;
	};
	assert.deepEqual([1, 2, 3].map(shape), ['1x1', '2x1', '3x1']);
	assert.deepEqual([4, 5, 6, 7, 8, 9, 10].map(shape), ['2x2', '3x2', '3x2', '4x2', '4x2', '5x2', '5x2']);
	assert.deepEqual([11, 12, 13, 15].map(shape), ['4x3', '4x3', '5x3', '5x3']);
});
