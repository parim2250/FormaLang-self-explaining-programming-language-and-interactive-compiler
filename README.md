<div align="center">

# FormaLang

### A small C-style programming language with a compiler that explains itself

Write code, run it, then watch every stage of the compiler work, right in your browser.

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![CodeMirror](https://img.shields.io/badge/Editor-CodeMirror%206-orange)](https://codemirror.net/)
[![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)](#-tests)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🌐 [Live Demo → formalang.vercel.app](https://formalang.vercel.app/)

</div>

---

## 📌 About

Most compilers are black boxes: code goes in, and you get a result or a cryptic error. **FormaLang** turns that around. It is a small, statically typed teaching language with an interactive browser IDE that exposes every stage of compilation, so you can see exactly how source code becomes output.

```
Source → Lexer (DFA) → Parser (AST) → Semantic Analyzer → Interpreter → Output
```

Built as a **Theory of Computation** project. The lexer is a real DFA stored as a transition table, and the parser follows an EBNF grammar, so the theory from class is visible in working software.

## ✨ Features

**🔬 Self-explaining compiler**
- **Show How It Works** panel with *Tokens, AST, Semantic, Execution,* and *Summary* tabs
- Each stage reports passed / failed / skipped, with counts (tokens, AST nodes, symbols)
- Step-by-step **execution trace** with variable snapshots and a live **call stack** (great for understanding recursion)

**💬 Friendly errors**
- Every problem has a stable code (`E201`, `E301`, ...) and a plain-language hint
- Click a problem and the editor jumps straight to the line
- The semantic analyzer reports all errors in one pass, without cascading follow-up errors

**🖥️ Real IDE feel**
- CodeMirror 6 editor with syntax highlighting
- Multi-file explorer with tabs, search across files, and a source control panel
- Console and Problems panels, built-in language guide, and ready-made examples (including programs that fail on purpose)
- Shortcuts: `Ctrl/⌘ + Enter` to run, `Ctrl + S` to save

**🤖 Forma Assistant (optional)**
- Groq-powered explanations: *Explain my code, Explain error, Why this output?, Explain execution flow, Suggest a fix,* or ask your own question
- It only explains what the compiler produced and never runs code itself
- The compiler works fully without it

## ⚙️ How It Works

| Stage | What it does | Errors |
|---|---|---|
| **Lexer** | A table-driven DFA scans characters into tokens using maximal munch | `E1xx` |
| **Parser** | Hand-written recursive descent (LL(2)) builds the Abstract Syntax Tree | `E4xx` |
| **Semantic analyzer** | Scoped symbol table, static type checks, function and return checks, all before anything runs | `E2xx`, `E3xx` |
| **Interpreter** | Tree-walking execution with a call stack, recursion, and safety limits (200 call depth, 1,000,000 steps) | `E5xx` |

If a stage fails, the later stages are marked as skipped and the Summary tab shows exactly where compilation stopped.

## 🧾 The Language

```c
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

```
Hello from FormaLang!
Step 1
Step 2
Step 3
```

| | |
|---|---|
| **Types** | `int` (64-bit), `float`, `bool`, `string`, `void` (return type only) |
| **Statements** | declarations, `=` `+=` `-=` `*=` `/=`, `++` `--`, `if / else if / else`, `while`, `for`, `break`, `continue`, `return` |
| **Functions** | top-level, pass by value, recursion allowed, callable before definition |
| **Built-ins** | `print(x)`, `int(x)`, `float(x)`, `string(x)`, `bool(x)` |
| **Comments** | `// line` and `/* block */` |

**A few rules:** `int` widens to `float` automatically, but `float` to `int` needs an explicit `int(x)`. Conditions must be `bool` (no truthiness). Variables are block scoped, and redeclaring in the same scope is an error.

Full grammar and rules: [`docs/LANGUAGE_SPEC.md`](docs/LANGUAGE_SPEC.md)

## 🚨 Error Codes

| Range | Stage | Examples |
|---|---|---|
| **E1xx** | Lexer | E101 unterminated string, E102 unexpected character, E103 malformed number |
| **E2xx** | Types | E201 type mismatch, E203 condition not bool, E204 wrong argument count, E206 missing return |
| **E3xx** | Scope | E301 undeclared name, E302 redeclared name, E304 break outside loop |
| **E4xx** | Syntax | E401 unexpected token, E402 missing token |
| **E5xx** | Runtime | E501 division by zero, E502 overflow, E503 call depth, E504 step limit |

Example: `float version = "1.0";` gives `E201` (expected `float`, received `string`).

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12+, FastAPI, Uvicorn, Pydantic |
| Compiler | Pure Python: DFA lexer, recursive-descent parser, semantic analyzer, tree-walking interpreter |
| Frontend | HTML, CSS, vanilla JavaScript (ES modules), CodeMirror 6 |
| AI (optional) | Groq API |
| Testing | pytest, httpx |

## 🚀 Getting Started

**Prerequisite:** Python 3.12 or newer.

**Windows (one click)**

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
setup.bat
```

This creates the virtual environment, installs packages, runs the tests, and starts the server. Next time, just run `run.bat`.

**macOS / Linux / manual**

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>/backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**. The backend serves the frontend too, so there is nothing else to run.

## 🤖 Forma Assistant Setup (optional)

1. Get an API key from [console.groq.com](https://console.groq.com/).
2. Add it to `backend/.env`:

```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-120b   # optional, any model ID from your Groq account
```

3. Restart the server.

The key stays on the server and is never sent to the browser. The assistant only receives the compiler's data from your last run.

## 🔌 API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Status, version, and whether AI is configured |
| `POST` | `/api/run` | Run the full pipeline on `{ "source": "..." }` |
| `POST` | `/api/assist` | Ask Forma Assistant |

```bash
curl -X POST http://127.0.0.1:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"source": "print(\"Hello, FormaLang!\");"}'
```

Swagger docs are available at `/docs`.

## 🧪 Tests

```bash
cd backend
python -m pytest
```

185+ tests across 14 files covering the lexer, parser, semantic analyzer, interpreter, control flow, functions, error codes, hints, execution trace, assistant (no network calls), API, and golden tests for every program in `examples/`.

## 🎬 Quick Demo

1. Open **Examples → Language tour** and click **Run**.
2. Expand **Show how it works** and flip through *Tokens, AST, Semantic, Execution*.
3. Open **Functions and recursion** and watch the call stack grow and shrink in the Execution tab.
4. Open **Type error** and run it. See `E201` in Problems, read the hint, and click to jump to the line.

## 📁 Project Structure

```
FormaLang/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI routes + frontend hosting
│   │   ├── assistant.py       # Forma Assistant (Groq)
│   │   └── compiler/          # lexer, parser, semantic, interpreter, hints, pipeline
│   ├── tests/                 # pytest suite
│   └── requirements.txt
├── frontend/                  # index.html, css/, js/ (browser IDE)
├── examples/                  # example programs + expected results
├── docs/LANGUAGE_SPEC.md      # language definition
├── setup.bat / run.bat        # Windows helpers
└── LICENSE
```

## 🗺️ Roadmap

- [ ] Arrays and structs
- [ ] `input()` support
- [ ] Float exponent notation
- [ ] Imports / multi-file programs
- [ ] Step-through debugger with breakpoints

## 👩‍💻 Author

**Pari Mittal**

## 📄 License

Released under the MIT License. See [LICENSE](LICENSE).

---

<div align="center">

If you like FormaLang, consider giving it a ⭐

</div>