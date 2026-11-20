"""
FormaLang pipeline entry point.

CONTRACT (frozen from Phase 0):
  CompileResult fields may be ADDED in later phases, never renamed or removed.
  The UI reads only these fields, so earlier UI code keeps working.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

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
    """Phase 0 stub. Each later phase replaces one stage with real logic."""
    result = CompileResult(ok=False)
    result.stages = [StageStatus(name=n, status="not_implemented") for n in STAGE_NAMES]
    result.output = ["FormaLang compiler is not wired up yet (Phase 0 shell)."]
    return result