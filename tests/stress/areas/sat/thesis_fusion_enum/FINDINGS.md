# Stress findings — `thesis_fusion_enum`

_Original heading: Findings — `thesis_fusion_enum`_

# Findings — `thesis_fusion_enum`

All runs used `$ROOT/ucas` from this directory, bounded by `timeout`.
No source files were edited. The generator is `gen.py`; the independent range oracle is
`_scratch/oracle.py`; the perf timing harness is `_scratch/perf_probe.py`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| HANG | 1 | SAT give-up time is not stable; identical input can exceed 30 s |
| LIMIT | 2 | new SAT give-up boundaries well beyond `tests/satsteps.ucas` |

## Findings

### HANG-1 — SAT give-up time is not stable; identical input can exceed 30 s
**Severity:** HANG
_Original classification: `HANG + DETERMINISM`._
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (file is `_scratch/perf_p1.ucas`, content shown):

```sh
cd $ROOT/tests/stress/areas/sat/thesis_fusion_enum
cat > _scratch/perf_p1.ucas <<'EOF'
pf(x: u32, y: u32, z: u32) = ((x*y)*z) ^ 5
pg(x: u32, y: u32, z: u32) = ((y*x)*z) ^ 5
equiv pf pg
EOF
for i in 1 2 3; do
  start=$(date +%s%N)
  timeout 29 $ROOT/ucas _scratch/perf_p1.ucas > _scratch/run$i.out 2>&1
  ec=$?
  echo "run$i exit=$ec wall_ms=$(( ($(date +%s%N)-start)/1000000 ))"
done
```

**Observed:**

```
run1 exit=124 wall_ms=29046
run2 exit=0   wall_ms=18054
run3 exit=0   wall_ms=16723
```

`run1.out` (timeout) contains only the three echoed statements and **no answer**:

```
> pf(x: u32, y: u32, z: u32) = ((x*y)*z) ^ 5
> pg(x: u32, y: u32, z: u32) = ((y*x)*z) ^ 5
> equiv pf pg
```

`run2.out` and `run3.out` are byte-identical and contain:

```
pf and pg are equal on the domain of pf (sampled, not proved; SAT gave up on 44720 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
  polynomials of total degree at most 15, equal at 4 random points mod 2^61 - 1: ... (Schwartz-Zippel), ...
```

**Why it matters:** the *answer text* is deterministic (the AIG-node count and budget are
counters, not wall time), but the *time to reach it* varies from ~16.7 s to >29 s on the
same machine for the same bytes. Since the stress runner uses `timeout 30`, this input
is a flaky hang: it sometimes produces a golden, sometimes produces nothing. It is
therefore **not** kept as a `.out` golden; it lives only here and in
`12_perf_pathological.ucas` (which also has no golden).

### LIMIT-1 — new SAT give-up boundaries well beyond `tests/satsteps.ucas`
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

**Observed:**
```sh
cd $ROOT/tests/stress/areas/sat/thesis_fusion_enum
timeout 29 $ROOT/ucas 12_perf_pathological.ucas
```

The corpus `satsteps.ucas` records the canonical boundary for a product against its
swap under an xor. The pathological generator found substantially larger AIG frontiers
before the same 100000-conflict / 100M-step budget gives up:

| input | type | AIG nodes at give-up | notes |
|---|---|---|---|
| `tests/satsteps.ucas` `(x*y)^5` vs `(y*x)^5` | u32 | 35081 | baseline, ~11.9 s |
| `12_perf_pathological.ucas` p1 `((x*y)*z)^5` vs `((y*x)*z)^5` | u32 | 44720 | 16.7–29+ s (see finding 1) |
| `12_perf_pathological.ucas` p2 `((x*y)^5)*z` vs `((y*x)^5)*z` | u32 | 44720 | ~27.8 s in one run |
| `12_perf_pathological.ucas` p3 `((x*y)*(y*z))^0x5a` vs swap | u32 | 90933 | completed once, timed out at 29 s in another run |
| `12_perf_pathological.ucas` p4 `(x*y)^5` vs `(y*x)^5` | u64 | 148921 | completed 11.8/13.1 s alone; timed out at 29 s in the probe |

For p3 the first combined run printed:

```
pf_p3 and pg_p3 are equal on the domain of pf_p3 (sampled, not proved; SAT gave up on 90933 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```

and for p4 (run alone):

```
pf4 and pg4 are equal on the domain of pf4 (sampled, not proved; SAT gave up on 148921 AIG nodes within its budget of 100000 conflicts or 100000000 steps)
```

The whole `12_perf_pathological.ucas` file timed out (`exit=124`) after finishing only
p1 in a fresh run. **
**Why it matters:** these are new, reproducible performance cliffs
(up to ~4.2x the baseline AIG frontier) and confirm that the SAT budget is the binding
constraint on fusion-pair proofs. This file is deliberately NOT a golden.

### LIMIT-2 — no standalone `differ` command; the thesis' "assert differ" must use `error` or `equiv`
**Severity:** LIMIT
_Original classification: `LIMIT (documentation of an oracle gap, not a crash`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**

```sh
cd $ROOT
printf 'f(x: u8, y: u8) = x+y\ng(x: u8, y: u8) = y+x\ndiffer f g\n' | ./ucas 2>&1
```

**Observed:**

```
<stdin>:1:10: error: f takes 2 arguments
    differ f g
             ^
```

`differ` is parsed as an ordinary identifier, not a command — e.g. `differ (x^2)`
defines `_(differ: real, x: real) = differ*x^2`. **Expected / workaround:** the
"differ finds nothing" half of a Semantic Fusion pair is expressed as
`error g ~ f` reporting `max abs error 0` (used in files 01–07 and in
`mcp_fusion_pairs.jsonl`), while the "must report a difference" half is the ordinary
`equiv` output `... differ at N points ...` (used in `13_nearmiss_differ.ucas`).
This is why the fusion goldens use `error` rather than a literal `differ` statement.

## Checks that passed

### Negative results (things checked that were clean)
- **Exhaustive enumeration soundness:** all 288 depth-1 expressions over
  `+ - * & | xor << >>` on **u4**, all 288 on **u8**, and a deterministic 400-expression
  depth-2 family on u4 (976 total) were `range`d in ucas and independently re-evaluated
  over the whole machine domain in Python (`_scratch/oracle.py`, logs
  `_scratch/oracle_bulk.out`, `_scratch/oracle_u8.out`). **0 wrong ranges** — min, max,
  distinct count, the emitted value list (including run compression and the u8
  24-entry truncation), and the undefined-shift point count all matched for every
  expression.
- **Fusion soundness:** every equal-by-construction pair in files 01–07 proved equal
  (exhaustive / SAT / algebra) and `error g ~ f` reported max abs error 0. **0 false
  "differ"** on genuinely-equal pairs.
- **Near-miss soundness:** all 8 deliberately-unequal pairs in `13_nearmiss_differ.ucas`
  were reported as `differ at N points` with a concrete witness; witnesses for n1, n6,
  n8 were re-evaluated by hand and are valid. **0 false "equal:true"**.
- **Reflexivity:** `equiv e e` proved equal for all 15 enumerated expressions in file 09.
- **Crashes:** **0** — all goldens exited 0; no signals, truncated JSON, or malformed
  outputs were observed in this area.
