from app.compiler.pipeline import run_pipeline


def test_valid_program_runs():
    r = run_pipeline("int x = 1;")
    assert [s.status for s in r.stages] == ["passed", "passed", "passed", "passed"]
    assert r.ok is True
    assert r.output == []
    assert r.ast["type"] == "Program"
    assert r.diagnostics == []


def test_syntax_error_stops_before_semantics():
    r = run_pipeline("int x = ;")
    assert [s.status for s in r.stages] == ["passed", "failed", "skipped", "skipped"]
    assert r.ast is None
    diag = r.diagnostics[0]
    assert (diag.stage, diag.code, diag.line, diag.col) == ("parser", "E401", 1, 9)


def test_lexer_error_still_skips_parser():
    r = run_pipeline("int x = 1 @;")
    assert r.stages[0].status == "failed"
    assert r.stages[1].status == "skipped"