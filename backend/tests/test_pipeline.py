from app.compiler.pipeline import run_pipeline


def test_valid_program_passes_lexer():
    r = run_pipeline("int x = 1;")
    assert r.stages[0].status == "passed"
    assert r.stages[0].detail == "5 tokens"
    assert r.diagnostics == []
    assert r.tokens[-1]["kind"] == "EOF"
    assert r.stages[1].status == "passed"
    assert r.stages[2].status == "passed"
    assert r.stages[3].status == "passed"
def test_lexer_error_stops_the_pipeline():
    r = run_pipeline("int x = 1 @;")
    assert r.stages[0].status == "failed"
    assert r.diagnostics[0].code == "E102"
    assert r.diagnostics[0].stage == "lexer"
    assert all(s.status == "skipped" for s in r.stages[1:])
    assert r.ok is False


def test_empty_source_has_only_eof():
    r = run_pipeline("")
    assert r.stages[0].status == "passed"
    assert [t["kind"] for t in r.tokens] == ["EOF"]