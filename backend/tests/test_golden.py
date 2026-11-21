"""Phase 10 golden tests: every program in examples/ must match its recorded result."""

import json
from pathlib import Path

import pytest

from app.compiler.pipeline import run_pipeline

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"
EXPECTED = json.loads((EXAMPLES_DIR / "expected.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_matches_golden(name):
    source = (EXAMPLES_DIR / f"{name}.fl").read_text(encoding="utf-8")
    data = run_pipeline(source).to_dict()
    expected = EXPECTED[name]
    assert data["ok"] is expected["ok"]
    assert data["output"] == expected["output"]
    assert [d["code"] for d in data["diagnostics"]] == expected["codes"]


def test_every_example_file_has_a_golden_entry():
    files = {path.stem for path in EXAMPLES_DIR.glob("*.fl")}
    assert files == set(EXPECTED)