# SUMMARY — `grammar_corpus_mutate`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 4
- Files created: 4

### Original preamble

One-line takeaway: 840 seeded grammar-aware mutants produced no new crash or
hard hang, but a boundary-literal differential found a real unsoundness —
bigint-scale `int` results (`2^63`) make `equiv` report a *proved* equality of
different functions while `domain`/`range` simultaneously claim the function is
undefined everywhere.

### Counts

| Item | Count |
|---|---|
| Grammar mutants generated & run under `timeout 10` | 840 (240 + 300 + 300, seeds `0x5EED`, `0xC0FFEE`, `0xBADF00D`) |
| Distinct seed files (`tests/*.ucas`, read-only) | 21 (parse, ops2, rules, calc, float, forms, lambert, phashtable, prove, nlp_numbers, roundmagic, fp64minmax, f16bits, simplify, glslline, atomkinds, execfconst, gates, identities, satsteps, dwcase) |
| Tree mutations applied | 11 kinds: `ts-del`, `ts-swap`, `ts-shrink`, `ts-dup`, `ts-ins`, `ts-kdel`, `ts-kins`, `ts-stutter`, `ts-fdel`, `ts-fdup`, `ts-fins`, `ts-fbreak`, `ts-wrap` |
| Token-bank entries | operators (29), types (15), commands (35), boundary literals (26: `0, -1, MIN, MAX, 2^63, 2^64`, NaN payloads …), SPIR-V/GLSL lines (22) |
| Semantic-differential function pairs (`semantic_hunt.py`) | 160 (37 `equal`, 123 `differ`, 7 parse errors, 0 timeouts; 8 raw candidates → 1 confirmed distinct bug after triage) |
| ddmin reductions run | 1 (78 → 18 lines) |
| Golden files written | 4 (3 CLI `.ucas`+`.out`, 1 MCP `.jsonl`+`.out`) — all deterministic |
| Files created total | `mutate.py`, `run_fuzz.py`, `reduce.py`, `semantic_hunt.py`, `FINDINGS.md`, `SUMMARY.md`, 3 `.ucas`, 3 `.out`, 1 `.jsonl`, 1 `.out`, plus `_scratch/` artifacts |

### How to reproduce the work

```sh
cd $ROOT/tests/stress/areas/sat/grammar_corpus_mutate
python3 mutate.py gen --count 300 --seed 0xC0FFEE   # deterministic corpus
python3 run_fuzz.py --timeout 10                    # 300 bounded runs + dedup
python3 semantic_hunt.py --count 160 --seed 0x5EED  # boundary-literal differential
python3 reduce.py --id 93 --corpus 0x5EED --expect HANG --timeout 5
timeout 30 $ROOT/ucas 01_bigint_vacuous_equiv.ucas
```


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 1 | Bigint-scale int result: show f(0)=2^63 vs show g(0)=0, yet equiv f g → equal:true, exhaustive:true, mismatch_points:0; domain/range call f  |
| LIMIT | 2 | 6 timeouts inherited from heavy identities.ucas seed (find searches, timing-sensitive, ddmin'd); pre-existing fdotint.ucas SIGSEGV in a read |

### Issues by severity

| Severity | Count | Summary |
|---|---|---|
| WRONG | 1 | Bigint-scale `int` result: `show f(0)=2^63` vs `show g(0)=0`, yet `equiv f g` → `equal:true, exhaustive:true, mismatch_points:0`; `domain`/`range` call `f` undefined everywhere (Finding 1) |
| CRASH (new, from mutation) | 0 | — |
| HANG (new, hard) | 0 | — |
| LIMIT | 2 | 6 timeouts inherited from heavy `identities.ucas` seed (`find` searches, timing-sensitive, ddmin'd); pre-existing `fdotint.ucas` SIGSEGV in a read-only seed |
| DETERMINISM | 0 | All kept goldens byte-stable across repeated runs |


## Takeaway
One-line takeaway: 840 seeded grammar-aware mutants produced no new crash or hard hang, but a boundary-literal differential found a real unsoundness — bigint-scale `int` results (`2^63`) make `equiv` report a *proved* equality of different functions while `domain`/`range` simultaneously claim the function is undefined everywhere.

### Folder confinement

All generated files, scratch data, reducers and goldens live only in
`tests/stress/areas/sat/grammar_corpus_mutate/`.  No source file, Makefile, existing test,
`opencode.json`, git state or another subagent's folder was touched; no rebuild
was run.  Seed files under `tests/*.ucas` were opened read-only.
