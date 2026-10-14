/**
 * Keep the page from scrolling while a dialog is open, so that a scroll gesture goes to
 * the dialog and never to what is behind it. Dialogs can stack: the page is released when
 * the last one lets go. The scrollbar's room is kept, so the page does not shift sideways.
 */

let holders = 0;
let saved: { overflow: string; gutter: string } | null = null;

/** Lock the page's scrolling; call the returned function to release it. */
export function lockScroll(): () => void {
	const root = document.documentElement;
	if (holders === 0) {
		saved = { overflow: root.style.overflow, gutter: root.style.scrollbarGutter };
		root.style.scrollbarGutter = 'stable';
		root.style.overflow = 'hidden';
	}
	holders += 1;
	let released = false;
	return () => {
		if (released) return;
		released = true;
		holders -= 1;
		if (holders === 0 && saved !== null) {
			root.style.overflow = saved.overflow;
			root.style.scrollbarGutter = saved.gutter;
			saved = null;
		}
	};
}
