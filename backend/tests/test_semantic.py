from app.compiler.lexer import tokenize
from app.compiler.parser import parse
from app.compiler.semantic import analyze

EXAMPLE = '''string greet(string name) { return "Hello, " + name + "!"; }
string language = "FormaLang";
float version = 1.0;
// float version = "1.0";
print(greet(language));
for (int i = 1; i <= 3; i++) { print("Step " + i); }
'''


def check(source):
    lexed = tokenize(source)
    assert lexed.errors == []
    parsed = parse(lexed.tokens)
    assert parsed.errors == []
    return analyze(parsed.ast)


def codes(source):
    return [e.code for e in check(source).errors]


# ------------------------------------------------------------ valid programs

def test_valid_program_has_no_errors():
    assert codes("int x = 1; float y = x; print(y);") == []


def test_spec_example_has_no_errors():
    assert codes(EXAMPLE) == []


def test_shadowing_in_inner_block_is_allowed():
    assert codes("int x = 1; { int x = 2; }") == []


def test_string_concatenation_is_allowed():
    assert codes('print("Step " + 1 + true);') == []


def test_continue_inside_loop_is_allowed():
    assert codes("while (true) { continue; }") == []


def test_call_before_definition_is_allowed():
    assert codes("print(add(1, 2)); int add(int a, int b) { return a + b; }") == []


def test_function_call_with_correct_arguments():
    assert codes("int add(int a, int b) { return a + b; } print(add(1, 2));") == []


def test_int_argument_widens_to_float_parameter():
    assert codes("float f(float a) { return a; } print(f(1));") == []


def test_if_else_both_return_satisfies_return_rule():
    assert codes("int f(bool b) { if (b) { return 1; } else { return 2; } }") == []


def test_while_true_with_return_satisfies_return_rule():
    assert codes("int f() { while (true) { return 1; } }") == []


# ------------------------------------------------------------ scope errors

def test_undeclared_variable():
    assert codes("print(y);") == ["E301"]


def test_redeclared_in_same_scope():
    assert codes("int x = 1; int x = 2;") == ["E302"]


def test_block_variable_is_not_visible_outside():
    assert codes("{ int y = 1; } print(y);") == ["E301"]


def test_declare_before_use():
    assert codes("print(x); int x = 1;") == ["E301"]


def test_variable_cannot_use_itself_in_its_initializer():
    assert codes("int x = x;") == ["E301"]


def test_break_outside_loop():
    assert codes("break;") == ["E304"]


def test_continue_outside_loop():
    assert codes("int x = 1; continue;") == ["E304"]


def test_return_at_top_level():
    assert codes("return 1;") == ["E305"]


def test_undefined_function():
    assert codes("print(f());") == ["E303"]


def test_duplicate_function():
    assert codes("int f() { return 1; } int f() { return 2; }") == ["E302"]


def test_print_cannot_be_redefined():
    assert codes("void print(int a) { }") == ["E302"]


def test_duplicate_parameter():
    assert codes("int f(int a, int a) { return a; }") == ["E302"]


def test_void_parameter():
    assert codes("void f(void x) { }") == ["E201"]


def test_parameter_clashes_with_body_declaration():
    assert codes("int f(int a) { int a = 1; return a; }") == ["E302"]


# ------------------------------------------------------------ type errors

def test_float_to_int_declaration():
    result = check("int x = 1.5;")
    assert [e.code for e in result.errors] == ["E201"]
    assert "int(...)" in result.errors[0].message


def test_assignment_type_mismatch():
    assert codes("int x = 1; x = 2.5;") == ["E201"]


def test_compound_assignment_result_must_fit():
    assert codes("int x = 1; x += 1.5;") == ["E201"]


def test_bool_in_arithmetic():
    assert codes("print(true + 1);") == ["E202"]


def test_comparing_string_with_int():
    assert codes('print("a" == 1);') == ["E202"]


def test_float_modulo():
    assert codes("print(5.0 % 2);") == ["E202"]


def test_not_on_int():
    assert codes("print(!5);") == ["E202"]


def test_and_on_int():
    assert codes("print(1 && true);") == ["E202"]


def test_void_stored_in_variable():
    assert codes("int x = print(1);") == ["E201"]


def test_print_with_no_arguments():
    assert codes("print();") == ["E204"]


def test_print_with_two_arguments():
    assert codes("print(1, 2);") == ["E204"]


def test_printing_a_void_value():
    assert codes("print(print(1));") == ["E202"]


def test_if_condition_must_be_bool():
    assert codes("if (1) { }") == ["E203"]


def test_while_condition_must_be_bool():
    assert codes('while ("a") { }') == ["E203"]


def test_argument_count_mismatch():
    assert codes("int f(int a) { return a; } print(f());") == ["E204"]


def test_argument_type_mismatch():
    assert codes('int f(int a) { return a; } print(f("x"));') == ["E205"]


def test_return_type_mismatch():
    assert codes("int f() { return 1.5; }") == ["E206"]


def test_missing_return():
    assert codes("int f() { int x = 1; }") == ["E206"]


def test_void_function_returning_a_value():
    assert codes("void f() { return 1; }") == ["E206"]


def test_break_defeats_while_true_return_rule():
    assert codes("int f() { while (true) { break; } }") == ["E206"]


# ------------------------------------------------------------ recovery

def test_multiple_errors_are_all_reported():
    assert codes("print(y);\nprint(z);") == ["E301", "E301"]


def test_failed_declaration_still_declares_the_name():
    # the bad initializer is reported once; later uses of x do not add errors
    assert codes('int x = "a"; print(x + 1);') == ["E201"]


def test_unknown_value_does_not_cascade():
    assert codes("if (y) { }") == ["E301"]


# ------------------------------------------------------------ symbol table

def test_symbols_record_declared_and_inferred_types():
    symbols = {s["name"]: s for s in check("int x = 1; float y = 2; string s;").symbols}
    assert symbols["x"]["declared_type"] == "int"
    assert symbols["x"]["inferred_type"] == "int"
    assert symbols["y"]["declared_type"] == "float"
    assert symbols["y"]["inferred_type"] == "int"
    assert symbols["s"]["inferred_type"] == "string"
    assert symbols["x"]["scope"] == "global"


def test_symbols_record_function_scopes():
    symbols = {s["name"]: s for s in check("int f(int a) { int b = a; }").symbols}
    assert symbols["f"]["kind"] == "function"
    assert symbols["f"]["declared_type"] == "(int a) -> int"
    assert symbols["a"]["kind"] == "parameter"
    assert symbols["a"]["scope"] == "function f"
    assert symbols["b"]["scope"] == "function f"


def test_block_symbols_are_labelled_block():
    (sym,) = check("{ int x = 1; }").symbols
    assert sym["scope"] == "block"