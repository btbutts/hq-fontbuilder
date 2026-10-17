/**
 * The library's one entry point: pages and layouts import what they need from `#lib`.
 * Files inside `lib/` import each other by relative path, never from here (it would be a cycle).
 */

// Server data: the API calls and their types, and the stores that hold what they return
export * from './data/api.ts';
export { consoleStore } from './data/console.svelte.ts';
export { overlayStore } from './data/overlay.svelte.ts';
export { unicodeNames } from './data/unicodeNames.svelte.ts';
export { recalledScroll, rememberScroll } from './data/mainScroll.ts';

// Styles and tooltips
export { colors } from './styles.svelte.ts';
export { emphasis, tip } from './tooltip/tooltip.ts';
export { default as Tooltip } from './tooltip/Tooltip.svelte';

// Buttons, switches and other controls
export { default as BareIconButton } from './button/BareIconButton.svelte';
export { default as CtrlButton } from './button/CtrlButton.svelte';
export { default as PeekButton } from './button/PeekButton.svelte';
export { default as Dropdown } from './dropdown/Dropdown.svelte';
export { default as Slider } from './slider/Slider.svelte';
export { default as ThemeToggle } from './toggle/ThemeToggle.svelte';
export { default as Toggle } from './toggle/Toggle.svelte';
export { default as ViewToggles } from './toggle/ViewToggles.svelte';
export { viewOptions } from './toggle/viewOptions.svelte.ts';

// Page layout, tables and modals
export { default as PageHeader } from './layout/PageHeader.svelte';
export { default as StickyBar } from './layout/StickyBar.svelte';
export { ColumnOrder } from './table/columnOrder.svelte.ts';
export { default as ReorderableColumns } from './table/ReorderableColumns.svelte';
export { default as ConfirmModal } from './modal/ConfirmModal.svelte';
export { default as SelectGlyphCategories } from './modal/SelectGlyphCategories.svelte';
export { default as StyleMappingModal } from './modal/StyleMappingModal.svelte';

// Glyphs
export { familyColor, familyCssName, fontFaceRules, installFontFaces } from './glyph/families.ts';
export { clippedCount, describeFit } from './glyph/fitDisplay.ts';
export { default as GlyphChooser, type Candidate } from './glyph/GlyphChooser.svelte';
export { default as GlyphGrid } from './glyph/GlyphGrid.svelte';
export {
	FULL_GRID_MAX,
	PAGE_SIZE,
	geometryFor,
	type LayoutCell
} from './glyph/glyphLayout.ts';

// The build proof
export { BLOCK_SAMPLES, PROOF_TABLES } from './proof/boxTables.ts';
export { cellWidths, pixelCell } from './proof/cellGrid.ts';
export { default as ProofTable } from './proof/ProofTable.svelte';
