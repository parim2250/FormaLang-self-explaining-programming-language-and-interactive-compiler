// Phase 7: "Show how it works" tabs: Tokens, AST, Semantic, Execution, Summary.
// Tokens, AST, Semantic and Execution reuse the stage-card renderers that already
// exist (app.js, parser-view.js, semantic-view.js, trace-view.js) by activating the
// matching stage card. Summary is rendered here. The default Write → Run → Output
// view is untouched; the tabs live inside the collapsible panel only.

const CARD_FOR_TAB = { tokens: 0, ast: 1, semantic: 2, execution: 3 };
const TAB_FOR_CARD = ["tokens", "ast", "semantic", "execution"];
const TABS = [
  { id: "tokens", label: "Tokens" },
  { id: "ast", label: "AST" },
  { id: "semantic", label: "Semantic" },
  { id: "execution", label: "Execution" },
  { id: "summary", label: "Summary" },
];
const STAGE_ORDER = ["Lexer", "Parser", "Semantic analyzer", "Interpreter"];

let activeTab = "summary";
let lastRun = null;

const originalFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const response = await originalFetch(...args);
  const target = args[0];
  const url = typeof target === "string" ? target : target?.url ?? "";
  if (url.includes("/api/run")) {
    response.clone().json().then((data) => {
      lastRun = data;
      // Other wrappers store their copy of the run too. Wait a moment so the
      // open tab re-renders with this run, not the previous one.
      setTimeout(refreshIfOpen, 60);
    }).catch(() => {});
  }
  return response;
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function note(text) {
  return `<div class="tv-note">${esc(text)}</div>`;
}

function isOpen() {
  const body = document.getElementById("howBody");
  return !!body && body.offsetParent !== null;
}

function highlight(id) {
  activeTab = id;
  document.querySelectorAll("#howTabs .how-tab").forEach((button) => {
    const on = button.dataset.tab === id;
    button.classList.toggle("active", on);
    button.setAttribute("aria-selected", on ? "true" : "false");
  });
}

function selectTab(id) {
  highlight(id);
  if (id === "summary") {
    renderSummary();
    return;
  }
  const card = document.querySelectorAll("#stages .stage")[CARD_FOR_TAB[id]];
  card?.click();
}

function refreshIfOpen() {
  if (isOpen()) selectTab(activeTab);
}

function renderSummary() {
  const detail = document.getElementById("stageDetail");
  if (!detail) return;
  if (!lastRun) {
    detail.innerHTML = note("Run a program to see the summary.");
    return;
  }

  const stages = lastRun.stages ?? [];
  const byName = (name) => stages.find((s) => s.name === name);
  const totalMs = stages.reduce((sum, s) => sum + (Number(s.time_ms) || 0), 0);
  const timeText = totalMs < 1 ? "under 1 ms" : `${Math.round(totalMs)} ms`;
  const verdict = lastRun.ok ? "Completed" : "Stopped";

  const tokenMatch = /(\d+)\s+tokens/.exec(byName("Lexer")?.detail ?? "");
  const astMatch = /(\d+)\s+AST node/.exec(byName("Parser")?.detail ?? "");
  const trace = lastRun.trace ?? [];
  const maxDepth = trace.reduce((max, s) => Math.max(max, s.depth ?? 0), 0);
  const outputLines = lastRun.output ?? [];
  const problemCount = (lastRun.diagnostics ?? []).length;
  const symbolCount = (lastRun.symbols ?? []).length;

  const chips = [
    `<span class="sum-chip passed">Source</span>`,
    ...STAGE_ORDER.map((name) => {
      const status = byName(name)?.status ?? "pending";
      return `<span class="sum-chip ${esc(status)}">${esc(name)}</span>`;
    }),
    `<span class="sum-chip ${lastRun.ok ? "passed" : "failed"}">Output</span>`,
  ].join(`<span class="sum-arrow">→</span>`);

  const stat = (label, value) => `
    <div class="sum-stat">
      <div class="label">${esc(label)}</div>
      <div class="value">${esc(value)}</div>
    </div>`;

  const stats = [
    stat("Tokens", tokenMatch ? tokenMatch[1] : "–"),
    stat("AST nodes", astMatch ? astMatch[1] : "–"),
    stat("Symbols", symbolCount),
    stat("Trace steps", trace.length),
    stat("Max call depth", maxDepth),
    stat("Output lines", outputLines.length),
    stat("Problems", problemCount),
  ].join("");

  const stageRows = stages.map((s) => {
    const time = s.status === "skipped" ? "–" : `${(Number(s.time_ms) || 0).toFixed(2)} ms`;
    return `
    <tr>
      <td>${esc(s.name)}</td>
      <td><span class="sum-chip ${esc(s.status)}">${esc(String(s.status).replace("_", " "))}</span></td>
      <td class="tv-num">${esc(time)}</td>
      <td>${esc(s.detail || "")}</td>
    </tr>`;
  }).join("");

  detail.innerHTML = `
    <div class="sum-verdict">${esc(verdict)} · in ${esc(timeText)}</div>
    <div class="sum-strip">${chips}</div>
    <div class="sum-stats">${stats}</div>
    <div class="tv-card">
      <div class="tv-head"><span class="tv-title">Stages</span></div>
      <table class="tv-table">
        <thead><tr><th>STAGE</th><th>STATUS</th><th>TIME</th><th>DETAIL</th></tr></thead>
        <tbody>${stageRows}</tbody>
      </table>
    </div>
    <div class="tv-card">
      <div class="tv-head"><span class="tv-title">Output</span></div>
      <pre class="sum-output">${esc(outputLines.length ? outputLines.join("\n") : "(no output)")}</pre>
    </div>
  `;
}

function mountTabs() {
  const stages = document.getElementById("stages");
  if (!stages || document.getElementById("howTabs")) return;

  const bar = document.createElement("div");
  bar.id = "howTabs";
  bar.className = "how-tabs";
  bar.setAttribute("role", "tablist");
  bar.innerHTML = TABS.map((tab) =>
    `<button type="button" role="tab" class="how-tab" data-tab="${tab.id}" aria-selected="false">${tab.label}</button>`
  ).join("");
  stages.parentNode.insertBefore(bar, stages);

  bar.addEventListener("click", (event) => {
    const button = event.target.closest(".how-tab");
    if (button) selectTab(button.dataset.tab);
  });

  // Clicking a stage card directly moves the tab highlight to match.
  stages.addEventListener("click", (event) => {
    const card = event.target.closest(".stage");
    if (!card) return;
    const index = Array.from(stages.querySelectorAll(".stage")).indexOf(card);
    if (TAB_FOR_CARD[index] !== undefined) highlight(TAB_FOR_CARD[index]);
  });

  // Opening the panel shows the active tab.
  document.getElementById("howToggle")?.addEventListener("click", () => {
    setTimeout(() => {
      if (isOpen()) selectTab(activeTab);
    }, 0);
  });

  highlight(activeTab);
}

mountTabs();