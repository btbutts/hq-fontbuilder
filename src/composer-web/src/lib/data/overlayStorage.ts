/**
 * What the browser remembers of the category overlay: whether it is on, the order of each
 * overlay category, and the categories the user hid. Pure helpers, so `bun test` runs them.
 */

export const ENABLED_KEY = 'fc-overlay-enabled';
export const ORDERS_KEY = 'fc-overlay-orders';
export const EXCLUDED_KEY = 'fc-excluded-categories';

export interface KeyValueStore {
	getItem(key: string): string | null;
	setItem(key: string, value: string): void;
}

/** The browser's storage, or null when it is blocked (a private window, site data off). */
export function browserStorage(): KeyValueStore | null {
	try {
		return localStorage;
	} catch {
		return null;
	}
}

function read(store: KeyValueStore | null, key: string): unknown {
	try {
		const text = store?.getItem(key);
		return text ? (JSON.parse(text) as unknown) : undefined;
	} catch {
		return undefined;
	}
}

function isStringList(value: unknown): value is string[] {
	return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export function readEnabled(store: KeyValueStore | null): boolean {
	const value = read(store, ENABLED_KEY);
	return typeof value === 'boolean' ? value : true;
}

export function readExcluded(store: KeyValueStore | null): string[] {
	const value = read(store, EXCLUDED_KEY);
	return isStringList(value) ? [...new Set(value)] : [];
}

export function readOrders(store: KeyValueStore | null): Record<string, string[]> {
	const value = read(store, ORDERS_KEY);
	if (typeof value !== 'object' || value === null || Array.isArray(value)) return {};
	const orders: Record<string, string[]> = {};
	for (const [id, order] of Object.entries(value as Record<string, unknown>)) {
		if (isStringList(order)) orders[id] = order;
	}
	return orders;
}

export function save(store: KeyValueStore | null, key: string, value: unknown): void {
	try {
		store?.setItem(key, JSON.stringify(value));
	} catch {
		// blocked or full: the choice lasts for this page only
	}
}

export interface OrderSource {
	choices: Record<string, string[]>;
	overlay: { stored: boolean; orders: Record<string, string[]> };
}

/**
 * The inheritance order to show for a category: a block's comes from the file; an overlay
 * category's from the file when the user stores them there, else from this browser.
 */
export function categoryOrder(
	group: { id: string; overlay: boolean },
	state: OrderSource | null,
	local: Record<string, string[]>
): string[] {
	if (!group.overlay) return state?.choices[group.id] ?? [];
	if (state?.overlay.stored) return state.overlay.orders[group.id] ?? [];
	return local[group.id] ?? [];
}
