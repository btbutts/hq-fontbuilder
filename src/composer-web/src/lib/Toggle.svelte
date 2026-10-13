<script lang="ts">
	interface Props {
		checked: boolean;
		label: string;
		title?: string;
		disabled?: boolean;
		onchange?: (checked: boolean) => void;
	}

	let { checked, label, title, disabled = false, onchange }: Props = $props();
</script>

<!-- An on/off switch: a button with role "switch", so it works from the keyboard too. -->
<button
	type="button"
	role="switch"
	aria-checked={checked}
	{disabled}
	{title}
	class="inline-flex items-center gap-2 border-0 bg-transparent p-0 text-left enabled:cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
	onclick={() => onchange?.(!checked)}
>
	<span
		class="relative inline-block h-5 w-9 shrink-0 rounded-full transition-colors {checked
			? 'bg-[#1b4965]'
			: 'bg-[#b9b9bd]'}"
	>
		<span
			class="absolute top-0.5 left-0.5 size-4 rounded-full bg-white shadow transition-transform {checked
				? 'translate-x-4'
				: ''}"
		></span>
	</span>
	<span>{label}</span>
</button>
