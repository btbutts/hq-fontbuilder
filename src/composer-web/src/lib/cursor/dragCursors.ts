import handGrabSvg from '@tabler/icons/outline/hand-grab.svg?raw';
import handMoveSvg from '@tabler/icons/outline/hand-move.svg?raw';

export const CURSOR_MOVE_VAR = '--col-cursor-move';
export const CURSOR_GRAB_VAR = '--col-cursor-grab';

function cursorCss(rawSvg: string, stroke: string, size: number, tipratio: number, fallback: string): string {
	const svg = rawSvg
		.replace('stroke="currentColor"', `stroke="${stroke}"`)
		.replace('width="24"', `width="${size}"`)
		.replace('height="24"', `height="${size}"`)
		.replace(/\s+/g, ' ');
	const hotspot = Math.floor((size / 2) * tipratio); // slightly offset the hotspot for better visual alignment
	return `url("data:image/svg+xml;utf8,${encodeURIComponent(svg)}") ${hotspot} ${hotspot}, ${fallback}`;
}

/** Publish the hand-move and hand-grab cursors on <html>, `size` px square, drawn in `stroke`. */
export function publishDragCursors(stroke: string, size: number, tipRatio: number): void {
	const root = document.documentElement.style;
	root.setProperty(CURSOR_MOVE_VAR, cursorCss(handMoveSvg, stroke, size, tipRatio, 'grab'));
	root.setProperty(CURSOR_GRAB_VAR, cursorCss(handGrabSvg, stroke, size, tipRatio, 'grabbing'));
}
