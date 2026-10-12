/* Group page: render every code point of a group for each style of one family,
   each glyph in a box the size of the base family's cell. */

"use strict";

const params = new URLSearchParams(window.location.search);
const familyLabel = params.get("family");
const groupId = params.get("group");
const GLYPH_EM_PX = 48;

let currentVersion = -1;

async function fetchState() {
  const response = await fetch("/api/state");
  if (!response.ok) throw new Error(`/api/state: ${response.status}`);
  return response.json();
}

function groupCodepoints(group) {
  const points = [];
  for (const [low, high] of group.ranges) {
    for (let cp = low; cp <= high; cp += 1) points.push(cp);
  }
  return points;
}

function applyCellGeometry(base) {
  const root = document.documentElement;
  if (!base) {
    root.style.setProperty("--cell-w", "0.6");
    root.style.setProperty("--cell-h", "1.2");
    root.style.setProperty("--ascent", "0.93");
    return;
  }
  const upm = base.unitsPerEm;
  root.style.setProperty("--cell-w", String(base.cellAdvance / upm));
  root.style.setProperty("--cell-h", String((base.ascent - base.descent) / upm));
  root.style.setProperty("--ascent", String(base.ascent / upm));
}

function installFontFaces(family) {
  let styleEl = document.getElementById("fc-font-faces");
  if (!styleEl) {
    styleEl = document.createElement("style");
    styleEl.id = "fc-font-faces";
    document.head.appendChild(styleEl);
  }
  const rules = family.styles.map((style, index) => `
    @font-face {
      font-family: "fc-style-${index}";
      src: url("/fonts/${encodeURIComponent(family.label)}/${encodeURIComponent(style.file)}");
    }`);
  styleEl.textContent = rules.join("\n");
}

function glyphBox(cp, fontClass) {
  const box = document.createElement("span");
  box.className = "cellbox";
  const glyph = document.createElement("span");
  glyph.className = `glyph ${fontClass}`;
  glyph.textContent = String.fromCodePoint(cp);
  const baseline = document.createElement("span");
  baseline.className = "baseline";
  const label = document.createElement("span");
  label.className = "cp";
  label.textContent = `U+${cp.toString(16).toUpperCase().padStart(4, "0")}`;
  box.append(glyph, baseline, label);
  return box;
}

function renderStyleSection(style, index, codepoints) {
  const section = document.createElement("section");
  section.className = "style-section";
  const heading = document.createElement("h3");
  heading.textContent = `${style.file} — ${style.style}`;
  const meta = document.createElement("p");
  meta.className = "meta";
  const [present, total] = style.coverage[groupId];
  meta.textContent = `weight ${style.weight}, ${style.italic ? "italic" : "upright"}, ` +
    `upm ${style.unitsPerEm}, ascent ${style.ascent}, descent ${style.descent}, ` +
    `cell advance ${style.cellAdvance}; group coverage ${present}/${total}`;
  const grid = document.createElement("div");
  grid.className = "glyph-grid";
  grid.style.fontSize = `${GLYPH_EM_PX}px`;
  for (const cp of codepoints) {
    grid.appendChild(glyphBox(cp, `fc-style-${index}`));
  }
  section.append(heading, meta, grid);
  return section;
}

function updateChooseBar(state) {
  const chosen = state.choices[groupId] ?? null;
  document.getElementById("choose-this").checked = chosen === familyLabel;
  document.getElementById("choose-none").checked = chosen === null;
  const status = document.getElementById("choose-status");
  status.textContent = chosen === null
    ? "no family chosen for this group"
    : chosen === familyLabel
      ? `this family is the chosen source`
      : `currently sourced from ${chosen} — choosing here replaces it`;
}

async function postChoose(family) {
  const status = document.getElementById("choose-status");
  const response = await fetch("/api/choose", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ group: groupId, family }),
  });
  const payload = await response.json();
  if (!response.ok) {
    status.textContent = payload.error ?? `error ${response.status}`;
  }
  await refresh();
}

function installChooseBar() {
  document.getElementById("choose-this").addEventListener("change", () => {
    postChoose(familyLabel);
  });
  document.getElementById("choose-none").addEventListener("change", () => {
    postChoose(null);
  });
}

function render(state) {
  currentVersion = state.version;
  const group = state.groups.find((entry) => entry.id === groupId);
  const family = state.families.find((entry) => entry.label === familyLabel);
  if (!group || !family) {
    document.getElementById("title").textContent =
      `unknown family or group: ${familyLabel} / ${groupId}`;
    return;
  }
  document.getElementById("title").textContent =
    `${family.label} — ${group.id}${group.atomic ? " (atomic)" : ""}`;
  document.getElementById("subtitle").textContent =
    `${group.label}; ${group.total} code points; cell of base family ` +
    `${state.base ? state.base.family : "(none configured)"}.`;
  applyCellGeometry(state.base);
  installFontFaces(family);

  const host = document.getElementById("styles");
  host.replaceChildren();
  const codepoints = groupCodepoints(group);
  family.styles.forEach((style, index) => {
    host.appendChild(renderStyleSection(style, index, codepoints));
  });
  updateChooseBar(state);
}

/* Glyphs the font has no cmap entry for render as the browser's .notdef box, which
   is itself a useful signal on this page: missing code points stand out visually. */

async function refresh() {
  try {
    render(await fetchState());
  } catch (error) {
    console.error(error);
  }
}

async function pollVersion() {
  try {
    const response = await fetch("/api/version");
    const { version } = await response.json();
    if (version !== currentVersion) await refresh();
  } catch (error) {
    console.error(error);
  }
}

installChooseBar();
refresh();
setInterval(pollVersion, 2000);
