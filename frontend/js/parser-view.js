// Phase 2: Parser view.
// Adds the Parser stage detail: grammar, AST tree and AST JSON.
// app.js is not modified. This file listens for clicks on the stage cards using
// event delegation, so it runs after app.js has handled the click. It renders
// into #stageDetail when the Parser card (the second card) is clicked.
// It keeps the last /api/run response by wrapping fetch.

const GRAMMAR = `program        = { top_level } ;
top_level      = func_decl | statement ;
func_decl      = type IDENT "(" [ param { "," param } ] ")" block ;
param          = type IDENT ;
block          = "{" { statement } "}" ;
statement      = block | var_decl ";" | assign_stmt ";" | if_stmt | while_stmt | for_stmt | return_stmt ";" | "break" ";" | "continue" ";" | expr ";" ;
var_decl       = type IDENT [ "=" expr ] ;
assign_stmt    = IDENT ( "=" | "+=" | "-=" | "*=" | "/=" ) expr | IDENT ( "++" | "--" ) ;
if_stmt        = "if" "(" expr ")" block [ "else" ( if_stmt | block ) ] ;
while_stmt     = "while" "(" expr ")" block ;
for_stmt       = "for" "(" [ var_decl | assign_stmt ] ";" [ expr ] ";" [ assign_stmt ] ")" block ;
return_stmt    = "return" [ expr ] ;
type           = "int" | "float" | "bool" | "string" | "void" ;
expr           = or_expr ;
or_expr        = and_expr { "||" and_expr } ;
and_expr       = equality { "&&" equality } ;
equality       = relational { ( "==" | "!=" ) relational } ;
relational     = additive { ( "<" | "<=" | ">" | ">=" ) additive } ;
additive       = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative = unary { ( "*" | "/" | "%" ) unary } ;
unary          = ( "-" | "!" ) unary | primary ;
primary        = INT | FLOAT | STRING | "true" | "false" | IDENT [ "(" [ args ] ")" ] | type "(" expr ")" | "(" expr ")" ;
args           = expr { "," expr } ;`;

const PARSER_CARD_INDEX = 1;
const HIDDEN_KEYS = new Set(["type", "line", "col"]);

let lastRun = null;

// Keep the last /api/run response. The original response is returned untouched.
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
  if (cards.indexOf(card) !== PARSER_CARD_INDEX) return;
  renderParser();
});

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function note(text) {
  return el("p", "pv-note", text);
}

function card(title, body) {
  const wrap = el("div", "pv-card");
  wrap.append(el("div", "pv-title", title), body);
  return wrap;
}

function isNode(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// One AST node as a collapsible tree item. Child nodes become nested items;
// scalar fields (op, name, value, ...) are shown beside the node type.
function treeItem(node, label) {
  const scalars = [];
  const children = [];
  for (const [key, value] of Object.entries(node)) {
    if (HIDDEN_KEYS.has(key) || value === null) continue;
    if (Array.isArray(value)) {
      for (const item of value) {
        if (isNode(item)) children.push(treeItem(item, key));
      }
    } else if (isNode(value)) {
      children.push(treeItem(value, key));
    } else {
      scalars.push(`${key} ${JSON.stringify(value)}`);
    }
  }

  const head = el("span", "pv-head");
  if (label) head.append(el("span", "pv-label", `${label} `));
  head.append(el("span", "pv-type", node.type));
  if (scalars.length) head.append(el("span", "pv-attrs", `  ${scalars.join("   ")}`));
  head.append(el("span", "pv-pos", `${node.line}:${node.col}`));

  if (children.length === 0) {
    const leaf = el("div", "pv-leaf");
    leaf.append(head);
    return leaf;
  }
  const details = document.createElement("details");
  details.open = true;
  const summary = document.createElement("summary");
  summary.append(head);
  details.append(summary, ...children);
  return details;
}

function renderParser() {
  detailEl.replaceChildren();

  if (!lastRun) {
    detailEl.append(note("Run a program first, then open the Parser stage."));
    return;
  }

  if (!lastRun.ast) {
    const parser = lastRun.stages.find((s) => s.name === "Parser");
    const msg = parser && parser.status === "failed"
      ? `The parser found ${parser.detail}. No tree was built. See Problems.`
      : "The parser did not run because the lexer found errors. See Problems.";
    detailEl.append(note(msg));
    return;
  }

  const tree = el("div", "pv-tree");
  tree.append(treeItem(lastRun.ast, null));

  detailEl.append(
    card("Grammar", el("pre", "pv-code", GRAMMAR)),
    card("Abstract syntax tree", tree),
    card("AST JSON", el("pre", "pv-code", JSON.stringify(lastRun.ast, null, 2))),
  );
}