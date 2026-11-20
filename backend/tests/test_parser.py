from app.compiler.lexer import tokenize
from app.compiler.parser import parse

EXAMPLE = '''string greet(string name) { return "Hello, " + name + "!"; }
string language = "FormaLang";
float version = 1.0;
print(greet(language));
for (int i = 1; i <= 3; i++) { print("Step " + i); }
'''


def parse_src(source):
    lexed = tokenize(source)
    assert lexed.errors == []
    return parse(lexed.tokens)


def body_of(source):
    result = parse_src(source)
    assert result.errors == []
    return result.ast["body"]


def test_empty_source_gives_empty_program():
    result = parse_src("")
    assert result.errors == []
    assert result.ast == {"type": "Program", "line": 1, "col": 1, "body": []}


def test_var_decl_with_literal():
    (decl,) = body_of("int x = 1;")
    assert decl["type"] == "VarDecl"
    assert decl["var_type"] == "int"
    assert decl["name"] == "x"
    assert decl["init"]["type"] == "Literal"
    assert decl["init"]["value"] == 1


def test_positions_are_recorded():
    (decl,) = body_of("int x = 1;")
    assert (decl["line"], decl["col"]) == (1, 1)
    assert (decl["init"]["line"], decl["init"]["col"]) == (1, 9)


def test_multiplication_binds_tighter_than_addition():
    (decl,) = body_of("int r = 1 + 2 * 3;")
    assert decl["init"]["op"] == "+"
    assert decl["init"]["right"]["op"] == "*"


def test_subtraction_is_left_associative():
    (decl,) = body_of("int r = 10 - 4 - 3;")
    assert decl["init"]["op"] == "-"
    assert decl["init"]["left"]["op"] == "-"
    assert decl["init"]["right"]["value"] == 3


def test_unary_minus():
    (decl,) = body_of("int n = -5;")
    assert decl["init"]["type"] == "Unary"
    assert decl["init"]["op"] == "-"
    assert decl["init"]["operand"]["value"] == 5


def test_logical_and_binds_looser_than_comparison():
    (decl,) = body_of("bool ok = a < c && d;")
    assert decl["init"]["op"] == "&&"
    assert decl["init"]["left"]["op"] == "<"


def test_function_declaration_with_params():
    (func,) = body_of("int add(int a, int b) { return a + b; }")
    assert func["type"] == "FuncDecl"
    assert func["name"] == "add"
    assert func["return_type"] == "int"
    assert [p["name"] for p in func["params"]] == ["a", "b"]
    ret = func["body"]["body"][0]
    assert ret["type"] == "Return"
    assert ret["value"]["op"] == "+"


def test_call_with_arguments():
    (stmt,) = body_of("print(add(1, 2));")
    assert stmt["type"] == "ExprStmt"
    call = stmt["expr"]
    assert call["type"] == "Call" and call["name"] == "print"
    assert call["args"][0]["name"] == "add"
    assert len(call["args"][0]["args"]) == 2


def test_conversion_expression():
    (decl,) = body_of("float f = float(3);")
    assert decl["init"]["type"] == "Convert"
    assert decl["init"]["target_type"] == "float"
    assert decl["init"]["expr"]["value"] == 3


def test_if_else_if_else():
    (stmt,) = body_of("if (a) { } else if (b) { } else { }")
    assert stmt["type"] == "If"
    assert stmt["otherwise"]["type"] == "If"
    assert stmt["otherwise"]["otherwise"]["type"] == "Block"


def test_while_loop():
    (stmt,) = body_of("while (i < 3) { i++; }")
    assert stmt["type"] == "While"
    assert stmt["body"]["body"][0]["type"] == "Assign"
    assert stmt["body"]["body"][0]["op"] == "++"


def test_for_loop_with_declaration_and_increment():
    (stmt,) = body_of("for (int i = 0; i < 3; i++) { print(i); }")
    assert stmt["type"] == "For"
    assert stmt["init"]["type"] == "VarDecl"
    assert stmt["cond"]["op"] == "<"
    assert stmt["step"]["op"] == "++"
    assert stmt["step"]["value"] is None
    assert stmt["body"]["body"][0]["type"] == "ExprStmt"


def test_compound_assignment():
    (stmt,) = body_of("x += 2;")
    assert stmt["type"] == "Assign"
    assert stmt["op"] == "+="
    assert stmt["value"]["value"] == 2


def test_return_break_continue():
    (func,) = body_of("int f() { while (true) { continue; } return; }")
    loop, ret = func["body"]["body"]
    assert loop["body"]["body"][0]["type"] == "Continue"
    assert ret["type"] == "Return" and ret["value"] is None


def test_spec_example_parses_cleanly():
    body = body_of(EXAMPLE)
    assert [n["type"] for n in body] == ["FuncDecl", "VarDecl", "VarDecl", "ExprStmt", "For"]


def test_missing_semicolon_points_after_previous_token():
    result = parse_src("int x = 1")
    assert len(result.errors) == 1
    err = result.errors[0]
    assert (err.code, err.line, err.col) == ("E402", 1, 10)
    assert "';'" in err.message


def test_missing_close_paren_is_E402():
    result = parse_src('print("hi";')
    assert len(result.errors) == 1
    err = result.errors[0]
    assert err.code == "E402"
    assert (err.line, err.col) == (1, 11)


def test_missing_expression_is_E401():
    result = parse_src("int x = ;")
    assert len(result.errors) == 1
    err = result.errors[0]
    assert (err.code, err.line, err.col) == ("E401", 1, 9)
    assert "expected an expression" in err.message


def test_recovery_reports_each_bad_statement():
    result = parse_src("int x = ;\nint y = ;")
    assert [(e.code, e.line) for e in result.errors] == [("E401", 1), ("E401", 2)]


def test_missing_closing_brace_reported_once():
    result = parse_src("void f() {\n  int x = 1;\n")
    assert len(result.errors) == 1
    assert result.errors[0].code == "E402"
    assert "'}'" in result.errors[0].message


def test_function_inside_block_is_an_error():
    result = parse_src("void f() { int g() { } }")
    assert len(result.errors) == 1
    assert result.errors[0].code == "E401"
    assert "top level" in result.errors[0].message


def test_stray_closing_brace_does_not_hang():
    result = parse_src("}")
    assert len(result.errors) == 1
    assert result.ast is None