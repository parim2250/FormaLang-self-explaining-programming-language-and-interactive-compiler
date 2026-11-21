"""Phase 10 tests: every error code the compiler can emit has a hint."""

import re
from pathlib import Path

from app.compiler.hints import HINTS

COMPILER_DIR = Path(__file__).resolve().parents[1] / "app" / "compiler"


def codes_in_compiler() -> set[str]:
    found: set[str] = set()
    for path in COMPILER_DIR.glob("*.py"):
        if path.name == "hints.py":
            continue
        found |= set(re.findall(r'"(E\d{3})"', path.read_text(encoding="utf-8")))
    return found


def test_every_error_code_in_compiler_has_a_hint():
    missing = sorted(codes_in_compiler() - set(HINTS))
    assert missing == [], f"Codes without a hint: {missing}"