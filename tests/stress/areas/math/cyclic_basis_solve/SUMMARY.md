# SUMMARY — `cyclic_basis_solve`

## Counts
- Distinct expressions/queries tried: 318
- Goldens written: 129
- Files created: 129

### Counts

- Distinct statements / queries tried: **318**
  - 286 CLI statements across **119** `.ucas` files
  - 32 MCP tool calls across **10** `.jsonl` files (9 grouped + 1 `--flat`)
- Additional ad-hoc probes (deep chains, cap probes, hard searches): ~50
- Golden files written: **129** (119 CLI `.out` + 10 MCP `.out`), all run twice
  under `timeout 15` with byte-identical output.
- Support files: `FINDINGS.md`, this `SUMMARY.md`, `_scratch/manifest.tsv`,
  `_scratch/report.tsv`, `_scratch/outputs.json` (full captured outputs).

### Coverage

- Cyclic **basis** directives: self-inheritance (`basis a : a`), 2/3/5/10/20-node
  cycles built via redefinition, unknown parents, forward references, shadowed
  gate names, empty bases, LUT/u4/bool gates; driven through `gates` (incl.
  `max`, `nodes`, `as`) plus `cost`, `mca`, `funcs`, `show`.
- Cyclic **model** directives: self-inheritance, 2/3/5/10-node cycles, unknown
  parents, inherited/redefined `fuse`, empty models; driven through `cost`,
  `cost ... model`, `use`, `mca`, `models`, `folds`, `consecutive`.
- Degenerate **solve**: tautologies, contradictions, empty/zero equations,
  division by zero (coefficient and expression), inconsistent/rank-deficient/
  over-/under-determined systems, free variables, complex roots, `mod 0/1/8`
  and CRT, nonlinear and transcendental equations.
- Degenerate **dsolve**: missing/duplicate/conflicting/over-specified initial
  conditions, `steps 0/-1/100000`, reversed interval, blow-up RHS,
  non-Lipschitz RHS, non-constant IC.
- Degenerate **zsolve**: missing initial values, self-recurrence, vanishing
  highest-order term, non-recurrences, divide-by-zero coefficients, 1st/2nd
  order recurrences.
- MCP equivalents: `algebra/solve`, `ucas` (source), `session/use`, `session/models`,
  `english`, `rings/congruence` (via CLI), and the `--flat` transport.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 6 | F1 identity→"no solution"; F2 NaN/Inf "solutions" + vacuous check; F3 conflicting ICs silently resolved; F4 extra IC ignored; F5 phantom mod |
| NLP | 2 | F7 solve for x → dsolve; F8 English "equals" not parsed |
| LIMIT | 3 | F9 15 s search boundary; F10 invalid dsolve steps silently coerced; F11 non-unique ODE solution silently chosen |

### Issues by severity

| Severity | Count | Short description |
|---|---|---|
| CRASH | 0 | — |
| HANG | 0 | one timeout-boundary cost hazard (#9), documented as LIMIT |
| WRONG | 6 | F1 identity→"no solution"; F2 NaN/Inf "solutions" + vacuous check; F3 conflicting ICs silently resolved; F4 extra IC ignored; F5 phantom model/basis after rejected def; F6 mod-1 "every x" vs "1 solution" |
| STATE | 1 | F5 (rejected definition mutates symbol table; MCP reply has both result and error) |
| NLP | 2 | F7 `solve for x` → `dsolve`; F8 English "equals" not parsed |
| LIMIT | 3 | F9 15 s search boundary; F10 invalid `dsolve` steps silently coerced; F11 non-unique ODE solution silently chosen |

Total distinct issues documented: **11** (6 WRONG, 1 STATE, 2 NLP, 3 LIMIT
— F5 is counted in both WRONG and STATE).


## Takeaway
Cyclic basis/model inheritance is robust (visited-set breaks every cycle, no hang or crash, graceful 24-object / 6-input caps), but the solve family is not sound: identities are reported as having **no** solution, NaN/Infinity are accepted as verified solutions, contradictory ODE initial conditions are silently resolved, and a rejected model/basis definition leaves a phantom symbol with default costs — with the MCP envelope even reporting success and failure simultaneously.

### Original takeaway (verbatim)

Cyclic basis/model inheritance is robust (visited-set breaks every cycle, no
hang or crash, graceful 24-object / 6-input caps), but the solve family is not
sound: identities are reported as having **no** solution, NaN/Infinity are
accepted as verified solutions, contradictory ODE initial conditions are
silently resolved, and a rejected model/basis definition leaves a phantom
symbol with default costs — with the MCP envelope even reporting success and
failure simultaneously.
