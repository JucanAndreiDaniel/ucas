> **Portability:** set `ROOT=/path/to/ucas` (the repo root) before copy-pasting reproducers below, or `cd` to the repo root and use `ROOT=$PWD`; `$ROOT/ucas` is the built binary.

# IDEAS_MONKEY.md — the newborn-monkey / malicious-user chaos catalog

Role: idea researcher channeling (a) a newborn monkey hammering every key and (b) a malicious user who
has read the docs and is looking for the gap between "what ucas promises" and "what it actually does".
This is a **catalog of ideas**, not a passing test suite. Nothing here was added as a golden `.out`.
Ideas are ranked by a mix of novelty, likelihood of a real bug, and how cheaply they can be probed.

"Already covered" markers refer to *ideas*, not exact inputs — the same surface is often reachable from
a different angle. `[COVERED: area]` means `tests/stress/<area>/` already exercises roughly this shape;
`[PARTIAL: area]` means adjacent coverage exists but the specific vector below is new.

Binary is always `$ROOT/ucas` (abbreviated `ucas` below). Bound every probe with
`timeout 10`. All writes stay inside `tests/stress/`.

## Sources that fed this list

- Adversarial/chaos testing: Netflix Chaos Monkey, Trussed "AI agent chaos engineering", `agent-chaos`
  (LLM/tool/user-input chaos), Shopify "Cyber Chaos Monkey" (offensive agent + judge agent), Khaos SDK
  (tool-call misuse, permission escalation, multi-agent failure propagation). Key lesson: **attack the
  tool-call layer, not just the prompt; malformed tool RESULTS are the vector.**
- Prompt-injection / MCP literature: "MCP Deep Dive Part 8 — When a Tool Result Is the Attack", OWASP
  LLM01 tool-output poisoning, Promptfoo MCP tool-metadata injection DB, MDPI 2026 survey (Unicode Tags
  invisible instructions, ANSI escape codes in tool descriptions, tool shadowing / namespace collisions,
  cross-tool contamination, "rug pull" tools). Key lesson: **treat every tool output as hostile input to
  the next tool call; look for hidden characters and cross-tool exfiltration.**
- Compiler/CAS fuzzing: coverage-guided grammar fuzzing, metamorphic identities, ddmin, cross-library
  differential (RESEARCH.md / FOCUSED_IDEAS.md already distilled these; this catalog adds the *user-
  interaction* layer those docs omit).

## Quick probe results (already run, `timeout 10`)

| Probe | Observed | Consequence |
|---|---|---|
| `printf '\033[31mwhat is 2+2?\033[0m' \| ucas` | `sorry: I can't read the character` twice, rc 0 | ANSI/control bytes in English are rejected, but *silently* (no `understood:false` envelope) |
| MCP `tools/call name:"english"` with a second `initialize` inserted mid-stream | second initialize answered, state NOT reset (already known); `tools/call name:"tools/list"` → `-32602 unknown tool "tools/list"` | tool-discovery-as-tool is a fresh surface |
| CLI `loop(x: u8) = loop(x)` then `show loop(3)` | error `'loop' is not defined` **but** a stray `_(loop: real) = 3loop` definition is left behind | failed self-referential define leaves garbage state |
| MCP `animate` with `args.inputs=[{"file":"/etc/hostname"}]` (via `plot op:"animate"`) | path echoed in error `animate exec input 1 file /etc/hostname nofile` | arbitrary `file` paths are accepted and tokenized — file-read idea is actionable |
| MCP `ucas source:"show sin(1)"` | output `_() = 0.8414709848` — anonymous `_` definition created | confirms `_` clobber from a different vector |

---

# Tier 1 — top 10 most promising chaos ideas

### 1. Recursive self-fuzzing: feed a tool's own output back as the next tool's input
- **Description:** A tool's `text`/`result` field is itself valid-ish ucas syntax (`_() = …`, `  ucas: …`,
  notes with `-> real`). Feed it straight back into the `ucas` tool's `source`, and repeat 5–10 times.
  The monkey does not read the output — it just pastes it back.
- **Command (MCP JSONL, ids unique):**
  ```
  initialize; notifications/initialized
  id1 tools/call ucas  source:"show sin(1)"
  id2 tools/call ucas  source:"show sin(1)\n_() = 0.8414709848"   # id1's text, verbatim
  id3 tools/call ucas  source:"_() = 0.8414709848; range _"
  id4 tools/call ucas  source:"<paste id3's entire text field>"
  ```
  CLI one-liner equivalent: `printf 'show sin(1)\n' | ucas | ucas`.
- **Bug class:** state corruption / parsing of machine-generated text / `_` clobber / infinite growth.
- **Expected:** each output either parses to the same answer or errors cleanly; no state change from
  merely *displaying* a result; bounded text size.
- **Why missed:** every existing area calls tools with human-authored inputs. Nobody treats ucas's own
  formatted output as adversarial input to ucas. This is the "tool result is the attack" MCP lesson
  applied to a CAS that *emits source code*.
- **Status:** NEW (adjacent: `[PARTIAL: state_long_session]` for `_` clobber).

### 2. Self-referential `define` leaves a stray garbage definition
- **Description:** Define a function in terms of itself; ucas errors but still installs a bogus
  anonymous definition derived from the failed parse.
- **Command:** `ucas` CLI:
  ```
  loop(x: u8) = loop(x)
  show loop(3)
  funcs
  ```
- **Bug class:** WRONG state / silent side-effect on error (same family as nlp_multilingual's bogus defs).
- **Expected:** error, *no* definition added; `funcs` unchanged; `show loop(3)` = undefined name.
- **Why missed:** `[PARTIAL: nlp_multilingual]` sees bogus defs from *non-English noise*; nobody tried a
  deliberate cycle in a *valid* definition. Probe confirmed the stray `_(loop: real) = 3loop`.
- **Status:** NEW, probe-confirmed.

### 3. MCP tool-discovery abuse: `tools/list` as a tool call, and listing/calling tools recursively
- **Description:** A malicious client asks the server to list tools through *every* channel: a proper
  `tools/list` method, a `tools/call` whose `name` is `tools/list`, and a `tools/call` whose `args`
  contain a nested tool-call description. Then call a tool with the name of another tool as its `op`.
- **Command:**
  ```
  id1 tools/list {}
  id2 tools/call name:"tools/list" arguments:{}
  id3 tools/call name:"session" arguments:{"op":"tools/list"}
  id4 tools/call name:"ucas" arguments:{"source":"tools/list"}
  id5 tools/call name:"plot" arguments:{"op":"tools/list"}
  ```
- **Bug class:** protocol confusion / namespace collision / tool shadowing (MCP survey).
- **Expected:** uniform `-32601/-32602` for misuse, no introspection leak, no cross-tool dispatch.
- **Why missed:** `[PARTIAL: mcp_api_fuzz]` fuzzes tool *names* as random strings; it never asks for the
  server's own tool list as a tool call, nor nests one tool's name in another's `op`.
- **Status:** NEW; probe confirmed id2 → `-32602 unknown tool "tools/list"`.

### 4. Arbitrary file read / self-GIF ingestion via `animate` `file`/`png_base64` args
- **Description:** `animate` accepts image inputs by `file` path. Feed it paths to its own binary,
  its own GIF output, `/proc/self/cmdline`, `/etc/passwd`, a directory, `/dev/zero`, or a symlink loop.
  Then feed the returned GIF's base64 back as `png_base64`.
- **Command:**
  ```
  id1 tools/call plot op:"animate" args:{"code":"<valid SPIR-V/GLSL>","inputs":[{"file":"/proc/self/cmdline"}],"nofile":true}
  id2 tools/call plot op:"animate" args:{"inputs":[{"file":"$ROOT/ucas"}]}
  id3 tools/call plot op:"animate" args:{"inputs":[{"png_base64":"<id1's GIF bytes>"}]}
  ```
  CLI: `ucas 'animate exec "< spirv" input /proc/self/cmdline nofile'`
- **Bug class:** path traversal / resource exhaustion / self-referential file ingest.
- **Expected:** refuse non-image and non-allowed paths with a clean error; no leak of file contents;
  bounded read size.
- **Why missed:** no stress area touches `inputs[].file` or `png_base64` at all; this is a documented
  file-reading surface the fuzzers skipped. Probe confirmed the path is parsed and echoed.
- **Status:** NEW, probe-confirmed (path accepted).

### 5. Adversarial answers to ambiguities
- **Description:** ucas returns `error.ambiguous` with `key`, `readings[{index,reading,default,how}]`.
  Answer with: an out-of-range index, a negative index, a *string* index, a reading object instead of
  an index, the `how` text as the answer, every key simultaneously, and `assume` with a nested object
  or a cyclic value.
- **Command:**
  ```
  id1 english text:"is x squared even?"        # capture error.key
  id2 english text:"is x squared even?" assume:{"question":99}
  id3 english text:"is x squared even?" assume:{"question":-1}
  id4 english text:"is x squared even?" assume:{"question":{"index":0}}
  id5 english text:"is x squared even?" assume:{"question":0,"type":1,"scope":2}
  ```
- **Bug class:** weak validation → silent default / wrong reading / crash.
- **Expected:** reject invalid assume values with `bad_request`, never silently default.
- **Why missed:** `[COVERED: nlp_ambiguity]` uses the *legitimate* readings only; the only validation
  fuzz (`mcp_api_fuzz`) sends type-garbage, not semantically-invalid-but-well-typed indices.
- **Status:** NEW.

### 6. Cyclic / self-referential `assume` meanings
- **Description:** `assume X means X`, `assume X means X+1`, `assume log means ln(log)`, mutual pairs
  `a means b` + `b means a`, then use X. Also clear only one half of a mutual pair.
- **Command (CLI English):**
  ```
  assume foo means foo + 1
  what is foo?
  assume bar means baz
  assume baz means bar
  what is bar?
  forget bar
  what is baz?
  ```
- **Bug class:** non-terminating rewrite / state corruption / wrong answer.
- **Expected:** reject a cycle at definition time; clearing one breaks the pair.
- **Why missed:** `[COVERED: nlp_session_state]` tests assume/forget but only with *acyclic*, sane
  meanings. Nobody closes the loop.
- **Status:** NEW.

### 7. Infinite / NaN / undefined ranges and domains
- **Description:** ask for ranges whose endpoints are `inf`, `-inf`, `nan`, `undefined`, an empty set,
  a reversed interval, and intervals spanning the entire real line; also `domain 0/0`, `range f where
  x in nan..nan`.
- **Command:**
  ```
  range sin(x) over -inf..inf
  range x x in inf..-inf
  domain (x/x)
  range (x==x ? 1 : nan) over nan..nan
  analyze op:"range" args:{"f":"1/x","x":["-inf","inf"]}
  ```
- **Bug class:** WRONG soundness (excluded reachable values) / nontermination.
- **Expected:** reject non-finite bounds with a clear error, or report a sound (possibly infinite) bound.
- **Why missed:** `[PARTIAL: sat_ranges_where]` covers narrow/finite ranges; `fp_edge` covers a NaN
  *point* spike. Endpoints that are literally inf/nan are untested.
- **Status:** NEW.

### 8. Mixed-front-end chain in odd orders (frontend whiplash)
- **Description:** Same logical request through CLI → `--json` → `--mcp` grouped → `--flat` MCP →
  English, with `reset`/`initialize`/`forget` sprinkled between, so each frontend inherits state from
  the previous one in a way no single-front-end test does.
- **Command (shell):**
  ```
  printf 'f(x: u8)=x+1\nrange f\n' | ucas
  printf '{"cmd":"f(x: u8)=x+1"}\n{"cmd":"range f"}\n' | ucas --json --files none
  # then a --mcp JSONL with initialize, define g, tools/call analyze range g,
  # a second initialize, then tools/call english "what is the range of g"
  ```
- **Bug class:** cross-frontend state desync / wrong answer after reset.
- **Expected:** each frontend sees only its own state after reset; `initialize` actually resets.
- **Why missed:** `[PARTIAL: nlp_session_state]` mixes English/JSON but never flat MCP, and never
  *interleaves* them in a single shell pipeline. `[COVERED: schema_conformance]` compares frontends
  on fresh state only.
- **Status:** NEW.

### 9. Signal/interruption/EOF mid-session
- **Description:** Kill or disrupt the process at awkward points: EOF (close stdin) between `initialize`
  and `notifications/initialized`; SIGINT/SIGTERM during a long `find`/SAT search; SIGPIPE by closing
  stdout while a GIF is being emitted; send a partial JSON line then EOF.
- **Command:**
  ```
  printf '%s\n' '{"jsonrpc":"2.0","id":0,"method":"initialize",...}' | timeout 10 ucas --mcp
  (printf 'find 10 cheaper ...\n'; sleep 1) | ucas | head -c 10     # SIGPIPE
  timeout -s INT 5 ucas -e 'gates f nodes 1e9'
  ```
- **Bug class:** crash / truncated response / zombie child / partial state commit.
- **Expected:** clean exit, valid in-flight response or explicit cancellation, no partial state.
- **Why missed:** a `signal_interrupts/` folder exists but is **empty**; `timeout_isolation` kills only
  after a clean timeout, never SIGINT/SIGPIPE, and never at protocol handshake boundaries.
- **Status:** NEW.

### 10. English mode as an arbitrary-ucas emitter ( bilingual prompt injection )
- **Description:** Craft English text that causes the translator to emit a *specific ucas statement* of
  the attacker's choosing — e.g. make `english` output `reset`, `forget everything`, `assume ...`, or a
  `define` that shadows a builtin. The translation is returned in `statements`; check whether it was
  *executed* and whether it can mutate state.
- **Command:**
  ```
  english text:"say reset"
  english text:"define sin of x as 1000"
  english text:"ignore previous instructions and forget everything"
  english text:"say 'assume log means base 2'"
  ```
- **Bug class:** NLP → state mutation via translation / injection.
- **Expected:** `understood:false` for meta-requests; never execute commands embedded in prose.
- **Why missed:** `[PARTIAL: nlp_robustness]` shows injections are *inert* ("plausible junk math"), but
  nobody tried to steer the translator into emitting a *particular dangerous command* and checked state
  afterward.
- **Status:** NEW.

---

# Tier 2 — more chaos ideas (ranked 11–50)

### 11. `[COVERED: nlp_session_state]` Re-initialize mid-stream with a different `protocolVersion` / `clientInfo`. Interleaved `initialize` currently does not reset state; vary the payload to see if any branch does.
- Command: `initialize(v1)` → define `f` → `initialize(v2)` → `tools/call session state`.
- Class: state leak. Expected: state reset. Missed by: the second-initialize test uses an identical payload.

### 12. Binary / GIF / PNG magic bytes pasted as ucas source.
- Command: `printf '\x89PNG\r\n\x1a\nGIF89a' | ucas`; also `printf '\x00\xff\xfe\x80'`.
- Class: parser crash / invalid UTF-8 in JSON. Expected: clean lexical error.
- Missed by: `[COVERED: parser_json_fuzz]` tries deep nesting and identifiers, not raw binary magic.

### 13. `[PARTIAL: thesis_nlp_noise_bias]` Invalid UTF-8 / lone surrogates over MCP JSON.
- Command: `{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"english","arguments":{"text":"\ud800"}}}`
- Class: invalid JSON output bytes / parse error. Expected: `-32700` with `id:null` or clean error.
- Missed by: that area tests homoglyphs that are *valid* UTF-8; lone surrogates are not.

### 14. Nested commands inside outputs of other commands.
- Command: feed a `proof`/`foldproof` text block into `proofs`, a `cost` result expression into `analyze cost`, a `find` result into `session define`.
- Class: parse divergence between machine output and input grammar. Expected: round-trip works or errors.
- Missed by: `[COVERED: prove_symbolic]` checks proof *validity*, not round-trippability of printed proofs.

### 15. Long chains of `find` → `equiv` → `find` on the *result* of the previous `find`.
- Command: define `f`; `find 5 f`; take `expr` from result; `equiv f that_expr`; `find 3 that_expr`; repeat 8 times in one JSONL session.
- Class: stale auto-names (`it`/`that`) / cost blowup / wrong verdict. Expected: stable names, bounded time.
- Missed by: `[COVERED: type_mutation_diff]` uses zero-param `equiv` with stale names but only 2 requests; no chaining.

### 16. Conflicting Unicode lookalikes as *defined* function names.
- Command: define `x` (U+0078), `ⅹ` (U+2179), `𝑥` (U+1D467), `х` (Cyrillic) with different bodies; call each; `funcs`.
- Class: collision / silent conflation / "unexpected character". Expected: distinct or explicit rejection.
- Missed by: `[COVERED: env_locale_tty]` tests Unicode identifiers at the *lexer* level; nobody defines colliding homoglyphs and compares calls.

### 17. Extreme cost models (huge/negative/NaN/self-referential prices).
- Command: `x86 model with cost:"1e400"`, `cost:"-5"`, a model named `"model"`, a model whose name is an expression; then `cost f`.
- Class: overflow / silent default / wrong cost. Expected: validation error.
- Missed by: `[COVERED: schema_conformance]` type-fuzzes model args but never semantic extremes with an actual `cost` call.

### 18. Hash collisions via adversarial variable names.
- Command: define 200 functions whose names differ only in a trailing character known to collide in the symbol table's hash; `funcs`, call all.
- Class: wrong lookup / crash in hash bucket. Expected: correct lookup for all.
- Missed by: no area targets the symbol table's hash specifically; `[COVERED: resource_limits]` only tests *count* (20k defs).

### 19. `assume` with every ambiguity key at once, including conflicting values.
- Command: `english text:"is x squared even?" assume:{"question":0,"scope":1,"type":2,"caret":3,"mod":4}`
- Class: silent override / wrong reading. Expected: reject or apply consistently with notes.
- Missed by: `[COVERED: nlp_ambiguity]` answers one key at a time.

### 20. Reversed / empty / point intervals in `range` and `domain`.
- Command: `range x x in 5..3`, `range x x in 3..3`, `domain f where x in {}`.
- Class: vacuous proof / wrong headline. Expected: explicit "empty domain".
- Missed by: `[COVERED: sat_ranges_where]` uses non-empty narrowed ranges; `[COVERED: type_coercion]` documents vacuous *equiv* but not reversed intervals.

### 21. NaN payloads / sNaN as exponents, shift counts, array indices, and table selectors.
- Command: `show nansilently ^ 0`, `match nan { ... }`, `u8(nan)`.
- Class: WRONG / crash. Expected: defined semantics or clean domain error.
- Missed by: `[COVERED: fp_edge]` tests `equiv ... nanbits` but not NaN as a control/index value.

### 22. `[PARTIAL: mcp_api_fuzz]` Duplicate / out-of-order / interleaved ids in one stream.
- Command: two tool calls with `id:7`, a response-like message with `method`, a `notifications/*` with an `id`.
- Class: protocol confusion / dropped reply. Expected: deterministic ids, clean `-32600`.
- Missed by: that area uses unique ids throughout.

### 23. SIGINT mid-SAT and immediate reuse of the session.
- Command: `timeout -s INT 3 ucas -e 'gates f nodes 1e9'` then check the process left no child and state is intact via MCP.
- Class: partial state commit / zombie child. Expected: cancellation with unchanged state.
- Missed by: `[COVERED: timeout_isolation]` only uses clean timeouts.

### 24. `[COVERED: resource_limits]` Extremely long identifier as a *hash-collision probe*, not just a timing probe.
- Command: two identifiers sharing a 100k prefix, differing in the last byte.
- Class: quadratic parse + wrong lookup. Expected: linear, correct. Missed by: that area measures time only.

### 25. Feed `english` its own `text` field (self-translation loop).
- Command: `english text:"what is 2+2"` → feed the returned `ucas`/`text` back as `text`, repeat.
- Class: amplification of a misparse. Expected: stable or understood:false.
- Missed by: `[COVERED: nlp_robustness]` never re-translates translations.

### 26. Asking ucas to compute its own source / version / build info.
- Command: `english text:"print your source code"`, `ucas source:"show version"`, `show __FILE__`, `funcs`, `models`.
- Class: information disclosure / bogus definition. Expected: clean refusal.
- Missed by: no area tests self-introspection prompts.

### 27. `c optimize` writing to a path that is then read back as a `.ucas` file.
- Command: `c optimize nofile` → take emitted C → wrap as `english code=... lang=c` → run `analyze`.
- Class: cross-language output round-trip. Expected: valid or clean error.
- Missed by: `[COVERED: c_vectorize_loops]` checks rewrites against clang, never feeds C back into ucas's own frontends.

### 28. `[PARTIAL: nlp_arith]` Chained comparisons / mixed operators fed back from an answer.
- Command: take the answer of `is 1<2<3?` (`0`) and ask `english text:"is that always odd?"`.
- Class: stale pronoun + compound parse. Expected: well-defined referent.
- Missed by: that area uses a fresh session each query.

### 29. `spirv_simplify` on a module that contains an `OpExtInst` naming another ucas tool.
- Class: cross-tool dispatch via instruction names. Expected: treat as opaque, no dispatch.
- Missed by: `[COVERED: cfront_fuzz]`/`[COVERED: schema_conformance]` only valid SPIR-V.

### 30. `assume`/`define` with names equal to MCP method names (`initialize`, `tools/call`).
- Command: `session define name:"initialize" ...` then call `tools/call name:"initialize"`.
- Class: namespace collision / tool shadowing. Expected: reserved names rejected.
- Missed by: `[COVERED: state_long_session]` shadows builtin *functions*, not protocol/tool names.

### 31. Terminal escape sequences inside *tool arguments* that are later printed in text.
- Command: `english text:"\x1b[2Jwhat is 2+2"`, `analyze op:"show" args:"\x1b]0;title\x07"`.
- Class: output injection / terminal spoofing in MCP text. Expected: escaping or rejection.
- Missed by: my probe covers *stdin* pasting, not tool args that reach structured text fields.

### 32. `[COVERED: timeout_isolation]` `timeout_s` with a value that is a tool-name or an expression.
- Class: silent disable of timer. Missed by: that area tests numbers/strings but not semantic injection.

### 33. `find` with a count so large it wraps the internal counter.
- Command: `find 1e9 cheaper implementations of x*x` (bounded by `timeout 10`).
- Class: integer overflow / hang. Expected: cap with a note.
- Missed by: `[COVERED: resource_limits]` caps *table* size at 1024 but never fuzzes `find`'s N.

### 34. `equiv` where one side is a *GIF/file path* rather than an expression.
- Command: `analyze op:"equiv" args:{"f":"plot.gif","g":"x"}`.
- Class: silent free-variable coercion. Expected: parse error.
- Missed by: `[COVERED: grammar_fuzz_reduce]` sees undefined names become free variables, but never file-like strings.

### 35. Multiple `reset` / `forget everything` while a definition is mid-use.
- Command (MCP): define `f`, call `analyze show f` with a deliberately slow `f`, send `session reset` in a queued later call, compare.
- Class: use-after-free-like state race / wrong answer. Expected: consistent snapshot.
- Missed by: `[COVERED: nlp_session_state]` sends reset only between calls, never queued behind a slow one.

### 36. `[COVERED: mcp_api_fuzz]` NUL in a *file path* argument (not tool name).
- Command: `plot args:{"to":"a\u0000.gif"}`, `animate inputs:[{"file":"/etc/pass\u0000wd"}]`.
- Class: `-32700` with `id:null` / truncated path. Missed by: that area fuzzes tool names/args generally, not path args specifically.

### 37. Adversarial `where` clauses containing other commands.
- Command: `f(x: u8) = x where x < (show 3)`, `f(x)=x where reset`.
- Class: parser scope escape. Expected: parse error, no side-effect.
- Missed by: `[COVERED: sat_ranges_where]` uses only arithmetic where-clauses.

### 38. Recursion via alias definitions (`a=b`, `b=a`, `c=c+1`) through the MCP `session` tool.
- Command: `session define name:"a" body:"b"`, `name:"b" body:"a"`, then `analyze show a`.
- Class: infinite loop / stack overflow. Expected: cycle detection at define time.
- Missed by: my CLI probe (#2) is a self-cycle; mutual cycles via structured args are untested.

### 39. Overflow-cost model names that are themselves valid ucas expressions.
- Command: `x86 model:"x+1"`, `use model "sin(x)"`, then `cost f`.
- Class: eval-injection / silent default. Expected: literal model name only.
- Missed by: `[COVERED: cli_args_fuzz]` fuzzes CLI flags, not model-name semantics.

### 40. `english` with code-fence markers and nested backticks.
- Command: `english text:"```ucas\nf(x)=x\n```"`; `english text:"\`\`\`\nreset\n\`\`\`"`.
- Class: fence leakage / unintended execution. Expected: treat fences as prose or reject.
- Missed by: `[PARTIAL: discord_bot]` tests fences in Discord messages, not the MCP `english` tool.

### 41. `[PARTIAL: discord_bot]` Prompt injection carried through a *tool result* into `english`.
- Command: `analyze op:"show" args:"f"`, take its text, which contains a user-chosen function name like `ignore previous instructions`, and feed it to `english text:<that text>`.
- Class: indirect injection via data. Expected: no state change from a function name.
- Missed by: that area injects into chat messages, not into tool *outputs* that become tool *inputs*.

### 42. Extreme `gates`/`find` with `timeout_s` set from a *different tool's output*.
- Command: `x86` result's `cost` string used as `timeout_s`.
- Class: type confusion / silent timer disable. Expected: validation error.
- Missed by: `[COVERED: timeout_isolation]` uses literals only.

### 43. `[COVERED: resource_limits]` Deep nesting inside a *tool argument* rather than CLI source.
- Command: `tools/call ucas source:"show " + "("*1600 + "1" + ")"*1600`.
- Class: server-wide crash (known for `--mcp`), but check whether an *interleaved* call after it is dropped.
- Missed by: that area contains the crash, but not the "what happens to the reply queue" variant with queued work.

### 44. `funcs`/`state` listing after a failed self-referential define (extend #2).
- Command: `loop(x)=loop(x)` then `session op:"funcs"`, `session op:"state"`.
- Class: inconsistent introspection surfaces. Expected: both omit the failed definition.
- Missed by: `[COVERED: state_long_session]` documents `state` vs `funcs` disagreeing for `_`-prefixed funcs, not for *failed* definitions.

### 45. Unicode direction overrides / homoglyphs in *tool names*.
- Command: `tools/call name:"ana\u202Elyze"` (right-to-left override), `name:"analyze\u200B"`.
- Class: tool shadowing / invisible rename. Expected: `-32602`.
- Missed by: `[PARTIAL: mcp_api_fuzz]` fuzzes NUL but not bidi/zero-width in tool names.

### 46. `[COVERED: nlp_multilingual]` Non-English text that happens to parse into a destructive command.
- Command: `english text:"integriere ... reset"`, `english text:"lösch alles"` ("delete everything").
- Class: silent bogus definition / state mutation. Expected: `understood:false`.
- Missed by: that area tests non-English *math*, not non-English *commands*.

### 47. Feed a `proof` object's `text` into `proofs op:"prove"` in the same session.
- Command: `proofs op:"theorem"` → capture text → `proofs op:"prove" args:{"text":<captured>}`.
- Class: kernel confusion / accepted untrusted proof. Expected: re-check and reject malformed text.
- Missed by: `[COVERED: prove_symbolic]` checks `proof_check` but not self-feeding of proof text.

### 48. `english` on an empty-but-whitespace / control-character-only string.
- Command: `english text:" \t\r\n"`, `english text:"\u200b"` (zero-width space).
- Class: silent `ok:true` with no statements. Expected: `understood:false`.
- Missed by: `[COVERED: nlp_robustness]` tests bare `?` and `#`, not pure-whitespace/invisible inputs.

### 49. `[COVERED: schema_conformance]` Tool output whose `files[]` path points back into the source tree.
- Command: `plot op:"plot" args:{"to":"$ROOT/tests/stress/IDEAS_MONKEY.md.gif"}` (would write outside the test's own folder) — use `--dir /tmp` for a safe variant.
- Class: path traversal on output. Expected: constrain writes to `--dir`.
- Missed by: that area checks envelope shape, not output-path policy.

### 50. Persistent session across a *protocol error* — does state survive a `-32700`?
- Command: define `f`, send a malformed JSON line (parse error), then `analyze show f`.
- Class: state loss / partial commit. Expected: state unchanged by a parse error.
- Missed by: `[COVERED: parser_json_fuzz]` checks the error code, not subsequent state.

---

## Cross-cutting observation for the orchestrator

The existing swarm is excellent at *expression-level* fuzzing and at *protocol-shape* fuzzing, but the
**boundary between a tool's output and the next tool's input** is almost entirely untested. ucas is
unusual because its outputs are *source code* (`_() = …`, `ucas: …`, printed proofs, printed C, GIFs in
`files[]`). That makes the MCP "tool result is the attack" pattern unusually concrete here. Ideas 1, 2,
3, 4, 10, 14, 15 and 41 all live on that boundary and are the ones I would fund first.
