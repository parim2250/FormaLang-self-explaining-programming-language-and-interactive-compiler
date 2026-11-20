# FormaLang Language Spec v0.1

## 1. Lexical structure (DFA-recognized)
Whitespace (space, tab, CR, LF) is ignored outside strings.

| Token      | Pattern                                             |
|------------|-----------------------------------------------------|
| IDENT      | [A-Za-z_][A-Za-z0-9_]*  (not a keyword)             |
| INT        | [0-9]+                                              |
| FLOAT      | [0-9]+ "." [0-9]+   (no exponent in v0.1)           |
| STRING     | "..." with escapes \n \t \\ \"  (single line)       |
| Keywords   | if else while for return break continue true false  |
| Type words | int float bool string void                          |
| Operators  | + - * / % = += -= *= /= ++ -- == != < <= > >= && || ! |
| Punct      | ( ) { } , ;                                         |
| Comments   | // to end of line,  /* ... */                       |

## 2. Grammar (EBNF)
program        = { top_level } ;
top_level      = func_decl | statement ;
func_decl      = type IDENT "(" [ param { "," param } ] ")" block ;
param          = type IDENT ;
block          = "{" { statement } "}" ;
statement      = block
               | var_decl ";"
               | assign_stmt ";"
               | if_stmt
               | while_stmt
               | for_stmt
               | return_stmt ";"
               | "break" ";"
               | "continue" ";"
               | expr ";" ;
var_decl       = type IDENT [ "=" expr ] ;
assign_stmt    = IDENT ( "=" | "+=" | "-=" | "*=" | "/=" ) expr
               | IDENT ( "++" | "--" ) ;
if_stmt        = "if" "(" expr ")" block [ "else" ( if_stmt | block ) ] ;
while_stmt     = "while" "(" expr ")" block ;
for_stmt       = "for" "(" [ var_decl | assign_stmt ] ";" [ expr ] ";" [ assign_stmt ] ")" block ;
return_stmt    = "return" [ expr ] ;
type           = "int" | "float" | "bool" | "string" | "void" ;
expr           = or_expr ;
or_expr        = and_expr { "||" and_expr } ;
and_expr       = equality { "&&" equality } ;
equality       = relational { ( "==" | "!=" ) relational } ;
relational     = additive { ( "<" | "<=" | ">" | ">=" ) additive } ;
additive       = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative = unary { ( "*" | "/" | "%" ) unary } ;
unary          = ( "-" | "!" ) unary | primary ;
primary        = INT | FLOAT | STRING | "true" | "false"
               | IDENT [ "(" [ args ] ")" ]
               | type "(" expr ")"          (* conversion, e.g. float(7) *)
               | "(" expr ")" ;
args           = expr { "," expr } ;

Note: a statement starting with `type IDENT` is a declaration. A statement
starting with `type "("` is a conversion expression. Two-token lookahead
resolves this (LL(2)).

## 3. Types
- int: 64-bit signed. float: IEEE double. bool. string. void (return only).
- Implicit: int -> float (assignment, arguments, return, mixed arithmetic).
- float -> int requires an explicit int(x) (truncates toward zero).
- string + any type concatenates; the other operand is converted to text.
- Text form: ints as "42"; floats always show a decimal ("1.0"); bools "true"/"false".
- / on two ints is integer division. % is int only.
- Comparisons < <= > >= are numeric only and return bool.
- == and != need compatible operands (int and float are compatible).
- && || ! require bool. No truthiness: if/while/for conditions must be bool.

## 4. Scope and functions
- Block scoped. Declare before use. Inner-scope shadowing is allowed.
- Same-scope redeclaration is an error.
- Functions are global. Top-level calls may precede the definition.
- No nested functions, no overloading. Parameters are passed by value.
- A non-void function that never returns a value is an error (E206).

## 5. Built-ins
- print(x): prints one value of type int, float, bool, or string. Returns void.

## 6. Error codes
- E1xx lexer:    E101 unterminated string, E102 unexpected character,
                 E103 malformed number, E104 unterminated block comment,
                 E105 invalid escape
- E2xx types:    E201 type mismatch, E202 invalid operands, E203 non-bool condition,
                 E204 wrong argument count, E205 argument type mismatch,
                 E206 return type mismatch / missing return
- E3xx scope:    E301 undeclared identifier, E302 redeclaration, E303 undefined function,
                 E304 break/continue outside loop, E305 return outside function
- E4xx syntax:   E401 unexpected token, E402 expected token (e.g. ';' or ')')
- E5xx runtime:  E501 division by zero, E503 call depth exceeded (200),
                 E504 execution step limit reached (1,000,000)

## 7. Out of scope for v0.1
Arrays, structs, classes, pointers, input(), imports, closures, ++/-- inside expressions.

## 8. Example
string greet(string name) {
    return "Hello, " + name + "!";
}
string language = "FormaLang";
float version = 1.0;
print(greet(language));
for (int i = 1; i <= 3; i++) {
    print("Step " + i);
}
// float version = "1.0";   -> E201 type mismatch: expected float, received string