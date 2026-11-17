# dd_diff_isolation — generalized delta debugging on ucas input pairs

`dd.py` implements Hildebrandt & Zeller's generalized `dd`: given a passing input `A`
and a failing input `B`, it finds a 1-minimal set of token-level changes that, applied
to `A`, still flips the verdict to the bug. The ucas CLI is the oracle.

## Files

- `dd.py` — tokenizer, edit-script builder, `dd` loop, bug oracles, 247 pair generators,
  driver and analysis.
- `results.jsonl` — one record per pair: minimal flip, normalized cause, oracle-call count.
- `mutations.jsonl` — strict-vs-verdict-only minimization comparison.
- `analysis.md` — per-class minimal flips, root-cause clusters, mutation analysis.
- `FINDINGS.md` / `SUMMARY.md` — report.
- `NN_*.ucas` + `NN_*.out` — deterministic CLI goldens (buggy verdicts captured as
  regression tests; crash kept out of goldens).

## Run

```sh
cd $ROOT/tests/stress/areas/sat/dd_diff_isolation
python3 dd.py --full                 # all 247 pairs (bounded, ~1 min)
python3 dd.py --class equiv_cast --limit 5 --no-write
```

## Algorithm (in `dd.py`)

1. Tokenize A and B (whitespace, identifiers, digits, multi-char operators, single chars).
2. `edit_script()` uses `difflib.SequenceMatcher` to emit atomic edits `keep`/`del`/`ins`;
   applying all edits to A yields B, applying none yields A.
3. `dd()` partitions the current change set into `n` chunks (starting at 2) and tests,
   for each chunk, (a) the complement and (b) the chunk alone. Any subset that still
   exhibits the bug becomes the new change set (`n = max(n-1,2)`); when none works,
   `n` doubles. Stops at 1-minimality (`n >= |Δ|`).
4. Each bug class supplies a **strict oracle**: it checks the verdict *and* that the
   defining construct is intact and the output has no parse error, so minimizing cannot
   silently switch to the undefined-name bug. A verdict-only oracle is used deliberately
   in `run_mutation_experiment()` to show that failure mode.
5. Oracle calls are cached by candidate text; every run uses `timeout 15`.

Determinism: `dd.py` uses no RNG and `difflib`/cache make the algorithm reproducible.
All classes except `nesting_crash` regenerate byte-identically; the crash class inherits
the binary's ±1 nondeterministic depth-1525 boundary (FINDINGS.md §7), so crash minimal
flips and `oracle_calls_total` can shift by a token between `--full` runs.
