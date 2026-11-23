<div align="center">

# FormaLang

**A small C-style programming language with a compiler that explains itself.**

Write code, run it, then watch every compiler stage work, right in your browser.

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

### 🌐 [Live Demo → formalang.vercel.app](https://formalang.vercel.app/)

</div>

---

## About

FormaLang is a small, statically typed teaching language with an interactive browser IDE. Most compilers are black boxes. FormaLang shows every stage of compilation, so you can see exactly how source code becomes output:

```
Source → Lexer (DFA) → Parser (AST) → Semantic Analyzer → Interpreter → Output
```

Built as a Theory of Computation project: the lexer is a real DFA stored as a transition table, and the parser follows an EBNF grammar.

## Features

- **Show How It Works panel** with Tokens, AST, Semantic, Execution, and Summary tabs
- **Execution trace** with variable snapshots and a live call stack (great for recursion)
- **Clear errors**: every problem has a code (`E201`, `E301`, ...) and a plain-language hint, and clicking it jumps to the line
- **Full IDE feel**: CodeMirror 6 editor, multi-file explorer, search, source control panel, console, language guide, built-in examples
- **Forma Assistant (optional)**: Groq-powered explanations of your code, errors, and output. The compiler works fully without it

## The Language

```c
string greet(string name) {
    return "Hello from " + name + "!";
}

print(greet("FormaLang"));
for (int i = 1; i <= 3; i++) {
    print("Step " + i);
}
```

| | |
|---|---|
| **Types** | `int` (64-bit), `float`, `bool`, `string`, `void` |
| **Statements** | declarations, `=` `+=` `-=` `*=` `/=`, `++` `--`, `if/else`, `while`, `for`, `break`, `continue`, `return` |
| **Functions** | top-level, pass by value, recursion allowed |
| **Built-ins** | `print(x)`, `int()`, `float()`, `string()`, `bool()` |
| **Comments** | `// line` and `/* block */` |

Full grammar and rules: [`docs/LANGUAGE_SPEC.md`](docs/LANGUAGE_SPEC.md)

## Error Codes

| Range | Stage | Examples |
|---|---|---|
| E1xx | Lexer | E101 unterminated string, E102 unexpected character |
| E2xx | Types | E201 type mismatch, E203 condition not bool, E206 missing return |
| E3xx | Scope | E301 undeclared name, E302 redeclared name, E304 break outside loop |
| E4xx | Syntax | E401 unexpected token, E402 missing token |
| E5xx | Runtime | E501 division by zero, E503 call depth, E504 step limit |

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, Uvicorn
- **Compiler:** pure Python (DFA lexer, recursive-descent parser, semantic analyzer, tree-walking interpreter)
- **Frontend:** HTML, CSS, vanilla JavaScript, CodeMirror 6
- **AI (optional):** Groq API
- **Tests:** pytest

## Getting Started

**Windows (one click)**

```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
setup.bat
```

This sets up the virtual environment, installs packages, runs the tests, and starts the server. Next time, just run `run.bat`.

**macOS / Linux / manual**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open **http://127.0.0.1:8000**. The backend serves the frontend too.

## Forma Assistant (optional)

1. Get a key from [console.groq.com](https://console.groq.com/).
2. Add it to `backend/.env`:

```env
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-120b   # optional
```

3. Restart the server.

The key stays on the server. The assistant only sees the compiler's data from your last run.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Status, version, whether AI is configured |
| POST | `/api/run` | Run the pipeline on `{ "source": "..." }` |
| POST | `/api/assist` | Ask Forma Assistant |

## Tests

```bash
cd backend
python -m pytest
```

185+ tests covering the lexer, parser, semantic analyzer, interpreter, error codes, hints, API, and golden tests for every program in `examples/`.

## Project Structure

```
backend/
  app/main.py            FastAPI routes
  app/assistant.py       Forma Assistant (Groq)
  app/compiler/          lexer, parser, semantic, interpreter, hints, pipeline
  tests/                 pytest suite
frontend/                index.html, css/, js/ (browser IDE)
examples/                example programs + expected results
docs/LANGUAGE_SPEC.md    language definition
```

## Roadmap

- [ ] Arrays and structs
- [ ] `input()` support
- [ ] Imports / multi-file programs
- [ ] Step-through debugger with breakpoints

## Author

**Pari Mittal**

## License

MIT. See [LICENSE](LICENSE).