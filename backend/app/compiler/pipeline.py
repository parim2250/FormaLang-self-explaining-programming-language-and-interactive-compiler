"""Runs every compiler stage in order and returns one structured result.

Contract fields may gain new keys in later phases but are never renamed or removed.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from app.compiler.hints import hint_for
from app.compiler.interpreter import Interpreter, RunError, find_unsupported
from app.compiler.lexer import tokenize
from app.compiler.parser import count_nodes, parse
from app.compiler.semantic import analyze

VERSION = "0.1.0"
STAGE_NAMES = ["Lexer", "Parser", "Semantic analyzer", "Interpreter"]


@dataclass
class Diagnostic:
    stage: str
    code: str
    message: str
    line: int
    col: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "code": self.code,
            "message": self.message,
            "line": self.line,
            "col": self.col,
            "hint": hint_for(self.code),
        }


@dataclass
class StageStatus:
    name: str
    status: str
    time_ms: float = 0.0
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "time_ms": round(self.time_ms, 3),
            "detail": self.detail,
        }


def _token_dict(token: Any) -> dict[str, Any]:
    if isinstance(token, dict):
        return token
    to_dict = getattr(token, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    return asdict(token)


def _as_dict(item: Any) -> dict[str, Any]:
    """Accept either a plain dict or an object with to_dict()."""
    if isinstance(item, dict):
        return item
    return item.to_dict()


def _field(item: Any, key: str) -> Any:
    """Read a field from either a dict or an object."""
    if isinstance(item, dict):
        return item[key]
    return getattr(item, key)


def _diagnostics(stage: str, items: list[Any]) -> list[Diagnostic]:
    return [
        Diagnostic(
            stage,
            _field(item, "code"),
            _field(item, "message"),
            _field(item, "line"),
            _field(item, "col"),
        )
        for item in items
    ]


@dataclass
class CompileResult:
    ok: bool
    output: list[str]
    diagnostics: list[Diagnostic]
    stages: list[StageStatus]
    tokens: list[dict[str, Any]]
    ast: dict | None
    symbols: list[dict]
    trace: list[dict]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "output": self.output,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "stages": [s.to_dict() for s in self.stages],
            "tokens": list(self.tokens),
            "ast": self.ast,
            "symbols": self.symbols,
            "trace": self.trace,
        }


def _timed(index: int, status: str, started: float, detail: str = "") -> StageStatus:
    elapsed_ms = (time.perf_counter() - started) * 1000
    return StageStatus(STAGE_NAMES[index], status, elapsed_ms, detail)


def run_pipeline(source: str) -> CompileResult:
    diagnostics: list[Diagnostic] = []
    stages: list[StageStatus] = []
    symbols: list[dict] = []
    trace: list[dict] = []

    def skip_from(index: int) -> None:
        for name in STAGE_NAMES[index:]:
            stages.append(StageStatus(name, "skipped"))

    # 1. Lexer
    started = time.perf_counter()
    lexed = tokenize(source)
    token_dicts = [_token_dict(t) for t in lexed.tokens]
    if lexed.errors:
        stages.append(_timed(0, "failed", started, f"{len(lexed.errors)} error(s)"))
        diagnostics.extend(_diagnostics("lexer", lexed.errors))
        skip_from(1)
        return CompileResult(
            False,
            ["Stopped at the lexer. See Problems for details."],
            diagnostics, stages, token_dicts, None, symbols, trace,
        )
    token_count = sum(1 for t in lexed.tokens if t.kind != "EOF")
    stages.append(_timed(0, "passed", started, f"{token_count} tokens"))

    # 2. Parser
    started = time.perf_counter()
    parsed = parse(lexed.tokens)
    if parsed.errors:
        stages.append(_timed(1, "failed", started, f"{len(parsed.errors)} error(s)"))
        diagnostics.extend(_diagnostics("parser", parsed.errors))
        skip_from(2)
        return CompileResult(
            False,
            ["Stopped at the parser. See Problems for details."],
            diagnostics, stages, token_dicts, None, symbols, trace,
        )
    ast = parsed.ast
    stages.append(_timed(1, "passed", started, f"{count_nodes(ast)} AST nodes"))

    # 3. Semantic analyzer
    started = time.perf_counter()
    analysis = analyze(ast)
    symbols = [_as_dict(s) for s in analysis.symbols]
    if analysis.errors:
        stages.append(_timed(2, "failed", started, f"{len(analysis.errors)} error(s)"))
        diagnostics.extend(_diagnostics("semantic", analysis.errors))
        skip_from(3)
        return CompileResult(
            False,
            ["Stopped at the semantic analyzer. See Problems for details."],
            diagnostics, stages, token_dicts, ast, symbols, trace,
        )
    stages.append(_timed(2, "passed", started, f"{len(symbols)} symbol(s), no errors"))

    # 4. Interpreter
    started = time.perf_counter()
    unsupported = find_unsupported(ast)
    if unsupported is not None:
        feature, phase, _node = unsupported
        stages.append(_timed(3, "not_implemented", started, f"{feature} · Phase {phase}"))
        return CompileResult(
            False,
            [f"Not run yet: {feature} (Phase {phase}). Nothing was executed."],
            diagnostics, stages, token_dicts, ast, symbols, trace,
        )

    interpreter = Interpreter()
    try:
        interpreter.run(ast)
    except RunError as error:
        stages.append(_timed(3, "failed", started, "1 error(s)"))
        diagnostics.append(
            Diagnostic("interpreter", error.code, error.message, error.line, error.col)
        )
        output = list(interpreter.output) + ["Stopped at the interpreter. See Problems for details."]
        return CompileResult(
            False, output, diagnostics, stages, token_dicts, ast, symbols, interpreter.trace,
        )

    stages.append(_timed(3, "passed", started, f"{len(interpreter.output)} line(s) printed"))
    return CompileResult(
        True, list(interpreter.output), diagnostics, stages, token_dicts, ast, symbols,
        interpreter.trace,
    )