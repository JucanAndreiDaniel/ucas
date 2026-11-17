# Stress findings — `cfront_preprocessor`

_Original heading: cfront_preprocessor — findings_

# cfront_preprocessor — findings

Area: the C frontend's preprocessor, exercised through `c lower`, `c optimize`
and the MCP tool `c`. Binary: `$ROOT/ucas` (already built, not
rebuilt). Reference C preprocessor: `cc -E -P` (`/usr/bin/gcc`).

All commands below run from
`$ROOT/tests/stress/areas/systems/cfront_preprocessor` unless stated.
Severity legend: `CRASH` | `HANG` | `WRONG` | `NLP` | `LIMIT` | `DETERMINISM`.

**Summary of the hunt:** 268 distinct C snippets were tried; 154 of them appear
in the 22 CLI goldens (`*.ucas`/`*.out`) and the MCP golden, the rest were
exploratory. No crash,
no hang and no nondeterminism was found; every one of the 22 CLI goldens and the
MCP golden was run twice and diffed identically (all exited 0). The five issues
below are two silent wrong-branch bugs and three conformance limits. For the
wrong cases the reproducer `.ucas` files are kept **without** a `.out` golden
(because the `.out` would enshrine incorrect lowered code); the test runner
skips `.ucas` files that have no matching `.out`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | 1 — `#if` ignores C's signed/unsigned arithmetic conversions (silent wrong branch) |
| LIMIT | 3 | 1 — `#if` does not short-circuit `&&` / `||` |

## Findings

### WRONG-1 — 1 — `#if` ignores C's signed/unsigned arithmetic conversions (silent wrong branch)
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_preprocessor
timeout 15 $ROOT/ucas bug_if_signed_unsigned.ucas
```

**Observed:** output (exact):

```
> c lower nofile
  w1(x: i32) = 111
  w2(x: i32) = 222
  w3(x: i32) = 111
  w4(x: i32) = 222
  w5(x: i32) = 222
```

**Expected:** `cc -E -P` on the same five `#if` expressions selects the other
branch in every case: `w1 = 222`, `w2 = 111`, `w3 = 222`, `w4 = 111`,
`w5 = 111` (gcc also warns that `9223372036854775808` is unsigned).

**Why it matters:** `cx_prim` (`src/cf_pp.c:704-756`) parses every integer
constant with `strtoull(..., 0)` and casts the result to `int64_t`, and `cx_bin`
(`:758-802`) does all arithmetic and comparisons in signed 64-bit. C's `#if`
evaluates in `intmax_t`/`uintmax_t` with the usual arithmetic conversions:
a `U`-suffixed constant (or one too large for `intmax_t`) has type `uintmax_t`,
so a negative operand is converted to the large unsigned value. Hence:

| expression | real C | ucas |
|---|---|---|
| `-1 < 1U` | false (222) | true (111) |
| `0xFFFFFFFFFFFFFFFF > 0` | true (111) | false (222, wraps to -1) |
| `-1 <= 0U` | false (222) | true (111) |
| `9223372036854775808 > 0` | true (111) | false (222) |
| `'\xff' < 0` | true (111) | false (222) |

The wrong branch is compiled with no diagnostic, so the lowered function is
silently wrong. `c optimize` goes through the same preprocessor (confirmed). A
single-case reproducer is also available as `t51`-style input; the batched file
above covers all five.

### WRONG-2 — 2 — `//` comments do not observe backslash-newline splicing
**Severity:** WRONG
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_preprocessor
timeout 15 $ROOT/ucas bug_comment_splice.ucas
```

`bug_comment_splice.ucas` contains:

```c
c lower nofile
```c
int w6(int x){
  // a comment \
  return 111;
  return 222;
}
```
```

**Observed:** output (exact):

```
> c lower nofile
  w6(x: i32) = 111
```

**Expected:** `cc -E -P` leaves only `return 222;`, i.e. `w6(x) = 222`.

**Why it matters:** translation phase 2 splices backslash-newline *before
comments are recognised. The source is therefore one comment
`// a comment \  return 111;` followed by a live `return 222;`. In the frontend's
`lex_file` (`src/cf_pp.c:150-271`) the `\\\n` case (`:170-181`) is only reached
when the backslash is scanned at top level; the `//` branch (`:187-192`) consumes
up to the first `\n` and ignores the preceding backslash. The `return 111;`
line is compiled instead of being commented out. This is a second mechanism for
silently dropping a preprocessor condition / picking the wrong code.

### LIMIT-1 — 1 — `#if` does not short-circuit `&&` / `||`
**Severity:** LIMIT
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_preprocessor
timeout 15 $ROOT/ucas bug_if_shortcircuit.ucas
```

**Observed:** output (exact):

```
> c lower nofile
error: <block>:3:1: #if: cannot evaluate the expression
```

**Expected:** `f(x) = 111` — `cc -E -P` accepts `#if 1 || (1/0)` and emits
`return 111;`; likewise `#if 0 && (1/0)` emits `return 222;`.

**Why it matters:** it is a limit:** `cx_bin` (`src/cf_pp.c:758-802`) evaluates both operands
before applying `&&`/`||`. The division by zero on the dead right-hand side sets
`c->err`, so `pp_ifexpr` reports "cannot evaluate the expression" and the whole
translation unit is rejected. Valid C that relies on short-circuiting is lost
(hard error, not a wrong value).

### LIMIT-2 — 2 — `__LINE__` and `__FILE__` are not predefined
**Severity:** LIMIT
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_preprocessor
timeout 15 $ROOT/ucas bug_line_file_missing.ucas
```

**Observed:** output (exact):

```
> c lower nofile
error: <block>:2:35: '__LINE__' is not declared
```

(`__FILE__` fails identically: `'__FILE__' is not declared`.)

**Expected:** both are standard C99 predefined macros; `__LINE__` should expand
to the current source line and `__FILE__` to a string literal.

**Why it matters:** it is a limit:** the predefine table in `cf_preprocess`
(`src/cf_pp.c:1265-1275`) lists `__STDC__`, target feature macros and
`__SIZEOF_*`/`__ORDER_*`, but not the four standard `__LINE__`, `__FILE__`,
`__DATE__`, `__TIME__`. Valid C using them fails to lower.

### LIMIT-3 — 3 — `#line` is accepted but has no effect on diagnostics
**Severity:** LIMIT
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/cfront_preprocessor
timeout 15 $ROOT/ucas bug_line_ignored.ucas
```

**Observed:** output (exact):

```
> c lower nofile
error: <block>:2:40: 'undeclared_symbol' is not declared
```

**Expected:** after `#line 500 "generated.c"` a C compiler reports
`generated.c:500` (the following line). ucas still prints `<block>:2:40`.

**Why it matters:** it is a limit:** `process` (`src/cf_pp.c:1213-1215`) explicitly skips
`#line` without updating any line/file state. Consistent with LIMIT-2 (there is
no `__LINE__` to change either), but diagnostic line remapping is lost.

## Checks that passed

### Constructs verified to work (no issue)
The goldens cover and confirm correct handling of: object macros and macro
chaining (`01`, `02`); function-like macros, nested/argument prescan (`03`,
`21`, `22`); `#ifdef`/`#ifndef`/`#elif`/`#else` and `defined()` (`04`, `05`);
stringification, token pasting (including empty arguments), `__VA_ARGS__`
(`06`, `07`); known system-header preludes and unknown-header skipping, plus
real local `#include` with include guards (`08`, `19`); `#pragma`, `#warning`,
`#error` in dead branches (`09`); backslash line continuations (`10`); block
and line comments inside/around macros (`11`); recursive macros (`#define X X`)
and `#undef` producing clean errors rather than hangs (`12`, `13`);
`#if 0` hiding syntactically invalid C (`17`); target predefined macros
(`18`); macros expanding to statements and to `if/else` (`16`); conditional
compilation removing a division-by-zero guard (`15`). Stress cases of 200-level
macro chains, 2000-token `#if` expressions and 2000 macro expansions all
finished in under a second; 300 nested `#if`s produced the clean guard message
`#if nested too deeply`.

There is deliberately **no** golden for the five bug reproducers, since their
observed output is incorrect; they are documented here with exact commands and
output instead.
