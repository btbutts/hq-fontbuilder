import assert from 'node:assert/strict';
import { test } from 'node:test';
import { insertionIndex, moveTo, parseSavedOrder, reconcileOrder } from './columnOrder.ts';

test('nothing saved: the order is the server order', () => {
	assert.deepEqual(reconcileOrder([], ['a', 'b', 'c']), ['a', 'b', 'c']);
});

test('the saved order wins when every font is still there', () => {
	assert.deepEqual(reconcileOrder(['c', 'a', 'b'], ['a', 'b', 'c']), ['c', 'a', 'b']);
});

test('a removed font is skipped and the others keep their places', () => {
	assert.deepEqual(reconcileOrder(['c', 'x', 'a'], ['a', 'b', 'c']), ['c', 'a', 'b']);
});

test('a new font goes after the saved ones, in server order', () => {
	assert.deepEqual(reconcileOrder(['b', 'a'], ['a', 'b', 'n1', 'n2']), ['b', 'a', 'n1', 'n2']);
});

test('a duplicate in the saved order is placed once', () => {
	assert.deepEqual(reconcileOrder(['b', 'b', 'a'], ['a', 'b']), ['b', 'a']);
});

test('no fonts: no columns', () => {
	assert.deepEqual(reconcileOrder(['a'], []), []);
});

test('parseSavedOrder reads a list of strings and nothing else', () => {
	assert.deepEqual(parseSavedOrder('["a","b","a"]'), ['a', 'b']);
	assert.deepEqual(parseSavedOrder('["a",3,null,"b"]'), ['a', 'b']);
	assert.deepEqual(parseSavedOrder('{"a":1}'), []);
	assert.deepEqual(parseSavedOrder('not json'), []);
	assert.deepEqual(parseSavedOrder(null), []);
});

test('insertionIndex: left of everything is 0, right of everything is the end', () => {
	const centres = [100, 300, 500];
	assert.equal(insertionIndex(-4000, centres), 0);
	assert.equal(insertionIndex(99, centres), 0);
	assert.equal(insertionIndex(200, centres), 1);
	assert.equal(insertionIndex(301, centres), 2);
	assert.equal(insertionIndex(9000, centres), 3);
	assert.equal(insertionIndex(10, []), 0);
});

test('moveTo puts a column at an index counted among the others', () => {
	assert.deepEqual(moveTo(['a', 'b', 'c', 'd'], 'a', 2), ['b', 'c', 'a', 'd']);
	assert.deepEqual(moveTo(['a', 'b', 'c', 'd'], 'd', 0), ['d', 'a', 'b', 'c']);
	assert.deepEqual(moveTo(['a', 'b', 'c'], 'b', 99), ['a', 'c', 'b']);
});
