// Phase 5: execution trace and step-through view.
// Renders into #stageDetail when the Interpreter stage card (index 3) is clicked.
// Same pattern as parser-view.js and semantic-view.js; moves into app.js in Phase 7.

const INTERPRETER_CARD_INDEX = 3;
const PLAY_INTERVAL_MS = 600;

let lastRun = null;
let stepIndex = 0;
let playTimer = null;

const originalFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const response = await originalFetch(...args);
  const target = args[0];
  const url = typeof target === "string" ? target : target?.url ?? "";
  if (url.includes("/api/run")) {
    stopPlay();
    stepIndex = 0;
    response.clone().json().then((data) => { lastRun = data; }).catch(() => {});
  }
  return response;
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function currentTrace() {
  return Array.isArray(lastRun?.trace) ? lastRun.trace : [];
}

function note(text) {
  return `<div class="tv-note">${esc(text)}</div>`;
}

function renderTrace() {
  const detail = document.getElementById("stageDetail");
  if (!detail) return;

  if (!lastRun) {
    detail.innerHTML = note("Run a program to see its execution trace.");
    return;
  }

  const stage = lastRun.stages?.[INTERPRETER_CARD_INDEX];
  if (stage?.status === "skipped") {
    detail.innerHTML = note("Interpreter skipped. An earlier stage stopped the run; see Problems.");
    return;
  }
  if (stage?.status === "not_implemented") {
    detail.innerHTML = note(`Not run yet · ${stage.detail}.`);
    return;
  }

  const trace = currentTrace();
  if (!trace.length) {
    detail.innerHTML = note("No steps were recorded for this run.");
    return;
  }

  stepIndex = Math.min(Math.max(stepIndex, 0), trace.length - 1);
  const current = trace[stepIndex];

  const rows = trace.map((entry, index) => `
    <tr class="tv-row${index === stepIndex ? " active" : ""}" data-trace-step="${index}">
      <td class="tv-num">${esc(entry.step)}</td>
      <td class="tv-num">${esc(entry.line)}</td>
      <td><code>${esc(entry.operation)}</code></td>
      <td>${esc(entry.result)}</td>
    </tr>`).join("");

  const variables = current.variables ?? [];
  const variableRows = variables.length
    ? variables.map((v) => `
        <tr>
          <td><code>${esc(v.name)}</code></td>
          <td>${esc(v.type)}</td>
          <td>${esc(v.value)}</td>
        </tr>`).join("")
    : `<tr><td colspan="3" class="tv-empty">No variables in scope.</td></tr>`;

  const playing = playTimer !== null;

  detail.innerHTML = `
    <div class="tv-card">
      <div class="tv-head">
        <span class="tv-title">Execution trace</span>
        <span class="tv-count">Step ${stepIndex + 1} of ${trace.length}</span>
      </div>
      <div class="tv-controls">
        <button type="button" class="tv-btn" data-trace-action="first">First</button>
        <button type="button" class="tv-btn" data-trace-action="prev">Prev</button>
        <button type="button" class="tv-btn" data-trace-action="play">${playing ? "Pause" : "Play"}</button>
        <button type="button" class="tv-btn" data-trace-action="next">Next</button>
        <button type="button" class="tv-btn" data-trace-action="last">Last</button>
      </div>
      <div class="tv-table-wrap">
        <table class="tv-table">
          <thead><tr><th>STEP</th><th>LINE</th><th>OPERATION</th><th>RESULT</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
    <div class="tv-card">
      <div class="tv-head">
        <span class="tv-title">Variables at step ${stepIndex + 1}</span>
      </div>
      <table class="tv-table">
        <thead><tr><th>NAME</th><th>TYPE</th><th>VALUE</th></tr></thead>
        <tbody>${variableRows}</tbody>
      </table>
    </div>
    <div class="tv-footer">${lastRun.ok ? "Process exited successfully" : "Process stopped with an error"}</div>
  `;

  detail.querySelector(".tv-row.active")?.scrollIntoView({ block: "nearest" });
}

function stepTo(index) {
  const total = currentTrace().length;
  if (!total) return;
  stepIndex = Math.min(Math.max(index, 0), total - 1);
}

function stopPlay() {
  if (playTimer !== null) {
    clearInterval(playTimer);
    playTimer = null;
  }
}

function togglePlay() {
  if (playTimer !== null) {
    stopPlay();
    renderTrace();
    return;
  }
  playTimer = setInterval(() => {
    if (!document.querySelector("#stageDetail .tv-card")) {
      stopPlay();
      return;
    }
    if (stepIndex >= currentTrace().length - 1) {
      stopPlay();
      renderTrace();
      return;
    }
    stepIndex += 1;
    renderTrace();
  }, PLAY_INTERVAL_MS);
  renderTrace();
}

// Open the trace when the Interpreter card is clicked.
document.getElementById("stages")?.addEventListener("click", (event) => {
  const card = event.target.closest(".stage");
  if (!card) return;
  const cards = Array.from(document.querySelectorAll("#stages .stage"));
  if (cards.indexOf(card) === INTERPRETER_CARD_INDEX) renderTrace();
});

// Step controls and row selection inside the detail panel.
document.getElementById("stageDetail")?.addEventListener("click", (event) => {
  const action = event.target.closest("[data-trace-action]");
  if (action) {
    const total = currentTrace().length;
    switch (action.dataset.traceAction) {
      case "first": stepTo(0); break;
      case "prev": stepTo(stepIndex - 1); break;
      case "next": stepTo(stepIndex + 1); break;
      case "last": stepTo(total - 1); break;
      case "play": togglePlay(); return;
    }
    renderTrace();
    return;
  }
  const row = event.target.closest("[data-trace-step]");
  if (row) {
    stepTo(Number(row.dataset.traceStep));
    renderTrace();
  }
});