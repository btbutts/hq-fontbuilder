/**
 * Typed client for the font-composer console API. The interfaces mirror the
 * /api/state payload built by font_composer/composer/state.py exactly.
 */

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
	coverage: Record<string, [number, number]>;
}

export interface FamilyError {
	file: string;
	reason: string;
}

export interface FamilyInfo {
	label: string;
	styles: StyleInfo[];
	errors: FamilyError[];
}

export interface GroupInfo {
	id: string;
	label: string;
	total: number;
	atomic: boolean;
	ranges: [number, number][];
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
}

export interface StyleFileInfo {
	file: string;
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

export interface StyleMap {
	outputStyles: string[];
	/** families used by some group -> their style files */
	families: Record<string, StyleFileInfo[]>;
	/** output style -> family -> the file picked */
	entries: Record<string, Record<string, StyleEntry>>;
}

export interface ProblemFont {
	path: string;
	reason: string;
}

export interface ComposerState {
	version: number;
	fontsDir: string;
	groups: GroupInfo[];
	families: FamilyInfo[];
	coverage: Record<string, Record<string, [number, number]>>;
	/** family label -> ids of the groups on which the styles of the family disagree */
	uneven: Record<string, string[]>;
	/** group id -> families in inheritance order */
	choices: Record<string, string[]>;
	/** "U+2714" -> the family pinned to that code point */
	glyphOverrides: Record<string, string>;
	styleMap: StyleMap;
	base: BaseMetrics | null;
	summary: SummaryEntry[];
	problems: ProblemFont[];
	/** set while composer.toml does not parse; the last good configuration stays in force */
	configError: string | null;
}

export interface GlyphsPayload {
	family: string;
	group: string;
	/** style file name -> code points of the group that the file holds */
	styles: Record<string, number[]>;
}

export interface ChooseResult {
	ok: boolean;
	error?: string;
}

export type ChooseAction = 'add' | 'remove' | 'up' | 'down' | 'clear';

export interface ResolvedGlyph {
	codepoint: number;
	/** the family the glyph is taken from */
	source: string;
	/** every family that has the glyph, in inheritance order; only present when > 1 */
	candidates?: string[];
	overridden?: boolean;
}

export interface Composition {
	version: number;
	group: string;
	label: string;
	atomic: boolean;
	total: number;
	order: string[];
	/** family -> the style file its glyphs are drawn from (the reference style) */
	fonts: Record<string, string>;
	/** the code points that some family has, in code point order */
	glyphs: ResolvedGlyph[];
	missing: number;
	/** family -> how many glyphs are taken from it */
	contributions: Record<string, number>;
	invalidOverrides: { codepoint: number; family: string; reason: string }[];
}

export async function fetchState(): Promise<ComposerState> {
	const response = await fetch('/api/state');
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
	const query = new URLSearchParams({ family, group });
	const response = await fetch(`/api/glyphs?${query}`);
	if (!response.ok) throw new Error(`/api/glyphs: ${response.status}`);
	return (await response.json()) as GlyphsPayload;
}

async function post(path: string, body: unknown): Promise<Response> {
	return fetch(path, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
}

async function result(response: Response): Promise<ChooseResult> {
	if (response.ok) return { ok: true };
	const payload = (await response.json().catch(() => ({}))) as { error?: string };
	return { ok: false, error: payload.error ?? `error ${response.status}` };
}

export async function postChoose(
	group: string,
	action: ChooseAction,
	family: string | null = null
): Promise<ChooseResult> {
	return result(await post('/api/choose', { group, action, family }));
}

export async function fetchComposition(group: string): Promise<Composition> {
	const response = await fetch(`/api/composition?${new URLSearchParams({ group })}`);
	if (!response.ok) throw new Error(`/api/composition: ${response.status}`);
	return (await response.json()) as Composition;
}

/** Serve one code point from one family; `null` goes back to the inheritance order. */
export async function postGlyph(
	codepoint: number,
	family: string | null
): Promise<ChooseResult> {
	return result(await post('/api/glyph', { codepoint, family }));
}

/** Map an output style of a family to one of its style files; `null` is the default rules. */
export async function postStyle(
	style: string,
	family: string,
	file: string | null
): Promise<ChooseResult> {
	return result(await post('/api/style', { style, family, file }));
}
