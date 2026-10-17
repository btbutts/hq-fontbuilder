/** Where the main page was scrolled when the user left it, so that coming back lands there. */

export interface ScrollPlace {
	/** the page's own scroll */
	x: number;
	y: number;
	/** the sideways scroll of the coverage table */
	tableLeft: number;
}

let place: ScrollPlace = { x: 0, y: 0, tableLeft: 0 };

export function rememberScroll(next: ScrollPlace): void {
	place = next;
}

export function recalledScroll(): ScrollPlace {
	return place;
}
