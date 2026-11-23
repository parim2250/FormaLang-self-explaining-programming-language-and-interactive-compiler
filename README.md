<div align="center">

# FormaLang

### A small C-style programming language with a compiler that explains itself

Write code. Run it. Then *watch* every stage of the compiler (lexer, parser, semantic analyzer, interpreter) work, right in your browser.

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Frontend](https://img.shields.io/badge/Frontend-CodeMirror%206-orange)](https://codemirror.net/)
[![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)](#-testing)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### 🌐 Live Demo: [ADD YOUR WEBSITE LINK HERE](https://your-website-link-here.com)

</div>

---

## 📖 Table of Contents

- [About the Project](#-about-the-project)
- [Why FormaLang?](#-why-formalang)
- [Key Features](#-key-features)
- [Screenshots](#-screenshots)
- [How It Works](#-how-it-works)
- [The Language at a Glance](#-the-language-at-a-glance)
- [Error Codes](#-error-codes)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Forma Assistant (Optional AI)](#-forma-assistant-optional-ai)
- [API Reference](#-api-reference)
- [Testing](#-testing)
- [Demo Walkthrough](#-demo-walkthrough)
- [Roadmap](#-roadmap)
- [Author](#-author)
- [License](#-license)

---

## 📌 About the Project

**FormaLang** is a small, statically typed, C-style teaching language paired with an interactive, browser-based compiler IDE. Most compilers are black boxes: you give them source code and get back either a result or a cryptic error. FormaLang turns that around. Every stage of compilation is exposed, inspectable, and explained.

```
Source → Lexer (DFA) → Parser (Recursive Descent → AST) → Semantic Analyzer → Interpreter → Output
```

The project was built as a **Theory of Computation** project. It shows, end to end, how the ideas from the course (finite automata, formal grammars, parsing) become a working language implementation.

---

## 💡 Why FormaLang?

| The problem | FormaLang's answer |
|---|---|
| Compilers are black boxes, so students never see *how* code becomes output | Every stage has its own visual view: tokens, AST, symbol table, execution trace |
| Compiler errors are cryptic | Every error has a stable code (like `E201`) plus a plain-language hint |
| Theory (DFA, grammars) feels disconnected from real software | The lexer is literally a **DFA stored as a transition table**, and the parser follows an **EBNF grammar** |
| Debugging recursion and scope is hard to picture | The execution view shows variable snapshots and a **live call stack** growing and shrinking |

---

## ✨ Key Features

### 🔬 Self-Explaining Compiler
- **"Show How It Works" panel** with five tabs: **Tokens**, **AST**, **Semantic**, **Execution**, and **Summary**
- Each pipeline stage reports *passed / failed / skipped* with timing and counts (tokens, AST nodes, symbols)
- **Step-by-step execution trace**: every step records the line, the operation, the result, a snapshot of visible variables, the call depth, and the call stack

### 🧠 A Real Compiler Pipeline
- **Lexer**: a table-driven **Deterministic Finite Automaton (DFA)** using maximal munch
- **Parser**: hand-written **recursive descent (LL(2))** parser that builds a full Abstract Syntax Tree
- **Semantic analyzer**: scoped symbol table, static type checking, and function and return checks, reporting *all* errors in one pass
- **Interpreter**: tree-walking interpreter with a call stack, recursion, and safety limits

### 💬 Friendly Diagnostics
- Structured error codes (`E1xx` to `E5xx`) grouped by compiler stage
- Plain-language **hint** under each problem
- Click a problem and the editor cursor jumps straight to the offending line

### 🖥️ A Proper IDE Experience
- **CodeMirror 6** editor with syntax highlighting
- Multi-file **project explorer** with tabs and a breadcrumb bar
- **Search across all files**
- Built-in **source control panel** (commit your changes)
- **Console** and **Problems** panels, plus a built-in **language guide**
- Ready-made **examples** (including programs that fail on purpose, to demo error handling)
- Keyboard shortcuts: `Ctrl/⌘ + Enter` to run, `Ctrl + S` to save

### 🤖 Forma Assistant (Optional)
- AI explainer powered by **Groq**: *Explain my code, Explain error, Why this output?, Explain execution flow, Suggest a fix*, or ask your own question
- **Grounded in the compiler's real data**. It only explains what the compiler produced and never runs or checks code itself
- The API key stays **server-side** and is never sent to the browser
- The compiler works **100% without it**

---

## 📸 Screenshots

> Replace the placeholders below with your own screenshots (for example, put them in a `docs/screenshots/` folder).

| Main IDE | Show How It Works |
|:---:|:---:|
| ![IDE](docs/screenshots/ide.png) | ![How it works](docs/screenshots/how-it-works.png) |
| **Tokens (DFA lexer)** | **AST view** |
| ![Tokens](docs/screenshots/tokens.png) | ![AST](docs/screenshots/ast.png) |
| **Execution trace and call stack** | **Problems and error hints** |
| ![Execution](docs/screenshots/execution.png) | ![Problems](docs/screenshots/problems.png) |
| **Forma Assistant** | **Language guide** |
| ![Assistant](docs/screenshots/assistant.png) | ![Guide](docs/screenshots/guide.png) |

---

## ⚙️ How It Works

```
┌──────────┐   ┌───────────────┐   ┌──────────────┐   ┌────────────────────┐   ┌───────────────┐   ┌────────┐
│  Source  │──▶│     Lexer     │──▶│    Parser    │──▶│ Semantic Analyzer  │──▶│  Interpreter  │──▶│ Output │
│   code   │   │  (DFA table)  │   │ (Rec. descent)│  │ (symbols + types)  │   │ (exec. trace) │   │        │
└──────────┘   └───────────────┘   └──────────────┘   └────────────────────┘   └───────────────┘   └────────┘
                    tokens              AST             symbol table, errors     steps, call stack
```

| Stage | What it does | Where you see it |
|---|---|---|
| **1. Lexer** | A DFA (a transition table, not hand-written branching) scans characters into tokens using maximal munch. Reports `E1xx` errors. | *Tokens* tab |
| **2. Parser** | Recursive descent over the EBNF grammar builds the AST. Reports `E4xx` syntax errors. | *AST* tab |
| **3. Semantic analyzer** | Builds the scoped symbol table, checks types, scopes, and function calls and returns before anything runs. Reports `E2xx` and `E3xx`. | *Semantic* tab |
| **4. Interpreter** | Executes the AST and records every step with a variable snapshot and call stack. Reports `E5xx` runtime errors. | *Execution* tab |

If a stage fails, later stages are marked **skipped**, and the Summary tab shows exactly where compilation stopped.

---

## 🧾 The Language at a Glance

**Types:** `int` (64-bit) · `float` (double) · `bool` · `string` · `void` (return type only)

**Statements:** declarations · assignment (`=`, `+=`, `-=`, `*=`, `/=`) · `++` / `--` · `if` / `else if` / `else` · `while` · `for` · `break` · `continue` · `return`

**Functions:** top-level only · pass by value · recursion allowed · may be called before they are defined

**Built-ins:** `print(x)` · conversions `int(x)`, `float(x)`, `string(x)`, `bool(x)`

**Comments:** `// line` and `/* block */`

### Example

```c
// FormaLang: a small language with a readable compiler
string greet(string name) {
    return "Hello from " + name + "!";
}

string language = "FormaLang";
float version = 1.0;

print(greet(language));
for (int i = 1; i <= 3; i++) {
    print("Step " + i);
}
```

**Output**

```
Hello from FormaLang!
Step 1
Step 2
Step 3
```

### Typing rules in brief
- `int` widens to `float` implicitly. `float` to `int` needs an explicit `int(x)` (truncates toward zero).
- `string + anything` concatenates (floats always print with a decimal, such as `1.0`).
- `/` on two ints is integer division. `%` is int-only.
- No truthiness: `if`, `while`, and `for` conditions **must** be `bool`.
- Block-scoped variables with shadowing allowed. Same-scope redeclaration is an error.

📘 The full definition, including the grammar in EBNF, is in [`docs/LANGUAGE_SPEC.md`](docs/LANGUAGE_SPEC.md).

---

## 🚨 Error Codes

Every problem has a stable code and a plain-language hint.

| Range | Stage | Codes |
|---|---|---|
| **E1xx** | Lexer | `E101` unterminated string · `E102` unexpected character · `E103` malformed number · `E104` unterminated block comment · `E105` invalid escape |
| **E2xx** | Types | `E201` type mismatch · `E202` invalid operands · `E203` condition not bool · `E204` wrong argument count · `E205` argument type mismatch · `E206` return type mismatch / missing return |
| **E3xx** | Scope | `E301` undeclared identifier · `E302` redeclaration · `E303` undefined function · `E304` break/continue outside loop · `E305` return outside function |
| **E4xx** | Syntax | `E401` unexpected token · `E402` expected token (e.g. `;` or `)`) |
| **E5xx** | Runtime | `E501` division by zero · `E502` integer overflow · `E503` call depth exceeded (200) · `E504` step limit reached (1,000,000) |

**Try it:** `float version = "1.0";` → `E201`: expected `float`, received `string`.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12+, FastAPI, Uvicorn, Pydantic |
| **Compiler** | Pure Python: table-driven DFA lexer, recursive-descent parser, semantic analyzer, tree-walking interpreter |
| **Frontend** | HTML, CSS, vanilla JavaScript (ES modules), CodeMirror 6, Lucide icons |
| **AI (optional)** | Groq API via `httpx` |
| **Testing** | pytest, httpx |

---

## 📁 Project Structure

```
FormaLang/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI routes + static frontend hosting
│   │   ├── assistant.py         # Forma Assistant (Groq integration)
│   │   └── compiler/
│   │       ├── lexer.py         # DFA-driven tokenizer
│   │       ├── parser.py        # Recursive-descent parser → AST
│   │       ├── semantic.py      # Symbol table, type & scope checks
│   │       ├── interpreter.py   # Tree-walking interpreter + execution trace
│   │       ├── hints.py         # Plain-language hints per error code
│   │       └── pipeline.py      # Runs all stages, returns one structured result
│   ├── tests/                   # pytest suite
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/                      # app, inspector, parser/semantic/trace views,
│                                # how-tabs, examples, ai-assistant, ...
├── examples/                    # Example programs (.fl) + expected results
├── docs/
│   └── LANGUAGE_SPEC.md         # Full language definition
├── setup.bat                    # One-click setup + tests + run (Windows)
├── run.bat                      # Start the server (Windows)
├── LICENSE
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.12 or newer** ([python.org](https://www.python.org/downloads/)). On Windows, tick *"Add python.exe to PATH"* during install.
- A modern web browser

### Option A: Windows (one click)

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>

# 2. Run the setup script
#    (creates a virtual environment, installs packages, runs tests, starts the server)
setup.bat
```

Then open **http://127.0.0.1:8000**.

After the first setup, use `run.bat` to start the server without re-running the tests.

### Option B: Manual setup (Windows / macOS / Linux)

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>/backend

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) create your environment file
cp .env.example .env

# 5. Start the server
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**. The backend serves the frontend too, so there is nothing else to run.

---

## 🤖 Forma Assistant (Optional AI)

Forma Assistant explains compiler results in plain language. It is **completely optional**, and the compiler works without it.

1. Create a free API key at [console.groq.com](https://console.groq.com/).
2. Open `backend/.env` and add:

   ```env
   GROQ_API_KEY=your_key_here
   GROQ_MODEL=openai/gpt-oss-120b   # optional; use any model ID from your Groq account
   ```

   If `GROQ_MODEL` is not set, the default model in `backend/app/assistant.py` is used.
3. Restart the server.

**Available actions:** Explain my code · Explain error · Why this output? · Explain execution flow · Suggest a fix · Ask a custom question.

**Privacy and safety**
- The API key lives on the server only and is never exposed to the browser.
- The assistant receives only the compiler's data for the **last run** (source, stages, problems, symbols, output, and a trimmed trace).
- It never executes or validates code. It only explains what the compiler already produced.

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Returns server status, version, and whether the AI assistant is configured |
| `POST` | `/api/run` | Runs the full pipeline on `{ "source": "..." }` and returns stages, tokens, AST, symbols, diagnostics, trace, and output |
| `POST` | `/api/assist` | Asks Forma Assistant: `{ "action", "question", "source", "result" }` |

**Example**

```bash
curl -X POST http://127.0.0.1:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"source": "print(\"Hello, FormaLang!\");"}'
```

Interactive API docs are available at **http://127.0.0.1:8000/docs** (FastAPI Swagger UI).

---

## 🧪 Testing

From the `backend` folder:

```bash
python -m pytest
```

(On Windows with the setup script's environment: `.venv\Scripts\python.exe -m pytest`)

The suite has **185+ tests across 14 files** and covers:

- Lexer (DFA behavior and lexical errors)
- Parser (grammar, AST shape, syntax errors)
- Semantic analyzer (types, scopes, functions)
- Interpreter, control flow, and functions (including recursion limits)
- Error codes and plain-language hints
- Execution trace
- Assistant (no network calls are made)
- API endpoints
- **Golden tests** for every program in `examples/`, checked against `examples/expected.json`

---

## 🎬 Demo Walkthrough

1. Open **Examples → Hello** and click **Run**.
2. Open **Language tour** and run it. You will see the greeting and the three steps.
3. Open **Types and conversion**. Notice that whole `float` values print as `7.0`, and that `int(total)` is needed to go from `float` to `int`.
4. Open **Functions and recursion**, expand **Show how it works**, and go to the **Execution** tab. Watch the call stack grow and shrink.
5. Open **Type error** and run it. You will see `E201` in Problems, the hint, and the cursor jump to the line.
6. Open the **Assistant** panel and click **Explain error** (requires an API key).

---

## 🗺️ Roadmap

FormaLang v0.1 deliberately keeps the language small. Ideas for future versions:

- [ ] Arrays and structs
- [ ] `input()` for interactive programs
- [ ] Exponent notation for floats
- [ ] Imports / multi-file programs
- [ ] Closures and nested functions
- [ ] Bytecode backend or a compile-to-C target
- [ ] Shareable program links
- [ ] Step-through debugger with breakpoints

---

## 👩‍💻 Author

**Pari Mittal**

- GitHub: [@your-github-username](https://github.com/your-github-username)
- LinkedIn: [your-linkedin](https://www.linkedin.com/in/your-linkedin)

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

<div align="center">

**If you found FormaLang useful, consider giving it a ⭐**

*Built to make compilers less mysterious.*

</div>