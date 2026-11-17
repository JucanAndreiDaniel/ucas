# Stress findings — `gates_find_cost`

_Original heading: FINDINGS — `gates_find_cost`_

# FINDINGS — `gates_find_cost`

Area: synthesis (`gates`), cheaper-implementation search (`find`), pricing
(`cost`, `model`, `mca`) and the matching MCP ops. All runs used the prebuilt
`$ROOT/ucas`, bounded by `timeout`. 227 isolated statements
plus 13 golden files were exercised; every golden was run twice and diffed
(no nondeterminism observed).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | deeply nested expression overflows the parser stack (CLI **and** MCP server) |
| NLP | 2 | documented `cost n` on a basis gate does not parse |
| LIMIT | 2 | `gates` silently caps at 6 input bits (clean error, worth noting) |

## Findings

### CRASH-1 — deeply nested expression overflows the parser stack (CLI **and** MCP server)
**Severity:** CRASH
_Original classification: `CRASH (high`._
**Why it matters:** _not recorded_
all subsequent requests on that connection are lost.

**Reproducer:**
Reproducer (CLI):
```sh
cd $ROOT/tests/stress/areas/sat/gates_find_cost
timeout 15 $ROOT/ucas crash_deep_expr.ucas > /tmp/deep.out 2>&1
echo $?   # 139
```
`crash_deep_expr.ucas` is `D(x: u32) = (((...((x+1)+1)...+1))` with 1600 nested
additions, followed by `cost D`. Regenerate with:
```sh
python3 - <<'EOF'
e = 'x'
for _ in range(1600): e = '(' + e + '+1)'
open('d.ucas', 'w').write('D(x: u32) = ' + e + '\ncost D\n')
EOF
```
The crash happens while *parsing the definition* — a file containing only the
definition (no `cost`/`show`) segfaults too, so it is not specific to pricing.

**Observed:** output:
```
/usr/bin/bash: line 1: ... Segmentation fault         timeout 15 $ROOT/ucas crash_deep_expr.ucas
EXIT=139
```
Only the echoed definition line (truncated) is printed before the signal.
Depth 1520 succeeds; depth 1550 and 1600 reliably segfault.

**MCP variant:** sending the same 1600-deep expression as `analyze` / `cost` `f`
makes the server process exit:
```
MCP tool "analyze" on server "ucas" failed: Connection closed: MCP server process exited
```
i.e. a single deeply nested request kills the JSON-RPC connection instead of
returning a `parse_error` / `domain_error` result.

**Expected:** either parse arbitrary-depth expressions, or fail with a clean
"expression too deep" diagnostic. A parser must not segfault on valid input,
and an MCP server must not die on one request.

### NLP-1 — documented `cost n` on a basis gate does not parse
**Severity:** NLP
_Original classification: `NLP / LIMIT (medium`._
**Expected:** _not recorded_
unreachable, so cost-sensitive minimality experiments on user bases can't be done.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/gates_find_cost
cat > basiscost.ucas <<'EOF'
basis b { and(x, y) = x & y cost 3 }
maj(a: bool, b: bool, c: bool) = a & b | a & c | b & c
gates maj basis b
EOF
timeout 10 $ROOT/ucas basiscost.ucas
```

**Observed:** output:
```
> basis b { and(x, y) = x & y cost 3 }
basiscost.ucas:1:29: error: 'cost' is not defined
    basis b { and(x, y) = x & y cost 3 }
                                ^
> gates maj basis b
basiscost.ucas:3:18: error: basis b has no gates
```

**Why it matters:** `README.md` §"Bases and exact synthesis" and `help` both
document `basis name { gate(x, y) = expr [cost n]; ... }`. The tokenizer does not
treat `cost` as a stop-word inside `parse_expr`, so `x & y cost 3` is read as
implicit multiplication with an undefined variable `cost`; `accept_kw(p,"cost")`
in `parse_basis` is never reached. Every gate in the basis is therefore left at
its default cost 1, and the documented feature is unusable.

### LIMIT-1 — `gates` silently caps at 6 input bits (clean error, worth noting)
**Severity:** LIMIT
_Original classification: `LIMIT (low; documented behaviour, recorded for completeness`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer / output:
**Observed:**
```
> gates (a: u1, b: u1, c: u1, d: u1, e: u1, f: u1, g: u1) = a & b
...: error: gates handles up to 6 input bits (7 here); exact synthesis beyond that needs SAT, not implemented yet
```
Exit 0, clean diagnostic — not a crash. See `10_degenerate.ucas`.

### NLP-2 — negative `find` op count is parsed as function application
**Severity:** NLP
_Original classification: `NLP / LIMIT (low`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer / output:
**Observed:**
```
> f(x: u8 in 0..15) = x*x
> find f -1
find 1: 1 point, computing in u8, costs from gt1030
  cost 0   1                                        constant
```
`find f -1` (and `find f +1`, `find f -2`) is parsed as `f(-1)` — a constant
application — rather than as `find f` with a negative budget. The user gets a
report about the constant `1` instead of an argument-range error. Exit 0.

### LIMIT-2 — MCP error-code inconsistency for an unknown µarch
**Severity:** LIMIT
_Original classification: `LIMIT (low`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
In `mcp_errors.out`, the same user mistake ("no such model") is classified
differently by sibling tools:
**Observed:**
**Reproducer:**
```sh
id 4  analyze/cost  model=nosuch   -> ok=false  error.code = "parse_error"   message "unknown model"
id 5  x86/mca       model=nosuch   -> ok=false  error.code = "failed"       message "unknown x86 µarch 'nosuch' (skl skx glc rpl zen4 x86v2 x86v3 x86v4)"
```
Both are clean errors and the CLI prints a normal `error:` line, but clients
that branch on `error.code` will treat these two identical mistakes differently.

## Checks that passed

### Non-findings (checked, no bug)
- **No false minimality claims found.** `gates` exhaustive bounds ("no program of
  cost <= N exists") held across bases `c`, `spirv`, `a64`, `a64sha`, `x86bmi`,
  `avx512`, `nand`, custom LUT-2/LUT-3 bases and incomplete bases. Superset
  bases never produced a higher minimal cost; NPN-equivalent 4-input functions
  under a LUT-3 basis always got the same cost. `gates npn` proved all 222
  classes minimal. When the node budget / `max` is hit, the tool correctly
  reports "an upper bound, not proved minimal" rather than claiming minimality.
- **No wrong cost ordering found.** `mca` simulated cycles were >= every stated
  bound (critical path / ports / front end) across 117 function×µarch pairs;
  `cost` and `find` used the same active-model prices, and zero-cost models
  behaved consistently (no hangs, no negative prices accepted).
- **No nondeterminism found.** Every golden was produced twice under
  `timeout 30` and the two outputs `diff`ed identically, including `find`
  (`more`, `stoke` with its fixed default seed 1), `cost`, `gates` and `mca`,
  in both CLI and MCP (`--mcp` and `--mcp --flat`) modes.
- **No hangs found.** Every one of 227 isolated statements finished within its
  `timeout 12` bound; exhaustive `find` searches stop at the documented term
  bank (e.g. 1048576 / 65536 columns) and report "'more' continues".
- Malformed inputs (unknown basis, unknown model, >6 inputs, empty ranges,
  non-bit parameters, missing snippet files, negative/fractional op counts)
  all returned clean `error:` diagnostics with exit 0, never a crash.
