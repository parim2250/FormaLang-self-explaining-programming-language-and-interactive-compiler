"""Phase 5 tests: if/else, while, for, break/continue, step limit, execution trace."""

from app.compiler.interpreter import TRACE_LIMIT, find_unsupported
from app.compiler.lexer import tokenize
from app.compiler.parser import parse
from app.compiler.pipeline import run_pipeline


def stage(result, name):
    return next(s for s in result.stages if s.name == name)


def codes(result):
    return [d.code for d in result.diagnostics]


def test_if_runs_then_branch():
    result = run_pipeline('int x = 1; if (x == 1) { print("yes"); } else { print("no"); }')
    assert result.ok
    assert result.output == ["yes"]


def test_if_runs_else_branch():
    result = run_pipeline('int x = 2; if (x == 1) { print("yes"); } else { print("no"); }')
    assert result.output == ["no"]


def test_if_without_else_skips_when_false():
    result = run_pipeline('int x = 2; if (x == 1) { print("yes"); } print("done");')
    assert result.output == ["done"]


def test_else_if_chain():
    source = (
        'int x = 2; if (x == 1) { print("one"); } '
        'else if (x == 2) { print("two"); } else { print("other"); }'
    )
    assert run_pipeline(source).output == ["two"]


def test_while_counts_up():
    result = run_pipeline("int i = 0; while (i < 3) { print(i); i++; }")
    assert result.ok
    assert result.output == ["0", "1", "2"]


def test_while_false_never_runs_body():
    result = run_pipeline('while (false) { print("never"); }')
    assert result.ok
    assert result.output == []


def test_break_exits_while():
    source = "int i = 0; while (true) { if (i == 2) { break; } print(i); i++; }"
    assert run_pipeline(source).output == ["0", "1"]


def test_continue_skips_rest_of_body():
    source = "for (int i = 0; i < 5; i++) { if (i == 2) { continue; } print(i); }"
    assert run_pipeline(source).output == ["0", "1", "3", "4"]


def test_for_loop_matches_spec_example():
    source = 'for (int i = 1; i <= 3; i++) { print("Step " + i); }'
    assert run_pipeline(source).output == ["Step 1", "Step 2", "Step 3"]


def test_nested_loops():
    source = (
        "for (int i = 0; i < 2; i++) { "
        "for (int j = 0; j < 2; j++) { print(i * 10 + j); } }"
    )
    assert run_pipeline(source).output == ["0", "1", "10", "11"]


def test_loop_variable_is_gone_after_loop():
    source = "for (int i = 0; i < 1; i++) { } int i = 5; print(i);"
    result = run_pipeline(source)
    assert result.ok
    assert result.output == ["5"]


def test_while_with_compound_assignment():
    source = "int n = 10; int c = 0; while (n > 0) { n -= 3; c++; } print(c);"
    assert run_pipeline(source).output == ["4"]


def test_non_bool_condition_is_a_semantic_error():
    result = run_pipeline("int x = 1; while (x) { }")
    assert not result.ok
    assert stage(result, "Semantic analyzer").status == "failed"
    assert "E203" in codes(result)


def test_infinite_loop_hits_step_limit():
    result = run_pipeline("while (true) { }")
    assert not result.ok
    assert stage(result, "Interpreter").status == "failed"
    assert codes(result) == ["E504"]


def test_trace_records_declarations_and_assignments():
    result = run_pipeline("int x = 1; x += 2;")
    assert [s["operation"] for s in result.trace] == ["declare int x = 1", "x += 2"]
    assert [s["result"] for s in result.trace] == ["x = 1", "x = 3"]
    assert [s["step"] for s in result.trace] == [1, 2]


def test_trace_snapshots_variables():
    result = run_pipeline("int x = 1; x += 2;")
    assert result.trace[1]["variables"] == [{"name": "x", "type": "int", "value": "3"}]


def test_trace_records_if_condition_and_print():
    result = run_pipeline("int x = 1; if (x == 1) { print(x); }")
    operations = [s["operation"] for s in result.trace]
    assert "if (x == 1)" in operations
    assert "print(x)" in operations


def test_trace_is_capped_and_program_still_finishes():
    result = run_pipeline("int i = 0; while (i < 1000) { i++; }")
    assert result.ok
    assert len(result.trace) == TRACE_LIMIT + 1
    assert result.trace[-1]["operation"].startswith("Trace limit")


def test_control_flow_has_no_unsupported_features():
    tokens = tokenize("while (true) { break; }").tokens
    assert find_unsupported(parse(tokens).ast) is None


def test_interpreter_detail_counts_lines():
    result = run_pipeline("int x = 1; print(x);")
    assert stage(result, "Interpreter").detail == "1 line(s) printed"