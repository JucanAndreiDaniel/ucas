> **Portability:** set `ROOT=/path/to/ucas` (the repo root) before copy-pasting reproducers below, or `cd` to the repo root and use `ROOT=$PWD`; `$ROOT/ucas` is the built binary.

# New stress ideas — source audit + external testing tricks

Author: IDEA RESEARCHER subagent. Do **not** modify source. Nothing here is a golden test;
this is a ranked backlog for the orchestrator to assign to implementation subagents.

Scope read: `tests/stress/SPEC.md`, `tests/stress/MASTER_FINDINGS.md` (29 covered areas),
and the C sources under `src/`. External inspiration was verified by fetching CWE pages
(websearch returned no results in this environment, so CWE/OWASP URLs were fetched directly).

Legend for coverage marks:
- **[NEW]** — not represented in `MASTER_FINDINGS.md`.
- **[PARTIAL]** — an adjacent area exists but this exact input class/edge was not tried.
- **[COVERED]** — already reported; listed for completeness / as a "do not redo" marker.

Rank = expected yield × novelty × cheapness. Top 10 are copy-pasteable and were prioritised
for the quick probes in the last section.

---

## Top 10 — exact commands

| # | Command / input | Target |
|---|---|---|
| 1 | `printf '%s\n' '{"jsonrpc":"2.0","id":1e400,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"s","version":"1"}}}' \| ./ucas --mcp` | MCP emits bare `id: 1e400` (Infinity) — invalid JSON number |
| 2 | `UCAS_SEED=abc ./ucas -e $'f(x)=x+1\ng(x)=1+x\npit f g trials 8'` | unchecked `strtoull` env → seed 0 (instead of default 1) |
| 3 | `UCAS_SEED=-1 ./ucas -e $'f(x)=x+1\ng(x)=1+x\npit f g trials 8'` | seed becomes `18446744073709551615` |
| 4 | `timeout 10 ./ucas -e 'abselftest 2147483647'` | `atoi` with no bound → 10 s timeout (rc 124) |
| 5 | `timeout 10 ./ucas -e 'diophantine x^2 + 2*y^2 = 3 count -1'` | negative `count`/`search`/`maxmult` silently accepted |
| 6 | `printf 'f(x)=x+1\ng(x)=1+x\npit f g trials 8 seed -1\n' \| ./ucas` | explicit negative `seed K` reaches `rseed()` unchecked |
| 7 | `./ucas -e 'show 1e400'` and `./ucas -e 'show f32(1e400)'` | `strtod(buf,NULL)` with no `ERANGE` check for reals |
| 8 | `printf 'pit f g trials 8\n' \| ./ucas` twice with `UCAS_SEED=0` vs `UCAS_SEED=1` | env-driven nondeterministic verdict on a *false* identity |
| 9 | `./ucas --json` request `{"id":7,"cmd":"pit","args":{...,"seed":-1}}` | JSON-mode numeric seed path (different parser from MCP) |
| 10 | `timeout 10 ./ucas -e 'abselftest 1000000'` | atoi scales to 1e6 iterations — measure time (resource asymmetry) |

Probe evidence is at the end of this file.

---

## A. Ideas derived specifically from suspicious source patterns

### 1. JSON number canonicalization / Infinity smuggling  [SRC] [NEW]
- **Idea:** `strtod` parses `1e400` to `inf` but the writer preserves the original token string, so the server emits a non-finite JSON number.
- **Inspired by:** `src/json.c:327` `v->num = strtod(v->s, NULL);` (no `isfinite` check, unlike `jv_num()` at line 68) and `src/json.c:532` writer uses `v->s` verbatim.
- **Input shape:** MCP `initialize` / any request with `"id":1e400`, `"id":-1e400`, `"id":1E+9999`, `"timeout_s":1e400`, or an argument `{"x":-0.0}`.
- **Bug class:** WRONG / protocol conformance; strict JSON consumers reject `1e400` as `Infinity`, and a client can smuggle a non-finite value past validation that checks `isfinite(num)`.
- **Why missed:** `schema_conformance` checked the envelope shape and all 27 tool families but used ordinary finite ids; `mcp_api_fuzz` tested `timeout_s:1e400` but only as a disabled timer, not as an echoed id/argument. `parser_json_fuzz` tested nesting, not numeric tokens.

### 2. `UCAS_SEED` environment variable is parsed with unchecked `strtoull`  [SRC] [NEW]
- **Idea:** seed for every stochastic verifier is taken from `getenv("UCAS_SEED")` with `strtoull(e,NULL,10)` and no validation of the end pointer, sign or range.
- **Inspired by:** `src/stoch.c:117-125` `stoch_seed()`.
- **Input shape:** `UCAS_SEED=abc|""|-1|0|18446744073709551616 ./ucas -e $'f(x)=x+1\ng(x)=1+x\npit f g trials 8'`; also `stoke`, `phash`, `find stoke`.
- **Bug class:** WRONG / DETERMINISM — `abc`→0, `-1`→ULLONG_MAX, huge→saturates; a probabilistic `equal:true` can flip with the ambient environment.
- **Why missed:** `env_locale_tty` covered 28 env configs but not `UCAS_SEED`; `timeout_isolation` covered `timeout_s`, not seeds.

### 3. `abselftest N` unbounded `atoi` → controllable CPU DoS  [SRC] [NEW]
- **Idea:** `int n = atoi(s)`, `n <= 0 → 100`, otherwise used directly as the number of random group pairs.
- **Inspired by:** `src/absalg_cmd.c:1288-1297` `cmd_selftest`.
- **Input shape:** `timeout 10 ./ucas -e 'abselftest 2147483647'` (probed: rc 124), `abselftest 1000000`, `abselftest 99999999999999999999` (atoi overflow → default 100, so silently ignored).
- **Bug class:** HANG / LIMIT — silent clamping of out-of-range values; no timeout around the self-test.
- **Why missed:** `resource_limits` tested parser nesting/table caps, not command-specific numeric options; `--sat-selftest` was tested but `abselftest` is a different selftest with a different parser.

### 4. Unchecked `strtol`/`strtoll` end pointers in `diophantine` options  [SRC] [NEW]
- **Idea:** `count`, `maxmult`, `search` are parsed as `(int)strtol(t + N, &t, 10)` / `strtoll(t + N, &t, 10)` with no sign, range, or trailing-junk validation.
- **Inspired by:** `src/ec_cmd.c:973-982`.
- **Input shape:** `diophantine a/(b+c) + b/(a+c) + c/(a+b) = 4 count -1`, `... maxmult -5`, `... search 9999999999999999999999`, `... count 12junk`.
- **Bug class:** WRONG / HANG — negative counts can invert loop semantics; huge `search` can spin; trailing junk silently ignored.
- **Why missed:** no elliptic-curve/diophantine area exists in `MASTER_FINDINGS.md`; `resource_limits` never reached `ec_cmd.c`.

### 5. Global single `jmp_buf fail_jmp` + `longjmp` on every error  [SRC] [NEW]
- **Idea:** one global jump target for all errors; ~20 files manually `memcpy` save/restore it, so any error raised in a nested call (callback, comparator, signal handler, compiler shim) can jump to a stale frame.
- **Inspired by:** `src/ucas.h:47`, `src/util.c:193`, `src/util.c:264-302`; manual save/restore in `src/parse.c:3365-3382`, `src/cf_bridge.c:331-360`, `src/cf_opt.c:618-639`, `src/sg.c:858-863`, `src/spirv.c:10927-10932`, etc.
- **Input shape:** a failing tool call inside a larger analysis: MCP JSONL with `tools/call gates` on an unsatisfiable function followed in the same session by `tools/call find`, plus a deliberately failing `c` compile between them; look for lost output / wrong `isError` / session corruption.
- **Bug class:** WRONG / CRASH / LIMIT — non-local exit bypasses cleanup, leaving partial output or a stale error handler.
- **Why missed:** `mcp_api_fuzz` checked envelope invariants on ordinary calls, not an error raised *during* a nested analysis; `nlp_session_state` covered value state, not the control-flow jump buffer.

### 6. `atoi` on SPIR-V operands used as bit widths and array indices  [SRC] [NEW]
- **Idea:** SPIR-V text operands are converted with bare `atoi` and used directly as `bits`, `nop` offsets and array indices with no range check.
- **Inspired by:** `src/spirv.c:902` (`atoi(I->opnd[i])`), `src/spirv.c:8276` (`bits = atoi(q+5)`), `src/spirv.c:8293` (`v = atoi(q)`), `src/spirv.c:8954` (`n = atoi(V.id[rt].name+7)`).
- **Input shape:** MCP `spirv` / `spirv_simplify` with a module containing `OpTypeInt 999999999999 1`, an image format `VK_FORMAT_R999999999_UNORM`, or a name `%999999999999`.
- **Bug class:** CRASH (OOB index) / WRONG (saturated bit width accepted as a valid format).
- **Why missed:** no SPIR-V shader area in `MASTER_FINDINGS.md`; `schema_conformance` only exercised SPIR-V envelope fields with valid modules.

### 7. `#line` directive parsing accepts negative/out-of-range line numbers  [SRC] [NEW]
- **Idea:** `atoi(m+6) > 0 && < 10000` — the lower bound is positive, but leading `+`, hex/octal (`010`), and whitespace forms are accepted and can disagree with the actual line count.
- **Inspired by:** `src/spirv.c:6644-6646` and the duplicate in `src/glslfn.c:6495-6497`.
- **Input shape:** glslc source `#line 0005`, `#line +7`, `#line 0x10`; check emitted debug line numbers.
- **Bug class:** WRONG — wrong diagnostic line numbers mislead users (error-message side channel).
- **Why missed:** `cfront_fuzz` covered C front-end `#line` indirectly but not GLSL/SPIR-V `#line` with odd numeric forms.

### 8. `strcat` into a fixed-size engine-name buffer  [SRC] [NEW]
- **Idea:** model/engine names are concatenated with `strcat` into a fixed `char engine[...]`; many fused engines can overflow.
- **Inspired by:** `src/cf_opt.c:1867-1868` `strcat(w->engine, "+"); strcat(w->engine, s[k].engine);`.
- **Input shape:** a `cost` / `c optimize` request whose model chains dozens of named optimisation passes (via MCP `models`/`use` and `cost`), then `c optimize`.
- **Bug class:** CRASH (stack/heap overflow) / WRONG (truncated engine string).
- **Why missed:** `c_vectorize_loops` and `cfront_fuzz` used ordinary single-pass models; no area built a long engine chain.

### 9. `clock()` deadlines make `find`/`stoke` results machine-speed dependent  [SRC] [NEW]
- **Idea:** search stops when `clock() > F.deadline`, so the number of results and their order depend on CPU speed and load.
- **Inspired by:** `src/find.c:632`, `src/find.c:3534`, `src/find.c:3814`; `src/stoch.c:3066`.
- **Input shape:** `find 50 stoke`, `find 10 snippets`, `stoke f steps 100000` run twice back-to-back and under load; diff the outputs.
- **Bug class:** DETERMINISM — golden tests with these flags would be flaky.
- **Why missed:** `grammar_fuzz_reduce` tested `find` but with default (deterministic) search; `cfront_fuzz` saw clock-based `bench` noise, not `find`.

### 10. Fixed-size `part[256]`, `rows[64]`, `cells[64]` in abstract-algebra NLP  [SRC] [NEW]
- **Idea:** comma-separated lists split into fixed arrays with no `n < cap` check before writing.
- **Inspired by:** `src/absalg_cmd.c:2024` `char *part[256]`, `:2263` `char *rows[64]`, `:2280` `char *cells[64]`, `:1112`/`:1767` `part[64]`.
- **Input shape:** MCP `english` / CLI sentence `is [64+ comma-separated cyclic groups] isomorphic to Z2`; an abelian group with >64 invariant factors; a matrix printed with >64 rows.
- **Bug class:** CRASH (stack OOB write) / LIMIT.
- **Why missed:** no abstract-algebra area in `MASTER_FINDINGS.md`; `nlp_robustness`/`nlp_ambiguity` never generated >64 comma-separated operands.

### 11. `tok_text` truncation into `char w[64]` in hypercomplex dispatch  [SRC] [NEW]
- **Idea:** identifiers longer than 63 chars are silently truncated before `func_find`, so a long user name can alias a builtin.
- **Inspired by:** `src/hyper.c:2093` `char w[64]` + `tok_text(t,a,w,sizeof w)` at `:2100`.
- **Input shape:** define a 70-char function name whose first 60 chars match a builtin, then use it in a hypercomplex expression; check which definition wins.
- **Bug class:** WRONG / NLP — silent alias to another symbol (name-shadowing variant already seen in `state_long_session` but here caused by truncation, not by dispatch).
- **Why missed:** `state_long_session` tested short builtin-shadowing names; no one tested >63-char names.

### 12. Recursion cap mismatch: `emit_constant` capped at 32, `fx_build` uncapped  [SRC] [NEW]
- **Idea:** one SPIR-V/GLSL path caps recursion at depth 32 while the type-building path recurses without a visible cap.
- **Inspired by:** `src/snxglslc/emit.c:820-831` `if (depth > 32) return 0;` vs `src/spirv.c:8776` `fx_build(g, idx(...), atoi(...), depth+1)`.
- **Input shape:** MCP `spirv_simplify` with 2000 nested `OpTypePointer`/`OpTypeArray` types; MCP `glslc` with 2000 nested `struct { struct {...} }`.
- **Bug class:** CRASH (stack overflow) — distinct from `resource_limits`' expression nesting crash because it is in the shader compiler, not the expression parser.
- **Why missed:** `resource_limits` covered `show`/`parse` nesting; no shader-compiler depth area exists.

### 13. `memcpy` of SPIR-V source slices into fixed buffers  [SRC] [NEW]
- **Idea:** token slices are copied into fixed `char[]` buffers using `tok - st` lengths without an explicit bound.
- **Inspired by:** `src/spirv.c:291` (`memcpy(src_text, q+1, z>q?z-q-1:0)`), `:309`, `:382`, `:10103`, `:14070`, `:14216`.
- **Input shape:** `spirv` source with a single 100 KB identifier / 100 KB literal in an operand, opcode line, or `#line` comment.
- **Bug class:** CRASH (OOB write) / WRONG (silent truncation).
- **Why missed:** `parser_json_fuzz` covered a 100 k identifier through the *expression* lexer; the SPIR-V lexer is a separate code path.

### 14. `strtoll(..., NULL, 0)` base-0 parsing of `assume` bounds  [SRC] [PARTIAL]
- **Idea:** `assume x lo hi` accepts `0x…`, octal `010`, and signs, silently changing the declared range.
- **Inspired by:** `src/cf_cmd.c:553-554` `strtoll(a, NULL, 0)` / `strtoll(b, NULL, 0)`.
- **Input shape:** `assume n 0x0 0xff`, then `range`/`equiv` on `n`; or `assume n 010 020` (octal).
- **Bug class:** WRONG — the C frontend's range assumptions disagree with the declared numeric type.
- **Why missed:** `c_vectorize_loops` tested `assume n 0 10` (decimal only); `cfront_fuzz` never varied the radix.

### 15. `strtoll(s, &end, 10)` with unchecked end pointer in hom-algebra  [SRC] [NEW]
- **Idea:** integer arguments accept trailing junk and out-of-range values.
- **Inspired by:** `src/homalg_cmd.c:91`.
- **Input shape:** `bigint 12abc`, `abgroup Z/12junk`, `snf [[1,2junk],[3,4]]`.
- **Bug class:** WRONG / LIMIT — malformed arguments accepted with a plausible answer.
- **Why missed:** no homological-algebra area; `parser_json_fuzz` tested malformed JSON but not malformed *numeric arguments* to algebra commands.

### 16. `atoi(q+4)` on the `samples=` option of `tcdot`  [SRC] [NEW]
- **Idea:** sample count parsed with `atoi` and used as a loop bound/allocation size.
- **Inspired by:** `src/tcdot.c:413` `k = atoi(q + 4)`.
- **Input shape:** MCP `tcdot` with `samples=-1`, `samples=999999999`, `samples=12junk`.
- **Bug class:** HANG / CRASH (negative→huge size_t) / WRONG.
- **Why missed:** `tex_domain_modules` tested `samples=100000` (valid positive) and timing, not malformed values.

### 17. `memcpy(name, sent+(q+4-buf), k)` with unchecked derived length  [SRC] [NEW]
- **Idea:** source span computed from an NLP phrase offset is copied into a fixed buffer; a long name can overflow.
- **Inspired by:** `src/winograd.c:270`.
- **Input shape:** MCP `english` sentence naming a 500-character variable in a Winograd-style question.
- **Bug class:** CRASH (OOB write) / WRONG (truncation).
- **Why missed:** `nlp_robustness` tested long *sentences* but not long *identifiers in this specific NLP hook*.

### 18. `atoi(d)` on the "N bits" phrase of `dword cases` NLP  [SRC] [NEW]
- **Idea:** bit count taken from a sentence with `atoi`, no bound; negative and huge values flow into case analysis.
- **Inspired by:** `src/dword.c:3054-3058` `snprintf(out, sizeof out, "dword cases %d", atoi(d))`.
- **Input shape:** MCP `english` with text `"case analysis of double-word arithmetic at -24 bits"`, and `"… at 999999999999 bits"`.
- **Bug class:** WRONG / HANG — negative bit counts in an algorithm that assumes positive widths.
- **Why missed:** `nlp_arith`/`nlp_numbers` never targeted the double-word NLP hook.

### 19. Lexer special-cases the word `file` and swallows the rest of the line  [SRC] [NEW]
- **Idea:** `input 1 file a/b.png` causes the lexer to consume everything up to whitespace/`;` as a path, with no validation — including `../`, NUL-adjacent, and `/dev/*` paths.
- **Inspired by:** `src/lex.c:113-120`.
- **Input shape:** `input 1 file /proc/self/environ`, `input 1 file ../../etc/passwd`, `input 2 file /dev/zero`.
- **Bug class:** WRONG / path traversal / HANG (blocking reads).
- **Why missed:** `cli_args_fuzz` tested a *directory argument* silently accepted as empty input, not this file-path lexer mode.

### 20. Real literals use `strtod` without `ERANGE` checking  [SRC] [PARTIAL]
- **Idea:** unlike integer literals (which check `errno == ERANGE`), real literals accept overflow to `inf`/underflow to `0` silently.
- **Inspired by:** `src/parse.c:280-300` — `errno = 0;` is set but only checked at line 298, *after* the real branch `return`s at 292-294.
- **Input shape:** `show 1e400`, `show -1e400`, `show 1e-400`, `show f32(1e400)`, `show 1e400 == 1e400`.
- **Bug class:** WRONG / LIMIT — `inf`/`0` produced without a diagnostic; `equiv` on such literals may be unsound.
- **Why missed:** `fp_edge` tested f32/f64 special values via casts and functions, not literal-overflow parsing; `nlp_numbers` tested spelled numbers.

### 21. `fx_build` / `emit_constant` use `atoi` operands as object indices  [SRC] [NEW]
- **Idea:** the shader compiler treats textual numeric operands as SPIR-V ids and indexes into arrays with them.
- **Inspired by:** `src/spirv.c:902`, `:1188`, `:1237`, `:2919`, `:6626`, `:10984`.
- **Input shape:** `spirv_simplify` on a module where `OpAccessChain` has an index operand of `999999999` or `-1`.
- **Bug class:** CRASH (OOB) / WRONG (index clamped silently).
- **Why missed:** no shader area covered operand-index validation.

### 22. `char *part[64]` / `by = find_word(...)` parser of abstract-algebra commands  [SRC] [NEW]
- **Idea:** split-on-keyword logic writes into fixed arrays based on the number of keywords found in a user sentence.
- **Inspired by:** `src/absalg_cmd.c:600`, `:776`, `:931`, `:969`, `:1081`, `:1112`, `:1767`.
- **Input shape:** a sentence with 70 occurrences of `by`, `to`, `->`, or `,` fed to `english`.
- **Bug class:** CRASH (stack OOB write).
- **Why missed:** `nlp_robustness` used at most a few dozen words; no stress on repeated *keyword* density.

### 23. Chained `(int)strtol(sp, &sp, 10)` in EC-field command parsing  [SRC] [NEW]
- **Idea:** multiple integers parsed from one string with the end pointer advanced but never checked for failure.
- **Inspired by:** `src/ecff_cmd.c:205-207`.
- **Input shape:** `gf 2^999999999999`, `ecff` curve parameters with truncated/overflowing exponents.
- **Bug class:** WRONG / CRASH (negative or saturated field degree).
- **Why missed:** `sat_crypto_circuits` used valid GF(2^8)/GF(2^16) parameters only.

### 24. `sprintf` into an 8-slot rotating `pbuf` for big-integer printing  [SRC] [PARTIAL]
- **Idea:** `nn_str`/`nn_hex` return pointers into `pbuf[pslot++ & 7]`; more than 8 live results in one expression alias each other.
- **Inspired by:** `src/ecmp.c:1117-1161` (`static char pbuf[8][400]; static int pslot;`).
- **Input shape:** `show` / `bigint` of an expression that formats 9+ big integers in one call (e.g. a large `snf` diagonal matrix printed inline).
- **Bug class:** WRONG — two printed values become identical because the buffer slot wrapped.
- **Why missed:** `nlp_numbers` tested big literals but never >8 simultaneous formatted big integers.

### 25. `fgets(reply, 512, stdin)` plus unbounded `cur` growth in prompt loop  [SRC] [PARTIAL]
- **Idea:** answers are truncated to 511 bytes and appended to `cur` on every retry, so a long answer or many retries changes the sentence being parsed.
- **Inspired by:** `src/nlp.c:8014`, `:8062-8077` (`reply[512]`, `p = xmalloc(strlen(cur)+strlen(reply)+4); sprintf(p, "%s , %s", cur, reply);`).
- **Input shape:** an English question that asks a follow-up, answered with a 600-character line; or 20 successive short answers.
- **Bug class:** WRONG / NLP — silently truncated answer changes the math.
- **Why missed:** `nlp_robustness` tested long input *sentences*, not long *answers to interactive prompts*.

### 26. In-process signal handlers in the C checker  [SRC] [PARTIAL]
- **Idea:** `cf_check.c` installs `SIGFPE`/`SIGSEGV`/`SIGBUS` handlers in the ucas process before running generated C; a crash in the shim may jump or corrupt shared state rather than being contained.
- **Inspired by:** `src/cf_check.c:336-337`.
- **Input shape:** `c optimize nofile` on a snippet that divides by zero, then issue another tool call in the same MCP session; check whether the session survives.
- **Bug class:** CRASH / WRONG (state corruption after a caught signal).
- **Why missed:** `c_vectorize_loops` found a SIGFPE but only recorded the crash, not the post-signal session state.

### 27. `memcpy(g->prev, pix, g->w * g->h)` trusts dimensions from decoded data  [SRC] [NEW]
- **Idea:** GIF frame dimensions are used directly for a buffer copy; a mismatched frame size yields OOB.
- **Inspired by:** `src/gif.c:219` and the bundled `src/third_party/stb_image.h` image decoder.
- **Input shape:** MCP `input 1 file <crafted truncated/oversized GIF>`; `animate` producing a GIF whose frame header disagrees with the canvas.
- **Bug class:** CRASH / OOB read+write — classic image-parser fuzz target.
- **Why missed:** no image-file area; `tex_domain_modules` tested texture *encoding* arguments, not decoding arbitrary files.

### 28. `slurp()` file buffer doubling without overflow check  [SRC] [PARTIAL]
- **Idea:** `cap *= 2` with no `SIZE_MAX/2` guard; a file near the limit wraps and under-allocates.
- **Inspired by:** `src/main.c:19-34`.
- **Input shape:** sparse file / `/proc` pseudo-file that reports huge size; not directly reachable without a >1 GB file, so low priority.
- **Bug class:** CRASH / OOM.
- **Why missed:** `resource_limits` tested up to 100 MB text and got a clean OOM message at a different allocation site.

### 29. `strtoull` on `UCAS_SEED` accepts whitespace and a leading `+`  [SRC] [NEW]
- **Idea:** variant of #2 targeting lexical acceptance: `" 5x"`, `"+7abc"` all parse as valid seeds.
- **Inspired by:** `src/stoch.c:120-123`.
- **Input shape:** `UCAS_SEED=' 5x'`, `UCAS_SEED='+7abc'`, `UCAS_SEED='0x10'` (base 10 → 0).
- **Bug class:** WRONG / DETERMINISM.
- **Why missed:** same as #2.

---

## B. Ideas inspired by external testing tricks (CWE / OWASP / CTF-style)

External pages fetched and used:
- <https://cwe.mitre.org/data/definitions/674.html> — CWE-674 Uncontrolled Recursion
- <https://cwe.mitre.org/data/definitions/367.html> — CWE-367 TOCTOU Race Condition
- <https://owasp.org/www-community/attacks/Unicode_Encoding> — Unicode encoding / bypass
Additional CWE IDs cited by their canonical URLs (`https://cwe.mitre.org/data/definitions/<id>.html`).

### 30. Recursion bomb in a *non-expression* parser  [EXT CWE-674] [PARTIAL]
- **Idea:** CWE-674 stack exhaustion, but target the GLSL/SPIR-V and abstract-algebra parsers instead of `parse.c`.
- **Source:** CWE-674; `src/snxglslc/parser.c`, `src/hyper.c:1933`.
- **Input shape:** `glslc` with 2000 nested parentheses; `english` with 2000 nested `sin(sin(...))` in a hypercomplex question.
- **Bug class:** CRASH.
- **Why missed:** `resource_limits` tested expression nesting only (`show`, `abs`, `u8`, `[[…]]`, `|…|`).

### 31. TOCTOU on an output file path  [EXT CWE-367] [NEW]
- **Idea:** `c optimize <file>` / `plot` write to a path; race the path between validation and write with a symlink.
- **Source:** CWE-367; `src/cf_emit.c`, `src/plot.c`, `src/viz.c`.
- **Input shape:** start `c optimize /tmp/opencode/race.c`, then swap `race.c`→symlink to a sentinel file during the compile.
- **Bug class:** WRONG / file corruption.
- **Why missed:** no file-system race area; `cli_args_fuzz` tested argument parsing, not races.

### 32. TOCTOU on an input file path (`input N file …`)  [EXT CWE-367] [NEW]
- **Idea:** swap the input file between the lexer's size check and the read.
- **Source:** CWE-367; `src/lex.c:113-120`, `src/img.c`.
- **Input shape:** as in #19 but with a fast loop replacing the file between two calls.
- **Bug class:** WRONG / crash if the replacement is a directory or FIFO.
- **Why missed:** same as #19.

### 33. Hash-collision DoS in the shader type/constant hash table  [EXT CWE-400] [NEW]
- **Idea:** `GLSLC_HASH_SIZE` buckets with a fixed number of entries; craft many distinct names that collide in the hash to force linear probing or a clean error.
- **Source:** CWE-400 (Uncontrolled Resource Consumption); `src/snxglslc/emit.c:284-292`.
- **Input shape:** `glslc` source declaring thousands of types/constants; observe "the shader needs more than the %u types…" vs quadratic slowdown.
- **Bug class:** HANG / LIMIT.
- **Why missed:** no shader area; `resource_limits` tested tables in the *expression* engine (cap 1024), not the GLSL hash table.

### 34. ReDoS-style backtracking in the hypercomplex grammar scanner  [EXT CWE-1333/CWE-674] [NEW]
- **Idea:** ambiguous `hy_scan`/`hy_decide` explores token assignments; a long ambiguous token sequence can backtrack exponentially.
- **Source:** CWE-674 / CWE-407; `src/hyper.c:2104-2132`.
- **Input shape:** `english` with 40 ambiguous `i j k` products, or `show` of a 40-term hypercomplex expression with mixed `*` and implicit multiplication.
- **Bug class:** HANG.
- **Why missed:** `nlp_ambiguity` tested short ambiguous phrases (2–4 words), not exponentially many ambiguities.

### 35. Concurrent MCP requests against shared global state  [EXT CWE-362] [NEW]
- **Idea:** all state (`N`, `funcs`, `notes`, `fail_jmp`, `range_nocrit`, cost model) is process-global with no locking; two clients on one `--mcp` process can interleave definitions.
- **Source:** CWE-362 (Concurrent Execution using Shared Resource); `src/ucas.h` globals.
- **Input shape:** feed two JSONL streams into one `ucas --mcp` process concurrently (interleave lines), with `session assume` / `use` / `english` in one and `range` in the other.
- **Bug class:** WRONG / DETERMINISM / CRASH.
- **Why missed:** every MCP area used a single sequential stream; `nlp_session_state` tested sequential leakage only.

### 36. Error-message side channel via `funcs`/`session state`/diagnostics  [EXT CWE-209] [PARTIAL]
- **Idea:** error text and `funcs` reveal internal symbol names and assumptions that the successful result does not; use it to distinguish hidden states.
- **Source:** CWE-209 (Generation of Error Message Containing Sensitive Information); `src/util.c:267-292`, `src/jsonmode.c` `funcs`/`session state`.
- **Input shape:** define a function, fail a `range` call, then compare `funcs` and the error caret text; try the same over MCP where notes differ.
- **Bug class:** WRONG / NLP (inconsistent disclosure).
- **Why missed:** `state_long_session` found state omissions but did not treat diagnostics as an oracle for hidden state.

### 37. Unicode normalization / homoglyph alias  [EXT OWASP Unicode Encoding] [COVERED]
- **Idea:** visually identical identifiers from different Unicode code points resolve to different symbols.
- **Input shape:** `show 𝑥` (mathematical italic e) vs `show e`; zero-width joiner in a name.
- **Bug class:** NLP/WRONG.
- **Why missed:** **already covered** — `nlp_multilingual`, `thesis_nlp_noise_bias` (Cyrillic/Greek homoglyphs, zero-width chars). Do not redo.

### 38. Null-byte / control-character injection into tool arguments  [EXT CWE-20] [COVERED]
- **Input shape:** `tools/call name="ana\u0000lyze"`.
- **Bug class:** WRONG (`id` dropped to null).
- **Why missed:** **already covered** — `mcp_api_fuzz`.

### 39. Deeply nested JSON recursion bomb  [EXT CWE-674] [COVERED]
- **Input shape:** 1000 nested `[` in a JSON argument.
- **Bug class:** CRASH.
- **Why missed:** **already covered** — `parser_json_fuzz`, `resource_limits`.

### 40. Path traversal in output file arguments  [EXT CWE-22] [NEW]
- **Idea:** `plot`, `plot3d`, `animate`, `c optimize`, and `report` take paths; no normalisation before writing.
- **Source:** CWE-22; `src/plot.c`, `src/viz.c`, `src/gif.c`, `src/cf_emit.c`, `src/report.c`.
- **Input shape:** MCP `plot fs="../../tmp/opencode/pwn.gif"`, `c optimize file="../../tmp/opencode/pwn.c"`.
- **Bug class:** WRONG / file overwrite outside the working directory.
- **Why missed:** no file-output area; `cli_args_fuzz` only checked that a *directory argument* was accepted as empty input.

### 41. Symlink following on those output paths  [EXT CWE-59] [NEW]
- **Input shape:** pre-create `pwn.gif` as a symlink to a sentinel, then `plot fs="pwn.gif"`.
- **Bug class:** WRONG / unintended overwrite.
- **Why missed:** as #40.

### 42. OS command injection / untrusted compiler via `UCAS_CC`  [EXT CWE-78] [PARTIAL]
- **Idea:** the C checker invokes a compiler; `UCAS_CC` is honoured. A value with spaces/shell metacharacters may be executed.
- **Source:** CWE-78; `src/cf_check.c` (`-fsanitize-minimal-runtime` hard-coded, `UCAS_CC` mentioned in `cfront_fuzz` findings).
- **Input shape:** `UCAS_CC='/bin/sh -c "touch /tmp/opencode/pwn"'` with a `check` request; use `strace`/sentinel to observe exec.
- **Bug class:** CRASH / command execution.
- **Why missed:** `cfront_fuzz` only noted that `check` ignores `UCAS_CC` on host GCC; no one tried a metacharacter-laden value.

### 43. Untrusted search path (`PATH`) for the compiler helper  [EXT CWE-426] [NEW]
- **Input shape:** put a fake `cc` earlier in `PATH` that logs its arguments; run `c check`.
- **Bug class:** WRONG / hijacked execution.
- **Why missed:** same as #42.

### 44. Negative / huge numeric options (`table max`, `find N`, `taylor N`)  [EXT CWE-1284] [PARTIAL]
- **Idea:** "improper validation of specified quantity in input" — signed integers feeding loop bounds and allocations.
- **Source:** CWE-1284; `src/parse.c:3873` (`opt_int(p,"max",64)`), `:3976` (`want = (int)N.ki[...]`), `src/calc2.c` taylor order.
- **Input shape:** `table f max -1`, `find -5`, `find 2147483647`, `taylor exp(x) x -1`.
- **Bug class:** HANG / CRASH (negative→huge `size_t`) / WRONG.
- **Why missed:** `resource_limits` tested large *positive* caps; `grammar_fuzz_reduce` tested `find 0` (silent default 10) but not negatives.

### 45. `xmalloc(n * sizeof …)` with attacker-controlled signed `n`  [EXT CWE-190/CWE-681] [NEW]
- **Idea:** signed count from `atoi`/`strtol` multiplied by `sizeof` wraps to a small allocation, then the loop writes `n` elements → heap overflow.
- **Source:** CWE-190/CWE-681; `src/absalg_cmd.c:1563,1571,1614,1655,1783`, `src/parse.c:399`.
- **Input shape:** `abgroup` with a declared order of `-1` / `2147483647`; `diophantine ... count 2147483647`.
- **Bug class:** CRASH (heap overflow).
- **Why missed:** `resource_limits` tested positive large counts and saw clean OOM, which would mask wrap cases.

### 46. Malformed image decode through `stb_image.h`  [EXT CWE-125/CWE-787] [NEW]
- **Idea:** classic OOB read/write fuzz target — truncated PNG/GIF headers, huge dimensions in the header.
- **Source:** CWE-125/CWE-787; `src/third_party/stb_image.h`, `src/img.c`, `src/gif.c`.
- **Input shape:** MCP `input 1 file /tmp/opencode/truncated.png`; point at the file after writing 30 random bytes.
- **Bug class:** CRASH.
- **Why missed:** no image-decoding area exists.

### 47. Empty-domain / vacuous-proof family extended to NFT-style commands  [EXT CWE-670] [PARTIAL]
- **Idea:** "proof" commands on a function undefined everywhere return `equal:true`; try the same on `pit`, `identify`, `monotonic`, `injective` with a partial `where` clause.
- **Source:** CWE-670 (Always-Incorrect Control Flow Implementation); `src/prove_cmd.c`, `src/stoch.c:729`.
- **Input shape:** `f(x:u8)=x where x>255`, then `pit f f trials 8`, `injective f`, `monotonic f`.
- **Bug class:** WRONG (vacuous verdict).
- **Why missed:** `type_mutation_diff`/`sat_crypto_circuits` found vacuous `equiv` only; other proof commands were not swept.

### 48. Repeated failed tool calls leak memory until OOM  [EXT CWE-401] [PARTIAL]
- **Idea:** error paths `longjmp` out of allocation-heavy code without freeing; thousands of failing calls in one MCP session exhaust memory.
- **Source:** CWE-401 (Missing Release of Memory); `src/util.c:267-292` `fail()` → `longjmp`.
- **Input shape:** a `.jsonl` with 5000 `tools/call` requests that each fail halfway (e.g. `gates` with an unsatisfiable budget), watch RSS / eventual `out of memory`.
- **Bug class:** CRASH / resource leak.
- **Why missed:** `resource_limits` tested large single requests, not many failing requests in one long-lived process.

### 49. Integer literal boundary `2^63-8 … 2^63` across frontends  [EXT CWE-681] [COVERED]
- **Input shape:** `show 9223372036854775800`, `--mcp` `parse` with the same literal.
- **Bug class:** WRONG / LIMIT.
- **Why missed:** **already covered** — `prove_symbolic` found bare `error:` for literals ≥ 2^63−8.

### 50. Locale invariance of numeric formatting  [EXT OWASP / locale] [COVERED]
- **Bug class:** none (clean).
- **Why missed:** **already covered** — `env_locale_tty` verified 28 env configs byte-identical.

---

## Quick probes actually run (all bounded with `timeout 10`)

```
$ ./ucas -e 'abselftest -5'                 -> 100 random pairs, rc 0 (atoi<=0 -> default 100)
$ ./ucas -e 'abselftest 200'                -> 200 random pairs, rc 0 (atoi scales as expected)
$ ./ucas -e 'abselftest 99999999999999999999999' -> default 100, rc 0 (atoi overflow silently ignored)
$ timeout 10 ./ucas -e 'abselftest 2147483647'   -> NO OUTPUT, rc 124  [idea #3]
$ ./ucas -e 'diophantine x^2 + 2*y^2 = 3 count -1'   -> normal "genus 0" output, rc 0 (option accepted, no effect on this curve) [idea #4]
$ printf '{"jsonrpc":"2.0","id":1e400,"method":"initialize",...}' | ./ucas --mcp
      -> {"jsonrpc": "2.0", "id": 1e400, "result": {...}}   [idea #1 CONFIRMED]
$ printf '{"jsonrpc":"2.0","id":1e400,...} | ./ucas --json
      -> {"id": 1e400, "ok": false, ...}                    [idea #1 CONFIRMED both frontends]
$ UCAS_SEED=abc  ./ucas -e $'f(x)=x+1\ng(x)=1+x\npit f g trials 8' -> "seed 0"   [idea #2]
$ UCAS_SEED=-1   ... -> "seed 18446744073709551615"                              [idea #2]
$ UCAS_SEED=18446744073709551616 ... -> "seed 18446744073709551615" (saturates) [idea #2 / #29]
```

Notes for the implementer: `pit` CLI syntax is `pit F G [trials N] [seed K]` (keywords required).
`abselftest 2147483647` is a *deliberate* long self-test; treat it as a HANG/LIMIT reproducer,
not a golden `.out`. The `1e400` id is emitted by both `--mcp` and `--json` and is deterministic,
so it can become a golden MCP test **only if** the orchestrator decides invalid-JSON output is
acceptable to pin; otherwise file it in `FINDINGS.md` as a protocol WRONG.

Total ideas: 50 (29 source-pattern-derived, 21 external-trick-derived).
Marked covered: 6 (#37, #38, #39, #49, #50, and the recursion-bomb overlap in #30).
