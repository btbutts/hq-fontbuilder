<script lang="ts">
	import IconArrowBack from '@tabler/icons-svelte/icons/arrow-back';
	import IconDeviceFloppy from '@tabler/icons-svelte/icons/device-floppy';
	import IconPencil from '@tabler/icons-svelte/icons/pencil';
	import IconPencilCheck from '@tabler/icons-svelte/icons/pencil-check';
	import { colors } from '../styles.svelte.ts';
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
		/** told whenever the field opens or closes (and `false` when this goes away open) */
		onediting?: (editing: boolean) => void;
	}

	let { original, custom, onsave, onreset, onediting }: Props = $props();

	const shown = $derived(custom ?? original);

	let editing = $state(false);
	let draft = $state('');
	let problem = $state<string | null>(null);
	let busy = $state(false);
	let field = $state<HTMLInputElement | null>(null);
	const problemId = `rename-problem-${Math.random().toString(36).slice(2)}`;

	$effect(() => {
		onediting?.(editing);
		return () => onediting?.(false);
	});

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

<!-- the root fills its cell edge to edge (the cell has no padding of its own); editing turns the
     whole of it into the field, with the buttons inside it at the right -->
<svelte:element
	this={editing ? 'label' : 'div'}
	class="flex min-h-[1lh] min-w-0 items-center justify-between gap-3 px-3 py-1 {editing ? colors.inputBackground : ''}"
>
	{#if editing}
		<input
			data-no-drag
			bind:this={field}
			bind:value={draft}
			{onkeydown}
			oninput={() => (problem = null)}
			type="text"
			class="m-0 min-w-0 flex-1 border-0 bg-transparent p-0 outline-none {colors.textPrimary}"
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
				class="max-w-[50%] shrink-0 truncate text-[0.8em] font-normal {colors.textError}"
			>
				{problem}
			</span>
		{/if}
		<span data-no-drag class="flex shrink-0 items-center gap-2">
			<BareIconButton
				icon={IconArrowBack}
				label={custom === null ? 'Discard the Change' : `Use the Default Name, ${original}`}
				onclick={() => void back()}
			/>
			<BareIconButton icon={IconDeviceFloppy} label="Save the Name" onclick={() => void save()} />
		</span>
	{:else}
		<span class="min-w-0 truncate">{shown}</span>
		<span data-no-drag class="-m-1.5 flex cursor-pointer p-1.5">
			<BareIconButton
				icon={custom === null ? IconPencil : IconPencilCheck}
				label={custom === null
					? 'Change Font Style Name'
					: `Called ${custom} instead of ${original}\nClick to Change`}
				onclick={begin}
			/>
		</span>
	{/if}
</svelte:element>
