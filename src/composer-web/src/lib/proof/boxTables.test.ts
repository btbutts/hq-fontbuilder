import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ARM_GLYPHS } from './armGlyphs.ts';
import { PROOF_TABLES, doubleTable, drawTable, uniform } from './boxTables.ts';

test('every light and heavy combination of arms has a glyph', () => {
	assert.equal(Object.keys(ARM_GLYPHS).length, 80);
	assert.equal(new Set(Object.values(ARM_GLYPHS)).size, 80);
});

test('a thin 2 x 2 table is drawn with the light corner, tee and cross glyphs', () => {
	assert.deepEqual(drawTable({ rows: 2, cols: 2, fill: 1, h: uniform(1), v: uniform(1) }), [
		'┌─┬─┐',
		'│ │ │',
		'├─┼─┤',
		'│ │ │',
		'└─┴─┘'
	]);
});

test('a heavy 1 x 1 table is drawn with the heavy glyphs', () => {
	assert.deepEqual(drawTable({ rows: 1, cols: 1, fill: 2, h: uniform(2), v: uniform(2) }), [
		'┏━━┓',
		'┃  ┃',
		'┗━━┛'
	]);
});

test('a thick top half over a thin bottom half meets in the mixed junctions', () => {
	const lines = PROOF_TABLES.find((table) => table.title === 'Thick top, thin bottom')?.lines;
	assert.ok(lines);
	assert.equal(lines[0]?.[0], '┏');
	assert.equal(lines.at(-1)?.[0], '└');
	// the middle line: nothing left, a light arm right, a heavy arm up and a light one down
	assert.equal(lines[4]?.[0], String.fromCodePoint(ARM_GLYPHS['0121'] ?? 0));
	assert.equal(lines[4]?.[0], '┞');
});

test('the bottom half of a thin-top table is heavy, the right half of a thin-left one too', () => {
	const bottom = PROOF_TABLES.find((table) => table.title === 'Thin top, thick bottom')?.lines;
	assert.ok(bottom);
	assert.equal(bottom[1]?.[0], '│');
	assert.equal(bottom[5]?.[0], '┃');
	assert.equal(bottom[7]?.[0], '┃');
	assert.equal(bottom[0]?.[0], '┌');
	assert.equal(bottom.at(-1)?.[0], '┗');
	const right = PROOF_TABLES.find((table) => table.title === 'Thin left, thick right')?.lines;
	assert.ok(right);
	assert.equal(right[1]?.[0], '│');
	assert.equal(right[1]?.at(-1), '┃');
	assert.equal(right[0]?.slice(1, 3), '──');
	assert.equal(right[0]?.slice(-3, -1), '━━');
});

test('every table has equal-length lines and only the glyphs the font should have', () => {
	for (const table of PROOF_TABLES) {
		const widths = new Set(table.lines.map((line) => [...line].length));
		assert.equal(widths.size, 1, table.title);
		for (const char of table.lines.join('')) {
			const codepoint = char.codePointAt(0) ?? 0;
			assert.ok(char === ' ' || (codepoint >= 0x2500 && codepoint <= 0x259f), `${table.title}: ${char}`);
		}
	}
});

test('the tables are the thin, the thick, the four mixed halves, the double and the rounded', () => {
	assert.deepEqual(
		PROOF_TABLES.map((table) => table.title),
		[
			'Thin',
			'Thick',
			'Thick top, thin bottom',
			'Thin top, thick bottom',
			'Thick left, thin right',
			'Thin left, thick right',
			'Double',
			'Rounded corners'
		]
	);
});

test('a double table uses the double glyphs', () => {
	assert.deepEqual(doubleTable(1, 1, 1), ['╔═╗', '║ ║', '╚═╝']);
});
