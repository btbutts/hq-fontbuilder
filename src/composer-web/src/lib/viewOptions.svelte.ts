/**
 * How glyphs are shown on the group and combined-result pages, shared by both so that
 * the switches behave the same on each and keep their position when you move between them.
 *
 * - `wrap`: one wrapping run of cells instead of stacked rows (remembered by the browser).
 * - `unfitted`: show the donor glyphs as they are, outlined red where the base cell cuts
 *   them off. Off by default: glyphs are shown as the fit will place them.
 */

import { FULL_GRID_MAX, type LayoutMode } from './glyphLayout';

const WRAP_STORAGE_KEY = 'fc-glyph-wrap';

function readWrapPreference(): boolean {
	try {
		return localStorage.getItem(WRAP_STORAGE_KEY) === '1';
	} catch {
		return false;
	}
}

class ViewOptions {
	wrap = $state(readWrapPreference());
	unfitted = $state(false);

	setWrap(enabled: boolean): void {
		this.wrap = enabled;
		try {
			localStorage.setItem(WRAP_STORAGE_KEY, enabled ? '1' : '0');
		} catch {
			// private window or blocked storage: the choice just lasts for this page
		}
	}

	/** Glyphs are drawn fitted unless the user asked for the originals. */
	get showFitted(): boolean {
		return !this.unfitted;
	}

	/**
	 * Rows, or a wrapping run. A group too large to draw whole (private use) is a sparse
	 * list of glyphs; rows of 16 would be mostly holes, so it always wraps.
	 */
	layoutMode(groupTotal: number): LayoutMode {
		return this.wrap || groupTotal > FULL_GRID_MAX ? 'wrap' : 'rows';
	}
}

export const viewOptions = new ViewOptions();
