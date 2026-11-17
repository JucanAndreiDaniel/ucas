# Stress findings — `dd_diff_isolation`

_Original heading: FINDINGS — area `dd_diff_isolation`_

# FINDINGS — area `dd_diff_isolation`

Generalized delta debugging (Hildebrandt & Zeller, ISSTA 2000) on **pairs** of ucas
inputs. `dd.py` implements `dd(A_pass, B_fail)`: it diffs the two inputs into a list of
atomic token edits (delete / insert), then repeatedly tests subsets with the ucas CLI
as oracle until it reaches a 1-minimal set of edits that still flips the verdict from
correct (PASS) to buggy (FAIL). That surviving set is the **minimal flip**.

- Pairs run: **247** (all valid: A=PASS, B=FAIL, dd succeeded). Oracle calls: ~1136–1140
  (cached by candidate text; the small spread is the §7 crash-boundary nondeterminism).
  Full data: `results.jsonl`, `mutations.jsonl`, `analysis.md`.
- Every command bounded with `timeout`; binary `$ROOT/ucas`.
- All kept goldens were generated twice and `diff`ed identically (see SUMMARY.md).
- The findings themselves are pre-existing ucas bugs (confirmed in other stress areas);
  the new contribution here is the *minimal-difference* and *root-cause clustering*
  analysis, plus a demonstrated **bug mutation** under a naive oracle.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| CRASH | 1 | minimal flip is a *count* of `(` tokens, and dd finds unbalanced parens crash too |
| WRONG | 3 | root-cause cluster: ONE token (`+N` in G's body) explains 3 different findings |
| NLP | 1 | one English function word flips the parse (44 pairs) |
| LIMIT | 1 | ucas silently ignores a trailing digit after a call (`i32(x)1` == `i32(x)`) |
| DETERMINISM | 1 | the nesting-depth crash boundary is nondeterministic (±1 level) |

## Findings

### WRONG-1 — root-cause cluster: ONE token (`+N` in G's body) explains 3 different findings
**Severity:** WRONG
**Expected:** _not recorded_
**107 pairs across 3 bug classes** reduce to the same minimal flip: delete the additive
offset (`+1`/`+2`/`+3`/`+4`/`+5`) in the *second* function's body, so that the two bodies
coincide on whatever view `equiv` actually compares. The three "different" findings are:

- `equiv_where/body_coincide` (40 pairs) — see `sat_ranges_where` finding 1 / corroborator.
- `equiv_cast/result_coercion` (39 pairs) — see `grammar_fuzz_reduce` finding 1.
- `equiv_signed/reinterpret` (28 pairs) — see `type_coercion` finding 1.

Example reproducer (result coercion, `03_equiv_cast.ucas`):

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/dd_diff_isolation
timeout 30 $ROOT/ucas 03_equiv_cast.ucas
```

**Observed:** (`03_equiv_cast.out`):

```
> f(x: i8) = u8(x)
> g(x: i8) = i32(x)
> equiv f g
f and g are equal on the domain of f (exhaustive)
```

dd on the pair `A = {g(x:i8)=i32(x)+1}` (verdict *differ*) vs
`B = {g(x:i8)=i32(x)}` (verdict *equal*) returns minimal flip
`delete '+'` → `g(x: i8) = i32(x)1` (the trailing `1` is silently ignored, see finding 6),
or with larger offsets `delete '+' and delete 'N'`. All 107 pairs share this cause:

```
cause: "delete additive offset (+N) in G body -> bodies coincide"  (107 pairs)
  groups: equiv_cast/result_coercion, equiv_signed/reinterpret, equiv_where/body_coincide
```

**Why it matters:** the three findings were reported under three different titles and
three different root causes ("where clause ignored", "result-type coercion",
"signed↔unsigned reinterpretation"). The minimal-difference view shows they are the
same testable condition: make G's compared value equal F's and `equiv` returns an
unsound `equal:true`. A fix at the comparison layer (`equiv`) would address all 107;
fixing each symptom separately would not. This is the central root-cause-clustering
result.

### WRONG-2 — narrowing G's `where` bound flips *correctness*, not the verdict string
**Severity:** WRONG
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**64 pairs.** The verdict string is `are equal` in BOTH the passing and failing inputs,
so a symptom-only oracle cannot even see the difference; the strict oracle must inspect
G's declared domain.

**Reproducer:**
Reproducer (`01_equiv_where_narrow.ucas`):

```sh
cd $ROOT/tests/stress/areas/sat/dd_diff_isolation
timeout 30 $ROOT/ucas 01_equiv_where_narrow.ucas
```

**Observed:** (`01_equiv_where_narrow.out`):

```
> f(x: u8) = x where x < 10
> g(x: u8) = x where x < 5
> equiv f g
f and g are equal on the domain of f (exhaustive)
  domain: x in 0..9 by the where clause (10 points enumerated)
> domain g
domain of g:
  x: u8, 0..255
  where x < 5
  no conditions: total on its parameter types
  defined at 5 of 5 points
  over all 5 points of the domain
```

dd pair: A = `g where x<10` (same domain as f → `equal` is **correct**), B = `g where x<5`
(g undefined at 5..9 → `equal` is **wrong**). Minimal flip for all 64 pairs:
**replace the single numeric bound token** in G's `where` clause with a smaller value
(`del:'10'|ins:'5'`, etc.). This is the "narrowed vs un-narrowed `where`" class; the
minimal flip is a one-token bound change, and the bug is invisible if you only diff
the `equiv` output.

### NLP-1 — one English function word flips the parse (44 pairs)
**Severity:** NLP
**Expected:** _not recorded_
**Why it matters:** _not recorded_
#### 3a. `the wrap of e` (correct) vs `wrap of e` (misparsed) — 12 pairs

**Reproducer:**
Reproducer (`05_english_of.ucas`):

```sh
cd $ROOT/tests/stress/areas/sat/dd_diff_isolation
timeout 30 $ROOT/ucas 05_english_of.ucas
```

**Observed:** (`05_english_of.out`):

```
> wrap of x+1
  note: 'of' read as o*f (single-letter variables)
wrap analysis of o*f*x + 1:
  ...
  over all 1030301 points of the domain
```

The passing input `the wrap of x+1` instead gives `ucas: it(x) = x + 1; wrap it` over
`101` domain points. Minimal flip: **delete the word `the`** (one token, `del:'the'`).

#### 3b. `N/8 of 64 please` (correct → 56) vs `N/8 of 64` (misparsed) — 32 pairs

**Reproducer:**
Reproducer (`06_english_fraction.ucas`):

```sh
cd $ROOT/tests/stress/areas/sat/dd_diff_isolation
timeout 30 $ROOT/ucas 06_english_fraction.ucas
```

**Observed:** (`06_english_fraction.out`):

```
> 7/8 of 64
  note: 'of' read as o*f (single-letter variables)
  note: 7/512(o*f) read as 7/(512(o*f)); write (7/...)... for the other reading
_(o: real, f: real) = 7/(512(o*f))
  -> real
```

With the trailing word `please` ucas prints `7/8*64` then `56` (the README-documented
answer). Minimal flip: **delete the word `please`** (`del:'please'`), one token. Same
flip for every numerator/denominator tested. (Compare `nlp_ambiguity` finding 1.)

### CRASH-1 — minimal flip is a *count* of `(` tokens, and dd finds unbalanced parens crash too
**Severity:** CRASH
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**16 pairs.** The crash is the known nesting-depth stack overflow. On this host depth
1524 always succeeds and depth 1526 always SIGSEGVs; **depth 1525 is a nondeterministic
boundary** (see §7). dd reduces a 100-pair difference down to the minimum number of
inserted `(` tokens needed to cross the threshold — that minimum fluctuates by ±1 token
because of §7.

Threshold probe (fast, copy-pasteable):

**Reproducer:**
```sh
cd /tmp
python3 -c "n=1526; open('dd_nest.ucas','w').write('parse '+'('*n+'x'+')'*n+'\n')"
timeout 10 $ROOT/ucas dd_nest.ucas; echo "exit=$?"
```

**Observed:** `Segmentation fault`, `exit=139` (1525 gives `exit=0`). Not kept as a `.out`
golden because it crashes; `08_nest_safe.ucas` (1200 deep, exit 0) is the safe golden.

**dd insight:** the minimal flip is *not* a balanced `()` pair — it is `insert N × '('`
only. E.g. pair `parse (^1500 x )^1500` → `parse (^1600 x )^1600` reduces to **25 inserted
`(` tokens** (total 1525 open, 1500 close), which still SIGSEGVs. Adding the matching
`)` tokens is not needed: the parser recurses once per `(`, so the true cause is open-paren
recursion depth, not balanced nesting. Minimal `N` observed across the 16 pairs equals
`1525 − depth_pass` ±1 (e.g. 25±1 for a 1500-deep A, 525±1 for a 1000-deep A); the ±1 is
the threshold nondeterminism of §7. This is a case where reduction changes the *shape* of
the reproducer (balanced → unbalanced) while keeping the bug.

### WRONG-3 — a verdict-only oracle reduces a coercion bug into a DIFFERENT bug
**Severity:** WRONG
_Original classification: `WRONG (bug mutation`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**18/18** equiv pairs change their minimization under a naive oracle defined as
`"are equal" in output` instead of a strict mechanism check. The verdict-only oracle
picks a smaller flip: delete the single digit `N` from `+N`, leaving a dangling `+`:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/dd_diff_isolation
timeout 30 $ROOT/ucas 09_minflip_mutated.ucas
```

**Observed:** (`09_minflip_mutated.out`):

```
> f(x: u8) = x where x < 10
> g(x: u8) = x+ where x < 5
09_minflip_mutated.ucas:2:15: error: 'where' is not defined
    g(x: u8) = x+ where x < 5
                  ^
> equiv f g
f and g are equal on the domain of f (exhaustive)
  domain: x in 0..9 by the where clause (10 points enumerated)
```

Deleting `1` from `x+1` is one edit vs two for deleting `+1`. But `x+` is a parse error:
G's definition fails, so `equiv f g` reports `are equal` via the
**undefined-function-name** bug (`grammar_fuzz_reduce` finding 5) — a different root cause
than where-ignoring / result coercion / signed reinterpretation.

The 16 `conflation` pairs demonstrate this directly: A = `a=x; b=x+N; equiv a b` (differ),
B = `a=x; equiv a b` (equal because `b` is undefined). Under a verdict-only oracle the
minimal flip is always **`delete '('`** from `b(x: u8)`, mangling the definition into
`bx: u8)` and leaving `b` undefined — again the undefined-name bug, not the intended
one. Conclusion: **an oracle defined purely by the output verdict merges and mutates
unrelated findings**; the strict oracles in `dd.py` (which reject any run containing
`error` and require the defining construct to be intact) are required to keep the
clusters honest.

### LIMIT-1 — ucas silently ignores a trailing digit after a call (`i32(x)1` == `i32(x)`)
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Found as a side effect of the minimal flip for offset `+1` (finding 1). Reproducer:

**Reproducer:**
```sh
printf 'f(x: u8) = i32(x)1\nshow f(200)\n' > /tmp/i32q.ucas
timeout 10 $ROOT/ucas /tmp/i32q.ucas
```

**Observed:**

```
> f(x: u8) = i32(x)1
> show f(200)
_() = 200
  -> i32
```

No note, no error: `i32(x)1` is accepted as `i32(x)`. This is why `delete '+'` alone is a
valid minimal flip for the `+1` coercion/signed pairs. Low severity, but it means a
malformed expression can pass silently.

### DETERMINISM-1 — the nesting-depth crash boundary is nondeterministic (±1 level)
**Severity:** DETERMINISM
**Why it matters:** _not recorded_
boundary depth the same input crashes or succeeds nondeterministically, likely because
stack layout / ASLR changes the usable stack per run.

**Reproducer:**
Reproducer (12 runs of the same 1525-deep-open-paren input):

```sh
cd /tmp
python3 -c "open('th.ucas','w').write('parse '+'('*1525+'x'+')'*1500+'\n')"
for i in $(seq 1 12); do timeout 10 $ROOT/ucas th.ucas >/dev/null 2>&1; echo -n "$? "; done; echo
```

**Observed:**

```
-11 -11 0 0 0 0 -11 -11 0 -11 -11 -11
```

Depth 1524 gives `0` in all 12 runs; depth 1526 gives `-11` in all 12. So the boundary
is depth 1525 with a roughly 50% crash probability.
**Expected:** a deterministic depth
guard (a clean "expression nested too deeply" error), not a probabilistic overflow.

Consequence for this area: the `nesting_crash` minimal flips in `results.jsonl` vary by
±1 token between `dd.py --full` runs (e.g. 25 vs 26 inserted `(`), and `oracle_calls_total`
shifts accordingly. This is a property of the binary, not of `dd.py`'s algorithm (which
uses no RNG). It is why no crash `.out` golden is kept; `08_nest_safe.ucas` (1200 deep, far
below the boundary) is deterministic.

## Checks that passed

### Determinism of the artifacts
All nine golden outputs were generated twice and `diff`ed identically (exit code 0 each
time). `dd.py` itself uses no RNG and caches oracle results by candidate text; every
class **except `nesting_crash`** reproduces byte-identically across `--full` runs. Only
the crash class inherits the binary's boundary nondeterminism (§7); that case is
documented here and in the per-pair data, not kept as a golden `.out`.
