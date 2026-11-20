"""FormaLang interpreter: tree-walking execution with an execution trace.

Phase 3 added declarations, expressions and print.
Phase 5 adds if/else, while, for, break, continue, the step limit (E504)
and the execution trace. Functions and return are still reported by
find_unsupported until Phase 6.
"""

from __future__ import annotations

import json
import math
import operator
from typing import Any

INT_MIN = -(2**63)
INT_MAX = 2**63 - 1
STEP_LIMIT = 1_000_000
TRACE_LIMIT = 500

# Token kinds and lexemes both map to the same operator text.
_OP_ALIASES = {
    "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/", "PERCENT": "%",
    "AND": "&&", "OR": "||", "BANG": "!",
    "EQ": "==", "NE": "!=", "LT": "<", "LE": "<=", "GT": ">", "GE": ">=",
    "ASSIGN": "=", "PLUS_ASSIGN": "+=", "MINUS_ASSIGN": "-=",
    "STAR_ASSIGN": "*=", "SLASH_ASSIGN": "/=", "INCR": "++", "DECR": "--",
}

_PRECEDENCE = {
    "||": 1, "&&": 2, "==": 3, "!=": 3,
    "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5, "*": 6, "/": 6, "%": 6,
}

_ARITH = {"+": operator.add, "-": operator.sub, "*": operator.mul}
_COMPARE = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}


class RunError(Exception):
    """A runtime error with a FormaLang error code and the AST node it points at."""

    def __init__(self, code: str, message: str, node: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.node = node or {}

    @property
    def line(self) -> int:
        return self.node.get("line", 1)

    @property
    def col(self) -> int:
        return self.node.get("col", 1)


class _LoopSignal(Exception):
    """Raised by break and continue; caught by the enclosing loop."""

    def __init__(self, keyword: str, node: dict):
        super().__init__(keyword)
        self.keyword = keyword
        self.node = node


# ---------------------------------------------------------------- helpers

def _norm(op: str) -> str:
    return _OP_ALIASES.get(op, op)


def _target_name(target: Any) -> str:
    if isinstance(target, str):
        return target
    return target["name"]


def _literal_value(node: dict) -> Any:
    vtype = str(node.get("value_type", "")).lower()
    value = node.get("value")
    if vtype == "int":
        return int(value)
    if vtype == "float":
        return float(value)
    if vtype == "bool":
        if isinstance(value, bool):
            return value
        return str(value).lower() == "true"
    if vtype == "string":
        return str(value)
    return value


def type_name(value: Any) -> str:
    if value is None:
        return "void"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    return "?"


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def default_value(vtype: str) -> Any:
    return {"int": 0, "float": 0.0, "bool": False, "string": ""}.get(vtype)


def to_text(value: Any) -> str:
    if value is None:
        return "void"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = repr(value)
        if "." not in text and "e" not in text and "n" not in text:
            text += ".0"
        return text
    return str(value)


def _check_int(value: int, node: dict | None) -> int:
    if value < INT_MIN or value > INT_MAX:
        raise RunError("E502", "Integer overflow: the result does not fit in a 64-bit int", node)
    return value


def _trunc_div(a: int, b: int) -> int:
    """Integer division that truncates toward zero (caller checks b != 0)."""
    quotient = abs(a) // abs(b)
    return quotient if (a >= 0) == (b > 0) else -quotient


def coerce(value: Any, from_type: str, to_type: str, node: dict | None = None) -> Any:
    """Implicit conversion. Only int to float widens; float to int needs int(x)."""
    if from_type == to_type:
        return value
    if from_type == "int" and to_type == "float":
        return float(value)
    if from_type == "float" and to_type == "int":
        raise RunError("E201", "Cannot assign float to int. Use int(x) to convert explicitly.", node)
    raise RunError("E201", f"Cannot use {from_type} where {to_type} is expected", node)


def convert(target: str, value: Any, node: dict | None = None) -> Any:
    """Explicit conversion: int(), float(), string(), bool()."""
    source = type_name(value)
    if target == "string":
        return to_text(value)
    if target == "bool":
        if source == "bool":
            return value
        raise RunError("E201", f"bool() only accepts a bool, not {source}", node)
    if target == "int":
        if source == "int":
            return value
        if source == "float":
            if math.isnan(value) or math.isinf(value):
                raise RunError("E502", "The value does not fit in a 64-bit int", node)
            return _check_int(int(value), node)  # int() truncates toward zero
        raise RunError("E201", f"int() only accepts int or float, not {source}", node)
    if target == "float":
        if source in ("int", "float"):
            return float(value)
        raise RunError("E201", f"float() only accepts int or float, not {source}", node)
    raise RunError("E201", f"Cannot convert to {target}", node)


def _equal(left: Any, right: Any, node: dict | None) -> bool:
    if is_number(left) and is_number(right):
        return left == right
    if isinstance(left, bool) and isinstance(right, bool):
        return left == right
    if isinstance(left, str) and isinstance(right, str):
        return left == right
    raise RunError("E202", f"Cannot compare {type_name(left)} with {type_name(right)}", node)


def _require_numbers(op: str, left: Any, right: Any, node: dict | None) -> None:
    if not (is_number(left) and is_number(right)):
        raise RunError(
            "E202",
            f"'{op}' needs number operands, not {type_name(left)} and {type_name(right)}",
            node,
        )


def _need_bool(value: Any, op: str, node: dict | None) -> None:
    if not isinstance(value, bool):
        raise RunError("E202", f"'{op}' needs bool operands, not {type_name(value)}", node)


def binary_op(op: str, left: Any, right: Any, node: dict | None = None) -> Any:
    op = _norm(op)
    if op == "+" and (isinstance(left, str) or isinstance(right, str)):
        return to_text(left) + to_text(right)
    if op in ("==", "!="):
        equal = _equal(left, right, node)
        return equal if op == "==" else not equal

    _require_numbers(op, left, right, node)
    if op in _COMPARE:
        return _COMPARE[op](left, right)

    both_int = isinstance(left, int) and isinstance(right, int)
    if op == "%":
        if not both_int:
            raise RunError("E202", "'%' only works on int values", node)
        if right == 0:
            raise RunError("E501", "Division by zero", node)
        return _check_int(left - right * _trunc_div(left, right), node)
    if op == "/":
        if right == 0:
            raise RunError("E501", "Division by zero", node)
        if both_int:
            return _check_int(_trunc_div(left, right), node)
        return float(left) / float(right)
    if op in _ARITH:
        if both_int:
            return _check_int(_ARITH[op](left, right), node)
        return _ARITH[op](float(left), float(right))
    raise RunError("E202", f"Unknown operator '{op}'", node)


def unary_op(op: str, value: Any, node: dict | None = None) -> Any:
    op = _norm(op)
    if op == "-":
        if not is_number(value):
            raise RunError("E202", f"'-' needs a number, not {type_name(value)}", node)
        if isinstance(value, int):
            return _check_int(-value, node)
        return -value
    if op == "!":
        if not isinstance(value, bool):
            raise RunError("E202", f"'!' needs a bool, not {type_name(value)}", node)
        return not value
    raise RunError("E202", f"Unknown operator '{op}'", node)


def expr_text(node: dict | None, parent: int = 0) -> str:
    """Rebuild readable source text from an expression node, for the trace."""
    if node is None:
        return ""
    kind = node.get("type")
    if kind == "Literal":
        value = _literal_value(node)
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        return to_text(value)
    if kind == "Var":
        return node.get("name", "?")
    if kind == "Binary":
        op = _norm(node["op"])
        prec = _PRECEDENCE.get(op, 0)
        text = f"{expr_text(node['left'], prec)} {op} {expr_text(node['right'], prec + 1)}"
        return f"({text})" if prec < parent else text
    if kind == "Unary":
        return f"{_norm(node['op'])}{expr_text(node['operand'], 7)}"
    if kind == "Convert":
        return f"{node['target_type']}({expr_text(node['expr'])})"
    if kind == "Call":
        args = ", ".join(expr_text(arg) for arg in node.get("args", []))
        return f"{node['name']}({args})"
    return "?"


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


def find_unsupported(ast: dict) -> tuple[str, int, dict] | None:
    """Return (feature, phase, node) for the earliest construct not yet executable."""
    found = []
    for node in _walk(ast):
        kind = node.get("type")
        if kind == "FuncDecl":
            found.append(("functions", 6, node))
        elif kind == "Return":
            found.append(("return", 6, node))
        elif kind == "Call" and node.get("name") != "print":
            found.append(("calls to user functions", 6, node))
    if not found:
        return None
    found.sort(key=lambda item: (item[2].get("line", 0), item[2].get("col", 0)))
    return found[0]


# ------------------------------------------------------------ interpreter

class Interpreter:
    def __init__(self) -> None:
        self.scopes: list[dict[str, list[Any]]] = [{}]
        self.output: list[str] = []
        self.trace: list[dict[str, Any]] = []
        self.steps = 0
        self._trace_full = False

    def run(self, program: dict) -> list[str]:
        self.scopes = [{}]
        self.output = []
        self.trace = []
        self.steps = 0
        self._trace_full = False
        try:
            for statement in program.get("body", []):
                self._exec(statement)
        except _LoopSignal as signal:
            raise RunError(
                "E304", f"'{signal.keyword}' can only be used inside a loop", signal.node
            ) from None
        return self.output

    # -- bookkeeping

    def _tick(self, node: dict) -> None:
        self.steps += 1
        if self.steps > STEP_LIMIT:
            raise RunError(
                "E504",
                "Step limit of 1,000,000 reached. The program may be stuck in a loop.",
                node,
            )

    def _record(self, node: dict, operation: str, result: str) -> None:
        """Callers check self._trace_full first so skipped steps cost nothing."""
        if len(self.trace) >= TRACE_LIMIT:
            self._trace_full = True
            self.trace.append({
                "step": len(self.trace) + 1,
                "line": node.get("line", 1),
                "col": node.get("col", 1),
                "operation": (
                    f"Trace limit of {TRACE_LIMIT} steps reached. "
                    "The program keeps running, but later steps are not shown."
                ),
                "result": "",
                "variables": [],
            })
            return
        self.trace.append({
            "step": len(self.trace) + 1,
            "line": node.get("line", 1),
            "col": node.get("col", 1),
            "operation": operation,
            "result": result,
            "variables": self._snapshot(),
        })

    def _snapshot(self) -> list[dict[str, str]]:
        visible: dict[str, list[Any]] = {}
        for scope in self.scopes:
            for name, entry in scope.items():
                visible[name] = entry
        return [
            {"name": name, "type": vtype, "value": to_text(value)}
            for name, (vtype, value) in visible.items()
        ]

    def _lookup(self, name: str, node: dict) -> list[Any]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise RunError("E301", f"'{name}' is not declared", node)

    def _condition(self, expr: dict | None) -> bool:
        if expr is None:
            return True
        value = self._eval(expr)
        if not isinstance(value, bool):
            raise RunError("E203", f"A condition must be bool, not {type_name(value)}", expr)
        return value

    # -- statements

    def _exec(self, node: dict) -> None:
        self._tick(node)
        kind = node.get("type")
        if kind == "VarDecl":
            self._var_decl(node)
        elif kind == "Assign":
            self._assign(node)
        elif kind == "ExprStmt":
            self._expr_stmt(node)
        elif kind == "If":
            self._if(node)
        elif kind == "While":
            self._while(node)
        elif kind == "For":
            self._for(node)
        elif kind == "Block":
            self._block(node.get("body", []))
        elif kind in ("Break", "Continue"):
            keyword = "break" if kind == "Break" else "continue"
            if not self._trace_full:
                outcome = "exit the loop" if keyword == "break" else "skip to the next iteration"
                self._record(node, keyword, outcome)
            raise _LoopSignal(keyword, node)
        else:
            raise RunError("E401", f"Unexpected {kind} in a statement position", node)

    def _block(self, statements: list[dict]) -> None:
        self.scopes.append({})
        try:
            for statement in statements:
                self._exec(statement)
        finally:
            self.scopes.pop()

    def _var_decl(self, node: dict) -> None:
        vtype = node["var_type"]
        name = node["name"]
        if vtype == "void":
            raise RunError("E201", "A variable cannot have type void", node)
        if name in self.scopes[-1]:
            raise RunError("E302", f"'{name}' is already declared in this scope", node)
        init = node.get("init")
        if init is None:
            value = default_value(vtype)
        else:
            value = self._eval(init)
            value = coerce(value, type_name(value), vtype, node)
        self.scopes[-1][name] = [vtype, value]
        if not self._trace_full:
            shown = f"declare {vtype} {name}"
            if init is not None:
                shown += f" = {expr_text(init)}"
            self._record(node, shown, f"{name} = {to_text(value)}")

    def _assign(self, node: dict) -> None:
        name = _target_name(node["target"])
        op = _norm(node.get("op", "="))
        entry = self._lookup(name, node)
        vtype, old = entry

        if op in ("++", "--"):
            if not is_number(old):
                raise RunError("E202", f"'{op}' only works on int and float variables", node)
            new = binary_op("+" if op == "++" else "-", old, 1, node)
            new = coerce(new, type_name(new), vtype, node)
            shown = f"{name}{op}"
        else:
            value = self._eval(node["value"])
            if op != "=":
                value = binary_op(op[:-1], old, value, node)
            new = coerce(value, type_name(value), vtype, node)
            shown = f"{name} {op} {expr_text(node['value'])}"

        entry[1] = new
        if not self._trace_full:
            self._record(node, shown, f"{name} = {to_text(new)}")

    def _expr_stmt(self, node: dict) -> None:
        expr = node["expr"]
        value = self._eval(expr)
        if expr.get("type") != "Call" and not self._trace_full:
            result = "done" if value is None else to_text(value)
            self._record(node, f"evaluate {expr_text(expr)}", result)

    def _if(self, node: dict) -> None:
        value = self._condition(node["cond"])
        otherwise = node.get("otherwise")
        if not self._trace_full:
            if value:
                outcome = "true → run then branch"
            elif otherwise is not None:
                outcome = "false → run else branch"
            else:
                outcome = "false → skip"
            self._record(node, f"if ({expr_text(node['cond'])})", outcome)
        if value:
            self._exec(node["then"])
        elif otherwise is not None:
            self._exec(otherwise)

    def _while(self, node: dict) -> None:
        while True:
            self._tick(node)
            value = self._condition(node["cond"])
            if not self._trace_full:
                outcome = "true → run loop body" if value else "false → exit loop"
                self._record(node, f"while ({expr_text(node['cond'])})", outcome)
            if not value:
                break
            try:
                self._exec(node["body"])
            except _LoopSignal as signal:
                if signal.keyword == "break":
                    break

    def _for(self, node: dict) -> None:
        self.scopes.append({})
        try:
            if node.get("init") is not None:
                self._exec(node["init"])
            while True:
                self._tick(node)
                cond = node.get("cond")
                value = self._condition(cond)
                if not self._trace_full:
                    shown = f"for ({expr_text(cond)})" if cond is not None else "for (no condition)"
                    outcome = "true → run loop body" if value else "false → exit loop"
                    self._record(node, shown, outcome)
                if not value:
                    break
                try:
                    self._exec(node["body"])
                except _LoopSignal as signal:
                    if signal.keyword == "break":
                        break
                if node.get("step") is not None:
                    self._exec(node["step"])
        finally:
            self.scopes.pop()

    # -- expressions

    def _eval(self, node: dict) -> Any:
        kind = node.get("type")
        if kind == "Literal":
            return _literal_value(node)
        if kind == "Var":
            return self._lookup(node["name"], node)[1]
        if kind == "Binary":
            return self._binary(node)
        if kind == "Unary":
            return unary_op(node["op"], self._eval(node["operand"]), node)
        if kind == "Convert":
            return convert(node["target_type"], self._eval(node["expr"]), node)
        if kind == "Call":
            return self._call(node)
        raise RunError("E401", f"Cannot evaluate {kind}", node)

    def _binary(self, node: dict) -> Any:
        op = _norm(node["op"])
        if op in ("&&", "||"):
            left = self._eval(node["left"])
            _need_bool(left, op, node)
            if op == "&&" and not left:
                return False
            if op == "||" and left:
                return True
            right = self._eval(node["right"])
            _need_bool(right, op, node)
            return right
        return binary_op(op, self._eval(node["left"]), self._eval(node["right"]), node)

    def _call(self, node: dict) -> None:
        name = node.get("name")
        args = node.get("args", [])
        if name != "print":
            raise RunError("E303", f"'{name}' is not a known function", node)
        if len(args) != 1:
            raise RunError("E204", f"print takes 1 argument, but {len(args)} were given", node)
        text = to_text(self._eval(args[0]))
        self.output.append(text)
        if not self._trace_full:
            self._record(node, f"print({expr_text(args[0])})", text)
        return None