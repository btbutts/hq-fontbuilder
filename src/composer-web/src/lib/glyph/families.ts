/**
 * Shared helpers for pages that draw glyphs from several families at once: one colour
 * per family (by position in the inheritance order) and the @font-face rules that make
 * each family's reference style available to SVG text under a short CSS name.
 */

import { colors } from '../styles.svelte';

/**
 * The colour of the family at `index` of an inheritance order, from `colors.family`: a
 * text colour class, to be used with `bg-current`, `fill-current` or `stroke-current`.
 */
export function familyColor(index: number): string {
	return colors.family[index % colors.family.length] ?? '';
}

/** The CSS font-family name the font-face rule below gives the family at `index`. */
export function familyCssName(index: number): string {
	return `fc-fam-${index}`;
}

/** @font-face rules for the families of `order`, each from its `fonts` file. */
export function fontFaceRules(order: string[], fonts: Record<string, string>): string {
	return order
		.map((family, index) => {
			const file = fonts[family];
			if (!file) return '';
			return (
				`@font-face {\n  font-family: "${familyCssName(index)}";\n` +
				`  src: url("/fonts/${encodeURIComponent(family)}/${encodeURIComponent(file)}");\n}`
			);
		})
		.filter((rule) => rule !== '')
		.join('\n');
}

/** Install (or replace) the page's single <style> element of font-face rules. */
export function installFontFaces(elementId: string, css: string): void {
	let element = document.getElementById(elementId);
	if (!element) {
		element = document.createElement('style');
		element.id = elementId;
		document.head.appendChild(element);
	}
	element.textContent = css;
}
