// Phase 8: adds a plain-language hint under each Problem.
// app.js still renders the Problems list. This file adds one line to each item
// that matches a diagnostic from the last run (matched by code and line:col).

let lastRun = null;

const originalFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const response = await originalFetch(...args);
  const target = args[0];
  const url = typeof target === "string" ? target : target?.url ?? "";
  if (url.includes("/api/run")) {
    response.clone().json().then((data) => {
      lastRun = data;
      decorate();
    }).catch(() => {});
    setTimeout(decorate, 80);
  }
  return response;
};

function decorate() {
  const list = document.getElementById("problemsView");
  if (!list || !lastRun) return;
  const diagnostics = Array.isArray(lastRun.diagnostics) ? lastRun.diagnostics : [];

  list.querySelectorAll(".problem").forEach((item) => {
    if (item.querySelector(".problem-hint")) return;
    const text = item.textContent || "";
    const match = diagnostics.find((d) =>
      d.hint && text.includes(d.code) && text.includes(`line ${d.line}:${d.col}`)
    );
    if (!match) return;
    const hint = document.createElement("div");
    hint.className = "problem-hint";
    hint.textContent = "Hint: " + match.hint;
    item.appendChild(hint);
  });
}

// Problems are re-rendered by app.js on every run; add hints again each time.
const problemsView = document.getElementById("problemsView");
if (problemsView) {
  new MutationObserver(decorate).observe(problemsView, { childList: true });
}