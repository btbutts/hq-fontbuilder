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
