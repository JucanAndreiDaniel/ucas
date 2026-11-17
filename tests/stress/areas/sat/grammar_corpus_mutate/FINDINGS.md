# Stress findings — `grammar_corpus_mutate`

_Original heading: FINDINGS — `grammar_corpus_mutate`_

# FINDINGS — `grammar_corpus_mutate`

Area: seeded AFL-style grammar-aware corpus mutation of `tests/*.ucas` sources
(identifier renaming + tree mutations + operator/type/boundary-literal dictionary).
Binary: `$ROOT/ucas` (not rebuilt).  All fuzz runs were bounded
with `timeout 10`; every would-be golden was generated twice and diffed.  Work
stayed inside this folder; `tests/*.ucas` seeds were only ever read.

Tooling left runnable in this folder:

- `mutate.py gen --count N --seed S` — deterministic corpus generator
  (seeding, `v0..` renaming, `ts-del/swap/shrink/dup/ins/kdel/kins/stutter`,
  fence-body `ts-fdel/fdup/fins/fbreak`, `ts-wrap`).
- `run_fuzz.py --timeout 10` — runs every mutant, de-dups by
  (exit-code class, first significant output line) into `_scratch/anomalies.jsonl`.
- `reduce.py --id I --corpus S --expect HANG|CRASH|'substring' --timeout T` —
  ddmin over source lines.
- `semantic_hunt.py --count N --seed S` — same-result-type differential
  (`equiv` verdict vs. `show` at boundary literals).

Campaigns: 240 mutants (`0x5EED`) + 300 (`0xC0FFEE`) + 300 (`0xBADF00D`) =
**840 grammar mutants**, plus **160** semantic-differential function pairs.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | CRASH (pre-existing, inherited seed — not produced by mutation) |
| HANG | 1 | 6 mutants overrun `timeout 10`; inherited from a heavy seed, not a new hard hang |
| WRONG | 1 | bigint-scale `int` result: `equiv` claims exhaustive equality, and `domain`/`range` contra… |

## Findings

### WRONG-1 — bigint-scale `int` result: `equiv` claims exhaustive equality, and `domain`/`range` contradict `show`
**Severity:** WRONG
**Discovered by** `semantic_hunt.py` (a grammar-mutated f/g pair from boundary
literal `2^63`), minimised by hand to three statements.  Severity: WRONG.

**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/sat/grammar_corpus_mutate
timeout 30 $ROOT/ucas 01_bigint_vacuous_equiv.ucas
```

**Observed:** (`01_bigint_vacuous_equiv.out`, exact):

```
> f(x: u8) = 2^63
> g(x: u8) = x
> show f(0)
_() = 2^63
  -> int
> show g(0)
_() = 0
  -> u8
> show f(1)
_() = 2^63
  -> int
> show g(1)
_() = 1
  -> u8
> equiv f g
f and g are equal on the domain of f (exhaustive)
```

Via MCP (`mcp_bigint_vacuous.jsonl` / `mcp_bigint_vacuous.out`) the same query
returns the structured verdict:

```
"kind":"equiv"  "equal":true  "exhaustive":true  "mismatch_points":0  "method":"exhaustive"
```

**A second, self-contradictory symptom** (`02_bigint_domain_show_contradiction.ucas`,
exact output in `02_bigint_domain_show_contradiction.out`):

```
domain of f:
  x: u8, 0..255
  no conditions: total on its parameter types
  defined at 0 of 256 points
  undefined e.g. at x=0; x=1; x=2; x=3
range of f -> int:
  empty (undefined everywhere)
  undefined at 256 points
> show f(0)
_() = 2^63
  -> int
```

i.e. the domain engine says `f` is undefined at every one of its 256 points and
its range is empty, while the evaluator happily returns `2^63` for those very
points.  `equiv f g` then treats that (incorrectly) empty domain as a vacuous
proof of equality.

**Threshold** (`03_bigint_threshold.ucas` / `.out`, exact and deterministic):

```
a(x: u8) = 2^62
b(x: u8) = x
equiv a b
a and b differ at 256 points, e.g. x=0: 4611686018427387904 vs 0
c(x: u8) = 2^63
d(x: u8) = x
equiv c d
c and d are equal on the domain of c (exhaustive)
c(x: u8) = 2^63 - 1
d(x: u8) = x
equiv c d
c and d are equal on the domain of c (exhaustive)
```

The flip is syntactic/semantic-scale, not merely the final numeric value:
`2^63 - 2^62` (= 2^62) still triggers the wrong "equal", while the literal
`2^62` correctly reports `differ`.  `show 2^63 - 2^62` stays symbolic
(`2^63 - 4611686018427387904`), so an `int` expression that contains a
bigint-scale subterm is enough.  The bug fires for `u8 u16 u32 i8 i32` result
domains and in both CLI and MCP; the reverse query `equiv g f` correctly says
`differ ... 0 vs undefined` (asymmetry).

**Why it matters:** it is a bug.** `show` proves `f(0)=2^63` and `g(0)=0` are two different
concrete values; `domain g` reports 256/256 defined points, so both functions
are defined at `x=0`.  `equiv` nevertheless returns `equal:true,
exhaustive:true, mismatch_points:0`, i.e. a *proved* equality of unequal
functions.
**Expected:** report `differ` with a counterexample, or refuse to
compare an unbounded `int`-typed result.  This is distinct from the already
catalogued vacuous `equiv` over an empty domain caused by an undefined shift
(`sat_crypto_circuits`: `x<<32`): here the evaluator defines `f` at every point.

### HANG-1 — 6 mutants overrun `timeout 10`; inherited from a heavy seed, not a new hard hang
**Severity:** HANG
_Original classification: `HANG / LIMIT`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Campaign `0x5EED` produced 6 timeouts (mutant ids 93, 100, 114, 118, 140, 144),
all derived from the `identities.ucas` seed.  Their sources are preserved in
`_scratch/hangs_0x5EED/`.  Reproducer:

**Observed:**
**Reproducer:**
```sh
cd $ROOT/tests
timeout 10 $ROOT/ucas identities.ucas ; echo "RC=$?"   # 124
cd $ROOT/tests/stress/areas/sat/grammar_corpus_mutate
timeout 10 $ROOT/ucas _scratch/hangs_0x5EED/m0093.ucas ; echo "RC=$?"
```

**ddmin result.** `python3 reduce.py --id 93 --corpus 0x5EED --expect HANG --timeout 5`
reduced the 78-line mutant to 18 lines (`_scratch/minimized/m0093_min.ucas`),
still dominated by `find v15/v16/v24/v25/v26/v27 1` searches on small-range
maps.  Re-running that 18-line file at `timeout 5` completes with `rc=0`, so the
"hang" is **timing-sensitive slow search, not a deterministic non-termination**
(the unmutated `identities.ucas` seed itself already exceeds 10 s).  Reported as
LIMIT rather than HANG; no golden `.out` kept.

### CRASH-1 — CRASH (pre-existing, inherited seed — not produced by mutation)
**Severity:** CRASH
_Original classification: `CRASH (pre-existing, inherited seed`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
While timing candidate seeds I found that the stock test file crashes:

**Observed:**
**Reproducer:**
```sh
cd $ROOT/tests
timeout 10 $ROOT/ucas fdotint.ucas ; echo "RC=$?"   # 139 (SIGSEGV)
```

Its checked-in golden `fdotint.out` shows a full successful run, so the current
binary regressed relative to that golden.  This file was **not** included in any
mutation campaign and was **not** modified; it is recorded here only so the
orchestrator can triage it against other areas' crash catalogues.

## Checks that passed

### Determinism
All 840 fuzz mutants were run once each (they are throwaway probes); the four
kept goldens (`01_*`, `02_*`, `03_*`, `mcp_*`) were each generated twice and
`diff`-clean, and re-verified run.sh-style from this folder.  The generators
`mutate.py gen` and `semantic_hunt.py` are seeded and avoid set/hash-order
iteration, so a fixed `--seed` reproduces the same corpus.  No nondeterministic
case was kept as a golden.

### Negative results (important)
- No new crash or hard hang was produced by any of the 840 grammar mutants,
  including deep `ts-wrap` nesting (up to 12 levels), fence delimiter breaks,
  and NaN-payload / `2^63` / `2^64` token-bank insertions.  234/240, 300/300 and
  300/300 mutants in the three campaigns exited 0 under `timeout 10`.
- 30+ mutants whose output contained "are equal on the domain" were all traced
  to the `ops2.ucas` seed's original **true** identity `h = copysign(abs(x),x)`,
  `g = x`; no additional false equality came from statement-level mutation.
- The only semantic bug found came from the dedicated boundary-literal
  differential (`semantic_hunt.py`), i.e. Finding 1.
