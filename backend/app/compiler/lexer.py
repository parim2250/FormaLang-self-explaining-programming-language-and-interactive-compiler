"""
FormaLang lexer: a deterministic finite automaton (DFA) driven by a table.

The automaton is data (the DFA dict below), not hand-written branching code.
tokenize() runs maximal munch over it: it steps while a transition exists, then
either ACCEPTs (emit a token, or skip whitespace/comments) or reports the error
attached to the state where the machine got stuck. Every non-accepting state
has an error attached, so the scanner never needs to backtrack.

Transition keys, checked in this order:
  1. the literal character              e.g. "+"
  2. a character class                  "ALPHA", "DIGIT", "SP" (space/tab/CR), "NL"
  3. "ANY"                              fallback for any other character
A value of None is an explicit dead end (it blocks the ANY fallback).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

KEYWORDS = {"if", "else", "while", "for", "return", "break", "continue"}
BOOL_WORDS = {"true", "false"}
TYPE_WORDS = {"int", "float", "bool", "string", "void"}
INT_MAX = 2**63 - 1
MAX_ERRORS = 20

DFA: dict[str, dict[str, str | None]] = {
    # start, whitespace, comments
    "START": {
        "SP": "WS", "NL": "WS",
        "ALPHA": "IDENT", "DIGIT": "INT", '"': "STR_BODY",
        "/": "SLASH", "+": "PLUS", "-": "MINUS", "*": "STAR", "%": "PERCENT",
        "=": "ASSIGN", "!": "BANG", "<": "LT", ">": "GT", "&": "AMP", "|": "PIPE",
        "(": "LPAREN", ")": "RPAREN", "{": "LBRACE", "}": "RBRACE", ",": "COMMA", ";": "SEMI",
    },
    "WS": {"SP": "WS", "NL": "WS"},
    "LINE_COMMENT": {"NL": None, "ANY": "LINE_COMMENT"},
    "BLOCK": {"*": "BLOCK_STAR", "ANY": "BLOCK"},
    "BLOCK_STAR": {"/": "BLOCK_CLOSE", "*": "BLOCK_STAR", "ANY": "BLOCK"},
    "BLOCK_CLOSE": {},
    # identifiers and keywords
    "IDENT": {"ALPHA": "IDENT", "DIGIT": "IDENT"},
    # numbers
    "INT": {"DIGIT": "INT", ".": "FLOAT_DOT", "ALPHA": "ERR_NUM"},
    "FLOAT_DOT": {"DIGIT": "FLOAT"},
    "FLOAT": {"DIGIT": "FLOAT", "ALPHA": "ERR_NUM"},
    "ERR_NUM": {},
    # strings
    "STR_BODY": {'"': "STR_CLOSE", "\\": "STR_ESC", "NL": None, "ANY": "STR_BODY"},
    "STR_ESC": {"n": "STR_BODY", "t": "STR_BODY", "\\": "STR_BODY", '"': "STR_BODY"},
    "STR_CLOSE": {},
    # operators and punctuation
    "AMP": {"&": "AND"}, "AND": {},
    "PIPE": {"|": "OR"}, "OR": {},
    "PLUS": {"=": "PLUS_ASSIGN", "+": "INCR"}, "PLUS_ASSIGN": {}, "INCR": {},
    "MINUS": {"=": "MINUS_ASSIGN", "-": "DECR"}, "MINUS_ASSIGN": {}, "DECR": {},
    "STAR": {"=": "STAR_ASSIGN"}, "STAR_ASSIGN": {},
    "SLASH": {"=": "SLASH_ASSIGN", "/": "LINE_COMMENT", "*": "BLOCK"}, "SLASH_ASSIGN": {},
    "PERCENT": {},
    "ASSIGN": {"=": "EQ"}, "EQ": {},
    "BANG": {"=": "NE"}, "NE": {},
    "LT": {"=": "LE"}, "LE": {},
    "GT": {"=": "GE"}, "GE": {},
    "LPAREN": {}, "RPAREN": {}, "LBRACE": {}, "RBRACE": {}, "COMMA": {}, "SEMI": {},
}

_OPERATOR_STATES = [
    "AND", "OR", "PLUS", "PLUS_ASSIGN", "INCR", "MINUS", "MINUS_ASSIGN", "DECR",
    "STAR", "STAR_ASSIGN", "SLASH", "SLASH_ASSIGN", "PERCENT", "ASSIGN", "EQ",
    "BANG", "NE", "LT", "LE", "GT", "GE",
    "LPAREN", "RPAREN", "LBRACE", "RBRACE", "COMMA", "SEMI",
]

# accepting state -> token kind
ACCEPT: dict[str, str] = {s: s for s in _OPERATOR_STATES}
ACCEPT.update({"IDENT": "IDENT", "INT": "INT", "FLOAT": "FLOAT", "STR_CLOSE": "STRING"})

# accepting states that produce no token (whitespace and comments)
SKIP = {"WS", "LINE_COMMENT", "BLOCK_CLOSE"}

# non-accepting states -> (error code, message) when the scanner gets stuck there
ERRORS: dict[str, tuple[str, str]] = {
    "START": ("E102", "Unexpected character"),
    "AMP": ("E102", "Expected '&&' (a single '&' is not an operator)"),
    "PIPE": ("E102", "Expected '||' (a single '|' is not an operator)"),
    "FLOAT_DOT": ("E103", "Malformed number: a digit must follow '.'"),
    "ERR_NUM": ("E103", "Malformed number: a letter cannot directly follow digits"),
    "STR_BODY": ("E101", "Unterminated string literal (strings must close on the same line)"),
    "STR_ESC": ("E105", "Invalid escape sequence (allowed: \\n \\t \\\\ \\\")"),
    "BLOCK": ("E104", "Unterminated block comment"),
    "BLOCK_STAR": ("E104", "Unterminated block comment"),
}

_CLASS_LABEL = {"ALPHA": "letter", "DIGIT": "digit", "SP": "space", "NL": "newline"}
_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"'}


@dataclass
class Token:
    kind: str
    lexeme: str
    value: Any
    line: int
    col: int
    path: list[str] = field(default_factory=list)   # DFA states visited, START first
    edges: list[str] = field(default_factory=list)  # label of each transition taken

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LexError:
    code: str
    message: str
    line: int
    col: int


@dataclass
class LexResult:
    tokens: list[Token]
    errors: list[LexError]


def _char_class(ch: str) -> str:
    if ch == "\n":
        return "NL"
    if ch in " \t\r":
        return "SP"
    if ch == "_" or "a" <= ch <= "z" or "A" <= ch <= "Z":
        return "ALPHA"
    if "0" <= ch <= "9":
        return "DIGIT"
    return "OTHER"


def _step(state: str, ch: str) -> tuple[str | None, str]:
    """One DFA transition. Returns (next_state or None, label for the edge)."""
    row = DFA[state]
    if ch in row:
        return row[ch], ch
    cls = _char_class(ch)
    if cls in row:
        return row[cls], _CLASS_LABEL.get(cls, cls)
    if "ANY" in row:
        return row["ANY"], "any char"
    return None, ""


def _advance(line: int, col: int, text: str) -> tuple[int, int]:
    for ch in text:
        if ch == "\n":
            line, col = line + 1, 1
        else:
            col += 1
    return line, col


def _decode(body: str) -> str:
    out: list[str] = []
    k = 0
    while k < len(body):
        if body[k] == "\\":
            out.append(_ESCAPES[body[k + 1]])
            k += 2
        else:
            out.append(body[k])
            k += 1
    return "".join(out)


def _make_token(state: str, lexeme: str, line: int, col: int,
                path: list[str], edges: list[str]) -> tuple[Token | None, LexError | None]:
    kind = ACCEPT[state]
    value: Any = None
    if state == "IDENT":
        if lexeme in KEYWORDS:
            kind = "KEYWORD"
        elif lexeme in BOOL_WORDS:
            kind, value = "BOOL", lexeme == "true"
        elif lexeme in TYPE_WORDS:
            kind = "TYPE"
    elif state == "INT":
        value = int(lexeme)
        if value > INT_MAX:
            return None, LexError("E103", "Integer literal is out of the 64-bit range", line, col)
    elif state == "FLOAT":
        value = float(lexeme)
    elif state == "STR_CLOSE":
        value = _decode(lexeme[1:-1])
    return Token(kind, lexeme, value, line, col, path, edges), None


def tokenize(source: str) -> LexResult:
    tokens: list[Token] = []
    errors: list[LexError] = []
    n = len(source)
    i, line, col = 0, 1, 1

    while i < n:
        # whitespace separates tokens; skip it before the DFA runs
        ch = source[i]
        if ch == "\n":
            line += 1
            col = 1
            i += 1
            continue
        if ch in " \t\r":
            col += 1
            i += 1
            continue

        # comments are skipped before the DFA runs
        if source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            stop = n if end == -1 else end + 2
            if end == -1:
                errors.append(LexError("E104", "Unterminated block comment", line, col))
            line, col = _advance(line, col, source[i:stop])
            i = stop
            continue

        start_line, start_col = line, col
        state, j = "START", i
        path, edges = ["START"], []

        # maximal munch: keep stepping while the DFA has a transition
        while j < n:
            nxt, label = _step(state, source[j])
            if nxt is None:
                break
            path.append(nxt)
            edges.append(label)
            state = nxt
            j += 1

        lexeme = source[i:j]

        if state in ACCEPT:
            if state not in SKIP:
                token, error = _make_token(state, lexeme, start_line, start_col, path, edges)
                if error is not None:
                    errors.append(error)
                else:
                    tokens.append(token)
            line, col = _advance(line, col, lexeme)
            i = j
        else:
            code, message = ERRORS.get(state, ("E102", "Unexpected character"))
            if state == "START":
                message = f"Unexpected character '{source[i]}'"
            errors.append(LexError(code, message, start_line, start_col))
            # recover: skip the bad text (at least one character) and keep scanning
            step = max(j - i, 1)
            line, col = _advance(line, col, source[i:i + step])
            i += step
            if len(errors) >= MAX_ERRORS:
                break

    tokens.append(Token("EOF", "", None, line, col))
    return LexResult(tokens, errors)