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
	chosen: string | null;
	candidates: string[];
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
	choices: Record<string, string>;
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

export async function postChoose(group: string, family: string | null): Promise<ChooseResult> {
	const response = await fetch('/api/choose', {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ group, family })
	});
	if (response.ok) return { ok: true };
	const payload = (await response.json().catch(() => ({}))) as { error?: string };
	return { ok: false, error: payload.error ?? `error ${response.status}` };
}
