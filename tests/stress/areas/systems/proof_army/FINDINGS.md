# Stress findings — `proof_army`

Area: proof certificate / counterexample generation, axiom accounting,
report serialization and resource handling in the proof commands.  All
goldens were generated from the fixed binary under the canonical
environment (`UCAS_NO_TIMES=1`, `UCAS_SPIRV_CROSS=none`) and checked to be
byte-identical on two runs.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | a closed false theorem reports `counterexample:` with an empty value |

## Findings

### WRONG-1 — closed false statements produce an empty counterexample (WRONG)
**Severity:** WRONG
**Files:** `src/prove_model.c` (`pm_refute`), surfaced by `src/prove_cmd.c`
(`cmd_prove`, both CLI and MCP `proofs`/`prove`).

`pm_refute()` calls `search()`, which only recurses through leading
`forall` binders.  When the statement is *closed* (no leading `forall`),
`search()` reaches `eval()` immediately and returns 1 as soon as the body
is false — but it never writes any assignment, so `out` is empty.  The
tail of `pm_refute()` only strips the trailing `", "` of a real
assignment; it left the empty buffer as-is.  `cmd_prove()` then printed
`counterexample: ` with nothing after the colon, and MCP exposed
`"counterexample": ""`.

The verdict was right (the statement really is false in the concrete
model) but the "counterexample" was useless: a client cannot tell what
was refuted, and an empty string in `structuredContent` is easy to
mistake for a parsing or serialization failure.

**Reproducer (CLI):**

```sh
cd $ROOT/tests/stress/areas/systems/proof_army
env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none $ROOT/ucas 01_closed_false.ucas
```

**Observed before the fix** (first two lines of `prove c01`):

```
c01: NOT proved
  automation: could not prove 1 = 2
  counterexample: 
  (evaluated in a concrete model: ...)
```

**After the fix:**

```
c01: NOT proved
  automation: could not prove 1 = 2
  counterexample: the statement is false as written (no variables to assign)
  (evaluated in a concrete model: ...)
```

**Reproducer (MCP):** `mcp_closed_false.jsonl`; `structuredContent.result.counterexample`
was `""`, now the descriptive sentence above.

**Fix:** in `pm_refute()`, when `search()` reports a refutation but no
assignment text was produced (closed statement), write an explicit
description.  The fix is at the source so both CLI text and the MCP
structured field are correct; no change to the soundness of `search()`.

**Controls:** `02_controls.ucas` and `mcp_controls.jsonl` verify that
quantified false statements still print a real assignment (`x = 0`) and
that true statements still get no counterexample at all.  Existing
goldens in `proof_kernel_axioms` and `prove_symbolic` all use quantified
false statements, so they are unaffected.

## Investigated, not changed

* A theorem name may still shadow an axiom name (`theorem int_discrete:
  ...`), and a hyphen in a theorem name (`theorem e-dash: ...`) is still
  parsed as subtraction.  Both are documented NLP/LIMIT findings in
  `sat/proof_kernel_axioms`; changing them would alter established NLP
  behaviour outside this area.
* `prove` reports the proof DAG size (4) while `check` reports kcheck's
  count (122) for the same automatically-proved theorem: `kcheck.c`
  (not owned here) follows every declared homomorphism for any `KR_CONV`
  node, while `total_inferences()` and the `proof` tree follow only the
  homomorphisms actually used.  The verdict is correct; only the two
  "inference" counters differ.  Left untouched.
* Deeply nested quantifiers in `search()` can write past `env[32]`
  (`prove_model.c`); up to 64 nested binders the parser accepts and the
  output is still correct, so no observable bug.  `quant()` already
  guards its own recursion with `nenv >= 31`.

## Existing goldens needing recapture

The fixed binary changes two goldens in
`tests/stress/areas/sat/thesis_mr_mining/` that recorded the empty
counterexample (both are closed false statements):

* `256_f06.out` (`theorem f06: 0^0 = 0`)
* `320_t_false_zeroone.out` (`theorem t_false_zeroone: 0 = 1`)

They were not edited here (outside this area's ownership).
