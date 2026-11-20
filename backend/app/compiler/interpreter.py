"""Tree-walking interpreter for the Phase 3 subset of FormaLang.

Runs the AST dicts from parser.py. Phase 3 runs: variable declarations,
assignment (= += -= *= /= ++ --), expressions, conversions, blocks and print().
Functions, if, while, for, return, break and continue arrive in later phases.
find_unsupported() detects them before anything runs, so a program never runs
halfway and then stops.

Runtime values are Python objects:
  int -> int, float -> float, bool -> bool, string -> str, void -> None

The checks here are a safety net. The Phase 4 semantic analyzer will report
most of these errors before the program runs.

Error codes raised here:
  E201 type mismatch          E202 invalid operands        E204 wrong argument count
  E301 undeclared identifier  E302 redeclared variable     E303 undefined function
  E501 division by zero       E502 numeric overflow
"""
from __future__ import annotations

import math

INT_MIN = -(2**63)
INT_MAX = 2**63 - 1

ARITHMETIC_OPS = {"+", "-", "*", "/", "%"}
RELATIONAL_OPS = {"<", "<=", ">", ">="}
EQUALITY_OPS = {"==", "!="}

# Constructs Phase 3 cannot run: node type -> (feature name, phase that adds it)
UNSUPPORTED = {
    "FuncDecl": ("functions", 6),
    "Return": ("return", 6),
    "If": ("if / else", 5),
    "While": ("while loops", 5),
    "For": ("for loops", 5),
    "Break": ("break", 5),
    "Continue": ("continue", 5),
}


class RunError(Exception):
    def __init__(self, code: str, message: str, node: dict) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.line = node["line"]
        self.col = node["col"]


# ---------------------------------------------------------------- values

def type_name(value) -> str:
    if value is None:
        return "void"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"


def is_number(value) -> bool:
    return type_name(value) in ("int", "float")


def default_value(var_type: str):
    return {"int": 0, "float": 0.0, "bool": False, "string": ""}[var_type]


def to_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)  # keeps the decimal point, e.g. 3.0
    return str(value)


def coerce(value, target: str, node: dict, name: str):
    """Value stored into a variable of type `target`. int widens to float; nothing else converts."""
    if target == "float" and type_name(value) == "int":
        return float(value)
    if type_name(value) == target:
        return value
    hint = ""
    if target == "int" and type_name(value) == "float":
        hint = " Use int(...) to convert explicitly."
    raise RunError(
        "E201",
        f"Type mismatch: '{name}' is {target}, but the value is {type_name(value)}.{hint}",
        node,
    )


# ------------------------------------------------------------- operators

def _checked_int(value: int, node: dict) -> int:
    if not INT_MIN <= value <= INT_MAX:
        raise RunError("E502", "Integer overflow: the result does not fit in a 64-bit int", node)
    return value


def _checked_float(value: float, node: dict) -> float:
    if not math.isfinite(value):
        raise RunError("E502", "Float overflow: the result is too large for a float", node)
    return value


def _trunc_div(a: int, b: int) -> int:
    """Integer division that rounds toward zero, as the spec requires."""
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _int_arith(op: str, a: int, b: int, node: dict) -> int:
    if op in ("/", "%") and b == 0:
        raise RunError("E501", "Division by zero", node)
    if op == "+":
        return _checked_int(a + b, node)
    if op == "-":
        return _checked_int(a - b, node)
    if op == "*":
        return _checked_int(a * b, node)
    q = _trunc_div(a, b)
    if op == "/":
        return _checked_int(q, node)
    return a - b * q  # %: the sign follows the dividend


def _float_arith(op: str, a: float, b: float, node: dict) -> float:
    if op == "/" and b == 0:
        raise RunError("E501", "Division by zero", node)
    if op == "+":
        result = a + b
    elif op == "-":
        result = a - b
    elif op == "*":
        result = a * b
    else:
        result = a / b
    return _checked_float(result, node)


def binary_op(op: str, a, b, node: dict):
    # string + anything concatenates; the other operand is converted to text
    if op == "+" and (isinstance(a, str) or isinstance(b, str)):
        if a is None or b is None:
            raise RunError("E202", "A void value cannot be used with '+'", node)
        return to_text(a) + to_text(b)

    if op in EQUALITY_OPS:
        same_kind = (is_number(a) and is_number(b)) or (
            type_name(a) == type_name(b) and type_name(a) in ("bool", "string")
        )
        if not same_kind:
            raise RunError("E202", f"Cannot compare {type_name(a)} with {type_name(b)}", node)
        equal = a == b
        return equal if op == "==" else not equal

    if op in RELATIONAL_OPS:
        if not (is_number(a) and is_number(b)):
            raise RunError(
                "E202",
                f"'{op}' compares numbers, but got {type_name(a)} and {type_name(b)}",
                node,
            )
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == ">":
            return a > b
        return a >= b

    if op in ARITHMETIC_OPS:
        if not (is_number(a) and is_number(b)):
            raise RunError(
                "E202",
                f"'{op}' needs numbers, but got {type_name(a)} and {type_name(b)}",
                node,
            )
        if op == "%" and not (type_name(a) == "int" and type_name(b) == "int"):
            raise RunError("E202", "'%' works only on two int values", node)
        if type_name(a) == "int" and type_name(b) == "int":
            return _int_arith(op, a, b, node)
        return _float_arith(op, float(a), float(b), node)

    raise RuntimeError(f"unknown operator {op}")


def unary_op(op: str, value, node: dict):
    if op == "-":
        if not is_number(value):
            raise RunError("E202", f"'-' needs a number, but got {type_name(value)}", node)
        if type_name(value) == "int":
            return _checked_int(-value, node)
        return -value
    # "!"
    if type_name(value) != "bool":
        raise RunError("E202", f"'!' needs a bool, but got {type_name(value)}", node)
    return not value


def convert(target: str, value, node: dict):
    """Explicit conversion: int(x), float(x), string(x), bool(x)."""
    if target == "string":
        if value is None:
            raise RunError("E202", "A void value cannot be converted to string", node)
        return to_text(value)
    if target == "bool":
        if type_name(value) == "bool":
            return value
        raise RunError("E202", f"Cannot convert {type_name(value)} to bool", node)
    if not is_number(value):
        raise RunError("E202", f"Cannot convert {type_name(value)} to {target}", node)
    if target == "int":
        if type_name(value) == "int":
            return value
        return _checked_int(math.trunc(value), node)  # truncates toward zero
    return float(value)  # target == "float"


# ----------------------------------------------------------- interpreter

class Interpreter:
    def __init__(self) -> None:
        self.scopes: list[dict] = [{}]  # each scope maps name -> (declared type, value)
        self.output: list[str] = []

    def run(self, program: dict) -> None:
        for stmt in program["body"]:
            self._exec(stmt)

    def _find_scope(self, name: str, node: dict) -> dict:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope
        raise RunError("E301", f"'{name}' is not declared", node)

    # ------------------------------------------------------- statements
    def _exec(self, node: dict) -> None:
        kind = node["type"]
        if kind == "VarDecl":
            self._var_decl(node)
        elif kind == "Assign":
            self._assign(node)
        elif kind == "ExprStmt":
            self._eval(node["expr"])
        elif kind == "Block":
            self._block(node)
        else:
            raise RuntimeError(f"statement {kind} is not handled in Phase 3")

    def _block(self, node: dict) -> None:
        self.scopes.append({})
        try:
            for stmt in node["body"]:
                self._exec(stmt)
        finally:
            self.scopes.pop()

    def _var_decl(self, node: dict) -> None:
        name, var_type = node["name"], node["var_type"]
        if name in self.scopes[-1]:
            raise RunError("E302", f"'{name}' is already declared in this scope", node)
        if var_type == "void":
            raise RunError("E201", "A variable cannot have type void", node)
        if node["init"] is None:
            value = default_value(var_type)
        else:
            value = coerce(self._eval(node["init"]), var_type, node, name)
        self.scopes[-1][name] = (var_type, value)

    def _assign(self, node: dict) -> None:
        name, op = node["target"], node["op"]
        scope = self._find_scope(name, node)
        var_type, current = scope[name]
        if op in ("++", "--"):
            if var_type not in ("int", "float"):
                raise RunError("E202", f"'{op}' works only on int and float variables", node)
            one = 1.0 if var_type == "float" else 1
            new = binary_op(op[0], current, one, node)
        elif op == "=":
            new = self._eval(node["value"])
        else:  # += -= *= /=
            right = self._eval(node["value"])
            new = binary_op(op[0], current, right, node)
        scope[name] = (var_type, coerce(new, var_type, node, name))

    # ------------------------------------------------------ expressions
    def _eval(self, node: dict):
        kind = node["type"]
        if kind == "Literal":
            return node["value"]
        if kind == "Var":
            return self._find_scope(node["name"], node)[node["name"]][1]
        if kind == "Unary":
            return unary_op(node["op"], self._eval(node["operand"]), node)
        if kind == "Binary":
            return self._binary(node)
        if kind == "Convert":
            return convert(node["target_type"], self._eval(node["expr"]), node)
        if kind == "Call":
            return self._call(node)
        raise RuntimeError(f"expression {kind} is not handled in Phase 3")

    def _binary(self, node: dict):
        op = node["op"]
        left = self._eval(node["left"])
        if op in ("&&", "||"):
            # short-circuit: the right side runs only when it can change the result
            if type_name(left) != "bool":
                raise RunError("E202", f"'{op}' needs bools, but got {type_name(left)}", node)
            if op == "&&" and not left:
                return False
            if op == "||" and left:
                return True
            right = self._eval(node["right"])
            if type_name(right) != "bool":
                raise RunError("E202", f"'{op}' needs bools, but got {type_name(right)}", node)
            return right
        right = self._eval(node["right"])
        return binary_op(op, left, right, node)

    def _call(self, node: dict):
        if node["name"] != "print":
            raise RunError("E303", f"Function '{node['name']}' is not defined", node)
        if len(node["args"]) != 1:
            raise RunError(
                "E204", f"print takes 1 argument, but got {len(node['args'])}", node
            )
        value = self._eval(node["args"][0])
        if value is None:
            raise RunError("E202", "A void value cannot be printed", node)
        self.output.append(to_text(value))
        return None


# ------------------------------------------------------- support scan

def _scan(node, found: list) -> None:
    if isinstance(node, list):
        for item in node:
            _scan(item, found)
        return
    if not isinstance(node, dict):
        return
    kind = node.get("type")
    if kind in UNSUPPORTED:
        feature, phase = UNSUPPORTED[kind]
        found.append((feature, phase, node))
    elif kind == "Call" and node["name"] != "print":
        found.append(("calls to user functions", 6, node))
    for value in node.values():
        _scan(value, found)


def find_unsupported(ast: dict):
    """(feature, phase, node) for the earliest construct this phase cannot run, or None."""
    found: list = []
    _scan(ast, found)
    if not found:
        return None
    return min(found, key=lambda item: (item[2]["line"], item[2]["col"]))