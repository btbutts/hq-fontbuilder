/**
 * Official Unicode names of the code points of the groups viewed so far. Python reads
 * NamesList.txt once and answers per group; this keeps the answers, reactively, so a
 * glyph's tooltip fills in as soon as its group's names arrive.
 */

import { fetchNames } from './api.ts';

class UnicodeNames {
	private names = $state<Record<number, string>>({});
	private loaded = new Set<string>();

	/** Fetch the names of a group once; later calls for the same group do nothing. */
	async load(groupId: string): Promise<void> {
		if (!groupId || this.loaded.has(groupId)) return;
		this.loaded.add(groupId);
		try {
			const payload = await fetchNames(groupId);
			const merged = { ...this.names };
			for (const [codepoint, name] of Object.entries(payload.names)) {
				merged[Number(codepoint)] = name;
			}
			this.names = merged;
		} catch {
			this.loaded.delete(groupId); // try again next time the group is opened
		}
	}

	nameOf(codepoint: number): string | undefined {
		return this.names[codepoint];
	}
}

export const unicodeNames = new UnicodeNames();
