<script lang="ts">
	import { colors } from '../styles.svelte.ts';

	interface Props {
		value: number;
		min: number;
		max: number;
		step?: number;
		/** the accessible name */
		label: string;
	}

	let { value = $bindable(), min, max, step = 1, label }: Props = $props();

	// 0 to 1: how far the thumb is, for the filled part of the track
	const fraction = $derived(max > min ? (value - min) / (max - min) : 0);
</script>

<!-- A range input in the colours of `colors.slider`; its states are tints of them (see there). -->
<input
	type="range"
	aria-label={label}
	{min}
	{max}
	{step}
	bind:value
	class="fc-slider {colors.slider.primary} {colors.slider.track} {colors.slider.border}
		{colors.slider.filled} {colors.slider.hover} {colors.slider.pressed}"
	style="--fraction: {fraction}"
/>

<style>
	/* the input is the track: the filled part up to the thumb's centre, then the rest, outlined */
	.fc-slider {
		--thumb: var(--slider-primary);
		--filled: color-mix(in srgb, var(--slider-primary), var(--slider-filled));
		--stop: calc(0.5rem + (100% - 1rem) * var(--fraction));
		appearance: none;
		width: 8rem;
		height: 0.5rem;
		margin: 0.375rem 0;
		border-radius: 999px;
		background: linear-gradient(to right, var(--filled) var(--stop), var(--slider-track) var(--stop));
		box-shadow: inset 0 0 0 1px var(--slider-border);
		cursor: pointer;
	}
	.fc-slider:hover {
		--thumb: color-mix(in srgb, var(--slider-primary), var(--slider-hover));
	}
	.fc-slider:active {
		--thumb: color-mix(in srgb, var(--slider-primary), var(--slider-pressed));
		--filled: color-mix(in srgb, var(--slider-primary), var(--slider-pressed));
	}
	.fc-slider:focus-visible {
		outline: 2px solid var(--slider-primary);
		outline-offset: 4px;
	}
	.fc-slider::-webkit-slider-thumb {
		appearance: none;
		width: 1rem;
		height: 1rem;
		border: 0;
		border-radius: 50%;
		background: var(--thumb);
	}
	.fc-slider::-moz-range-thumb {
		width: 1rem;
		height: 1rem;
		border: 0;
		border-radius: 50%;
		background: var(--thumb);
	}
</style>
