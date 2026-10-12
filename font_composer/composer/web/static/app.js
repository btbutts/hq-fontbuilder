/* Coverage table page: fetch /api/state, render the matrix, poll for changes. */

"use strict";

let currentVersion = -1;

async function fetchState() {
  const response = await fetch("/api/state");
  if (!response.ok) throw new Error(`/api/state: ${response.status}`);
  return response.json();
}

function cellClass(present, total) {
  if (present === 0) return "empty";
  if (present === total) return "complete";
  return "partial";
}

function renderTable(state) {
  const head = document.getElementById("coverage-head");
  const body = document.getElementById("coverage-body");
  head.replaceChildren();
  body.replaceChildren();

  const corner = document.createElement("th");
  corner.textContent = "group";
  head.appendChild(corner);
  for (const family of state.families) {
    const th = document.createElement("th");
    th.textContent = family.label;
    if (family.errors.length) th.textContent += " ⚠";
    head.appendChild(th);
  }

  for (const group of state.groups) {
    const tr = document.createElement("tr");
    const label = document.createElement("td");
    label.className = "group-id";
    label.textContent = group.id;
    if (group.atomic) {
      const flag = document.createElement("span");
      flag.className = "atomic-flag";
      flag.textContent = " atomic";
      label.appendChild(flag);
    }
    tr.appendChild(label);

    for (const family of state.families) {
      const [present, total] = state.coverage[family.label][group.id];
      const td = document.createElement("td");
      td.className = `cell ${cellClass(present, total)}`;
      if (state.choices[group.id] === family.label) td.classList.add("chosen");
      td.textContent = `${present}/${total}`;
      td.title = `${family.label} — ${group.label}`;
      td.addEventListener("click", () => {
        const params = new URLSearchParams({ family: family.label, group: group.id });
        window.location.href = `/group.html?${params}`;
      });
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
}

function renderSummary(state) {
  const host = document.getElementById("summary");
  host.replaceChildren();
  const list = document.createElement("dl");
  for (const entry of state.summary) {
    const dt = document.createElement("dt");
    dt.textContent = entry.group;
    const dd = document.createElement("dd");
    if (entry.chosen) {
      dd.textContent = entry.chosen;
    } else {
      dd.className = "unsourced";
      dd.textContent = entry.candidates.length
        ? `unsourced — full coverage: ${entry.candidates.join(", ")}`
        : "unsourced — no family covers this group fully";
    }
    list.append(dt, dd);
  }
  host.appendChild(list);
}

function renderProblems(state) {
  const host = document.getElementById("problems");
  host.replaceChildren();
  for (const problem of state.problems) {
    const li = document.createElement("li");
    li.textContent = `${problem.path}: ${problem.reason}`;
    host.appendChild(li);
  }
}

function render(state) {
  currentVersion = state.version;
  renderTable(state);
  renderSummary(state);
  renderProblems(state);
}

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

refresh();
setInterval(pollVersion, 2000);
