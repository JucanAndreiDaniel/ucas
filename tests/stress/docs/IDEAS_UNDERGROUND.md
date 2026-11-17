> **Portability:** set `ROOT=/path/to/ucas` (the repo root) before copy-pasting reproducers below, or `cd` to the repo root and use `ROOT=$PWD`; `$ROOT/ucas` is the built binary. Reproducers using the `$UC` shorthand also need `UC=$ROOT/ucas`.

# Underground / weird-input ideas for stressing ucas

IDEA RESEARCHER deliverable. Read `SPEC.md`, `RESEARCH.md`, `PHD_RESEARCH.md`,
`FOCUSED_IDEAS.md`, `HISTORICAL_PAPERS.md`, `FLOAT_MAGIC.md` and `MASTER_FINDINGS.md`
first so we do not duplicate the 28 areas already reported.

**Scope of this document:** ideas only (plus a few 10-second confirmation probes). No
large campaign was run. Writes are confined to `tests/stress/`. Binary shorthand below:
`UC=$ROOT/ucas`.

## Legend

- Bug class: **CRASH** / **HANG** / **WRONG** / **NLP** / **STATE** / **PROTO** / **LEAK** / **LIMIT**
- Coverage marker: **NEW** (not in any existing area) · **PARTIAL** (adjacent area exists, angle is new) · **COVERED — DO NOT DUPLICATE**
- Ranks are by (cheapness × likelihood of crash/hang/wrong/state bug). Tier 1 = try first.

## Sources consulted (all reachable 2026)

- Trojan Source / bidi + homoglyph: Boucher & Anderson, USENIX Security 2023, <https://www.usenix.org/system/files/sec23fall-prepub-151-boucher.pdf>; CVE-2021-42574/42694; Knostic zero-width guide <https://www.knostic.ai/blog/zero-width-unicode-characters-risks>; CSA note on Tags-block injection into MCP/agent files <https://labs.cloudsecurityalliance.org/research/csa-research-note-unicode-instruction-injection-ai-skills-20>; MITRE T1027.018 <https://attack.mitre.org/techniques/T1027/018>.
- Unicode normalization / confusables: UAX #15 <https://unicode.org/reports/tr15>; "confusables.txt and NFKC disagree on 31 characters" <https://paultendo.github.io/posts/unicode-confusables-nfkc-conflict>; UTS #39 skeleton.
- Parser differentials / LangSec: GitLab blog <https://about.gitlab.com/blog/how-to-exploit-parser-differentials>; GitHub SAML SSO bypass <https://github.blog/security/sign-in-as-anyone-bypassing-saml-sso-authentication-with-parser-differentials>; OffensiveCon25 Joernchen talk; "weird machines" Bratus et al. <https://langsec.org/papers/Bratus.pdf>.
- JSON parser minefield: HN <https://news.ycombinator.com/item?id=20724672>; nlohmann/json #5322 `1e400` → infinity <https://github.com/nlohmann/json/issues/5322>; duplicate-key bug bounty <https://medium.com/@Charlie001/json-duplicate-key-parsing-differential-in-manifest-signing-api-7250239fb6a2>; NHI duplicate-key guide.
- Billion Laughs / quadratic blowup: ZAP alert 40044 <https://www.zaproxy.org/docs/alerts/40044>; Wikipedia <https://en.wikipedia.org/wiki/Billion_laughs_attack>.
- Algorithmic complexity / hash DoS: Crosby & Wallach USENIX 2003 <https://www.cs.auckland.ac.nz/~mcw/Teaching/refs/misc/denial-of-service.pdf>; CERT VU#903934.
- ReDoS: OWASP <https://community.owasp.org/attacks/Regular_expression_Denial_of_Service_-_ReDoS>; SoK <https://arxiv.org/html/2406.11618v1>.
- Error/timing oracles: NCC padding-oracle guide <https://www.nccgroup.com/research/cryptopals-exploiting-cbc-padding-oracles>; USENIX Security 2024 timing study <https://www.usenix.org/system/files/usenixsecurity24-dunsche.pdf>; Intel timing guidance.
- Fuzzing folklore: Miller/Fredriksen/So (gwern PDF), Fuzzing Book <https://www.fuzzingbook.org/html/Fuzzer.html>; HN "text parsing is easy" thread <https://news.ycombinator.com/item?id=11977036>; SandboxJS deep-nesting CVE-2026-34211.
- CTF integer/null-byte folklore: CTF Wiki off-by-one <https://ctf-wiki.mahaloz.re/pwn/linux/glibc-heap/off_by_one>; CTF Cookbook integer overflow <https://ctfcookbook.com/docs/pwn/integer-overflow>.
- CAS wrong-answer folklore: SymPy best-practices ("silently give the wrong answer") <https://docs.sympy.org/latest/explanation/best-practices.html>; HN SymPy bug thread <https://news.ycombinator.com/item?id=25684678>; SymPy issue #17418.

---

## Tier 1 — cheap, high-yield, mostly NEW

### 1. Exponential definition chains ("Billion Laughs" via named functions) — CONFIRMED CRASH — NEW
- **Description:** a chain where each definition calls the previous one twice expands exponentially and segfaults the evaluator.
- **Source:** Billion Laughs / quadratic blowup, ZAP alert 40044 + Wikipedia (folklore ported to CAS semantics).
- **Command:**
  ```sh
  python3 -c '
  L=["f0(x: u8) = x + 1"]
  for i in range(1,15): L.append("f%d(x: u8) = f%d(f%d(x))"%(i,i-1,i-1))
  L.append("show f14(0)")
  open("/tmp/opencode/bl14.ucas","w").write("\n".join(L)+"\n")'
  timeout 10 $ROOT/ucas /tmp/opencode/bl14.ucas
  ```
- **Bug class:** CRASH (SIGSEGV, rc=139; core dumped).
- **Why missed:** `resource_limits` tested syntactic nesting depth and large *text*, not semantic fan-out through 14 short definitions. `grammar_fuzz_reduce` generates random trees, not doubling chains. 15 lines, ~0.2 s. **Probe result:** depth 13 → rc 0, depth 14 → rc 139, depth 15 → rc 139. Also check MCP containment (a `--json`/`--mcp` server-wide kill would be a second finding).

### 2. NUL byte inside a `.ucas` source line — NEW
- **Description:** an embedded NUL truncates/re-splits a line and can silently fabricate an anonymous definition.
- **Source:** CTF "poison null byte" / off-by-one folklore (CTF Wiki).
- **Command:** `printf 'show 1+2\000show 3+4\n' | $UC`  → observed `_() = 3` / `-> int` (expected `3` then `7`, or an error).
- **Bug class:** WRONG + parser differential (CLI vs MCP string arg).
- **Why missed:** `mcp_api_fuzz` put `\u0000` in a *tool name* and got `-32700`; nobody put a raw NUL in a `.ucas` file or MCP `source` string. Cheap: one printf.

### 3. Failed self-referential definition leaves a bogus anonymous definition — NEW
- **Description:** `f(x)=f(x)` errors, yet the session is left with a fabricated `_(f: real) = f`.
- **Source:** recursive-definition folklore (Wikipedia "infinite recursion") + LangSec "state after a parse error".
- **Command:** `printf 'f(x: u8) = f(x)\nshow f\nfuncs\n' | $UC`
- **Bug class:** STATE / WRONG (error must be atomic; a rejected definition must not mutate the symbol table).
- **Why missed:** `state_long_session` covered builtin shadowing and clobbered `_`, `nlp_session_state` covered English/JSON stores; neither injected a *failed* definition. Relates to the master finding "one lexical error aborts a whole file" — here the error is semantic and does not abort.

### 4. Non-finite JSON numeric literals echoed verbatim in the reply envelope — NEW
- **Description:** a JSON-RPC `id` of `1e400` is accepted and echoed back as the literal `1e400`, which is not a valid JSON number in the output.
- **Source:** nlohmann/json #5322 (`1e400` overflow → infinity), HN "Parsing JSON Is a Minefield".
- **Command:**
  ```sh
  printf '%s\n' '{"jsonrpc":"2.0","id":1e400,"method":"tools/call","params":{"name":"english","arguments":{"text":"what is 2+2?"}}}' | $UC --mcp
  ```
  Observed `"id": 1e400` twice (top level and `structuredContent.id`).
- **Bug class:** PROTO / WRONG (output is not parseable by strict JSON consumers; check `NaN`, `Infinity`, `-Infinity`, `1e-400`, `1.5`).
- **Why missed:** `schema_conformance` checked id *types* (null/bool/array/object) and 27 tool families; `mcp_api_fuzz` checked NUL in names. No one swept numeric-literal grammar.

### 5. Trojan-Source bidi overrides inside identifiers and English text — PARTIAL
- **Description:** U+202E/U+202A bidi controls are rejected with `unexpected character '?'`, but are echoed raw into stderr and likely into MCP JSON as invalid UTF-8.
- **Source:** Boucher & Anderson CVE-2021-42574; Knostic.
- **Command:** `printf 'show \342\200\256X\342\200\254\n' | $UC` and the MCP `english` equivalent with `text` = `"is \u202eX\u202c even?"`.
- **Bug class:** NLP / invalid-UTF-8-in-MCP / possible display-vs-parse confusion.
- **Why missed:** `nlp_multilingual` and `thesis_nlp_noise_bias` tested Cyrillic/Greek homoglyphs and zero-width chars, explicitly *not* bidi controls or the Tags block.

### 6. Unicode Tags block (U+E0000–U+E007F) invisible instruction payload — NEW
- **Description:** invisible tag characters embedded in English text or a `basis`/`model` name can split/alter tokens with no visible difference.
- **Source:** CSA research note on hidden adversarial payloads in MCP servers/skill files; Knostic GlassWorm analysis.
- **Command:** `python3 -c 'print("is " + chr(0xE0061)+"x even?")' | $UC` (tag 'a' before `x`); compare with clean `is x even?`.
- **Bug class:** NLP / invalid UTF-8 / prompt-injection surface.
- **Why missed:** prior Unicode work stopped at zero-width joiners and homoglyphs; Tags block untested.

### 7. Math-Unicode operator normalization is asymmetric — NEW
- **Description:** `≤` is silently normalized to `<=` and answered, while `∫` is rejected — no consistent policy for mathematical Unicode.
- **Source:** Mötley Crüe Unicode Normalization guide; UAX #15.
- **Command:**
  ```sh
  printf 'is 1 \342\211\244 2?\n' | $UC          # observed: ucas: 1 <= 2 / 1
  printf 'what is \342\210\253 x from 0 to 1?\n' | $UC  # observed: sorry: I can't read the character
  ```
- **Bug class:** NLP (silent acceptance of some symbols, rejection of others), potential WRONG if a confusable maps to a different operator.
- **Why missed:** no math-symbol sweep; `nlp_multilingual` used natural-language text, not mathematical operators. Sweep `∑ ∏ √ ∞ ≠ ≈ ∈ ∀ ∃ ≤ ≥ ± × ÷ ^ ′ ∂ ∇`.

### 8. NFKC-confusable command keywords and identifier collisions — NEW
- **Description:** fullwidth / mathematical-bold / ligature spellings of `show`, `range`, `i`, `x` may normalize to ASCII commands or become distinct identifiers.
- **Source:** UAX #15; paultendo "confusables.txt and NFKC disagree on 31 characters"; UTS #39 skeleton.
- **Command:** `printf '\357\275\307\357\275\210\357\275\177 1+2\n' | $UC` (fullwidth `ｓｈｏｗ`); and define `𝐱` and `x` then compare `show` results.
- **Bug class:** NLP / STATE (two names that NFKC-collapse to one, or a keyword bypass).
- **Why missed:** `env_locale_tty` noted "Unicode-identifier limits" as a LIMIT but did not sweep confusable keyword spellings.

### 9. ReDoS-style English repetition — NEW
- **Description:** long ambiguous noun-phrase chains may trigger catastrophic backtracking in the English tokenizer/grammar.
- **Source:** OWASP ReDoS; SoK arXiv 2406.11618.
- **Command:** `python3 -c 'print("what is " + "a of "*400 + "x?")' | timeout 10 $UC` (also `"is "`+`"x and "*Y`, `"range of "*Y`).
- **Bug class:** HANG (quadratic/exponential NLP parse).
- **Why missed:** `nlp_robustness` capped at 200–400 *words* and tested "too long" handling, not a repeating ambiguous *pattern* that stays under the cap.

### 10. Negative / zero / huge numeric arguments to option keywords — PARTIAL
- **Description:** counts, sizes, degrees and indices passed as negative or 0 can underflow allocations or loops.
- **Source:** CTF integer-overflow/underflow folklore (CTF Cookbook).
- **Command:** for `c` in `"cost f consecutive -1"`, `"approx f list -1"`, `"texenc T rows -1"`, `"tcdot n 1 samples -1"`, `"dword f ulp -1"`, `"plot f x in 1..0"` do `printf '%s\n' "$c" | timeout 10 $UC`.
- **Bug class:** CRASH / HANG (negative → huge size_t).
- **Why missed:** `resource_limits` tested table/list *max sizes* and `in {...}` caps; `timeout_isolation` tested `timeout_s` negatives. Option-level negative counts on search/texture commands are untested. **Probe result:** `approx x count -1`, `stoke f steps 0`, `banks f size 0`, `animate scan n 0` were all rejected gracefully — lower priority, but `consecutive`/`list`/`rows`/`samples` were not probed.

### 11. Timing oracle: SAT difficulty leaks proof internals via `timeout_s` — PARTIAL
- **Description:** measure response time across equal vs unequal pairs with the same apparent structure; a satisfiability-dependent timing delta is an information leak and also a determinism hazard.
- **Source:** padding-oracle / timing-attack folklore (NCC Group, USENIX Security '24).
- **Command:** time `equiv f g timeout_s:2` for GF(2^16) commutativity vs a trivially-equal transform; repeat 20×, compare distributions.
- **Bug class:** LEAK / DETERMINISM.
- **Why missed:** `timeout_isolation` verified that timers fire and sessions survive; it never treated *time-to-answer* as an observable. `sat_*` areas recorded give-ups, not timing distributions.

### 12. Error-message / progress oracle — PARTIAL
- **Description:** verbose proof text ("N AIG nodes, M conflicts", "empty domain", "sampled, not proved", "counterexample did not reproduce") reveals which internal path ran and can differ between frontends.
- **Source:** error-message oracle folklore (NCC "illustrative错误消息" padding-oracle discussion).
- **Command:** run the same `equiv`/`range` via CLI, `--json`, `--mcp` and `--flat`, diff the human `text` field and the `proof`/`notes` fields.
- **Bug class:** LEAK / DETERMINISM / NLP.
- **Why missed:** wire-level differential exists (`mcp_api_fuzz`, `schema_conformance`) but compares envelope shape, not the *semantic explanation* field across four frontends for a battery of give-up cases.

---

## Tier 2 — cheap, medium yield, new angles

### 13. Cyclic `basis`/`model` inheritance — NEW
- **Description:** `basis a : a` or `a : b`, `b : a` may recurse forever when resolving gates/costs.
- **Source:** cyclic-inheritance folklore (classic object-model bug).
- **Command:** `printf 'basis a : b { g(x) = x }\nbasis b : a { h(x) = x }\ngates g\nuse a\n' | timeout 10 $UC` (verify syntax with `help basis` first; my `cost 1` probe used the wrong syntax).
- **Bug class:** HANG / CRASH.
- **Why missed:** no existing area constructs basis/model inheritance graphs at all.

### 14. Cyclic `where` clause / mutually-referential params — NEW
- **Description:** `f(x)=x where x=f(x)` or `g(x)=y where y=g(x)` can loop during definedness analysis.
- **Source:** recursive-definition folklore.
- **Command:** `printf 'f(x: u8) = x where x = f(x)\nrange f\ndomain f\n' | timeout 10 $UC`
- **Bug class:** HANG / WRONG (vacuous proof).
- **Why missed:** `sat_ranges_where` tested *narrowing* with `where`, never self-reference.

### 15. Unicode-confusable name used consistently as a model/basis parent — PARTIAL
- **Description:** define `basis a : 𝐚 {...}` where the parent is a look-alike; check if resolution silently succeeds.
- **Source:** Trojan Source homoglyph CVE-2021-42694; NFKC conflict page.
- **Command:** `printf 'basis a { g(x)=x cost 1 }\nbasis b : \360\235\204\240 { h(x)=x cost 1 }\n' | $UC`
- **Bug class:** STATE / WRONG / NLP.
- **Why missed:** homoglyph tests were only in the English frontend, not in symbol-table resolution.

### 16. `--flat` MCP op-name homoglyph / near-spelling — PARTIAL
- **Description:** flat mode uses the tool name as the op; a confusable or British spelling may silently no-op or misroute.
- **Source:** parser-differential folklore; homoglyph catalog.
- **Command:** JSON-RPC `{"method":"tools/call","params":{"name":"analyse","args":{...}}}` and `name:"an\u0430lyze"` (Cyrillic а) in a file with `.flags` = `--flat`.
- **Bug class:** NLP / PROTO (silent default).
- **Why missed:** `mcp_api_fuzz` covered grouped MCP; `schema_conformance` covered flat with valid names only.

### 17. Duplicate JSON keys → whole request lost with `id:null` — NEW
- **Description:** duplicate keys anywhere in a request produce `-32700 parse error` with `id:null`, discarding the legitimate `id`; most parsers keep last-wins.
- **Source:** RFC 8259 duplicate-key ambiguity; duplicate-key bug bounty writeup; NHI guide.
- **Command:** `printf '%s\n' '{"jsonrpc":"2.0","id":1,"id":2,"method":"tools/call","params":{"name":"english","arguments":{"text":"what is 2?"}}}' | $UC --mcp` → observed `"id": null, "error": {"code":-32700,...}`. Same for duplicate keys inside `arguments`.
- **Bug class:** PROTO (correlating replies impossible).
- **Why missed:** `state_long_session` saw a duplicate key inside `assume.set` produce `id:null`; nobody generalized to *any* object in the envelope. Low severity but free.

### 18. JSON numeric-literal grammar sweep — NEW
- **Description:** accepted/rejected number spellings differ between the top-level `id` and numeric *arguments*.
- **Source:** HN JSON minefield; Coderanch NaN/Infinity debate.
- **Command:** feed `id` values `01`, `+1`, `.5`, `1.`, `1e`, `1e+`, `NaN`, `Infinity`, `-Infinity`, `0x10`, `1_000`, `1e-400` to `--mcp`; diff echoed `id` and error codes.
- **Bug class:** PROTO / WRONG.
- **Why missed:** no numeric-grammar sweep in `schema_conformance` or `parser_json_fuzz`.

### 19. BOM / CR-only line endings / mixed CRLF as statement separators — NEW
- **Description:** encoding-level line handling can merge or split statements.
- **Source:** parser-differential folklore; HN JSON minefield.
- **Command:**
  ```sh
  printf '\357\273\277show 1+2\n' | $UC          # observed: unexpected character '?'
  printf 'show 1+2\rshow 3+4\r' | $UC
  printf 'show 1+2\r\nshow 3+4\n' | $UC
  ```
- **Bug class:** NLP / WRONG (a whole file silently becoming one statement).
- **Why missed:** `env_locale_tty` varied env/TERM, never byte-level file encoding.

### 20. Overlong UTF-8 and lone surrogates in `source` strings — PARTIAL
- **Description:** invalid UTF-8 sequences can be echoed raw into MCP JSON (already seen for emoji/Cyrillic) or index past the end of a decode buffer.
- **Source:** UTF-8 security folklore; MITRE T1027.018.
- **Command:** `printf 'show \300\2571\n' | $UC` (overlong `/`); MCP `source` containing `\ud800` unpaired surrogate escape.
- **Bug class:** CRASH / invalid-UTF-8 output.
- **Why missed:** prior invalid-UTF-8 findings were *generated by* ucas from valid emoji input, not by feeding malformed encodings in.

### 21. Combining-mark bomb on a short identifier — NEW
- **Description:** thousands of combining marks after one letter stress normalization/column-width bookkeeping.
- **Source:** Unicode normalization folklore (UAX #15 "not closed under concatenation").
- **Command:** `python3 -c 'print("x" + "\u0301"*5000 + " = 1")' | timeout 10 $UC`
- **Bug class:** HANG / CRASH (column counter overflow in error caret).
- **Why missed:** `resource_limits` tested 100k plain chars (linear); combining marks add a normalization pass.

### 22. Negative-index / NaN-index expressions — NEW
- **Description:** array/list indexing with `-1`, `2^63`, `0/0`, `inf` may bypass bounds checks.
- **Source:** off-by-one CTF folklore (CTF Wiki).
- **Command:** for `e` in `a[-1]`, `a[9223372036854775808]`, `a[0/0]`, `a[inf]` do `printf 'a[3]=1;2;3\na=%s\nshow a\n' "$e" | timeout 10 $UC` (adjust to recurrences if needed).
- **Bug class:** CRASH / OOB read / WRONG.
- **Why missed:** no indexing stress in `sat_*` or `transforms_ode_series`.

### 23. Repeated failed definitions accumulate dead state — PARTIAL
- **Description:** hundreds of syntactically-invalid definitions may leak entries into `funcs` / `session state`.
- **Source:** LangSec "state after error"; `state_long_session` spirit.
- **Command:** `python3 -c 'print("\n".join("f%d(x: u8) = f%d(x)"%(i,i) for i in range(300)));print("funcs")' | $UC | wc -l`
- **Bug class:** STATE / HANG.
- **Why missed:** prior state tests used *successful* definitions.

### 24. `ring Z/1` zero-ring algebra contradictions — NEW
- **Description:** the zero ring reports `phi(1)=1` and `inverse 0 mod 1` claims every element is its own inverse — arguably wrong/inconsistent with the rest of the ring output.
- **Source:** ring-theory edge-case folklore.
- **Command:** `printf 'ring Z/1\ninverse 0 mod 1\norder 0 mod 1\ndlog 0 base 0 mod 1\n' | $UC`
- **Bug class:** WRONG / LIMIT (should be documented, not silently asserted).
- **Why missed:** `algebra_ring_ff` folder exists but is empty in the master index; no ring edge cases reported.
- **Probe result:** graceful, but `dlog` prints `check: 0^0 = 0` — contestable.

### 25. `factorint` of a hard near-2^64 semiprime — NEW
- **Description:** number-theoretic command with a 2^64 domain; a hard composite can hang past the budget.
- **Source:** algorithmic-complexity folklore (Crosby–Wallach).
- **Command:** `printf 'factorint 18446744073709551557\nfactorint 18446743979220271189\n' | timeout 10 $UC`
- **Bug class:** HANG.
- **Why missed:** no ring/FFT stress area reported results.

### 26. `solve` with zero variables, contradictory equations, or duplicate equations — NEW
- **Description:** degenerate linear systems may produce vacuous or wrong solution sets.
- **Source:** SymPy "silently give the wrong answer" / issue #17418.
- **Command:** for `q` in `"solve 1 = 2"`, `"solve x = x"`, `"solve x = 1, x = 2"`, `"solve 0*x = 0"` do `printf '%s\n' "$q" | $UC`.
- **Bug class:** WRONG / CRASH.
- **Why missed:** `prove_symbolic` focused on `equiv`/`axioms`/`identify`, not `solve`.

### 27. `substitute` with cyclic or undefined replacement — NEW
- **Description:** `substitute x = y in F`, `y = x` pairs, or replacing a reserved constant can loop or corrupt state.
- **Source:** symbolic-rewrite folklore (billion laughs for rewriters).
- **Command:** `printf 'substitute x = y in x^2\nsubstitute i = 1 in i*x\nsubstitute x = x in x\n' | timeout 10 $UC`
- **Bug class:** HANG / WRONG / STATE.
- **Why missed:** algebra commands had no dedicated stress area.

### 28. `gcd`/`lcm` of huge and zero operands — NEW
- **Description:** boundary values in polynomial/integer GCD can trigger division-by-zero or wrong degrees.
- **Source:** integer-overflow folklore.
- **Command:** `printf 'gcd 0, 0\nlcm 0, 0\ngcd 18446744073709551615, 0\nquo x, 0\nrem x, 0\nresultant 2, 3\n' | $UC`
- **Bug class:** CRASH / WRONG.
- **Why missed:** no algebra area reported. **Probe result:** `gcd 0,0` and `lcm 0,0` both return 0 (fine); `quo`/`rem` by zero untested.

### 29. `nthroots`/`unity` at the upper bound 64 — NEW
- **Description:** documented range 1..64; 64th roots/unity can swell or give up.
- **Source:** resource-limit folklore (upper bound is where bugs live).
- **Command:** `printf 'unity 64\nnthroots 64 x\n' | timeout 10 $UC`
- **Bug class:** HANG / LIMIT.
- **Why missed:** only `nthroots 0` was rejected in my probe; upper bound untested.

### 30. Expression-size oracle via `cost`/`gates`/`find` across reformulations — PARTIAL
- **Description:** equivalent algebraic forms should have stable reported node/cost counts; large jumps indicate a rewrite bug or a nondeterministic cost model.
- **Source:** PerfFuzz-like pathological input generation (Padhye thesis, already cited in PHD_RESEARCH) — new *application* to cost numbers.
- **Command:** `printf 'a(x)=x+x\nfind a\nmore 5\nmorph ...\n' | $UC` repeated; diff `cost` lines across runs.
- **Bug class:** DETERMINISM / WRONG.
- **Why missed:** `gates_find_cost` folder is empty; `metamorphic_identities` checks verdicts, not cost numbers.

---

## Tier 3 — lower yield / overlaps to be aware of

### 31. Unaffected-but-worth-a-golden: invalid numeric literals — NEW
`printf 'show 0x1p4\nshow 1_000\nshow .5\nshow 5.\nshow 01\nshow ++1\nshow 1+-2\n' | $UC`.
Bug class: NLP/WRONG. Source: parser-differential folklore. Existing `nlp_numbers` tested `1010b` and spelled decimals but not hex-float/underscore forms in the CLI parser.

### 32. `--flat` with `id:1e400` and a Unicode tool name — PARTIAL
Same as #4/#16 but in flat mode; source nlohmann/json #5322; bug class PROTO/LEAK; likely a second frontend-specific divergence.

### 33. Very long numeric literal is rejected (negative control) — COVERED
`show `+`9`*10000 → `error: number too long` (my probe). `resource_limits` already covers long text; keep only as a control.

### 34. Format-string-looking identifiers — COVERED/low
`show %s%s%s%s` parses as modulo chain, no crash (my probe). Include only as a cheap negative control; CTF format-string folklore suggested it.

### 35. `ring GF(2^64)` / huge modulus — NEW but graceful
`ring GF(2^64)` printed subfields; `ring Z/0` and `Z/-5` are rejected; `ring Z/18446744073709551616` gives a caret error (my probes). Bug class LIMIT; document as handled rather than spending campaign time.

### 36. `solve ... mod m` with modulus 1 / 0 — NEW
Source: ring edge-case folklore; command `printf 'solve x = 2 mod 1\nsolve x^2 = 1 mod 0\n' | $UC`; bug class WRONG/CRASH; no algebra area reported.

### 37. `legendre`/`jacobi` with even or negative modulus — NEW
`printf 'legendre 2 4\njacobi 2 -3\nlegendre -1 3\n' | $UC` (my `legendre 2 4` probe gave a caret error — check `jacobi`). Bug class WRONG/LIMIT.

### 38. `parity`/`symmetry` of expressions containing `i`, `NaN` — PARTIAL
`fp_edge` found "symmetric AND antisymmetric" for `1e-20*(x+y)`; extend to complex-unit and NaN payload inputs. Command `printf 'identify NaN*x\nsymmetry i*x\n' | $UC`. Bug class WRONG.

### 39. `timeout_s` set to string `"NaN"` / `"-Inf"` / `"1e-400"` / huge int — COVERED mostly
`timeout_isolation` did strings, 0, negative, +Inf; these exact spellings are marginal. Source: nlohmann #5322.

### 40. Signals delivered mid-proof — COVERED BY OTHER AREA
`signal_interrupts/` exists (another subagent); do not duplicate.

### 41. Concurrent JSON clients sharing session state — COVERED BY OTHER AREA
`concurrent_clients/` exists; TOCTOU on `assume`/`defaults` belongs there.

### 42. Witness verification of `differ`/`wrap`/`equiv` counterexamples — COVERED BY OTHER AREA
`witness_verification/` exists; do not duplicate.

### 43. Magic constants (`magic D`, fast inverse sqrt) — COVERED BY OTHER AREA
`magic_constants/` exists; FLOAT_MAGIC.md already has the recipes.

### 44. Exhaustive f16 / NaN modes / subnormals — COVERED BY OTHER AREA
`float_exhaustive/`, `nan_subnormal_modes/` exist; FLOAT_MAGIC.md covers them.

### 45. Deep nesting / 100k identifiers / 20k defs — COVERED
`resource_limits` and `parser_json_fuzz` found stack overflows at 1000–1600 and the quadratic identifier hang. Do not re-run.

### 46. Invalid UTF-8 emitted by ucas from emoji/homoglyph input — COVERED
`nlp_ambiguity` (emoji → raw `0xf0`) and `thesis_nlp_noise_bias` (Cyrillic homoglyph → raw `0xd0`). Idea #5/#6 target *bidi/Tags* input specifically, not a repeat.

### 47. `bench` rdtsc nondeterminism — COVERED
`cfront_fuzz` already reported it.

### 48. Prompt injection inert — COVERED
`nlp_robustness` and `thesis_nlp_noise_bias` tested `ignore previous instructions`; no need to repeat unless Unicode-encoded (ideas #5/#6).

### 49. `expand (1+x)^n` silent no-op above n=64 — COVERED
My probe confirmed `expand (1+x)^70` is a no-op; `resource_limits` already reported it.

### 50. Parsing one lexical error aborts a whole file — COVERED
`parser_json_fuzz` LIMIT; idea #3 is the *semantic-error* variant which does not abort.

---

## Quick probe log (all under `timeout 10`, no campaign)

| Probe | Result | Interpretation |
|---|---|---|
| Doubling defs, depth 13 / 14 / 15 | rc 0 / **139** / **139** | idea #1 confirmed CRASH |
| `show 1+2\0show 3+4` | `_() = 3` | idea #2 confirmed WRONG |
| `f(x:u8)=f(x)` then `show f` | error, then `_(f:real)=f` | idea #3 confirmed STATE |
| MCP `id:1e400` | echoed `1e400` verbatim | idea #4 confirmed PROTO |
| MCP duplicate `id` / duplicate `arguments` key | `-32700`, `id:null` | idea #17 confirmed |
| `is 1 ≤ 2?` / `what is ∫ x...` | `<=` answered / `∫` rejected | idea #7 confirmed NLP asymmetry |
| Bidi U+202E in identifier | `unexpected character '?'`, raw byte echoed | idea #5 actionable |
| U+200B in expression | `unexpected character '?'` | zero-width already partly covered |
| BOM at file start | `unexpected character '?'` | idea #19 actionable |
| `ring Z/0`, `Z/-5`, `factorint 0/-1`, `nthroots 0` | clean errors | negative controls |
| `ring Z/1`, `inverse 0 mod 1`, `dlog 0 base 0 mod 1` | odd but graceful | idea #24 low severity |
| `%s`, huge literal, `count -1`, `steps 0`, `size 0` | graceful | negative controls |

## Ranked top 10 to try first

1. #1 doubling definitions → `show f14(0)` (CONFIRMED rc 139)
2. #2 `printf 'show 1+2\000show 3+4\n' | $UC`
3. #3 `printf 'f(x: u8) = f(x)\nshow f\nfuncs\n' | $UC`
4. #4 MCP `id:1e400`
5. #7 `printf 'is 1 \342\211\244 2?\n' | $UC`
6. #5 bidi override in identifier / English text
7. #17 MCP duplicate JSON key
8. #9 `printf 'what is '; for i in $(seq 400); do printf 'a of '; done; printf 'x?\n'`
9. #13 cyclic basis inheritance
10. #26 `printf 'solve 1 = 2\nsolve x = x\n' | $UC`
