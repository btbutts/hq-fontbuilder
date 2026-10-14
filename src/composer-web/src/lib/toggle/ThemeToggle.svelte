<script lang="ts">
	import IconSunMoon from '@tabler/icons-svelte/icons/sun-moon';
	import { theme } from '../styles.svelte';
	import Toggle from './Toggle.svelte';
</script>

<Toggle
	label="Dark mode"
	icon={IconSunMoon}
	title="switch between the light and the dark theme"
	checked={theme.dark}
	onchange={(enabled) => theme.set(enabled)}
/>
