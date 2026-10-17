import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
	categoryOrder,
	ENABLED_KEY,
	EXCLUDED_KEY,
	ORDERS_KEY,
	readEnabled,
	readExcluded,
	readOrders,
	save,
	type KeyValueStore
} from './overlayStorage.ts';

function memory(initial: Record<string, string> = {}): KeyValueStore & { data: Record<string, string> } {
	const data = { ...initial };
	return {
		data,
		getItem: (key) => data[key] ?? null,
		setItem: (key, value) => {
			data[key] = value;
		}
	};
}

const blocked: KeyValueStore = {
	getItem() {
		throw new Error('blocked');
	},
	setItem() {
		throw new Error('blocked');
	}
};

test('nothing stored, or no storage at all: the overlay is on and nothing is hidden', () => {
	for (const store of [null, memory(), blocked]) {
		assert.equal(readEnabled(store), true);
		assert.deepEqual(readExcluded(store), []);
		assert.deepEqual(readOrders(store), {});
	}
});

test('corrupt or mistyped values fall back to the defaults', () => {
	const store = memory({
		[ENABLED_KEY]: '{not json',
		[EXCLUDED_KEY]: '[1, 2]',
		[ORDERS_KEY]: '["a"]'
	});
	assert.equal(readEnabled(store), true);
	assert.deepEqual(readExcluded(store), []);
	assert.deepEqual(readOrders(store), {});
});

test('valid values are read back, and a mistyped order is dropped on its own', () => {
	const store = memory({
		[ENABLED_KEY]: 'false',
		[EXCLUDED_KEY]: '["Arrows","Arrows","Dingbats"]',
		[ORDERS_KEY]: '{"overlay:powerline":["A","B"],"overlay:ascii-alnum":"A"}'
	});
	assert.equal(readEnabled(store), false);
	assert.deepEqual(readExcluded(store), ['Arrows', 'Dingbats']);
	assert.deepEqual(readOrders(store), { 'overlay:powerline': ['A', 'B'] });
});

test('save writes JSON and never throws, whatever the storage does', () => {
	const store = memory();
	save(store, ORDERS_KEY, { x: ['A'] });
	assert.equal(store.data[ORDERS_KEY], '{"x":["A"]}');
	assert.doesNotThrow(() => save(blocked, ORDERS_KEY, {}));
	assert.doesNotThrow(() => save(null, ORDERS_KEY, {}));
});

test('a block takes its order from the file, an overlay category from the browser or the file', () => {
	const state = {
		choices: { Arrows: ['A'], 'overlay:powerline': ['Z'] },
		overlay: { stored: false, orders: { 'overlay:powerline': ['Z'] } }
	};
	const local = { 'overlay:powerline': ['B'] };
	assert.deepEqual(categoryOrder({ id: 'Arrows', overlay: false }, state, local), ['A']);
	assert.deepEqual(categoryOrder({ id: 'overlay:powerline', overlay: true }, state, local), ['B']);
	const stored = { ...state, overlay: { ...state.overlay, stored: true } };
	assert.deepEqual(categoryOrder({ id: 'overlay:powerline', overlay: true }, stored, local), ['Z']);
	assert.deepEqual(categoryOrder({ id: 'Arrows', overlay: false }, null, local), []);
	assert.deepEqual(categoryOrder({ id: 'overlay:x', overlay: true }, null, {}), []);
});
