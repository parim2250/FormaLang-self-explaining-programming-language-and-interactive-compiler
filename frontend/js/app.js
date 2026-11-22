import { EditorView, basicSetup } from "https://esm.sh/codemirror@6";
import { StreamLanguage, syntaxHighlighting, HighlightStyle } from "https://esm.sh/@codemirror/language@6";
import { tags as t } from "https://esm.sh/@lezer/highlight@1";


/* =========================================================
   CONSTANTS
   ========================================================= */
const PROJECT_KEY = "formalang.project.v1";
const COMMITS_KEY = "formalang.commits.v1";
const LEGACY_KEY = "formalang.main.forma";
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
const CHANGE_NAME = { M: "Modified", A: "Added", D: "Deleted" };


const $ = (sel) => document.querySelector(sel);
const escapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const has = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
const prefs = JSON.parse(localStorage.getItem(PREF_KEY) || "{}");


let lastRun = null;      // last /api/run response, used by the stage detail views
let selectedStage = 0;   // index into STAGES


/* =========================================================
   PROJECT FILES
   Saved files live in localStorage. Unsaved edits are "drafts" held in memory
   until saved or reset. The commit baseline is what Source control compares against.
   ========================================================= */
function seedProject() {
  return {
    folders: ["src"],
    saved: {
      "src/main.forma": localStorage.getItem(LEGACY_KEY) ?? "",
      "src/utils.forma": "// Helper functions for this project.\n",
      "formalang.json": '{\n  "name": "untitled-project",\n  "version": "0.1"\n}\n',
      "README.md": "# untitled-project\n\nA FormaLang project.\n",
    },
  };
}


function loadProject() {
  try {
    const data = JSON.parse(localStorage.getItem(PROJECT_KEY) || "null");
    if (data && Array.isArray(data.folders) && data.saved && typeof data.saved === "object") return data;
  } catch {
    /* unreadable data: start fresh below */
  }
  const fresh = seedProject();
  localStorage.setItem(PROJECT_KEY, JSON.stringify(fresh));
  return fresh;
}


function loadBaseline() {
  try {
    const data = JSON.parse(localStorage.getItem(COMMITS_KEY) || "null");
    if (data && data.files && Array.isArray(data.log)) return data;
  } catch {
    /* fall through */
  }
  const fresh = { files: { ...project.saved }, log: [] };
  localStorage.setItem(COMMITS_KEY, JSON.stringify(fresh));
  return fresh;
}


function persist() {
  localStorage.setItem(PROJECT_KEY, JSON.stringify(project));
}


function persistBaseline() {
  localStorage.setItem(COMMITS_KEY, JSON.stringify(baseline));
}


const project = loadProject();
let baseline = loadBaseline();
const drafts = new Map();            // path -> unsaved text (only kept when it differs from saved)
const expanded = new Set(["src"]);   // folders expanded in the explorer
let openTabs = [];                   // open file paths, in tab order
let active = null;                   // path of the file in the editor, or null
let sideView = "explorer";
let loadingDoc = false;              // true while the app itself replaces the editor text


const fileNames = () => Object.keys(project.saved).sort();
const contentOf = (p) => (drafts.has(p) ? drafts.get(p) : project.saved[p]);
const isDirty = (p) => drafts.has(p);
const baseName = (p) => p.slice(p.lastIndexOf("/") + 1);
const parentOf = (p) => (p.includes("/") ? p.slice(0, p.lastIndexOf("/")) : "");
const exists = (p) => has(project.saved, p) || project.folders.includes(p);
const remap = (p, from, to) => (p === from ? to : p.startsWith(from + "/") ? to + p.slice(from.length) : p);
const iconFor = (name) =>
  name.endsWith(".forma") ? "file-code" : name.endsWith(".json") ? "braces" : name.endsWith(".md") ? "file-text" : "file";


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


const view = new EditorView({
  doc: "",
  parent: $("#editor"),
  extensions: [
    basicSetup,
    formaLang,
    syntaxHighlighting(formaHighlight),
    formaTheme,
    EditorView.updateListener.of((u) => {
      if (u.docChanged && !loadingDoc && active) {
        const text = u.state.doc.toString();
        const before = isDirty(active);
        if (text === project.saved[active]) drafts.delete(active);
        else drafts.set(active, text);
        if (before !== isDirty(active)) {
          renderTabs();
          renderTree();
        }
        setSaveStatus();
        refreshEmptyState();
        if (sideView === "scm") renderSourceControl();
      }
      if (u.docChanged || u.selectionSet) updateCursor();
    }),
  ],
});


/* Put a file's content into the editor. Nothing is marked as an edit. */
function setActive(p) {
  active = p && has(project.saved, p) ? p : null;
  loadingDoc = true;
  try {
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: active ? contentOf(active) : "" },
      selection: { anchor: 0 },
    });
  } finally {
    loadingDoc = false;
  }
  refreshUI();
}


function refreshUI() {
  renderTabs();
  renderTree();
  renderBreadcrumb();
  setSaveStatus();
  refreshEmptyState();
  updateCursor();
  if (sideView === "scm") renderSourceControl();
  requestAnimationFrame(() => view.requestMeasure());
}


function renderBreadcrumb() {
  $("#breadcrumb").textContent = active
    ? ["untitled-project", ...active.split("/")].join(" / ")
    : "No file open";
}


function setSaveStatus() {
  const el = $("#saveStatus");
  if (!active) {
    el.textContent = "● No file open";
    el.style.color = "var(--muted)";
    return;
  }
  const dirty = isDirty(active);
  el.textContent = dirty ? "● Unsaved changes" : "● All changes saved";
  el.style.color = dirty ? "var(--warn)" : "var(--ok)";
}


function refreshEmptyState() {
  const noFile = !active;
  $("#editorWrap").classList.toggle("no-file", noFile);
  $("#emptyState").classList.toggle("hidden", !noFile && view.state.doc.length > 0);
  $("#emptyDoc").classList.toggle("hidden", noFile);
  $("#emptyNoFile").classList.toggle("hidden", !noFile);
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
   TABS AND EXPLORER
   ========================================================= */
function renderTabs() {
  const bar = $("#tabs");
  bar.innerHTML = "";
  for (const p of openTabs) {
    const tab = document.createElement("div");
    tab.className = `tab${p === active ? " active" : ""}`;
    tab.title = p;
    tab.innerHTML = `<i data-lucide="${iconFor(baseName(p))}"></i><span>${escapeHtml(baseName(p))}</span>${
      isDirty(p) ? '<span class="dirty-dot" title="Unsaved changes"></span>' : ""
    }<button class="icon-btn sm tab-close" type="button" title="Close tab"><i data-lucide="x"></i></button>`;
    tab.addEventListener("click", (event) => {
      if (event.target.closest(".tab-close")) closeTab(p);
      else if (p !== active) openFile(p);
    });
    bar.appendChild(tab);
  }
  lucide.createIcons();
}


function renderTree() {
  const tree = $("#tree");
  tree.innerHTML = '<div class="tree-root"><i data-lucide="chevron-down"></i> UNTITLED-PROJECT</div>';
  appendChildren(tree, "", 0);
  lucide.createIcons();
}


function appendChildren(container, dir, depth) {
  const prefix = dir ? `${dir}/` : "";
  const dirs = project.folders
    .filter((f) => f.startsWith(prefix) && !f.slice(prefix.length).includes("/"))
    .sort();
  const files = fileNames().filter((p) => p.startsWith(prefix) && !p.slice(prefix.length).includes("/"));

  for (const d of dirs) {
    const open = expanded.has(d);
    container.appendChild(treeRow({ path: d, label: baseName(d), isFolder: true, depth, open }));
    if (open) appendChildren(container, d, depth + 1);
  }
  for (const f of files) {
    container.appendChild(treeRow({ path: f, label: baseName(f), isFolder: false, depth, open: false }));
  }
}


function treeRow({ path, label, isFolder, depth, open }) {
  const row = document.createElement("div");
  row.className = `tree-row${!isFolder && path === active ? " active" : ""}`;
  row.style.paddingLeft = `${6 + depth * 14}px`;
  row.title = path;
  const chevron = isFolder
    ? `<i data-lucide="${open ? "chevron-down" : "chevron-right"}"></i>`
    : '<span class="chev-gap"></span>';
  const icon = isFolder ? (open ? "folder-open" : "folder") : iconFor(label);
  row.innerHTML = `${chevron}<i data-lucide="${icon}"></i><span class="tree-name">${escapeHtml(label)}</span>${
    !isFolder && isDirty(path) ? '<span class="dirty-dot" title="Unsaved changes"></span>' : ""
  }`;
  row.addEventListener("click", () => (isFolder ? toggleFolder(path) : openFile(path)));
  row.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    openMenu(event.clientX, event.clientY, isFolder ? folderItems(path) : fileItems(path));
  });
  return row;
}


function toggleFolder(p) {
  if (expanded.has(p)) expanded.delete(p);
  else expanded.add(p);
  renderTree();
}


function showSideView(name) {
  sideView = name;
  document.querySelectorAll(".act[data-view]").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $("#explorerView").classList.toggle("hidden", name !== "explorer");
  $("#searchView").classList.toggle("hidden", name !== "search");
  $("#scView").classList.toggle("hidden", name !== "scm");
  if (name === "search") $("#searchInput").focus();
  if (name === "scm") renderSourceControl();
}


/* =========================================================
   FILE OPERATIONS
   ========================================================= */
function openFile(p) {
  if (!has(project.saved, p)) return;
  if (!openTabs.includes(p)) openTabs.push(p);
  if (p !== active) setActive(p);
  else refreshUI();
}


/* Closing a tab keeps its unsaved draft, so no work is lost. */
function closeTab(p) {
  const i = openTabs.indexOf(p);
  if (i < 0) return;
  openTabs.splice(i, 1);
  if (active === p) setActive(openTabs[Math.min(i, openTabs.length - 1)] ?? null);
  else refreshUI();
}


function saveFile(p = active) {
  if (!p || !isDirty(p)) return;
  project.saved[p] = drafts.get(p);
  drafts.delete(p);
  persist();
  refreshUI();
}


function resetActive() {
  if (active && isDirty(active)) {
    if (!confirm(`Discard unsaved changes in ${baseName(active)}?`)) return;
    drafts.delete(active);
  }
  clearRunState();
  setActive(active);
}


function askName(message, value = "") {
  const answer = prompt(message, value);
  if (answer === null) return null;
  const name = answer.trim();
  if (!name || name === "." || name === ".." || /[\\/]/.test(name)) {
    alert("Names cannot be empty or contain / or \\.");
    return null;
  }
  return name;
}


function newFile(dir = "") {
  const name = askName("New file name (for example: math.forma)");
  if (!name) return;
  const file = name.includes(".") ? name : `${name}.forma`;
  const path = dir ? `${dir}/${file}` : file;
  if (exists(path)) {
    alert(`${path} already exists.`);
    return;
  }
  project.saved[path] = "";
  if (dir) expanded.add(dir);
  persist();
  openFile(path);
}


function newFolder(dir = "") {
  const name = askName("New folder name");
  if (!name) return;
  const path = dir ? `${dir}/${name}` : name;
  if (exists(path)) {
    alert(`${path} already exists.`);
    return;
  }
  project.folders.push(path);
  if (dir) expanded.add(dir);
  expanded.add(path);
  persist();
  refreshUI();
}


function renameEntry(path, isFolder) {
  const current = baseName(path);
  const answer = askName(`Rename ${current} to:`, current);
  if (!answer) return;
  let name = answer;
  if (!isFolder && !name.includes(".")) name += ".forma";
  if (name === current) return;
  const dir = parentOf(path);
  const to = dir ? `${dir}/${name}` : name;
  if (exists(to)) {
    alert(`${to} already exists.`);
    return;
  }
  renamePath(path, to);
  persist();
  setActive(active);
}


function renamePath(from, to) {
  const moved = (p) => remap(p, from, to);

  const saved = {};
  for (const p of Object.keys(project.saved)) saved[moved(p)] = project.saved[p];
  project.saved = saved;

  const entries = [...drafts];
  drafts.clear();
  for (const [p, text] of entries) drafts.set(moved(p), text);

  project.folders = project.folders.map(moved);

  const open = [...expanded];
  expanded.clear();
  for (const f of open) expanded.add(moved(f));

  openTabs = openTabs.map(moved);
  if (active) active = moved(active);
}


function deleteEntry(path, isFolder) {
  const prefix = `${path}/`;
  const affected = isFolder ? fileNames().filter((p) => p.startsWith(prefix)) : [path];
  const unsaved = affected.some(isDirty);
  const what = isFolder ? `${path} and its ${affected.length} file(s)` : path;
  let message = `Delete ${what}? This cannot be undone.`;
  if (unsaved) message += "\n\nSome of these files have unsaved changes that will be lost.";
  if (!confirm(message)) return;

  dropFiles((p) => (isFolder ? p.startsWith(prefix) : p === path));
  if (isFolder) {
    project.folders = project.folders.filter((f) => f !== path && !f.startsWith(prefix));
    for (const f of [...expanded]) {
      if (f === path || f.startsWith(prefix)) expanded.delete(f);
    }
  }
  persist();
  setActive(active);
}


/* Removes files that match, with their drafts and tabs. Does not touch the editor. */
function dropFiles(match) {
  for (const p of Object.keys(project.saved)) {
    if (match(p)) {
      delete project.saved[p];
      drafts.delete(p);
    }
  }
  openTabs = openTabs.filter((p) => has(project.saved, p));
  if (!active || !has(project.saved, active)) {
    active = openTabs[openTabs.length - 1] ?? null;
  }
}


function ensureFolders(dir) {
  if (!dir) return;
  let acc = "";
  for (const part of dir.split("/")) {
    acc = acc ? `${acc}/${part}` : part;
    if (!project.folders.includes(acc)) project.folders.push(acc);
  }
}


/* =========================================================
   CONTEXT MENU
   ========================================================= */
function openMenu(x, y, items) {
  closeMenu();
  const menu = document.createElement("div");
  menu.id = "ctxMenu";
  menu.className = "ctx-menu";
  for (const item of items) {
    if (item === "-") {
      const sep = document.createElement("div");
      sep.className = "ctx-sep";
      menu.appendChild(sep);
      continue;
    }
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ctx-item";
    button.textContent = item.label;
    button.addEventListener("click", () => {
      closeMenu();
      item.run();
    });
    menu.appendChild(button);
  }
  document.body.appendChild(menu);
  const rect = menu.getBoundingClientRect();
  menu.style.left = `${Math.max(6, Math.min(x, window.innerWidth - rect.width - 6))}px`;
  menu.style.top = `${Math.max(6, Math.min(y, window.innerHeight - rect.height - 6))}px`;
}


function closeMenu() {
  document.getElementById("ctxMenu")?.remove();
}


function rootItems(dir) {
  return [
    { label: "New file", run: () => newFile(dir) },
    { label: "New folder", run: () => newFolder(dir) },
  ];
}


function folderItems(p) {
  return [
    ...rootItems(p),
    "-",
    { label: "Rename", run: () => renameEntry(p, true) },
    { label: "Delete", run: () => deleteEntry(p, true) },
  ];
}


function fileItems(p) {
  return [
    { label: "Open", run: () => openFile(p) },
    "-",
    { label: "Rename", run: () => renameEntry(p, false) },
    { label: "Delete", run: () => deleteEntry(p, false) },
  ];
}


/* =========================================================
   SEARCH
   ========================================================= */
function runSearch(query) {
  const list = $("#searchResults");
  list.innerHTML = "";
  const q = query.trim().toLowerCase();
  if (!q) {
    $("#searchMeta").textContent = "Type to search all files.";
    return;
  }
  const hits = [];
  for (const p of fileNames()) {
    contentOf(p).split("\n").forEach((text, i) => {
      const col = text.toLowerCase().indexOf(q);
      if (col >= 0 && hits.length < 300) hits.push({ p, line: i + 1, col: col + 1, text });
    });
  }
  const fileCount = new Set(hits.map((h) => h.p)).size;
  $("#searchMeta").textContent = hits.length
    ? `${hits.length} result(s) in ${fileCount} file(s)${hits.length === 300 ? " (first 300 shown)" : ""}`
    : "No results";

  for (const h of hits) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "hit";
    row.innerHTML = `<div class="hit-loc">${escapeHtml(h.p)}:${h.line}:${h.col}</div><div class="hit-text">${escapeHtml(h.text.trim())}</div>`;
    row.addEventListener("click", () => {
      openFile(h.p);
      jumpTo(h.line, h.col);
    });
    list.appendChild(row);
  }
}


/* =========================================================
   SOURCE CONTROL (local, compares against the last commit)
   ========================================================= */
function changes() {
  const out = [];
  const all = [...new Set([...Object.keys(baseline.files), ...fileNames()])].sort();
  for (const p of all) {
    const before = has(baseline.files, p);
    const now = has(project.saved, p);
    if (!before && now) out.push({ p, code: "A" });
    else if (before && !now) out.push({ p, code: "D" });
    else if (before && now && contentOf(p) !== baseline.files[p]) out.push({ p, code: "M" });
  }
  return out;
}


function smallButton(label, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = "btn btn-ghost sm";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}


function renderSourceControl() {
  const list = changes();
  $("#scMeta").textContent = list.length
    ? `${list.length} change(s) since the last commit`
    : "No changes since the last commit";

  const box = $("#scChanges");
  box.innerHTML = "";
  for (const change of list) {
    const row = document.createElement("div");
    row.className = "sc-row";
    row.innerHTML = `<span class="sc-code ${change.code}" title="${CHANGE_NAME[change.code]}">${change.code}</span><span class="sc-path" title="${escapeHtml(change.p)}">${escapeHtml(change.p)}</span>`;
    const actions = document.createElement("span");
    actions.className = "sc-actions";
    if (change.code !== "D") actions.appendChild(smallButton("Open", () => openFile(change.p)));
    actions.appendChild(smallButton("Revert", () => revert(change)));
    row.appendChild(actions);
    box.appendChild(row);
  }

  const logBox = $("#scLog");
  logBox.innerHTML = "";
  if (!baseline.log.length) {
    logBox.innerHTML = '<div class="side-empty">No commits yet.</div>';
  }
  for (const entry of baseline.log.slice(0, 20)) {
    const row = document.createElement("div");
    row.className = "commit-row";
    row.innerHTML = `<div>${escapeHtml(entry.message)}</div><div class="muted small">${escapeHtml(entry.time)}</div>`;
    logBox.appendChild(row);
  }
}


function revert(change) {
  const { p, code } = change;
  if (code === "M") {
    project.saved[p] = baseline.files[p];
    drafts.delete(p);
  } else if (code === "D") {
    ensureFolders(parentOf(p));
    project.saved[p] = baseline.files[p];
  } else {
    if (!confirm(`Delete ${p}? It is not in the last commit.`)) return;
    dropFiles((name) => name === p);
  }
  persist();
  setActive(active);
}


function commit() {
  const input = $("#commitMsg");
  for (const [p, text] of drafts) project.saved[p] = text;   // commit saves open edits first
  drafts.clear();

  const list = changes();
  if (!list.length) {
    persist();
    setActive(active);
    alert("Nothing to commit. Make a change first.");
    return;
  }
  const message = input.value.trim() || `Update ${list.length} file(s)`;
  baseline = {
    files: { ...project.saved },
    log: [{ message, time: new Date().toLocaleString() }, ...baseline.log],
  };
  persistBaseline();
  persist();
  input.value = "";
  setActive(active);
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


function clearRunState() {
  lastRun = null;
  selectedStage = 0;
  clearConsole();
  renderProblems([]);
  renderStages([]);
  showStage(0);
  $("#howSummary").textContent = "Not run yet";
  setRunStatus("● Ready", "var(--muted)");
}


/* =========================================================
   RUN
   ========================================================= */
async function run() {
  clearConsole();
  if (!active) {
    log("muted", "No file is open. Create or open a .forma file first.");
    return;
  }
  if (!active.endsWith(".forma")) {
    log("muted", `${baseName(active)} is not a FormaLang program, so it cannot run. Open a .forma file.`);
    return;
  }
  saveFile(active);
  const source = project.saved[active];
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
   MODALS AND PANELS
   ========================================================= */
function toggleAi(force) {
  const open = force ?? $("#aiPanel").classList.contains("hidden");
  $("#aiPanel").classList.toggle("hidden", !open);
  $("#mainGrid").classList.toggle("ai-open", open);
}


function openModal(selector) {
  $(selector).classList.remove("hidden");
}


function closeAllModals() {
  document.querySelectorAll(".modal-backdrop").forEach((m) => m.classList.add("hidden"));
}


/* =========================================================
   EVENTS
   ========================================================= */
$("#btnRun").addEventListener("click", run);
$("#btnReset").addEventListener("click", resetActive);
$("#btnSave").addEventListener("click", () => saveFile(active));
$("#btnClear").addEventListener("click", clearConsole);
$("#btnLoadExample").addEventListener("click", () => $("#btnExamples")?.click());
$("#btnDocs").addEventListener("click", () => openModal("#guideModal"));
$("#openGuideLink").addEventListener("click", () => openModal("#guideModal"));
$("#btnGuide").addEventListener("click", () => openModal("#guideModal"));
$("#btnNewFile").addEventListener("click", () => newFile(""));
$("#btnAi").addEventListener("click", () => toggleAi());
$("#btnCloseAi").addEventListener("click", () => toggleAi(false));
$("#howToggle").addEventListener("click", () => setHowOpen($("#howBody").classList.contains("hidden")));

$("#btnExplorerMenu").addEventListener("click", (event) => {
  const r = event.currentTarget.getBoundingClientRect();
  openMenu(r.left, r.bottom + 4, rootItems(""));
});
$("#tree").addEventListener("contextmenu", (event) => {
  if (event.target.closest(".tree-row")) return;
  event.preventDefault();
  openMenu(event.clientX, event.clientY, rootItems(""));
});

document.querySelectorAll(".act[data-view]").forEach((b) =>
  b.addEventListener("click", () => showSideView(b.dataset.view)));
$("#searchInput").addEventListener("input", (e) => runSearch(e.target.value));
$("#btnCommit").addEventListener("click", commit);
$("#commitMsg").addEventListener("keydown", (e) => {
  if (e.key === "Enter") commit();
});

document.querySelectorAll(".open-settings").forEach((b) =>
  b.addEventListener("click", () => openModal("#settingsModal")));
document.addEventListener("click", (event) => {
  const target = event.target;
  if (target.classList && target.classList.contains("modal-backdrop")) {
    target.classList.add("hidden");
    return;
  }
  const closer = target.closest ? target.closest("[data-close]") : null;
  if (closer) closer.closest(".modal-backdrop")?.classList.add("hidden");
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeMenu();
    closeAllModals();
  }
});
document.addEventListener("pointerdown", (e) => {
  if (!e.target.closest || !e.target.closest("#ctxMenu")) closeMenu();
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
  if (e.key.toLowerCase() === "s") { e.preventDefault(); e.stopPropagation(); saveFile(active); }
}, true);


// Warn before leaving the page while unsaved drafts exist.
window.addEventListener("beforeunload", (e) => {
  if (drafts.size) {
    e.preventDefault();
    e.returnValue = "";
  }
});


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
  showSideView("explorer");
  const first = has(project.saved, "src/main.forma") ? "src/main.forma" : fileNames()[0];
  if (first) openFile(first);
  else setActive(null);
  loadHealth();
  view.focus();
}
init();