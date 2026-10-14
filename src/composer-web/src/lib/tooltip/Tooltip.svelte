<script lang="ts">
	import { onMount } from 'svelte';
	import { colors } from '../styles.svelte';
	import { TIP_BODY_ATTRIBUTE, TIP_TITLE_ATTRIBUTE, tipRuns } from './tooltip';

	// The one tooltip of the page. Elements describe themselves with `tip()`; this finds
	// the nearest described element under the pointer (or the focused one) and shows it.
	const OFFSET_PX = 14;
	const SHOW_DELAY_MS = 120;
	const MARGIN_PX = 8;

	let title = $state('');
	let lines = $state<string[]>([]);
	let left = $state(0);
	let top = $state(0);
	let visible = $state(false);
	let box = $state<HTMLElement | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;
	let current: Element | null = null;

	function described(target: EventTarget | null): Element | null {
		if (!(target instanceof Element)) return null;
		return target.closest(`[${TIP_TITLE_ATTRIBUTE}], [${TIP_BODY_ATTRIBUTE}]`);
	}

	function place(x: number, y: number): void {
		const width = box?.offsetWidth ?? 280;
		const height = box?.offsetHeight ?? 80;
		left = Math.max(MARGIN_PX, Math.min(x + OFFSET_PX, window.innerWidth - width - MARGIN_PX));
		const below = y + OFFSET_PX;
		top =
			below + height + MARGIN_PX > window.innerHeight
				? Math.max(MARGIN_PX, y - OFFSET_PX - height)
				: below;
	}

	function show(element: Element, x: number, y: number): void {
		title = element.getAttribute(TIP_TITLE_ATTRIBUTE) ?? '';
		lines = (element.getAttribute(TIP_BODY_ATTRIBUTE) ?? '').split('\n').filter(Boolean);
		visible = true;
		place(x, y);
	}

	function hide(): void {
		clearTimeout(timer);
		visible = false;
		current = null;
	}

	function onMove(event: PointerEvent): void {
		const element = described(event.target);
		if (element !== current) {
			hide();
			if (element) {
				current = element;
				timer = setTimeout(() => show(element, event.clientX, event.clientY), SHOW_DELAY_MS);
			}
		} else if (visible) {
			place(event.clientX, event.clientY);
		}
	}

	function onFocus(event: FocusEvent): void {
		const element = described(event.target);
		if (!element) return;
		const rect = element.getBoundingClientRect();
		current = element;
		show(element, rect.left, rect.bottom);
	}

	// A focused element that is removed (a button that navigates away) fires focusout while
	// Svelte is tearing it down, when state may not be set: hide a moment later.
	function onFocusOut(): void {
		queueMicrotask(hide);
	}

	onMount(() => {
		document.addEventListener('pointermove', onMove);
		document.addEventListener('pointerdown', hide);
		document.addEventListener('focusin', onFocus);
		document.addEventListener('focusout', onFocusOut);
		document.addEventListener('scroll', hide, true);
		return () => {
			document.removeEventListener('pointermove', onMove);
			document.removeEventListener('pointerdown', hide);
			document.removeEventListener('focusin', onFocus);
			document.removeEventListener('focusout', onFocusOut);
			document.removeEventListener('scroll', hide, true);
			clearTimeout(timer);
		};
	});
</script>

{#if visible}
	<div
		bind:this={box}
		role="tooltip"
		class="pointer-events-none fixed z-50 max-w-80 rounded border px-3 py-2 text-[0.85rem] leading-snug {colors.border} {colors.bandBackground} {colors.textPrimary} {colors.floatingShadow}"
		style:left="{left}px"
		style:top="{top}px"
	>
		{#if title}
			<div class="font-semibold">{title}</div>
		{/if}
		{#each lines as line, index (index)}
			<div class={colors.textSecondary}>
				{#each tipRuns(line) as run, position (position)}
					{#if run.italic}<em>{run.text}</em>{:else}{run.text}{/if}
				{/each}
			</div>
		{/each}
	</div>
{/if}
