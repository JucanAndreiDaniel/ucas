# SUMMARY — `ode_boundary_problems`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 21
- Files created: not recorded

### What was tried

- **Distinct ODE expressions / queries: ≈ 250** (well over the 150 target), covering:
  - 2–5 coupled linear systems (distinct/repeated/defective/complex/zero eigenvalues,
    forcing, non-zero initial time), nonlinear coupled systems;
  - stiff equations (`-10^3 y` … `-10^9 y`, van der Pol μ=10, `y'=-1000(y-cos t)`);
  - singular coefficients (`t*y'=y`, `t^2 y''=-t y'`, `y'=y/t`, `1/(2√t)`, `log t`, pole forcing);
  - boundary-value problems (Dirichlet, mixed) and comparisons against IVPs;
  - periodic/chaotic systems (harmonic, van der Pol, Lorenz, Rössler, Lotka–Volterra,
    Duffing, pendulum, Mathieu, 3rd/4th-order oscillators);
  - discontinuous RHS (`sign`, `floor`, `ceil`, `abs`, `max`, ternary step, sawtooth);
  - parameterized ODEs and recurrences; exact solutions (exp/harmonic/damped/resonance,
    power series, Taylor, radius);
  - implicit / non-linear-in-derivative ODEs (Clairaut, `(y')^2=4y`, `y'^2+y^2=1`);
  - non-uniqueness (`3y^(2/3)`, `√y`), blow-up (`y'=y^2`), 6th/10th-order equations;
  - cross-checks between `dsolve`, `laplace_solve`, `zsolve`, `powerseries`, `identify`,
    `tf`, and adaptive numeric stepping, via CLI and MCP (`calculus`, `transforms`,
    `properties`, `session`, `ucas`).

### Files created (all inside `tests/stress/areas/math/ode_boundary_problems/`)

- 21 CLI golden pairs: `01_linear_systems` … `21_stiff_misdiagnosis` (`.ucas` + `.out`).
- 3 MCP golden pairs: `mcp_ode_dsolve`, `mcp_ode_transforms`, `mcp_ode_identify`
  (`.jsonl` + `.out`).
- `FINDINGS.md`, `SUMMARY.md`.
- **Total: 50 files.** All golden outputs were produced with `timeout 30`, run twice and
  `diff`ed byte-for-byte (all deterministic). No crash, hang, or nondeterministic case
  was found, so none were kept as goldens.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 4 | identify y' = sign(y) → false "linear/proved/r=0"; identify y'' + ay'+by=0 → "in y(a)"; y'=-1e8y → false "blow-up/undefined"; extra/duplicat |
| LIMIT | 6 | dsolve rejects non-solved/singular/implicit forms; no BVP; polynomial forcing gives no closed form; laplace_solve rejects pure y'=f(t); non- |

### Issues by severity

| Severity | Count | Short reproducer |
|---|---|---|
| WRONG | 4 | `identify y' = sign(y)` → false "linear/proved/r=0"; `identify y'' + a*y'+b*y=0` → "in y(a)"; `y'=-1e8*y` → false "blow-up/undefined"; extra/duplicate ICs and equations silently dropped |
| LIMIT | 6 | `dsolve` rejects non-solved/singular/implicit forms; no BVP; polynomial forcing gives no closed form; `laplace_solve` rejects pure `y'=f(t)`; non-uniqueness never flagged; symbolic solve stops at order/system size ~9 |
| CRASH / HANG / DETERMINISM | 0 | — |


## Takeaway
The numeric/symbolic ODE solvers are accurate on ordinary IVPs and systems, but the `identify` classifier returns **false proven linearity** and the **wrong independent variable**, a smooth stiff ODE is **misdiagnosed as a blow-up**, and BVPs, implicit/singular forms, and non-uniqueness are silently unsupported.

### Original takeaway (verbatim)

The numeric/symbolic ODE solvers are accurate on ordinary IVPs and systems, but the
`identify` classifier returns **false proven linearity** and the **wrong independent
variable**, a smooth stiff ODE is **misdiagnosed as a blow-up**, and BVPs, implicit/singular
forms, and non-uniqueness are silently unsupported.
