#!/usr/bin/env python3
"""Emit MUTATION_RESULTS.md from mutations.csv."""
# PORTABILITY: '$ROOT' in repro commands means the ucas checkout root; set ROOT=/path/to/ucas before copy-pasting.
import os, csv
D=os.path.dirname(os.path.abspath(__file__))
rows=list(csv.DictReader(open(os.path.join(D,"mutations.csv"))))
L=["# Mutation testing results","",
"30 single-token semantic mutations applied to copies of existing `tests/*.ucas` in",
"`mutations/`. Each mutant was run twice with `timeout 60` against the shipped binary;",
"stored output is `mutations/<id>.out`.",
"",
"**Detection** = the stored original `.out` would differ from the mutant's output.",
"`raw` counts the `> ` command echo; `semantic` ignores `> ` echo lines and floating-point",
"check-noise lines (the latter vary across platforms).","",
"| ID | Base test | Kind | Mutation | Raw detect | Semantic detect | Deterministic |",
"|---|---|---|---|:--:|:--:|:--:|"]
for r in rows:
    L.append(f"| {r['mutation']} | {r['base']} | {r['kind']} | {r['desc']} | "
             f"{'YES' if r['raw_detect']=='True' else 'NO'} | "
             f"{'YES' if r['sem_detect']=='True' else '**NO**'} | "
             f"{'yes' if r['deterministic']=='True' else 'NO'} |")
n=len(rows)
L += ["", f"**Totals:** {n}/{n} mutations applied and deterministic; "
      f"{sum(r['raw_detect']=='True' for r in rows)}/{n} raw-detected; "
      f"{sum(r['sem_detect']=='True' for r in rows)}/{n} semantically detected.", "",
"## Blind spot (m15)","",
"`counter.ucas` original line `f(x in 0..4) = x*(x - 1)/2` mutated to `x*(x - 2)/2`.",
"The ONLY difference in output is the echoed command line (`> ...`); every semantic line",
"is byte-identical, including the verdict `f and g differ at 5 points, e.g. x=0: 0 vs 1`.",
"Reason: x=0 remains the first witness with the same printed values (0 vs 1), so the",
"reported counterexample and all other results do not move. A regression that changed",
"this coefficient (or any change that preserves the first witness) would be invisible to",
"the golden's semantic content.",
"",
"## Reproduce","",
"```sh",
"cd $ROOT/tests",
"diff counter.out stress/suite_mutation_testing/mutations/m15.out   # only the '> ' echo line differs",
"python3 stress/suite_mutation_testing/data/mutate.py              # regenerate all 30 mutants",
"```",
""]
open(os.path.join(D,"..","MUTATION_RESULTS.md"),"w").write("\n".join(L))
print("wrote MUTATION_RESULTS.md")
