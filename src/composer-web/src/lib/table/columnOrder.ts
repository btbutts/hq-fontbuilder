/** The saved order: anything but a JSON list of strings is no order. */
export function parseSavedOrder(json: string | null): string[] {
	if (json === null) return [];
	let value: unknown;
	try {
		value = JSON.parse(json);
	} catch {
		return [];
	}
	if (!Array.isArray(value)) return [];
	const seen = new Set<string>();
	for (const entry of value) {
		if (typeof entry === 'string') seen.add(entry);
	}
	return [...seen];
}

/** The saved order for columns that still exist, then new ones in `current` order. */
export function reconcileOrder(saved: readonly string[], current: readonly string[]): string[] {
	const exists = new Set(current);
	const placed = new Set<string>();
	const order: string[] = [];
	for (const id of saved) {
		if (exists.has(id) && !placed.has(id)) {
			placed.add(id);
			order.push(id);
		}
	}
	for (const id of current) {
		if (!placed.has(id)) {
			placed.add(id);
			order.push(id);
		}
	}
	return order;
}

/** The slot for a column dropped at `x`: after every column whose centre is left of it. */
export function insertionIndex(x: number, centres: readonly number[]): number {
	let index = 0;
	while (index < centres.length && centres[index] < x) index += 1;
	return index;
}

/** `ids` with `moved` taken out and inserted at `index` among the others. */
export function moveTo(ids: readonly string[], moved: string, index: number): string[] {
	const others = ids.filter((id) => id !== moved);
	others.splice(Math.max(0, Math.min(index, others.length)), 0, moved);
	return others;
}
