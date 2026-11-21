# FormaLang

FormaLang is a small C-style teaching language with a compiler that explains itself.
Every stage of the compilation is visible in the browser:

Source → Lexer (DFA) → Parser (recursive descent, AST) → Semantic analyzer
(symbol table, type checks) → Interpreter (execution trace) → Output

An optional assistant, Forma Assistant, explains the compiler's results using Groq.
The compiler works fully without it.

## Quick start (Windows)

1. Install Python 3.12 from python.org. Tick "Add python.exe to PATH".
2. In the project folder, run `setup.bat`. It creates the virtual environment,
   installs the packages, runs the tests, and starts the server.
3. Open http://127.0.0.1:8000

After the first setup, run `run.bat` to start the server without the tests.

## The language

- Types: `int` (64-bit), `float` (double), `bool`, `string`, `void` (return type only)
- Statements: declarations, assignment (`=`, `+=`, `-=`, `*=`, `/=`), `++`, `--`,
  `if` / `else`, `while`, `for`, `break`, `continue`, `return`
- Functions: top level only, pass by value, recursion allowed
- Built-in: `print(x)`
- Conversions: `int(x)`, `float(x)`, `string(x)`, `bool(x)`
- Comments: `// line` and `/* block */`

The full definition is in `docs/LANGUAGE_SPEC.md`. Example programs are in `examples/`.

## Error codes

| Range | Stage | Examples |
|---|---|---|
| E1xx | Lexer | E101 unterminated string, E102 unexpected character |
| E2xx | Types | E201 type mismatch, E203 condition not bool, E206 missing return |
| E3xx | Scope | E301 undeclared name, E302 redeclared name, E304 break outside loop |
| E4xx | Syntax | E401 unexpected token, E402 missing token |
| E5xx | Runtime | E501 division by zero, E503 call depth, E504 step limit |

Each problem in the Problems list has a plain-language hint.

## Forma Assistant (optional)

1. Create a Groq API key.
2. Open `backend/.env` and set:
GROQ_API_KEY=your_key
GROQ_MODEL=openai/gpt-oss-120b

text

Use a model ID from your account's model list. Without `GROQ_MODEL`, the default
model in `backend/app/assistant.py` is used.
3. Restart the server. Run `run.bat` again.

The key stays on the server and is never sent to the browser. The assistant only
receives the compiler's data for the last run.

## Tests

Run `setup.bat`, or from `backend` run `.venv\Scripts\python.exe -m pytest`.
The suite covers the lexer, parser, semantic analyzer, interpreter, the trace,
functions, hints, the assistant (no network calls), and golden tests for every
program in `examples/`.

## Project layout
backend/
app/main.py FastAPI routes
app/assistant.py Forma Assistant (Groq)
app/compiler/ lexer, parser, semantic, interpreter, hints, pipeline
tests/ pytest suite
frontend/
index.html, css/, js/ browser UI (CodeMirror 6)
examples/ example programs and expected results
docs/LANGUAGE_SPEC.md language definition

text


## Demo script

1. Open the page and click **Examples → Hello**. Run it.
2. Open **Language tour**. Run it. Show the greeting and the three steps.
3. Open **Types and conversion**. Point out that `float` values print with `.0`
   when whole, and that `int(total)` is needed to go from float to int.
4. Open **Functions and recursion**. Open "Show how it works", then the Execution
   tab. Show the call stack growing and shrinking.
5. Open **Type error**. Run it. Show E201 in Problems, the hint, and the cursor jump.
6. Open the Assistant panel and click **Explain error** (with a key set).