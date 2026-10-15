import { parseSavedOrder, reconcileOrder } from './columnOrder.ts';

function readSaved(storageKey: string): string[] {
	try {
		return parseSavedOrder(localStorage.getItem(storageKey));
	} catch {
		return [];
	}
}

export class ColumnOrder {
	#storageKey: string;
	#currentIds: () => string[];
	#saved = $state<string[]>([]);
	#locked = $state(false);

	/**
	 * @param storageKey the key by which the order is saved to localStorage
	 * @param currentIds ids of columns already in our table, in order
	 */
	constructor(storageKey: string, currentIds: () => string[]) {
		this.#storageKey = storageKey;
		this.#currentIds = currentIds;
		this.#saved = readSaved(storageKey);
		try {
			this.#locked = localStorage.getItem(`${storageKey}:locked`) === '1';
		} catch {
			// blocked storage: unlocked
		}
	}

	/** Columns cannot be dragged; remembered like the order. */
	get locked(): boolean {
		return this.#locked;
	}

	set locked(locked: boolean) {
		this.#locked = locked;
		try {
			localStorage.setItem(`${this.#storageKey}:locked`, locked ? '1' : '0');
		} catch {
			// private window or blocked storage: the lock just lasts for this page
		}
	}

	/** The ids of the columns, left to right. */
	get ids(): string[] {
		return reconcileOrder(this.#saved, this.#currentIds());
	}

	/** Make this the order, and remember it. */
	set(ids: string[]): void {
		this.#saved = ids;
		try {
			localStorage.setItem(this.#storageKey, JSON.stringify(ids));
		} catch {
			// private window or blocked storage: the order just lasts for this page
		}
	}
}
