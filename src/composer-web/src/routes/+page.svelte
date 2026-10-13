<script lang="ts">
	import { consoleStore } from '#lib/console.svelte.js';

	const state = $derived(consoleStore.state);

	function cellClasses(present: number, total: number): string {
		if (present === 0) return 'bg-[#ececf0] text-[#9a9aa0]';
		if (present === total) return 'bg-[#d8f3dc] text-[#2d6a4f]';
		return 'bg-[#fff3cd] text-[#9c7c00]';
	}

	function groupHref(familyLabel: string, groupId: string): string {
		const params = new URLSearchParams({ family: familyLabel, group: groupId });
		return `/group?${params}`;
	}

	function composeHref(groupId: string): string {
		return `/compose?${new URLSearchParams({ group: groupId })}`;
	}
</script>

<h1 class="mb-1 text-[1.4rem] font-semibold">font-composer</h1>
<p class="mt-0 max-w-5xl text-[#555]">
	Coverage by glyph group and family, measured on each family's reference style (the upright
	cut nearest Regular). Click a cell to inspect the group's glyphs for that family and to add
	the family to the group's inheritance order. Atomic groups count as sourced only at 100% and
	come from one family. A ≠ marks a group on which the family's styles hold different glyphs.
	<a href="/styles" class="ml-2 text-[#1b4965] underline">Style mapping →</a>
</p>

{#if state?.configError}
	<p class="mt-4 max-w-5xl rounded border border-[#b02e2e] bg-[#fdecec] px-3 py-2 text-[#b02e2e]">
		The configuration file does not parse, so the last good configuration is still in force and
		nothing will be saved until it is fixed: {state.configError}
	</p>
{/if}

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
						{@const position = (state.choices[group.id] ?? []).indexOf(family.label)}
						{@const uneven = state.uneven[family.label]?.includes(group.id) ?? false}
						<td
							class="border border-[#b9b9bd] p-0 text-center whitespace-nowrap {cellClasses(present, total)} {position >= 0 ? 'font-bold shadow-[inset_0_0_0_3px_#1b4965]' : ''}"
						>
							<a
								href={groupHref(family.label, group.id)}
								class="block px-2 py-1 outline-2 outline-offset-2 outline-transparent hover:outline-[#1b4965] focus-visible:outline-[#1b4965]"
								title="{family.label} — {group.label}{position >= 0 ? ` (number ${position + 1} in the inheritance order)` : ''}{uneven ? ' (styles differ)' : ''}"
							>
								{present}/{total}{uneven ? ' ≠' : ''}{#if position >= 0}<sup class="ml-0.5 text-[0.7em] text-[#1b4965]">{position + 1}</sup>{/if}
							</a>
						</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>

	<h2 class="mt-8 text-[1.1rem] font-semibold">Composition so far</h2>
	<p class="mt-0 max-w-5xl text-[#555]">
		Each group takes a glyph from the first family of its inheritance order that has one; the
		following families fill in what is missing. Click a category to see the combined result and
		to pick single glyphs.
	</p>
	<table class="border-collapse">
		<thead>
			<tr>
				<th class="border border-[#b9b9bd] bg-[#f0f0f4] px-3 py-1 text-left font-semibold">
					Glyph Categories
				</th>
				<th class="border border-[#b9b9bd] bg-[#f0f0f4] px-3 py-1 text-left font-semibold">
					Font Inheritance Order
				</th>
			</tr>
		</thead>
		<tbody>
			{#each state.summary as entry (entry.group)}
				<tr>
					<td class="border border-[#b9b9bd] px-3 py-1 font-mono whitespace-nowrap">
						{#if entry.order.length}
							<a href={composeHref(entry.group)} class="text-[#1b4965] underline"
								title="show the combined glyphs of {entry.group}">{entry.group}</a
							>
						{:else}
							{entry.group}
						{/if}
					</td>
					<td class="border border-[#b9b9bd] px-3 py-1">
						{#if entry.order.length}
							{entry.order.join(', ')}
							<span class="ml-2 text-[0.85em] text-[#777]"
								>{entry.covered}/{entry.total} code points</span
							>
						{:else}
							<span class="text-[#b02e2e]">
								{entry.candidates.length
									? `unsourced — full coverage: ${entry.candidates.join(', ')}`
									: 'unsourced — no family covers this group fully'}
							</span>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>

	<h2 class="mt-8 text-[1.1rem] font-semibold">Problem fonts</h2>
	<ul>
		{#each state.problems as problem (problem.path)}
			<li class="font-mono text-[0.9em] text-[#b02e2e]">{problem.path}: {problem.reason}</li>
		{:else}
			<li class="text-[#777]">none</li>
		{/each}
	</ul>
{/if}
