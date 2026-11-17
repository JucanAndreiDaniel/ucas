# Master findings

This file lists the main bugs. Each area has full reproducers in `areas/<domain>/<area>/FINDINGS.md`.
The area index is in `AREAS.md`.

Severity names:

- `CRASH` — the process exits with a signal.
- `HANG` — the process gives no answer before the timeout.
- `WRONG` — the answer is wrong or unsound.
- `NLP` — the English frontend parses the input wrong.
- `LIMIT` — the tool stops but reports the limit.
- `DETERMINISM` — the output changes between runs.

## Top priorities

1. `equiv` gives wrong verdicts. `real` `equiv` rejects 101 of 101 true identities with witnesses whose values
   print the same. All four frontends drop `where`, range and set restrictions on the second function.
   Other paths: signed reinterpretation, cast coercion, bigint results at 2^63, and stale auto-names across
   requests. See `sat/symbolic_diff_exact`, `sat/equiv_domain_systematic`, `math/type_coercion`.

2. A timeout child can desynchronise the reply stream. Its late output gives one request two replies and gives
   the next request the wrong `id`. This affects `--json` and `--mcp`. See
   `systems/soak_nondeterminism/repro_timeout_desync.py`.

3. One deep expression can kill the whole `--json` or `--mcp` server. The server loses queued requests.
   See `frontend/parser_json_fuzz`.

4. `range` and `domain` give wrong bounds. Some miss reachable spikes. Some call a function total even when
   no point works. Some prove a bound that the values contradict. See `sat/range_sampled_soundness`,
   `sat/sat_wrap_domain`.

5. The session cannot be reset in full. English and JSON stores stay separate. `forget` and a second
   `initialize` leave old definitions. See `frontend/session_reset_systematic`, `nlp/nlp_session_state`.

6. Float functions are one ulp off in many cases. f64 calls host `libm`. f32 and f16 round again. `equiv` can
   claim two functions equal while a witness in the same session differs. See `float/worst_case_rounding`.

7. The English parser hangs on nested phrases. A 61-word input expands to about 2^n parses.
   See `nlp/english_redos`.

8. Many inputs crash the CLI. Deep parentheses, INT64_MIN / -1, large products and long long loops cause signals.
   ASan also found two out-of-bounds reads. See `systems/sanitizer_builds`.

## Clean cores

Independent oracles found no fault in these areas:

- SAT proofs on machine types, multipliers and witnesses
- Rewriter output: 301 emitted forms checked with six methods
- Determinant algebra, rings arithmetic and integer division
- Table lookups and BC4 decodes
- Protocol envelope, advertised MCP capabilities and non-fast-math builds

## Coverage

A clang coverage build ran 5,281 corpus invocations. The suite reaches 67% of lines, 81% of functions and 56%
of branches. The suite reaches all 27 MCP tools. The gaps are slow paths, rare GPU and algebra operations, and
dead code. See `systems/coverage_gap_analysis/FINDINGS.md`.
