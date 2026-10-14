<script lang="ts">
	import IconArrowBack from '@tabler/icons-svelte/icons/arrow-back';
	import IconDeviceFloppy from '@tabler/icons-svelte/icons/device-floppy';
	import IconPencil from '@tabler/icons-svelte/icons/pencil';
	import IconPencilCheck from '@tabler/icons-svelte/icons/pencil-check';
	import { colors } from '../styles.svelte';
	import BareIconButton from './BareIconButton.svelte';

	/**
	 * A name that can be changed where it is shown, for the header cell of a table:
	 *
	 *     <InlineRename original="Oblique" custom={null} onsave={save} onreset={undo} />
	 *
	 * At rest it shows the name and, at the right edge, a pencil (a pencil with a check once the
	 * name has been changed). The pencil, not the cell, turns the cell into a text field that
	 * starts with the name shown. While the field is open the pencil is a floppy disk (save;
	 * Enter does the same) and, to the left of it, an arrow (back to the default name; Escape
	 * only closes the field). None of the icons has a box: each one is the button.
	 *
	 * The name is not stored here. `onsave` and `onreset` resolve with the reason the change was
	 * refused (shown under the field, which stays open) or `null` when it was made.
	 */
	interface Props {
		/** the name the style has without a custom one: it never goes away */
		original: string;
		/** the name the user gave it, or `null` */
		custom: string | null;
		onsave: (name: string) => Promise<string | null>;
		onreset: () => Promise<string | null>;
	}

	let { original, custom, onsave, onreset }: Props = $props();

	const shown = $derived(custom ?? original);

	let editing = $state(false);
	let draft = $state('');
	let problem = $state<string | null>(null);
	let busy = $state(false);
	let field = $state<HTMLInputElement | null>(null);
	const problemId = `rename-problem-${Math.random().toString(36).slice(2)}`;

	// the field takes the keyboard and its text is selected, as soon as it is there
	$effect(() => {
		if (editing && field) {
			field.focus();
			field.select();
		}
	});

	function begin(): void {
		draft = shown;
		problem = null;
		editing = true;
	}

	function close(): void {
		editing = false;
		problem = null;
	}

	async function settle(change: () => Promise<string | null>): Promise<void> {
		if (busy) return;
		busy = true;
		const refused = await change();
		busy = false;
		if (refused === null) close();
		else problem = refused;
	}

	const save = (): Promise<void> => settle(() => onsave(draft.trim()));

	// with no custom name there is nothing to take away: the arrow just closes the field
	const back = (): Promise<void> => (custom === null ? Promise.resolve(close()) : settle(onreset));

	function onkeydown(event: KeyboardEvent): void {
		if (event.isComposing) return;
		if (event.key === 'Enter') {
			event.preventDefault();
			void save();
		} else if (event.key === 'Escape') {
			// the dialog this sits in closes on Escape: this one only closes the field
			event.stopPropagation();
			close();
		}
	}
</script>

<div class="min-w-0">
	<!-- the field is taller than a line of text: it takes the room of the cell's own padding, so
	     the row does not grow when it opens -->
	<div class="flex min-h-[1lh] items-center justify-between gap-3">
		{#if editing}
			<!-- a refusal is written inside the field, at its right end -->
			<span class="relative -my-[3px] flex h-[calc(1lh+6px)] min-w-0 flex-1">
				<input
					bind:this={field}
					bind:value={draft}
					{onkeydown}
					oninput={() => (problem = null)}
					type="text"
					class="h-full min-w-0 flex-1 rounded border px-2 {colors.border} {colors.inputBackground} {colors.textPrimary} {problem !== null ? 'pr-36' : ''}"
					aria-label="Name of the {original} style"
					aria-invalid={problem !== null}
					aria-describedby={problem !== null ? problemId : undefined}
					autocomplete="off"
					spellcheck="false"
				/>
				{#if problem !== null}
					<span
						id={problemId}
						role="alert"
						class="pointer-events-none absolute top-1/2 right-2 max-w-[60%] -translate-y-1/2 truncate text-[0.8em] font-normal {colors.textError}"
					>
						{problem}
					</span>
				{/if}
			</span>
			<span class="flex shrink-0 items-center gap-2">
				<BareIconButton
					icon={IconArrowBack}
					label={custom === null ? 'Discard the change' : `Use the default name, ${original}`}
					onclick={() => void back()}
				/>
				<BareIconButton icon={IconDeviceFloppy} label="Save the name" onclick={() => void save()} />
			</span>
		{:else}
			<span class="min-w-0 truncate">{shown}</span>
			<BareIconButton
				icon={custom === null ? IconPencil : IconPencilCheck}
				label={custom === null
					? 'Give this style another name'
					: `Called ${custom} instead of ${original}: click to change`}
				onclick={begin}
			/>
		{/if}
	</div>
</div>
