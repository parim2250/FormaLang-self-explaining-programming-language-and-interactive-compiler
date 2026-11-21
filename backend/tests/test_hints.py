"""Phase 8 tests: hints attached to problems."""

from app.compiler.hints import HINTS, hint_for
from app.compiler.pipeline import run_pipeline


def test_unknown_code_has_no_hint():
    assert hint_for("E999") == ""


def test_every_hint_is_a_nonempty_sentence():
    for code, text in HINTS.items():
        assert len(code) == 4 and code.startswith("E")
        assert text.strip()


def test_undeclared_problem_carries_hint():
    data = run_pipeline("int x = 1; print(y);").to_dict()
    problem = data["diagnostics"][0]
    assert problem["code"] == "E301"
    assert problem["hint"].startswith("Declare the variable")


def test_hint_does_not_replace_message():
    problem = run_pipeline("int x = 1; x = 2.5;").to_dict()["diagnostics"][0]
    assert problem["code"] == "E201"
    assert problem["message"]
    assert problem["hint"].startswith("Check the types")


def test_runtime_problem_carries_hint():
    problem = run_pipeline("print(1 / 0);").to_dict()["diagnostics"][0]
    assert problem["code"] == "E501"
    assert problem["hint"]


def test_passing_run_has_no_diagnostics():
    assert run_pipeline("int x = 1;").to_dict()["diagnostics"] == []