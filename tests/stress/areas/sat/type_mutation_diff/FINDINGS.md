# Stress findings — `type_mutation_diff`

_Original heading: FINDINGS — `type_mutation_diff`_

# FINDINGS — `type_mutation_diff`

OpFuzz-style type-aware operator mutation + differential testing across ucas's own
proof paths (exhaustive / SAT / algebra-derivation / numeric-sampled) and across the
four frontends (plain CLI, `--json`, grouped MCP, `--flat` MCP).  All runs bounded
with `timeout`; binary `$ROOT/ucas` (not rebuilt).

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | zero-parameter inline `equiv` over JSON/MCP silently compares **stale** functions and retu… |
| NLP | 1 | NLP / ambiguity — the *same* zero-param inline `equiv` yields three different errors acros… |
| LIMIT | 2 | `equiv` reports a vacuous `equal:true` with an "exhaustive proof" on a domain with **zero*… |

## Findings

### WRONG-1 — zero-parameter inline `equiv` over JSON/MCP silently compares **stale** functions and returns a fabricated counterexample
**Severity:** WRONG
**Why it matters:** _not recorded_
**Reproducer:**
Repro** (input file `bug_zeroparam_stale.jsonl`):

```sh
cd $ROOT/tests/stress/areas/sat/type_mutation_diff
timeout 15 $ROOT/ucas --json < bug_zeroparam_stale.jsonl
```

**Observed:** (id 2 — note `ucas` claims two *identical* zero-param functions):

```json
{"id": 2, "ok": true, "cmd": "equiv", "ucas": "it() = 3 ^ 5 & 1\nthat() = 3 ^ 5 & 1\nequiv it that", "structured": true, "result": {"kind": "equiv", "equal": false, "exhaustive": true, "mismatch_points": 1701, "method": "exhaustive", "counterexample": "x=1, y=1: 2 vs 0"}, "notes": [], "conditions": [], "checks": [], "files": [], "text": "it and that differ at 1701 points, e.g. x=1, y=1: 2 vs 0\n"}
```

The `counterexample` is `x=1, y=1: 2 vs 0`, a 2-parameter witness that can only
come from request 1 (`it = x << y`, `that = x >> y`).  The user asked to compare a
function **to itself**; the answer `equal:false` and the counterexample are bogus.

Same wrong result over **both** MCP frontends (grouped and `--flat`), so this is not
a JSON-only artifact:

```sh
# grouped MCP — id 2 returns equal:false, mismatch_points:1701, counterexample x=1,y=1:2 vs 0
timeout 15 $ROOT/ucas --mcp < bug_zeroparam_stale.jsonl
timeout 15 $ROOT/ucas --mcp --flat < bug_zeroparam_stale.jsonl
```

**Root cause (observable behaviour):** for an inline `{"body":...,"params":[]}` the
tool emits the temp names `it()` / `that()`.  These cannot be (re)defined cleanly —
`it` is also parsed as `i*t` — so when a *previous* request in the session already
bound `it`/`that`, the new definitions are ignored and `equiv it that` compares the
old functions.  With same-arity, non-empty params the redefinition works (verified),
so the corruption is specific to zero-parameter bodies and to multi-request sessions.

**Expected:** `equal:true`, `mismatch_points:0`, no counterexample; a self-comparison
must never be refuted.  **Severity:** WRONG (unsound answer with a fabricated witness).

### NLP-1 — NLP / ambiguity — the *same* zero-param inline `equiv` yields three different errors across frontends / session states
**Severity:** NLP
_Original classification: `NLP / ambiguity`._
**Why it matters:** _not recorded_
**Reproducer:**
Repro** (fresh session, input file `bug_zeroparam_fresh.jsonl`):

```sh
timeout 15 $ROOT/ucas --json < bug_zeroparam_fresh.jsonl
```

**Observed:** (JSON, fresh session):** `ok:false`, an ambiguity error on the auto-name:

```json
{"error": {"code": "ambiguous", "message": "'it' read as i*t (single-letter variables)", "key": "juxtaposition", ...}}
```

Adding `"defaults": true` to the *same* request instead gives a **different** error —
a plain `parse_error` "expected an expression" at `<json>:3:14`.  Plain CLI with a
user-named zero-param function gives yet another error:

```sh
printf '%s\n' 'r() = 3 ^ 5 & 1' 's() = 3 ^ 5 & 1' 'equiv r s' | timeout 15 $ROOT/ucas
# <stdin>:1:10: error: expected an expression
#     equiv r s
```

And the *identical* JSON request succeeds (`ok:true, equal:true`) if any earlier
successful inline `equiv` with typed params is in the session (see WRONG above).
**Expected:** one well-typed request should have one deterministic outcome.  Instead
the outcome and error `code` depend on frontend and prior session state.

### LIMIT-1 — `equiv` reports a vacuous `equal:true` with an "exhaustive proof" on a domain with **zero** defined points
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
printf '%s\n' \
 'd(x: u8, y: u8) = x / (y - y)' \
 'e(x: u8, y: u8) = x' \
 'domain d' 'equiv d e' \
 | timeout 15 $ROOT/ucas
```

**Observed:** `domain d` says "requires 0 != 0", "defined at 0 of 65536 points",
"C undefined behaviour at 65536 points", yet `equiv d e` prints
`d and e are equal on the domain of d (exhaustive)` with
`{equal:true, exhaustive:true, mismatch_points:0, proof.kind:exhaustive}`.
Reversing the arguments (`equiv e d`) correctly reports 65536 mismatches, so this
is the documented "domain of the first argument" rule taken to an empty set.  The
claim "equal" backed by an "exhaustive proof over every point" is vacuous and can
mislead a differential-testing oracle.  **Severity:** LIMIT (design choice, not a
contradiction, but unsafe as an oracle).

### LIMIT-2 — `^` is context-sensitive (xor next to bitwise ops, power otherwise); both readings only surface as `notes`
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`3 ^ 5 & 1` is parsed as xor ("note: ... read as xor, not power"), while `x ^ y`
is parsed as power ("note: '^' is power; use 'xor'").  This is signalled only in
`notes`, not in the structured result, so a mutation that flips `xor`→`^` can
silently change meaning.  Not a crash; flagged as a LIMIT for mutation campaigns.

## Checks that passed

### Negative results (things checked that behaved correctly)
- No crash, hang, nonzero exit, or truncated JSON in any run (all returned 0).
- No u8-exhaustive vs u32-SAT/algebra disagreement on well-typed seeds/mutants.
  The only cross-width answer differences (`shl_ors`, `shl_roundtrip` on signed)
  were legitimate width/signedness semantics, not solver bugs.
- 16 near-identities (single-bit / off-by-one corruptions of De Morgan, carry-save,
  difference-of-squares, min/max sum, div-vs-shift, mod-2^32 polynomial identities)
  were all correctly refuted; SAT/algebra proofs of the true forms were sound.
- All 48 representative requests returned byte-identical `equal`/`method` across
  plain CLI, `--json`, grouped MCP and `--flat` MCP.
