"""Pipeline: runs the compiler stages in order and collects one CompileResult.

Contract: fields may be added, never renamed or removed.
Diagnostic.stage uses lowercase stage keys: "lexer", "parser", "semantic", "interpreter".
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

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


@dataclass
class StageStatus:
    name: str
    status: str  # pending | passed | failed | skipped | not_implemented
    time_ms: float = 0.0
    detail: str = ""


@dataclass
class CompileResult:
    ok: bool
    output: list[str]
    diagnostics: list[Diagnostic]
    stages: list[StageStatus]
    tokens: list[dict]
    ast: dict | None
    symbols: list[dict]
    trace: list[dict]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "output": self.output,
            "diagnostics": [asdict(d) for d in self.diagnostics],
            "stages": [asdict(s) for s in self.stages],
            "tokens": self.tokens,
            "ast": self.ast,
            "symbols": self.symbols,
            "trace": self.trace,
        }


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 2)


def _skipped(name: str) -> StageStatus:
    return StageStatus(name, "skipped")


def run_pipeline(source: str) -> CompileResult:
    # Stage 1: lexer
    started = time.perf_counter()
    lexed = tokenize(source)
    tokens_out = [asdict(t) for t in lexed.tokens]
    token_count = len(lexed.tokens) - 1  # the EOF token is not counted
    diagnostics = [Diagnostic("lexer", e.code, e.message, e.line, e.col) for e in lexed.errors]

    if lexed.errors:
        stages = [
            StageStatus("Lexer", "failed", _ms(started), f"{len(lexed.errors)} error(s)"),
            _skipped("Parser"),
            _skipped("Semantic analyzer"),
            _skipped("Interpreter"),
        ]
        return CompileResult(
            False,
            ["Stopped at the lexer. See Problems for details."],
            diagnostics, stages, tokens_out, None, [], [],
        )

    lexer_stage = StageStatus("Lexer", "passed", _ms(started), f"{token_count} tokens")

    # Stage 2: parser
    started = time.perf_counter()
    parsed = parse(lexed.tokens)
    diagnostics += [Diagnostic("parser", e.code, e.message, e.line, e.col) for e in parsed.errors]

    if parsed.errors:
        stages = [
            lexer_stage,
            StageStatus("Parser", "failed", _ms(started), f"{len(parsed.errors)} error(s)"),
            _skipped("Semantic analyzer"),
            _skipped("Interpreter"),
        ]
        return CompileResult(
            False,
            ["Stopped at the parser. See Problems for details."],
            diagnostics, stages, tokens_out, None, [], [],
        )

    nodes = count_nodes(parsed.ast)
    parser_stage = StageStatus("Parser", "passed", _ms(started), f"{nodes} AST nodes")

    # Stage 3: semantic analysis. Every error is reported before anything runs.
    started = time.perf_counter()
    checked = analyze(parsed.ast)
    diagnostics += [Diagnostic("semantic", e.code, e.message, e.line, e.col) for e in checked.errors]

    if checked.errors:
        stages = [
            lexer_stage,
            parser_stage,
            StageStatus("Semantic analyzer", "failed", _ms(started), f"{len(checked.errors)} error(s)"),
            _skipped("Interpreter"),
        ]
        return CompileResult(
            False,
            ["Stopped at the semantic analyzer. See Problems for details."],
            diagnostics, stages, tokens_out, parsed.ast, checked.symbols, [],
        )

    semantic_stage = StageStatus(
        "Semantic analyzer", "passed", _ms(started), f"{len(checked.symbols)} symbol(s), no errors"
    )

    # Stage 4: interpreter. Constructs from later phases are found before anything runs.
    started = time.perf_counter()
    blocked = find_unsupported(parsed.ast)
    if blocked is not None:
        feature, phase, _where = blocked
        stages = [
            lexer_stage,
            parser_stage,
            semantic_stage,
            StageStatus("Interpreter", "not_implemented", 0.0, f"{feature} · Phase {phase}"),
        ]
        output = [f"Not run yet: {feature} (Phase {phase}). Nothing was executed."]
        return CompileResult(False, output, [], stages, tokens_out, parsed.ast, checked.symbols, [])

    interp = Interpreter()
    try:
        interp.run(parsed.ast)
    except RunError as err:
        diagnostics.append(Diagnostic("interpreter", err.code, err.message, err.line, err.col))
        stages = [
            lexer_stage,
            parser_stage,
            semantic_stage,
            StageStatus("Interpreter", "failed", _ms(started), "1 error(s)"),
        ]
        output = interp.output + ["Stopped at the interpreter. See Problems for details."]
        return CompileResult(False, output, diagnostics, stages, tokens_out, parsed.ast, checked.symbols, [])

    stages = [
        lexer_stage,
        parser_stage,
        semantic_stage,
        StageStatus("Interpreter", "passed", _ms(started), f"{len(interp.output)} line(s) printed"),
    ]
    return CompileResult(True, interp.output, [], stages, tokens_out, parsed.ast, checked.symbols, [])