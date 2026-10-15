<script lang="ts" generics="C extends { id: string }, R extends { id: string }">
	import type { Snippet } from 'svelte';
	import { flip } from 'svelte/animate';
	import type { Action } from 'svelte/action';
	import {
		dragHandle,
		dragHandleZone,
		TRIGGERS,
		type DndEvent
	} from 'svelte-dnd-action';
	import IconLock from '@tabler/icons-svelte/icons/lock';
	import IconLockOpen2 from '@tabler/icons-svelte/icons/lock-open-2';
	import BareIconButton from '../button/BareIconButton.svelte';
	import { publishDragCursors } from '../cursor/dragCursors.ts';
	import { dragCursor, dragColumnGhost } from '../styles.svelte.ts';
	import { insertionIndex, moveTo } from './columnOrder.ts';

	interface Props {
		/** the draggable columns, left to right */
		columns: C[];
		rows: R[];
		/** the name of a column, for assistive technology */
		label: (column: C) => string;
		/** called when a drag ends, with the ids of the columns in their new order */
		onreorder: (ids: string[]) => void;
		/** the table as a whole, for assistive technology */
		'aria-label': string;
		/** no column can be picked up (a header cell is being edited, say) */
		dragDisabled?: boolean;
		/** the user's lock: columns cannot be dragged (bind it to remember it) */
		locked?: boolean;
		/** background classes of every column (cells under the header have none of their own) */
		columnBackground?: string;
		/** receives the lock button, to render wherever it belongs in the header cell */
		fixedHeader: Snippet<[Snippet]>;
		fixedCell: Snippet<[R]>;
		/** put `use:handle` on the header cell; anything inside it marked `data-no-drag` is not part of the handle */
		header: Snippet<[C, Action<HTMLElement, void>]>;
		cell: Snippet<[C, R]>;
	}

	let {
		columns,
		rows,
		label,
		onreorder,
		'aria-label': ariaLabel,
		dragDisabled = false,
		locked = $bindable(false),
		columnBackground = '',
		fixedHeader,
		fixedCell,
		header,
		cell
	}: Props = $props();

	// one zone type per table: two tables on screen (a dialog over the page) must not trade columns
	const instanceId = $props.id();
	const zoneType = `fc-column-${instanceId}`;

	const FLIP_MS = 250;
	const reduceMotion =
		typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
	const flipMs = reduceMotion ? 0 : FLIP_MS;

	let dragging = $state<C[] | null>(null);
	const shown = $derived(dragging ?? columns);

	let scroller = $state<HTMLElement>();
	let zone = $state<HTMLElement>();

	// The library's handle gets only the events that may start a drag. Blocking the others
	// with stopPropagation would also starve Svelte's delegated handlers (the rename field's
	// Enter and Escape), so they are forwarded to a stand-in element instead. The disabled flag
	// of the library is a module-level store shared by every table, so the gate is here too.
	const handle: Action<HTMLElement, void> = (node) => {
		const standIn = document.createElement('div');
		const inner = dragHandle(standIn);
		node.tabIndex = 0;
		node.setAttribute('role', 'button');

		const forward = (event: Event) => {
			const target = event.target;
			if (dragDisabled || locked || (target instanceof Element && target.closest('[data-no-drag]'))) return;
			if (event instanceof KeyboardEvent) {
				standIn.dispatchEvent(new KeyboardEvent('keydown', { key: event.key }));
			} else {
				event.preventDefault();
				standIn.dispatchEvent(new Event(event.type, { cancelable: true }));
			}
		};
		const events = ['mousedown', 'touchstart', 'keydown'] as const;
		for (const name of events) node.addEventListener(name, forward);
		return {
			destroy() {
				for (const name of events) node.removeEventListener(name, forward);
				inner.destroy?.();
			}
		};
	};

	$effect(() => publishDragCursors(dragCursor.stroke, dragCursor.size, dragCursor.tipRatio));
	$effect(() => {
		document.documentElement.style.setProperty('--col-drag-opacity', String(dragColumnGhost.opacity));
	});

	// for a drop outside the zone: the other columns' centres and the last pointer x, both
	// within the scrolling box
	let centres = new Map<string, number>();
	let pointerX = 0;

	function contentX(clientX: number): number {
		if (!scroller) return clientX;
		return clientX - scroller.getBoundingClientRect().left + scroller.scrollLeft;
	}

	function measureColumns(): void {
		centres = new Map();
		if (!zone) return;
		for (const el of zone.querySelectorAll<HTMLElement>(':scope > [data-column-id]')) {
			const rect = el.getBoundingClientRect();
			centres.set(el.dataset.columnId ?? '', contentX((rect.left + rect.right) / 2));
		}
	}

	function trackPointer(event: MouseEvent | TouchEvent): void {
		const point = 'touches' in event ? event.touches[0] : event;
		if (point) pointerX = contentX(point.clientX);
	}

	function endDrag(): void {
		document.documentElement.classList.remove('fc-col-dragging');
		window.removeEventListener('mousemove', trackPointer);
		window.removeEventListener('touchmove', trackPointer);
	}

	function consider(event: CustomEvent<DndEvent<C>>): void {
		dragging = event.detail.items;
		if (event.detail.info.trigger === TRIGGERS.DRAG_STARTED) {
			measureColumns();
			document.documentElement.classList.add('fc-col-dragging');
			window.addEventListener('mousemove', trackPointer, { passive: true });
			window.addEventListener('touchmove', trackPointer, { passive: true });
		}
	}

	function finalize(event: CustomEvent<DndEvent<C>>): void {
		const { items, info } = event.detail;
		let ids = items.map((item) => item.id);
		if (info.trigger === TRIGGERS.DROPPED_OUTSIDE_OF_ANY) {
			// Released beyond the zone: the nearest slot to where the pointer last was.
			const others = ids.filter((id) => id !== info.id);
			const where = others.map((id) => centres.get(id));
			if (where.every((x) => x !== undefined)) {
				ids = moveTo(ids, info.id, insertionIndex(pointerX, where as number[]));
			}
		}
		endDrag();
		dragging = null;
		onreorder(ids);
	}

	$effect(() => endDrag);
</script>

{#snippet lockButton()}
	<BareIconButton
		icon={locked ? IconLock : IconLockOpen2}
		label={locked ? 'Unlock Columns' : 'Lock Columns'}
		onclick={() => (locked = !locked)}
	/>
{/snippet}

<div bind:this={scroller} class="fc-col-scroller overflow-x-auto overflow-y-hidden pb-2">
	<div
		class="fc-col-grid"
		style:grid-template-rows="repeat({rows.length + 1}, auto)"
		role="group"
		aria-label={ariaLabel}
		data-drag-disabled={dragDisabled || locked || undefined}
	>
		<div class="fc-col-fixed">
			{@render fixedHeader(lockButton)}
			{#each rows as row (row.id)}
				{@render fixedCell(row)}
			{/each}
		</div>
		<div
			bind:this={zone}
			class="fc-col-zone"
			use:dragHandleZone={{
				items: shown,
				flipDurationMs: flipMs,
				type: zoneType,
				useCursorForDetection: true,
				morphDisabled: true,
				dropTargetStyle: {}
			}}
			onconsider={consider}
			onfinalize={finalize}
		>
			{#each shown as column (column.id)}
				<div
					class="fc-col {columnBackground}"
					data-column-id={column.id}
					role="group"
					aria-label={label(column)}
					animate:flip={{ duration: flipMs }}
				>
					{@render header(column, handle)}
					{#each rows as row (row.id)}
						{@render cell(column, row)}
					{/each}
				</div>
			{/each}
		</div>
	</div>
</div>

<style>
	.fc-col-scroller {
		--fc-col-reach: 100vh;
	}
	.fc-col-grid {
		display: grid;
		grid-template-columns: max-content max-content;
		width: max-content;
	}
	.fc-col-fixed {
		position: sticky;
		left: 0;
		z-index: 20;
		display: grid;
		grid-column: 1;
		grid-row: 1 / -1;
		grid-template-rows: subgrid;
	}
	/* hit area only: padding and negative margin cancel, and only upwards (see the notes) */
	.fc-col-zone {
		display: grid;
		grid-column: 2;
		grid-row: 1 / -1;
		grid-auto-flow: column;
		grid-auto-columns: max-content;
		grid-template-rows: subgrid;
		padding-top: var(--fc-col-reach);
		margin-top: calc(-1 * var(--fc-col-reach));
		pointer-events: none;
	}
	.fc-col {
		display: grid;
		grid-row: 1 / -1;
		grid-template-rows: subgrid;
		pointer-events: auto;
	}

	/* the library writes inline cursors; only !important beats them */
	.fc-col-grid:not([data-drag-disabled]) :global(.fc-col-handle) {
		cursor: var(--col-cursor-move, grab) !important;
		touch-action: none;
		user-select: none;
	}
	.fc-col-grid[data-drag-disabled] :global(.fc-col-handle) {
		cursor: default !important;
	}

	:global(#dnd-action-dragged-el) {
		opacity: var(--col-drag-opacity, 0.55) !important;
		box-shadow: 0 8px 24px rgb(0 0 0 / 0.25);
		outline: none;
	}
	:global(html.fc-col-dragging),
	:global(html.fc-col-dragging *),
	:global(#dnd-action-dragged-el),
	:global(#dnd-action-dragged-el *) {
		cursor: var(--col-cursor-grab, grabbing) !important;
	}
	:global(html.fc-col-dragging) {
		user-select: none;
	}
</style>
