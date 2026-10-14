<script lang="ts">
	import { theme } from '../styles.svelte';
	import Toggle from './Toggle.svelte';
</script>

<Toggle
	label="Dark mode"
	title="switch between the light and the dark theme"
	checked={theme.dark}
	onchange={(enabled) => theme.set(enabled)}
/>
