# Stress findings — `snippets_db`

_Original heading: FINDINGS — `find F snippets` / `snippets grow` / the `.snip` database_

# FINDINGS — `find F snippets` / `snippets grow` / the `.snip` database

All commands below run from `$ROOT/tests/stress/areas/systems/snippets_db`.
The binary is `$ROOT/ucas`. All goldens were run twice and
`diff`ed; every golden in this folder is deterministic. No crash, hang, or
file written outside this folder was observed (path-like snippet names are
rejected by the identifier lexer, see LIMIT-2).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 4 | 1 — a named `find ... snippets NAME` pollutes the session database; the next unnamed `find… |
| LIMIT | 3 | 1 — only one unnamed session database is kept; each `snippets grow` overwrites the previou… |

## Findings

### WRONG-1 — 1 — a named `find ... snippets NAME` pollutes the session database; the next unnamed `find ... snippets` uses the wrong DB
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**
Reproducer (copy-paste):

```sh
cd $ROOT/tests/stress/areas/systems/snippets_db
printf 'f(a: u32, b: u32) = a + b\nfind f 1 snippets fx_freevar\nfind f 1 snippets\n' > /tmp/pollute.ucas
timeout 30 $ROOT/ucas /tmp/pollute.ucas
```

**Observed:** (exact):

```
> f(a: u32, b: u32) = a + b
> find f 1 snippets fx_freevar
find f: 1024 points (sampled; matches verified on the whole domain), computing in u32, costs from gt1030
  snippet database: its program with these values reads an input f does not have
  cost 1   a + b                                    exact (proved by SAT)
  [searched every term up to cost 1: 106 distinct columns; 'more' continues]
> find f 1 snippets
find f: 1024 points (sampled; matches verified on the whole domain), computing in u32, costs from gt1030
  snippet database: its program with these values reads an input f does not have
  cost 1   a + b                                    exact (proved by SAT)
  [searched every term up to cost 1: 106 distinct columns; 'more' continues]
```

Baseline (same function, no named lookup first) gives the correct built-in result:

```
  cost 1   a + b                                    the snippet database's program with these values (cost 1 under gt1030, where it was grown) (proved by SAT)
```

**Why it matters:** `snip_lookup()` calls `sd_read(name, 0)` for a named file and
leaves that file in the single global `SD`. On the next *unnamed* lookup, the
guard at `src/find.c:3229` only checks `SD.ready`, `nin`, width and model — not
whether `SD` came from a `snippets grow` session DB or from a transient named
find. `fx_freevar.snip` has 3 inputs, so the 2-parameter `f` passes the shape
guard, the matching entry's `var 2` cannot be built for `f`, and the user is
told "reads an input f does not have" instead of being shown the built-in
`gt1030_2x32` program. The same pollution makes a later unnamed find report
"differs from ... elsewhere" (after `fx_dupbad`) or "not consulted: it holds
programs of 1 input" (after `fx_rbadhash`). Reproduced in full by
`19_session_pollution.ucas` / `19_session_pollution.out`.

### WRONG-2 — 2 — duplicate hashes: only the first entry with a hash is considered, shadowing a correct program
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/snippets_db
timeout 30 $ROOT/ucas 11_custom_collision.ucas
```

`fx_dupbad.snip` contains, in this order:

```
var 0 1e671d01eb94396b
var 1 60f717a89d4dc72e
xor 0 1 f55dafd40e91123c
add 0 1 f55dafd40e91123c
```

Both level-1 entries carry the hash of `a + b`; the `xor` comes first.
**Observed:** for `find c1 1 snippets fx_dupbad` (c1 = `a + b`):

```
  snippet database: its program with these values, a xor b, differs from c1 elsewhere (32 points do not tell them apart)
  cost 1   a + b                                    exact (proved by SAT)
```

With the same two entries swapped (`fx_dupgood.snip`), the correct program is
found and the message is the normal "the snippet database's program ...".
**Why it matters:** `sd_index()`/`snip_lookup()` stop at the *first* entry whose
hash equals the query hash (`src/find.c:3290`). A correct program with the
same hash later in the file is never tried. A real grown database is unlikely
to collide under FNV-1a, but the loader accepts hand-written/duplicated files
without checking hash uniqueness, so the lookup can silently pick a wrong
program and report a spurious "differs elsewhere". Also silently changes the
outcome of the `c2(a: u32) = a + 0` probe in the same golden.

### WRONG-3 — 3 — malformed `levels` lines are accepted and produce a false "cost N under M, where it was grown" claim
**Severity:** WRONG
**Expected:** _not recorded_
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/systems/snippets_db
timeout 30 $ROOT/ucas 13_custom_cost.ucas
```

`fx_lvlcost.snip` has `levels 0 0 0 0 3`; `fx_declevels.snip` has
`levels 9 5 3` (non-monotonic, does not start at 0). Observed for
`w1(a: u32, b: u32) = a + b`:

```
  cost 1   a + b    the snippet database's program with these values (cost 3 under gt1030, where it was grown) (proved by SAT)
  cost 1   a + b    the snippet database's program with these values (cost 0 under gt1030, where it was grown) (proved by SAT)
```

**Why it matters:** the displayed match cost (`icost` under the active model) is
1 in both cases, while the "why" string claims cost 3 and cost 0 respectively.
`sd_read()` never validates that `lvl[0] == 0` or that levels are non-decreasing,
and `snip_lookup()` derives the growth cost `k` from those unchecked numbers.
The same false claim appears for a u32 DB consulted by an `i32` function
(`cost 1   i32(u32(a) + 1) ... (cost 0 under gt1030, where it was grown)`).

### WRONG-4 — 4 — a binary operation with a missing operand is silently accepted as `op X X`
**Severity:** WRONG
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/systems/snippets_db
timeout 30 $ROOT/ucas 13_custom_cost.ucas
```

`fx_bin1op.snip` contains the 3-word entry `add 0 f55dafd40e91123c` (a binary
`add` with only one operand). Observed for `find w1 1 snippets fx_bin1op`:

```
  snippet database: its program with these values, a + a, differs from w1 elsewhere (32 points do not tell them apart)
  cost 1   a + b                                    exact (proved by SAT)
```

**Why it matters:** the parser accepts a 3-word named entry with an arity-2
operation because `b` defaults to 0 (`src/find.c:3018-3034`), so `add 0` is
interpreted as `add 0 0` = `a + a`, producing a bogus "differs elsewhere"
message.
**Expected:** reject a 3-word entry whose operation has arity 2 (or reject
the defaulted operand). CRLF, blank lines, tabs and NUL bytes are handled with
clean diagnostics, so this one silent-acceptance path stands out.

### LIMIT-1 — 1 — only one unnamed session database is kept; each `snippets grow` overwrites the previous one
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/systems/snippets_db
timeout 30 $ROOT/ucas 14_grow_session.ucas
```

The file grows DBs for 1x8, 1x16, 2x8, 3x8 and 1x32 in that order, then:

```
> find u1 1 snippets
find u1: 256 points, computing in u8, costs from gt1030
  snippet database: none in this session for 1 input of 8 bits under gt1030, and no snippets/gt1030_1x8.snip (`make snippets` grows those snippets/grow.ucas lists)
```

**Expected:** /clarification: the README says the unnamed database "lives for the
session"; in practice `sd_from_bank()` replaces the single global `SD`, so
only the last-grown shape is retained. Not unsound, but surprising and it makes
multi-shape session workflows silently fall back to the built-in folder.

### LIMIT-2 — 2 — Unicode identifiers are rejected (CLI and MCP); path-like snippet names are rejected
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (CLI):

```sh
printf 'snippets grow \316\251 inputs 1 width 8 cost 1 seconds 0.2\n' > /tmp/u.ucas
timeout 10 $ROOT/ucas /tmp/u.ucas
```

**Observed:**

```
/tmp/u.ucas:1:15: error: unexpected character '?'
    snippets grow Ω inputs 1 width 8 cost 1 seconds 0.2
                  ^
```

A Unicode function name (`fΩ(a: u32) = a + 1`) gets the same lexer error at the
character. Over MCP, `session/define` with `"name":"fΩ"` returns
`bad_request: name: a name`. No crash on either path (an earlier transient
MCP "Connection closed" was a harness restart, reproduced cleanly on the wire).

Path-like names are also refused, so no file can be written outside the
working folder: `./inside` → `unexpected character '.'`; `../escape` →
`unexpected '..' after the statement`; `a-b` → `unexpected '-' after the
statement`. Plain names (`inside`, `bogus`) write `NAME.snip` in the cwd only.

### LIMIT-3 — 3 — out-of-range `const` values in a `.snip` file are silently accepted
**Severity:** LIMIT
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/systems/snippets_db
grep -A4 'fx_consthuge' 09_malformed_entries.out
timeout 30 $ROOT/ucas 09_malformed_entries.ucas
```

`fx_consthuge.snip` line 3 is `const 99999999999999999999999 0000000000000000`.
**Observed:** no error, the file loads and the lookup reports
`no program up to cost 0 has its values (1 programs of 2 inputs, 32 bits, ...)`.
`sscanf("%lld")` overflows and the wrapped/truncated value is stored as a
constant.
**Expected:** range-check the constant against the declared width.
`var 2` in a 2-input file (`fx_varidx3`) is likewise accepted at load time.

## Checks that passed

### Behaviours checked and found correct (no finding)
- Empty file, header-only, bad version/points/inputs/width, missing/garbage
  header, 0/1 levels entries, negative/huge/70-entry levels, wrong word counts,
  unknown op, forward/self references, bad `var`/`const` text, negative/huge
  operands, blank lines, CRLF, tab separators, NUL bytes, 400-byte lines — all
  produce clean diagnostics (goldens `07`, `08`, `09`).
- `snippets grow` argument validation (inputs 0/4, width 7/64, cost 0/31,
  seconds 0/121/1e30, no args, reordered options, repeated `fresh`), resume,
  `fresh`, shape mismatch, bad hash, unknown leaf, levels mismatch — all
  diagnosed (goldens `15`, `16`, `17`).
- Wrong parameter counts / widths / signedness, float functions, undefined at
  sample points, no-file names, extra tokens — all handled (goldens `05`,
  `06`, `18`).
- Named `grow` under MCP is refused with a clear message (by design,
  `src/find.c:3110`) — `mcp_snippets.out`, call id 4.
- Determinism: every CLI golden and the MCP golden were run twice and diffed;
  no ordering/cost drift was seen.
