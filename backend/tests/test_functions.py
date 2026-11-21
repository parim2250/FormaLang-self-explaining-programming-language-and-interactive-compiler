"""Phase 6 tests: functions, parameters, return, recursion, call stack in the trace."""

from app.compiler.pipeline import run_pipeline


def stage(result, name):
    return next(s for s in result.stages if s.name == name)


def codes(result):
    return [d.code for d in result.diagnostics]


def test_function_returns_value():
    result = run_pipeline("int add(int a, int b) { return a + b; } print(add(2, 3));")
    assert result.ok
    assert result.output == ["5"]


def test_call_may_precede_definition():
    result = run_pipeline("print(twice(4)); int twice(int n) { return n * 2; }")
    assert result.output == ["8"]


def test_void_function_runs_its_body():
    assert run_pipeline('void hello() { print("hi"); } hello();').output == ["hi"]


def test_bare_return_in_void_function():
    assert run_pipeline('void f() { return; } f(); print("ok");').output == ["ok"]


def test_early_return_skips_rest_of_body():
    source = (
        "int sign(int n) { if (n < 0) { return -1; } return 1; } "
        "print(sign(-5)); print(sign(5));"
    )
    assert run_pipeline(source).output == ["-1", "1"]


def test_recursion_factorial():
    source = (
        "int fact(int n) { if (n <= 1) { return 1; } return n * fact(n - 1); } "
        "print(fact(5));"
    )
    assert run_pipeline(source).output == ["120"]


def test_recursion_under_limit_works():
    source = "int down(int n) { if (n == 0) { return 0; } return down(n - 1); } print(down(150));"
    assert run_pipeline(source).output == ["0"]


def test_parameters_are_passed_by_value():
    source = "void change(int n) { n = 99; } int x = 1; change(x); print(x);"
    assert run_pipeline(source).output == ["1"]


def test_function_sees_globals_declared_before_it():
    source = "int g = 7; int get() { return g; } print(get());"
    assert run_pipeline(source).output == ["7"]


def test_function_cannot_see_callers_locals():
    source = "void show() { print(y); } void run() { int y = 2; show(); }"
    result = run_pipeline(source)
    assert not result.ok
    assert "E301" in codes(result)


def test_function_locals_do_not_leak_out():
    source = "void f() { int y = 2; } int y = 5; f(); print(y);"
    assert run_pipeline(source).output == ["5"]


def test_float_return_widens_int():
    assert run_pipeline("float f() { return 3; } print(f());").output == ["3.0"]


def test_int_argument_widens_to_float_parameter():
    assert run_pipeline("void show(float v) { print(v); } show(2);").output == ["2.0"]


def test_wrong_argument_count_is_semantic_error():
    result = run_pipeline("int f(int a) { return a; } print(f());")
    assert not result.ok
    assert stage(result, "Semantic analyzer").status == "failed"
    assert "E204" in codes(result)


def test_missing_return_is_semantic_error():
    result = run_pipeline("int f() { }")
    assert not result.ok
    assert "E206" in codes(result)


def test_break_outside_loop_inside_function_is_semantic_error():
    result = run_pipeline("void f() { break; }")
    assert not result.ok
    assert "E304" in codes(result)


def test_return_at_top_level_is_rejected():
    result = run_pipeline("return 1;")
    assert not result.ok


def test_infinite_recursion_hits_depth_limit():
    result = run_pipeline("int forever(int n) { return forever(n + 1); } print(forever(0));")
    assert not result.ok
    assert stage(result, "Interpreter").status == "failed"
    assert codes(result) == ["E503"]


def test_trace_records_call_and_return():
    result = run_pipeline("int add(int a, int b) { return a + b; } int r = add(1, 2);")
    call = next(s for s in result.trace if s["operation"] == "call add(1, 2)")
    assert call["call_stack"] == ["global", "add(1, 2)"]
    assert call["depth"] == 1
    ret = next(s for s in result.trace if s["operation"] == "return a + b")
    assert ret["result"] == "3 to caller"
    assert ret["depth"] == 1


def test_trace_depth_matches_recursion():
    source = (
        "int fact(int n) { if (n <= 1) { return 1; } return n * fact(n - 1); } "
        "print(fact(3));"
    )
    result = run_pipeline(source)
    assert max(s["depth"] for s in result.trace) == 3


def test_top_level_trace_steps_have_global_stack():
    result = run_pipeline("int x = 1;")
    assert result.trace[0]["call_stack"] == ["global"]
    assert result.trace[0]["depth"] == 0


def test_function_output_order_with_print_inside():
    source = 'void greet(string who) { print("Hello, " + who); } greet("FormaLang"); print("done");'
    assert run_pipeline(source).output == ["Hello, FormaLang", "done"]