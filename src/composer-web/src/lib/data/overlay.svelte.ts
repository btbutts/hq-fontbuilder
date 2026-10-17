/**
 * The category overlay as this browser holds it: the switch, the order of each overlay
 * category, and the categories the user hid. Python owns the categories and writes the
 * pins; this only remembers what the user chose and sends it back with each request.
 */

import type { ComposerState } from './api.ts';
import {
	browserStorage,
	categoryOrder,
	ENABLED_KEY,
	EXCLUDED_KEY,
	ORDERS_KEY,
	readEnabled,
	readExcluded,
	readOrders,
	save
} from './overlayStorage.ts';

class OverlayStore {
	private storage = browserStorage();
	enabled = $state(readEnabled(this.storage));
	orders = $state<Record<string, string[]>>(readOrders(this.storage));
	excluded = $state<string[]>(readExcluded(this.storage));

	setEnabled(value: boolean): void {
		this.enabled = value;
		save(this.storage, ENABLED_KEY, value);
	}

	isExcluded(id: string): boolean {
		return this.excluded.includes(id);
	}

	setExcluded(id: string, hidden: boolean): void {
		this.excluded = hidden
			? [...new Set([...this.excluded, id])]
			: this.excluded.filter((item) => item !== id);
		save(this.storage, EXCLUDED_KEY, this.excluded);
	}

	orderOf(group: { id: string; overlay: boolean }, state: ComposerState | null): string[] {
		return categoryOrder(group, state, this.orders);
	}

	setOrder(id: string, order: string[]): void {
		const next = { ...this.orders };
		if (order.length > 0) next[id] = order;
		else delete next[id];
		this.replaceOrders(next);
	}

	private replaceOrders(orders: Record<string, string[]>): void {
		if (JSON.stringify(orders) === JSON.stringify(this.orders)) return;
		this.orders = orders;
		save(this.storage, ORDERS_KEY, orders);
	}

	/** When the orders are stored in the file they win: the browser copy follows them. */
	reconcile(state: ComposerState): void {
		if (state.overlay.stored) this.replaceOrders({ ...state.overlay.orders });
	}
}

export const overlayStore = new OverlayStore();
