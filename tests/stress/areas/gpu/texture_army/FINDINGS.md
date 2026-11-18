# Stress findings — `texture_army`

Area: the constant-table codecs (`texenc.c`, `astc.c`, `astcblk.c`,
`bc7blk.c`, `etc2blk.c`, `tex.c`) and their CLI / English / MCP frontends.
Inputs and goldens were generated with the canonical environment
(`UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none`) from the fixed binary.

## Summary

| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | a 3-D or suffixed ASTC footprint was silently accepted as its 2-D prefix |

All eight goldens were run twice and were byte-identical.  Seven controls
(all 14 valid footprints, a valid English sentence, zero/invalid BH already
refused, and the ASTC decoder steps at their boundaries) found no wrong
decode.  Exhaustive differential checks of `astc_unquant`,
`astc_unquantw`, `astc_endpoint`, `astc_lerp` and `astc_partition` against a
translation of the astcenc-checked decoder in `astcblk.c` (all colour and
weight ranges and every value, 3,200 endpoint cases, 2,340 weights, 17,408
partition points) found no mismatch.  Random `texenc` sweeps over BC4/BC5,
EAC, ETC2, BC7, BC6H and all 14 ASTC footprints (3,900 cases), plus
ASan/UBSan fuzzing of the raw block decoders (200,000 random blocks), found
no crash or encoder/decoder disagreement.

## Findings

### WRONG-1 — `texenc` accepted a malformed ASTC footprint by dropping trailing characters

**Severity:** WRONG (malformed input silently accepted; also recorded as
WRONG-8 in `gpu/tex_domain_modules/FINDINGS.md`).
**Root cause:** `texenc_command` parsed the second component of `BWxBH` with
`atoi(w + 1)`, which stops at the first non-digit.  `4x4x4` and `4x4foo`
therefore became `4x4` and a valid block was written.  The English path had
the same fault: `sscanf(w, "%dx%d", ...)` ignored the trailing `x6` and
rebuilt the command as `astc 6x6`.

**Reproducer (CLI, fixed binary):**
```sh
cd tests/stress/areas/gpu/texture_army
env UCAS_NO_TIMES=1 UCAS_SPIRV_CROSS=none $ROOT/ucas 02_bad_3d_footprint.ucas
# error: texenc: astc takes a block's footprint, BWxBH (6x6, 8x5, ...)
```
Goldens: `02_bad_3d_footprint.out`, `03_bad_suffix_footprint.out`,
`05_bad_english_footprint.out`, `mcp_bad_footprint.out`.

**Observed before the fix:** `texenc [1,2,3,4] astc 4x4x4` printed a full
`ASTC_4x4_UNORM` report and block bytes; `compress R as ASTC 6x6x6` printed
`ucas: texenc R astc 6x6` and encoded a 6x6 block.  The MCP tool returned
`ok:true` with a 4x4 block for `"astc":"4x4x4"`.

**Expected:** a domain error, since the tool's own usage says 2-D footprints
only.  The fix validates that BH is a non-empty string of decimal digits
(`footprint_h`) and keeps the whole footprint token in the English rewrite so
it reaches that check.  Valid footprints, including the documented spaced
forms `4x 4` / `4 x 4`, are unchanged (`01_valid_footprints.out`,
`06_english_valid.out`).

## Existing goldens needing recapture

- `tests/stress/areas/gpu/tex_domain_modules/mcp_texenc_astc_etc.out`
  (id 8, `"astc":"4x4x4"`) currently records the buggy `ok:true` 4x4 report.
  After this fix that reply becomes an error (`code:"failed"`,
  `isError:true`).  The parent should run `bmake stress-accept
  STRESS_AREA=tex_domain_modules` for that area; I did not modify it.

## Checks that passed

- Control `01_valid_footprints`: all 14 footprints (4x4 .. 12x12) and both
  spaced spellings still encode and decode with stable bytes.
- Control `06_english_valid`: `compress R as ASTC 6x6` still rewrites to a
  valid 6x6 `texenc` command.
- Control `04_bad_zero_footprint`: `4x0` was already refused.
- Control `07_decoder_boundaries`: `astc_unquant` at 6 and 256 levels,
  `astc_unquantw` at 2 and 32 levels, `astc_lerp` at w = 0/64, the HDR error
  colour, the small-block partition hash and a weight grid read one grid past
  its edge all produce stable, correct values.
