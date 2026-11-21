"""Plain-language hints for FormaLang error codes.

A hint is a suggestion shown under a problem. It never replaces the compiler's
own message. Codes without an entry get no hint.
"""

HINTS: dict[str, str] = {
    "E101": "Close the string with a matching double quote on the same line.",
    "E102": "This character is not part of FormaLang. Remove it or check for a typo.",
    "E103": "Numbers look like 42 or 2.5. Remove extra dots or letters.",
    "E104": "Close the comment with */.",
    "E105": "Use only the escapes \\n, \\t, \\\\ and \\\".",
    "E201": "Check the types on both sides. Use int(x), float(x), string(x) or bool(x) to convert explicitly.",
    "E202": "This operator does not accept these types. Check the operands.",
    "E203": "Conditions must be bool. Compare with ==, <, > and similar, or use a bool variable.",
    "E204": "Pass exactly the number of arguments the function declares.",
    "E205": "Each argument must match its parameter type. An int can be passed where a float is expected.",
    "E206": "Add a return statement on every path through the function.",
    "E301": "Declare the variable before using it, with a type such as int x = 0;.",
    "E302": "Pick a new name, or remove one of the declarations.",
    "E303": "Only print and functions declared in this file can be called.",
    "E304": "break and continue only work inside while or for loops.",
    "E305": "return only works inside a function.",
    "E401": "The parser found a token it did not expect here. Check the statement just before it.",
    "E402": "Something is missing. Look just after the previous token.",
    "E501": "The divisor cannot be zero. Check the value you divide by.",
    "E502": "The number is too large for a 64-bit int. Use float for very large values.",
    "E503": "A function calls itself too many times. Check that the recursion has a stop condition.",
    "E504": "The loop never ends. Check that the loop condition eventually becomes false.",
}


def hint_for(code: str) -> str:
    return HINTS.get(code, "")