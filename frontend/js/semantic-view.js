// Phase 4: Semantic analyzer view.
// Adds the Semantic stage detail: symbol table and type/scope checks.
// Same pattern as parser-view.js: wraps fetch to keep the last /api/run result,
// and renders into #stageDetail when the Semantic card (third card) is clicked.

const SEMANTIC_CARD_INDEX = 2;

let lastRun = null;

const nativeFetch = window.fetch.bind(window);
window.fetch = async (input, init) => {
  const response = await nativeFetch(input, init);
  const url = typeof input === "string" ? input : input.url;
  if (url && url.endsWith("/api/run")) {
    response.clone().json().then((data) => { lastRun = data; }).catch(() => {});
  }
  return response;
};

const stagesEl = document.getElementById("stages");
const detailEl = document.getElementById("stageDetail");

stagesEl.addEventListener("click", (event) => {
  const card = event.target.closest(".stage");
  if (!card) return;
  const cards = [...stagesEl.querySelectorAll(".stage")];
  if (cards.indexOf(card) !== SEMANTIC_CARD_INDEX) return;
  renderSemantic();
});

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function note(text) {
  return el("p", "sv-note", text);
}

function card(title, body) {
  const wrap = el("div", "sv-card");
  wrap.append(el("div", "sv-title", title), body);
  return wrap;
}

function symbolTable(symbols) {
  const table = el("table", "sv-table");
  const head = el("thead");
  const headRow = el("tr");
  for (const label of ["SYMBOL", "DECLARED TYPE", "INFERRED TYPE", "SCOPE"]) {
    headRow.append(el("th", null, label));
  }
  head.append(headRow);

  const body = el("tbody");
  for (const sym of symbols) {
    const row = el("tr");
    row.append(
      el("td", "sv-name", sym.name),
      el("td", "sv-type", sym.declared_type),
      el("td", "sv-type", sym.inferred_type ?? "—"),
      el("td", "sv-scope", sym.scope),
    );
    body.append(row);
  }
  table.append(head, body);
  return table;
}

function checks(issues) {
  const wrap = el("div", "sv-checks");
  if (issues.length === 0) {
    wrap.append(el("p", "sv-ok", "No type or scope errors."));
    return wrap;
  }
  for (const issue of issues) {
    const row = el("div", "sv-issue");
    row.append(
      el("span", "sv-code", issue.code),
      el("span", "sv-msg", issue.message),
      el("span", "sv-pos", `${issue.line}:${issue.col}`),
    );
    wrap.append(row);
  }
  return wrap;
}

function renderSemantic() {
  detailEl.replaceChildren();

  if (!lastRun) {
    detailEl.append(note("Run a program first, then open the Semantic stage."));
    return;
  }

  const stage = lastRun.stages.find((s) => s.name === "Semantic analyzer");
  if (!stage || stage.status === "skipped") {
    detailEl.append(
      note("The semantic analyzer did not run because an earlier stage stopped the program. See Problems."),
    );
    return;
  }

  const issues = lastRun.diagnostics.filter((d) => d.stage === "semantic");
  const symbols = lastRun.symbols || [];

  detailEl.append(
    card("Symbol table", symbols.length ? symbolTable(symbols) : note("No symbols declared.")),
    card("Type and scope checks", checks(issues)),
  );
}