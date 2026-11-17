# Stress findings — `gates_basis_edges`

_Original heading: FINDINGS — `gates_basis_edges`_

# FINDINGS — `gates_basis_edges`

Area: degenerate and adversarial **gate bases** (`basis` / `gates` / `cost` / `find … snippets`,
CLI + MCP + `--mcp --flat`).  All runs used the prebuilt `$ROOT/ucas`, bounded
by `timeout 15` (25 s for MCP goldens).  **~240 distinct statements / tool calls** were tried.
Every golden was produced twice and `diff`ed byte-for-byte: all are deterministic.  No crash,
segfault, hang or truncated JSON was observed anywhere, including the 1000+ definition files.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 2 | gate cost is silently truncated to 8 bits; declared 256 becomes "minimal cost 0" |
| NLP | 1 | English number words as basis/model names break CLI `gates … basis NAME` |
| LIMIT | 3 | LIMIT / STATE (medium) — garbage after `= lut` is an error but the gate is still installed |

## Findings

### WRONG-1 — gate cost is silently truncated to 8 bits; declared 256 becomes "minimal cost 0"
**Severity:** WRONG
_Original classification: `WRONG (high`._
**Why it matters:** _not recorded_
`parse_basis()` stores a gate's cost with `g->cost = (uint8_t)N.ki[c]` (`parse.c:2620`).  Any
value ≥ 256 wraps modulo 256.  A gate declared `cost 256` is therefore priced 0, `257` priced 1,
`512`/`65536`/`0x100` priced 0, `0x101` priced 1.  `gates` then emits a **false cost and false
minimality claim** for the declared basis: the true minimum with a 256-cost LUT is 256 (one LUT-2),
but the tool reports cost 0.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/gates_basis_edges
timeout 15 $ROOT/ucas 06_cost_wrap.ucas
```
**Observed:** (excerpt):
```
> basis c256 { t(x, y) = lut cost 256 }
> gates f basis c256
gates for f: 2 input bits -> 1 output bit, basis c256
  minimal: cost 0, 8 steps (no program of cost <= -1 exists; 8 candidates searched)
...
> gates f basis c257
  minimal: cost 1, 1 step ...          # 257 -> 1
```
Declared `256`, `512`, `65536`, `0x100` all give `minimal: cost 0`; `257`/`0x101` give cost 1;
`1000` wraps to 232 and exceeds the default cost-12 bound (Shannon fallback, "no program found").
The MCP surface makes the unsoundness machine-readable — `mcp_basis_edges` id 4 and
`mcp_analyze_cost_find` id 3 return
`"structuredContent":{"ok":true,"result":{"kind":"gates","minimal":true,"cost":0,"steps":244,...}}`
and a `"proof":{"kind":"exhaustive",...}` for a basis whose gate was declared cost 256.

**Expected:** reject/retain costs that do not fit the field (or widen the field); never report a
cost/minimality proof that contradicts the declared gate costs.  Goldens: `06_cost_wrap.out`,
`mcp_basis_edges.out`, `mcp_analyze_cost_find.out`.

### WRONG-2 — WRONG / STATE (medium-high) — negative LUT cost coerced to 0 after a parse error; phantom cost-0 gate left installed
**Severity:** WRONG
_Original classification: `WRONG / STATE (medium-high`._
**Why it matters:** _not recorded_
`basis n { t(x, y) = lut cost -1 }` prints `error: expected a gate: name(x, y) = expr`
(the `-` is consumed by `number()` as the numeric literal 0 and the trailing `1` is read as a
new gate name).  Despite the error the gate `t` is already committed to the basis with cost 0,
so `gates f basis n` succeeds and again reports `minimal: cost 0`.  The basis definition is not
atomic.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/gates_basis_edges
timeout 15 $ROOT/ucas 07_negative_cost.ucas
```
**Observed:** (excerpt):
```
> basis n1 { t(x, y) = lut cost -1 }
07_negative_cost.ucas:2:32: error: expected a gate: name(x, y) = expr
    basis n1 { t(x, y) = lut cost -1 }
                                   ^
> gates f basis n1
gates for f: 2 input bits -> 1 output bit, basis n1
  minimal: cost 0, 8 steps (no program of cost <= -1 exists; 8 candidates searched)
```
Same for `-2`, `-255`, `-256`.  **
**Expected:** a rejected basis definition must not leave a usable
gate behind (error handling must be atomic), and a negative cost must be rejected, not mapped to 0.
Golden: `07_negative_cost.out`.

### NLP-1 — English number words as basis/model names break CLI `gates … basis NAME`
**Severity:** NLP
_Original classification: `NLP (medium`._
**Why it matters:** _not recorded_
A basis named `one`, `two`, …, `ten`, `hundred` or `half` can be **defined** and even used as a
parent (`basis child : one {…}` works), but selecting it on the CLI with `gates f basis one` or
`cost f model one` fails: the command is misrouted to the English frontend and returns the
nonsense reply `sorry: of what?`.  Words not in the number lexicon (`eleven`, `twelve`, `first`,
`zero`, `nan`, …) work fine.  The **MCP** path is unaffected: the same source via the `ucas`
MCP tool (`mcp_analyze_cost_find` id 4) returns a normal gates result.  This is a CLI-only
NLP/native-parser discrepancy.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/gates_basis_edges
timeout 15 $ROOT/ucas 11_numberword_basis.ucas
```
**Observed:**
```
> gates f basis one
  sorry: of what?
> gates f basis eleven            # control: works
  minimal: cost 1, 1 step ...
> cost f model one
  sorry: of what?
> show one
  ucas: show 1
_() = 1
  -> int
```
**Expected:** either accept the name as a normal identifier in every command position, or give a
consistent `unknown basis` diagnostic — never silently reinterpret the name as the number 1 and
fall through to an unrelated English error.  Golden: `11_numberword_basis.out`.

### LIMIT-1 — garbage after `= lut` is an error but the gate is still installed
**Severity:** LIMIT
_Original classification: `LIMIT / STATE (medium`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`basis g { t(x, y) = lut 255 }` (or `lut 0xe8`) raises `error: expected a gate: name(x, y) = expr`
at the stray table literal, yet `t` is already in the basis; `gates f basis g` then succeeds with a
1-step AND.  Same non-atomic-definition class as finding 2, but with a different trigger (an
illegal explicit LUT table literal — `= lut` takes no table argument).

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/gates_basis_edges
timeout 15 $ROOT/ucas 12_lut_table_garbage.ucas
```
**Observed:** (excerpt):
```
> basis g1 { t(x, y) = lut 255 }
12_lut_table_garbage.ucas:2:26: error: expected a gate: name(x, y) = expr
> gates f basis g1
gates for f: 2 input bits -> 1 output bit, basis g1
  minimal: cost 1, 1 step ...       # the gate IS installed despite the error
```
A bare `lut(0xff)` / `LUT` / `Lut` is handled differently (`'lut' is not defined` / `'LUT' is not
defined` → basis has no gates), so the malformed forms are not uniformly rejected.
Golden: `12_lut_table_garbage.out`.

### LIMIT-2 — documented `cost n` on a non-LUT gate is still not parsed (reconfirmed)
**Severity:** LIMIT
_Original classification: `LIMIT (medium`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Already reported in the sibling `gates_find_cost` area; reconfirmed here because it makes
cost-sensitive experiments on custom non-LUT bases impossible.  `basis b { and(x, y) = x & y cost 3 }`
→ `error: 'cost' is not defined` and `basis b has no gates` — the tokenizer reads `cost` as an
undefined variable in the body expression, so `accept_kw(p,"cost")` in `parse_basis` is never
reached.  Only `= lut … cost n` gates can carry a non-default cost, which is exactly how finding 1
is reachable.

**Reproducer:**
Reproducer:** `timeout 15 $ROOT/ucas 13_nonlut_cost.ucas`
**Observed:**
```
> basis b { and(x, y) = x & y cost 3 }
13_nonlut_cost.ucas:1:29: error: 'cost' is not defined
> gates maj basis b
13_nonlut_cost.ucas:3:18: error: basis b has no gates
```
Golden: `13_nonlut_cost.out`.

### LIMIT-3 — cost-0 LUT gates produce absurd "minimal: cost 0, N steps" with a vacuous proof
**Severity:** LIMIT
_Original classification: `LIMIT (low`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
When a gate's (effective) cost is 0, iterative deepening fixes the bound at 0 and the first
solution found is a huge minterm expansion (8 steps for a 2-input AND, 230 for a 3-input majority,
244 with the MCP majority case).  The tool still prints `minimal: cost 0, N steps` and the vacuous
clause `(no program of cost <= -1 exists; … candidates searched)`.  The claim is technically about
cost only, but pairing a "proof of minimality" with a 230/244-gate network at declared cost 256
(findings 1–2) is deeply misleading.  Golden: `06_cost_wrap.out`, `mcp_basis_edges.out`.

## Checks that passed

### Negative controls (checked, no bug)
* **No crash / hang.** `1000` gates in one basis, `1000` duplicate definitions, `1000` basis
  definitions and a `1000`-deep inheritance chain all finish in < 1 s with the documented caps
  (`too many gates`, `too many bases`, `unknown basis`); exit 0, no signal, no truncation.
* **Cyclic / self inheritance** (`basis a : a`, 2/3-node cycles with regular and LUT gates, cycles
  that redefine a gate with a different arity) terminate cleanly and synthesize correctly
  (`08_cycles.out`).
* **Duplicate gate replacement** is correct: a later same-named gate replaces the earlier one,
  including across inheritance and with a different arity (`03_duplicate_gates.out`).
* **Empty bases, one-gate bases, incomplete bases, unknown symbols and wrong arities** (0 or 4
  inputs) all give clean `error:` diagnostics or a clearly-labelled Shannon "upper bound, not
  proved minimal" fallback; `gates` never claims false minimality in these cases
  (`01`–`05`, `09`, `10`).
* **Unicode gate names** (`nánd`, `λgate`, `gate_日本`, `Ω`, …) are accepted and used correctly.
* **`find … snippets`** with degenerate bases in the session, a missing snippet file, and the
  MCP/`--flat` equivalents return clean, deterministic results (`14_find_snippets.out`,
  `mcp_analyze_cost_find.out`, `mcp_flat_basis.out`).
* **No nondeterminism**: all 14 CLI goldens and all 3 MCP goldens were run twice and diffed
  identically, including the wrapper costs and the 244-step MCP result.
