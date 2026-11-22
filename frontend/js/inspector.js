// Inspector views inside the existing "Show how it works" panel.
// Adds a DFA tab, and replaces the content of the Tokens, Semantic and Execution
// views with expanded versions. Parse tree, Summary, Run and the stage cards keep
// their behaviour. Loads last, after app.js and the other views.

const PLAY_MS = 600;
const VIEW_FOR_CARD = ["tokens", null, "semantic", "execution"];

// ---------- helpers ----------

function op(label, text) { return { label, cat: "cat-op", text }; }
function punct(label, text) { return { label, cat: "cat-punct", text }; }

const KIND_INFO = {
  IDENT: { label: "identifier", cat: "cat-id", text: "A name you chose for a variable or a function." },
  KEYWORD: { label: "keyword", cat: "cat-kw", text: "A reserved word that controls the flow of the program. You cannot use it as a name." },
  BOOL: { label: "boolean", cat: "cat-kw", text: "The value true or false." },
  TYPE: { label: "type", cat: "cat-type", text: "A type name. It tells the compiler what kind of value a variable holds." },
  INT: { label: "integer", cat: "cat-lit", text: "A whole-number literal." },
  FLOAT: { label: "float", cat: "cat-lit", text: "A decimal-number literal." },
  STRING: { label: "string", cat: "cat-str", text: "A piece of text in double quotes." },
  ASSIGN: op("assign", "The = operator. It stores a value in a variable."),
  PLUS: op("add", "The + operator. It adds numbers, or joins text."),
  MINUS: op("subtract", "The - operator. It subtracts numbers, or makes a number negative."),
  STAR: op("multiply", "The * operator."),
  SLASH: op("divide", "The / operator. Dividing two ints gives a whole number."),
  PERCENT: op("remainder", "The % operator. It gives the remainder of a whole-number division."),
  PLUS_ASSIGN: op("add and assign", "The += operator. It adds a value to a variable."),
  MINUS_ASSIGN: op("subtract and assign", "The -= operator."),
  STAR_ASSIGN: op("multiply and assign", "The *= operator."),
  SLASH_ASSIGN: op("divide and assign", "The /= operator."),
  INCR: op("increment", "The ++ operator. It adds one to a variable."),
  DECR: op("decrement", "The -- operator. It subtracts one from a variable."),
  EQ: op("equal to", "The == operator. It checks whether two values are equal."),
  NE: op("not equal", "The != operator. It checks whether two values differ."),
  LT: op("less than", "The < operator."),
  LE: op("less or equal", "The <= operator."),
  GT: op("greater than", "The > operator."),
  GE: op("greater or equal", "The >= operator."),
  AND: op("and", "The && operator. It is true only when both sides are true."),
  OR: op("or", "The || operator. It is true when either side is true."),
  BANG: op("not", "The ! operator. It flips true and false."),
  LPAREN: punct("opening parenthesis", "Opens a group, a condition, or the arguments of a call."),
  RPAREN: punct("closing parenthesis", "Closes a group, a condition, or the arguments of a call."),
  LBRACE: punct("opening brace", "Opens a block of statements."),
  RBRACE: punct("closing brace", "Closes a block of statements."),
  COMMA: punct("comma", "Separates items, such as function arguments."),
  SEMI: punct("semicolon", "Ends a statement."),
};

const LEGEND = [
  ["cat-kw", "keyword or boolean"],
  ["cat-type", "type"],
  ["cat-id", "identifier"],
  ["cat-lit", "number"],
  ["cat-str", "string"],
  ["cat-op", "operator"],
  ["cat-punct", "punctuation"],
];

const WORDS = new Set(["IDENT", "KEYWORD", "TYPE", "BOOL"]);

let lastRun = null;
let current = null;        // "tokens" | "dfa" | "semantic" | "execution" | null
let selectedToken = 0;
let selectedStep = 0;
let playTimer = null;

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function loc(line, col) {
  return line == null ? "" : `${line}:${col}`;
}

function clampIndex(i, n) {
  return n ? Math.min(Math.max(i, 0), n - 1) : 0;
}

function tokens() {
  return (lastRun?.tokens ?? []).filter((t) => t.kind !== "EOF");
}

function trace() {
  return Array.isArray(lastRun?.trace) ? lastRun.trace : [];
}

function stageNamed(name) {
  return (lastRun?.stages ?? []).find((s) => s.name === name);
}

function diagnostics(stage) {
  return (lastRun?.diagnostics ?? []).filter((d) => d.stage === stage);
}

function note(text) {
  return `<div class="ins-note">${esc(text)}</div>`;
}

function stat(label, value) {
  return `<div class="ins-stat"><div class="ins-stat-v">${esc(value)}</div><div class="ins-stat-k">${esc(label)}</div></div>`;
}

function kindInfo(kind) {
  return KIND_INFO[kind] ?? { label: String(kind).toLowerCase(), cat: "cat-op", text: "A token of the language." };
}

function errRow(d) {
  return `<div class="ins-err-row">
    <span class="ins-err">${esc(d.code)}</span>
    <span class="ins-err-msg">${esc(d.message)}</span>
    <span class="ins-muted">${esc(loc(d.line, d.col))}</span>
    ${d.hint ? `<div class="ins-hint">Hint: ${esc(d.hint)}</div>` : ""}
  </div>`;
}

function nameOf(nodes, id) {
  const n = nodes.get(id);
  return n ? (n.label || n.accept || id) : id;
}

function readSteps(steps) {
  if (!steps.length) return note("No steps to show.");
  return `<ol class="ins-steps">${steps.map((s) =>
    `<li><code>${esc(s.fromName)}</code> <span>--${esc(s.label)}--&gt;</span> <code>${esc(s.toName)}</code></li>`
  ).join("")}</ol>`;
}

// ---------- DFA built from the tokens of the run ----------

function dfaFor(toks) {
  const nodes = new Map();
  const edges = new Map();
  const paths = [];

  const addNode = (id, label, accept) => {
    if (!nodes.has(id)) nodes.set(id, { id, label, accept: accept ?? null });
    else if (accept && !nodes.get(id).accept) nodes.get(id).accept = accept;
  };
  addNode("start", "start", null);

  toks.forEach((tok, index) => {
    const lex = String(tok.lexeme ?? "");
    const kind = tok.kind;
    const steps = [];
    const trail = ["start"];
    let here = "start";

    const go = (to, label, toLabel, accept) => {
      const prev = here;
      addNode(to, toLabel, accept);
      const key = `${prev}\u0001${to}\u0001${label}`;
      if (!edges.has(key)) edges.set(key, { from: prev, to, label, tokens: new Set() });
      edges.get(key).tokens.add(index);
      steps.push({ label, fromName: nameOf(nodes, prev), toName: nameOf(nodes, to) });
      trail.push(to);
      here = to;
    };

    if (WORDS.has(kind)) {
      [...lex].forEach((_, i) =>
        go("word", i === 0 ? "letter or _" : "letter, digit or _", "word", null));
      const text = kind === "IDENT" ? "IDENT" : `${kind} ${lex}`;
      go(`acc:${text}`, "anything else", "", text);
    } else if (kind === "INT" || kind === "FLOAT") {
      const [whole, fraction] = lex.split(".");
      [...whole].forEach(() => go("number", "digit", "number", null));
      if (fraction !== undefined) {
        go("dot", ".", ".", null);
        [...fraction].forEach(() => go("fraction", "digit", "fraction", null));
      }
      go(`acc:${kind}`, "anything else", "", kind);
    } else if (kind === "STRING") {
      const inner = lex.length >= 2 && lex.startsWith('"') && lex.endsWith('"') ? lex.slice(1, -1) : lex;
      go("text", '"', "text", null);
      for (let i = 0; i < inner.length; i++) {
        if (inner[i] === "\\") {
          go("escape", "\\", "escape", null);
          i += 1;
          go("text", "escape letter", "text", null);
        } else {
          go("text", "any character", "text", null);
        }
      }
      go("acc:STRING", '"', "", "STRING");
    } else {
      const chars = [...lex];
      chars.forEach((ch, i) => {
        const prefix = chars.slice(0, i + 1).join("");
        const last = i === chars.length - 1;
        go(`op:${prefix}`, ch, prefix, last ? kind : null);
      });
    }

    paths.push({ nodes: trail, steps });
  });

  return { nodes, edges, paths };
}

function layout(g) {
  const adj = new Map();
  for (const e of g.edges.values()) {
    if (e.from === e.to) continue;
    if (!adj.has(e.from)) adj.set(e.from, []);
    adj.get(e.from).push(e.to);
  }

  const depth = new Map([["start", 0]]);
  const queue = ["start"];
  while (queue.length) {
    const id = queue.shift();
    for (const next of adj.get(id) ?? []) {
      if (!depth.has(next)) {
        depth.set(next, depth.get(id) + 1);
        queue.push(next);
      }
    }
  }

  const columns = new Map();
  for (const id of g.nodes.keys()) {
    const d = depth.get(id) ?? 0;
    if (!columns.has(d)) columns.set(d, []);
    columns.get(d).push(id);
  }

  const pos = new Map();
  let rows = 1;
  for (const [d, ids] of columns) {
    rows = Math.max(rows, ids.length);
    ids.forEach((id, row) => pos.set(id, { x: 80 + d * 150, y: 60 + row * 84, depth: d }));
  }
  const deepest = Math.max(...columns.keys());
  return { pos, width: 80 + deepest * 150 + 130, height: 60 + rows * 84 + 30 };
}

function towardPoint(x1, y1, x2, y2, r) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const len = Math.hypot(dx, dy) || 1;
  return { x: x1 + (dx / len) * r, y: y1 + (dy / len) * r };
}

function dfaSvg(g, sel) {
  const { pos, width, height } = layout(g);
  const R = 18;
  const onPath = new Set(g.paths[sel]?.nodes ?? []);
  let edgesSvg = "";
  let nodesSvg = "";

  for (const e of g.edges.values()) {
    const a = pos.get(e.from);
    const b = pos.get(e.to);
    const hi = e.tokens.has(sel);
    const cls = hi ? " hi" : "";
    const marker = `url(#ins-arrow${hi ? "-hi" : ""})`;

    if (e.from === e.to) {
      const y = a.y - R;
      edgesSvg += `<path class="ins-d-edge${cls}" d="M${a.x - 10} ${y} C${a.x - 40} ${y - 56} ${a.x + 40} ${y - 56} ${a.x + 10} ${y}" marker-end="${marker}"/>`;
      edgesSvg += `<text class="ins-d-lbl${cls}" x="${a.x}" y="${y - 62}" text-anchor="middle">${esc(e.label)}</text>`;
      continue;
    }

    const back = b.depth <= a.depth;
    const cx = (a.x + b.x) / 2;
    const cy = (a.y + b.y) / 2 + (back ? 46 : 0);
    const p1 = towardPoint(a.x, a.y, cx, cy, R);
    const p2 = towardPoint(b.x, b.y, cx, cy, R + 5);
    const lx = 0.25 * a.x + 0.5 * cx + 0.25 * b.x;
    const ly = 0.25 * a.y + 0.5 * cy + 0.25 * b.y;
    edgesSvg += `<path class="ins-d-edge${cls}" d="M${p1.x} ${p1.y} Q${cx} ${cy} ${p2.x} ${p2.y}" marker-end="${marker}"/>`;
    edgesSvg += `<text class="ins-d-lbl${cls}" x="${lx}" y="${ly - 6}" text-anchor="middle">${esc(e.label)}</text>`;
  }

  for (const [id, n] of g.nodes) {
    const p = pos.get(id);
    const hi = onPath.has(id) ? " hi" : "";
    if (id === "start") {
      edgesSvg += `<line class="ins-d-edge" x1="${p.x - 56}" y1="${p.y}" x2="${p.x - R - 2}" y2="${p.y}" marker-end="url(#ins-arrow)"/>`;
    }
    nodesSvg += `<circle class="ins-d-node${hi}" cx="${p.x}" cy="${p.y}" r="${R}"/>`;
    if (n.accept) nodesSvg += `<circle class="ins-d-acc${hi}" cx="${p.x}" cy="${p.y}" r="${R + 5}"/>`;
    if (n.label) nodesSvg += `<text class="ins-d-name" x="${p.x}" y="${p.y + 4}" text-anchor="middle">${esc(n.label)}</text>`;
    if (n.accept) nodesSvg += `<text class="ins-d-accept${hi}" x="${p.x}" y="${p.y + R + 20}" text-anchor="middle">${esc(n.accept)}</text>`;
  }

  const defs = `<defs>
    <marker id="ins-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#4f4f62"/></marker>
    <marker id="ins-arrow-hi" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#a78bfa"/></marker>
  </defs>`;

  return `<svg class="ins-d-svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="DFA for this program">${defs}${edgesSvg}${nodesSvg}</svg>`;
}

// ---------- views ----------

function tokensView() {
  if (!lastRun) return note("Run a program first. Its tokens appear here.");
  const toks = tokens();
  const errors = diagnostics("lexer");
  if (!toks.length && !errors.length) return note("No tokens were produced.");

  selectedToken = clampIndex(selectedToken, toks.length);
  const sel = toks[selectedToken];
  const info = sel ? kindInfo(sel.kind) : null;
  const steps = sel ? dfaFor(toks).paths[selectedToken].steps : [];
  const showValue = !!sel && sel.value != null && String(sel.value) !== String(sel.lexeme);

  const chips = toks.map((t, i) => {
    const ti = kindInfo(t.kind);
    return `<button type="button" class="ins-chip ${ti.cat}${i === selectedToken ? " on" : ""}" data-ins-tok="${i}" title="${esc(ti.text)}">
      <span class="ins-chip-lex">${esc(t.lexeme)}</span>
      <span class="ins-chip-kind">${esc(ti.label)}</span>
    </button>`;
  }).join("");

  const legend = LEGEND.map(([cat, label]) =>
    `<span class="ins-legend-item ${cat}"><span class="ins-swatch"></span>${label}</span>`
  ).join("");

  const detailCard = sel ? `
    <div class="ins-card">
      <div class="ins-card-title">Selected token · ${selectedToken + 1} of ${toks.length}</div>
      <div class="ins-big"><code class="${info.cat}">${esc(sel.lexeme)}</code><span class="ins-tag">${esc(info.label)}</span></div>
      <p class="ins-p">${esc(info.text)}</p>
      <div class="ins-kv">
        <span>Kind</span><span>${esc(sel.kind)}</span>
        <span>Position</span><span>${esc(loc(sel.line, sel.col))}</span>
        ${showValue ? `<span>Value</span><span>${esc(sel.value)}</span>` : ""}
      </div>
      <details class="ins-det" data-ins-key="tokens:read"><summary>How the lexer read it</summary>${readSteps(steps)}</details>
    </div>` : "";

  const table = `
    <details class="ins-det" data-ins-key="tokens:table"><summary>All tokens as a table</summary>
      <table class="ins-table">
        <thead><tr><th>#</th><th>LEXEME</th><th>KIND</th><th>VALUE</th><th>LINE:COL</th></tr></thead>
        <tbody>${toks.map((t, i) => `
          <tr class="ins-row${i === selectedToken ? " active" : ""}" data-ins-tok="${i}">
            <td class="ins-num">${i + 1}</td>
            <td><code>${esc(t.lexeme)}</code></td>
            <td>${esc(t.kind)}</td>
            <td>${esc(t.value ?? "")}</td>
            <td>${esc(loc(t.line, t.col))}</td>
          </tr>`).join("")}
        </tbody>
      </table>
    </details>`;

  const errorCard = errors.length
    ? `<div class="ins-card"><div class="ins-card-title">Lexical errors</div>${errors.map(errRow).join("")}</div>`
    : "";

  return `
    <p class="ins-caption">Your code, split into tokens. The lexer reads characters one at a time and groups them into these pieces. Click a token to see how it was read.</p>
    <div class="ins-legend">${legend}</div>
    <div class="ins-card"><div class="ins-chips">${chips}</div></div>
    ${detailCard}
    ${table}
    ${errorCard}`;
}

function dfaView() {
  if (!lastRun) return note("Run a program first. The diagram is drawn from the tokens of that run.");
  const toks = tokens();
  if (!toks.length) return note("There are no tokens to draw. See the lexical errors under Problems.");

  selectedToken = clampIndex(selectedToken, toks.length);
  const g = dfaFor(toks);
  const path = g.paths[selectedToken];
  const sel = toks[selectedToken];
  const info = kindInfo(sel.kind);
  const accepting = [...g.nodes.values()].filter((n) => n.accept);

  const options = toks.map((t, i) =>
    `<option value="${i}"${i === selectedToken ? " selected" : ""}>${i + 1}. ${esc(t.lexeme)} (${esc(t.kind)})</option>`
  ).join("");

  const edgeRows = [...g.edges.values()].map((e) => `
    <tr>
      <td><code>${esc(nameOf(g.nodes, e.from))}</code></td>
      <td><code>${esc(e.label)}</code></td>
      <td><code>${esc(nameOf(g.nodes, e.to))}</code></td>
      <td class="ins-num">${e.tokens.size}</td>
    </tr>`).join("");

  const acceptList = accepting.map((n) => {
    const count = g.paths.filter((p) => p.nodes.at(-1) === n.id).length;
    return `<li><code>${esc(n.accept)}</code> <span class="muted">reached by ${count} token${count === 1 ? "" : "s"}</span></li>`;
  }).join("");

  return `
    <p class="ins-caption">Drawn from your code. Only the states and arrows used by the tokens of this run are shown. Edit and run again to redraw it.</p>
    <div class="ins-card">
      <div class="ins-card-title">Automaton · ${g.edges.size} transitions · ${accepting.length} accepting states</div>
      <div class="ins-dfa">${dfaSvg(g, selectedToken)}</div>
    </div>
    <div class="ins-card">
      <div class="ins-row-inline">
        <span class="ins-card-title">Highlighted token</span>
        <select class="ins-select" data-ins-dfa-select>${options}</select>
      </div>
      <p class="ins-p">"${esc(sel.lexeme)}" is read as ${esc(info.label)}. The lexer took ${path.steps.length} steps and stopped in an accepting state.</p>
      ${readSteps(path.steps)}
    </div>
    <details class="ins-det" data-ins-key="dfa:edges"><summary>Transitions used by this code (${g.edges.size})</summary>
      <table class="ins-table">
        <thead><tr><th>FROM</th><th>ON</th><th>TO</th><th>TOKENS</th></tr></thead>
        <tbody>${edgeRows}</tbody>
      </table>
    </details>
    <details class="ins-det" data-ins-key="dfa:accept"><summary>Accepting states (${accepting.length})</summary>
      <ul class="ins-list">${acceptList}</ul>
    </details>
    <details class="ins-det" data-ins-key="dfa:how"><summary>How to read this diagram</summary>
      <ul class="ins-list">
        <li>Circles are states. The arrow from the left marks the start state.</li>
        <li>A double ring is an accepting state. The name under it is the kind of token that ends there.</li>
        <li>Each arrow is labelled with the characters that move the lexer along it.</li>
        <li>Purple marks the path of the token selected above.</li>
      </ul>
    </details>`;
}

function buildModel(ast) {
  const m = { scopes: [], uses: [], decls: [], funcs: new Map() };

  const makeScope = (label, parent) => {
    const s = { id: m.scopes.length, label, parent, names: new Map(), children: [] };
    m.scopes.push(s);
    if (parent) parent.children.push(s);
    return s;
  };
  const declare = (scope, name, type, node, kind) => {
    const decl = { name, type, kind, scope: scope.label, line: node.line, col: node.col };
    scope.names.set(name, decl);
    m.decls.push(decl);
    return decl;
  };
  const lookup = (scope, name) => {
    for (let s = scope; s; s = s.parent) {
      if (s.names.has(name)) return s.names.get(name);
    }
    return null;
  };
  const useOf = (scope, name, mode, node) => {
    m.uses.push({ name, mode, where: scope.label, line: node.line, col: node.col, decl: lookup(scope, name) });
  };
  const callUse = (scope, node) => {
    const builtin = node.name === "print";
    m.uses.push({
      name: node.name, mode: "call", where: scope.label, line: node.line, col: node.col,
      builtin, decl: builtin ? null : (m.funcs.get(node.name) ?? null),
    });
  };
  const walkAll = (list, scope) => {
    for (const n of list ?? []) walk(n, scope);
  };
  const branch = (node, label, parent) => {
    if (!node) return;
    if (node.type === "Block") {
      walkAll(node.body, makeScope(label, parent));
    } else {
      walk(node, parent);
    }
  };
  const walk = (node, scope) => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) { walkAll(node, scope); return; }
    switch (node.type) {
      case "FuncDecl": {
        const fscope = makeScope(`function ${node.name}`, scope);
        for (const p of node.params ?? []) declare(fscope, p.name, p.var_type, p.line !== undefined ? p : node, "parameter");
        walkAll(node.body?.body, fscope);
        return;
      }
      case "Block":
        walkAll(node.body, makeScope("block", scope));
        return;
      case "If":
        walk(node.cond, scope);
        branch(node.then, "if block", scope);
        branch(node.otherwise, "else block", scope);
        return;
      case "While":
        walk(node.cond, scope);
        branch(node.body, "while block", scope);
        return;
      case "For": {
        const fscope = makeScope("for loop", scope);
        walk(node.init, fscope);
        walk(node.cond, fscope);
        walk(node.step, fscope);
        branch(node.body, "for block", fscope);
        return;
      }
      case "VarDecl":
        walk(node.init, scope);
        declare(scope, node.name, node.var_type, node, "variable");
        return;
      case "Assign": {
        const name = typeof node.target === "string" ? node.target : node.target?.name;
        walk(node.value, scope);
        if (name) useOf(scope, name, node.op === "=" ? "assign" : "update", node);
        return;
      }
      case "Var":
        useOf(scope, node.name, "read", node);
        return;
      case "Call":
        walkAll(node.args, scope);
        callUse(scope, node);
        return;
      default:
        for (const [key, value] of Object.entries(node)) {
          if (key === "type" || key === "line" || key === "col") continue;
          if (value && typeof value === "object") walk(value, scope);
        }
    }
  };

  const global = makeScope("global", null);
  const body = ast?.body ?? [];
  for (const item of body) {
    if (item.type !== "FuncDecl") continue;
    const decl = { name: item.name, type: item.return_type, kind: "function", scope: "global", line: item.line, col: item.col };
    m.funcs.set(item.name, decl);
    m.decls.push(decl);
    global.names.set(item.name, decl);
  }
  walkAll(body, global);
  return m;
}

function resolution(u) {
  if (u.builtin) return "built-in function";
  if (u.decl) {
    return u.decl.kind === "function"
      ? `function returning ${u.decl.type}, declared in ${u.decl.scope}`
      : `${u.decl.kind} of type ${u.decl.type}, declared in ${u.decl.scope}`;
  }
  return u.mode === "call" ? "not defined (E303)" : "not declared (E301)";
}

function scopeTree(s) {
  const names = [...s.names.values()].map((d) =>
    `<li><code>${esc(d.name)}</code> <span class="ins-type">${esc(d.type ?? "")}</span> <span class="muted">${esc(d.kind)} · ${esc(loc(d.line, d.col))}</span></li>`
  ).join("");
  return `<details class="ins-tree" open data-ins-key="sem:scope:${s.id}">
    <summary>${esc(s.label)} <span class="muted">· ${s.names.size} name${s.names.size === 1 ? "" : "s"}</span></summary>
    ${names ? `<ul class="ins-list">${names}</ul>` : `<div class="ins-list muted">No names declared here.</div>`}
    ${s.children.map(scopeTree).join("")}
  </details>`;
}

function semanticView() {
  if (!lastRun) return note("Run a program first, then open the Semantic stage.");
  const stage = stageNamed("Semantic analyzer");
  if (!stage || stage.status === "skipped") {
    return note("The semantic analyzer did not run because an earlier stage stopped the program. See Problems.");
  }

  const symbols = lastRun.symbols ?? [];
  const issues = diagnostics("semantic");
  let model = null;
  try {
    model = lastRun.ast ? buildModel(lastRun.ast) : null;
  } catch {
    model = null;
  }
  const uses = model ? model.uses : [];
  const decls = model ? model.decls : [];

  const symbolRows = symbols.map((s, i) => {
    const decl = decls.find((d) => d.name === s.name && d.scope === s.scope) ?? decls.find((d) => d.name === s.name);
    const count = decl ? uses.filter((u) => u.decl === decl).length : 0;
    return `<details class="ins-sym" data-ins-key="sem:sym:${i}">
      <summary class="ins-sym-row">
        <span class="ins-name">${esc(s.name)}</span>
        <span class="ins-type">${esc(s.declared_type)}</span>
        <span class="ins-type">${esc(s.inferred_type ?? "—")}</span>
        <span class="ins-scope">${esc(s.scope)}</span>
      </summary>
      <div class="ins-sym-body">
        <div>Declared as <b>${esc(s.declared_type)}</b> in <b>${esc(s.scope)}</b>${decl ? ` at ${esc(loc(decl.line, decl.col))}` : ""}.</div>
        <div>Inferred type: <b>${esc(s.inferred_type ?? "not inferred")}</b>.</div>
        <div>${decl ? `Used ${count} time${count === 1 ? "" : "s"} in the program.` : "No matching declaration was found in the syntax tree."}</div>
      </div>
    </details>`;
  }).join("");

  const verbs = { read: "reads", assign: "assigns to", update: "updates", call: "calls" };
  const groups = new Map();
  for (const u of uses) {
    if (!groups.has(u.where)) groups.set(u.where, []);
    groups.get(u.where).push(u);
  }
  let groupIndex = 0;
  const resolutionHtml = [...groups].map(([where, list]) => `
    <details class="ins-det" open data-ins-key="sem:res:${groupIndex++}">
      <summary>In ${esc(where)} · ${list.length} use${list.length === 1 ? "" : "s"}</summary>
      <ul class="ins-list">${list.map((u) =>
        `<li><span class="ins-verb">${esc(verbs[u.mode] ?? u.mode)}</span> <code>${esc(u.name)}</code> <span class="muted">at ${esc(loc(u.line, u.col))}</span> → ${esc(resolution(u))}</li>`
      ).join("")}</ul>
    </details>`).join("");

  const stats = `<div class="ins-stats">
    ${stat("Declarations", decls.length)}
    ${stat("Uses", uses.length)}
    ${stat("Scopes", model ? model.scopes.length : 0)}
    ${stat("Errors", issues.length)}
  </div>`;

  return `
    ${stats}
    <p class="ins-caption">Names are checked the way the analyzer checks them: declare before use, block scope, and functions visible everywhere.</p>
    <div class="ins-card">
      <div class="ins-card-title">Symbol table</div>
      ${symbols.length
        ? `<div class="ins-sym-head"><span>NAME</span><span>DECLARED</span><span>INFERRED</span><span>SCOPE</span></div>${symbolRows}`
        : note("No symbols declared.")}
    </div>
    <div class="ins-card">
      <div class="ins-card-title">Scope tree</div>
      ${model ? scopeTree(model.scopes[0]) : note("No syntax tree to show.")}
    </div>
    <div class="ins-card">
      <div class="ins-card-title">Name resolution</div>
      ${resolutionHtml || note("No names are used in this program.")}
    </div>
    <div class="ins-card">
      <div class="ins-card-title">Type and scope checks</div>
      ${issues.length ? issues.map(errRow).join("") : '<p class="ins-ok">No type or scope errors.</p>'}
    </div>`;
}

function executionView() {
  if (!lastRun) return note("Run a program first, then open the Execution stage.");
  const stage = stageNamed("Interpreter");
  if (!stage || stage.status === "skipped") {
    return note("Interpreter skipped. An earlier stage stopped the run; see Problems.");
  }
  if (stage.status === "not_implemented") return note(`Not run yet · ${stage.detail}.`);

  const steps = trace();
  const output = lastRun.output ?? [];
  const outputCard = `
    <details class="ins-det" open data-ins-key="exec:output"><summary>Program output</summary>
      <pre class="ins-output">${esc(output.length ? output.join("\n") : "(no output)")}</pre>
    </details>`;
  if (!steps.length) return note("No steps were recorded for this run.") + outputCard;

  selectedStep = clampIndex(selectedStep, steps.length);
  const cur = steps[selectedStep];
  const frames = Array.isArray(cur.call_stack) && cur.call_stack.length ? cur.call_stack : ["global"];
  const depth = frames.length - 1;
  const maxDepth = steps.reduce((m, s) => Math.max(m, s.depth ?? 0), 0);
  const playing = playTimer !== null;

  const rows = steps.map((s, i) => `
    <tr class="ins-row${i === selectedStep ? " active" : ""}" data-ins-step="${i}">
      <td class="ins-num">${esc(s.step)}</td>
      <td class="ins-num">${esc(loc(s.line, s.col))}</td>
      <td style="padding-left:${8 + (s.depth ?? 0) * 14}px"><code>${esc(s.operation)}</code></td>
      <td>${esc(s.result)}</td>
    </tr>`).join("");

  const controls = [["first", "First"], ["prev", "Prev"], ["play", playing ? "Pause" : "Play"], ["next", "Next"], ["last", "Last"]]
    .map(([action, label]) =>
      `<button type="button" class="ins-btn${action === "play" && playing ? " on" : ""}" data-ins-exec="${action}">${label}</button>`
    ).join("");

  const frameList = frames.slice().reverse().map((f, i) =>
    `<li class="ins-frame${i === 0 ? " top" : ""}"><code>${esc(f)}</code></li>`).join("");

  const varRows = (list) => list.length
    ? list.map((v) => `<tr><td><code>${esc(v.name)}</code></td><td>${esc(v.type)}</td><td>${esc(v.value)}</td></tr>`).join("")
    : `<tr><td colspan="3" class="ins-muted">No variables.</td></tr>`;

  const vars = cur.variables ?? [];
  const finalVars = steps[steps.length - 1].variables ?? [];

  return `
    <div class="ins-stats">
      ${stat("Steps", steps.length)}
      ${stat("Max call depth", maxDepth)}
      ${stat("Output lines", output.length)}
      ${stat("Interpreter", String(stage.status).replace("_", " "))}
    </div>
    <div class="ins-card">
      <div class="ins-row-inline">
        <span class="ins-card-title">Execution trace</span>
        <span class="ins-count">Step ${selectedStep + 1} of ${steps.length}</span>
      </div>
      <div class="ins-btns">${controls}</div>
      <div class="ins-scroll">
        <table class="ins-table">
          <thead><tr><th>STEP</th><th>LINE:COL</th><th>OPERATION</th><th>RESULT</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>
    <div class="ins-card">
      <div class="ins-card-title">Selected step · ${esc(cur.step)}</div>
      <p class="ins-p"><code>${esc(cur.operation)}</code> → ${esc(cur.result)}</p>
      <details class="ins-det" open data-ins-key="exec:frames"><summary>Call stack (depth ${depth})</summary>
        <ol class="ins-frames">${frameList}</ol>
      </details>
      <details class="ins-det" open data-ins-key="exec:vars"><summary>Variables at this step (${vars.length})</summary>
        <table class="ins-table">
          <thead><tr><th>NAME</th><th>TYPE</th><th>VALUE</th></tr></thead>
          <tbody>${varRows(vars)}</tbody>
        </table>
      </details>
    </div>
    <details class="ins-det" data-ins-key="exec:final"><summary>Variables at the end (${finalVars.length})</summary>
      <table class="ins-table">
        <thead><tr><th>NAME</th><th>TYPE</th><th>VALUE</th></tr></thead>
        <tbody>${varRows(finalVars)}</tbody>
      </table>
    </details>
    ${outputCard}
    <div class="ins-verdict ${lastRun.ok ? "ok" : "err"}">${lastRun.ok ? "Process exited successfully" : "Process stopped with an error. See Problems."}</div>`;
}

// ---------- rendering and state ----------

function render() {
  const host = $("stageDetail");
  if (!host || !current) return;
  const views = { tokens: tokensView, dfa: dfaView, semantic: semanticView, execution: executionView };

  // Keep the open or closed state of expandable sections across re-renders.
  const open = new Map([...host.querySelectorAll("details[data-ins-key]")]
    .map((d) => [d.dataset.insKey, d.open]));

  host.innerHTML = `<div class="ins-root">${views[current]()}</div>`;

  host.querySelectorAll("details[data-ins-key]").forEach((d) => {
    if (open.has(d.dataset.insKey)) d.open = open.get(d.dataset.insKey);
  });

  if (current === "execution") {
    host.querySelector(".ins-row.active")?.scrollIntoView({ block: "nearest" });
  }
}

function show(view) {
  if (view !== current) stopPlay();
  current = view;
  render();
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
    render();
    return;
  }
  playTimer = setInterval(() => {
    const total = trace().length;
    if (current !== "execution" || selectedStep >= total - 1) {
      stopPlay();
      render();
      return;
    }
    selectedStep += 1;
    render();
  }, PLAY_MS);
  render();
}

function execControl(action) {
  const total = trace().length;
  if (!total) return;
  if (action === "play") {
    togglePlay();
    return;
  }
  stopPlay();
  const moves = { first: 0, last: total - 1, prev: selectedStep - 1, next: selectedStep + 1 };
  selectedStep = clampIndex(moves[action] ?? selectedStep, total);
  render();
}

// ---------- keep the last run ----------

const nativeFetch = window.fetch.bind(window);
window.fetch = async (input, init) => {
  const response = await nativeFetch(input, init);
  const url = typeof input === "string" ? input : input?.url ?? "";
  if (url.endsWith("/api/run")) {
    response.clone().json().then((data) => {
      lastRun = data;
      selectedToken = 0;
      selectedStep = 0;
      stopPlay();
      setTimeout(render, 80);
    }).catch(() => {});
  }
  return response;
};

// ---------- wiring ----------

function mountDfaTab() {
  const bar = $("howTabs");
  if (!bar || bar.querySelector('[data-tab="dfa"]')) return;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "how-tab";
  button.dataset.tab = "dfa";
  button.setAttribute("role", "tab");
  button.setAttribute("aria-selected", "false");
  button.textContent = "DFA";
  const tokensTab = bar.querySelector('[data-tab="tokens"]');
  if (tokensTab) tokensTab.after(button);
  else bar.append(button);
}

mountDfaTab();

// Runs after how-tabs.js has handled the click. Only DFA and Summary need work here;
// the other tabs click a stage card, which the handler below takes care of.
$("howTabs")?.addEventListener("click", (event) => {
  const tab = event.target.closest(".how-tab")?.dataset.tab;
  if (tab === "dfa") show("dfa");
  else if (tab === "summary") show(null);
});

// Stage cards. This listener is on #stages, so it runs after app.js, parser-view,
// semantic-view and trace-view have handled the same click.
$("stages")?.addEventListener("click", (event) => {
  const card = event.target.closest(".stage");
  if (!card) return;
  const index = [...$("stages").querySelectorAll(".stage")].indexOf(card);
  show(VIEW_FOR_CARD[index] ?? null);
});

// Opening the panel: restore the tab that was active.
$("howToggle")?.addEventListener("click", () => {
  setTimeout(() => {
    const tab = document.querySelector("#howTabs .how-tab.active")?.dataset.tab;
    if (tab === "dfa") show("dfa");
    else if (tab === "summary") show(null);
  }, 10);
});

// Clicks and changes inside the rendered views.
$("stageDetail")?.addEventListener("click", (event) => {
  const tokenButton = event.target.closest("[data-ins-tok]");
  if (tokenButton) {
    selectedToken = Number(tokenButton.dataset.insTok);
    render();
    return;
  }
  const stepRow = event.target.closest("[data-ins-step]");
  if (stepRow) {
    selectedStep = Number(stepRow.dataset.insStep);
    render();
    return;
  }
  const control = event.target.closest("[data-ins-exec]");
  if (control) execControl(control.dataset.insExec);
});

$("stageDetail")?.addEventListener("change", (event) => {
  if (event.target.hasAttribute?.("data-ins-dfa-select")) {
    selectedToken = Number(event.target.value);
    render();
  }
});