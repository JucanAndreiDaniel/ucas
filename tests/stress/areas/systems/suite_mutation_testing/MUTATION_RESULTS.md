# Mutation testing results

30 single-token semantic mutations applied to copies of existing `tests/*.ucas` in
`mutations/`. Each mutant was run twice with `timeout 60` against the shipped binary;
stored output is `mutations/<id>.out`.

**Detection** = the stored original `.out` would differ from the mutant's output.
`raw` counts the `> ` command echo; `semantic` ignores `> ` echo lines and floating-point
check-noise lines (the latter vary across platforms).

| ID | Base test | Kind | Mutation | Raw detect | Semantic detect | Deterministic |
|---|---|---|---|:--:|:--:|:--:|
| m01 | calc | bound | sum upper bound 10->11 | YES | YES | yes |
| m02 | find | const | match value 9->10 | YES | YES | yes |
| m03 | gates | type | param type u4->u5 | YES | YES | yes |
| m04 | prove | bound | quantifier bound 1<=r -> 2<=r | YES | YES | yes |
| m05 | rules | bound | rule cost 2->3 | YES | YES | yes |
| m06 | scheme | const | coefficient 2->3 | YES | YES | yes |
| m07 | satdefined | const | multiplier 3->4 | YES | YES | yes |
| m08 | paramsets | const | divisor 5->6 | YES | YES | yes |
| m09 | nlp_requests | bound | English upper bound 3->4 | YES | YES | yes |
| m10 | snippets | operator | inner & -> | | YES | YES | yes |
| m11 | f16 | type | param type u16->u32 | YES | YES | yes |
| m12 | float | const | epsilon 1e-8->1e-4 | YES | YES | yes |
| m13 | intfloat | bound | range 0..1000 -> 0..1001 | YES | YES | yes |
| m14 | fp64cmp | operator | comparison < -> <= | YES | YES | yes |
| m15 | counter | const | subtrahend 1->2 | YES | **NO** | yes |
| m16 | ops2 | const | fma addend 1->2 | YES | YES | yes |
| m17 | u64range | bound | range end 65535->65534 | YES | YES | yes |
| m18 | equivalg | operator | + -> - | YES | YES | yes |
| m19 | whereor | operator | +1 -> +2 | YES | YES | yes |
| m20 | cost | type | param type f32->f64 | YES | YES | yes |
| m21 | parse | const | constant 1->2 | YES | YES | yes |
| m22 | stoke | operator | - -> + | YES | YES | yes |
| m23 | nlp_numbers | const | English 256->257 | YES | YES | yes |
| m24 | nlp | const | English multiplier 2->3 | YES | YES | yes |
| m25 | algebra | const | equation 1->2 | YES | YES | yes |
| m26 | xform | const | power t^2->t^3 | YES | YES | yes |
| m27 | calculus2 | bound | taylor order 7->6 | YES | YES | yes |
| m28 | rings | const | modulus 11->13 | YES | YES | yes |
| m29 | absalg | const | count 500->501 | YES | YES | yes |
| m30 | fpsat | operator | * -> + | YES | YES | yes |

**Totals:** 30/30 mutations applied and deterministic; 30/30 raw-detected; 29/30 semantically detected.

## Blind spot (m15)

`counter.ucas` original line `f(x in 0..4) = x*(x - 1)/2` mutated to `x*(x - 2)/2`.
The ONLY difference in output is the echoed command line (`> ...`); every semantic line
is byte-identical, including the verdict `f and g differ at 5 points, e.g. x=0: 0 vs 1`.
Reason: x=0 remains the first witness with the same printed values (0 vs 1), so the
reported counterexample and all other results do not move. A regression that changed
this coefficient (or any change that preserves the first witness) would be invisible to
the golden's semantic content.

## Reproduce

```sh
cd $ROOT/tests
diff counter.out stress/suite_mutation_testing/mutations/m15.out   # only the '> ' echo line differs
python3 stress/suite_mutation_testing/data/mutate.py              # regenerate all 30 mutants
```
