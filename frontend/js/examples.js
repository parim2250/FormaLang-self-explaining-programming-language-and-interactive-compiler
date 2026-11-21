// Phase 8: example gallery.
// Opens a list of ready-made programs. Choosing one replaces the editor content.
// Uses the existing CodeMirror view on #editor. If that view cannot be found, it
// writes the example to the autosave key and reloads the page.

import { EditorView } from "https://esm.sh/@codemirror/view@6";

const AUTOSAVE_KEY = "formalang.main.forma";

const EXAMPLES = [
  {
    id: "hello",
    title: "Hello",
    summary: "Your first program.",
    code: `print("Hello, FormaLang!");
`,
  },
  {
    id: "tour",
    title: "Language tour",
    summary: "Functions, a comment, a loop and string concatenation.",
    code: `// FormaLang: a small language with a readable compiler
string greet(string name) {
    return "Hello from " + name + "!";
}

string language = "FormaLang";
float version = 1.0;
// float version = "1.0";   // E201: a string cannot become a float

print(greet(language));
for (int i = 1; i <= 3; i++) {
    print("Step " + i);
}
`,
  },
  {
    id: "types",
    title: "Types and conversion",
    summary: "int widens to float; float to int needs int(x).",
    code: `int apples = 3;
float price = 2.5;
float total = apples * price;
print(total);

int whole = int(total);
print(whole);
print(string(whole) + " apples");
`,
  },
  {
    id: "sum",
    title: "Loop sum",
    summary: "A for loop that adds numbers from 1 to 10.",
    code: `int sum = 0;
for (int i = 1; i <= 10; i++) {
    sum += i;
}
print("Sum of 1 to 10 = " + sum);
`,
  },
  {
    id: "collatz",
    title: "While and break",
    summary: "Counts Collatz steps until the value reaches 1.",
    code: `int n = 27;
int steps = 0;
while (true) {
    if (n == 1) { break; }
    if (n % 2 == 0) { n = n / 2; }
    else { n = 3 * n + 1; }
    steps++;
}
print("Collatz steps: " + steps);
`,
  },
  {
    id: "factorial",
    title: "Functions and recursion",
    summary: "A recursive factorial with a return value.",
    code: `int factorial(int n) {
    if (n <= 1) { return 1; }
    return n * factorial(n - 1);
}
print("5! = " + factorial(5));
`,
  },
  {
    id: "fail-type",
    title: "Type error",
    summary: "Assigning a float to an int variable.",
    fails: true,
    code: `int count = 1;
count = 2.5;
print(count);
`,
  },
  {
    id: "fail-undeclared",
    title: "Undeclared name",
    summary: "Using a variable that was never declared.",
    fails: true,
    code: `int total = 10;
print(totl);
`,
  },
  {
    id: "fail-divide",
    title: "Division by zero",
    summary: "Fails at runtime, after the program passes every check.",
    fails: true,
    code: `int a = 10;
int b = 0;
print(a / b);
`,
  },
];

let modal = null;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function currentView() {
  const host = document.getElementById("editor");
  return host ? EditorView.findFromDOM(host) : null;
}

function showModal() {
  modal?.classList.remove("hidden");
}

function hideModal() {
  modal?.classList.add("hidden");
}

function loadExample(example) {
  const view = currentView();
  if (view) {
    const current = view.state.doc.toString();
    if (current.trim() && current !== example.code &&
        !confirm("Replace your current code with this example?")) {
      return;
    }
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: example.code },
      selection: { anchor: 0 },
    });
    view.focus();
  } else {
    localStorage.setItem(AUTOSAVE_KEY, example.code);
    location.reload();
  }
  hideModal();
}

function buildModal() {
  modal = document.createElement("div");
  modal.id = "exampleModal";
  modal.className = "modal-backdrop hidden";
  modal.innerHTML = `
    <div class="modal ex-modal" role="dialog" aria-label="Examples">
      <div class="modal-header">
        <h3>Examples</h3>
        <button type="button" class="icon-btn" data-close aria-label="Close">×</button>
      </div>
      <p class="muted ex-intro">Load a program into the editor. Your current code is replaced.</p>
      <div class="ex-list">
        ${EXAMPLES.map((ex) => `
          <div class="ex-card">
            <div>
              <div class="ex-title">${esc(ex.title)}${ex.fails ? ' <span class="badge">fails on purpose</span>' : ""}</div>
              <div class="ex-summary">${esc(ex.summary)}</div>
            </div>
            <button type="button" class="btn sm" data-example="${esc(ex.id)}">Open</button>
          </div>`).join("")}
      </div>
    </div>`;
  document.body.appendChild(modal);

  modal.addEventListener("click", (event) => {
    if (event.target === modal || event.target.closest("[data-close]")) {
      hideModal();
      return;
    }
    const button = event.target.closest("[data-example]");
    if (!button) return;
    const example = EXAMPLES.find((ex) => ex.id === button.dataset.example);
    if (example) loadExample(example);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hideModal();
  });
}

function mountButton() {
  const button = document.createElement("button");
  button.id = "btnExamples";
  button.type = "button";
  button.className = "btn btn-ghost";
  button.textContent = "Examples";
  button.addEventListener("click", showModal);

  const run = document.getElementById("btnRun");
  if (run?.parentElement) {
    run.parentElement.insertBefore(button, run);
  } else {
    document.querySelector(".topbar")?.appendChild(button);
  }
}

buildModal();
mountButton();