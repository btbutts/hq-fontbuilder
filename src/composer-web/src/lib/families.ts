/**
 * Shared helpers for pages that draw glyphs from several families at once: one colour
 * per family (by position in the inheritance order) and the @font-face rules that make
 * each family's reference style available to SVG text under a short CSS name.
 */

const FAMILY_COLORS = [
	'#1b4965',
	'#c1440e',
	'#2d6a4f',
	'#7b2cbf',
	'#9a6b00',
	'#0077b6',
	'#b5179e',
	'#5f6c37'
];

export function familyColor(index: number): string {
	return FAMILY_COLORS[index % FAMILY_COLORS.length] ?? '#1b4965';
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
