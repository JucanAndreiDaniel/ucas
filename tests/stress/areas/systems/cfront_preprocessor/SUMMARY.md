# SUMMARY — `cfront_preprocessor`

## Counts
- Distinct expressions/queries tried: not recorded
- Goldens written: 23
- Files created: 23

### Original preamble

**Area:** the C frontend's preprocessor (`#define`/macros, `#if` family,
`#include`, `#pragma`, `#line`, `#`/`##`, recursion, comments, line
continuations) as exercised through `c lower`, `c optimize` and MCP tool `c`.

### Counts

- Distinct C snippets (functions + macro definitions) tried: **268**
  - 154 embedded in the kept golden files (99 functions, 55 macros)
  - ~114 additional exploratory cases used to locate the issues
- Golden files written: **23**
  - 22 CLI goldens: `01_object_macros` … `22_extra_macros` (`.ucas` + `.out`)
  - 1 MCP golden: `mcp_c_preproc.jsonl` + `mcp_c_preproc.out` (3 `c` calls:
    two `c_lower`, one `c_optimize`)
  - Supporting file: `local.h` (real local `#include` test)
- Bug reproducers (`.ucas`, deliberately **no** `.out`): **5**
  - `bug_if_signed_unsigned`, `bug_comment_splice`, `bug_if_shortcircuit`,
    `bug_line_file_missing`, `bug_line_ignored`
- Issues by severity:
  - `CRASH`: 0
  - `HANG`: 0
  - `WRONG`: 2 (silent wrong branch in `#if` signed/unsigned evaluation;
    `//` comment ignoring backslash-newline splicing)
  - `NLP`: 0
  - `LIMIT`: 3 (no `&&`/`||` short-circuit in `#if`; `__LINE__`/`__FILE__`
    missing; `#line` ignored in diagnostics)
  - `DETERMINISM`: 0 (every golden run twice and `diff`ed identically; all
    exits 0 under `timeout 30`)


## Issues by severity
| Severity | Count | Headline |
|----------|-------|----------|
| WRONG | 2 | — |
| LIMIT | 3 | — |

## Takeaway
the preprocessor's object/function macros, includes, conditionals and stringification are handled cleanly, but `#if` is evaluated with plain signed 64-bit arithmetic and `//` comments are stripped before backslash-newline splicing, so several common C idioms silently compile the wrong branch; it also lacks short-circuiting, `__LINE__`/`__FILE__` and `#line` diagnostic remapping.

### Original takeaway (verbatim)
the preprocessor's object/function macros, includes,
conditionals and stringification are handled cleanly, but `#if` is evaluated
with plain signed 64-bit arithmetic and `//` comments are stripped before
backslash-newline splicing, so several common C idioms silently compile the
wrong branch; it also lacks short-circuiting, `__LINE__`/`__FILE__` and `#line`
diagnostic remapping.

All work stayed inside `tests/stress/areas/systems/cfront_preprocessor/`: no source, Makefile,
test, `opencode.json` or git state was touched, and no other subagent's folder
was modified.
