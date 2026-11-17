# Stress findings — `syntax_weird`

_Original heading: FINDINGS — `syntax_weird`_

# FINDINGS — `syntax_weird`

Area: valid-but-unusual syntax (chained comparisons, Unicode, tables, `match`,
`where`, semicolons/comments, implicit multiplication, `?:`, `in`-ranges,
`mod`/`%`, `and`/`or`/`not` vs `&&`/`||`/`!`).
All commands below were run with `timeout 15` against
`$ROOT/ucas`. No CRASH, HANG, or nondeterminism was found;
the issues are WRONG answers and parse limitations.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | inline annotation at expression head silently corrupts the expression |
| LIMIT | 9 | leading unary `!` is rejected; `not` / parenthesized `!` work |

## Findings

### WRONG-1 — inline annotation at expression head silently corrupts the expression
**Severity:** WRONG
**Why it matters:** _not recorded_
An annotation `(x: T)` / `(x: T in a..b)` written before an anonymous expression
is *not* treated as a parameter declaration: it becomes a value (`T(x in a..b)`)
that is juxtaposed into the body (implicit multiplication), or hijacks a
`match` scrutinee. The returned function is different from the one written.

**Reproducer:**
Reproducer (CLI, stdin mode):

```sh
printf 'show (x: u8) 1 < x < 5\nrange (x: u8) x < 3 < 9\nrange (x: u8 in 0..10) x mod 2 == 0\n' | $ROOT/ucas
```

**Observed:**

```
  note: chained comparison read as a conjunction
_(x: u8) = x < x && x < 5
  -> bool
  note: chained comparison read as a conjunction
range of x*x < 3 -> bool:
  0..1   (2 distinct values)
  values: 0..1
  fits in u1
  over all 256 points of the domain
range of u8(x >= 0 && x <= 10)*x % 2 == 0 -> bool:
  0..1   (2 distinct values)
  values: 0..1
  fits in u1
  over all 256 points of the domain
```

**Expected:** `1 < x && x < 5`, `x < 3`, and `x % 2 == 0` restricted to x in 0..10.

More dramatic variant (the annotation's boolean becomes the `match` scrutinee,
so the pattern upper bound is coerced to `bool` and clamped to 1):

```sh
printf 'range match(x: u32 in 0..1000000) { 0..999999 => x, _ => 0 }\n' | $ROOT/ucas
```

**Observed:**

```
  note: literal 999999 does not fit bool; it becomes 1
range of t1 >= 0 && t1 <= 1 ? x : 0 where t1 = x >= 0 && x <= 1000000 -> u32:
  0..4294967295
  fits in u32
  sampled 65536 points (domain has 4294967296 points); not exhaustive
  sound bound (intervals): 0..4294967295
```

The same expression written with a proper named definition is correct:

```sh
printf 'f(x: u32 in 0..1000000) = match x { 0..999999 => x, _ => 0 }\nrange f\n' | $ROOT/ucas
# -> range of f -> u32:  0..999999
```

Also reproduces on the MCP wire (`analyze parse`, `args.expr = "(x: u8 in 0..10) x"`)
which returns `(u8(((x >= 0) && (x <= 10))) * x)`. Why: an inline annotation is a
*declaration* only when attached to a function definition; in a bare command
expression it is parsed as a value and silently multiplied into the body, so
the user's range/type clause is both misapplied and not ignored cleanly.

### LIMIT-1 — leading unary `!` is rejected; `not` / parenthesized `!` work
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'parse !a\nparse (!a)\nparse not a\nparse a && !b\n' | $ROOT/ucas
```

**Observed:**

```
<stdin>:1:7: error: unexpected '!' after the statement
    parse !a
          ^
(!(a != 0))
(!(a != 0))
((a != 0) && (!(b != 0)))
```

`!` in operand position (after `&&`, inside parens) is fine; only the first
token of the expression fails. Also fails for `range !x` and over MCP
(`analyze parse` with `expr: "!a"` returns `parse_error`). `not a` and `(!a)`
are valid equivalents, so this is a positional parser defect, not a grammar
rule. No `!` appears in any golden for this reason.

### LIMIT-2 — documented Unicode `∞` rejected (also `τ`, superscript `⁴`)
**Severity:** LIMIT
**Why it matters:** _not recorded_
The README documents `∞` as a limit/integral bound. It is rejected everywhere
as a token, reported as `?`:

**Reproducer:**
```sh
printf 'parse ∞\nlimit 1/x as x -> ∞\nintegrate exp(-x^2) from 0 to ∞\nparse x⁴\nparse 2π\nparse a ⊕ b\n' | $ROOT/ucas
```

**Observed:** (first four statements):

```
<stdin>:1:7: error: unexpected character '?'
    parse ∞
          ^
<stdin>:1:19: error: unexpected character '?'
    limit 1/x as x -> ∞
                      ^
<stdin>:1:31: error: unexpected character '?'
    integrate exp(-x^2) from 0 to ∞
                                  ^
<stdin>:1:8: error: unexpected character '?'
    parse x⁴
           ^
```

By contrast `π`, `⊕`, `°`, `²`, `³`, `≤`, `≥`, `≠`, `×`, `−`, `√` all parse
(golden `02_unicode.ucas`). `inf` and `oo` work as substitutes.
**Expected:** `∞`
accepted as documented, or documented as unsupported.

### LIMIT-3 — nested table cannot be double-indexed when the first index is a variable
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'parse [[1, 2], [3, 4]][i][j]\nparse [[1, 2], [3, 4]][i][0]\nparse [[1, 2], [3, 4]][1][j]\nparse [[1, 2], [3, 4]][1][0]\n' | $ROOT/ucas
```

**Observed:**

```
<stdin>:1:29: error: only a table [a, b, ...] can be indexed
    parse [[1, 2], [3, 4]][i][j]
                                ^
<stdin>:1:29: error: only a table [a, b, ...] can be indexed
    parse [[1, 2], [3, 4]][i][0]
                            ^
[3, 4][j]
3
```

A variable first index makes the second `[...]` fail even though the same
table with a constant first index works. A function using `T[i][j]` also fails
to define and then degrades to a free variable.

### LIMIT-4 — open bounds in `x in a..b` are rejected; failed definition leaks a free variable
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'q(x: int) = x where x in ..5\nr(x: int) = x where x in 5..\ns(x: int) = x where x in ..\nt(x: int) = x where x in (0..5)\n' | $ROOT/ucas
```

**Observed:** (one error per line, then `range q` analyses a free variable):

```
<stdin>:1:26: error: unexpected '..'
    q(x: int) = x where x in ..5
                             ^
<stdin>:1:29: error: expected an expression
    r(x: int) = x where x in 5..
                                ^
<stdin>:1:26: error: unexpected '..'
    s(x: int) = x where x in ..
                             ^
<stdin>:1:28: error: expected ')', found '..'
    t(x: int) = x where x in (0..5)
                               ^
```

Closed ranges and `{a, b, c}` value lists work (golden `08_where.ucas`).
After the parse error the name (`q`, `r`, ...) remains an undefined free
variable, so later commands silently analyse that instead of reporting the
failed definition.

### LIMIT-5 — trailing comma accepted in `match` arms but not in table literals
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'parse match x { 0 => 1, }\nparse [1, 2,][i]\n' | $ROOT/ucas
```

**Observed:**

```
((x == 0) ? 1 : undefined)
  note: match has no default arm: other values are outside the domain
<stdin>:1:13: error: unexpected ']'
    parse [1, 2,][i]
                ^
```

Same "trailing comma" syntax is accepted in one list construct and rejected
in the other.

### LIMIT-6 — `match` guard patterns rejected; piecewise `if` guards accepted
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'parse match x { n if n > 0 => n, _ => 0 }\nparse match x { 0 => 1, 1 => 2, 3.. => 4, _ => 5 }\nparse { x if x >= 0, -x otherwise }\n' | $ROOT/ucas
```

**Observed:**

```
<stdin>:1:17: error: expected a number in the pattern
    parse match x { n if n > 0 => n, _ => 0 }
                    ^
<stdin>:1:37: error: expected a number in the pattern
    parse match x { 0 => 1, 1 => 2, 3.. => 4, _ => 5 }
                                        ^
((x >= 0) ? x : (-x))
```

`match` patterns must be integer literals / ranges; guards and open-ended
range patterns (`3..`) are not supported, while the piecewise `{ e if cond, ...
otherwise }` form implements the same idea with guards.

### LIMIT-7 — duplicate and overlapping `match` arms silently accepted (dead arms, no warning)
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'parse match x { 0 => 1, 0 => 2, _ => 3 }\nparse match x { 0..5 => 1, 3..9 => 2, _ => 3 }\n' | $ROOT/ucas
```

**Observed:**

```
((x == 0) ? 1 : ((x == 0) ? 2 : 3))
(((x >= 0) && (x <= 5)) ? 1 : (((x >= 3) && (x <= 9)) ? 2 : 3))
```

The second `0 => 2` and the overlap `3..5` are unreachable. No note is emitted
(unlike the "no default arm" note). Likely harmless first-match semantics, but
"silently ignored clauses" are exactly what a syntax checker should flag.

### LIMIT-8 — `where` only binds to definitions; a second `where` is silently combined
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'parse x ? y : z where x in 0..3\nf(x: int) = x where x in 0..5 where x in 1..3\nrange f\n' | $ROOT/ucas
```

**Observed:**

```
<stdin>:1:17: error: unexpected 'where' after the statement
    parse x ? y : z where x in 0..3
                    ^
range of f -> int:
  1..3
  fits in u2
  over all 3 points of the domain
```

No way to attach a `where` clause to a bare expression in a command; two
`where` clauses on a definition are accepted and intersected with no note.

### LIMIT-9 — C-style `/* ... */` block comments are not recognized
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
printf 'parse 1 # ok\nparse 1 // ok\nparse 1 /* c */ + 2\n' | $ROOT/ucas
```

**Observed:**

```
1
1
<stdin>:1:10: error: unexpected '*'
    parse 1 /* c */ + 2
             ^
```

`#` (to end of line) and `//` work; `/* */` is read as operators, so a common
comment style is a parse error.

## Checks that passed

_No separate passed checks were recorded in the original document._
