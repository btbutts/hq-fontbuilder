import type { FitInfo } from './api';

/** How many of the given fits are glyphs the base cell cuts off. */
export function clippedCount(fits: Iterable<FitInfo | undefined>): number {
	let count = 0;
	for (const fit of fits) {
		if (fit?.clipped) count += 1;
	}
	return count;
}
