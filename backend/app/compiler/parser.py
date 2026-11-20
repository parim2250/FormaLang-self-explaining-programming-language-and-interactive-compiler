"""Recursive-descent parser: token list -> AST.

One method per grammar rule, following the EBNF in docs/LANGUAGE_SPEC.md.
The AST is plain dicts so it can be sent to the browser as JSON.

AST node shapes (every node has "type", "line", "col" of its first token):
  Program      body
  FuncDecl     return_type, name, params (Param: var_type, name), body (Block)
  VarDecl      var_type, name, init (expr or null)
  Assign       target, op ("=", "+=", "-=", "*=", "/=", "++", "--"), value (expr or null)
  If           cond, then (Block), otherwise (If, Block or null)
  While        cond, body (Block)
  For          init (VarDecl, Assign or null), cond (expr or null), step (Assign or null), body (Block)
  Return       value (expr or null)
  Break, Continue
  Block        body
  ExprStmt     expr
  Binary       op, left, right
  Unary        op, operand
  Literal      value_type ("int", "float", "bool", "string"), value
  Var          name
  Call         name, args
  Convert      target_type, expr

Errors:
  E401  unexpected token where something else was required
  E402  a required token is missing; the location is the end of the previous
        token, so a missing ';' points just after the code

Recovery: after an error the parser skips to the next ';' or '}' and keeps
going, so one run can report several syntax errors.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.compiler.lexer import Token

ASSIGN_OPS = {"=", "+=", "-=", "*=", "/="}
INCDEC_OPS = {"++", "--"}
EQUALITY_OPS = {"==", "!="}
RELATIONAL_OPS = {"<", "<=", ">", ">="}
ADDITIVE_OPS = {"+", "-"}
MULTIPLICATIVE_OPS = {"*", "/", "%"}
LITERAL_TYPES = {"INT": "int", "FLOAT": "float", "BOOL": "bool", "STRING": "string"}


@dataclass
class ParseError:
    code: str
    message: str
    line: int
    col: int


@dataclass
class ParseResult:
    ast: dict | None
    errors: list[ParseError]


class _Bail(Exception):
    """Internal: aborts the current statement and carries the error to record."""

    def __init__(self, error: ParseError) -> None:
        super().__init__(error.message)
        self.error = error


def _text(tok: Token) -> str | None:
    """Lexeme for punctuation, keywords and operators; None for string literals."""
    return None if tok.kind == "STRING" else tok.lexeme


def _describe(tok: Token) -> str:
    if tok.kind == "EOF":
        return "end of input"
    if tok.kind == "IDENT":
        return f"name '{tok.lexeme}'"
    if tok.kind in ("INT", "FLOAT"):
        return f"number '{tok.lexeme}'"
    if tok.kind == "STRING":
        return f"string {tok.lexeme}"
    return f"'{tok.lexeme}'"


def _node(src, kind: str, **fields) -> dict:
    """Build a node positioned at a token or at an existing node."""
    if isinstance(src, Token):
        line, col = src.line, src.col
    else:
        line, col = src["line"], src["col"]
    return {"type": kind, "line": line, "col": col, **fields}


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.errors: list[ParseError] = []

    # ------------------------------------------------------------ tokens
    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        tok = self.tokens[self.pos]
        if tok.kind != "EOF":
            self.pos += 1
        return tok

    def at(self, text: str, offset: int = 0) -> bool:
        return _text(self.peek(offset)) == text

    def at_kind(self, kind: str, offset: int = 0) -> bool:
        return self.peek(offset).kind == kind

    def match(self, text: str) -> bool:
        if self.at(text):
            self.advance()
            return True
        return False

    # ------------------------------------------------------------ errors
    def _unexpected(self, expecting: str | None = None) -> _Bail:
        tok = self.peek()
        msg = f"Unexpected {_describe(tok)}"
        if expecting:
            msg += f", expected {expecting}"
        return _Bail(ParseError("E401", msg, tok.line, tok.col))

    def _missing(self, what: str) -> _Bail:
        cur = self.peek()
        if self.pos > 0:
            prev = self.tokens[self.pos - 1]
            line, col = prev.line, prev.col + len(prev.lexeme)
        else:
            line, col = cur.line, cur.col
        return _Bail(ParseError("E402", f"Expected {what} but found {_describe(cur)}", line, col))

    def _record(self, error: ParseError) -> None:
        # Drop an exact repeat (same code and place), which nested blocks can produce.
        last = self.errors[-1] if self.errors else None
        if last is not None and (last.code, last.line, last.col) == (error.code, error.line, error.col):
            return
        self.errors.append(error)

    def _recover(self, start: int, error: ParseError) -> None:
        self._record(error)
        self._synchronize()
        if self.pos == start:  # guarantee progress so the loop cannot stall
            self.advance()

    def _synchronize(self) -> None:
        """Skip to just after the next ';', or stop before '}' or end of input."""
        while not self.at_kind("EOF"):
            if self.at("}"):
                return
            if _text(self.advance()) == ";":
                return

    def expect(self, text: str) -> Token:
        if self.at(text):
            return self.advance()
        raise self._missing(f"'{text}'")

    def expect_name(self) -> Token:
        if self.at_kind("IDENT"):
            return self.advance()
        raise self._missing("a name")

    def expect_type(self) -> Token:
        if self.at_kind("TYPE"):
            return self.advance()
        raise self._missing("a type (int, float, bool, string or void)")

    # ------------------------------------------------------------ program
    def parse_program(self) -> dict:
        body = []
        while not self.at_kind("EOF"):
            start = self.pos
            try:
                body.append(self.top_level())
            except _Bail as bail:
                self._recover(start, bail.error)
        return {"type": "Program", "line": 1, "col": 1, "body": body}

    def top_level(self) -> dict:
        if self.at_kind("TYPE") and self.at_kind("IDENT", 1) and self.at("(", 2):
            return self.func_decl()
        return self.statement()

    def func_decl(self) -> dict:
        ret = self.expect_type()
        name = self.expect_name()
        self.expect("(")
        params = []
        if not self.at(")"):
            params.append(self.param())
            while self.match(","):
                params.append(self.param())
        self.expect(")")
        body = self.block()
        return _node(ret, "FuncDecl", return_type=ret.lexeme, name=name.lexeme, params=params, body=body)

    def param(self) -> dict:
        ptype = self.expect_type()
        pname = self.expect_name()
        return _node(ptype, "Param", var_type=ptype.lexeme, name=pname.lexeme)

    def block(self) -> dict:
        open_tok = self.expect("{")
        body = []
        while not self.at("}") and not self.at_kind("EOF"):
            start = self.pos
            try:
                body.append(self.statement())
            except _Bail as bail:
                self._recover(start, bail.error)
        if self.at("}"):
            self.advance()
        else:
            self._record(self._missing("'}'").error)
        return _node(open_tok, "Block", body=body)

    # ---------------------------------------------------------- statements
    def statement(self) -> dict:
        tok = self.peek()
        if tok.kind == "TYPE":
            if self.at("(", 1):
                return self.expr_statement()  # conversion, e.g. int(2.5);
            if self.at_kind("IDENT", 1) and self.at("(", 2):
                self._record(ParseError("E401", "Functions can only be declared at the top level",
                                        tok.line, tok.col))
                return self.func_decl()
            return self._end_statement(self.var_decl())
        if self.at("{"):
            return self.block()
        if self.at("if"):
            return self.if_stmt()
        if self.at("while"):
            return self.while_stmt()
        if self.at("for"):
            return self.for_stmt()
        if self.at("return"):
            return self.return_stmt()
        if self.at("break") or self.at("continue"):
            kw = self.advance()
            self.expect(";")
            return _node(kw, "Break" if kw.lexeme == "break" else "Continue")
        if tok.kind == "IDENT" and _text(self.peek(1)) in ASSIGN_OPS | INCDEC_OPS:
            return self._end_statement(self.assign())
        return self.expr_statement()

    def _end_statement(self, node: dict) -> dict:
        self.expect(";")
        return node

    def expr_statement(self) -> dict:
        e = self.expr()
        self.expect(";")
        return _node(e, "ExprStmt", expr=e)

    def var_decl(self) -> dict:
        type_tok = self.expect_type()
        name = self.expect_name()
        init = self.expr() if self.match("=") else None
        return _node(type_tok, "VarDecl", var_type=type_tok.lexeme, name=name.lexeme, init=init)

    def assign(self) -> dict:
        target = self.expect_name()
        op = self.peek()
        if _text(op) in INCDEC_OPS:
            self.advance()
            return _node(target, "Assign", target=target.lexeme, op=op.lexeme, value=None)
        if _text(op) in ASSIGN_OPS:
            self.advance()
            value = self.expr()
            return _node(target, "Assign", target=target.lexeme, op=op.lexeme, value=value)
        raise self._missing("an assignment operator (=, +=, -=, *=, /=, ++ or --)")

    def if_stmt(self) -> dict:
        kw = self.advance()
        self.expect("(")
        cond = self.expr()
        self.expect(")")
        then = self.block()
        otherwise = None
        if self.match("else"):
            otherwise = self.if_stmt() if self.at("if") else self.block()
        return _node(kw, "If", cond=cond, then=then, otherwise=otherwise)

    def while_stmt(self) -> dict:
        kw = self.advance()
        self.expect("(")
        cond = self.expr()
        self.expect(")")
        body = self.block()
        return _node(kw, "While", cond=cond, body=body)

    def for_stmt(self) -> dict:
        kw = self.advance()
        self.expect("(")
        init = None
        if not self.at(";"):
            if self.at_kind("TYPE") and self.at_kind("IDENT", 1):
                init = self.var_decl()
            else:
                init = self.assign()
        self.expect(";")
        cond = None if self.at(";") else self.expr()
        self.expect(";")
        step = None if self.at(")") else self.assign()
        self.expect(")")
        body = self.block()
        return _node(kw, "For", init=init, cond=cond, step=step, body=body)

    def return_stmt(self) -> dict:
        kw = self.advance()
        value = None if self.at(";") else self.expr()
        self.expect(";")
        return _node(kw, "Return", value=value)

    # --------------------------------------------------------- expressions
    def expr(self) -> dict:
        return self._logical_or()

    def _logical_or(self) -> dict:
        return self._binary(self._logical_and, {"||"})

    def _logical_and(self) -> dict:
        return self._binary(self._equality, {"&&"})

    def _equality(self) -> dict:
        return self._binary(self._relational, EQUALITY_OPS)

    def _relational(self) -> dict:
        return self._binary(self._additive, RELATIONAL_OPS)

    def _additive(self) -> dict:
        return self._binary(self._multiplicative, ADDITIVE_OPS)

    def _multiplicative(self) -> dict:
        return self._binary(self._unary, MULTIPLICATIVE_OPS)

    def _binary(self, operand, ops: set[str]) -> dict:
        left = operand()
        while _text(self.peek()) in ops:
            op = self.advance()
            right = operand()
            left = _node(left, "Binary", op=op.lexeme, left=left, right=right)
        return left

    def _unary(self) -> dict:
        tok = self.peek()
        if _text(tok) in ("-", "!"):
            self.advance()
            operand = self._unary()
            return _node(tok, "Unary", op=tok.lexeme, operand=operand)
        return self._primary()

    def _primary(self) -> dict:
        tok = self.peek()
        if tok.kind in LITERAL_TYPES:
            self.advance()
            return _node(tok, "Literal", value_type=LITERAL_TYPES[tok.kind], value=tok.value)
        if tok.kind == "IDENT":
            self.advance()
            if self.at("("):
                self.advance()
                args = []
                if not self.at(")"):
                    args.append(self.expr())
                    while self.match(","):
                        args.append(self.expr())
                self.expect(")")
                return _node(tok, "Call", name=tok.lexeme, args=args)
            return _node(tok, "Var", name=tok.lexeme)
        if tok.kind == "TYPE" and self.at("(", 1):
            self.advance()
            self.advance()
            inner = self.expr()
            self.expect(")")
            return _node(tok, "Convert", target_type=tok.lexeme, expr=inner)
        if self.at("("):
            self.advance()
            inner = self.expr()
            self.expect(")")
            return inner
        raise self._unexpected("an expression")


def count_nodes(node) -> int:
    if isinstance(node, dict):
        return (1 if "type" in node else 0) + sum(count_nodes(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_nodes(v) for v in node)
    return 0


def parse(tokens: list[Token]) -> ParseResult:
    parser = _Parser(tokens)
    ast = parser.parse_program()
    if parser.errors:
        return ParseResult(ast=None, errors=parser.errors)
    return ParseResult(ast=ast, errors=[])