# Stress findings — `aig_growth_patterns`

_Original heading: FINDINGS — area `aig_growth_patterns` (AIG node counts & SAT-conflict growth)_

# FINDINGS — area `aig_growth_patterns` (AIG node counts & SAT-conflict growth)

All commands use the already-built `$ROOT/ucas`. No source file,
Makefile, existing test or `opencode.json` was edited; no rebuild, no git, no other
subagent's folder touched. Every would-be golden was generated from its own directory
with `timeout 30 … > NAME.out 2>&1` and verified stable across two runs (see below);
crashes/nondeterministic cases would not be kept as goldens.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 5 | give-up is not a function of AIG size; a 23-node change flips the verdict |
| DETERMINISM | 1 | all goldens and the sampled probes are stable |

## Findings

### LIMIT-1 — give-up is not a function of AIG size; a 23-node change flips the verdict
**Severity:** LIMIT
_Original classification: `LIMIT (behaviour to be aware of, not a wrong answer`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
The research goal was to hunt for "give-up at suspiciously low node counts". It happens:
SAT gives up at as few as **1200 AIG nodes** (`mul_maskff` u12), while a different
mask on the *same multiplier* is proved with **0 conflicts at 37863 nodes** (u64).

**Reproducer:**
Reproducer (both goldens in this folder):
```sh
cd $ROOT/tests/stress/areas/sat/aig_growth_patterns
timeout 30 $ROOT/ucas 01_mul_mask1_u16.ucas     # &1
timeout 30 $ROOT/ucas 11_maskff_u16.ucas         # &255
timeout 30 $ROOT/ucas 07_mul_xor_giveup_u16.ucas  # xor 5
```
**Observed:** (u16):
```
# &1   -> a and b are equal ... (proved by SAT: 2175 AIG nodes, 0 conflicts)
# &255 -> a and b are equal ... (sampled, not proved; SAT gave up on 2198 AIG nodes ...)
# xor5 -> a and b are equal ... (sampled, not proved; SAT gave up on 2230 AIG nodes ...)
```
At u64 the two mask variants have 37863 vs 37886 nodes (difference 23) yet one is
proved and the other gives up. **Expected/useful:** a consumer must not infer
"will be proved" from a small AIG node count, nor set a node-count give-up threshold;
the difficulty is in the bit-width of the compared cone, not the total node count.

### LIMIT-2 — new give-up boundary: associativity chain length (few nodes, many conflicts)
**Severity:** LIMIT
_Original classification: `LIMIT (previously unmapped boundary; deterministic, safe as golden`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Comparing left- vs right-associated sums with an `xor 1` mixer, increasing the number
of addends crosses the 100000-conflict budget sharply while the AIG stays tiny.

**Reproducer:**
Reproducer (goldens 09 / 10):
```sh
cd $ROOT/tests/stress/areas/sat/aig_growth_patterns
timeout 30 $ROOT/ucas 09_addchain4_u16.ucas
timeout 30 $ROOT/ucas 10_addchain5_u16.ucas
```
**Observed:**
```
u16, 4 addends -> proved by SAT: 962 AIG nodes, 28512 conflicts
u16, 5 addends -> sampled, not proved; SAT gave up on 1256 AIG nodes ...
```
Full probe (`_scratch/chain_probe.py`), `n` = addends:
```
u16: n=3 SAT 668 nodes/6350 conf | n=4 SAT 962/28512 | n=5 GAVEUP 1256 | n=6 GAVEUP 1550 | n=8 GAVEUP 2138
u32: n=3 SAT 1356/16162 conf      | n=4 GAVEUP 1954      | n=5 GAVEUP 2552 | n=6 GAVEUP 3150 | n=8 GAVEUP 4346
```
Also `add_assoc` (3 addends) at u16/u32/u48/u56/u64 needs
6350 / 16162 / 27765 / 30840 / 46370 conflicts — climbing toward the budget as width
grows. `nested_add3` u64 reaches 49313. These are the widest proved cases found.

### LIMIT-3 — conflicts, steps and solve time are not exposed for give-ups
**Severity:** LIMIT
_Original classification: `LIMIT (observability gap; relevant to "record conflicts/steps/time"`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
Reproducer (MCP golden in this folder):
```sh
cd $ROOT/tests/stress/areas/sat/aig_growth_patterns
timeout 30 $ROOT/ucas --mcp < mcp_aig_nodes.jsonl > /tmp/o 2>&1
python3 -c "import json;[print(json.loads(l)['result']['structuredContent']['result'].get('sat')) for l in open('/tmp/o') if '\"sat\"' in l]"
```
**Observed:** (from `mcp_aig_nodes.out`):
```
{"result": "proved",  "aig_nodes": 2175, "conflicts": 0}
{"result": "gave_up", "aig_nodes": 2230}
{"result": "proved",  "aig_nodes": 737,  "conflicts": 1032}
```
For `gave_up` the structured `sat` object has **only** `aig_nodes` — no conflicts, no
steps, no time. The CLI prose shows only the fixed *budget* constants
(`budget of 100000 conflicts or 100000000 steps`), never the conflicts actually used
or work actually performed. Source inspection: `src/sat.c` tracks `aig_conflicts`
and `aig_worked` but `src/analyze.c:2359-2365` emits `conflicts` only when
`pr.sat_status >= 0 || how == EQ_SAT`, and never emits steps/time at all. Thus a
complete per-family record of "conflicts, steps, time" is impossible via the public
interface; only AIG nodes (all cases) and conflicts (proved cases) are reportable,
and wall time must be measured externally.

### LIMIT-4 — give-up wall time tracks host load, not a hang
**Severity:** LIMIT
_Original classification: `LIMIT (operational; verified not a hang`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Under a heavily loaded host (many parallel stress agents), two wide `mul_pow5`
give-ups exceeded a 20 s harness timeout at u56/u64. Re-running them alone with a
70 s budget returned normally, deterministically:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/sat/aig_growth_patterns/_scratch
python3 -c "import sys;sys.path.insert(0,'.');from sweep import run_case;print(run_case('mul_pow5',64,timeout=70))"
```
**Observed:** `verdict=GAVEUP, nodes=148857, rc=0, t≈11.7 s` (and u56 →
`GAVEUP, 113021 nodes, ≈13.3 s`). No process hung; the fixed 100000-conflict /
100000000-step budget bounds work, but wall clock scales with machine load. Keep
give-up goldens to one statement each and allow generous client timeouts.

### DETERMINISM-1 — all goldens and the sampled probes are stable
**Severity:** DETERMINISM
_Original classification: `— (verified`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`_scratch/determinism.py` ran 9 diverse cases twice (fast proved, give-up, wide
associated adds, shifts, power forms) and compared full stdout/stderr + rc:
**Observed:**
**Reproducer:**
```sh
mul_mask1 u32        DETERMINISTIC rc=0/0      bitslice_add u32   DETERMINISTIC rc=0/0
mul_xor_const u16    DETERMINISTIC rc=0/0      nested_xor3 u24    DETERMINISTIC rc=0/0
add_assoc u64        DETERMINISTIC rc=0/0      rotl3 u48          DETERMINISTIC rc=0/0
mul_pow5 u32         DETERMINISTIC rc=0/0      mul_assoc u24      DETERMINISTIC rc=0/0
de_morgan u32        DETERMINISTIC rc=0/0
```
All 11 CLI goldens + the MCP golden regenerate byte-identically with the canonical
command. The give-up prose (fixed budget, AIG count) and the Schwartz–Zippel note are
static text — safe as goldens.

### LIMIT-5 — `^` (power) vs `xor` and single-letter MCP names (footguns)
**Severity:** LIMIT
_Original classification: `LIMIT (parsing/semantics, not a wrong answer`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
Two families in this sweep are easy to mis-specify:
- `(x*y)^5` means **power** (`x^5*y^5`), not xor; it prints a `note: '^' is power`
  and its give-up nodes differ from the `xor 5` family (u32: 35081 vs 9326).
  MCP refuses the bare `x^y` form with an `ambiguous / caret` error unless
  `assume.caret` is set, whereas CLI silently defaults it to xor — write `xor`.
- An MCP function named `bb` is parsed as `b*b` (juxtaposition ambiguity), so
  `equiv bitsa bb` fails. Use multi-letter non-juxtaposition names. The kept MCP
  golden uses `m1a/m1b/xa/xb/bitsa/bitsb` and is clean.

## Checks that passed

### Method
Sweep harness (`_scratch/sweep.py`) generated **330 distinct family×width cases**:
33 equal-function family shapes (products of increasing width, nested xor/add chains,
multiplier associativity/permutations, bit-sliced adders, barrel shifters/rotates,
table decoders/bit tricks, mask bounds, power forms, parity, random-looking logic
networks) × 10 widths `u12,u16,u20,u24,u28,u32,u40,u48,u56,u64`. Each case runs one
`equiv a b` and the full output is parsed for `AIG nodes`, `conflicts`, verdict and
wall time. Machine-readable data: `_scratch/results.json`; analyzer: `_scratch/analyze.py`.

Final tally: **240 SAT-proved, 60 SAT-gave-up (`sampled`), 30 exhaustive**. AIG node
counts range 25 … 148857; conflicts on proved cases 0 … 49313 (budget 100000).

### 1. No correctness bugs found (positive result — all invariants held)
_Original severity note: * — (negative result)_

Checks across all 330 cases:
- **Monotonicity:** AIG nodes are non-decreasing with width for every one of the 33
  families that reach SAT (0 non-monotonic sequences). E.g. `mul_mask1`:
  `1177,2175,3477,5083,6993,9207,14547,21103,28875,37863` (u12→u64);
  `mul_pow5`: `4011,7761,12743,18957,26403,35081,56133,82113,113021,148857`.
- **Plausibility:** no negative node counts, none above `MAXAIG = 4<<20` (4194304),
  no proved case reported conflicts < 0 or > 100000. Largest proved conflicts = 49313
  (`nested_add3` u64).
- **Consistency:** `mul_assoc` and `mul_3perm` (two syntactically different 3-factor
  products with `xor`) yield byte-identical node sequences at every width
  (`2552,4676,7440,10844,14888,19572,30860,44708,61116,80084`) — evidence the AIG
  builder is deterministic on structure, not on incidental naming.
- **Cross-checked** against the earlier `sat_hard_mult` area: the same node counts
  reproduce (`mul_xor_const` u16 = 2230, u32 = 9326, u64 = 38110; `mul_pow5`/`^5`
  u32 = 35081, u64 = 148857).

### Correction made during the sweep (not a tool bug)
The first `parity2` draft used a malformed identity
(`(x+y)&1 xor ((x&y)&1)<<1`), which correctly returned `DIFFER` at all 10 widths.
It was replaced with `(x+y)-2*(x&y) & 1` and re-run — all 10 widths then proved by
SAT with 0 conflicts (nodes 223 … 1263). No tool defect involved; the corrected
numbers are what is in `results.json` and the reported tally.
