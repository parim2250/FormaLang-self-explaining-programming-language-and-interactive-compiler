"""Semantic analyzer: symbol table, scope rules and static type checks.

Runs on the AST from parser.py before anything executes. It reports every
error it can find, not just the first one.

Types are strings: "int", "float", "bool", "string", "void".
UNKNOWN ("?") marks an expression whose type is unknown because an earlier
error was already reported. Checks on UNKNOWN values are skipped, so one
mistake does not cause a chain of follow-up errors.

Rules checked here:
  - a variable is visible only after its declaration (declare before use)
  - a variable may be redeclared in an inner block (shadowing), not in the same scope
  - functions are global; a call may come before the definition
  - int widens to float implicitly; nothing else converts

Error codes (see docs/LANGUAGE_SPEC.md):
  E201 type mismatch in a declaration, assignment or parameter/return value
  E202 invalid operands for an operator or conversion
  E203 condition is not bool
  E204 wrong number of arguments
  E205 argument type mismatch
  E206 return type mismatch, or a non-void function can finish without returning
  E301 undeclared identifier
  E302 redeclaration (variable, parameter, or function)
  E303 undefined function
  E304 break or continue outside a loop
  E305 return outside a function
"""
from __future__ import annotations

from dataclasses import dataclass

UNKNOWN = "?"
NUMERIC = ("int", "float")
COMPARISON_OPS = {"==", "!=", "<", "<=", ">", ">="}


@dataclass
class SemanticError:
    code: str
    message: str
    line: int
    col: int


@dataclass
class Symbol:
    name: str
    kind: str  # variable | parameter | function
    declared_type: str
    inferred_type: str | None
    scope: str
    line: int
    col: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "declared_type": self.declared_type,
            "inferred_type": self.inferred_type,
            "scope": self.scope,
            "line": self.line,
            "col": self.col,
        }


@dataclass
class FuncSig:
    node: dict
    return_type: str
    params: list[tuple[str, str]]  # (type, name)

    def describe(self) -> str:
        args = ", ".join(f"{t} {n}" for t, n in self.params)
        return f"({args}) -> {self.return_type}"


@dataclass
class SemanticResult:
    errors: list[SemanticError]
    symbols: list[dict]


def is_numeric(t: str) -> bool:
    return t in NUMERIC


def can_assign(value_type: str, target_type: str) -> bool:
    """Same type, or int widening to float. Nothing else converts implicitly."""
    return value_type == target_type or (target_type == "float" and value_type == "int")


def _is_true(node: dict) -> bool:
    return node["type"] == "Literal" and node["value_type"] == "bool" and node["value"] is True


def _has_break(node: dict) -> bool:
    """True if a break in this statement belongs to the enclosing loop.
    A break inside a nested loop belongs to that loop, so it does not count."""
    kind = node["type"]
    if kind == "Break":
        return True
    if kind == "Block":
        return any(_has_break(s) for s in node["body"])
    if kind == "If":
        return _has_break(node["then"]) or (
            node["otherwise"] is not None and _has_break(node["otherwise"])
        )
    return False


def _always_returns(node: dict) -> bool:
    """True if every path through this statement ends in a return."""
    kind = node["type"]
    if kind == "Return":
        return True
    if kind == "Block":
        return any(_always_returns(s) for s in node["body"])
    if kind == "If":
        return (
            node["otherwise"] is not None
            and _always_returns(node["then"])
            and _always_returns(node["otherwise"])
        )
    if kind == "While":
        return _is_true(node["cond"]) and not _has_break(node["body"])
    if kind == "For":
        infinite = node["cond"] is None or _is_true(node["cond"])
        return infinite and not _has_break(node["body"])
    return False


class _Analyzer:
    def __init__(self) -> None:
        self.scopes: list[dict[str, Symbol]] = []
        self.labels: list[str] = []
        self.functions: dict[str, FuncSig] = {}
        self.symbols: list[Symbol] = []
        self.errors: list[SemanticError] = []
        self.loop_depth = 0
        self.return_type: str | None = None  # None means "not inside a function"

    # ------------------------------------------------------------ bookkeeping
    def _error(self, code: str, message: str, node: dict) -> None:
        self.errors.append(SemanticError(code, message, node["line"], node["col"]))

    def _push(self, label: str) -> None:
        self.scopes.append({})
        self.labels.append(label)

    def _pop(self) -> None:
        self.scopes.pop()
        self.labels.pop()

    def _declare(self, name: str, declared: str, inferred: str | None, kind: str, node: dict) -> None:
        sym = Symbol(name, kind, declared, inferred, self.labels[-1], node["line"], node["col"])
        self.scopes[-1][name] = sym
        self.symbols.append(sym)

    def _lookup(self, name: str, node: dict) -> Symbol | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        self._error("E301", f"'{name}' is not declared", node)
        return None

    # ------------------------------------------------------------ program
    def analyze(self, program: dict) -> SemanticResult:
        self.scopes = [{}]
        self.labels = ["global"]
        # Pass 1: record every function signature, so calls may come before the definition.
        for stmt in program["body"]:
            if stmt["type"] == "FuncDecl":
                self._declare_function(stmt)
        # Pass 2: check top-level statements and function bodies in source order.
        for stmt in program["body"]:
            if stmt["type"] == "FuncDecl":
                self._check_function(stmt)
            else:
                self._stmt(stmt)
        ordered = sorted(self.symbols, key=lambda s: (s.line, s.col))
        return SemanticResult(self.errors, [s.to_dict() for s in ordered])

    def _declare_function(self, node: dict) -> None:
        name = node["name"]
        if name == "print":
            self._error("E302", "'print' is built in and cannot be redefined", node)
            return
        if name in self.functions:
            self._error("E302", f"Function '{name}' is already defined", node)
            return
        params = [(p["var_type"], p["name"]) for p in node["params"]]
        sig = FuncSig(node, node["return_type"], params)
        self.functions[name] = sig
        self.symbols.append(
            Symbol(name, "function", sig.describe(), None, "global", node["line"], node["col"])
        )

    def _check_function(self, node: dict) -> None:
        sig = self.functions.get(node["name"])
        if sig is None or sig.node is not node:
            return  # rejected in pass 1; its body is not checked
        self._push(f"function {node['name']}")
        for param in node["params"]:
            if param["var_type"] == "void":
                self._error("E201", "A parameter cannot have type void", param)
            if param["name"] in self.scopes[-1]:
                self._error("E302", f"'{param['name']}' is already declared in this scope", param)
            else:
                self._declare(param["name"], param["var_type"], param["var_type"], "parameter", param)

        saved = (self.return_type, self.loop_depth)
        self.return_type, self.loop_depth = sig.return_type, 0
        for stmt in node["body"]["body"]:  # parameters and body share one scope
            self._stmt(stmt)
        self.return_type, self.loop_depth = saved

        if sig.return_type != "void" and not _always_returns(node["body"]):
            self._error(
                "E206",
                f"'{node['name']}' can finish without returning a {sig.return_type} value",
                node,
            )
        self._pop()

    # ------------------------------------------------------------ statements
    def _stmt(self, node: dict) -> None:
        kind = node["type"]
        if kind == "VarDecl":
            self._var_decl(node)
        elif kind == "Assign":
            self._assign(node)
        elif kind == "ExprStmt":
            self._expr(node["expr"])
        elif kind == "Block":
            self._block(node, "block")
        elif kind == "If":
            self._if(node)
        elif kind == "While":
            self._while(node)
        elif kind == "For":
            self._for(node)
        elif kind == "Return":
            self._return(node)
        elif kind in ("Break", "Continue"):
            if self.loop_depth == 0:
                self._error("E304", f"'{kind.lower()}' is only allowed inside a loop", node)
        else:
            raise RuntimeError(f"semantic analysis does not handle {kind}")

    def _block(self, node: dict, label: str) -> None:
        self._push(label)
        for stmt in node["body"]:
            self._stmt(stmt)
        self._pop()

    def _var_decl(self, node: dict) -> None:
        name, var_type = node["name"], node["var_type"]
        if name in self.scopes[-1]:
            self._error("E302", f"'{name}' is already declared in this scope", node)
            if node["init"] is not None:
                self._expr(node["init"])
            return
        if var_type == "void":
            self._error("E201", "A variable cannot have type void", node)
        inferred = var_type
        if node["init"] is not None:
            value_type = self._expr(node["init"])  # evaluated before the name exists
            if value_type != UNKNOWN:
                inferred = value_type
            self._assignable(value_type, var_type, name, node)
        self._declare(name, var_type, inferred, "variable", node)

    def _assignable(self, value_type: str, target_type: str, name: str, node: dict) -> None:
        if value_type == UNKNOWN or can_assign(value_type, target_type):
            return
        hint = " Use int(...) to convert explicitly." if target_type == "int" and value_type == "float" else ""
        self._error(
            "E201",
            f"Type mismatch: '{name}' is {target_type}, but the value is {value_type}.{hint}",
            node,
        )

    def _assign(self, node: dict) -> None:
        name, op = node["target"], node["op"]
        sym = self._lookup(name, node)
        if op in ("++", "--"):
            if sym is not None and sym.declared_type not in NUMERIC:
                self._error("E202", f"'{op}' works only on int and float variables", node)
            return
        value_type = self._expr(node["value"])
        if sym is None:
            return
        if op == "=":
            self._assignable(value_type, sym.declared_type, name, node)
            return
        # compound assignment: the operator must work, and the result must still fit the variable
        result = self._binary_type(op[0], sym.declared_type, value_type, node)
        self._assignable(result, sym.declared_type, name, node)

    def _require_bool(self, t: str, node: dict) -> None:
        if t not in (UNKNOWN, "bool"):
            self._error("E203", f"The condition must be bool, but got {t}", node)

    def _if(self, node: dict) -> None:
        self._require_bool(self._expr(node["cond"]), node["cond"])
        self._block(node["then"], "if block")
        otherwise = node["otherwise"]
        if otherwise is not None:
            if otherwise["type"] == "If":
                self._if(otherwise)
            else:
                self._block(otherwise, "else block")

    def _while(self, node: dict) -> None:
        self._require_bool(self._expr(node["cond"]), node["cond"])
        self.loop_depth += 1
        self._block(node["body"], "while block")
        self.loop_depth -= 1

    def _for(self, node: dict) -> None:
        self._push("for loop")  # the loop variable lives in this header scope
        if node["init"] is not None:
            self._stmt(node["init"])
        if node["cond"] is not None:
            self._require_bool(self._expr(node["cond"]), node["cond"])
        self.loop_depth += 1
        self._block(node["body"], "for block")
        self.loop_depth -= 1
        if node["step"] is not None:
            self._stmt(node["step"])
        self._pop()

    def _return(self, node: dict) -> None:
        value = node["value"]
        if self.return_type is None:
            self._error("E305", "'return' is only allowed inside a function", node)
            if value is not None:
                self._expr(value)
            return
        expected = self.return_type
        if value is None:
            if expected != "void":
                self._error("E206", f"This return needs a {expected} value", node)
            return
        actual = self._expr(value)
        if expected == "void":
            self._error("E206", "A void function cannot return a value", node)
        elif actual != UNKNOWN and not can_assign(actual, expected):
            self._error(
                "E206",
                f"Return type mismatch: the function returns {expected}, but the value is {actual}",
                node,
            )

    # ------------------------------------------------------------ expressions
    def _expr(self, node: dict) -> str:
        kind = node["type"]
        if kind == "Literal":
            return node["value_type"]
        if kind == "Var":
            sym = self._lookup(node["name"], node)
            return sym.declared_type if sym is not None else UNKNOWN
        if kind == "Unary":
            return self._unary_type(node["op"], self._expr(node["operand"]), node)
        if kind == "Binary":
            left = self._expr(node["left"])
            right = self._expr(node["right"])
            if node["op"] in ("&&", "||"):
                return self._logic_type(node["op"], left, right, node)
            return self._binary_type(node["op"], left, right, node)
        if kind == "Convert":
            return self._convert_type(node["target_type"], self._expr(node["expr"]), node)
        if kind == "Call":
            return self._call_type(node)
        raise RuntimeError(f"semantic analysis does not handle {kind}")

    def _logic_type(self, op: str, left: str, right: str, node: dict) -> str:
        for t in (left, right):
            if t not in (UNKNOWN, "bool"):
                self._error("E202", f"'{op}' needs bools, but got {t}", node)
                return "bool"
        return "bool"

    def _unary_type(self, op: str, t: str, node: dict) -> str:
        if op == "-":
            if t == UNKNOWN:
                return UNKNOWN
            if not is_numeric(t):
                self._error("E202", f"'-' needs a number, but got {t}", node)
                return UNKNOWN
            return t
        # "!"
        if t not in (UNKNOWN, "bool"):
            self._error("E202", f"'!' needs a bool, but got {t}", node)
        return "bool"

    def _binary_type(self, op: str, left: str, right: str, node: dict) -> str:
        known = UNKNOWN not in (left, right)

        if op == "+" and "string" in (left, right):
            if "void" in (left, right):
                self._error("E202", "A void value cannot be used with '+'", node)
                return UNKNOWN
            return "string"

        if op in ("==", "!="):
            if known:
                same = (is_numeric(left) and is_numeric(right)) or (
                    left == right and left in ("bool", "string")
                )
                if not same:
                    self._error("E202", f"Cannot compare {left} with {right}", node)
            return "bool"

        if op in ("<", "<=", ">", ">="):
            if known and not (is_numeric(left) and is_numeric(right)):
                self._error("E202", f"'{op}' compares numbers, but got {left} and {right}", node)
            return "bool"

        # arithmetic: + - * / %
        if not known:
            return UNKNOWN
        if not (is_numeric(left) and is_numeric(right)):
            self._error("E202", f"'{op}' needs numbers, but got {left} and {right}", node)
            return UNKNOWN
        if op == "%" and not (left == "int" and right == "int"):
            self._error("E202", "'%' works only on two int values", node)
            return UNKNOWN
        return "int" if left == "int" and right == "int" else "float"

    def _convert_type(self, target: str, t: str, node: dict) -> str:
        if target == "void":
            self._error("E202", "Cannot convert to void", node)
            return UNKNOWN
        if target == "string":
            if t == "void":
                self._error("E202", "A void value cannot be converted to string", node)
            return "string"
        if target == "bool":
            if t not in (UNKNOWN, "bool"):
                self._error("E202", f"Cannot convert {t} to bool", node)
            return "bool"
        # int or float
        if t not in (UNKNOWN,) and not is_numeric(t):
            self._error("E202", f"Cannot convert {t} to {target}", node)
        return target

    def _call_type(self, node: dict) -> str:
        name, args = node["name"], node["args"]

        if name == "print":
            if len(args) != 1:
                self._error("E204", f"print takes 1 argument, but got {len(args)}", node)
                for arg in args:
                    self._expr(arg)
                return "void"
            if self._expr(args[0]) == "void":
                self._error("E202", "A void value cannot be printed", node)
            return "void"

        arg_types = [self._expr(arg) for arg in args]
        sig = self.functions.get(name)
        if sig is None:
            self._error("E303", f"Function '{name}' is not defined", node)
            return UNKNOWN
        if len(args) != len(sig.params):
            self._error(
                "E204",
                f"'{name}' takes {len(sig.params)} argument(s), but got {len(args)}",
                node,
            )
            return sig.return_type
        for (ptype, pname), arg, atype in zip(sig.params, args, arg_types):
            if atype != UNKNOWN and not can_assign(atype, ptype):
                self._error(
                    "E205",
                    f"Argument '{pname}' of '{name}' should be {ptype}, but got {atype}",
                    arg,
                )
        return sig.return_type


def analyze(program: dict) -> SemanticResult:
    return _Analyzer().analyze(program)