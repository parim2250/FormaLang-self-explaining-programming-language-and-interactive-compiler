from app.compiler.pipeline import run_pipeline


def test_valid_program_passes_every_stage():
    r = run_pipeline("int x = 1; print(x);")
    assert [s.status for s in r.stages] == ["passed", "passed", "passed", "passed"]
    assert r.ok is True
    assert r.symbols[0]["name"] == "x"


def test_semantic_error_stops_before_interpreter():
    r = run_pipeline("print(y);")
    assert [s.status for s in r.stages] == ["passed", "passed", "failed", "skipped"]
    assert r.ok is False
    assert r.output == ["Stopped at the semantic analyzer. See Problems for details."]
    diag = r.diagnostics[0]
    assert (diag.stage, diag.code, diag.line, diag.col) == ("semantic", "E301", 1, 7)


def test_all_semantic_errors_are_reported():
    r = run_pipeline("print(y);\nprint(z);")
    assert [(d.code, d.line) for d in r.diagnostics] == [("E301", 1), ("E301", 2)]