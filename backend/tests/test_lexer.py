
import pytest

from app.compiler.lexer import ACCEPT, DFA, tokenize

EXAMPLE = '''// Your first FormaLang program
string greet(string name) {
    return "Hello, " + name + "!";
}

string language = "FormaLang";
float version = 1.0;

print(greet(language));
print("Ready to build something great.");

// Try a loop
for (int i = 1; i <= 3; i++) {
    print("Step " + i);
}
'''


def kinds(src):
    return [t.kind for t in tokenize(src).tokens]


def codes(src):
    return [e.code for e in tokenize(src).errors]


def test_keywords_types_and_bools():
    assert kinds("if int true x") == ["KEYWORD", "TYPE", "BOOL", "IDENT", "EOF"]


def test_identifiers_with_underscores_and_digits():
    assert kinds("_x1 foo_2") == ["IDENT", "IDENT", "EOF"]


def test_integers_and_floats_have_values():
    toks = tokenize("42 3.14").tokens
    assert (toks[0].kind, toks[0].value) == ("INT", 42)
    assert (toks[1].kind, toks[1].value) == ("FLOAT", 3.14)


def test_operators_use_longest_match():
    src = "+= ++ + == = != ! <= < >= > && || -- - *= * /= / %"
    assert kinds(src) == [
        "PLUS_ASSIGN", "INCR", "PLUS", "EQ", "ASSIGN", "NE", "BANG", "LE", "LT",
        "GE", "GT", "AND", "OR", "DECR", "MINUS", "STAR_ASSIGN", "STAR",
        "SLASH_ASSIGN", "SLASH", "PERCENT", "EOF",
    ]


def test_comments_are_skipped_and_lines_still_count():
    src = "int a; // note\n/* multi\nline */ int b;"
    assert kinds(src) == ["TYPE", "IDENT", "SEMI", "TYPE", "IDENT", "SEMI", "EOF"]
    assert tokenize(src).tokens[3].line == 3


def test_string_escapes_are_decoded():
    tok = tokenize('"a\\nb\\"c"').tokens[0]
    assert tok.value == 'a\nb"c'


def test_token_path_records_dfa_states():
    tok = tokenize("great").tokens[0]
    assert tok.path == ["START", "IDENT", "IDENT", "IDENT", "IDENT", "IDENT"]
    assert len(tok.edges) == 5


def test_line_and_column_tracking():
    toks = tokenize("int x;\n  float y;").tokens
    assert (toks[3].lexeme, toks[3].line, toks[3].col) == ("float", 2, 3)
    assert (toks[4].lexeme, toks[4].line, toks[4].col) == ("y", 2, 9)


@pytest.mark.parametrize("src,code", [
    ('"abc', "E101"),
    ('"abc\n"', "E101"),
    ("int @x;", "E102"),
    ("a & b", "E102"),
    ("1.", "E103"),
    ("2abc", "E103"),
    ("9223372036854775808", "E103"),
    ("/* open", "E104"),
    ('"a\\q"', "E105"),
])
def test_lexical_errors(src, code):
    assert code in codes(src)


def test_error_recovery_keeps_scanning():
    assert codes("int @x; float $y;") == ["E102", "E102"]


def test_dfa_table_is_closed_and_consistent():
    for row in DFA.values():
        for target in row.values():
            if target is not None:
                assert target in DFA
    assert set(ACCEPT) <= set(DFA)


def test_example_program_has_no_lexical_errors():
    assert codes(EXAMPLE) == []