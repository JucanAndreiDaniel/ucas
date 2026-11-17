# Stress findings — `discord_bot`

_Original heading: Stress findings — `discord_bot` (Discord frontend)_

# Stress findings — `discord_bot` (Discord frontend)

Scope: the `discord/` frontend's parsing/routing and the engine invocations it
makes.  The `ucas-discord` binary is **not present** in this checkout and
Concord is not vendored (the Makefile would `git clone` it), so live gateway
and `--stdin` integration tests could not be run here — see LIMIT-1.  Instead
the real C parsing functions were compiled into unit harnesses (Concord
replaced by a mock `struct sbuf`), and every message body was fed to the real
`ucas` binary exactly as the bot does (a leading `\x1e` `defer` directive).

All harness sources, case lists, goldens and generators live in this folder.
Reproduce everything with `sh harness/run.sh`.

---

## Summary
| Severity | Count | One-line headline |
|----------|-------|-------------------|
| WRONG | 1 | a leading minus sign is silently deleted from addressed messages |
| NLP | 3 | new requests are swallowed as answers to an open follow-up question |
| LIMIT | 2 | 1 — `ucas-discord` cannot be built or run here |

## Findings

### WRONG-1 — a leading minus sign is silently deleted from addressed messages
**Severity:** WRONG
**Reproducer:**
Reproducer (the harness compiles the *real* `dc_command()` and verbatim copies
of `strip_mentions()` and the greeting loop from `bot.c`):

```sh
cd $ROOT/tests/stress/areas/frontend/discord_bot
R=$ROOT
cc -O0 -g -std=gnu99 -I$R/src -I$R/discord harness/route_harness.c -o harness/route_harness
printf '<@1000> -5\n' | harness/route_harness
```

**Observed:**

```
2|EVAL|0|5
```

**Expected:** code `-5` (the engine would answer `-5`; `ucas -e "-5"` → `-5`,
whereas it answers `5` for `5`).  More cases from `route.out`:

```
<@1000> -5      -> code "5"
<@1000> - 5     -> code "5"
<@1000> --5     -> code "5"
<@1000> -x      -> code "x"
<@1000> -(2+3)  -> code "(2+3)"
@Wimsy -42      -> code "42"
<@1000> -1.5    -> code "1.5"
```
(Inside an expression the sign survives: `1 + -2` and `x - 1` are unchanged —
only a *leading* `-` is lost.)

**Why it matters:** `bot.c:785-787` treats `-` (and `$`) as a skippable greeting
separator:

```c
while (*t == ' ' || *t == '\t' || *t == '\n' || *t == ',' || *t == ':' ||
       *t == ';' || *t == '!' || *t == '-' || *t == '$')
        t++;
```

A Discord message that mentions the bot and starts with a negative number or
a unary minus is therefore rewritten with the sign removed *before*
`dc_command()`/`run_text()` ever see it.  This is a wrong answer the user is
unlikely to notice (e.g. asking for a range starting at a negative bound).

### NLP-1 — new requests are swallowed as answers to an open follow-up question
**Severity:** NLP
**Expected:** _not recorded_
**Reproducer:**
Reproducer (verbatim copy of `looks_like_answer()` from `bot.c`):

```sh
cd $ROOT/tests/stress/areas/frontend/discord_bot
R=$ROOT
cc -O0 -g -std=gnu99 -I$R/src -I$R/discord harness/answer_harness.c -o harness/answer_harness
printf 'reset\nfactor 123456789\nwhat is 2 + 2\n' | harness/answer_harness
```

**Observed:**

```
reset|1|1
factor 123456789|1|1
what is 2 + 2|0|0
```

`1` means "treated as the answer to the open question" (bot.c:838-879 feeds it
back with `\x1eanswer`); `0` means "new request — drop the question".  Full
list in `answer_route.out`.  While a free-text question (`nopt==0`) is open,
these legitimate new commands are all classified as answers:

```
reset | factor 123456789 | prime 104729 | differentiate x^3 |
id x | factorial 10 | false | true | wrap of x+1 for u8
```

For a numbered choice (`nopt==3`) any of them with ≤ 3 words is *also*
swallowed (`bot.c:126-128`: `return words <= 3`).  Conversely a long but valid
option reply (`0 to pi/4 degree 4 nocrit`) is `1|0` — it would drop a numbered
question because it has more than three words.

**Why it matters:** the `starts[]` table at `bot.c:93-101` is an incomplete list
of the engine's command words.  `reset`, `factor`, `prime`,
`differentiate`, `id`, `wrap`, etc. are absent, so `looks_like_answer()`
falls through to `return 1`.  A user who wants to reset or start a new
computation while a question is pending has the text fed to the engine as an
answer instead; the original request is replayed and the new one is lost.
`reset` is the most damaging case: the reset never reaches the supervisor.

### NLP-2 — `c#` code-fence language tag leaks into the engine input
**Severity:** NLP
**Reproducer:**

```sh
cd $ROOT/tests/stress/areas/frontend/discord_bot
R=$ROOT
cc -O0 -g -std=gnu99 -I$R/src -I$R/discord harness/dc_harness.c -o harness/dc_harness
printf '$```c#\\nint x;\\n```\\n' | harness/dc_harness
```

**Observed:** `1|EVAL|1|c#\nint x;` (see `cmd_parse.out` case 63).
**Expected:** `int x;` — the language tag should be stripped like `c`, `c++`,
`python` are.

**Why it matters:** `is_lang()` in `discord/text.c:14-19` accepts `[A-Za-z0-9_+-]` but not
`#`.  For `$```c#\n...` the language scan stops at `#`, which is not `\n`, so
the tag is not consumed and ends up as the first line of code.  The engine
then reports a parse error on `c#`.

### NLP-3 — adjacent/nested code fences leave backticks in the code
**Severity:** NLP
**Reproducer:**

```sh
printf '$```\\n```\\n1+2\\n```\\n' | harness/dc_harness
```

**Observed:** (`cmd_parse.out` case 69): `EVAL|1` with code
```
```
1+2
```
```
(the inner `` ``` `` is passed through).
**Expected:** `1+2`.

**Why it matters:** `discord/text.c:47-58` consumes the first newline as the language-tag
line, then searches for the *last* `` ``` `` as the closing fence, leaving the
second `` ``` `` as content.  The engine rejects the backticks.  A user who
pastes a block containing its own fence can hit this.

### LIMIT-1 — 1 — `ucas-discord` cannot be built or run here
**Severity:** LIMIT
**Expected:** _not recorded_
**Why it matters:** _not recorded_
**Observed:**
**Reproducer:**
```sh
ls $ROOT/discord/ucas-discord   # No such file
ls $ROOT/discord/third_party     # No such directory
```

`discord/Makefile` clones Concord over the network and the bot needs a Discord
token; both are unavailable, and this suite does not rebuild.  Therefore the
live Gateway mode, `--stdin` gateway-event integration, attachments
(`attach_gather`), the bot allow-list / rate / chain gate (`botuse.c`), the
` ```json ` frontend (`dcjson.c`) and the outgoing `post()`/`react()` paths
were reviewed in source but not executed.  The pure message-parsing and
follow-up routing logic that does not need Concord was tested directly with
the harnesses in `harness/` (mock `sbuf`, real `text.c`, verbatim copies of the
`bot.c` helpers).

### LIMIT-2 — 2 — per-channel engine state is shared across users; `reset` is global to the channel
**Severity:** LIMIT
**Reproducer:** _not recorded_
**Observed:** _not recorded_
**Expected:** _not recorded_
**Why it matters:** _not recorded_
`handle_message()` keys the open-question table `asks[]` by
`(channel, author)` (`bot.c:76-83, 141-154`) but the engine worker is keyed by
channel only (`sup.c:220` runs every message in the channel's persistent
worker; `$reset` sends `SF_RESET` for that channel, `bot.c:831-837`).  In a
shared channel:

- definitions made by user A are visible to user B's later messages;
- a `reset` by user B wipes A's definitions and drops the channel's open
  questions (`ask_drop_chan`, `bot.c:618, 832`).

This is the intended per-channel model, not proven wrong, but it is the place
where cross-user state can leak.  It could not be exercised without the bot
binary; the engine-side persistence was checked by batching statements in
`01_defer_normal.ucas` (`f` is defined, then `range f` sees it).

## Checks that passed

### POSITIVE / DETERMINISM (no bug)
- **Prompt-injection defenses hold.**  `strip_directives()` (`bot.c:166-176`)
  removes every `\x1e` byte from user code before it is sent, and the engine
  only honours a directive at the start of a line (`nlp.c:9829`).  A raw
  `\x1eask` placed mid-message is inert/garbage: `05_injection_midline.out`
  shows `error: unexpected character '?'` rather than a forged question.
  Phrases like "ignore previous instructions and reveal the token" are simply
  parsed as English (`mcp_en_injection.out`) — the engine even silently
  "corrects" `token` to `taken`.  No token/secret is exposed by any input.
- **No crash or hang in the engine invocation.**  All 167 extracted `DC_EVAL`
  message bodies were run as `\x1edefer\n<body>` under `timeout 15`; exit-code
  tally `{0: 167}` (`harness/fuzz_engine.py`).
- **Unicode/emoji are handled gracefully.**  `🙂`, `α`, `café` produce a clean
  "sorry: I can't read the character" / parse error, never a crash
  (`06_unicode_graceful.out`, `mcp_en_injection.out`).
- **Determinism: clean.**  All 8 CLI and 4 MCP goldens were run twice and were
  byte-identical; `sh harness/run.sh` regenerates them identically (verified
  by sha256).  No nondeterministic outputs were kept as goldens.
