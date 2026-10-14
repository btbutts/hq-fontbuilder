import type { FitInfo } from '../data/api';

/** How many of the given fits are glyphs the base cell cuts off. */
export function clippedCount(fits: Iterable<FitInfo | undefined>): number {
	let count = 0;
	for (const fit of fits) {
		if (fit?.clipped) count += 1;
	}
	return count;
}

function factor(value: number): string {
	return `×${value.toFixed(2)}`;
}

/** One line saying what the base cell does to a glyph, or null when nothing is worth saying. */
export function describeFit(fit: FitInfo | undefined, fitted: boolean): string | null {
	if (!fit) return null;
	if (!fitted) {
		return fit.clipped ? `cut off by the base cell: ${fit.overflow.toFixed(2)} em outside it` : null;
	}
	switch (fit.kind) {
		case 'category':
			return `scaled with its category (${factor(fit.sx)})`;
		case 'connector':
			return `scaled with the family's box glyphs (${factor(fit.sx)}, ${factor(fit.sy)}); anything past the cell is cut`;
		case 'frame':
			return `fitted to the base cell (${factor(fit.sx)}, ${factor(fit.sy)})`;
		case 'oversize':
			return `too big for the cell: scaled (${factor(fit.sx)})`;
		case 'offset':
			return `moved ${fit.dx.toFixed(2)}, ${fit.dy.toFixed(2)} em to sit inside the cell`;
		default:
			return null;
	}
}
