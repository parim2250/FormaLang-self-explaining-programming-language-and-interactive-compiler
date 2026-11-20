"""
FormaLang pipeline entry point.

CONTRACT (frozen from Phase 0):
  CompileResult fields may be ADDED in later phases, never renamed or removed.
  StageStatus may gain fields too (Phase 1 added `detail`).
  The UI reads only these fields, so earlier UI code keeps working.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

from app.compiler.lexer import tokenize

VERSION = "0.1.0"
STAGE_NAMES = ["Lexer", "Parser", "Semantic analyzer", "Interpreter"]


@dataclass
class Diagnostic:
    stage: str      # lexer | parser | semantic | runtime
    code: str       # E1xx lexer, E2xx types, E3xx scope, E4xx syntax, E5xx runtime
    message: str
    line: int
    col: int


@dataclass
class StageStatus:
    name: str
    status: str     # pending | passed | failed | skipped | not_implemented
    time_ms: float = 0.0
    detail: str = ""  # short summary shown on the stage card (Phase 1+)


@dataclass
class CompileResult:
    ok: bool = False
    output: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    stages: list[StageStatus] = field(default_factory=list)
    tokens: list[dict[str, Any]] = field(default_factory=list)    # Phase 1+
    ast: dict[str, Any] | None = None                             # Phase 2+
    symbols: list[dict[str, Any]] = field(default_factory=list)   # Phase 4+
    trace: list[dict[str, Any]] = field(default_factory=list)     # Phase 5+

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_pipeline(source: str) -> CompileResult:
    result = CompileResult(ok=False)

    t0 = time.perf_counter()
    lexed = tokenize(source)
    lex_ms = round((time.perf_counter() - t0) * 1000, 2)

    result.tokens = [tok.to_dict() for tok in lexed.tokens]
    result.diagnostics = [
        Diagnostic(stage="lexer", code=e.code, message=e.message, line=e.line, col=e.col)
        for e in lexed.errors
    ]
    token_count = len(lexed.tokens) - 1  # exclude EOF

    if lexed.errors:
        # a lexer error stops the pipeline; later stages cannot run on a broken stream
        result.stages = [
            StageStatus("Lexer", "failed", lex_ms, f"{len(lexed.errors)} error(s)"),
            StageStatus("Parser", "skipped"),
            StageStatus("Semantic analyzer", "skipped"),
            StageStatus("Interpreter", "skipped"),
        ]
        result.output = ["Stopped at the lexer. See Problems for details."]
        return result

    result.stages = [
        StageStatus("Lexer", "passed", lex_ms, f"{token_count} tokens"),
        StageStatus("Parser", "not_implemented"),
        StageStatus("Semantic analyzer", "not_implemented"),
        StageStatus("Interpreter", "not_implemented"),
    ]
    result.output = [
        f"Lexer: {token_count} tokens, no lexical errors.",
        "Parser is not wired up yet (Phase 2), so the program was not executed.",
    ]
    return result