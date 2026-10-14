/**
 * Describe a tooltip with plain data attributes: `<div {...tip('Title', 'line\nline')}>`.
 * One host (Tooltip.svelte, mounted once in the layout) watches the pointer and shows
 * the nearest element's description, so thousands of glyph cells cost no listeners.
 */

export const TIP_TITLE_ATTRIBUTE = 'data-tip-title';
export const TIP_BODY_ATTRIBUTE = 'data-tip-body';

/** Attributes that give an element a tooltip: a bold title and lines of detail. */
export function tip(title?: string, body?: string): Record<string, string> {
	const attributes: Record<string, string> = {};
	if (title) attributes[TIP_TITLE_ATTRIBUTE] = title;
	if (body) attributes[TIP_BODY_ATTRIBUTE] = body;
	return attributes;
}

// Emphasis inside a line of a tooltip's body. The markers are private-use characters, so
// no text that is shown as it is (a glyph name, a font name) can contain one by accident.
const EMPHASIS_START = '';
const EMPHASIS_END = '';

/** `text` as an italic run inside a line of a tooltip's body: `${emphasis(name)} is here`. */
export function emphasis(text: string): string {
	return `${EMPHASIS_START}${text}${EMPHASIS_END}`;
}

export interface TipRun {
	text: string;
	italic: boolean;
}

/** Split one line of a tooltip's body into the plain and italic runs `emphasis()` made. */
export function tipRuns(line: string): TipRun[] {
	const runs: TipRun[] = [];
	let italic = false;
	let text = '';
	for (const character of line) {
		if (character === EMPHASIS_START || character === EMPHASIS_END) {
			if (text !== '') runs.push({ text, italic });
			text = '';
			italic = character === EMPHASIS_START;
		} else {
			text += character;
		}
	}
	if (text !== '') runs.push({ text, italic });
	return runs;
}
