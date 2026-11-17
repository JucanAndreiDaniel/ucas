# Stress findings — `table_interpolation`

_Original heading: Findings — `table_interpolation` stress area_

# Findings — `table_interpolation` stress area

Audit target: `[t0,...][i]` lookups, mixed element types, out-of-range /
negative indices, index coercion, nested tables, tables in `match`/`where`,
`find` packed constants, and `texenc` block encodings.  Binary:
`$ROOT/ucas`.  All runs were bounded with `timeout`.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| LIMIT | 2 | 1 — cannot chain table lookups with a runtime (non-constant) index |

## Findings

### LIMIT-1 — 1 — cannot chain table lookups with a runtime (non-constant) index
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**
Reproducer** (from this folder):

```sh
cd $ROOT/tests/stress/areas/math/table_interpolation
cat > /tmp/nest.ucas <<'EOF'
T = [[10,20],[30,40]]
show T[1][0]
g(x: u8 in 0..1) = T[x][0]
EOF
timeout 15 $ROOT/ucas /tmp/nest.ucas
```

**Observed:** output:

```
> T = [[10,20],[30,40]]
> show T[1][0]
_() = 30
  -> int
> g(x: u8 in 0..1) = T[x][0]
/tmp/nest.ucas:3:26: error: only a table [a, b, ...] can be indexed
    g(x: u8 in 0..1) = T[x][0]
                              ^
```

**Why it matters:** it is a limitation:** With a *constant* outer index the lookup is
folded to the inner table node, so `T[1][0]` works.  With a *variable* outer
index the result is an `O_INDEX` node whose type is the outer table's scalar
element type (`int`), so the trailing `[0]` sees a non-table and is rejected.
The same function can *return* the inner table (`u(x) = T[x]` prints `[30, 40]`
but is annotated `-> int`), yet that returned value cannot be indexed: `u(x)[0]`
and `(T[x])[0]` both fail identically.  A 2-D/row-major lookup should be
composable, or the table-valued result should keep a type that can be indexed.
Also captured in `09_errors.ucas` / `09_errors.out`.

### LIMIT-2 — 2 — heterogeneous nested tables are flattened before a second index
**Severity:** LIMIT
**Expected:** _not recorded_
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/math/table_interpolation
cat > /tmp/het.ucas <<'EOF'
show [[1,2],[3,4]][1][1]
show [[u8(1),u16(2)],[i8(3),i8(4)]][1][1]
EOF
timeout 15 $ROOT/ucas /tmp/het.ucas
```

**Observed:** output:

```
> show [[1,2],[3,4]][1][1]
_() = 4
  -> int
> show [[u8(1),u16(2)],[i8(3),i8(4)]][1][1]
/tmp/het.ucas:2:42: error: only a table [a, b, ...] can be indexed
    show [[u8(1),u16(2)],[i8(3),i8(4)]][1][1]
                                             ^
```

**Why it matters:** it is a limitation:** The outer table's rows have different common
types (`[u8,u16]` -> `u16`, `[i8,i8]` -> `i8`).  `mk_table` reduces them to one
common scalar type and casts each row to it, which destroys the inner table
nodes; the second `[1]` then has no table to index.  Homogeneous rows work.
This is a consequence of the same "table of tables is not a first-class type"
design as LIMIT-1.  Also captured in `09_errors.ucas` / `09_errors.out`.

## Checks that passed

### Summary of outcome
No CRASH, HANG, WRONG result, or nondeterminism was found in the core
lookup semantics.  A Python list model (`verify_model.py`) over 179 lookups,
37 `find` packed-constant/`equiv` differentials (`verify_find.py`), and 60
independent BC4 decoder checks (`verify_texenc.py`) all agreed with ucas.
Two structural **LIMIT** findings are documented below.

### Documented (not bugs) — verified as intended
These were checked and behave as documented; recorded so they are not
mistaken for regressions later:

* `texenc` refuses a table with entries outside `0..1` (or whole `0..255`)
  even with a large `tol`: `error: texenc: BC4 holds numbers from 0 to 1 ...
  U has an entry that is neither`.  Repro: `07_texenc.ucas`, `mcp_tables.jsonl`
  (id 8).
* A literal that does not fit the table's promoted element type is narrowed
  **with a note** (`note: literal 300 does not fit u8; it becomes 44`), not
  silently.  Repro: `02_mixed_types.ucas`.
* `show [10,20,30][3]` (out of range) and `show [10,20,30][-1]` both give
  `undefined`; `domain`/`range` report the restricted region and the count of
  undefined points.  Repro: `01_basic.ucas`, `08_domains.ucas`.
