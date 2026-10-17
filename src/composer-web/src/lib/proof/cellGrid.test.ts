import assert from 'node:assert/strict';
import { test } from 'node:test';
import { cellWidths, edgeRules, glyphTransform, pixelCell, textFontSize } from './cellGrid.ts';

// the base cell of the fonts in use: 1233 x 2384 units of 2048
const CELL = { width: 1233 / 2048, ascent: 1901 / 2048, descent: -483 / 2048 };
const UNITS = { upm: 2048, advance: 1233, ascent: 1901, descent: -483 };

test('a cell is a whole number of device pixels wide and tall', () => {
	assert.deepEqual(pixelCell(15, CELL), { w: 15, h: 29 });
	assert.deepEqual(pixelCell(30, CELL), { w: 30, h: 58 });
	assert.deepEqual(pixelCell(17, CELL), { w: 17, h: 33 });
});

test('the widths offered are whole device pixels, in css pixels from 8 to 48', () => {
	assert.deepEqual(cellWidths(1).slice(0, 3), [8, 9, 10]);
	assert.equal(cellWidths(1).at(-1), 48);
	assert.deepEqual(cellWidths(2).slice(0, 3), [16, 17, 18]);
	assert.equal(cellWidths(2).at(-1), 96);
});

test('the text size that makes the advance exactly the cell width', () => {
	const size = textFontSize(15, 1, CELL);
	assert.ok(Math.abs(size * CELL.width - 15) < 1e-9);
	const retina = textFontSize(30, 2, CELL);
	assert.ok(Math.abs(retina * CELL.width * 2 - 30) < 1e-9);
});

test('a glyph is placed on its cell and scaled so that its advance is the cell', () => {
	const place = glyphTransform(2, 1, { w: 15, h: 29 }, UNITS, 1);
	assert.equal(place.x, 30);
	assert.ok(Math.abs(place.sx * UNITS.advance - 15) < 1e-9);
	assert.ok(Math.abs(place.sy * (UNITS.ascent - UNITS.descent) - 29) < 1e-9);
	// the baseline of the second row: its top plus the scaled ascent
	assert.ok(Math.abs(place.baseline - (29 + UNITS.ascent * place.sy)) < 1e-9);
});

test('device pixels become css pixels', () => {
	const place = glyphTransform(1, 0, { w: 30, h: 58 }, UNITS, 2);
	assert.equal(place.x, 15);
	assert.ok(Math.abs(place.sx * UNITS.advance - 15) < 1e-9);
});

test('the edge rules include a visible last edge, inside the table', () => {
	const rules = edgeRules(2, 1, { w: 10, h: 20 }, 1);
	assert.deepEqual(rules.vertical, [0, 10, 19]);
	assert.deepEqual(rules.horizontal, [0, 19]);
	assert.equal(rules.thickness, 1);
	const sharp = edgeRules(1, 1, { w: 10, h: 20 }, 2);
	assert.deepEqual(sharp.vertical, [0, 4.5]);
	assert.equal(sharp.thickness, 0.5);
});
