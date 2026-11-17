# SUMMARY — `sat_crypto_circuits`

## Counts
- Distinct expressions/queries tried: ≈358
- Goldens written: 18
- Files created: not recorded

### Counts

- **Distinct statements / queries tried:** ≈ **358**
  - 191 exploratory statements across 51 throwaway probe files in `_scratch/`
  - 158 non-comment statements in the 18 kept golden `.ucas` files
  - 9 MCP `tools/call` queries in `mcp_sat_crypto.jsonl`
  - Plus repeated runs for determinism checks (not counted as new statements).
- **Files created (kept goldens):**
  - 18 CLI goldens: `01_gf8_mul` … `18_budget_xor_mul` (`.ucas` + `.out` each)
  - 1 MCP golden: `mcp_sat_crypto.jsonl` + `mcp_sat_crypto.out`
  - This `SUMMARY.md` and `FINDINGS.md`
  - `_scratch/` contains the generators and exploratory probes (not goldens).
- **Issues by severity:** WRONG **3**, LIMIT **8**, CRASH **0**, HANG **0**,
  DETERMINISM **0**, NLP **0**.


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 3 | — |
| LIMIT | 8 | — |

### Goldens (all deterministic; run twice and byte-identical)

| file | area | statements | worst wall time |
|---|---|---|---|
| `01_gf8_mul.ucas` | GF(2^8) xtime/mul, associativity give-up | 13 | 3.2 s |
| `02_aes_sbox_inv.ucas` | AES inverse x^254, involution, range | 10 | 0.02 s |
| `03_sha_rot_xor.ucas` | SHA Σ/σ, Ch, Maj via SAT | 13 | 0.03 s |
| `04_crc_lfsr.ucas` | CRC feedback, LFSR taps | 10 | 0.02 s |
| `05_bit_perm.ucas` | reversal, byte swap, neighbour swap | 10 | 0.01 s |
| `06_xor_and_net.ucas` | XOR/AND reduction networks | 7 | 0.03 s |
| `07_gf2_linear.ucas` | GF(2) linear maps, where clause | 9 | 0.01 s |
| `08_arx_mix.ucas` | 32-bit add-rotate-xor mixing | 9 | 0.03 s |
| `09_gf2n_mul.ucas` | GF(2^16) mul + range counterexample | 11 | 4.9 s |
| `10_sbox_tables.ucas` | `[]`/`match` S-boxes, `phash`, OOB domain | 12 | 0.11 s |
| `11_bitslice.ucas` | bit-sliced zero/equality predicates | 7 | 0.02 s |
| `12_gates_crypto.ucas` | minimal Ch/Maj gate networks, SHA basis | 7 | 0.01 s |
| `13_find_crypto.ucas` | `find` on small mixers | 6 | 1.7 s |
| `14_budget_equiv.ucas` | masked-multiplier SAT give-up | 3 | 7.7 s |
| `15_gates_budget.ucas` | `gates` node-budget give-up (6-bit S-box) | 2 | 11.4 s |
| `16_budget_gf16.ucas` | GF(2^16) commutativity give-up | 5 | 8.5 s |
| `17_power_no_sat.ucas` | `^`-as-power blocks reflexive proof | 2 | 0.01 s |
| `18_budget_xor_mul.ucas` | XOR-of-multipliers give-up | 3 | 8.3 s |
| `mcp_sat_crypto.jsonl` | MCP: raw define, equiv ×3, range, gates, find, domain, vacuous equiv | 9 | < 15 s total |

Generation used, from this directory:

```sh
timeout 30 $ROOT/ucas NAME.ucas > NAME.out 2>&1
timeout 30 $ROOT/ucas --mcp < mcp_sat_crypto.jsonl > mcp_sat_crypto.out 2>&1
```

Every golden was then re-run and `diff`ed against its `.out` with exit code 0.


## Takeaway
The SAT/proof core is sound on the equivalences tried (no wrong `equal:true` for actually-different circuits and no nondeterminism), but it gives up predictably on multiplication-heavy crypto circuits (masked u32 products, GF(2^16) products, GF(2^8) associativity, XOR of multipliers) and on 6-bit S-box synthesis; the substantive defects are a `range` headline that excludes a reachable value (`gm16` max printed 65534 while `gm16(1,65535)=65535`), a self-contradictory `domain` report for constant shifts by the width, and vacuous "proved by SAT" answers for everywhere-undefined functions.

### Original takeaway (verbatim)

The SAT/proof core is sound on the equivalences tried (no wrong `equal:true`
for actually-different circuits and no nondeterminism), but it gives up
predictably on multiplication-heavy crypto circuits (masked u32 products,
GF(2^16) products, GF(2^8) associativity, XOR of multipliers) and on 6-bit
S-box synthesis; the substantive defects are a `range` headline that excludes a
reachable value (`gm16` max printed 65534 while `gm16(1,65535)=65535`), a
self-contradictory `domain` report for constant shifts by the width, and
vacuous "proved by SAT" answers for everywhere-undefined functions.
