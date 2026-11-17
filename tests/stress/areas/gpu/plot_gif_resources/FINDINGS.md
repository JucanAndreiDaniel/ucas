# Stress findings — `plot_gif_resources`

_Original heading: FINDINGS — `plot_gif_resources`_

# FINDINGS — `plot_gif_resources`

Area: plotting, GIF generation, file-writing side effects.
Binary: `$ROOT/ucas` (already built; nothing rebuilt).
All probes ran with `cwd` inside `tests/stress/areas/gpu/plot_gif_resources/` (or a temp
subdirectory of it), always under `timeout`. No source, Makefile, shared test or
`opencode.json` was touched. No stray processes were left running.

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 3 | MCP silently drops oversized GIFs |
| LIMIT | 2 | `animate exec ... frames N` becomes a new variable |
| DETERMINISM | 1 | unseeded `random` animations |

## Findings

### WRONG-1 — MCP silently drops oversized GIFs
**Severity:** WRONG
_Original classification: `WRONG (medium`._
**Why it matters:** _not recorded_
The README states that MCP keeps images under 4 MiB of base64 by re-rendering
animations at a lower frame rate first. Instead, when the base64 would exceed
4 MiB, the `image` content block is simply omitted, with no note, no error and
`isError:false`; the client receives no GIF at all.

**Reproducer:**
Reproducer (copy-pasteable):

```sh
cd $ROOT/tests/stress/areas/gpu/plot_gif_resources
cat > /tmp/pgr_cap.jsonl <<'EOF'
{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"stress","version":"1"}}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"plot","arguments":{"op":"plot","args":{"fs":"x^2+y^2+t+s","options":"frames 160"}}}}
EOF
timeout 30 $ROOT/ucas --mcp < /tmp/pgr_cap.jsonl
```

**Observed:** (parsed from the response):

```
isError: False
content types: ['text', 'text']          <-- no image block
files: [{'name': 'plot.gif', 'mime': 'image/gif', 'bytes': 3187440}]
notes: []
text tail: '... animation: 780x640, 240 frames at 8 fps (30.0 s), 3187440 bytes\n  attached plot.gif (3187440 bytes)\n'
```

Threshold behaviour, measured over `frames N` on the same plot:

```
frames 100 -> GIF 1,993,759 B -> base64 2,658,348 chars -> image block PRESENT
frames 160 -> GIF 3,187,440 B -> base64 4,249,920 chars -> image block DROPPED
frames 180 -> GIF 3,583,155 B -> image block DROPPED
frames 200 -> GIF 3,982,101 B -> image block DROPPED
```

With `--dir`, the GIF is written to disk but still no image block is returned and
still no note is emitted:

```
$ timeout 120 ucas --mcp --dir /tmp/pgr_capdir < /tmp/pgr_cap.jsonl
# /tmp/pgr_capdir/bigplot.gif created (3,187,440 bytes)
# content types: ['text','text']; isError False; notes []
```

**Expected:** either re-render at a lower frame rate to get under the cap (as
documented), or emit a note/error saying the image was omitted. Silently
returning `ok` with a `files` entry but no bytes is a user-visible data loss.

### WRONG-2 — silent `--files write --dir` failure (JSON mode)
**Severity:** WRONG
_Original classification: `WRONG (medium`._
**Why it matters:** _not recorded_
A `--dir` that cannot be written is not fatal: `ok:true`, no top-level `error`,
no `notes`, and the text even claims the file was written. Only a per-file
`error` field records the failure.

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/gpu/plot_gif_resources
printf '%s\n' '{"id":1,"cmd":"plot","args":{"fs":"sin x"}}' | \
  timeout 10 $ROOT/ucas --json --files write --dir /no/such/dir
```

**Observed:** (trimmed):

```json
{"id":1,"ok":true,"cmd":"plot","structured":true,
 "result":{"kind":"plot",...,"details":[...,"wrote plot.gif"]},
 "notes":[],"checks":[],
 "files":[{"name":"plot.gif","mime":"image/gif","bytes":8729,
           "error":"No such file or directory"}],
 "text":"...\n  wrote plot.gif\n"}
```

With `--dir` pointing at a regular file, the only difference is
`"error":"Not a directory"`. No file is created anywhere (no fallback to cwd).
MCP behaves differently and better at startup: `ucas --mcp --dir /no/such/dir`
exits 2 with `/no/such/dir: No such file or directory` on stderr.

**Expected:** top-level `ok:false`/`error` (or at least a note), and the text should
not claim `wrote plot.gif`.

### WRONG-3 — NaN interval in plot details
**Severity:** WRONG
_Original classification: `WRONG (low`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/gpu/plot_gif_resources
timeout 10 $ROOT/ucas -e 'plot sin x x in -1e308..1e308 nofile'
```

**Observed:**

```
plot of sin(x)
  x in [-1e+308, 1e+308]: given
  y in [-1, 1]: the values
  sin(x): 1201 samples
    undefined for x in [-nan, inf]
  image: 640x440, 3310 bytes
  (nofile: GIF checksum 2d45c68a)
```

The same string appears in `structuredContent.result.details` in JSON/MCP mode.
`[-nan, inf]` is not a valid interval; the subtraction of `-1e308` and `1e308`
(or the sample spacing) has overflowed to `-nan`. Expected a valid interval or a
plain "all samples undefined" message.

### LIMIT-1 — `animate exec ... frames N` becomes a new variable
**Severity:** LIMIT
_Original classification: `LIMIT / NLP (low`._
**Why it matters:** _not recorded_
`frames` is a plot option, not an `animate exec` option, but instead of being
rejected or ignored it is lexed as an identifier and appended to the expression:

**Reproducer:**
```sh
cd $ROOT/tests/stress/areas/gpu/plot_gif_resources
timeout 10 $ROOT/ucas -e 'animate exec of 32-bit x*x+1 frames 100000 nofile'
```

**Observed:**

```
exec of x*x + 100000frames, cost model gt1030, 4 lanes in lockstep; x: u32, frames: u32
  result per lane: 100000 200001 300004 400009
  t1 = 100000 * frames   imul 3 ...
```

The program whose GIF is rendered is now `x*x + 100000*frames` with a free
variable `frames`, not the requested `x*x + 1`.
**Expected:** reject the unknown
option (`I don't understand 'frames 100000'`) as other unknown trailing tokens
are, or accept it as an option.

### DETERMINISM-1 — unseeded `random` animations
**Severity:** DETERMINISM
_Original classification: `DETERMINISM (info`._
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`animate exec of 32-bit x*x+1 random` reports a time-derived seed:

**Observed:**
**Reproducer:**
```sh
random inputs (seed 57051)   # process A
random inputs (seed 57059)   # process B
```

Within one JSON session the seed advances slowly (0,0,0,1,1,1,1,1), so repeated
calls can coincidentally match. No golden was kept for unseeded random output.
Use an explicit `seed K` (verified deterministic: `random seed 1` gives the same
GIF hash on every call) — `07_animate.ucas` does this. Other plots, surfaces,
animations and all `nofile` checksums were byte-for-byte deterministic across
repeated runs and across processes.

### LIMIT-2 — sampling/range options quietly ignored or clamped
**Severity:** LIMIT
_Original classification: `LIMIT (info`._
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
- `plot sin x points 0 nofile` and `plot sin x points 1 nofile` still report
  `1201 samples` (same GIF checksum as the default).
- `plot sin x points 1000000 nofile` reports `100000 samples` (capped) with no
  note.
- `plot sin x x in 1..0 nofile` and `y in 1..0` are silently normalised to
  `[0, 1]`; the user's reversed range is not reported.
- `frames 0` and `fps 0` fall back to the defaults (30 frames / 12 fps);
  negative `fps`/`frames` are correctly rejected.
- `frames 100000` and `seconds 100000` are clamped to 240 frames (20 s) with no
  note.

These are not crashes, but a caller cannot tell that the requested sampling was
not applied.

## Checks that passed

### Summary of issues
| # | Severity | Title |
|---|----------|-------|
| 1 | WRONG (medium) | MCP silently drops a GIF whose base64 exceeds 4 MiB instead of re-rendering it |
| 2 | WRONG (medium) | `--files write --dir DIR` reports success when the write fails (JSON mode) |
| 3 | WRONG (low) | NaN bound in printed interval: `undefined for x in [-nan, inf]` |
| 4 | LIMIT / NLP (low) | `animate exec ... frames N` silently absorbs `frames` as a variable |
| 5 | DETERMINISM (info) | Unseeded `random` animations use a time-derived seed (no golden kept) |
| 6 | LIMIT (info) | `points 0/1` ignored; `points 1000000` capped at 100000 with no note; reversed ranges silently normalised |

No CRASH, no HANG, no invalid GIF bytes and no files written outside this folder
were found in ~325 invocations.

### Things checked that were CLEAN
- **183 MCP calls** in `mcp_stress_*.jsonl` (0 crashes, 0 hangs, 0 malformed
  JSON-RPC responses, 0 missing responses); 12 base64 GIFs returned, all valid.
- **102 CLI plot/animate statements** in the two CLI batteries, plus ~40 targeted
  probes: no nonzero exit, no timeout, no unexpected file.
- **GIF bytes**: 9 representative GIFs (still, region, vector field, slope field,
  space curve, 36-frame rotation, 240-frame animations) all have the `GIF89a`
  header, trailer `0x3b` as the last byte, zero trailing bytes, a frame count
  matching `image.frames`, and load correctly in Pillow (`n_frames` 1/36/240).
  Declared `bytes` always equals the decoded base64 length.
- **File side effects**: default CLI writes only `plot.gif` (or `NAME.gif`) into
  the current directory; `to NAME` writes `NAME.gif`; dots, `/` and absolute
  paths are rejected (`to: a name` in JSON, parse error / "sorry" in CLI).
  Nothing was written outside this folder. `--files none|base64|both|write`,
  per-request `args.files`, and MCP `--dir` are honoured. Module/Image writers
  (`spirv_simplify` → `simplified.spvasm`, `plot` → `plot.gif`) all land in
  `--dir`. `--mcp --flat` routes plot/plot3d/animate/area correctly.
- **Leaks**: a 200-call JSON plot session kept RSS flat (~14–18 MB) and wrote no
  files in `base64`/`nofile` modes; 30 repeated plot calls produced 30 valid,
  byte-identical GIFs.

### Golden files and determinism
All kept goldens were run twice and `diff`ed clean:
`01_plot_1d`, `02_plot_degenerate`, `03_plot_geometry`, `04_plot_surface`,
`05_plot_malformed`, `06_solids`, `07_animate`, `08_plot_lexer_error`,
`mcp_small_plot`, `mcp_plot_nofile`, `mcp_plot_errors`.

`mcp_small_plot.out` deliberately keeps the **full base64 GIF** (9,914 bytes of
JSON-RPC, 8,016 base64 chars) — it was NOT trimmed; the GIF is deterministic and
small enough to keep verbatim.
