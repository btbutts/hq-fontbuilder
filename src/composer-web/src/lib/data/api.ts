/**
 * Typed client for the font-composer console API. The interfaces mirror the
 * /api/state payload built by font_composer/composer/state.py exactly.
 */

import { overlayStore } from './overlay.svelte.ts';

/** The view a read request is about: the overlay's categories, or the Unicode blocks. */
function view(): string {
	return overlayStore.enabled ? '1' : '0';
}

export interface StyleInfo {
	file: string;
	family: string;
	style: string;
	weight: number;
	width: number;
	italic: boolean;
	unitsPerEm: number;
	ascent: number;
	descent: number;
	fixedPitch: boolean;
	variable: boolean;
	instances: string[];
	cellAdvance: number;
	modalAdvance: number;
	codepointCount: number;
}

export interface FamilyError {
	file: string;
	reason: string;
}

export interface FamilyInfo {
	/** the family's folder name: the key in the configuration and in URLs */
	label: string;
	/** the family name the font file carries ("FiraMono Nerd Font"): what to show */
	displayName: string;
	styles: StyleInfo[];
	errors: FamilyError[];
}

export interface GroupFont {
	/** the family's folder name */
	family: string;
	/** the name its font file carries */
	name: string;
	/** how many glyphs of the category its reference style holds */
	count: number;
}

export interface NamedRow {
	label: string;
	low: number;
	high: number;
}

export interface GroupInfo {
	id: string;
	label: string;
	total: number;
	atomic: boolean;
	/** an overlay category: shown instead of a part of a block, never written to the file */
	overlay: boolean;
	/** the id of the Unicode block it lies in */
	block: string;
	/** stretches of consecutive code points of the category */
	ranges: [number, number][];
	/** rows of the group page that are not 16 wide (the ASCII letters and digits) */
	rows: NamedRow[];
	/** the families that have glyphs in it, with how many */
	fonts: GroupFont[];
}

export interface BaseMetrics {
	family: string;
	unitsPerEm: number;
	ascent: number;
	descent: number;
	cellAdvance: number;
}

export interface SummaryEntry {
	group: string;
	/** the families of the group in inheritance order, first choice first */
	order: string[];
	/** how many code points of the group some family of the order has a glyph for */
	covered: number;
	total: number;
	/** families that cover the whole group on their own */
	candidates: string[];
	/** family -> how many of the category's glyphs it supplies */
	sources: Record<string, number>;
}

export interface StyleFileInfo {
	file: string;
	/** the family name the font file itself carries (name table), not its folder */
	family: string;
	style: string;
	weight: number;
	italic: boolean;
}

export interface StyleEntry {
	/** the style file that serves the output style, or null when there is none */
	file: string | null;
	reason: string;
	overridden: boolean;
}

export interface StyleType {
	/** a style as one entry: "Bold", "Light Italic" (or as a font spells it, unconsolidated) */
	name: string;
	/** false until the user includes it: it gets no column and is not built */
	included: boolean;
	/** the other spellings merged into this entry ("Heavy" under "Black") */
	similar: string[];
}

export interface StyleTypes {
	/** similar styles are listed as one entry */
	consolidate: boolean;
	options: StyleType[];
}

export interface StyleMap {
	outputStyles: string[];
	/** families used by some group -> their style files */
	families: Record<string, StyleFileInfo[]>;
	/** output style -> family -> the file picked */
	entries: Record<string, Record<string, StyleEntry>>;
	/** output style -> the name the user gave it (only styles that have one): what is built */
	names: Record<string, string>;
}

export interface ProblemFont {
	path: string;
	reason: string;
}

export interface OverlayState {
	/** the overlay orders are kept in the configuration file */
	stored: boolean;
	orders: Record<string, string[]>;
}

export interface ComposerState {
	version: number;
	fontsDir: string;
	catalogReady: boolean;
	fontCount: number;
	groups: GroupInfo[];
	families: FamilyInfo[];
	coverage: Record<string, Record<string, [number, number]>>;
	/** family label -> ids of the groups on which the styles of the family disagree */
	uneven: Record<string, string[]>;
	/** group id -> families in inheritance order */
	choices: Record<string, string[]>;
	overlay: OverlayState;
	/** "U+2714" -> the family pinned to that code point */
	glyphOverrides: Record<string, string>;
	/** every style the fonts hold, upright first, light to heavy */
	styleTypes: StyleTypes;
	styleMap: StyleMap;
	base: BaseMetrics | null;
	summary: SummaryEntry[];
	problems: ProblemFont[];
	/** set while font_composer.toml does not parse; the last good configuration stays in force */
	configError: string | null;
}

/** How a glyph relates to the base cell, and the correction that fixes it. */
export interface FitInfo {
	kind: 'bleed' | 'frame' | 'oversize' | 'offset' | 'category' | 'connector';
	/** x' = sx * x + dx and y' = sy * y + dy, in em, y up from the baseline */
	sx: number;
	sy: number;
	dx: number;
	dy: number;
	/** how far the glyph's ink leaves the base cell, in em */
	overflow: number;
	/** how far it still leaves it after the correction */
	residual: number;
	/** true when ink is cut off by the cell (past a bleed) */
	clipped: boolean;
	/** a connector: its deliberate overshoot is cut at the cell edge, as the renderer will */
	clip: boolean;
}

export interface GlyphsPayload {
	family: string;
	group: string;
	/** style file name -> code points of the group that the file holds */
	styles: Record<string, number[]>;
	/** style file name -> code point -> fit, for the glyphs that are not simply inside */
	fit: Record<string, Record<string, FitInfo>>;
}

export interface ChooseResult {
	ok: boolean;
	error?: string;
	/** the new inheritance order of an overlay category */
	order?: string[];
}

export interface NamesPayload {
	group: string;
	/** code point -> official Unicode name, for those that have one */
	names: Record<string, string>;
}

export async function fetchNames(group: string): Promise<NamesPayload> {
	const response = await fetch(`/api/names?${new URLSearchParams({ group, overlay: view() })}`);
	if (!response.ok) throw new Error(`/api/names: ${response.status}`);
	return (await response.json()) as NamesPayload;
}

export type ChooseAction = 'add' | 'remove' | 'up' | 'down' | 'clear';

export interface ResolvedGlyph {
	codepoint: number;
	/** the family the glyph is taken from */
	source: string;
	/** every family that has the glyph, in inheritance order; only present when > 1 */
	candidates?: string[];
	overridden?: boolean;
	fit?: FitInfo;
}

export interface Composition {
	version: number;
	group: string;
	label: string;
	atomic: boolean;
	total: number;
	order: string[];
	/** families that serve or could serve a glyph without being in the order */
	extra: string[];
	/** family -> the style file its glyphs are drawn from (the reference style) */
	fonts: Record<string, string>;
	/** family -> the family name its font file carries ("FiraMono Nerd Font"), for display */
	familyNames: Record<string, string>;
	/** the code points that some family has, in code point order */
	glyphs: ResolvedGlyph[];
	missing: number;
	/** family -> how many glyphs are taken from it */
	contributions: Record<string, number>;
	invalidOverrides: { codepoint: number; family: string; reason: string }[];
}

export async function fetchState(overlay: boolean): Promise<ComposerState> {
	const response = await fetch(`/api/state?${new URLSearchParams({ overlay: overlay ? '1' : '0' })}`);
	if (!response.ok) throw new Error(`/api/state: ${response.status}`);
	return (await response.json()) as ComposerState;
}

export async function fetchVersion(): Promise<number> {
	const response = await fetch('/api/version');
	if (!response.ok) throw new Error(`/api/version: ${response.status}`);
	const payload = (await response.json()) as { version: number };
	return payload.version;
}

export async function fetchGlyphs(family: string, group: string): Promise<GlyphsPayload> {
	const query = new URLSearchParams({ family, group, overlay: view() });
	const response = await fetch(`/api/glyphs?${query}`);
	if (!response.ok) throw new Error(`/api/glyphs: ${response.status}`);
	return (await response.json()) as GlyphsPayload;
}

export interface FitPayload {
	family: string;
	group: string;
	file: string;
	/** code point -> fit, for those of the asked-for glyphs that are not simply inside */
	fit: Record<string, FitInfo>;
}

/** The fit of some glyphs of one style file: for a group too large to be fitted whole. */
export async function fetchFit(
	family: string,
	group: string,
	file: string,
	codepoints: number[]
): Promise<FitPayload> {
	const query = new URLSearchParams({ family, group, file, codepoints: codepoints.join(',') });
	const response = await fetch(`/api/fit?${query}`);
	if (!response.ok) throw new Error(`/api/fit: ${response.status}`);
	return (await response.json()) as FitPayload;
}

async function post(path: string, body: unknown): Promise<Response> {
	return fetch(path, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
}

async function result(response: Response): Promise<ChooseResult> {
	const payload = (await response.json().catch(() => ({}))) as { error?: string; order?: string[] };
	if (response.ok) return { ok: true, order: payload.order };
	return { ok: false, error: payload.error ?? `error ${response.status}` };
}

export async function fetchComposition(group: string, order?: string[]): Promise<Composition> {
	const query = new URLSearchParams({ group, overlay: view() });
	for (const family of order ?? []) query.append('order', family);
	const response = await fetch(`/api/composition?${query}`);
	if (!response.ok) throw new Error(`/api/composition: ${response.status}`);
	return (await response.json()) as Composition;
}

/** Map an output style of a family to one of its style files; `null` is the default rules. */
export async function postStyle(
	style: string,
	family: string,
	file: string | null
): Promise<ChooseResult> {
	return result(await post('/api/style', { style, family, file }));
}

/** Consider a style type in the style mapping and the build, or leave it out. */
export async function postStyleType(style: string, included: boolean): Promise<ChooseResult> {
	return result(await post('/api/style-type', { style, included }));
}

/** List similar styles as one entry, or each as the fonts spell it. */
export async function postStyleConsolidate(enabled: boolean): Promise<ChooseResult> {
	return result(await post('/api/style-consolidate', { enabled }));
}

/** Build an output style under another name; `null` goes back to the name the fonts give. */
export async function postStyleName(style: string, name: string | null): Promise<ChooseResult> {
	return result(await post('/api/style-name', { style, name }));
}

/** `order` is the order the browser holds, sent for an overlay category only. */
export async function postChoose(
	group: string,
	action: ChooseAction,
	family: string | null = null,
	order?: string[]
): Promise<ChooseResult> {
	return result(await post('/api/choose', { group, action, family, order }));
}

/** Serve one code point from one family; `null` goes back to the inheritance order. */
export async function postGlyph(
	codepoint: number,
	family: string | null,
	group?: string,
	order?: string[]
): Promise<ChooseResult> {
	return result(await post('/api/glyph', { codepoint, family, group, order }));
}

/** Keep the overlay orders in the configuration file, or take them out of it. */
export async function postOverlayStore(
	enabled: boolean,
	orders: Record<string, string[]>
): Promise<ChooseResult> {
	return result(await post('/api/overlay-store', { enabled, orders }));
}

/** One written font of a build proof: where to load it from, its cell, and what does not join. */
export interface ProofFont {
	style: string;
	file: string;
	url: string;
	/** em */
	cell: { width: number; ascent: number; descent: number };
	/** the font's own units, which `outlines` are in */
	units: { upm: number; advance: number; ascent: number; descent: number };
	/** code point -> SVG path of the box and block glyphs, y pointing up */
	outlines: Record<string, string>;
	seams: ProofSeam[];
}

export interface ProofSeam {
	/** em: how far the glyphs of this line miss each other */
	spread: number;
	/** an arc, a diagonal or a dashed line: a miss is only a warning */
	soft: boolean;
	members: { codepoint: number; edge: string; start: number }[];
}

/** What `build --show-proof` serves; only that command answers it. */
export async function fetchProof(): Promise<{ fonts: ProofFont[] }> {
	const response = await fetch('/api/proof');
	if (!response.ok) throw new Error(`/api/proof: ${response.status}`);
	return (await response.json()) as { fonts: ProofFont[] };
}
