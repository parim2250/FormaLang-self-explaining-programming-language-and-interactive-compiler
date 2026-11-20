"""Pipeline: runs the compiler stages in order and collects one CompileResult.

Contract: fields may be added, never renamed or removed.
Diagnostic.stage uses lowercase stage keys: "lexer", "parser".
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from app.compiler.lexer import tokenize
from app.compiler.parser import count_nodes, parse

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


def _not_implemented(name: str) -> StageStatus:
    return StageStatus(name, "not_implemented")


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
    stages = [
        lexer_stage,
        StageStatus("Parser", "passed", _ms(started), f"{nodes} AST nodes"),
        _not_implemented("Semantic analyzer"),
        _not_implemented("Interpreter"),
    ]
    output = [
        f"Lexer: {token_count} tokens, no lexical errors.",
        f"Parser: {nodes} AST nodes, no syntax errors.",
        "Semantic analysis and execution are not wired up yet (Phase 3), so the program was not run.",
    ]
    return CompileResult(False, output, [], stages, tokens_out, parsed.ast, [], [])