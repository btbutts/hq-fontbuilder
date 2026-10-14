/**
 * Shared console state: the latest /api/state snapshot plus the version poller.
 * The root layout starts polling; both pages read `store.state` reactively.
 */

import { fetchState, fetchVersion, type ComposerState } from './api';

const POLL_INTERVAL_MS = 2000;

class ConsoleStore {
	state = $state<ComposerState | null>(null);
	error = $state<string | null>(null);

	/**
	 * The name to show for a family: the one its font file carries. `label` (the folder name)
	 * is what the configuration and the URLs use, so it is shown only until the state has
	 * loaded, or for a family that is gone.
	 */
	nameOf(label: string): string {
		return this.state?.families.find((family) => family.label === label)?.displayName ?? label;
	}

	async refresh(): Promise<void> {
		try {
			this.state = await fetchState();
			this.error = null;
		} catch (cause) {
			this.error = cause instanceof Error ? cause.message : String(cause);
		}
	}

	startPolling(): () => void {
		void this.refresh();
		const timer = setInterval(() => {
			void (async () => {
				const current = this.state;
				if (!current) {
					await this.refresh();
					return;
				}
				try {
					const version = await fetchVersion();
					if (version !== current.version) await this.refresh();
				} catch {
					// Server briefly unreachable; the next tick retries.
				}
			})();
		}, POLL_INTERVAL_MS);
		return () => clearInterval(timer);
	}
}

export const consoleStore = new ConsoleStore();
