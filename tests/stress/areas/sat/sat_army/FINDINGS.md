# Stress findings — `sat_army`

New test area for the SAT/circuit audit. All goldens were generated from the
FIXED binary with the canonical command, run from this directory:

```sh
env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none /home/andrew/Code/ucas/ucas NAME.ucas > NAME.out
```

## Bug fixed — reflexive `equiv f f` had no proof for nodes without a circuit

**Severity:** WRONG (a trivial proof was reported as "sampled, not proved")
**Owned source:** `src/nodesat.c` (`nsat_equiv`)

`b refines a` is trivially true when `a` and `b` are the same node, on every
domain and for every kind of value. `nsat_equiv` nevertheless built the miter
first; when a node contained an operation the bit-blast has no circuit for
(`^` with a variable exponent, a float division by a non power of two, `sqrt`,
etc.), `blast()` sets `B.why`, and `nsat_equiv` returned `-2` (unsupported).
`equiv_decide` then degraded the answer to `EQ_SAMPLED`:

```
> g64(a: u64, b: u64) = a ^ b
> equiv g64 g64
g64 and g64 are equal on the domain of g64 (sampled, not proved; no SAT proof: a power)
```

The tool claimed "equal" without a proof for a statement that needs no search
at all. This is the defect recorded as LIMIT-7 in `sat_crypto_circuits/FINDINGS.md`
and visible in the MCP golden `sat_wrap_domain/mcp_wrap_domain_range.jsonl`
(`equiv d d noftz` on a `sqrt` formula).

**Fix:** at the `if (B.why)` unsupported/give-up branch of `nsat_equiv`, when
`a == b` (after `sg_lower` and the result-type cast) return status 0 (proved)
instead of `-2`. The check is deliberately inside that branch, so a supported
reflexive pair still builds its circuit and reports its real node/conflict
counts (`02_reflexive_supported_control` is the control).

After the fix the same command answers:

```
g64 and g64 are equal on the domain of g64 (proved by SAT: 129 AIG nodes, 0 conflicts)
```

**Tests:**
- `01_reflexive_unsupported.ucas` — power, float division and sqrt reflexive
  checks now proved; an exhaustive-domain reflexive check as a second control.
- `02_reflexive_supported_control.ucas` — a supported reflexive pair keeps its
  135-node proof, a genuine `+1` difference is still refuted, and a real
  multiplication identity is still proved by SAT (811 nodes, 1209 conflicts).
- `03_reflexive_domain_control.ucas` — a `where`-restricted reflexive proof and
  two everywhere-undefined reflexive cases stay `exhaustive` / `vacuous`:
  the new branch is only in the SAT path and must not change those verdicts.
- `04_crypto_equivalences_control.ucas` — XOR/AND crypto-style equivalences
  still prove/refute correctly; none is a reflexive pair, so the fix cannot
  touch them.

## Existing goldens needing recapture (behaviour intentionally changed)

These are owned by other areas; their old `.out` files record the buggy
"sampled, not proved" answer and must be recaptured with `stress-accept`:

1. `tests/stress/areas/sat/sat_crypto_circuits/17_power_no_sat.out`
   (`equiv g64 g64`, `a ^ b`): now `proved by SAT: 129 AIG nodes, 0 conflicts`.
   This makes `stress-test STRESS_AREA=sat_crypto_circuits` report one expected
   FAIL until recaptured.
2. `tests/stress/areas/sat/sat_wrap_domain/mcp_wrap_domain_range.out`
   (MCP call id 15, `equiv d d noftz` on a `sqrt` formula): the `sat` object goes
   from `{"result":"unsupported","why":"a float square root"}` to `proved` with
   the method `sat`; the prose goes from "sampled, not proved" to "proved by
   SAT: 1427 AIG nodes, 0 conflicts".

Note: `sat_crypto_circuits/mcp_sat_crypto.out` also shows a diff in this build,
but at call id 8 (`domain sh` wording, "empty domain ... every point" to "no
sampled point was defined"), which is a concurrent edit in another agent's file,
not caused by this fix. Its `equiv sh anyx` (id 9) is unchanged.

## Negative results (searched, no bug found)

- **Counterexample verification.** Fuzzed ~1000 random `equiv a b` pairs at
  u4/u32 (integer + float operations, variable shifts, division/modulo,
  popcount/clz/ctz) comparing the SAT path against an exhaustive ground truth
  on the same expressions. No wrong `equal`/`differ` verdict and no
  `counterexample did not reproduce` was found; SAT counterexamples always
  re-checked with the evaluator.
- **AIG node accounting.** `aig_nodes()` counts the constant, inputs and
  structural-hashed AND gates; `MAXAIG` gives up via `unsup` rather than
  overflowing. No off-by-one or node-count inconsistency found.
- **Crypto circuits.** GF(2^8) multiply-by-x, AES S-box inversion, CRC/LFSR,
  ARX mixing and bit-permutation equivalences all give correct verdicts.
- **Give-up nondeterminism.** Repeated each give-up case five times; verdicts
  and reported node counts were identical every time.
- **Crash/hang.** Wide types (> 64 bit), > 8 parameters and deep expressions
  are rejected at parse time; the SAT blaster itself is iterative and bounded.
