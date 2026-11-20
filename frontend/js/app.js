import { EditorView, basicSetup } from "https://esm.sh/codemirror@6";
import { StreamLanguage, syntaxHighlighting, HighlightStyle } from "https://esm.sh/@codemirror/language@6";
import { tags as t } from "https://esm.sh/@lezer/highlight@1";

/* =========================================================
   CONSTANTS
   ========================================================= */
const STORAGE_KEY = "formalang.main.forma";
const PREF_KEY = "formalang.prefs";
const KEYWORDS = new Set(["if", "else", "while", "for", "return", "break", "continue", "true", "false"]);
const TYPES = new Set(["int", "float", "bool", "string", "void"]);
const STAGES = [
  { id: "lexer", name: "Lexer", sub: "Source → tokens" },
  { id: "parser", name: "Parser", sub: "Tokens → syntax tree" },
  { id: "semantic", name: "Semantic analyzer", sub: "Types & symbols" },
  { id: "interpreter", name: "Interpreter", sub: "Execute program" },
];
const STATUS_LABEL = {
  pending: "Not run", passed: "Passed", failed: "Failed",
  skipped: "Skipped", not_implemented: "Not implemented",
};
const TOKEN_CLASS = { KEYWORD: "kw", BOOL: "kw", TYPE: "ty", IDENT: "id", INT: "num", FLOAT: "num", STRING: "str" };
const DFA_NAME = { IDENT: "identifier", INT: "integer", FLOAT: "float", STRING: "string", KEYWORD: "keyword", BOOL: "boolean", TYPE: "type word" };
const EXAMPLE = `// Your first FormaLang program
string greet(string name) {
    return "Hello, " + name + "!";
}

string language = "FormaLang";
float version = 1.0;

print(greet(language));
print("Ready to build something great.");

// Try a loop
for (int i = 1; i <= 3; i++) {
    print("Step " + i);
}
`;

const $ = (sel) => document.querySelector(sel);
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const prefs = JSON.parse(localStorage.getItem(PREF_KEY) || "{}");

let lastRun = null;      // last /api/run response, used by the stage detail views
let selectedStage = 0;   // index into STAGES

/* =========================================================
   EDITOR (CodeMirror 6)
   ========================================================= */
const formaLang = StreamLanguage.define({
  token(stream) {
    if (stream.eatSpace()) return null;
    if (stream.match("//")) { stream.skipToEnd(); return "comment"; }
    if (stream.match(/"(?:[^"\\]|\\.)*"?/)) return "string";
    if (stream.match(/\d+(\.\d+)?/)) return "number";
    if (stream.match(/[A-Za-z_]\w*/)) {
      const word = stream.current();
      if (KEYWORDS.has(word)) return "keyword";
      if (TYPES.has(word)) return "typeName";
      return "variableName";
    }
    stream.next();
    return null;
  },
});

const formaHighlight = HighlightStyle.define([
  { tag: t.keyword, color: "#c4b5fd" },
  { tag: t.typeName, color: "#7dd3fc" },
  { tag: t.string, color: "#86efac" },
  { tag: t.number, color: "#fdba74" },
  { tag: t.comment, color: "#55556a", fontStyle: "italic" },
  { tag: t.variableName, color: "#e7e7f0" },
]);

const formaTheme = EditorView.theme({
  "&": { height: "100%", color: "#e7e7f0", backgroundColor: "transparent", fontSize: "13px" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.7" },
  ".cm-content": { caretColor: "#a78bfa", padding: "8px 0" },
  ".cm-gutters": { backgroundColor: "transparent", color: "#4f4f62", border: "none" },
  ".cm-activeLine": { backgroundColor: "rgba(167,139,250,.06)" },
  ".cm-activeLineGutter": { backgroundColor: "transparent", color: "#a1a1b5" },
  "&.cm-focused .cm-cursor": { borderLeftColor: "#a78bfa" },
  ".cm-selectionBackground, &.cm-focused .cm-selectionBackground": { backgroundColor: "rgba(124,92,246,.3) !important" },
  ".cm-matchingBracket": { color: "#fff", backgroundColor: "rgba(167,139,250,.25)" },
}, { dark: true });

let saveTimer = null;
const view = new EditorView({
  doc: localStorage.getItem(STORAGE_KEY) ?? "",
  parent: $("#editor"),
  extensions: [
    basicSetup,
    formaLang,
    syntaxHighlighting(formaHighlight),
    formaTheme,
    EditorView.updateListener.of((u) => {
      if (u.docChanged) {
        setSaveStatus("unsaved");
        clearTimeout(saveTimer);
        saveTimer = setTimeout(saveDraft, 400);
        refreshEmptyState();
      }
      if (u.docChanged || u.selectionSet) updateCursor();
    }),
  ],
});

function saveDraft() {
  localStorage.setItem(STORAGE_KEY, view.state.doc.toString());
  setSaveStatus("saved");
}

function setSaveStatus(state) {
  const el = $("#saveStatus");
  el.textContent = state === "saved" ? "● All changes saved" : "● Unsaved changes";
  el.style.color = state === "saved" ? "var(--ok)" : "var(--warn)";
}

function refreshEmptyState() {
  $("#emptyState").classList.toggle("hidden", view.state.doc.length > 0);
}

function updateCursor() {
  const pos = view.state.selection.main.head;
  const line = view.state.doc.lineAt(pos);
  $("#cursorPos").textContent = `Ln ${line.number}, Col ${pos - line.from + 1}`;
}

function jumpTo(line, col) {
  const doc = view.state.doc;
  const ln = doc.line(Math.min(Math.max(line, 1), doc.lines));
  const pos = Math.min(ln.from + Math.max(col - 1, 0), ln.to);
  view.dispatch({ selection: { anchor: pos }, scrollIntoView: true });
  view.focus();
}

/* =========================================================
   CONSOLE, PROBLEMS
   ========================================================= */
function log(kind, text) {
  $("#consoleEmpty").classList.add("hidden");
  const div = document.createElement("div");
  div.className = `console-line ${kind}`;
  div.textContent = text;
  $("#consoleOutput").appendChild(div);
}

function clearConsole() {
  $("#consoleOutput").innerHTML = "";
  $("#consoleEmpty").classList.remove("hidden");
}

function renderProblems(list) {
  $("#problemCount").textContent = list.length;
  const pane = $("#problemsView");
  pane.innerHTML = "";
  if (!list.length) {
    pane.innerHTML = '<div class="muted">No problems</div>';
    return;
  }
  for (const d of list) {
    const row = document.createElement("div");
    row.className = "problem";
    row.title = "Click to jump to this location";
    row.innerHTML = `<span class="err">${d.code}</span> ${escapeHtml(d.message)} <span class="muted">· line ${d.line}:${d.col}</span>`;
    row.addEventListener("click", () => jumpTo(d.line, d.col));
    pane.appendChild(row);
  }
}

/* =========================================================
   STAGE CARDS AND DETAIL VIEWS
   ========================================================= */
function renderStages(results = []) {
  const wrap = $("#stages");
  wrap.innerHTML = "";
  STAGES.forEach((s, i) => {
    const r = results[i] ?? { status: "pending" };
    const card = document.createElement("button");
    card.type = "button";
    card.className = `stage ${r.status}${i === selectedStage ? " active" : ""}`;
    card.innerHTML = `
      <div class="stage-top"><span class="stage-num">0${i + 1}</span><span>${s.name}</span></div>
      <div class="stage-sub">${s.sub}</div>
      <div class="stage-status">${STATUS_LABEL[r.status] ?? r.status}${r.detail ? ` · ${escapeHtml(r.detail)}` : ""}</div>`;
    card.addEventListener("click", () => showStage(i));
    wrap.appendChild(card);
  });
}

function showStage(index) {
  selectedStage = index;
  document.querySelectorAll(".stage").forEach((c, i) => c.classList.toggle("active", i === index));
  const box = $("#stageDetail");
  box.classList.remove("rich");
  if (!lastRun) {
    box.textContent = "Run your program to inspect this stage.";
    return;
  }
  if (index === 0) return renderLexerDetail(lastRun);
  box.textContent = `${STAGES[index].name} inspection arrives in a later phase.`;
}

function renderLexerDetail(data) {
  const box = $("#stageDetail");
  box.classList.add("rich");
  const toks = (data.tokens || []).filter((tk) => tk.kind !== "EOF");
  const failed = data.stages[0].status === "failed";

  box.innerHTML = `
    ${failed ? `<div class="lex-note err">Lexer found ${data.diagnostics.length} error(s). The tokens below are partial. See Problems.</div>` : ""}
    <div class="lex-grid">
      <div class="lex-card">
        <div class="lex-label">Tokens stream <span class="muted">· ${toks.length} tokens</span></div>
        <div class="stream" id="tokenStream"></div>
        <div class="lex-info" id="tokenInfo"></div>
      </div>
      <div class="lex-card">
        <div class="lex-label" id="dfaLabel">DFA</div>
        <svg id="dfaSvg" class="dfa" viewBox="0 0 360 150" preserveAspectRatio="xMinYMid meet"></svg>
        <div class="muted lex-caption" id="dfaCaption"></div>
      </div>
    </div>`;

  const stream = $("#tokenStream");
  if (!toks.length) {
    stream.innerHTML = '<span class="muted">No tokens in this program.</span>';
    return;
  }
  toks.forEach((tk, i) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `tok ${TOKEN_CLASS[tk.kind] ?? "op"}`;
    b.textContent = tk.lexeme;
    b.title = `${tk.kind} · line ${tk.line}, col ${tk.col}`;
    b.addEventListener("click", () => selectToken(toks, i));
    stream.appendChild(b);
  });
  selectToken(toks, 0);
}

function selectToken(toks, i) {
  document.querySelectorAll(".tok").forEach((c, k) => c.classList.toggle("active", k === i));
  const tk = toks[i];
  const shown = ["INT", "BOOL", "STRING"].includes(tk.kind)
    ? ` <span class="muted">· value</span> <code>${escapeHtml(JSON.stringify(tk.value))}</code>`
    : "";
  $("#tokenInfo").innerHTML =
    `<b>${escapeHtml(tk.kind)}</b> <code>${escapeHtml(tk.lexeme)}</code> at line ${tk.line}, column ${tk.col}${shown}`;
  renderDfa(tk);
}

function renderDfa(tok) {
  const svg = $("#dfaSvg");
  $("#dfaLabel").textContent = `DFA · ${DFA_NAME[tok.kind] ?? tok.kind.toLowerCase()}`;
  if (!tok.path || tok.path.length < 2) {
    svg.innerHTML = "";
    $("#dfaCaption").textContent = "This token has no automaton path to show.";
    return;
  }

  // distinct states in order of first appearance: q0, q1, ...
  const ids = [];
  const pos = {};
  for (const s of tok.path) {
    if (!(s in pos)) { pos[s] = ids.length; ids.push(s); }
  }

  // merge transitions between the same pair of states; collect their labels
  const edges = new Map();
  for (let k = 1; k < tok.path.length; k++) {
    const a = tok.path[k - 1], b = tok.path[k];
    const key = `${a}>${b}`;
    if (!edges.has(key)) edges.set(key, { a, b, labels: [] });
    const labels = edges.get(key).labels;
    const lab = tok.edges[k - 1];
    if (!labels.includes(lab)) labels.push(lab);
  }

  const R = 18, Y = 70, STEP = 120;
  const W = Math.max(360, ids.length * STEP + 60);
  const cx = (s) => 60 + pos[s] * STEP;
  const final = tok.path[tok.path.length - 1];

  let g = `<defs><marker id="dfaArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8b8b9c"/></marker></defs>`;
  g += `<line x1="8" y1="${Y}" x2="${cx(tok.path[0]) - R}" y2="${Y}" stroke="#8b8b9c" stroke-width="1.5" marker-end="url(#dfaArrow)"/>`;
  g += `<text x="8" y="${Y - 12}" class="dfa-lbl">start</text>`;

  for (const { a, b, labels } of edges.values()) {
    const text = labels.slice(0, 3).join(", ") + (labels.length > 3 ? "…" : "");
    const x1 = cx(a), x2 = cx(b);
    if (a === b) {
      // self-loop drawn above the node
      g += `<path d="M ${x1 - 8} ${Y - R + 2} C ${x1 - 30} ${Y - R - 46}, ${x1 + 30} ${Y - R - 46}, ${x1 + 8} ${Y - R + 2}" fill="none" stroke="#a78bfa" stroke-width="1.5" marker-end="url(#dfaArrow)"/>`;
      g += `<text x="${x1}" y="${Y - R - 40}" text-anchor="middle" class="dfa-lbl">${escapeHtml(text)}</text>`;
      continue;
    }
    // forward transitions arc above, backward transitions arc below
    const fwd = x2 > x1;
    const sx = x1 + (fwd ? R : -R), ex = x2 + (fwd ? -R : R);
    const ctrlY = fwd ? Y - 44 : Y + 44;
    const mx = (sx + ex) / 2;
    const labelY = fwd ? Y - 30 : Y + 40;
    g += `<path d="M ${sx} ${Y} Q ${mx} ${ctrlY} ${ex} ${Y}" fill="none" stroke="#a78bfa" stroke-width="1.5" marker-end="url(#dfaArrow)"/>`;
    g += `<text x="${mx}" y="${labelY}" text-anchor="middle" class="dfa-lbl">${escapeHtml(text)}</text>`;
  }

  ids.forEach((s, i) => {
    const x = cx(s);
    const isFinal = s === final;
    g += `<circle cx="${x}" cy="${Y}" r="${R}" fill="#16161f" stroke="${isFinal ? "#a78bfa" : "#33333f"}" stroke-width="2"/>`;
    if (isFinal) g += `<circle cx="${x}" cy="${Y}" r="${R - 5}" fill="none" stroke="#a78bfa" stroke-width="1.5"/>`;
    g += `<text x="${x}" y="${Y + 4}" text-anchor="middle" class="dfa-node">q${i}</text>`;
  });
  g += `<text x="${cx(final)}" y="${Y + R + 22}" text-anchor="middle" class="dfa-ok">accept ${escapeHtml(tok.kind)}</text>`;

  svg.setAttribute("viewBox", `0 0 ${W} 150`);
  svg.innerHTML = g;
  $("#dfaCaption").textContent =
    `Read ${tok.lexeme.length} character(s) through ${tok.edges.length} transition(s) and accepted ${tok.kind}.`;
}

function setHowOpen(open) {
  $("#howBody").classList.toggle("hidden", !open);
  $("#howCaret").textContent = open ? "▾" : "▸";
}

function setRunStatus(text, color) {
  const el = $("#runStatus");
  el.textContent = text;
  el.style.color = color;
}

/* =========================================================
   RUN
   ========================================================= */
async function run() {
  const source = view.state.doc.toString();
  clearConsole();
  if (!source.trim()) {
    log("muted", "Nothing to run yet. Write some code or load an example.");
    return;
  }
  setRunStatus("● Running…", "var(--muted)");
  try {
    const res = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    lastRun = data;
    data.output.forEach((line) => log("", line));
    renderProblems(data.diagnostics);
    renderStages(data.stages);
    showStage(selectedStage);
    const passed = data.stages.filter((s) => s.status === "passed").length;
    $("#howSummary").textContent = `${passed} of ${data.stages.length} stages passed`;
    setRunStatus(data.ok ? "● Completed" : "● Stopped", data.ok ? "var(--ok)" : "var(--err)");
  } catch (err) {
    log("error", `Could not reach the FormaLang server: ${err.message}`);
    setRunStatus("● Offline", "var(--err)");
  }
}

/* =========================================================
   HEALTH (AI status only; the key itself never reaches the browser)
   ========================================================= */
async function loadHealth() {
  try {
    const h = await (await fetch("/api/health")).json();
    const on = !!h.ai_configured;
    $("#groqStatus").textContent = on ? "Configured" : "Not configured";
    $("#groqStatus").classList.toggle("badge-ok", on);
    $("#aiStatus").textContent = on ? "Enabled" : "Disabled";
    $("#aiStatus").classList.toggle("badge-ok", on);
  } catch {
    /* server offline: keep defaults */
  }
}

/* =========================================================
   EVENTS
   ========================================================= */
function toggleAi(force) {
  const open = force ?? $("#aiPanel").classList.contains("hidden");
  $("#aiPanel").classList.toggle("hidden", !open);
  $("#mainGrid").classList.toggle("ai-open", open);
}

$("#btnRun").addEventListener("click", run);
$("#btnReset").addEventListener("click", () => {
  lastRun = null;
  selectedStage = 0;
  clearConsole();
  renderProblems([]);
  renderStages([]);
  showStage(0);
  $("#howSummary").textContent = "Not run yet";
  setRunStatus("● Ready", "var(--muted)");
});
$("#btnClear").addEventListener("click", clearConsole);
$("#btnLoadExample").addEventListener("click", () => {
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: EXAMPLE } });
  view.focus();
});
$("#btnAi").addEventListener("click", () => toggleAi());
$("#btnCloseAi").addEventListener("click", () => toggleAi(false));
$("#howToggle").addEventListener("click", () => setHowOpen($("#howBody").classList.contains("hidden")));

document.querySelectorAll(".open-settings").forEach((b) =>
  b.addEventListener("click", () => $("#settingsModal").classList.remove("hidden")));
$("#settingsModal").addEventListener("click", (e) => {
  if (e.target.id === "settingsModal" || e.target.closest("[data-close]")) {
    $("#settingsModal").classList.add("hidden");
  }
});
$("#prefShowHow").addEventListener("change", (e) => {
  prefs.alwaysOpenHow = e.target.checked;
  localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
});

document.querySelectorAll(".ptab").forEach((btn) =>
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ptab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".panel-pane").forEach((p) => p.classList.toggle("active", p.id === btn.dataset.panel));
  }));

// Capture phase so CodeMirror's own Mod-Enter never sees these keys.
window.addEventListener("keydown", (e) => {
  if (!(e.metaKey || e.ctrlKey)) return;
  if (e.key === "Enter") { e.preventDefault(); e.stopPropagation(); run(); }
  if (e.key.toLowerCase() === "s") { e.preventDefault(); e.stopPropagation(); saveDraft(); }
}, true);

/* =========================================================
   INIT
   ========================================================= */
function init() {
  lucide.createIcons();
  $("#runKbd").textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘ ↵" : "Ctrl ↵";
  $("#prefShowHow").checked = !!prefs.alwaysOpenHow;
  setHowOpen(!!prefs.alwaysOpenHow);
  renderStages([]);
  showStage(0);
  renderProblems([]);
  refreshEmptyState();
  updateCursor();
  loadHealth();
  view.focus();
}
init();