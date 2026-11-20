from app.compiler.pipeline import run_pipeline


def out(source):
    r = run_pipeline(source)
    assert r.ok, r.diagnostics
    return r.output


def fails(source):
    r = run_pipeline(source)
    assert not r.ok
    failed = [s for s in r.stages if s.status == "failed"]
    assert len(failed) == 1
    assert len(r.diagnostics) == 1
    return r.diagnostics[0]

# ------------------------------------------------------------ output

def test_print_integer():
    assert out("print(42);") == ["42"]


def test_precedence():
    assert out("print(1 + 2 * 3);") == ["7"]


def test_integer_division_truncates_toward_zero():
    assert out("print(7 / 2);") == ["3"]
    assert out("print(-7 / 2);") == ["-3"]
    assert out("print(7 / -2);") == ["-3"]


def test_remainder_follows_dividend_sign():
    assert out("print(-7 % 3);") == ["-1"]
    assert out("print(7 % -3);") == ["1"]


def test_float_arithmetic_and_text():
    assert out("print(7.0 / 2);") == ["3.5"]
    assert out("print(1.0 + 2);") == ["3.0"]


def test_float_variable_accepts_int_and_prints_decimal():
    assert out("float v = 1; print(v);") == ["1.0"]


def test_string_concatenation_converts_other_operand():
    assert out('print("Step " + 1);') == ["Step 1"]
    assert out('print("v" + 1.5);') == ["v1.5"]
    assert out('print("ok" + true);') == ["oktrue"]
    assert out('print(1 + "x");') == ["1x"]


def test_comparisons_and_equality():
    assert out("print(1 < 2);") == ["true"]
    assert out("print(2.0 >= 3);") == ["false"]
    assert out("print(2 == 2.0);") == ["true"]
    assert out('print("a" != "b");') == ["true"]
    assert out("print(true == false);") == ["false"]


def test_logical_operators():
    assert out("print(true && !false);") == ["true"]
    assert out("print(false || false);") == ["false"]


def test_short_circuit_skips_right_side():
    assert out("print(false && (1 / 0) == 1);") == ["false"]
    assert out("print(true || (1 / 0) == 1);") == ["true"]


def test_variables_and_compound_assignment():
    assert out("int x = 1; x += 4; x *= 2; print(x);") == ["10"]
    assert out("int x = 5; x -= 2; x /= 2; print(x);") == ["1"]
    assert out("int x = 0; x++; x++; x--; print(x);") == ["1"]


def test_float_increment():
    assert out("float f = 1.5; f++; print(f);") == ["2.5"]


def test_default_values():
    assert out("int n; string s; bool b; float f; print(n); print(s); print(b); print(f);") == [
        "0", "", "false", "0.0",
    ]


def test_conversions():
    assert out("print(int(2.9));") == ["2"]
    assert out("print(int(-2.9));") == ["-2"]
    assert out("print(float(3));") == ["3.0"]
    assert out("print(string(1.5));") == ["1.5"]


def test_blocks_create_scopes():
    assert out("int x = 1; { int x = 2; print(x); } print(x);") == ["2", "1"]


def test_inner_block_assigns_outer_variable():
    assert out("int x = 1; { x = 5; } print(x);") == ["5"]


def test_output_before_error_is_kept():
    r = run_pipeline("print(1); print(1 / 0);")
    assert r.output == ["1", "Stopped at the interpreter. See Problems for details."]


# ------------------------------------------------------------ errors

def test_division_by_zero():
    d = fails("print(1 / 0);")
    assert (d.stage, d.code, d.line, d.col) == ("interpreter", "E501", 1, 7)


def test_undeclared_variable():
    assert fails("print(y);").code == "E301"


def test_redeclared_in_same_scope():
    assert fails("int x = 1; int x = 2;").code == "E302"


def test_float_to_int_needs_conversion():
    assert fails("int x = 1.5;").code == "E201"


def test_assigning_float_to_int_variable():
    assert fails("int x = 1; x = 2.5;").code == "E201"


def test_bool_in_arithmetic():
    assert fails("print(true + 1);").code == "E202"


def test_comparing_string_with_int():
    assert fails('print("a" == 1);').code == "E202"


def test_integer_overflow():
    assert fails("print(9223372036854775807 + 1);").code == "E502"


def test_print_needs_one_argument():
    assert fails("print();").code == "E204"


def test_void_cannot_be_stored():
    assert fails("int x = print(1);").code == "E201"


# ------------------------------------------------- later-phase constructs



def test_function_declaration_is_reported_as_phase_6():
    r = run_pipeline("int f() { return 1; }")
    assert r.stages[3].status == "not_implemented"
    assert "Phase 6" in r.stages[3].detail

def test_loops_are_reported_not_run():
    from app.compiler.interpreter import find_unsupported
    from app.compiler.lexer import tokenize
    from app.compiler.parser import parse

    tokens = tokenize("while (true) { break; }").tokens
    assert find_unsupported(parse(tokens).ast) is None


def test_unsupported_construct_runs_nothing():
    from app.compiler.pipeline import run_pipeline

    result = run_pipeline("void f() { }")
    assert not result.ok
    assert result.output == ["Not run yet: functions (Phase 6). Nothing was executed."]