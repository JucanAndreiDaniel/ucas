# SUMMARY — `fp_edge`

## Counts
- Distinct expressions/queries tried: 260
- Goldens written: 10
- Files created: not recorded

### Coverage
- Distinct expressions / queries tried: ~260 (float edge constants via `show`;
  `range`/`domain`/`wrap`/`crit` on NaN/inf/subnormal/max-finite functions at
  f16/f32/f64; `equiv` with `nanbits`, `ftz`/`noftz`, full-bit-pattern `u32`
  inputs via `asfloat`, fma cancellation, roundeven/floor/ceil boundaries;
  `error`/`fit`/`approx` of quake/rsqrt and 1/x/log near endpoints; MCP
  `analyze`/`properties`/`session` calls; deep-nesting crash probes).
- All candidate goldens were run 3x and diffed; every kept golden is exit 0 and
  byte-identical across runs.

### Files created
CLI goldens (`.ucas` + `.out`):
- `01_special_values.ucas/.out` — 20 show queries: ±inf, quiet NaN, min
  subnormal, max finite at f16/f32/f64; asuint/asint/asfloat round-trips;
  signed zero.
- `02_range_edges.ucas/.out` — 17 queries (9 defs + 8 commands): range of
  sqrt/1/x/x/x/exp and f16 exhaustive NaN counting.
- `03_equiv_nanbits.ucas/.out` — 18 queries: nanbits equiv over all u32 bit
  patterns (round-trips, abs, copysign, add/mul/div by 1), SAT/exhaustive.
- `04_ftz_subnormals.ucas/.out` — 11 queries: ftz vs noftz and subnormal
  flushing equivalences.
- `05_rounding.ucas/.out` — 16 queries: roundeven/floor/ceil ties, signed
  zeros, `equiv` of roundeven vs floor(x+0.5), `find`.
- `06_error_fit.ucas/.out` — 9 queries: `fit`/`error` of rsqrt magic constant,
  quake and alternate-magic Newton step near endpoints.
- `07_approx.ucas/.out` — 2 approx queries (sqrt on [1,2], 1/x with kept
  endpoint at 0, as f32).
- `08_wrap_domain.ucas/.out` — 17 queries: wrap/domain/range of NaN and inf
  functions at f16 and f32.

MCP goldens:
- `mcp_float_edges.jsonl/.out` — 11 calls: session.define + analyze
  equiv/range/wrap/error/show + properties monotonic.
- `mcp_flat.jsonl/.out` + `mcp_flat.flags` (`--flat`) — 6 calls: show, parse,
  define, equiv via flat tool-per-op mode.

Documentation: `FINDINGS.md`, `SUMMARY.md`.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| CRASH | 1 | — |
| WRONG | 3 | — |
| NLP | 1 | — |
| LIMIT | 2 | — |

### Issues by severity
- CRASH: 1 — SIGSEGV (stack overflow) on ~1600+ nested parentheses in `parse`
  (threshold between 1200 and 1600).
- WRONG: 3 — MCP `equiv` with inline expression args returns a bogus structured
  verdict; `symmetry` claims both symmetric and antisymmetric for near-zero
  functions; `range` returns `[0,0]` for a reachable point spike.
- NLP: 1 — (also WRONG) MCP `equiv` argument concatenation; plus inline
  annotation misparse in bare CLI expressions (`sqrt`->isqrt, `1/cond`).
- LIMIT: 2 — `error` reports max 0 when all samples are inf/NaN; `equiv nanbits`
  evaluator-vs-SAT disagreement on sNaN payloads ("counterexample did not
  reproduce").
- DETERMINISM: 0 in kept goldens (all verified 3x identical). Two apparent
  nondeterministic diffs were traced to a full `/tmp` filesystem truncating the
  scratch output file, not to the binary.

No hangs were observed; every probe returned within its `timeout` except the
SIGSEGV crash cases, which died immediately.


## Takeaway
The float machinery is largely sound and deterministic on ordinary edge cases (bit casts, NaN/inf counting, ftz, nanbits SAT proofs, quake/rsqrt fits), but the MCP `equiv` argument builder and the numeric `symmetry` tolerance can return confidently wrong answers, a deep-parenthesis input crashes the parser, and sampled `range`/`error` can silently miss or misreport isolated NaN/inf cases.

### Original takeaway (verbatim)
The float machinery is largely sound and deterministic on ordinary edge cases
(bit casts, NaN/inf counting, ftz, nanbits SAT proofs, quake/rsqrt fits), but
the MCP `equiv` argument builder and the numeric `symmetry` tolerance can return
confidently wrong answers, a deep-parenthesis input crashes the parser, and
sampled `range`/`error` can silently miss or misreport isolated NaN/inf cases.
