<script lang="ts">
	import { goto } from '$app/navigation';
	import { consoleStore } from '#lib/console.svelte.js';

	const state = $derived(consoleStore.state);

	function cellClasses(present: number, total: number): string {
		if (present === 0) return 'bg-[#ececf0] text-[#9a9aa0]';
		if (present === total) return 'bg-[#d8f3dc] text-[#2d6a4f]';
		return 'bg-[#fff3cd] text-[#9c7c00]';
	}

	function openGroup(familyLabel: string, groupId: string): void {
		const params = new URLSearchParams({ family: familyLabel, group: groupId });
		void goto(`/group?${params}`);
	}
</script>

<h1 class="mb-1 text-[1.4rem] font-semibold">font-composer</h1>
<p class="mt-0 max-w-5xl text-[#555]">
	Coverage by glyph group and family. Click a cell to inspect the group's glyphs for that
	family. Atomic groups count as sourced only at 100%.
</p>

{#if state === null}
	<p class="mt-4 text-[#555]">{consoleStore.error ?? 'loading…'}</p>
{:else}
	<table class="mt-4 border-collapse">
		<thead>
			<tr>
				<th class="border border-[#b9b9bd] bg-[#f0f0f4] px-2 py-1 font-semibold whitespace-nowrap">group</th>
				{#each state.families as family (family.label)}
					<th class="border border-[#b9b9bd] bg-[#f0f0f4] px-2 py-1 font-semibold whitespace-nowrap">
						{family.label}{family.errors.length ? ' ⚠' : ''}
					</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each state.groups as group (group.id)}
				<tr>
					<td class="border border-[#b9b9bd] px-2 py-1 text-left font-mono whitespace-nowrap">
						{group.id}{#if group.atomic}<span class="text-[0.8em] text-[#b02e2e]"> atomic</span>{/if}
					</td>
					{#each state.families as family (family.label)}
						{@const [present, total] = state.coverage[family.label]?.[group.id] ?? [0, group.total]}
						{@const chosen = state.choices[group.id] === family.label}
						<td
							class="cursor-pointer border border-[#b9b9bd] px-2 py-1 text-center whitespace-nowrap outline-2 outline-offset-[-2px] outline-transparent hover:outline-[#1b4965] {cellClasses(present, total)} {chosen ? 'font-bold shadow-[inset_0_0_0_3px_#1b4965]' : ''}"
							title="{family.label} — {group.label}"
							onclick={() => openGroup(family.label, group.id)}
						>
							{present}/{total}
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>

	<h2 class="mt-8 text-[1.1rem] font-semibold">Composition so far</h2>
	<dl class="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-[0.15rem]">
		{#each state.summary as entry (entry.group)}
			<dt class="font-mono">{entry.group}</dt>
			{#if entry.chosen}
				<dd class="m-0">{entry.chosen}</dd>
			{:else}
				<dd class="m-0 text-[#b02e2e]">
					{entry.candidates.length
						? `unsourced — full coverage: ${entry.candidates.join(', ')}`
						: 'unsourced — no family covers this group fully'}
				</dd>
			{/if}
		{/each}
	</dl>

	<h2 class="mt-8 text-[1.1rem] font-semibold">Problem fonts</h2>
	<ul>
		{#each state.problems as problem (problem.path)}
			<li class="font-mono text-[0.9em] text-[#b02e2e]">{problem.path}: {problem.reason}</li>
		{:else}
			<li class="text-[#777]">none</li>
		{/each}
	</ul>
{/if}
