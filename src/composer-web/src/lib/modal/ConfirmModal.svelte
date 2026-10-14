<script lang="ts">
	import CtrlButton from '../button/CtrlButton.svelte';
	import { colors } from '../styles.svelte';

	interface Props {
		title: string;
		/** what is about to happen, in a sentence or two */
		message: string;
		confirmLabel?: string;
		cancelLabel?: string;
		onconfirm: () => void;
		oncancel: () => void;
	}

	let {
		title,
		message,
		confirmLabel = 'Confirm',
		cancelLabel = 'Cancel',
		onconfirm,
		oncancel
	}: Props = $props();
</script>

<svelte:window onkeydown={(event) => event.key === 'Escape' && oncancel()} />

<!-- a click on the dimmed page behind the dialog cancels -->
<button
	type="button"
	class="fixed inset-0 z-20 cursor-default border-0 {colors.modalOverlay}"
	aria-label="cancel"
	onclick={oncancel}
></button>

<div
	role="alertdialog"
	aria-modal="true"
	aria-labelledby="confirm-title"
	aria-describedby="confirm-message"
	class="fixed top-[15vh] left-1/2 z-30 flex w-[min(96vw,30rem)] -translate-x-1/2 flex-col rounded border {colors.border} {colors.modalBackground} {colors.floatingShadow}"
>
	<div class="flex items-start justify-between gap-4 border-b px-5 py-3 {colors.border}">
		<h2 id="confirm-title" class="m-0 text-[1.2rem] font-semibold">{title}</h2>
		<CtrlButton function="modal.CLOSE" onclick={oncancel} />
	</div>
	<p id="confirm-message" class="m-0 px-5 py-4 {colors.textSecondary}">{message}</p>
	<div class="flex justify-end gap-3 border-t px-5 py-3 {colors.border}">
		<CtrlButton padding="px-3 py-1.5" onclick={oncancel}>{cancelLabel}</CtrlButton>
		<CtrlButton padding="px-3 py-1.5" fontWeight="font-medium" onclick={onconfirm}>
			{confirmLabel}
		</CtrlButton>
	</div>
</div>
