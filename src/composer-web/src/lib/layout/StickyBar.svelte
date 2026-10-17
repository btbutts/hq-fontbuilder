<script lang="ts">
	import type { Snippet } from 'svelte';
	import IconMenu2 from '@tabler/icons-svelte/icons/menu-2';
	import BareIconButton from '../button/BareIconButton.svelte';
	import { colors, floating } from '../styles.svelte.ts';

	interface Props {
		/** the whole toolbar, drawn while it fits on one line */
		full: Snippet;
		/**
		 * the toolbar without its dispensable parts (a sentence of explanation), drawn when
		 * `full` does not fit but this does; the menu comes only when this does not fit either
		 */
		reduced?: Snippet;
		/** what stays on the bar, beside the menu button, when the full toolbar does not fit */
		compact?: Snippet;
		/** what the menu button's pop-up holds when the full toolbar does not fit */
		menu: Snippet;
	}

	let { full, reduced, compact, menu }: Props = $props();

	let content = $state<HTMLElement>();
	let natural = $state<HTMLElement>();
	let wrapper = $state<HTMLElement>();
	let naturalReduced = $state<HTMLElement>();
	let stage = $state<'full' | 'reduced' | 'narrow'>('full');
	const narrow = $derived(stage === 'narrow');
	let open = $state(false);

	// The toolbar never wraps. Each layout is also drawn, invisibly, at its natural width;
	// the bar shows the first of full, reduced and (menu button + compact) whose natural
	// width fits in the room the bar has. Measuring copies, rather than the bar itself, keeps
	// the decision independent of which layout is showing.
	$effect(() => {
		const room = content;
		const needed = natural;
		const neededReduced = naturalReduced;
		if (!room || !needed) return;
		const measure = () => {
			const available = room.getBoundingClientRect().width + 0.5;
			if (needed.getBoundingClientRect().width <= available) stage = 'full';
			else if (neededReduced && neededReduced.getBoundingClientRect().width <= available)
				stage = 'reduced';
			else stage = 'narrow';
		};
		measure();
		const observer = new ResizeObserver(measure);
		observer.observe(room);
		observer.observe(needed);
		if (neededReduced) observer.observe(neededReduced);
		return () => observer.disconnect();
	});

	$effect(() => {
		if (!narrow) open = false;
	});

	function closeOnOutside(event: PointerEvent): void {
		if (open && wrapper && !wrapper.contains(event.target as Node)) open = false;
	}

	function closeOnEscape(event: KeyboardEvent): void {
		if (open && event.key === 'Escape') open = false;
	}
</script>

<svelte:window onpointerdown={closeOnOutside} onkeydown={closeOnEscape} />

<!--
	The toolbar that stays at the top of the viewport: edge to edge, like the PageHeader. Its
	height is fixed (the content row's), so that it is the same on both pages and at every
	width, whichever layout it shows. overflow-x-clip: the hidden copy may be wider than the
	viewport and must not give the page a scrollbar; the pop-up still hangs out below.
-->
<div
	class="sticky top-0 z-10 -mx-(--page-gutter) overflow-x-clip border-b px-(--page-gutter) py-2 {colors.border} {colors.bandBackground}"
>
	<div bind:this={content} class="relative flex h-7 items-center whitespace-nowrap">
		{#if narrow}
			<div bind:this={wrapper} class="relative mr-4 flex shrink-0">
				<BareIconButton
					icon={IconMenu2}
					label="Toolbar options"
					size={24}
					expanded={open}
					colorClasses={colors.menuIconButton}
					onclick={() => (open = !open)}
				/>
				{#if open}
					<div
						role="group"
						aria-label="Toolbar options"
						class="absolute top-full left-0 z-20 mt-2 flex w-max max-w-[calc(100vw-2*var(--page-gutter))] flex-col items-start gap-3 border p-3 whitespace-normal {floating.radius} {colors.border} {colors.popoverTint} {colors.floatingShadow}"
						style={floating.style}
					>
						{@render menu()}
					</div>
				{/if}
			</div>
			{@render compact?.()}
		{:else if stage === 'reduced' && reduced}
			{@render reduced()}
		{:else}
			{@render full()}
		{/if}
		<div
			bind:this={natural}
			class="pointer-events-none invisible absolute top-0 left-0 flex h-full w-max items-center"
			aria-hidden="true"
			inert
		>
			{@render full()}
		</div>
		{#if reduced}
			<div
				bind:this={naturalReduced}
				class="pointer-events-none invisible absolute top-0 left-0 flex h-full w-max items-center"
				aria-hidden="true"
				inert
			>
				{@render reduced()}
			</div>
		{/if}
	</div>
</div>
